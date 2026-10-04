"""Explicit fixed-fit continuation after the original Primordia wall cap exhausted."""
import argparse
import json
from pathlib import Path
import subprocess
import uuid

from evonn_shared.artifact_io import publish_artifact
from evonn_shared.export_reader import read_export
from evonn_shared.runtime_io import derived
from . import campaign as c
from . import primordia_study as study
from .audit import artifact_json
from .baseline_study import validate_replay

TOTAL_SECONDS = 36000.0
VERIFIED_PREPARATION_SHA = "d5dd4415c0097c4a829caa5755d5af214153f17053c30874c58d9c75566ac8a6"


def key(item):
    return f"{item['campaign']}/{item['seed']}"


def read(root):
    value = json.loads(c.read_document(root, 'continuation.json'))
    if value['sha256'] != c.sha({k: v for k, v in value.items() if k != 'sha256'}):
        raise ValueError('continuation manifest checksum drift')
    if value['schema_version'] != 'evonn.primordia-time-amendment/v1' or value['total_seconds'] != TOTAL_SECONDS:
        raise ValueError('unsupported time amendment')
    parent = study.read_plan(Path(value['parent']))
    if parent['sha256'] != value['parent_sha256'] or value['schedule'] != study.schedule('comparison'):
        raise ValueError('parent protocol or schedule drift')
    if c.identity() != value['identity']:
        raise ValueError('continuation producer/environment drift')
    for campaign, digest in value['campaigns'].items():
        if c.read_manifest(root/campaign)['sha256'] != digest:
            raise ValueError('continuation campaign drift')
    for name, digest in value['retained_failure']['documents'].items():
        if c.hashlib.sha256((Path(value['retained_failure']['run'])/name).read_bytes()).hexdigest() != digest:
            raise ValueError('retained failed-run evidence drift')
    return value


def observation(workspace, item):
    manifest = c.read_manifest(workspace)
    case = c.Case(item['pack'], 256, item['seed'])
    run, reference = c.adopted(workspace, manifest, case, 'primordia')
    if reference is None:
        return run, None
    replay = json.loads(c.read_document(workspace/'replays', case.id+'.json'))
    if replay['reference'] != reference:
        raise ValueError('replay reference drift')
    validate_replay(replay['replay'], reference['run_id'], case.pack)
    bundle = read_export(run/'symbiosis')
    attempts = artifact_json(bundle, 'trial_records.json')
    if len(attempts) != 256 or any(a['status'] != 'ok' or a['charged'] != 1 for a in attempts):
        raise ValueError('failed or incomplete attempts')
    winners = artifact_json(bundle, 'best_results.json')
    return run, {**item, 'reference': reference, 'scores': {b: v['quality'] for b, v in winners.items()},
                 'train_seconds': sum(a['train_seconds'] for a in attempts),
                 'optimizer_updates': sum(a['updates'] for a in attempts)}



def parent_snapshot(parent):
    """Historical config paths are verified only in their original producer."""
    plan = study.read_plan(parent)
    program = """
import json, sys
from pathlib import Path
from evonn_compare import primordia_study as study
from evonn_compare import campaign as c
root = Path(sys.argv[1])
plan = study.read_plan(root)
if c.identity() != plan['identity']:
    raise ValueError('historical producer/environment drift')
qualification, qmissing = study.collect(root, 'qualification')
comparison, missing = study.collect(root, 'comparison')
print(json.dumps(dict(qualification=qualification, qmissing=qmissing, comparison=comparison, missing=missing)))
"""
    result = subprocess.run([plan['identity']['python'], '-c', program, str(parent)],
                            cwd=Path(plan['identity']['python']).parents[2], check=True,
                            capture_output=True, text=True, timeout=900)
    return json.loads(result.stdout)


