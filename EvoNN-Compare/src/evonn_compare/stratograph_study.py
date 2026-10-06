"""User-authorized within-Stratograph study; no cross-engine superiority claims.

Preparation performs data work only. Ordinary all-engine CampaignSpec admission
remains unchanged. Execution uses Stratograph's CLI and verified export boundary.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from evonn_shared.active_catalog import get_benchmark, load_parity_pack
from evonn_shared.artifact_io import publish_artifact, read_verified_artifact
from evonn_shared.datasets import array_digest
from evonn_shared.engine_evidence import artifact_json, validate_engine_bundle
from evonn_shared.export_reader import read_document, read_export
from evonn_shared.hierarchy_presets import hierarchy_presets
from evonn_shared.runtime_io import derived, encode
from evonn_shared.telemetry import ArtifactReference
from .campaign import _bounded_process, identity, lease, sha
from .statistics import paired_inference


PANELS = {
    'core': ('tier_b_core_v2', ('banknote_classification', 'digits_image', 'diabetes_regression', 'shakespeare_byte_lm')),
    'real_text': ('language_breadth_v1', ('shakespeare_byte_lm', 'shakespeare_context64_lm', 'aesop_context64_lm')),
    'memory': ('language_breadth_v1', ('delayed_copy_lm',)),
}
SCOPE = 'Explicit user request: compare only the 11 current Stratograph presets; no other engines.'


def execution_environment():
    names = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS',
             'EVONN_SHARED_BENCHMARKS_DIR', 'PYTHONPATH')
    return {name: os.environ[name] if name in os.environ else None for name in names}


class StudySpec(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    arms: list[str] = Field(default_factory=lambda: list(hierarchy_presets()))
    seeds: list[int] = Field(default_factory=lambda: list(range(1701, 1717)))
    qualification_seed: int = 1799
    budget: int = 128
    qualification_budget: int = 16
    epochs: int = 12
    timeout: float = 1500.
    fit_timeout: float = 120.
    backend: str = 'mlx_native'

    @model_validator(mode='after')
    def valid(self):
        if self.arms != list(hierarchy_presets()):
            raise ValueError('this protocol requires all eleven fixed Stratograph presets')
        if len(self.seeds) < 16 or len(set(self.seeds)) != len(self.seeds):
            raise ValueError('at least sixteen unique paired seeds required')
        if self.qualification_seed in self.seeds or any(not 0 <= s < 2**32 for s in [*self.seeds, self.qualification_seed]):
            raise ValueError('disjoint valid qualification and main seeds required')
        if any(not 16 <= b <= 256 or b % 4 for b in (self.budget, self.qualification_budget)):
            raise ValueError('budgets must be multiples of four in [16,256]')
        if (not 1 <= self.epochs <= 100 or not 0 < self.fit_timeout <= self.timeout <= 1500
                or self.backend not in ('mlx_native', 'numpy_fallback')):
            raise ValueError('invalid bounded execution settings')
        return self


def slots(spec):
    policies = hierarchy_presets()
    result = []
    packs = ('tier_b_core_v2', 'language_breadth_v1')
    for stage, seeds, budget in [('qualification', [spec.qualification_seed], spec.qualification_budget),
                                 ('main', spec.seeds, spec.budget)]:
        # Rotate the arm order within each paired block to distribute host drift.
        for block, seed in enumerate(seeds):
            for offset, pack in enumerate(packs):
                rotation = (block + offset) % len(spec.arms)
                arms = spec.arms[rotation:] + spec.arms[:rotation]
                for arm in arms:
                    config = dict(pack=pack, budget=budget, seed=seed, epochs=spec.epochs,
                                  population_size=4, variant='shared', target_device='cpu',
                                  backend=spec.backend, timeout=spec.timeout, fit_timeout=spec.fit_timeout,
                                  research=policies[arm].model_dump(mode='json'))
                    result.append(dict(id=f'{stage}-{pack}-s{seed}-{arm}', stage=stage, arm=arm, config=config))
    return result


def hypotheses(spec):
    return [dict(arm=arm, reference='v2_reference', panel=panel)
            for arm in spec.arms if arm != 'v2_reference' for panel in PANELS]


def read_plan(root):
    value = json.loads(read_document(root, 'study.json'))
    if value.get('schema_version') != 'stratograph-only/v1' or value.get('sha256') != sha({k: v for k, v in value.items() if k != 'sha256'}):
        raise ValueError('study manifest hash/schema mismatch')
    spec = StudySpec.model_validate(value['spec'])
    if value['slots'] != slots(spec) or value['hypotheses'] != hypotheses(spec):
        raise ValueError('study cells or hypotheses differ from frozen specification')
    return value


def preflight(root):
    plan = read_plan(root)
    spec = StudySpec.model_validate(plan['spec'])
    if identity() != plan['identity']:
        raise ValueError('frozen producer, dependencies, catalog or host changed')
    if execution_environment() != plan['execution_environment']:
        raise ValueError('thread settings or import/data paths changed')
    if shutil.disk_usage(root).free < 4 * 1024**3:
        raise ValueError('at least 4 GiB free disk reserve required')
    if spec.backend == 'mlx_native':
        import mlx.core as mx
        mx.eval(mx.array([1.]) + 1)
    expected = {(name, seed) for seed in [spec.qualification_seed, *spec.seeds]
                for pack in ('tier_b_core_v2', 'language_breadth_v1') for name in load_parity_pack(pack).benchmarks}
    actual = [(d['benchmark_id'], d['seed']) for d in plan['datasets']]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError('incomplete or duplicated frozen datasets')
    for data in plan['datasets']:
        arrays = {}
        for item in data['cache_artifacts']:
            payload = read_verified_artifact(Path(data['cache_directory']), ArtifactReference(path=item['path'], sha256=item['sha256']), size_bytes=item['size_bytes'])
            arrays[Path(item['path']).stem] = np.load(io.BytesIO(payload), allow_pickle=False)
        if set(arrays) != {'x_train', 'y_train', 'x_validation', 'y_validation'} or array_digest(arrays) != data['split_sha256']:
            raise ValueError('dataset cache drift')
    return dict(status='passed', planned_runs=len(plan['slots']), training_started=False,
                plan_sha256=plan['sha256'], prepared_dataset_splits=len(actual))


def prepare(root, cache, spec, *, timeout=1800):
    root, cache = root.absolute(), cache.absolute()
    pinned = identity()
    deadline = time.monotonic() + timeout
    with lease(root):
        if (root / 'study.json').exists():
            raise ValueError('study already prepared; use preflight')
        preparation = root / 'preparation'
        preparation.mkdir(exist_ok=False)
        pairs = sorted({(seed, name) for slot in slots(spec) for seed in [slot['config']['seed']]
                        for name in load_parity_pack(slot['config']['pack']).benchmarks})
        data = []
        for index, (seed, name) in enumerate(pairs):
            output = preparation / f'{name}-{seed}.json'
            _bounded_process([sys.executable, '-m', 'evonn_compare.campaign_worker', 'prepare', name, str(seed), str(cache), str(output)],
                             min(120., deadline-time.monotonic()), output.with_suffix('.log'))
            data.append(json.loads(output.read_text()))
            print(f'Prepared {index+1}/{len(pairs)} dataset splits', flush=True)
        if identity() != pinned:
            raise ValueError('producer changed during preparation')
        value = dict(schema_version='stratograph-only/v1', scope=SCOPE, spec=spec.model_dump(),
                     slots=slots(spec), hypotheses=hypotheses(spec), identity=pinned,
                     execution_environment=execution_environment(),
                     cache=str(cache), datasets=data, analysis=dict(
                         unit='independent paired seed; candidate fits are not replicates',
                         effect='mean within seed of signed 2*(candidate-reference)/(abs(candidate)+abs(reference)); lower-is-better metrics reverse sign; ties contribute zero',
                         inference='paired_inference: pointwise 95% bootstrap CI and two-sided signed-rank permutation',
                         multiplicity='Holm over all 30 declared arm/reference/panel contrasts; missing tests retain p=1',
                         materiality=.01, alpha=.05, protected_tests='unused',
                         claims='within-Stratograph validation performance only; no automatic unique-winner or cross-engine claim',
                         stopping='no outcome-driven early stopping or arm removal; failed slots keep study incomplete'))
        publish_artifact(root/'study.json', encode({**value, 'sha256': sha(value)}))
    return preflight(root)


def adopt(root, plan, slot):
    directory = root / 'runs' / slot['id']
    found = list(directory.iterdir()) if directory.exists() else []
    if len(found) > 1 or any(not p.is_dir() or p.is_symlink() for p in found):
        raise ValueError('ambiguous/unsafe run directory; never silently replace an attempt')
    if not found:
        return None, None
    run = found[0]
    if not (run/'symbiosis').exists():
        return run, None
    bundle = read_export(run/'symbiosis')
    validate_engine_bundle(bundle, verify_cache=True)
    cfg = artifact_json(bundle, 'config.yaml')
    planned = slot['config']
    expected = {k: v for k, v in planned.items() if k not in ('budget', 'target_device')}
    expected.update(total=planned['budget'], device=planned['target_device'],
                    source_sha256=plan['identity']['source_sha256'], git_commit=plan['identity']['commit'], code_dirty=False)
    if bundle.manifest.system.value != 'stratograph' or any(k not in cfg or cfg[k] != v for k, v in expected.items()):
        raise ValueError('export differs from frozen Stratograph slot')
    host = plan['identity']['host']
    host_record = dict(host=host[0], system=host[1], machine=host[2], processor=host[3])
    runtime = bundle.manifest.runtime
    if (runtime.host_fingerprint != hashlib.sha256(encode(host_record)).hexdigest()
            or runtime.backend.value != planned['backend']
            or runtime.device_class != host[1].lower()+'_'+host[2]+'_cpu'):
        raise ValueError('export runtime differs from frozen host/backend')
    data = artifact_json(bundle, 'dataset_provenance.json')
    names = set(load_parity_pack(planned['pack']).benchmarks)
    expected_data = [d for d in plan['datasets'] if d['seed'] == planned['seed'] and d['benchmark_id'] in names]
    if sorted(data, key=lambda d: d['benchmark_id']) != sorted(expected_data, key=lambda d: d['benchmark_id']):
        raise ValueError('paired dataset provenance mismatch')
    if bundle.manifest.status.value != 'completed' or bundle.results.coverage.ok != planned['budget']:
        raise ValueError('incomplete/failed slot; scientific completion is blocked')
    attempts = artifact_json(bundle, 'attempts.json')['attempts']
    if any(a['status'] != 'ok' for a in attempts) or len(attempts) != planned['budget']:
        raise ValueError('failed/invalid attempts cannot be hidden from the study')
    metrics = {w.benchmark_id: w.value for w in bundle.summary.best_per_benchmark}
    if set(metrics) != names:
        raise ValueError('missing winner panel')
    documents = {name: hashlib.sha256((bundle.root/name).read_bytes()).hexdigest() for name in ('manifest.json', 'results.json', 'summary.json')}
    return run, dict(export=str(bundle.root.relative_to(root)), documents=documents, metrics=metrics,
                     train_seconds=sum(a['train_seconds'] for a in attempts),
                     optimizer_updates=sum(a['updates'] for a in attempts))


def run_session(root, *, session_timeout=1800., max_runs=None):
    if not 0 < session_timeout <= 1800 or (max_runs is not None and max_runs < 1):
        raise ValueError('bounded positive session/run limits required')
    root = root.absolute()
    deadline, launched = time.monotonic()+session_timeout, 0
    with lease(root) as descriptor:
        preflight(root)
        plan = read_plan(root)
        state = (json.loads(read_document(root, 'status.json')) if (root/'status.json').exists()
                 else dict(plan_sha256=plan['sha256'], status='prepared', completed={}, failures=[]))
        if state['plan_sha256'] != plan['sha256'] or state['failures']:
            raise ValueError('plan drift or retained failure requires investigation; no automatic retry')
        for slot in plan['slots']:
            if slot['id'] in state['completed']:
                receipt = state['completed'][slot['id']]
                for name, expected in receipt['documents'].items():
                    if hashlib.sha256((root/receipt['export']/name).read_bytes()).hexdigest() != expected:
                        raise ValueError('completed export document drift')
                if hashlib.sha256((root/receipt['replay']).read_bytes()).hexdigest() != receipt['replay_sha256']:
                    raise ValueError('completed replay receipt drift')
                continue
            if (root/'PAUSE').exists() or (max_runs is not None and launched >= max_runs) or deadline-time.monotonic() < slot['config']['timeout']+200:
                state['status'] = 'paused'
                break
            state.update(status='running', active_slot=slot['id'])
            derived(root/'status.json', encode(state))
            work = root/'dispatch'/slot['id']
            work.mkdir(parents=True, exist_ok=True)
            sequence = len(list(work.glob('*.log')))
            try:
                existing, receipt = adopt(root, plan, slot)
                if receipt is None:
                    command = [sys.executable, '-m', 'stratograph.cli', 'run']
                    if existing is not None:
                        command += ['--resume', str(existing)]
                    else:
                        config = work/'config.json'
                        if not config.exists():
                            publish_artifact(config, encode(slot['config']))
                        elif json.loads(config.read_text()) != slot['config']:
                            raise ValueError('dispatch configuration drift')
                        command += ['--config', str(config), '--output', str(root/'runs'/slot['id']), '--cache', plan['cache']]
                    _bounded_process(command, slot['config']['timeout']+20, work/f'{sequence:04d}.log', pass_fds=(descriptor,))
                    existing, receipt = adopt(root, plan, slot)
                    if receipt is None:
                        raise ValueError('engine returned without a complete verified export')
                replay = work/f'{sequence:04d}.replay.json'
                _bounded_process([sys.executable, '-m', 'stratograph.cli', 'replay', str(existing)],
                                 min(180., deadline-time.monotonic()), work/f'{sequence:04d}.replay.log',
                                 stdout_path=replay, pass_fds=(descriptor,))
                if json.loads(replay.read_text())['status'] != 'passed':
                    raise ValueError('saved-winner replay failed')
                receipt['replay_sha256'] = hashlib.sha256(replay.read_bytes()).hexdigest()
                receipt['replay'] = str(replay.relative_to(root))
                state['completed'][slot['id']] = receipt
                launched += 1
            except (ValueError, OSError, TimeoutError, subprocess.SubprocessError) as error:
                state['failures'].append(dict(slot=slot['id'], reason=str(error)))
                state['status'] = 'incomplete'
                derived(root/'status.json', encode(state))
                raise
            state['active_slot'] = None
            derived(root/'status.json', encode(state))
        else:
            state['status'] = 'complete'
        derived(root/'status.json', encode(state))
    return dict(status=state['status'], completed=len(state['completed']), planned=len(plan['slots']))


def effects_for_panel(observations, spec, arm, panel):
    pack, names = PANELS[panel]
    effects = []
    for seed in spec.seeds:
        values = []
        for name in names:
            before = observations[('v2_reference', pack, seed)]['metrics'][name]
            after = observations[(arm, pack, seed)]['metrics'][name]
            denominator = abs(before)+abs(after)
            delta = 2*(after-before)/denominator if denominator else 0.
            values.append(delta if get_benchmark(name).primary_metric.direction.value == 'max' else -delta)
        effects.append(float(np.mean(values)))
    return effects


def analyze(root):
    plan = read_plan(root)
    spec = StudySpec.model_validate(plan['spec'])
    observations, missing = {}, []
    state = json.loads(read_document(root, 'status.json')) if (root/'status.json').exists() else {'completed': {}}
    for slot in plan['slots']:
        if slot['id'] not in state['completed']:
            missing.append(slot['id'])
            continue
        _, observed = adopt(root, plan, slot)
        receipt = state['completed'][slot['id']]
        replay = root/receipt['replay']
        if hashlib.sha256(replay.read_bytes()).hexdigest() != receipt['replay_sha256'] or json.loads(replay.read_text())['status'] != 'passed':
            raise ValueError('missing or changed winner replay')
        if slot['stage'] == 'main':
            observations[(slot['arm'], slot['config']['pack'], slot['config']['seed'])] = observed
    comparisons = []
    failures = state.get('failures', [])
    for contrast in plan['hypotheses']:
        try:
            effects = effects_for_panel(observations, spec, contrast['arm'], contrast['panel'])
            inference = paired_inference(effects, materiality=.01)
            p = inference['wilcoxon']['pvalue'] if inference['wilcoxon']['status'] == 'available' else 1.
            comparisons.append(dict(**contrast, **inference, pvalue=p))
        except KeyError:
            comparisons.append(dict(**contrast, status='missing_paired_cells', pvalue=1.))
    adjusted = 0.
    for index, result in enumerate(sorted(comparisons, key=lambda r: r['pvalue'])):
        adjusted = max(adjusted, min(1., result['pvalue']*(len(comparisons)-index)))
        result['holm_pvalue'] = adjusted
        ci = result['bootstrap_ci95'] if 'bootstrap_ci95' in result else None
        result['material_gain'] = bool(not missing and not failures and ci and ci[0] > .01 and adjusted < .05)
    report = dict(status='incomplete' if missing or failures else 'complete', missing=missing, failures=failures,
                  plan_sha256=plan['sha256'], contrasts=comparisons,
                  observations=[dict(arm=k[0], pack=k[1], seed=k[2], **v) for k, v in observations.items()],
                  interpretation='Pointwise 95% intervals; Holm correction spans all 30 tests. Non-significance does not establish equivalence. No cross-engine or protected-test claim.')
    derived(root/'analysis.json', encode(report))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    preparing = commands.add_parser('prepare')
    preparing.add_argument('workspace', type=Path)
    preparing.add_argument('--cache', type=Path, required=True)
    preparing.add_argument('--spec', type=Path)
    for name in ('preflight', 'run', 'analyze'):
        command = commands.add_parser(name)
        command.add_argument('workspace', type=Path)
        if name == 'run':
            command.add_argument('--max-runs', type=int)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        spec = StudySpec.model_validate_json(args.spec.read_text()) if args.spec else StudySpec()
        result = prepare(args.workspace, args.cache, spec)
    elif args.command == 'preflight':
        result = preflight(args.workspace)
    elif args.command == 'run':
        result = run_session(args.workspace, max_runs=args.max_runs)
    else:
        result = analyze(args.workspace)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
