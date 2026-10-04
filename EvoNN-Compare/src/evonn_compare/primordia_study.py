"""Frozen Primordia-only variant study, explicitly requested on 2026-09-21."""
import argparse
from itertools import combinations
import json
import math
from pathlib import Path
import sys
import uuid

import numpy as np

from evonn_shared.artifact_io import publish_artifact
from evonn_shared.export_reader import read_export
from evonn_shared.primordia_policy import PrimordiaResearchPolicy
from evonn_shared.primordia_presets import ARMS
from . import campaign as c
from .audit import artifact_json
from .baseline_study import validate_replay

PACKS = ['tier_b_core_v2', 'language_breadth_v1']
SEEDS = list(range(23101, 23117))
QUALIFICATION_SEED = 23191
ENDPOINTS = [
    ('tier_b_core_v2', 'digits_image', 'max', .005),
    ('tier_b_core_v2', 'diabetes_regression', 'min', math.log(1.02)),
    ('tier_b_core_v2', 'shakespeare_byte_lm', 'min', math.log(1.02)),
    ('language_breadth_v1', 'shakespeare_context64_lm', 'min', math.log(1.02)),
    ('language_breadth_v1', 'aesop_context64_lm', 'min', math.log(1.02)),
    ('language_breadth_v1', 'delayed_copy_lm', 'min', math.log(1.05)),
]
POLICY = dict(
    schema_version='evonn.primordia-variant-study/v1',
    authorization='User explicitly requested a comparison of only Primordias current versions on 2026-09-21; scoped exception to the usual all-engine roster.',
    systems=['primordia'], arms=ARMS, seeds=SEEDS, qualification_seed=QUALIFICATION_SEED,
    packs=PACKS, budget=256, epochs=12, qualification_budget=64, qualification_epochs=2,
    backend='mlx_native', device='cpu', population_size=4, max_width=48, max_depth=8,
    timeout=1740., fit_timeout=120., runs=416, fits=106496, qualification_runs=26, qualification_fits=1664,
    endpoints=[dict(pack=p, benchmark=b, direction=d, materiality=m) for p, b, d, m in ENDPOINTS],
    contrasts='All 78 unordered preset pairs on each of six declared endpoints: 468 tests, one frozen Holm family.',
    uncertainty='20000 paired-seed bootstrap resamples, RNG 23100; pointwise percentile CI95 and simultaneous 95% max-standardized-deviation intervals across all 468 contrasts. Approximate finite-sample intervals; zero sample variance cannot establish material superiority.',
    test='Exact two-sided sign-flip test of mean paired effects, all 65536 assignments, then Holm FWER 0.05. Assumes independent seed blocks and symmetric paired effects under the null; ties retained.',
    effect='Accuracy: raw accuracy difference. Lower-is-better: log(before/after); positive favors after. No averaging of regression, image, real language and synthetic memory into one winner.',
    decision='Only after all slots and winner replays pass: supported material gain requires Holm p<=0.05 and simultaneous lower bound>materiality; loss is symmetric. An equivalence label requires the simultaneous interval strictly inside +/-materiality. Otherwise inconclusive. No overall champion or engine promotion.',
    sentinels='Banknote and breadth Shakespeare bridge are reported descriptively; banknote ceiling ties get no win credit. Delayed copy is a separate synthetic endpoint, never pooled with real text.',
    runtime='Report summed measured attempt training seconds and actual optimizer updates separately per pack/seed; runtime is descriptive, with no matched-compute or wall-clock superiority claim.',
    scheduling='Seed blocks; rotate/reverse preset order and alternate pack order. Serial execution on the pinned host; no optional stopping for favorable results.',
    failures='Stop on incomplete/failed slots, preserve artifacts, never omit or replace an arm/seed. Source changes require a new study. Incomplete matrices get no inferential decisions.',
    protected_test_access=False, training_started_by_preparation=False,
    limits='Validation-selected winners on fixed datasets and repeated seeds, not independent dataset replication or protected-test generalization. Sixteen seeds do not guarantee power; inconclusive is a valid outcome.',
    references=['https://docs.scipy.org/doc/scipy-1.15.2/reference/generated/scipy.stats.wilcoxon.html',
                'https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html'],
)