def prepare(root, parent):
    root, parent = root.absolute(), parent.absolute()
    if root.exists():
        raise ValueError('use a fresh continuation directory')
    original = study.read_plan(parent)
    # Verify the original frozen environment with its own interpreter.
    subprocess.run([original['identity']['python'], '-m', 'evonn_compare.primordia_study', 'preflight', str(parent)],
                   cwd=Path(original['identity']['python']).parents[2], check=True)
    snapshot = parent_snapshot(parent)
    qualification, qmissing = snapshot['qualification'], snapshot['qmissing']
    inherited, missing = snapshot['comparison'], snapshot['missing']
    if qmissing or len(qualification) != 26 or not missing:
        raise ValueError('requires fully qualified but incomplete original study')
    failures = []
    for item in missing:
        workspace = parent/item['campaign']
        run, reference = c.adopted(workspace, c.read_manifest(workspace), c.Case(item['pack'], 256, item['seed']), 'primordia')
        if run is not None:
            state = json.loads(c.read_document(run, 'state.json'))
            if reference is not None or not (0 < state['completed'] < 256 and state['elapsed'] >= 1740):
                raise ValueError('unexpected interruption; amendment only covers exhausted original total cap')
            if any(a['status'] != 'ok' for a in state['attempts']):
                raise ValueError('failed fits require separate diagnosis')
            failures.append(dict(run=str(run), completed_attempts=state['completed'], elapsed=state['elapsed'],
                measured_train_seconds=sum(a['train_seconds'] for a in state['attempts']),
                documents={n: c.hashlib.sha256((run/n).read_bytes()).hexdigest()
                           for n in ('config.yaml', 'state.json', 'summary.json', 'trial_records.json')}))
    if len(failures) != 1:
        raise ValueError('expected exactly one diagnosed exhausted slot')
    pinned = c.identity()
    root.mkdir(parents=True)
    inherited_map = {key(item): item for item in inherited}
    campaigns = {}
    for row in original['matrix']:
        if row['phase'] != 'comparison':
            continue
        selected = [i['seed'] for i in study.schedule('comparison')
                    if i['campaign'] == row['campaign'] and key(i) not in inherited_map]
        if not selected:
            continue
        prior = c.read_manifest(parent/row['campaign'])
        spec = c.CampaignSpec.model_validate({**prior['spec'], 'seeds': selected, 'timeout': TOTAL_SECONDS})
        workspace = root/row['campaign']
        value = dict(schema_version='evonn.campaign/v1', spec=spec.model_dump(mode='json'), identity=pinned,
                     cache=prior['cache'], workspace=str(workspace),
                     datasets=[d for d in prior['datasets'] if d['seed'] in selected])
        with c.lease(workspace):
            publish_artifact(workspace/'campaign.json', c.encoded({**value, 'sha256': c.sha(value)}))
        campaigns[row['campaign']] = c.preflight(workspace)['manifest_sha256']
    if c.identity() != pinned:
        raise ValueError('producer drift during amendment preparation')
    value = dict(schema_version='evonn.primordia-time-amendment/v1', parent=str(parent), parent_sha256=original['sha256'],
                 identity=pinned, total_seconds=TOTAL_SECONDS, campaigns=campaigns,
                 inherited=inherited_map, qualification=qualification, retained_failure=failures[0],
                 schedule=study.schedule('comparison'),
                 authorization='User requested fix and resume after diagnosed time exhaustion, 2026-09-21.',
                 amendment='Uniform 36000-second cumulative safety cap for every unfinished slot, in sessions <=1740 seconds. Fit/epoch/seed/architecture settings unchanged. Exhausted original slot restarted once, with its 248 original attempts retained and charged separately.',
                 interpretation='Amended fixed-fit comparison; reuse completed original runs. Original study remains incomplete. Mixed time caps and producer revisions; no equal-wall-time or protected-test claim. Original paired inference policy retained.')
    publish_artifact(root/'continuation.json', c.encoded({**value, 'sha256': c.sha(value)}))
    return dict(status='prepared', inherited_comparisons=len(inherited), remaining=416-len(inherited))



