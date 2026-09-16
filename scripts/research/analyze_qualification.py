"""Read-only descriptive analysis of receipt-bound qualification exports.

No training, replay, policy nomination or statistical promotion is performed.
Usage: .venv/bin/python scripts/research/analyze_qualification.py BASE OUTPUT
"""
import collections
import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

SYSTEMS = ['prism', 'topograph', 'stratograph', 'primordia', 'contenders']
CORE = ['banknote_classification', 'digits_image', 'diabetes_regression', 'shakespeare_byte_lm']
BREADTH = ['shakespeare_context64_lm', 'aesop_context64_lm', 'shakespeare_byte_lm', 'delayed_copy_lm']


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mean(values):
    return statistics.mean(values)


def analyze(base):
    matrix = read(base/'qualification-matrix.json')
    required = {row['id']+'-'+system: (row, system) for row in matrix for system in row['systems']}
    rows, runs, baselines, sources = [], [], [], []
    dataset_groups = collections.defaultdict(set)
    actual = set()
    for path in sorted((base/'receipts').glob('*.json')):
        if not (path.stem in required):
            raise ValueError(f'Unexpected slot: {path}')
        if not (path.stem not in actual):
            raise ValueError('qualification integrity check failed')
        actual.add(path.stem)
        expected, system = required[path.stem]
        receipt = read(path)
        if not ((receipt['system'], receipt['seed'], receipt['budget'], receipt['stage']) == (system, expected['seed'], expected['regime']['proposal_limit'], expected['stage'])):
            raise ValueError('qualification integrity check failed')
        export = Path(receipt['export'])
        if set(receipt['documents']) != {'manifest.json', 'summary.json', 'results.json'}:
            raise ValueError('Incomplete completion document hashes')
        for name, digest in receipt['documents'].items():
            if not (sha(export / name) == digest):
                raise ValueError(f'Changed receipt-bound document: {export / name}')
        manifest, summary, results = [read(export/name) for name in ['manifest.json', 'summary.json', 'results.json']]
        if not (manifest['status'] == 'completed'):
            raise ValueError('qualification integrity check failed')
        if not (manifest['accounting'] == receipt['accounting'] == summary['accounting']):
            raise ValueError('qualification integrity check failed')
        if not (manifest['seed'] == receipt['seed'] and manifest['system'] == system):
            raise ValueError('qualification integrity check failed')
        if not (manifest['pack_id'] == expected['pack']):
            raise ValueError('qualification integrity check failed')
        artifacts = {r['path']:r['sha256'] for r in manifest['artifacts']}
        artifacts[manifest['config_snapshot']['path']] = manifest['config_snapshot']['sha256']
        consumed = {}
        def artifact(name):
            if not (name in artifacts):
                raise ValueError('qualification integrity check failed')
            if not (sha(export / name) == artifacts[name]):
                raise ValueError(f'Changed analysis input: {export / name}')
            consumed[name] = artifacts[name]
            return read(export/name)
        attempts = artifact('attempts.json')['attempts']
        artifact(manifest['config_snapshot']['path'])
        provenance = artifact('dataset_provenance.json')
        for data in provenance:
            identity = tuple(data[k] for k in ['definition_sha256', 'raw_sha256', 'split_sha256', 'seed'])
            dataset_groups[(receipt['stage'], receipt['budget'], receipt['seed'], data['benchmark_id'])].add(identity)
        if not (len(attempts) == receipt['budget'] == receipt['accounting']['evaluation_count']):
            raise ValueError('qualification integrity check failed')
        if not (all((a['status'] == 'ok' and a['charged'] == 1 for a in attempts))):
            raise ValueError('qualification integrity check failed')
        if not (receipt['accounting']['failed_evaluations'] == receipt['accounting']['invalid_evaluations'] == 0):
            raise ValueError('qualification integrity check failed')
        if not (len(results['records']) == len(attempts)):
            raise ValueError('qualification integrity check failed')
        replay = receipt.get('replay')
        if system != 'contenders':
            if not (replay['status'] == 'passed' and len(replay['checks']) == 4):
                raise ValueError('qualification integrity check failed')
        training = sum(a['train_seconds'] for a in attempts)
        if not (math.isfinite(training) and training > 0):
            raise ValueError('qualification integrity check failed')
        metadata = {k:receipt[k] for k in ['stage','system','budget','seed']}
        cost = dict(**metadata, run_id=manifest['run_id'], training_seconds=training,
                    recorded_elapsed_seconds=manifest['timing']['elapsed_seconds'],
                    serialized_winner_bytes=0, replay_checks=len(replay['checks']) if replay else 0,
                    fit_count=len(attempts), git_commit=manifest['git_commit'],
                    config_sha256=manifest['config_snapshot']['sha256'])
        if not (len(summary['best_per_benchmark']) == 4):
            raise ValueError('qualification integrity check failed')
        for best in summary['best_per_benchmark']:
            benchmark = best['benchmark_id']
            records = [r for r in results['records'] if r['benchmark_id'] == benchmark and r['status'] == 'ok']
            winner = next(r for r in records if r['outcome_id'] == best['outcome_id'])
            choose = max if best['direction'] == 'max' else min
            if not (winner['metric']['value'] == best['value'] == choose((r['metric']['value'] for r in records))):
                raise ValueError('qualification integrity check failed')
            if replay:
                check = next(c for c in replay['checks'] if c['benchmark'] == benchmark)
                if not (check['exported'] == best['value']):
                    raise ValueError('qualification integrity check failed')
                if not (math.isclose(check['observed'], best['value'], rel_tol=1e-06, abs_tol=1e-08)):
                    raise ValueError('qualification integrity check failed')
            task_attempts = [a for a in attempts if a['benchmark_id'] == benchmark]
            rows.append(dict(**metadata, benchmark=benchmark, metric=best['metric_name'],
                             direction=best['direction'], score=best['value'], outcome_id=best['outcome_id'],
                             winner_model_bytes=winner['model_bytes']['value'],
                             winner_parameter_count=winner['parameter_count']['value'],
                             task_training_seconds=sum(a['train_seconds'] for a in task_attempts),
                             task_fits=len(task_attempts)))
            cost['serialized_winner_bytes'] += winner['model_bytes']['value'] or 0
            if system == 'contenders':
                for family in sorted({a['family'] for a in task_attempts}):
                    family_attempts = [a for a in task_attempts if a['family'] == family]
                    baselines.append(dict(**metadata, benchmark=benchmark, family=family,
                                          score=choose(a['score'] for a in family_attempts),
                                          fits=len(family_attempts),
                                          training_seconds=sum(a['train_seconds'] for a in family_attempts)))
        if system == 'topograph':
            profile = artifact('engine_telemetry.json').get('runtime_profile', {})
            cost['checkpoint_publication_seconds'] = sum(t['checkpoint_seconds'] for t in profile.get('checkpoint_publications', []))
            cost['missing_checkpoint_timings'] = profile.get('missing_checkpoint_timings')
        runs.append(cost)
        sources.append(dict(receipt=str(path), receipt_sha256=sha(path), export=str(export),
                            documents=receipt['documents'], analyzed_artifacts=consumed))
    if not (all((len(identities) == 1 for identities in dataset_groups.values()))):
        raise ValueError('Dataset mismatch within paired case')
    groups = collections.defaultdict(list)
    for row in rows:
        groups[(row['stage'],row['budget'],row['system'],row['benchmark'])].append(row)
    means = [dict(stage=key[0],budget=key[1],system=key[2],benchmark=key[3],
                  seeds=sorted(v['seed'] for v in values), n=len(values),
                  mean=mean(v['score'] for v in values), minimum=min(v['score'] for v in values),
                  maximum=max(v['score'] for v in values),
                  winner_bytes_mean=mean(v['winner_model_bytes'] for v in values))
             for key, values in sorted(groups.items())]
    scaling = []
    for system in SYSTEMS:
        for benchmark in CORE:
            low = {r['seed']:r for r in rows if r['stage']=='Q-core' and r['system']==system and r['benchmark']==benchmark and r['budget']==128}
            high = {r['seed']:r for r in rows if r['stage']=='Q-core' and r['system']==system and r['benchmark']==benchmark and r['budget']==256}
            if not (set(low) == set(high) == {1001, 1002}):
                raise ValueError('qualification integrity check failed')
            a, z = mean(r['score'] for r in low.values()), mean(r['score'] for r in high.values())
            scaling.append(dict(system=system,benchmark=benchmark,mean128=a,mean256=z,
                                relative_reduction_percent=100*(a-z)/a if low[1001]['direction']=='min' else None,
                                accuracy_gain_percentage_points=100*(z-a) if low[1001]['direction']=='max' else None,
                                pairs=[dict(seed=s,score128=low[s]['score'],score256=high[s]['score']) for s in sorted(low)]))
    cost_groups = collections.defaultdict(list)
    for r in runs: cost_groups[(r['stage'],r['budget'],r['system'])].append(r)
    costs = [dict(stage=k[0],budget=k[1],system=k[2],training_seconds_mean=mean(r['training_seconds'] for r in v),
                  n=len(v), seeds=sorted(r['seed'] for r in v)) for k,v in sorted(cost_groups.items())]
    missing_slots = sorted(set(required) - actual)
    declared_deferred = read(base/'deferred-slots.json')['slots']
    if set(missing_slots) != set(declared_deferred):
        raise ValueError('Missing receipts differ from declared deferred slots')
    return dict(generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),base=str(base),
                classification='descriptive qualification analysis; incomplete comparison; no promotion',
                required_runs=len(required),completed_runs=len(runs),missing_slots=missing_slots,
                deferred_slots=declared_deferred,
                successful_fits=sum(r['fit_count'] for r in runs),
                native_replay_checks=sum(r['replay_checks'] for r in runs),
                dataset_parity_groups_checked=len(dataset_groups),
                validation='Receipt hashes, consumed artifact hashes, winner/record consistency, charged-fit accounting, recorded replay agreement, and within-case dataset identity checked; no new fitting or replay',
                rows=rows,means=means,budget_scaling=scaling,runs=runs,costs=costs,baseline_families=baselines,sources=sources)


