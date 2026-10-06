"""Budget-time continuation; retain verified cells and all failed evidence.

Run a frozen copy outside the producer. The per-fit cap stays unchanged.
"""
import argparse
from copy import deepcopy
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from evonn_compare import campaign as c, topograph_study as s
from evonn_shared.engine_evidence import artifact_json
from evonn_shared.export_reader import read_export
from evonn_shared.runtime_journal import load_runtime_checkpoint

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)

def status(root, mode, **fields):
    value = dict(status=mode, updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), **fields)
    write(root / 'status.json', value)
    return value

def bind_documents(paths):
    return {str(path.absolute()): digest(path) for path in paths}

def verify_documents(documents):
    for path, expected in documents.items():
        if digest(Path(path)) != expected:
            raise ValueError('bound evidence changed: ' + path)

def saved_receipt(campaign):
    path = campaign / 'winner-replay.json'
    if not path.exists():
        return None
    replay = s.read_signed(campaign, 'winner-replay.json')
    if replay['result']['status'] != 'passed':
        raise ValueError('winner replay failed')
    reference = replay['reference']
    export = campaign / reference['export']
    for document in reference['documents']:
        if digest(export / document['path']) != document['sha256']:
            raise ValueError('completed export document drift')
    manifest = c.read_manifest(campaign)
    completions = [event['details'] for event in c.events(campaign, manifest) if event['kind'] == 'complete']
    if completions != [reference]:
        raise ValueError('completion journal disagrees with replay receipt')
    return reference


def amended_rows(rows, inherited):
    output = deepcopy(rows)
    for row in output:
        if row['campaign'] not in inherited:
            spec = row['spec']
            allowance = spec['budgets'][0] * (spec['fit_timeout'] + 30) + 600
            if not 0 < allowance <= 43200:
                raise ValueError('derived run allowance outside engine bound')
            spec['timeout'] = allowance
    return output


def campaign_path(root, plan, row):
    origin = Path(plan['parent']) if row['campaign'] in plan['inherited'] else root
    return origin / row['campaign']


def admit_origin(parent, campaign):
    """Historical exports must be admitted by their original frozen producer."""
    producer = parent.parent / 'producer'
    program = '''import json,sys
from pathlib import Path
from evonn_compare import campaign as c
p=Path(sys.argv[1]); c.preflight(p); m=c.read_manifest(p)
case,system=c.slots(c.CampaignSpec.model_validate(m['spec']))[0]
run,reference=c.adopted(p,m,case,system)
print(json.dumps({'run':str(run) if run is not None else None,'reference':reference}))
'''
    result = subprocess.run([str(producer / '.venv/bin/python'), '-c', program, str(campaign)],
                            cwd=producer, capture_output=True, text=True, check=True, timeout=1800)
    value = json.loads(result.stdout)
    return (Path(value['run']) if value['run'] is not None else None), value['reference']


