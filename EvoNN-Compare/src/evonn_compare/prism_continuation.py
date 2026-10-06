"""Explicit fixed-fit Prism continuation; deploy outside the frozen producer."""
import argparse
from contextlib import ExitStack
import importlib.util
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import uuid

from evonn_shared.artifact_io import publish_artifact
from evonn_shared.engine_evidence import validate_engine_bundle
from evonn_shared.export_reader import read_export
from evonn_shared.runtime_io import derived
from evonn_compare import campaign as c
from evonn_compare import prism_confidence as study
from evonn_compare.baseline_study import validate_replay


def key(entry):
    return entry['campaign'] + '/' + str(entry['seed'])


def timeout(spec):
    seconds = spec['budgets'][0] * (spec['fit_timeout'] + 30.) + 600.
    if not 0 < seconds <= 43200:
        raise ValueError('fit-derived safety allowance exceeds engine limit')
    return seconds


def digest(path):
    return c.hashlib.sha256(path.read_bytes()).hexdigest()


def observation(workspace, row, entry):
    case, identifier = study.slot(row, entry)
    manifest = c.read_manifest(workspace)
    _, reference = c.adopted(workspace, manifest, case, 'prism')
    if reference is None:
        raise ValueError('missing complete export')
    replay = workspace/'replays'/(identifier+'.json')
    validate_replay(json.loads(replay.read_bytes()), reference['run_id'], case.pack)
    bundle = read_export(workspace/reference['export'])
    attempts = c.artifact_json(bundle, 'attempts.json')['attempts']
    if len(attempts) != case.budget or any(a['status'] != 'ok' or a['charged'] != 1 for a in attempts):
        raise ValueError('failed or incomplete fit coverage')
    return dict(entry=entry, workspace=str(workspace), reference=reference,
                replay=str(replay), replay_sha256=digest(replay), campaign_sha256=manifest['sha256'])


def parent_audit(root):
    """Execute using the historical producer; never rewrite its evidence."""
    plan = study.read_plan(root)
    if c.identity() != plan['identity']:
        raise ValueError('historical producer/environment drift')
    # Each inherited export is audited with its pinned dataset below. Unused
    # splits are checked once under the amended manifests during preparation.
    rows = {r['campaign']: r for r in plan['campaigns']}
    receipts = study.completed_receipts(root, plan)
    inherited, failures = {}, []
    for entry in plan['schedule']:
        row = rows[entry['campaign']]
        workspace = root/entry['campaign']
        slot = f"{row['spec']['pack']}_b{row['spec']['budgets'][0]}_s{entry['seed']}_prism"
        if slot in receipts[entry['campaign']]:
            record = observation(workspace, row, entry)
            if record['reference'] != receipts[entry['campaign']][slot]:
                raise ValueError('journal/export disagreement')
            inherited[key(entry)] = record
            if len(inherited) % 10 == 0:
                print(json.dumps({'historical_runs_verified':len(inherited)}), file=sys.stderr, flush=True)
        else:
            if not (workspace/'runs'/slot).exists():
                continue
            case, _ = study.slot(row, entry)
            run, reference = c.adopted(workspace, c.read_manifest(workspace), case, 'prism')
            if reference is not None:
                raise ValueError('unjournaled completion requires separate recovery')
            if run is not None:
                state = json.loads((run/'state.json').read_bytes())
                ends = sorted((run/'invocation_clock').glob('*_end.json'))
                elapsed = json.loads(ends[-1].read_bytes())['elapsed'] if ends else state['elapsed']
                if not (0 < state['completed'] < case.budget and elapsed >= row['spec']['timeout']):
                    raise ValueError('only diagnosed cumulative timeout can be restarted')
                if any(a['status'] != 'ok' for a in state['attempts']):
                    raise ValueError('failed fits need separate diagnosis')
                files = [run/n for n in ('state.json', 'config.yaml', 'attempts.json', 'summary.json')]
                files += list((run/'invocation_clock').glob('*.json'))
                failures.append(dict(entry=entry, run=str(run), charged_attempts=state['completed'], elapsed=elapsed,
                    measured_train_seconds=sum(a.get('train_seconds', 0.) for a in state['attempts']),
                    documents={str(p): digest(p) for p in files}))
    if (len(inherited) != 52 or len(failures) != 1
            or set(inherited) != {key(e) for e in plan['schedule'][:52]}
            or failures[0]['entry'] != plan['schedule'][52]):
        raise ValueError('unexpected historical coverage; review amendment before training')
    return dict(parent_sha256=plan['sha256'], inherited=inherited, retained_failures=failures)


