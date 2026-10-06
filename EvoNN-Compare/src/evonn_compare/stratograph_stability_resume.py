"""Numerical-overflow repair with explicit ancestry and retained failure cost.

Copy this controller outside a clean producer. Historical producers and journals
stay immutable; all inherited exports retain their original source identities.
"""
import argparse
from copy import deepcopy
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from evonn_compare import stratograph_study as study
from evonn_compare.campaign import _bounded_process, lease, sha
from evonn_shared.artifact_io import publish_artifact
from evonn_shared.engine_evidence import artifact_json
from evonn_shared.export_reader import read_export
from evonn_shared.runtime_io import derived, encode


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def budget_timeout(config):
    seconds = config['budget'] * (config['fit_timeout'] + 30.) + 600.
    if not 0 < seconds <= 21600:
        raise ValueError('full fit budget exceeds the bounded engine allowance')
    return seconds


def amended_slots(previous):
    cells = deepcopy(previous['slots'])
    for cell in cells:
        if cell['id'] not in previous['completed']:
            cell['config']['timeout'] = budget_timeout(cell['config'])
    return cells


def verify_receipt(origin, receipt):
    for name, expected in receipt['documents'].items():
        if digest(origin/receipt['export']/name) != expected:
            raise ValueError('export receipt drift')
    replay = origin/receipt['replay']
    if digest(replay) != receipt['replay_sha256'] or json.loads(replay.read_text())['status'] != 'passed':
        raise ValueError('winner replay receipt drift')


def full_epochs(origin, receipt):
    attempts = artifact_json(read_export(origin/receipt['export']), 'attempts.json')['attempts']
    if any(a['status'] != 'ok' or a['epochs'] != a['allocated_epochs'] for a in attempts):
        raise ValueError('full successful allocated epochs required')


def prepare(root, previous_root, ancestor_launcher, producer_patch):
    if root.exists():
        raise ValueError('a fresh continuation directory is required')
    subprocess.run(['/bin/bash', str(ancestor_launcher), 'preflight'], check=True, timeout=180)
    prior = json.loads((previous_root/'continuation.json').read_text())
    old = json.loads((previous_root/'status.json').read_text())
    parent_root = Path(prior['parent_root'])
    parent = study.read_plan(parent_root)
    if old['status'] != 'incomplete' or not old['failures']:
        raise ValueError('diagnosed failed continuation required')
    origins, inherited = {}, deepcopy(old['completed'])
    inherited_identities = {}
    if prior['schema_version'] != 'stratograph-only/budget-resume-v1':
        raise ValueError('expected the diagnosed budget continuation')
    slots = {cell['id']: cell for cell in prior['slots']}
    for key, receipt in inherited.items():
        origin = Path(prior['origins'][key]) if key in prior['origins'] else previous_root
        source = parent['identity'] if key in prior['origins'] else prior['identity']
        inherited_identities[str(origin)] = source
        verify_receipt(origin, receipt)
        _, actual = study.adopt(origin, dict(parent, identity=source), slots[key])
        if actual is None or any(actual[k] != receipt[k] for k in actual):
            raise ValueError('inherited receipt differs from verified export')
        full_epochs(origin, receipt)
        origins[key] = str(origin)
    retained = deepcopy(prior['retained_failures'])
    for failure in old['failures']:
        candidates = list((previous_root/'runs'/failure['slot']).iterdir())
        if len(candidates) != 1:
            raise ValueError('ambiguous failed run')
        run = candidates[0]
        attempts = json.loads((run/'attempts.json').read_text())['attempts']
        failed = [a for a in attempts if a['status'] != 'ok']
        if not failed or any(a['reason'] != 'nonfinite loss or gradient' for a in failed):
            raise ValueError('only the diagnosed nonfinite-gradient failure may be restarted')
        retained.append(dict(**failure, run=str(run),
                             documents={n: digest(run/n) for n in ('attempts.json','summary.json','config.yaml')},
                             charged_attempts=sum(a['charged'] for a in attempts),
                             successful_attempts=sum(a['status'] == 'ok' for a in attempts),
                             failed_attempts=len(failed),
                             measured_train_seconds_successful=sum(a.get('train_seconds', 0.) for a in attempts)))
    identity = study.identity()
    # The new producer must differ solely by the reviewed overflow-recovery patch.
    actual_patch = subprocess.check_output(['git','diff','--no-ext-diff',prior['identity']['commit'],identity['commit']])
    if actual_patch != producer_patch.read_bytes():
        raise ValueError('producer differs from the explicit numerical-recovery patch')
    if {k:v for k,v in identity.items() if k not in ('commit','source_sha256')} != {k:v for k,v in parent['identity'].items() if k not in ('commit','source_sha256')}:
        raise ValueError('producer runtime, host or data drift')
    cells = amended_slots(dict(slots=prior['slots'], completed=inherited))
    bound = [parent_root/'study.json', parent_root/'status.json', previous_root/'continuation.json', previous_root/'status.json', ancestor_launcher, ancestor_launcher.parent/'controller.py', producer_patch]
    value = dict(schema_version='stratograph-only/stability-resume-v1', parent_root=str(parent_root),
                 parent_sha256=parent['sha256'], previous_root=str(previous_root),
                 controller_sha256=digest(Path(__file__)), identity=identity,
                 execution_environment=study.execution_environment(), ancestor_launcher=str(ancestor_launcher),
                 bound_files={str(p):digest(p) for p in bound},
                 inherited=inherited, origins=origins, inherited_identities=inherited_identities,
                 ancestor_roots=[str(parent_root),prior['previous_root'],str(previous_root)],
                 retained_failures=retained, slots=cells,
                 interpretation='Explicit backward-overflow amendment; original studies remain incomplete. Successful finite-gradient arithmetic is unchanged, and inherited full-epoch runs retain their original producer identities. Nonfinite gradients with finite loss use a single host-float64 backward recovery with a saturated-GELU argument before the existing global clipping; all recovery work counts against the original fit deadline. No seed, fit, epoch or model policy change. Mixed producer versions and safety caps; no equal-wall-time claim. Prior failed work is charged separately.')
    root.mkdir(parents=True)
    publish_artifact(root/'continuation.json', encode({**value, 'sha256':sha(value)}))
    derived(root/'status.json', encode(dict(status='prepared',plan_sha256=sha(value),active_slot=None,
                                          completed=inherited,failures=[],inherited_runs=len(inherited))))
    return dict(status='prepared', inherited=len(inherited),remaining=len(cells)-len(inherited),
                prior_charged_attempts=sum(f['charged_attempts'] for f in retained))