def prepare(root, parent, patch):
    if root.exists():
        raise ValueError('fresh continuation directory required')
    previous = s.read_signed(parent, 'continuation.json')
    if previous['schema'] != 'evonn.topograph-confirmation-repair/v1':
        raise ValueError('expected resource-admission confirmation ancestry')
    if previous['rows'] != s.matrix('confirmation', previous['nominee']):
        raise ValueError('original confirmation matrix changed')
    verify_documents(previous['bound_documents'])
    identity = c.identity()
    actual_patch = subprocess.check_output(['git', 'diff', '--no-ext-diff', previous['identity']['commit'], identity['commit']], cwd=c.ROOT)
    if actual_patch != patch.read_bytes():
        raise ValueError('producer differs from reviewed timeout-only patch')
    for key in ('host', 'versions', 'data_files'):
        if identity[key] != previous['identity'][key]:
            raise ValueError('host/runtime/catalog drift')
    bound = [parent / 'continuation.json', parent / 'status.json', patch]
    inherited, failures = {}, []
    for row in previous['rows']:
        campaign = parent / row['campaign']
        manifest = c.read_manifest(campaign)
        if manifest['sha256'] != previous['campaign_sha256'][row['campaign']]:
            raise ValueError('ancestor campaign drift')
        bound.append(campaign / 'campaign.json')
        reference = saved_receipt(campaign)
        if reference is not None:
            _, verified = admit_origin(parent, campaign)
            if verified != reference:
                raise ValueError('inherited export failed full admission')
            inherited[row['campaign']] = reference
            bound.append(campaign / 'winner-replay.json')
            bound.extend(campaign / reference['export'] / d['path'] for d in reference['documents'])
            continue
        runs = list((campaign / 'runs').glob('*/*'))
        if not runs:
            continue
        if len(runs) != 1:
            raise ValueError('ambiguous failed run')
        run = runs[0]
        state = json.loads((run / 'state.json').read_text())
        attempts = json.loads((run / 'attempts.json').read_text())['attempts']
        failed = [a for a in attempts if a['status'] != 'ok']
        if (state['elapsed'] < row['spec']['timeout'] or not failed
                or any(a['reason'] != 'isolated worker wall-clock cap exceeded' for a in failed)):
            raise ValueError('only diagnosed cumulative-budget exhaustion may restart')
        for attempt in failed:
            request = json.loads((run / attempt['directory'] / 'request.json').read_text())
            if request['training']['timeout'] >= row['spec']['fit_timeout']:
                raise ValueError('failure was not shortened by cumulative run limit')
            bound.append(run / attempt['directory'] / 'request.json')
        failures.append(dict(campaign=row['campaign'], run=str(run), charged_fits=sum(a['charged'] for a in attempts),
                             successful_fits=sum(a['status'] == 'ok' for a in attempts),
                             failed_fits=len(failed), successful_training_seconds=sum(a.get('train_seconds', 0.) for a in attempts)))
        bound.extend(run / name for name in ('attempts.json', 'state.json', 'config.yaml', 'summary.json'))
    if not failures:
        raise ValueError('diagnosed failed cell required')
    rows = amended_rows(previous['rows'], inherited)
    root.mkdir(parents=True)
    hashes = {}
    for row in rows:
        if row['campaign'] in inherited:
            continue
        campaign = root / row['campaign']
        original = c.read_manifest(parent / row['campaign'])
        value = {k: v for k, v in original.items() if k != 'sha256'}
        value.update(identity=identity, spec=row['spec'], workspace=str(campaign.absolute()))
        with c.lease(campaign):
            s.publish_json(campaign / 'campaign.json', s.signed(value))
        hashes[row['campaign']] = c.read_manifest(campaign)['sha256']
    document = dict(schema='evonn.topograph-budget-resume/v1', parent=str(parent),
                    parent_sha256=previous['sha256'], nominee=previous['nominee'], rows=rows,
                    identity=identity, campaign_sha256=hashes, inherited=inherited,
                    bound_documents={**previous['bound_documents'], **bind_documents(bound)},
                    controller_sha256=digest(Path(__file__)), segment_fits=32,
                    retained_confirmation=[*previous['retained_confirmation'], *failures],
                    interpretation='The two verified confirmation cells retain their original identities and safety caps. Unfinished cells receive budget*(fit_timeout+30)+600 seconds, with the original per-fit cap, model, optimizer, epoch, seed, fit-count, nominee and inference settings. The exhausted failed cell restarts in a fresh location; all failed work is retained and charged separately. Checkpoint boundaries every 32 fits allow pauses. Mixed total safety caps and producer identities; no equal-wall-time claim. Legacy is the resource-admission-repaired control.')
    s.publish_json(root / 'continuation.json', s.signed(document))
    status(root, 'prepared', completed=len(inherited), declared=len(rows), inherited=len(inherited))
    return preflight(root, datasets=True)