def specification(arm, pack, *, qualification=False):
    return c.CampaignSpec(pack=pack, budgets=[64 if qualification else 256],
        seeds=[QUALIFICATION_SEED] if qualification else SEEDS, systems=['primordia'],
        comparison_scope='primordia_variants_v1', backend='mlx_native', epochs=2 if qualification else 12,
        primordia_research=PrimordiaResearchPolicy(**ARMS[arm]), timeout=1740., fit_timeout=120.,
        min_free_bytes=20 * 1024**3)


def matrix():
    return [dict(phase=phase, arm=arm, pack=pack, campaign=f'{phase}/{arm}/{pack}',
                 spec=specification(arm, pack, qualification=phase == 'qualification').model_dump(mode='json'))
            for phase in ('qualification', 'comparison') for arm in ARMS for pack in PACKS]


def schedule(phase):
    if phase not in {'qualification', 'comparison'}:
        raise ValueError('unknown study phase')
    rows = []
    arms = list(ARMS)
    for index, seed in enumerate([QUALIFICATION_SEED] if phase == 'qualification' else SEEDS):
        order = arms[index % len(arms):] + arms[:index % len(arms)]
        if index % 2:
            order.reverse()
        for arm_index, arm in enumerate(order):
            for pack in PACKS if (index + arm_index) % 2 == 0 else list(reversed(PACKS)):
                rows.append(dict(phase=phase, seed=seed, arm=arm, pack=pack,
                                 campaign=f'{phase}/{arm}/{pack}'))
    return rows


def seed_audit():
    requested = set(SEEDS + [QUALIFICATION_SEED])
    checked = []

    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {'seed', 'seeds', 'qualification_seed'}:
                    values = item if isinstance(item, list) else [item]
                    if requested.intersection(v for v in values if type(v) is int):
                        raise ValueError('study seeds overlap prior recorded evidence: ' + str(path))
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    for path in sorted([*(c.ROOT / 'governance').rglob('*.json'), *(c.ROOT / 'reports').rglob('*.json')]):
        payload = path.read_bytes()
        visit(json.loads(payload))
        checked.append(dict(path=str(path.relative_to(c.ROOT)), sha256=c.hashlib.sha256(payload).hexdigest()))
    return dict(requested=sorted(requested), files=checked,
                scope='Repository governance/reports JSON; qualification and comparison seeds disjoint. This is not an audit of arbitrary external or deleted runs.')


def prepare(root, cache):
    root, cache = root.absolute(), cache.absolute()
    if root.exists():
        raise ValueError('use a fresh study directory; never overwrite a protocol')
    pinned, audit = c.identity(), seed_audit()
    root.mkdir(parents=True)
    datasets = []
    prep = root / 'preparation'
    prep.mkdir()
    benchmarks = sorted({b for p in PACKS for b in c.load_parity_pack(p).benchmarks})
    # Prepare each split once; all arm manifests bind the same verified bytes.
    for seed in [QUALIFICATION_SEED, *SEEDS]:
        for benchmark in benchmarks:
            output = prep / f'{benchmark}-{seed}.json'
            c._bounded_process([sys.executable, '-m', 'evonn_compare.campaign_worker', 'prepare',
                                benchmark, str(seed), str(cache), str(output)], 180,
                               output.with_suffix('.log'))
            datasets.append(json.loads(output.read_bytes()))
        print(json.dumps(dict(prepared_seed=seed, splits=len(datasets), total_splits=len(benchmarks) * 17)), flush=True)
    rows = matrix()
    manifests = {}
    for row in rows:
        workspace = root / row['campaign']
        spec = c.CampaignSpec.model_validate(row['spec'])
        names = c.load_parity_pack(spec.pack).benchmarks
        value = dict(schema_version='evonn.campaign/v1', spec=row['spec'], identity=pinned,
                     cache=str(cache), workspace=str(workspace),
                     datasets=[d for d in datasets if d['seed'] in spec.seeds and d['benchmark_id'] in names])
        with c.lease(workspace):
            publish_artifact(workspace / 'campaign.json', c.encoded({**value, 'sha256': c.sha(value)}))
        manifests[row['campaign']] = c.preflight(workspace)['manifest_sha256']
    if c.identity() != pinned:
        raise ValueError('producer/environment changed during preparation; retain and reprepare separately')
    value = dict(policy=POLICY, identity=pinned, matrix=rows, seed_audit=audit, campaign_sha256=manifests,
                 workspace=str(root), schedule={phase: schedule(phase) for phase in ('qualification', 'comparison')})
    publish_artifact(root / 'study.json', c.encoded({**value, 'sha256': c.sha(value)}))
    return preflight(root)


