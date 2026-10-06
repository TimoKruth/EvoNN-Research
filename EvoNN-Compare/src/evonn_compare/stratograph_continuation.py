"""Explicit time-cap amendment; retain original evidence and the frozen engine.

At runtime this controller is copied outside the producer and imports its frozen
study helpers. Its own bytes are independently bound in the amendment manifest.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from evonn_shared.artifact_io import publish_artifact
from evonn_shared.engine_evidence import artifact_json
from evonn_shared.export_reader import read_export
from evonn_shared.runtime_io import derived, encode
from evonn_compare import stratograph_study as study
from evonn_compare.campaign import _bounded_process, lease, sha


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def amended_slots(parent, inherited):
    cells = deepcopy(parent['slots'])
    for cell in cells:
        if cell['id'] not in inherited:
            cell['config']['timeout'] = 1800.
    return cells


def read_manifest(root):
    value = json.loads((root/'continuation.json').read_text())
    if value['schema_version'] != 'stratograph-only/continuation-v1' or value['sha256'] != sha({k: v for k, v in value.items() if k != 'sha256'}):
        raise ValueError('continuation manifest drift')
    if digest(Path(__file__)) != value['controller_sha256']:
        raise ValueError('continuation controller source drift')
    parent = study.read_plan(Path(value['parent_root']))
    if parent['sha256'] != value['parent_sha256'] or value['slots'] != amended_slots(parent, value['inherited']):
        raise ValueError('parent study or amendment cells drift')
    return value, parent


def verify_receipt(root, receipt):
    for name, expected in receipt['documents'].items():
        if digest(root/receipt['export']/name) != expected:
            raise ValueError('retained export document drift')
    replay = root/receipt['replay']
    if digest(replay) != receipt['replay_sha256'] or json.loads(replay.read_text())['status'] != 'passed':
        raise ValueError('retained winner replay drift')


def prepare(parent_root, root):
    parent_root, root = parent_root.absolute(), root.absolute()
    study.preflight(parent_root)
    parent = study.read_plan(parent_root)
    old = json.loads((parent_root/'status.json').read_text())
    if old['status'] != 'incomplete' or not old['failures']:
        raise ValueError('a retained failed study is required for this amendment')
    if root.exists():
        raise ValueError('use a new continuation directory')
    inherited, failures = {}, []
    by_id = {s['id']: s for s in parent['slots']}
    for identity, receipt in old['completed'].items():
        verify_receipt(parent_root, receipt)
        _, observed = study.adopt(parent_root, parent, by_id[identity])
        if observed is None or observed['documents'] != receipt['documents']:
            raise ValueError('parent completion receipt differs from verified export')
        bundle = read_export(parent_root/receipt['export'])
        attempts = artifact_json(bundle, 'attempts.json')['attempts']
        if any(a['epochs'] != a['allocated_epochs'] for a in attempts):
            raise ValueError('time-limited training cannot be inherited into a full-fit comparison')
        inherited[identity] = receipt
    for failure in old['failures']:
        candidates = list((parent_root/'runs'/failure['slot']).iterdir())
        if len(candidates) != 1:
            raise ValueError('ambiguous failed run')
        run = candidates[0]
        attempts = json.loads((run/'attempts.json').read_text())['attempts']
        unsuccessful = [a for a in attempts if a['status'] != 'ok']
        if not unsuccessful or any('wall-clock cap' not in (a['reason'] or '') for a in unsuccessful):
            raise ValueError('this amendment only addresses the diagnosed wall-clock exhaustion')
        failures.append(dict(**failure, run=str(run),
                             documents={name: digest(run/name) for name in ('attempts.json', 'summary.json', 'config.yaml')},
                             charged_attempts=sum(a['charged'] for a in attempts),
                             successful_attempts=sum(a['status'] == 'ok' for a in attempts),
                             failed_attempts=len(unsuccessful),
                             measured_train_seconds_successful=sum(a.get('train_seconds', 0.) for a in attempts)))
    value = dict(schema_version='stratograph-only/continuation-v1', parent_root=str(parent_root),
                 parent_sha256=parent['sha256'], parent_status_sha256=digest(parent_root/'status.json'),
                 controller_sha256=digest(Path(__file__)), inherited=inherited, retained_failures=failures,
                 slots=amended_slots(parent, inherited),
                 amendment='User-authorized resume: 1800-second run cap for every unfinished slot; complete full-epoch parent runs reused; interrupted slot restarted from scratch once; all prior work retained and charged separately.',
                 unchanged=['engine producer', 'datasets', 'seeds', 'fit counts', 'fit timeout', 'epochs', 'policies', 'hypotheses'],
                 interpretation='Amended fixed-fit comparison with mixed safety caps; original study remains incomplete. No equal-wall-time claim.')
    root.mkdir(parents=True)
    publish_artifact(root/'continuation.json', encode({**value, 'sha256': sha(value)}))
    derived(root/'status.json', encode(dict(status='prepared', plan_sha256=sha(value), active_slot=None,
                                          completed=deepcopy(inherited), failures=[], inherited_runs=len(inherited))))
    return dict(status='prepared', inherited_runs=len(inherited), remaining_runs=len(value['slots'])-len(inherited),
                retained_failed_attempts=sum(f['charged_attempts'] for f in failures))


def preflight(root):
    manifest, parent = read_manifest(root)
    parent_root = Path(manifest['parent_root'])
    study.preflight(parent_root)
    if digest(parent_root/'status.json') != manifest['parent_status_sha256']:
        raise ValueError('historical parent status changed')
    for failure in manifest['retained_failures']:
        for name, expected in failure['documents'].items():
            if digest(Path(failure['run'])/name) != expected:
                raise ValueError('historical failed-run evidence changed')
    state = json.loads((root/'status.json').read_text())
    if state['plan_sha256'] != manifest['sha256']:
        raise ValueError('continuation state/manifest mismatch')
    if any(k not in state['completed'] or state['completed'][k] != v for k, v in manifest['inherited'].items()):
        raise ValueError('inherited completion receipts changed')
    if set(state['completed']) - {s['id'] for s in manifest['slots']}:
        raise ValueError('unknown completed slot')
    for identity, receipt in state['completed'].items():
        verify_receipt(parent_root if identity in manifest['inherited'] else root, receipt)
    return manifest, parent, state


def run(root):
    root = root.absolute()
    manifest, parent, state = preflight(root)
    parent_root = Path(manifest['parent_root'])
    with lease(root) as descriptor, lease(parent_root):
        manifest, parent, state = preflight(root)
        if state['failures']:
            raise ValueError('retained continuation failure; automatic retries are disabled')
        for cell in manifest['slots']:
            if cell['id'] in state['completed']:
                continue
            if (root/'PAUSE').exists() or (parent_root/'PAUSE').exists():
                state['status'] = 'paused'
                derived(root/'status.json', encode(state))
                return state['status']
            # Recheck the unchanged producer/data environment before each run.
            study.preflight(parent_root)
            state.update(status='running', active_slot=cell['id'])
            derived(root/'status.json', encode(state))
            work = root/'dispatch'/cell['id']
            work.mkdir(parents=True, exist_ok=True)
            sequence = len(list(work.glob('*.log')))
            try:
                existing, receipt = study.adopt(root, parent, cell)
                if receipt is None:
                    command = [sys.executable, '-m', 'stratograph.cli', 'run']
                    if existing is None:
                        cfg = work/'config.json'
                        if not cfg.exists():
                            publish_artifact(cfg, encode(cell['config']))
                        elif json.loads(cfg.read_text()) != cell['config']:
                            raise ValueError('continuation dispatch config drift')
                        command += ['--config', str(cfg), '--output', str(root/'runs'/cell['id']), '--cache', parent['cache']]
                    else:
                        command += ['--resume', str(existing)]
                    _bounded_process(command, 1820., work/f'{sequence:04d}.log', pass_fds=(descriptor,))
                    existing, receipt = study.adopt(root, parent, cell)
                    if receipt is None:
                        raise ValueError('run did not produce a full verified export within the amended cap')
                attempts = artifact_json(read_export(root/receipt['export']), 'attempts.json')['attempts']
                if any(a['epochs'] != a['allocated_epochs'] for a in attempts):
                    raise ValueError('amended run contains time-limited training')
                replay = work/f'{sequence:04d}.replay.json'
                _bounded_process([sys.executable, '-m', 'stratograph.cli', 'replay', str(existing)], 180.,
                                 work/f'{sequence:04d}.replay.log', stdout_path=replay, pass_fds=(descriptor,))
                if json.loads(replay.read_text())['status'] != 'passed':
                    raise ValueError('winner replay failed')
                receipt.update(replay=str(replay.relative_to(root)), replay_sha256=digest(replay))
                state['completed'][cell['id']] = receipt
                state.update(status='running', active_slot=None)
                derived(root/'status.json', encode(state))
                print(json.dumps(dict(completed=len(state['completed']), planned=len(manifest['slots']))), flush=True)
            except (ValueError, OSError, subprocess.SubprocessError) as error:
                state['failures'].append(dict(slot=cell['id'], reason=str(error)))
                state['status'] = 'incomplete'
                derived(root/'status.json', encode(state))
                raise
        state['status'] = 'complete'
        derived(root/'status.json', encode(state))
    return state['status']


def analyze(root):
    manifest, parent, state = preflight(root)
    parent_root = Path(manifest['parent_root'])
    observations, missing = {}, []
    for cell in manifest['slots']:
        if cell['id'] not in state['completed']:
            missing.append(cell['id'])
            continue
        origin = parent_root if cell['id'] in manifest['inherited'] else root
        _, receipt = study.adopt(origin, parent, cell)
        if receipt is None:
            raise ValueError('completion receipt has no complete export')
        if cell['stage'] == 'main':
            observations[(cell['arm'], cell['config']['pack'], cell['config']['seed'])] = receipt
    comparisons = []
    spec = study.StudySpec.model_validate(parent['spec'])
    for contrast in parent['hypotheses']:
        try:
            values = study.effects_for_panel(observations, spec, contrast['arm'], contrast['panel'])
            inference = study.paired_inference(values, materiality=.01)
            p = inference['wilcoxon']['pvalue'] if inference['wilcoxon']['status'] == 'available' else 1.
            comparisons.append(dict(**contrast, **inference, pvalue=p))
        except KeyError:
            comparisons.append(dict(**contrast, status='missing_paired_cells', pvalue=1.))
    adjusted = 0.
    for index, result in enumerate(sorted(comparisons, key=lambda r: r['pvalue'])):
        adjusted = max(adjusted, min(1., result['pvalue']*(len(comparisons)-index)))
        ci = result['bootstrap_ci95'] if 'bootstrap_ci95' in result else None
        result.update(holm_pvalue=adjusted, material_gain=bool(not missing and not state['failures'] and ci and ci[0] > .01 and adjusted < .05))
    report = dict(status='incomplete' if missing or state['failures'] else 'complete', missing=missing,
                  manifest_sha256=manifest['sha256'], original_study_status='incomplete',
                  prior_failed_run_cost=manifest['retained_failures'], inherited_runs=len(manifest['inherited']),
                  contrasts=comparisons, observations=[dict(arm=k[0], pack=k[1], seed=k[2], **v) for k, v in observations.items()],
                  interpretation=manifest['interpretation']+' Pointwise 95% intervals; original 30-contrast Holm family retained.')
    derived(root/'analysis.json', encode(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'preflight', 'run', 'analyze'))
    parser.add_argument('workspace', type=Path)
    parser.add_argument('--parent', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        if args.parent is None:
            parser.error('--parent required for preparation')
        result = prepare(args.parent, args.workspace)
    elif args.command == 'preflight':
        manifest, _, state = preflight(args.workspace)
        result = dict(status='passed', completed=len(state['completed']), planned=len(manifest['slots']))
    elif args.command == 'run':
        result = {'status': run(args.workspace)}
        if result['status'] == 'complete':
            analyze(args.workspace)
    else:
        result = analyze(args.workspace)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
