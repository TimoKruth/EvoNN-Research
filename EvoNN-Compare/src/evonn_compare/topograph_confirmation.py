"""Explicit confirmation restart after legacy resource-admission repair.

Execute a copy outside a clean producer; keep historical studies immutable.
All confirmation cells are repeated under one repaired source identity.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from evonn_compare import campaign as c, topograph_study as s
from evonn_shared.engine_evidence import artifact_json
from evonn_shared.export_reader import read_export


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


def validate_screening(report, nomination):
    evidence = {k: v for k, v in report.items() if k != 'limits'}
    if (evidence['status'] != 'complete' or evidence['failures'] or evidence['missing']
            or c.sha(evidence) != nomination['screening_sha256']
            or s.choose_nominee(evidence['results'])[0] != nomination['nominee']):
        raise ValueError('nomination differs from complete frozen screening')


def prepare(root, parent, patch):
    if root.exists():
        raise ValueError('fresh confirmation directory required')
    plan = s.read_plan(parent)
    nomination = s.read_signed(parent, 'nomination.json')
    screening_path = parent.parent / 'screening-report.json'
    screening = json.loads(screening_path.read_text())
    validate_screening(screening, nomination)
    if nomination['study_sha256'] != plan['sha256']:
        raise ValueError('nomination study mismatch')
    rows = s.stage_rows(parent, plan, 'confirmation')
    identity = c.identity()
    actual_patch = subprocess.check_output(['git', 'diff', '--no-ext-diff', plan['identity']['commit'], identity['commit']], cwd=c.ROOT)
    if actual_patch != patch.read_bytes():
        raise ValueError('producer differs from reviewed repair patch')
    for key in ('host', 'versions', 'data_files'):
        if identity[key] != plan['identity'][key]:
            raise ValueError('host/runtime/catalog drift')
    bound = [parent / 'study.json', parent / 'nomination.json', parent / 'confirmation.json',
             screening_path, parent.parent / 'qualification-report.json', patch]
    # The signed nominee binds a report created by full export validation. Bind
    # each originating export's document digests and passed replay as well.
    for stage in ('qualification', 'screening'):
        report = json.loads((parent.parent / (stage + '-report.json')).read_text())
        declared = [r for r in plan['matrix'] if r['campaign'].startswith(stage + '/')]
        expected = {(r['arm'], r['seed'], r['pack']): r for r in declared}
        if report['status'] != 'complete' or len(report['results']) != len(expected):
            raise ValueError('incomplete prior stage')
        seen = set()
        for result in report['results']:
            key = (result['arm'], result['seed'], result['pack'])
            if key not in expected or key in seen:
                raise ValueError('duplicate or unexpected prior result')
            seen.add(key)
            campaign = parent / expected[key]['campaign']
            replay = s.read_signed(campaign, 'winner-replay.json')
            if replay['reference'] != result['reference'] or replay['result']['status'] != 'passed':
                raise ValueError('historical winner replay mismatch')
            bound += [campaign / 'campaign.json', campaign / 'winner-replay.json']
            export = campaign / result['reference']['export']
            for document in result['reference']['documents']:
                path = export / document['path']
                if digest(path) != document['sha256']:
                    raise ValueError('historical export receipt mismatch')
                bound.append(path)
    retained = []
    for row in rows:
        old_campaign = parent / row['campaign']
        bound.append(old_campaign / 'campaign.json')
        for run in (old_campaign / 'runs').glob('*/*'):
            if not run.is_dir():
                continue
            attempts = json.loads((run / 'attempts.json').read_text())['attempts']
            failed = [a for a in attempts if a['status'] != 'ok']
            if failed and any(a.get('reason') != 'invalid pre-fit candidate: compiled candidate exceeds local runtime parameter safety cap'
                              or a['charged'] != 0 for a in failed):
                raise ValueError('unexpected historical confirmation failure')
            retained.append(dict(campaign=row['campaign'], run=str(run), charged_fits=sum(a['charged'] for a in attempts),
                                 rejected_candidates=len(failed), successful_fits=sum(a['status'] == 'ok' for a in attempts),
                                 successful_training_seconds=sum(a.get('train_seconds', 0.) for a in attempts)))
            bound.extend(run / name for name in ('attempts.json', 'state.json', 'summary.json', 'config.yaml'))
            bound.extend(run / 'symbiosis' / name for name in ('manifest.json', 'results.json', 'summary.json'))
    if not any(r['rejected_candidates'] for r in retained):
        raise ValueError('diagnosed cap rejection required')
    root.mkdir(parents=True)
    hashes = {}
    for row in rows:
        original = c.read_manifest(parent / row['campaign'])
        campaign = root / row['campaign']
        value = {k: v for k, v in original.items() if k != 'sha256'}
        value.update(identity=identity, workspace=str(campaign.absolute()))
        with c.lease(campaign):
            s.publish_json(campaign / 'campaign.json', s.signed(value))
        hashes[row['campaign']] = c.read_manifest(campaign)['sha256']
    document = dict(schema='evonn.topograph-confirmation-repair/v1', parent=str(parent),
                    parent_sha256=plan['sha256'], nominee=nomination['nominee'], rows=rows,
                    identity=identity, campaign_sha256=hashes, bound_documents=bind_documents(bound),
                    controller_sha256=digest(Path(__file__)), retained_confirmation=retained,
                    interpretation='All 128 confirmation cells restart under the resource-admission repair. Original confirmation remains incomplete and excluded from inference; its cost and failures are retained. Screening nomination, paired seeds, fit/epoch budgets, safety caps and inference stay fixed. Legacy now retains its valid parent when a proposed mutation exceeds the existing parameter cap. Conclusions concern this amended legacy control. No isolated wall-time or cross-engine claim.')
    s.publish_json(root / 'continuation.json', s.signed(document))
    return preflight(root, datasets=True)


def preflight(root, *, datasets=False):
    plan = s.read_signed(root, 'continuation.json')
    if plan['schema'] != 'evonn.topograph-confirmation-repair/v1' or plan['controller_sha256'] != digest(Path(__file__)):
        raise ValueError('continuation/controller drift')
    if c.identity() != plan['identity']:
        raise ValueError('producer/environment drift')
    verify_documents(plan['bound_documents'])
    if plan['rows'] != s.matrix('confirmation', plan['nominee']):
        raise ValueError('confirmation protocol drift')
    verified = set()
    for row in plan['rows']:
        campaign = root / row['campaign']
        manifest = c.read_manifest(campaign)
        if (manifest['sha256'] != plan['campaign_sha256'][row['campaign']]
                or manifest['spec'] != row['spec'] or manifest['identity'] != plan['identity']):
            raise ValueError('campaign drift')
        key = c.sha(manifest['datasets'])
        if datasets and key not in verified:
            c.preflight(campaign)
            verified.add(key)
    return dict(status='ready', declared=len(plan['rows']), nominee=plan['nominee'])


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


def report(root):
    preflight(root)
    plan = s.read_signed(root, 'continuation.json')
    results = []
    for row in plan['rows']:
        campaign = root / row['campaign']
        receipt = saved_receipt(campaign)
        if receipt is None:
            raise ValueError('incomplete confirmation; no inference')
        manifest = c.read_manifest(campaign)
        case, system = c.slots(c.CampaignSpec.model_validate(row['spec']))[0]
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
                                         for b in bundle.summary.best_per_benchmark}, reference=reference))
    value = dict(status='complete', declared=len(plan['rows']), completed=len(results),
                 results=results, contrasts=s.inference(results, plan['nominee']),
                 interpretation=plan['interpretation'], retained_confirmation=plan['retained_confirmation'])
    write(root / 'report.json', value)
    return value


def run(root):
    with c.lease(root):
        preflight(root)
        plan = s.read_signed(root, 'continuation.json')
        completed = 0
        try:
            for row in plan['rows']:
                if (root / 'PAUSE').exists():
                    return status(root, 'paused', completed=completed, declared=len(plan['rows']))
                campaign = root / row['campaign']
                if saved_receipt(campaign) is not None:
                    completed += 1
                    continue
                status(root, 'running', completed=completed, declared=len(plan['rows']), active=row['campaign'])
                # Each single-cell campaign has its own complete bounded window.
                c.run_campaign(campaign, max_runs=1, session_timeout=1800)
                manifest = c.read_manifest(campaign)
                case, system = c.slots(c.CampaignSpec.model_validate(row['spec']))[0]
                trained, reference = c.adopted(campaign, manifest, case, system)
                if reference is None:
                    raise ValueError('campaign did not complete; retain evidence')
                replay = subprocess.run([sys.executable, '-m', 'topograph.cli', 'replay', str(trained)],
                                        capture_output=True, text=True, timeout=120)
                if replay.returncode:
                    raise ValueError('winner replay failed: ' + replay.stderr[-2000:])
                result = json.loads(replay.stdout)
                if result['status'] != 'passed':
                    raise ValueError('winner replay did not pass')
                s.publish_json(campaign / 'winner-replay.json', s.signed(dict(reference=reference, result=result)))
                completed += 1
                status(root, 'running', completed=completed, declared=len(plan['rows']), active=None)
            if (root / 'PAUSE').exists():
                return status(root, 'paused', completed=completed, declared=len(plan['rows']))
            status(root, 'validating_report', completed=completed, declared=len(plan['rows']))
            report(root)
            return status(root, 'complete', completed=completed, declared=len(plan['rows']), report=str(root / 'report.json'))
        except Exception as error:
            status(root, 'failed', completed=completed, declared=len(plan['rows']), error=str(error))
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