def read_plan(root):
    value = json.loads(c.read_document(root, 'study.json'))
    if (set(value) != {'policy', 'identity', 'matrix', 'seed_audit', 'workspace', 'schedule', 'sha256', 'campaign_sha256'}
            or value['sha256'] != c.sha({k: v for k, v in value.items() if k != 'sha256'})
            or value['workspace'] != str(root.absolute()) or value['policy'] != POLICY
            or value['matrix'] != matrix()
            or value['schedule'] != {phase: schedule(phase) for phase in ('qualification', 'comparison')}):
        raise ValueError('study protocol, matrix, schedule or identity binding differs')
    for row in value['matrix']:
        manifest = c.read_manifest(root / row['campaign'])
        if (manifest['spec'] != row['spec'] or manifest['identity'] != value['identity']
                or manifest['sha256'] != value['campaign_sha256'][row['campaign']]):
            raise ValueError('campaign differs from frozen Primordia study')
    return value


def preflight(root):
    plan = read_plan(root)
    if c.identity() != plan['identity']:
        raise ValueError('study producer/environment drift')
    for row in plan['matrix']:
        c.preflight(root / row['campaign'])
    return dict(status='prepared', qualification_runs=26, comparison_runs=416,
                fit_attempts=108160, study_sha256=plan['sha256'], training_started=False,
                qualification='required before comparison', scientific_decision='not_evaluated')


def replay_slot(workspace, case, run, reference):
    directory = workspace / 'replays'
    directory.mkdir(exist_ok=True)
    path = directory / (case.id + '.json')
    if not path.exists():
        log = directory / (case.id + '-' + uuid.uuid4().hex + '.log')
        output = log.with_suffix('.stdout.json')
        c._bounded_process([sys.executable, '-m', 'evonn_primordia.cli', 'replay', str(run)], 300, log, stdout_path=output)
        value = json.loads(output.read_bytes())
        validate_replay(value, reference['run_id'], case.pack)
        publish_artifact(path, c.encoded(dict(reference=reference, replay=value)))
    value = json.loads(c.read_document(directory, path.name))
    if value['reference'] != reference:
        raise ValueError('saved replay refers to different run evidence')
    validate_replay(value['replay'], reference['run_id'], case.pack)
    return value


def collect(root, phase):
    rows, missing = [], []
    for item in schedule(phase):
        workspace = root / item['campaign']
        manifest = c.read_manifest(workspace)
        case = c.Case(item['pack'], 64 if phase == 'qualification' else 256, item['seed'])
        try:
            run, reference = c.adopted(workspace, manifest, case, 'primordia')
            if reference is None:
                raise ValueError('not complete')
            replay = json.loads(c.read_document(workspace / 'replays', case.id + '.json'))
            if replay['reference'] != reference:
                raise ValueError('replay evidence changed')
            validate_replay(replay['replay'], reference['run_id'], case.pack)
            bundle = read_export(run / 'symbiosis')
            attempts = artifact_json(bundle, 'trial_records.json')
            if any(a['status'] != 'ok' or a['charged'] != 1 for a in attempts) or len(attempts) != case.budget:
                raise ValueError('failed or uncharged attempts; study remains incomplete')
            winners = artifact_json(bundle, 'best_results.json')
            rows.append({**item, 'reference': reference,
                         'scores': {key: value['quality'] for key, value in winners.items()},
                         'train_seconds': sum(a['train_seconds'] for a in attempts),
                         'optimizer_updates': sum(a['updates'] for a in attempts)})
        except (ValueError, OSError) as error:
            missing.append({**item, 'reason': str(error)})
    return rows, missing