def historical(root):
    plan = study.read_plan(root)
    result = subprocess.run([plan['identity']['python'], str(Path(__file__).resolve()), 'audit-parent', str(root)],
        cwd=Path(plan['identity']['python']).parents[2], text=True, stdout=subprocess.PIPE, check=True, timeout=900)
    value = json.loads(result.stdout)
    receipt = Path(__file__).resolve().parent/('parent-audit-'+uuid.uuid4().hex+'.json')
    publish_artifact(receipt, c.encoded(value))
    return value


def prepare(root, parent, patch):
    if root.exists():
        raise ValueError('use a fresh continuation directory')
    original = study.read_plan(parent)
    snapshot = historical(parent)
    identity = c.identity()
    actual = subprocess.check_output(['git', 'diff', '--no-ext-diff', original['identity']['commit'], identity['commit']])
    if actual != patch.read_bytes():
        raise ValueError('producer differs from reviewed timeout-only patch')
    for name in ('host', 'versions', 'data_files'):
        if identity[name] != original['identity'][name]:
            raise ValueError('runtime, host or data drift')
    root.mkdir(parents=True)
    campaigns = {}
    for row in original['campaigns']:
        if row['stage'] != 'main':
            continue
        old = c.read_manifest(parent/row['campaign'])
        spec = {**old['spec'], 'timeout': timeout(old['spec'])}
        c.CampaignSpec.model_validate(spec)
        workspace = root/row['campaign']
        value = {k:v for k,v in old.items() if k != 'sha256'}
        value.update(spec=spec, identity=identity, workspace=str(workspace))
        with c.lease(workspace):
            publish_artifact(workspace/'campaign.json', c.encoded({**value, 'sha256':c.sha(value)}))
        campaigns[row['campaign']] = c.preflight(workspace)['manifest_sha256']
        print(json.dumps({'campaign_preflight':row['campaign']}), file=sys.stderr, flush=True)
    if c.identity() != identity:
        raise ValueError('producer changed during preparation')
    value = dict(schema_version='evonn.prism-budget-continuation/v1', parent=str(parent), **snapshot,
        identity=identity, campaigns=campaigns, controller_sha256=digest(Path(__file__)),
        producer_patch=str(patch), producer_patch_sha256=digest(patch), schedule=original['schedule'],
        authorization='User requested fix and resume after cumulative time exhaustion on 2026-09-21.',
        amendment='Every unfinished slot receives budget*(fit_timeout+30)+600 seconds. Completed historical runs retain their identities. Restart only the exhausted cell from scratch; its 98 charged attempts remain separately reported. Fit counts, seeds, epochs, per-fit limits, variants and inference unchanged.',
        interpretation='Amended fixed-fit within-Prism comparison with mixed run safety caps and producer versions. Historical studies remain incomplete. No equal-wall-time, other-engine or protected-test claim.')
    publish_artifact(root/'continuation.json', c.encoded({**value, 'sha256':c.sha(value)}))
    status(root, value, 'prepared', len(snapshot['inherited']), None)
    return dict(status='prepared', inherited=len(snapshot['inherited']), remaining=1012-len(snapshot['inherited']))


def fit_failure(state, budget):
    attempts = state['attempts']
    failed = [a for a in attempts if a['status'] != 'ok']
    if (state['completed'] != budget or len(attempts) != budget or len(failed) != 1
            or failed[0]['status'] != 'failed'
            or failed[0].get('reason') != 'training wall-clock cap reached'
            or any(a['charged'] != 1 for a in attempts)):
        raise ValueError('unexpected failure; only the diagnosed single per-fit timeout is authorized')
    return failed[0]