def preflight(root):
    manifest = json.loads((root/'continuation.json').read_text())
    if manifest['schema_version'] != 'stratograph-only/stability-resume-v1' or manifest['sha256'] != sha({k:v for k,v in manifest.items() if k != 'sha256'}):
        raise ValueError('amendment manifest drift')
    if manifest['controller_sha256'] != digest(Path(__file__)):
        raise ValueError('controller drift')
    for path, expected in manifest['bound_files'].items():
        if digest(Path(path)) != expected:
            raise ValueError('historical evidence or patch drift')
    for failure in manifest['retained_failures']:
        for name, expected in failure['documents'].items():
            if digest(Path(failure['run'])/name) != expected:
                raise ValueError('retained failure evidence drift')
    if study.identity() != manifest['identity'] or study.execution_environment() != manifest['execution_environment']:
        raise ValueError('producer or execution environment drift')
    if shutil.disk_usage(root).free < 4 * 1024**3:
        raise ValueError('at least 4 GiB disk reserve required')
    # Execute ancestry/data verification under its unchanged producer/environment.
    subprocess.run(['/bin/bash', manifest['ancestor_launcher'], 'preflight'], check=True, timeout=180, stdout=subprocess.DEVNULL)
    parent = study.read_plan(Path(manifest['parent_root']))
    prior = json.loads((Path(manifest['previous_root'])/'continuation.json').read_text())
    if parent['sha256'] != manifest['parent_sha256'] or manifest['slots'] != amended_slots(dict(slots=prior['slots'],completed=manifest['inherited'])):
        raise ValueError('slot or original protocol drift')
    state = json.loads((root/'status.json').read_text())
    if state['plan_sha256'] != manifest['sha256'] or any(k not in state['completed'] or state['completed'][k] != v for k,v in manifest['inherited'].items()):
        raise ValueError('state or inherited receipts drift')
    if set(state['completed']) - {c['id'] for c in manifest['slots']}:
        raise ValueError('unknown completed slot')
    for key, receipt in state['completed'].items():
        verify_receipt(Path(manifest['origins'][key]) if key in manifest['origins'] else root, receipt)
    return manifest, parent, state