def run(root, *, phase='all', max_runs=None):
    if phase not in {'all', 'qualification', 'comparison'} or (max_runs is not None and max_runs < 1):
        raise ValueError('invalid phase or run limit')
    with c.lease(root / 'controller'):
        preflight(root)
        launched = 0
        phases = ['qualification', 'comparison'] if phase == 'all' else [phase]
        for current in phases:
            if current == 'comparison':
                _, missing = collect(root, 'qualification')
                if missing:
                    raise ValueError('all 26 qualification slots and winner replays must pass first')
            for item in schedule(current):
                if (root / 'PAUSE').exists():
                    return dict(status='paused', new_runs=launched)
                if max_runs is not None and launched >= max_runs:
                    return dict(status='paused', new_runs=launched)
                workspace = root / item['campaign']
                manifest = c.read_manifest(workspace)
                case = c.Case(item['pack'], 64 if current == 'qualification' else 256, item['seed'])
                _, before_reference = c.adopted(workspace, manifest, case, 'primordia')
                if before_reference is None:
                    result = c.run_campaign(workspace, max_runs=1)
                    launched += result['new_runs']
                model_run, reference = c.adopted(workspace, manifest, case, 'primordia')
                if reference is None:
                    raise ValueError('scheduled slot incomplete; retained for diagnosis/resume')
                bundle = read_export(model_run / 'symbiosis')
                attempts = artifact_json(bundle, 'trial_records.json')
                if len(attempts) != case.budget or any(a['status'] != 'ok' or a['charged'] != 1 for a in attempts):
                    raise ValueError('failed/uncharged fit in scheduled slot; retained and study stopped')
                replay_slot(workspace, case, model_run, reference)
                print(json.dumps({**item, 'status': 'complete', 'new_runs': launched}), flush=True)
        return report(root)