def prepare_fit(root, predecessor):
    """Freeze a separate amendment; keep producer and all historical evidence intact."""
    if root.exists():
        raise ValueError('use a fresh continuation directory')
    controller = predecessor.parent/'controller.py'
    module_spec = importlib.util.spec_from_file_location('historical_prism_controller', controller)
    previous = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(previous)
    old, original = previous.read(predecessor)
    failure_path = predecessor/'failure.json'
    failure = json.loads(failure_path.read_bytes())
    entry = original['schedule'][52]
    if (failure['active'] != entry or failure['completed'] != 52
            or set(old['inherited']) != {key(e) for e in original['schedule'][:52]}):
        raise ValueError('unexpected predecessor coverage')
    dispatches = []
    for name in old['campaigns']:
        manifest = c.read_manifest(predecessor/name)
        events = c.events(predecessor/name, manifest)
        if any(e['kind'] == 'complete' for e in events):
            raise ValueError('additional completions require explicit adoption')
        dispatches.extend(e for e in events if e['kind'] == 'dispatch')
    if len(dispatches) != 1:
        raise ValueError('unexpected predecessor dispatch count')
    row = next(r for r in original['campaigns'] if r['campaign'] == entry['campaign'])
    case, identifier = study.slot(row, entry)
    runs = list((predecessor/entry['campaign']/'runs'/identifier).glob('prism_*'))
    if len(runs) != 1:
        raise ValueError('ambiguous failed run')
    failed_run = runs[0]
    state = json.loads((failed_run/'state.json').read_bytes())
    failed = fit_failure(state, case.budget)
    files = [failed_run/n for n in ('state.json','config.yaml','attempts.json','summary.json')]
    files += list((failed_run/'invocation_clock').glob('*.json'))
    files += [p for p in failed_run.glob('attempt_*/result.json')]
    files += [p for p in failed_run.glob('attempt_*/request.json')]
    retained = dict(entry=entry, run=str(failed_run), charged_attempts=case.budget,
        elapsed=state['elapsed'], failed_attempt=failed,
        measured_train_seconds=sum(a.get('train_seconds',0.) for a in state['attempts']),
        documents={str(p):digest(p) for p in files})
    root.mkdir(parents=True)
    campaigns = {}
    for name in old['campaigns']:
        manifest = c.read_manifest(predecessor/name)
        spec = {**manifest['spec'], 'timeout':43200., 'fit_timeout':1800.}
        c.CampaignSpec.model_validate(spec)
        workspace = root/name
        value = {k:v for k,v in manifest.items() if k != 'sha256'}
        value.update(spec=spec, workspace=str(workspace))
        with c.lease(workspace):
            publish_artifact(workspace/'campaign.json',c.encoded({**value,'sha256':c.sha(value)}))
        campaigns[name] = c.preflight(workspace)['manifest_sha256']
    value = {k:v for k,v in old.items() if k != 'sha256'}
    value.update(campaigns=campaigns,controller_sha256=digest(Path(__file__)),
        predecessor=str(predecessor), predecessor_documents={str(p):digest(p) for p in
            (predecessor/'continuation.json',controller,failure_path)},
        retained_failures=[*old['retained_failures'],retained],
        authorization='User requested fix and resume on 2026-09-22 after per-fit timeout.',
        amendment='All unfinished slots receive a 1800-second per-fit safety cap and a 43200-second cumulative cap. Epochs, fit counts, seeds, variants, optimizer and inference remain unchanged. The failed 128-fit cell restarts separately; all 226 charged attempts from both failed continuations remain extra cost.',
        interpretation='Amended fixed-fit within-Prism comparison with mixed safety caps and historical producer versions. Historical studies remain incomplete. No equal-wall-time, other-engine or protected-test claim.')
    publish_artifact(root/'continuation.json',c.encoded({**value,'sha256':c.sha(value)}))
    status(root,value,'prepared',len(value['inherited']),None)
    return dict(status='prepared',inherited=len(value['inherited']),remaining=960,retained_extra_attempts=226)


def size_failure(state, budget):
    attempts = state['attempts']
    failed = [a for a in attempts if a['status'] != 'ok']
    if (state['completed'] != budget or len(attempts) != budget or len(failed) != 1
            or failed[0]['status'] != 'failed' or failed[0]['charged'] != 0 or failed[0]['invalid'] != 1
            or failed[0]['reason'] != 'invalid pre-fit candidate: compiled candidate exceeds local runtime parameter safety cap'
            or failed[0]['compiled_parameter_count'] <= 2_000_000
            or sum(a['charged'] for a in attempts) != budget-1):
        raise ValueError('unexpected failure; expected one uncharged oversized proposal')
    return failed[0]