def verify_cached_parent(plan):
    cache = plan['verified_preparation']
    if cache['sha256'] != VERIFIED_PREPARATION_SHA:
        raise ValueError('unrecognized verified preparation')
    previous = json.loads(c.read_document(Path(cache['root']), 'continuation.json'))
    if (previous['sha256'] != cache['sha256'] or previous['sha256'] != c.sha({k: v for k, v in previous.items() if k != 'sha256'})
            or previous['parent_sha256'] != plan['parent_sha256']
            or previous['inherited'] != plan['inherited'] or previous['qualification'] != plan['qualification']
            or previous['retained_failure'] != plan['retained_failure']):
        raise ValueError('verified preparation receipt drift')
    # The prior frozen producer already performed the full semantic audit. Verify
    # every hash-bound export byte again, including all model/data artifacts.
    parent = Path(plan['parent'])
    for row in [*plan['qualification'], *plan['inherited'].values()]:
        workspace = parent/row['campaign']
        reference = row['reference']
        export = workspace/reference['export']
        for doc in reference['documents']:
            if c.hashlib.sha256(c.read_document(export, doc['path'])).hexdigest() != doc['sha256']:
                raise ValueError('verified historical document changed')
        read_export(export)
        case = c.Case(row['pack'], 64 if row['phase'] == 'qualification' else 256, row['seed'])
        payload = c.read_document(workspace/'replays', case.id+'.json')
        if c.hashlib.sha256(payload).hexdigest() != cache['replays'][key(row)]:
            raise ValueError('historical replay bytes changed')
        replay = json.loads(payload)
        if replay['reference'] != reference:
            raise ValueError('historical replay reference changed')
        validate_replay(replay['replay'], reference['run_id'], row['pack'])


def prepare_from_verified(root, previous_root):
    root, previous_root = root.absolute(), previous_root.absolute()
    previous = json.loads(c.read_document(previous_root, 'continuation.json'))
    if previous['sha256'] != VERIFIED_PREPARATION_SHA or previous['sha256'] != c.sha({k: v for k, v in previous.items() if k != 'sha256'}):
        raise ValueError('preparation checksum drift')
    if previous['schema_version'] != 'evonn.primordia-time-amendment/v1' or previous['schedule'] != study.schedule('comparison'):
        raise ValueError('unsupported prepared amendment')
    if list(previous_root.glob('comparison/*/*/runs')):
        raise ValueError('cannot replace a continuation that has started training')
    if root.exists():
        raise ValueError('use a fresh study directory')
    # Bind the exact completed semantic audit and replay files from the preserved
    # preparation; no model evidence is copied, changed or reselected.
    parent = Path(previous['parent'])
    replays = {}
    for row in [*previous['qualification'], *previous['inherited'].values()]:
        case = c.Case(row['pack'], 64 if row['phase'] == 'qualification' else 256, row['seed'])
        payload = c.read_document(parent/row['campaign']/'replays', case.id+'.json')
        replays[key(row)] = c.hashlib.sha256(payload).hexdigest()
    value = {**previous, 'verified_preparation': dict(root=str(previous_root), sha256=previous['sha256'], replays=replays),
             'identity': c.identity(), 'campaigns': {},
             'dispatch_policy': 'Dispatch exactly the scheduled declared case; prior slots remain in the matrix and report.'}
    del value['sha256']
    verify_cached_parent(value)
    root.mkdir(parents=True)
    for name, expected in previous['campaigns'].items():
        prior = c.read_manifest(previous_root/name)
        if prior['sha256'] != expected:
            raise ValueError('prepared campaign changed')
        workspace = root/name
        campaign = {**prior, 'identity': value['identity'], 'workspace': str(workspace)}
        del campaign['sha256']
        with c.lease(workspace):
            publish_artifact(workspace/'campaign.json', c.encoded({**campaign, 'sha256': c.sha(campaign)}))
        value['campaigns'][name] = c.preflight(workspace)['manifest_sha256']
    publish_artifact(root/'continuation.json', c.encoded({**value, 'sha256': c.sha(value)}))
    return dict(status='prepared', inherited_comparisons=len(value['inherited']), remaining=416-len(value['inherited']))