def inference(rows):
    expected = {(a, p, s) for a in ARMS for p in PACKS for s in SEEDS}
    keys = [(r['arm'], r['pack'], r['seed']) for r in rows]
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError('complete unique paired-seed matrix required for inference')
    scores = {(r['arm'], r['pack'], r['seed']): r['scores'] for r in rows}
    columns, effects = [], []
    for pack, benchmark, direction, margin in ENDPOINTS:
        for before, after in combinations(ARMS, 2):
            left = np.array([scores[(before, pack, seed)][benchmark] for seed in SEEDS], dtype=float)
            right = np.array([scores[(after, pack, seed)][benchmark] for seed in SEEDS], dtype=float)
            if not np.isfinite(left).all() or not np.isfinite(right).all() or (direction == 'min' and (np.any(left <= 0) or np.any(right <= 0))):
                raise ValueError('invalid endpoint scores')
            delta = right - left if direction == 'max' else np.log(left / right)
            effects.append(delta)
            columns.append(dict(pack=pack, benchmark=benchmark, before=before, after=after,
                                effect_scale='accuracy_difference' if direction == 'max' else 'log_ratio', materiality=margin))
    array = np.asarray(effects).T
    n, count = array.shape
    means, se = array.mean(axis=0), array.std(axis=0, ddof=1) / math.sqrt(n)
    nondegenerate = se > 1e-12
    rng = np.random.default_rng(23100)
    samples = np.zeros((20000, count), dtype=float)
    for start in range(0, len(samples), 250):
        indices = rng.integers(0, n, size=(min(250, len(samples) - start), n))
        samples[start:start + len(indices)] = array[indices].mean(axis=1)
    pointwise = np.quantile(samples, [.025, .975], axis=0)
    critical = (float(np.quantile(np.max(np.abs((samples[:, nondegenerate] - means[nondegenerate]) / se[nondegenerate]), axis=1), .95))
                if nondegenerate.any() else 0.)
    extreme = np.zeros(count, dtype=np.int64)
    for start in range(0, 2**n, 512):
        assignments = np.arange(start, min(start + 512, 2**n), dtype=np.uint32)
        signs = ((assignments[:, None] >> np.arange(n, dtype=np.uint32)) & 1).astype(float) * 2 - 1
        permuted = signs @ array / n
        extreme += (np.abs(permuted) >= np.abs(means) - 1e-12).sum(axis=0)
    pvalues = extreme / 2**n
    order = np.argsort(pvalues, kind='stable')
    adjusted = np.ones(count)
    adjusted[order] = np.minimum(1., np.maximum.accumulate(pvalues[order] * (count - np.arange(count))))
    for i, row in enumerate(columns):
        interval = [float(means[i] - critical * se[i]), float(means[i] + critical * se[i])] if nondegenerate[i] else None
        decision = 'inconclusive'
        if interval is not None:
            if adjusted[i] <= .05 and interval[0] > row['materiality']:
                decision = 'after_supported_material_gain'
            elif adjusted[i] <= .05 and interval[1] < -row['materiality']:
                decision = 'after_supported_material_loss'
            elif interval[0] > -row['materiality'] and interval[1] < row['materiality']:
                decision = 'within_materiality_interval'
        if np.all(array[:, i] == 0):
            decision = 'observed_exact_tie'
        row.update(n=n, seed_effects=array[:, i].tolist(), mean_effect=float(means[i]),
                   pointwise_ci95=pointwise[:, i].tolist(), simultaneous_ci95=interval,
                   pvalue=float(pvalues[i]), holm_pvalue=float(adjusted[i]), decision=decision,
                   zero_sample_variance=not bool(nondegenerate[i]))
    return dict(contrasts=columns, family_size=count, bootstrap_draws=20000,
                permutations=2**n, simultaneous_critical_value=critical,
                overall_winner=None, scope='paired validation performance only')


def report(root):
    plan = read_plan(root)
    qualification, qmissing = collect(root, 'qualification')
    rows, missing = collect(root, 'comparison')
    complete = not qmissing and not missing
    value = dict(study_sha256=plan['sha256'], status='complete' if complete else 'incomplete',
                 qualification_complete=len(qualification), comparison_complete=len(rows),
                 missing_qualification=qmissing, missing_comparison=missing, rows=rows,
                 inference=inference(rows) if complete else None, protected_test_access=False)
    output = root / ('analysis-' + uuid.uuid4().hex + '.json')
    publish_artifact(output, c.encoded(value))
    return {**{key: value[key] for key in ('status', 'qualification_complete', 'comparison_complete')},
            'report': str(output), 'scientific_decision': 'see scoped contrasts' if complete else 'not_evaluated'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('workspace', type=Path)
    prep.add_argument('--cache', required=True, type=Path)
    for name in ('preflight', 'report', 'pause', 'resume', 'run'):
        command = commands.add_parser(name)
        command.add_argument('workspace', type=Path)
        if name in {'run', 'resume'}:
            command.add_argument('--phase', choices=['all', 'qualification', 'comparison'], default='all')
            command.add_argument('--max-runs', type=int)
    args = parser.parse_args()
    root = args.workspace.absolute()
    if args.command == 'prepare':
        result = prepare(root, args.cache)
    elif args.command == 'preflight':
        result = preflight(root)
    elif args.command == 'report':
        result = report(root)
    elif args.command == 'pause':
        read_plan(root)
        (root / 'PAUSE').touch()
        result = dict(status='pause_requested', behavior='current bounded run finishes')
    else:
        if args.command == 'resume':
            preflight(root)
            (root / 'PAUSE').unlink(missing_ok=True)
        result = run(root, phase=args.phase, max_runs=args.max_runs)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