def size_parent(root):
    """Bind already journaled evidence; semantic verification happens before dispatch."""
    controller=root.parent/'controller.py'
    spec=importlib.util.spec_from_file_location('previous_prism_controller',controller)
    previous=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    old, original=previous.read(root)
    failure=json.loads((root/'failure.json').read_bytes())
    if failure['completed'] != 163 or failure['active'] != original['schedule'][163]:
        raise ValueError('unexpected failed continuation coverage')
    inherited=dict(old['inherited'])
    rows={r['campaign']:r for r in original['campaigns']}
    manifests={name:c.read_manifest(root/name) for name in old['campaigns']}
    histories={name:c.events(root/name,manifest) for name,manifest in manifests.items()}
    for entry in original['schedule']:
        name=entry['campaign']
        if key(entry) in inherited or name not in manifests:
            continue
        row=rows[name]
        case,identifier=study.slot(row,entry)
        complete=[e for e in histories[name] if e['slot']==identifier and e['kind']=='complete']
        if not complete:
            continue
        if len(complete)!=1:
            raise ValueError('duplicate completed cell')
        reference=complete[0]['details']
        replay=root/name/'replays'/(identifier+'.json')
        validate_replay(json.loads(replay.read_bytes()),reference['run_id'],case.pack)
        inherited[key(entry)]=dict(entry=entry,workspace=str(root/name),reference=reference,
            replay=str(replay),replay_sha256=digest(replay),campaign_sha256=manifests[name]['sha256'])
    if set(inherited)!={key(e) for e in original['schedule'][:163]}:
        raise ValueError('unexpected completed prefix')
    entry=failure['active']
    row=rows[entry['campaign']]
    case,identifier=study.slot(row,entry)
    runs=list((root/entry['campaign']/'runs'/identifier).glob('prism_*'))
    if len(runs)!=1:
        raise ValueError('ambiguous failed cell')
    run=runs[0]
    state=json.loads((run/'state.json').read_bytes())
    failed=size_failure(state,case.budget)
    files=[run/n for n in ('state.json','config.yaml','attempts.json','summary.json')]
    files+=list((run/'invocation_clock').glob('*.json'))
    retained=dict(entry=entry,run=str(run),charged_attempts=255,invalid_proposals=1,
        elapsed=state['elapsed'],failed_attempt=failed,
        measured_train_seconds=sum(a.get('train_seconds',0.) for a in state['attempts']),
        documents={str(p):digest(p) for p in files})
    docs={**old.get('predecessor_documents',{}),**{str(p):digest(p) for p in
        (root/'continuation.json',controller,root/'failure.json')}}
    for name in manifests:
        docs.update({str(p):digest(p) for p in (root/name/'events').glob('*.json')})
    return dict(inherited=inherited,retained_failures=[*old['retained_failures'],retained],
        predecessor_documents=docs)


def prepare_size(root, predecessor, patch):
    if root.exists():
        raise ValueError('use a fresh continuation directory')
    old=json.loads((predecessor/'continuation.json').read_bytes())
    result=subprocess.run([old['identity']['python'],str(Path(__file__).resolve()),'audit-size-parent',str(predecessor)],
        cwd=Path(old['identity']['python']).parents[2],text=True,stdout=subprocess.PIPE,check=True,timeout=900)
    snapshot=json.loads(result.stdout)
    publish_artifact(root.parent/'predecessor-audit.json',c.encoded(snapshot))
    identity=c.identity()
    for field in ('host','versions','data_files'):
        if identity[field]!=old['identity'][field]:
            raise ValueError('environment or data drift')
    original=study.read_plan(Path(old['parent']))
    actual=subprocess.check_output(['git','diff','--no-ext-diff',original['identity']['commit'],identity['commit']])
    if actual!=patch.read_bytes():
        raise ValueError('producer differs from reviewed repair patch')
    root.mkdir(parents=True)
    campaigns={}
    for name in old['campaigns']:
        manifest=c.read_manifest(predecessor/name)
        workspace=root/name
        value={k:v for k,v in manifest.items() if k!='sha256'}
        value.update(identity=identity,workspace=str(workspace))
        with c.lease(workspace):
            publish_artifact(workspace/'campaign.json',c.encoded({**value,'sha256':c.sha(value)}))
        campaigns[name]=c.preflight(workspace)['manifest_sha256']
    value={k:v for k,v in old.items() if k!='sha256'}
    value.update(**snapshot,identity=identity,campaigns=campaigns,
        predecessor=str(predecessor),predecessor_identity=old['identity'],
        controller_sha256=digest(Path(__file__)),producer_patch=str(patch),producer_patch_sha256=digest(patch),
        authorization='User requested Fix and Resume after oversized pre-fit rejection on 2026-09-23.',
        amendment='Keep 163 completed cells. Restart the failed cell separately. All unfinished cells use deterministic shrink_widths_v1 to keep evolved proposals within the existing 2000000-parameter cap, recording original and effective genomes. No resampling, extra fit, cap increase or swallowed failure. Retain 481 charged attempts plus one invalid proposal from failed continuations. Fit budgets, seeds, epochs, time limits and inference remain fixed.',
        interpretation='Amended fixed-fit within-Prism study with mixed historical producers and safety caps. Results describe variants under the explicit runtime size constraint. No equal-wall-time, other-engine or protected-test claim.')
    publish_artifact(root/'continuation.json',c.encoded({**value,'sha256':c.sha(value)}))
    status(root,value,'prepared',len(value['inherited']),None)
    return dict(status='prepared',inherited=163,remaining=849,retained_extra_fits=481,retained_invalid_proposals=1)