def preflight(root, *, datasets=False):
    plan = s.read_signed(root, 'continuation.json')
    if plan['schema'] != 'evonn.topograph-budget-resume/v1' or plan['controller_sha256'] != digest(Path(__file__)):
        raise ValueError('continuation/controller drift')
    if c.identity() != plan['identity']:
        raise ValueError('producer/environment drift')
    verify_documents(plan['bound_documents'])
    previous = s.read_signed(Path(plan['parent']), 'continuation.json')
    if (previous['sha256'] != plan['parent_sha256'] or plan['nominee'] != previous['nominee']
            or plan['rows'] != amended_rows(previous['rows'], plan['inherited']) or plan['segment_fits'] != 32):
        raise ValueError('protocol amendment drift')
    verified = set()
    for row in plan['rows']:
        campaign = campaign_path(root, plan, row)
        manifest = c.read_manifest(campaign)
        inherited = row['campaign'] in plan['inherited']
        expected = previous if inherited else plan
        if (manifest['sha256'] != expected['campaign_sha256'][row['campaign']]
                or manifest['spec'] != row['spec'] or manifest['identity'] != expected['identity']):
            raise ValueError('campaign drift')
        if inherited and saved_receipt(campaign) != plan['inherited'][row['campaign']]:
            raise ValueError('inherited receipt changed')
        key = c.sha(manifest['datasets'])
        if datasets and not inherited and key not in verified:
            c.preflight(campaign)
            verified.add(key)
    return dict(status='ready', declared=len(plan['rows']), inherited=len(plan['inherited']), nominee=plan['nominee'])


def checkpoint_progress(run):
    _, payload = load_runtime_checkpoint(run / 'checkpoints')
    state = json.loads(payload)
    if any(a['status'] != 'ok' or a['charged'] != 1 for a in state['attempts']):
        raise ValueError('failed attempt retained; no automatic retry')
    return state['completed']


def dispatch_segment(root, campaign, row, lease_fd, segment_fits):
    """Use the native committed checkpoint contract; never kill a fit to pause."""
    with c.lease(campaign) as campaign_fd:
        c.preflight(campaign)
        manifest = c.read_manifest(campaign)
        spec = c.CampaignSpec.model_validate(row['spec'])
        case, system = c.slots(spec)[0]
        slot = c.slot_id(case, system)
        history = c.events(campaign, manifest)
        c.active_dispatch(campaign, history, slot)
        run, reference = c.adopted(campaign, manifest, case, system)
        if reference is not None:
            if not any(e['kind'] == 'complete' for e in history):
                c.append_event(campaign, manifest, history, slot, 'complete', reference)
            return run, reference, case.budget
        before = checkpoint_progress(run) if run is not None else 0
        target = min(case.budget, before + segment_fits)
        output = campaign / 'runs' / slot
        command = [sys.executable, '-m', 'topograph.cli', 'run', '--pack', case.pack,
                   '--budget', str(case.budget), '--seed', str(case.seed), '--output', str(output),
                   '--cache', manifest['cache'], '--timeout', str(spec.timeout), '--fit-timeout', str(spec.fit_timeout),
                   '--backend', spec.backend, '--epochs', str(spec.epochs), '--variant', spec.topograph_variant,
                   '--stop-after', str(target)]
        if spec.topograph_research is not None:
            command += ['--research-options', json.dumps(spec.topograph_research.model_dump(mode='json'), sort_keys=True)]
        if run is not None:
            command += ['--resume', str(run)]
        if (root / 'PAUSE').exists():
            return run, None, before
        event = c.append_event(campaign, manifest, history, slot, 'dispatch', {'command': command})
        work = campaign / 'dispatch'
        work.mkdir(exist_ok=True)
        description = work / f"{event['sequence']:06d}.json"
        s.publish_json(description, event)
        limit = min(spec.timeout + 20, (target - before) * (spec.fit_timeout + 30) + 600)
        c._bounded_process([sys.executable, '-m', 'evonn_compare.campaign_worker', 'dispatch', str(description), str(campaign_fd)],
                           limit, work / f"{event['sequence']:06d}.log", pass_fds=(lease_fd, campaign_fd))
        run, reference = c.adopted(campaign, manifest, case, system)
        if run is None or checkpoint_progress(run) != target:
            raise ValueError('segment did not reach committed target; retained for inspection')
        if reference is not None:
            c.append_event(campaign, manifest, history, slot, 'complete', reference)
        elif target == case.budget:
            raise ValueError('missing complete export at full budget')
        return run, reference, target