def render(data):
    lines=['# Qualification results — 16 September 2026','',
           '**Descriptive evidence only.** 28/30 runs complete; two Primordia breadth slots remain blocked. This is two seeds per regime, not the planned mechanism or confirmation study. No engine promotion or later-stage acceptance follows.','',
           f"Inputs checked: {data['successful_fits']:,} successful charged fits, {data['native_replay_checks']} recorded native winner replay checks, and {data['dataset_parity_groups_checked']} within-case dataset groups. All consumed document/artifact hashes matched. This analysis does not rerun training or independently replay models.",'',
           'Core coverage is complete: five systems × two budgets × two seeds = 20 runs. Breadth coverage is 8/10. Budgets count fits across the four tasks, not per task. Means below are arithmetic means of each seed’s validation-selected winner; they are not held-out test scores.','']
    index={(x['stage'],x['budget'],x['system'],x['benchmark']):x for x in data['means']}
    for budget in [128,256]:
        lines += [f'## Core at {budget} fits','', '| System | Banknote accuracy ↑ | Digits accuracy ↑ | Diabetes MSE ↓ | Shakespeare perplexity ↓ |','| --- | ---: | ---: | ---: | ---: |']
        for system in SYSTEMS:
            vals=[index[('Q-core',budget,system,b)]['mean'] for b in CORE]
            lines.append(f'| {system.title()} | {vals[0]*100:.2f}% | {vals[1]*100:.2f}% | {vals[2]:.1f} | {vals[3]:.3f} |')
        lines += ['']
    lines += ['## Breadth at 64 fits','', 'All entries are perplexity (lower is better). Shakespeare byte is a bridge task; delayed copy is a separate synthetic diagnostic. Do not average them together to claim language superiority.','',
              '| System | Shakespeare context 64 | Aesop context 64 | Original Shakespeare | Delayed copy |','| --- | ---: | ---: | ---: | ---: |']
    for system in SYSTEMS:
        vals=[index[('Q-breadth',64,system,b)] if ('Q-breadth',64,system,b) in index else None for b in BREADTH]
        lines.append('| '+system.title()+' | '+' | '.join(f"{v['mean']:.4f}" if v else 'Blocked' for v in vals)+' |')
    lines += ['', '## Paired budget scaling: 128 → 256','',
              'Percent reductions are ratios of the two-seed means, not means of seed-level percentages. Raw pairs are retained in analysis.json. Banknote stays at 100% for every system/seed/budget.','',
              '| System | Digits gain (percentage points) | MSE reduction | Perplexity reduction | Recorded training-time multiplier |','| --- | ---: | ---: | ---: | ---: |']
    costs={(r['stage'],r['budget'],r['system']):r['training_seconds_mean'] for r in data['costs']}
    for system in SYSTEMS:
        d={v['benchmark']:v for v in data['budget_scaling'] if v['system']==system}
        ratio=costs[('Q-core',256,system)]/costs[('Q-core',128,system)]
        lines.append(f"| {system.title()} | {d['digits_image']['accuracy_gain_percentage_points']:.3f} | {d['diabetes_regression']['relative_reduction_percent']:.2f}% | {d['shakespeare_byte_lm']['relative_reduction_percent']:.2f}% | {ratio:.2f}× |")
    lines += ['', '## Recorded training costs','',
              'Sum of per-attempt train_seconds across all four tasks, averaged over the two seeds. These are backend-specific recorded timers, not matched FLOPs or an audited common-compute budget. They exclude much orchestration/checkpoint work. Export elapsed time spans scheduler gaps/manual pauses and is unsuitable for throughput ranking.','',
              '| System | Core 128 (s) | Core 256 (s) | Breadth 64 (s) |','| --- | ---: | ---: | ---: |']
    for system in SYSTEMS:
        vals=[costs[(stage,budget,system)] if (stage,budget,system) in costs else None for stage,budget in [('Q-core',128),('Q-core',256),('Q-breadth',64)]]
        lines.append('| '+system.title()+' | '+' | '.join(f'{v:.1f}' if v is not None else 'Blocked' for v in vals)+' |')
    lines += ['', '## Named language baselines','',
              'These panels separate the best frozen contender pool from named baselines. Successfully executing a baseline does not establish adequate tuning or matching training effort.','',
              '| Stage / budget | Task | Family | Mean best validation perplexity |','| --- | --- | --- | ---: |']
    bg=collections.defaultdict(list)
    for x in data['baseline_families']:
        if x['benchmark'].endswith('_lm'): bg[(x['stage'],x['budget'],x['benchmark'],x['family'])].append(x['score'])
    for (stage,budget,bench,family),vals in sorted(bg.items()):lines.append(f'| {stage} / {budget} | {bench} | {family} | {mean(vals):.4f} |')
    lines += ['', '## Raw paired winners','', '| Stage | Budget | Seed | System | Task | Score | Winner bytes |','| --- | ---: | ---: | --- | --- | ---: | ---: |']
    for r in sorted(data['rows'],key=lambda r:(r['stage'],r['budget'],r['seed'],r['system'],r['benchmark'])):
        lines.append(f"| {r['stage']} | {r['budget']} | {r['seed']} | {r['system']} | {r['benchmark']} | {r['score']:.8g} | {r['winner_model_bytes']} |")
    lines += ['', '## Scope and integrity limits','',
              '- Primordia seed 1003 failed during Aesop preparation before fits; seed 1004 was explicitly deferred for the same unsupported loader. Missing evidence is not a poor performance score.',
              '- Two seeds give a pilot estimate only. Budgets and benchmarks are not extra independent seed replicates. No significance tests or confidence intervals are used for promotion.',
              '- Validation-selected winners may overstate generalization. Protected text test data was not evaluated; delayed copy has no protected test split in this protocol.',
              '- No policy treatments or mechanism ablations were run. The data cannot establish which component caused a gain.',
              '- Seeds differ from the previous 64-run refresh, and Topograph’s producer includes the FP16 repair. Historical score differences are not paired version effects.',
              '- Chunking, recovery, scheduler versions and manual pauses affect wall time. Profiling equivalence and disjoint timing reconciliation remain unaccepted.',
              '- The report retains all five systems and the two missing slots. It does not mark qualification complete or authorize stages A/B/C/D.','']
    return '\n'.join(lines)


if __name__ == '__main__':
    base,output=map(Path,sys.argv[1:3])
    data=analyze(base.resolve())
    if not (data['completed_runs'] == 28 and data['required_runs'] == 30):
        raise ValueError('qualification integrity check failed')
    if not (data['successful_fits'] == 4352 and data['native_replay_checks'] == 88):
        raise ValueError('qualification integrity check failed')
    output.mkdir(parents=True,exist_ok=False)
    (output/'analysis.json').write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    (output/'report.md').write_text(render(data))
    print(json.dumps({k:data[k] for k in ['completed_runs','required_runs','successful_fits','native_replay_checks','dataset_parity_groups_checked','missing_slots']},indent=2))