def verify_record(record):
    workspace = Path(record['workspace'])
    if c.read_manifest(workspace)['sha256'] != record['campaign_sha256']:
        raise ValueError('historical campaign changed')
    reference = record['reference']
    for document in reference['documents']:
        if digest(workspace/reference['export']/document['path']) != document['sha256']:
            raise ValueError('historical export receipt changed')
    bundle = read_export(workspace/reference['export'])
    manifest = c.read_manifest(workspace)
    entry = record['entry']
    case = c.Case(manifest['spec']['pack'], manifest['spec']['budgets'][0], entry['seed'])
    config = c.artifact_json(bundle, 'config.yaml')
    historical_root = Path(manifest['identity']['python']).parents[2]
    if config['shared_root'] != str(historical_root/'shared-benchmarks'):
        raise ValueError('historical benchmark root mismatch')
    # match_config uses its executing producer's ROOT for this one path.
    # Verify the historical path above, then normalize only the in-memory copy.
    c.match_config({**config, 'shared_root':str(c.ROOT/'shared-benchmarks')}, manifest, case, 'prism')
    validate_engine_bundle(bundle, verify_cache=True)
    attempts = c.artifact_json(bundle, 'attempts.json')['attempts']
    if len(attempts) != case.budget or any(a['status'] != 'ok' or a['charged'] != 1 for a in attempts):
        raise ValueError('historical fit coverage is incomplete')
    path = Path(record['replay'])
    if digest(path) != record['replay_sha256']:
        raise ValueError('historical replay changed')
    validate_replay(json.loads(path.read_bytes()), reference['run_id'], bundle.manifest.pack_id)


def read(root):
    plan = json.loads((root/'continuation.json').read_bytes())
    if (plan['schema_version'] != 'evonn.prism-budget-continuation/v1'
            or plan['sha256'] != c.sha({k:v for k,v in plan.items() if k != 'sha256'})
            or plan['controller_sha256'] != digest(Path(__file__))
            or digest(Path(plan['producer_patch'])) != plan['producer_patch_sha256']):
        raise ValueError('continuation manifest/controller/patch drift')
    parent = study.read_plan(Path(plan['parent']))
    if parent['sha256'] != plan['parent_sha256'] or parent['schedule'] != plan['schedule']:
        raise ValueError('original study drift')
    if c.identity() != plan['identity']:
        raise ValueError('producer/environment drift')
    for name, expected in plan['campaigns'].items():
        if c.read_manifest(root/name)['sha256'] != expected:
            raise ValueError('amended campaign drift')
    for path, expected in plan.get('predecessor_documents', {}).items():
        if digest(Path(path)) != expected:
            raise ValueError('predecessor evidence changed')
    for failure in plan['retained_failures']:
        for path, expected in failure['documents'].items():
            if digest(Path(path)) != expected:
                raise ValueError('retained failure changed')
    return plan, parent