def run(root):
    manifest, parent, state = preflight(root)
    with ExitStack() as stack:
        descriptors = tuple(stack.enter_context(lease(p)) for p in [root, *map(Path, manifest['ancestor_roots'])])
        manifest, parent, state = preflight(root)
        if state['failures']:
            raise ValueError('retained failure; no automatic retries')
        current_plan = dict(parent, identity=manifest['identity'])
        for cell in manifest['slots']:
            if cell['id'] in state['completed']:
                continue
            if any((p/'PAUSE').exists() for p in [root, *map(Path, manifest['ancestor_roots'])]):
                state.update(status='paused',active_slot=None)
                derived(root/'status.json',encode(state))
                return 'paused'
            try:
                preflight(root)
                state.update(status='running',active_slot=cell['id'])
                derived(root/'status.json',encode(state))
                work = root/'dispatch'/cell['id']
                work.mkdir(parents=True,exist_ok=True)
                sequence = len(list(work.glob('*.log')))
                existing, receipt = study.adopt(root,current_plan,cell)
                if receipt is None:
                    command = [sys.executable,'-m','stratograph.cli','run']
                    if existing is None:
                        cfg = work/'config.json'
                        if not cfg.exists():
                            publish_artifact(cfg,encode(cell['config']))
                        elif json.loads(cfg.read_text()) != cell['config']:
                            raise ValueError('dispatch configuration drift')
                        command += ['--config',str(cfg),'--output',str(root/'runs'/cell['id']),'--cache',parent['cache']]
                    else:
                        command += ['--resume',str(existing)]
                    _bounded_process(command,cell['config']['timeout']+60,work/f'{sequence:04d}.log',pass_fds=descriptors)
                    existing, receipt = study.adopt(root,current_plan,cell)
                    if receipt is None:
                        raise ValueError('missing complete export after budget-derived allowance')
                full_epochs(root,receipt)
                replay = work/f'{sequence:04d}.replay.json'
                _bounded_process([sys.executable,'-m','stratograph.cli','replay',str(existing)],180.,
                                 work/f'{sequence:04d}.replay.log',stdout_path=replay,pass_fds=descriptors)
                if json.loads(replay.read_text())['status'] != 'passed':
                    raise ValueError('winner replay failed')
                receipt.update(replay=str(replay.relative_to(root)),replay_sha256=digest(replay))
                state['completed'][cell['id']] = receipt
                state.update(status='running',active_slot=None)
                derived(root/'status.json',encode(state))
                print(json.dumps(dict(completed=len(state['completed']),planned=len(manifest['slots']))),flush=True)
            except (ValueError,OSError,subprocess.SubprocessError) as error:
                state['failures'].append(dict(slot=cell['id'],reason=str(error)))
                state.update(status='incomplete')
                derived(root/'status.json',encode(state))
                raise
        state.update(status='complete',active_slot=None)
        derived(root/'status.json',encode(state))
    return state['status']


def analyze(root):
    manifest,parent,state = preflight(root)
    observations,missing = {},[]
    for cell in manifest['slots']:
        key = cell['id']
        if key not in state['completed']:
            missing.append(key)
            continue
        origin = Path(manifest['origins'][key]) if key in manifest['origins'] else root
        source = manifest['inherited_identities'][str(origin)] if key in manifest['origins'] else manifest['identity']
        plan = dict(parent,identity=source)
        _, receipt = study.adopt(origin,plan,cell)
        if receipt is None:
            raise ValueError('missing complete export')
        full_epochs(origin,receipt)
        if cell['stage'] == 'main':
            observations[(cell['arm'],cell['config']['pack'],cell['config']['seed'])] = dict(receipt,origin=str(origin))
    comparisons = []
    spec = study.StudySpec.model_validate(parent['spec'])
    for contrast in parent['hypotheses']:
        try:
            values = study.effects_for_panel(observations,spec,contrast['arm'],contrast['panel'])
            inference = study.paired_inference(values,materiality=.01)
            p = inference['wilcoxon']['pvalue'] if inference['wilcoxon']['status'] == 'available' else 1.
            comparisons.append(dict(**contrast,**inference,pvalue=p))
        except KeyError:
            comparisons.append(dict(**contrast,status='missing_paired_cells',pvalue=1.))
    adjusted = 0.
    for index,result in enumerate(sorted(comparisons,key=lambda r:r['pvalue'])):
        adjusted = max(adjusted,min(1.,result['pvalue']*(len(comparisons)-index)))
        ci = result.get('bootstrap_ci95')
        result.update(holm_pvalue=adjusted,material_gain=bool(not missing and not state['failures'] and ci and ci[0] > .01 and adjusted < .05))
    report = dict(status='incomplete' if missing or state['failures'] else 'complete',missing=missing,
                  manifest_sha256=manifest['sha256'],prior_failed_run_cost=manifest['retained_failures'],
                  inherited_runs=len(manifest['inherited']),contrasts=comparisons,
                  observations=[dict(arm=k[0],pack=k[1],seed=k[2],**v) for k,v in observations.items()],
                  interpretation=manifest['interpretation']+' Pointwise 95% intervals; original 30-contrast Holm family retained.')
    derived(root/'analysis.json',encode(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','preflight','run','analyze'))
    parser.add_argument('workspace',type=Path)
    parser.add_argument('--previous',type=Path)
    parser.add_argument('--ancestor-launcher',type=Path)
    parser.add_argument('--producer-patch',type=Path)
    args = parser.parse_args()
    root = args.workspace.absolute()
    if args.command == 'prepare':
        if any(p is None for p in (args.previous,args.ancestor_launcher,args.producer_patch)):
            parser.error('prepare requires ancestry and producer patch')
        result = prepare(root,args.previous.absolute(),args.ancestor_launcher.absolute(),args.producer_patch.absolute())
    elif args.command == 'run':
        result = dict(status=run(root))
        if result['status'] == 'complete':
            analyze(root)
    elif args.command == 'analyze':
        result = analyze(root)
    else:
        manifest,_,state = preflight(root)
        result = dict(status='passed',completed=len(state['completed']),planned=len(manifest['slots']))
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