def preflight(root):
    plan = read(root)
    parent = Path(plan['parent'])
    if 'verified_preparation' in plan:
        verify_cached_parent(plan)
    else:
        snapshot = parent_snapshot(parent)
        qualification, qmissing = snapshot['qualification'], snapshot['qmissing']
        inherited = snapshot['comparison']
        if qmissing or qualification != plan['qualification'] or {key(i): i for i in inherited} != plan['inherited']:
            raise ValueError('parent qualification or inherited matrix drift')
    for campaign in plan['campaigns']:
        c.preflight(root/campaign)
    return plan


def report(root):
    plan = preflight(root)
    rows, missing = [], []
    for item in plan['schedule']:
        if key(item) in plan['inherited']:
            rows.append(plan['inherited'][key(item)])
            continue
        try:
            _, row = observation(root/item['campaign'], item)
            if row is None:
                raise ValueError('incomplete')
            rows.append(row)
        except (ValueError, OSError) as error:
            missing.append({**item, 'reason': str(error)})
    value = dict(status='incomplete' if missing else 'complete', amendment_sha256=plan['sha256'],
                 parent_study_status='incomplete', comparison_complete=len(rows), qualification_complete=26,
                 rows=rows, missing=missing, retained_failure_cost=plan['retained_failure'],
                 interpretation=plan['interpretation'], inference=None if missing else study.inference(rows))
    output = root/('analysis-'+uuid.uuid4().hex+'.json')
    publish_artifact(output, c.encoded(value))
    return dict(status=value['status'], comparison_complete=len(rows), report=str(output))


def run(root):
    if (root/'failure.json').exists():
        raise ValueError('retained continuation failure requires diagnosis before retry')
    with c.lease(root/'controller'):
        plan = preflight(root)
        with c.lease(Path(plan['parent'])/'controller'):
            completed = len(plan['inherited'])
            for item in plan['schedule']:
                if key(item) in plan['inherited']:
                    continue
                workspace = root/item['campaign']
                case = c.Case(item['pack'], 256, item['seed'])
                while True:
                    if (root/'PAUSE').exists():
                        return dict(status='paused', comparison_complete=completed)
                    manifest = c.read_manifest(workspace)
                    model_run, reference = c.adopted(workspace, manifest, case, 'primordia')
                    if reference is not None:
                        study.replay_slot(workspace, case, model_run, reference)
                        observation(workspace, item)
                        completed += 1
                        print(json.dumps({**item, 'status': 'complete', 'comparison_complete': completed}), flush=True)
                        derived(root/'status.json', c.encoded(dict(status='running', comparison_complete=completed, active=None)))
                        break
                    derived(root/'status.json', c.encoded(dict(status='running', comparison_complete=completed, active=item)))
                    result = c.run_campaign(workspace, max_runs=1, only_case=case)
                    if result['new_runs'] != 1:
                        raise ValueError('no segment dispatched; retained for diagnosis')
            result = report(root)
            derived(root/'status.json', c.encoded(result))
            return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'prepare-from-verified', 'preflight', 'run', 'resume', 'pause', 'report'))
    parser.add_argument('workspace', type=Path)
    parser.add_argument('--parent', type=Path)
    args = parser.parse_args()
    root = args.workspace.absolute()
    if args.command == 'prepare-from-verified':
        if args.parent is None:
            parser.error('--parent requires the verified preparation directory')
        result = prepare_from_verified(root, args.parent)
    elif args.command == 'prepare':
        if args.parent is None:
            parser.error('--parent required')
        result = prepare(root, args.parent)
    elif args.command == 'preflight':
        plan = preflight(root)
        result = dict(status='passed', inherited_comparisons=len(plan['inherited']))
    elif args.command == 'pause':
        read(root)
        (root/'PAUSE').touch()
        result = dict(status='pause_requested')
    elif args.command == 'report':
        result = report(root)
    else:
        if args.command == 'resume':
            preflight(root)
            (root/'PAUSE').unlink(missing_ok=True)
        try:
            result = run(root)
        except Exception as error:
            derived(root/'failure.json', c.encoded(dict(status='incomplete', reason=str(error))))
            raise
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