def preflight(root):
    plan, parent = read(root)
    result = subprocess.run([parent['identity']['python'], '-c',
        'import json; from evonn_compare import campaign as c; print(json.dumps(c.identity()))'],
        cwd=Path(parent['identity']['python']).parents[2], text=True, capture_output=True, check=True, timeout=60)
    if json.loads(result.stdout) != parent['identity']:
        raise ValueError('historical producer/environment drift')
    if plan.get('predecessor_identity'):
        expected = plan['predecessor_identity']
        result = subprocess.run([expected['python'], '-c',
            'import json; from evonn_compare import campaign as c; print(json.dumps(c.identity()))'],
            cwd=Path(expected['python']).parents[2], text=True, capture_output=True, check=True, timeout=60)
        if json.loads(result.stdout) != expected:
            raise ValueError('predecessor producer/environment drift')
    for index, record in enumerate(plan['inherited'].values(), 1):
        verify_record(record)
        if index % 20 == 0:
            print(json.dumps({'inherited_runs_verified':index}), file=sys.stderr, flush=True)
    for name in plan['campaigns']:
        c.preflight(root/name)
    return plan, parent


def status(root, plan, state, completed, active, **extra):
    value = dict(status=state, amendment_sha256=plan.get('sha256', c.sha(plan)),
                 updated_at=datetime.now(timezone.utc).isoformat(),
                 qualification_complete=22, main_complete=max(0, completed-22),
                 completed=completed, planned=1012, active=active, **extra)
    derived(root/'status.json', c.encoded(value))
    return value


def dispatch(root, row, entry, fds):
    workspace = root/entry['campaign']
    case, identifier = study.slot(row, entry)
    with c.lease(workspace) as campaign_fd:
        c.preflight(workspace)
        manifest = c.read_manifest(workspace)
        history = c.events(workspace, manifest)
        c.active_dispatch(workspace, history, identifier)
        run, reference = c.adopted(workspace, manifest, case, 'prism')
        old = [e for e in history if e['kind'] == 'complete' and e['slot'] == identifier]
        if old and (len(old) != 1 or old[0]['details'] != reference):
            raise ValueError('completion journal drift')
        if reference is None:
            if run is not None:
                raise ValueError('interrupted amended slot requires diagnosis; no automatic retry')
            spec = manifest['spec']
            output = c.create_artifact_directory(workspace/'runs'/identifier)
            command = [sys.executable, '-m', 'prism.cli', 'run', '--pack', case.pack, '--budget', str(case.budget),
                '--seed', str(case.seed), '--output', str(output), '--cache', manifest['cache'],
                '--timeout', str(spec['timeout']), '--fit-timeout', str(spec['fit_timeout']),
                '--backend', spec['backend'], '--epochs', str(spec['epochs'])]
            for k,v in spec['prism_research'].items():
                if v is not None:
                    command += ['--'+k.replace('_','-'), json.dumps(v) if isinstance(v,dict) else v]
            c.append_event(workspace, manifest, history, identifier, 'dispatch', {'command':command})
            event = history[-1]
            directory = c.create_artifact_directory(workspace/'dispatch')
            path = directory/f"{event['sequence']:06d}.json"
            publish_artifact(path, c.encoded(event))
            c._bounded_process([sys.executable, '-m', 'evonn_compare.campaign_worker', 'dispatch', str(path), str(campaign_fd)],
                spec['timeout']+20, path.with_suffix('.log'), pass_fds=(*fds,campaign_fd))
            _, reference = c.adopted(workspace, manifest, case, 'prism')
            if reference is None:
                raise ValueError('amended run lacks complete verified export')
        study.replay(root, row, entry)
        record = observation(workspace, row, entry)
        if not old:
            c.append_event(workspace, manifest, history, identifier, 'complete', reference)
        return record