def report(root):
    preflight(root)
    plan = s.read_signed(root, 'continuation.json')
    results = []
    for row in plan['rows']:
        campaign = campaign_path(root, plan, row)
        receipt = saved_receipt(campaign)
        if receipt is None:
            raise ValueError('incomplete confirmation; no inference')
        manifest = c.read_manifest(campaign)
        case, system = c.slots(c.CampaignSpec.model_validate(row['spec']))[0]
        if row['campaign'] in plan['inherited']:
            run, reference = admit_origin(Path(plan['parent']), campaign)
        else:
            run, reference = c.adopted(campaign, manifest, case, system)
        if reference != receipt:
            raise ValueError('completed evidence drift')
        bundle = read_export(run / 'symbiosis')
        attempts = artifact_json(bundle, 'attempts.json')['attempts']
        results.append(dict(arm=row['arm'], seed=row['seed'], pack=row['pack'],
                            metrics={b.benchmark_id: b.value for b in bundle.summary.best_per_benchmark},
                            train_seconds=sum(a['train_seconds'] for a in attempts),
                            updates=sum(a['updates'] for a in attempts),
                            model_bytes={b.benchmark_id: next(a['model_bytes'] for a in attempts if a['outcome_id'] == b.outcome_id)
                                         for b in bundle.summary.best_per_benchmark}, reference=reference,
                            origin=str(campaign), inherited=row['campaign'] in plan['inherited']))
    value = dict(status='complete', declared=len(plan['rows']), completed=len(results),
                 results=results, contrasts=s.inference(results, plan['nominee']),
                 interpretation=plan['interpretation'], retained_confirmation=plan['retained_confirmation'])
    write(root / 'report.json', value)
    return value


def run(root):
    with c.lease(root) as lease_fd:
        completed = 0
        try:
            preflight(root)
            plan = s.read_signed(root, 'continuation.json')
            completed = sum(saved_receipt(campaign_path(root, plan, r)) is not None for r in plan['rows'])
            for row in plan['rows']:
                campaign = campaign_path(root, plan, row)
                if saved_receipt(campaign) is not None:
                    continue
                while True:
                    if (root / 'PAUSE').exists():
                        return status(root, 'paused', completed=completed, declared=len(plan['rows']))
                    status(root, 'running', completed=completed, declared=len(plan['rows']), active=row['campaign'])
                    trained, reference, progress = dispatch_segment(root, campaign, row, lease_fd, plan['segment_fits'])
                    status(root, 'running', completed=completed, declared=len(plan['rows']), active=row['campaign'], active_fits=progress)
                    if reference is not None:
                        break
                replay = subprocess.run([sys.executable, '-m', 'topograph.cli', 'replay', str(trained)],
                                        capture_output=True, text=True, timeout=120)
                if replay.returncode:
                    raise ValueError('winner replay failed: ' + replay.stderr[-2000:])
                result = json.loads(replay.stdout)
                if result['status'] != 'passed':
                    raise ValueError('winner replay did not pass')
                s.publish_json(campaign / 'winner-replay.json', s.signed(dict(reference=reference, result=result)))
                completed += 1
            if (root / 'PAUSE').exists():
                return status(root, 'paused', completed=completed, declared=len(plan['rows']))
            status(root, 'validating_report', completed=completed, declared=len(plan['rows']))
            report(root)
            return status(root, 'complete', completed=completed, declared=len(plan['rows']), report=str(root / 'report.json'))
        except Exception as error:
            status(root, 'failed', completed=completed, error=str(error))
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'preflight', 'run', 'resume', 'pause', 'report'))
    parser.add_argument('workspace', type=Path)
    parser.add_argument('--parent', type=Path)
    parser.add_argument('--patch', type=Path)
    args = parser.parse_args()
    root = args.workspace.absolute()
    if args.action == 'prepare':
        if args.parent is None or args.patch is None:
            parser.error('--parent and --patch required')
        result = prepare(root, args.parent.absolute(), args.patch.absolute())
    elif args.action == 'preflight':
        result = preflight(root, datasets=True)
    elif args.action == 'report':
        result = report(root)
    elif args.action == 'pause':
        (root / 'PAUSE').touch()
        result = dict(status='pause_requested')
    else:
        if args.action == 'resume':
            preflight(root)
            (root / 'PAUSE').unlink(missing_ok=True)
        result = run(root)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