def analyze(root):
    plan, parent = preflight(root)
    by_path = {r['campaign']:r for r in parent['campaigns']}
    records, missing = [], []
    for entry in plan['schedule']:
        if key(entry) in plan['inherited']:
            records.append(plan['inherited'][key(entry)])
            continue
        workspace = root/entry['campaign']
        row = by_path[entry['campaign']]
        _, slot = study.slot(row,entry)
        history = c.events(workspace,c.read_manifest(workspace))
        complete = [e for e in history if e['slot']==slot and e['kind']=='complete']
        if not complete:
            missing.append(entry)
            continue
        record = observation(workspace,row,entry)
        if len(complete)!=1 or complete[0]['details']!=record['reference']:
            raise ValueError('analysis journal/export mismatch')
        records.append(record)
    result = dict(status='incomplete' if missing else 'complete', amendment_sha256=plan['sha256'],
        missing=missing, completed=len(records), inherited=len(plan['inherited']),
        retained_failure_cost=plan['retained_failures'], interpretation=plan['interpretation'], statistics=None)
    if not missing:
        rows=[]
        for record in records:
            entry=record['entry']
            if entry['stage']=='qualification':
                continue
            bundle=read_export(Path(record['workspace'])/record['reference']['export'])
            attempts=c.artifact_json(bundle,'attempts.json')['attempts']
            for benchmark in c.load_parity_pack(bundle.manifest.pack_id).benchmarks:
                candidates=[a for a in attempts if a['benchmark_id']==benchmark and a['status']=='ok']
                winner=max(candidates,key=lambda a:a['score'])
                rows.append(dict(panel=entry['panel'],arm=entry['arm'],seed=entry['seed'],benchmark=benchmark,
                    direction=c.get_benchmark(benchmark).primary_metric.direction.value,value=winner['metric_value'],
                    parameter_count=winner['parameter_count'],model_bytes=winner['model_bytes'],
                    training_seconds=sum(a.get('train_seconds',0.) for a in candidates),
                    optimizer_updates=sum(a.get('updates',0) for a in candidates)))
        result.update(rows=rows, runs=records, statistics=study.inference(rows,study.ARMS,study.SEEDS))
    publish_artifact(root/('analysis-'+uuid.uuid4().hex+'.json'),c.encoded(result))
    return result


def run(root):
    if (root/'failure.json').exists():
        raise ValueError('recorded continuation failure requires diagnosis')
    initial=json.loads((root/'continuation.json').read_bytes())
    with ExitStack() as leases:
        fd = leases.enter_context(c.lease(root/'controller'))
        parent_fd = leases.enter_context(c.lease(Path(initial['parent'])/'controller'))
        if initial.get('predecessor'):
            leases.enter_context(c.lease(Path(initial['predecessor'])/'controller'))
        plan,parent=preflight(root)
        rows={r['campaign']:r for r in parent['campaigns']}
        completed=len(plan['inherited'])
        for entry in plan['schedule']:
            if key(entry) in plan['inherited']:
                continue
            if any((p/'PAUSE').exists() for p in (root,Path(plan['parent']))):
                return status(root,plan,'paused',completed,None)
            status(root,plan,'running',completed,entry)
            try:
                dispatch(root,rows[entry['campaign']],entry,(fd,parent_fd))
            except Exception as error:
                failure=status(root,plan,'incomplete',completed,entry,reason=str(error))
                publish_artifact(root/'failure.json',c.encoded(failure))
                raise
            completed+=1
            print(json.dumps(status(root,plan,'running',completed,None)),flush=True)
        result=analyze(root)
        return status(root,plan,result['status'],completed,None)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('audit-parent','prepare','prepare-fit','audit-size-parent','prepare-size','preflight','run','analyze'))
    parser.add_argument('workspace',type=Path)
    parser.add_argument('--parent',type=Path)
    parser.add_argument('--patch',type=Path)
    parser.add_argument('--predecessor',type=Path)
    args=parser.parse_args()
    root=args.workspace.resolve()
    if args.command=='audit-parent':
        result=parent_audit(root)
    elif args.command=='prepare':
        if args.parent is None or args.patch is None:
            parser.error('prepare requires --parent and --patch')
        with c.lease(args.parent.absolute()/'controller'):
            result=prepare(root,args.parent.absolute(),args.patch.absolute())
    elif args.command=='audit-size-parent':
        result=size_parent(root)
    elif args.command=='prepare-size':
        if args.predecessor is None or args.patch is None:
            parser.error('prepare-size requires --predecessor and --patch')
        with c.lease(args.predecessor.resolve()/'controller'):
            result=prepare_size(root,args.predecessor.resolve(),args.patch.resolve())
    elif args.command=='prepare-fit':
        if args.predecessor is None:
            parser.error('prepare-fit requires --predecessor')
        with c.lease(args.predecessor.resolve()/'controller'):
            result=prepare_fit(root,args.predecessor.resolve())
    elif args.command=='preflight':
        plan,_=preflight(root)
        result=dict(status='passed',inherited=len(plan['inherited']))
    elif args.command=='analyze':
        result=analyze(root)
    else:
        result=run(root)
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    main()
