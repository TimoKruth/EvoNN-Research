"""Summarize a verified complete JEPA campaign without pooling candidate slots as seeds.

Run with the worktree Python: analyze.py WORKSPACE --output OUTPUT_STEM.
This derives descriptive tables only. The existing report reader verifies all
worker, model and teacher artifacts first; frozen training inputs are not changed.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from statistics import mean, median

from evonn_compare.jepa import read_manifest, report

CONTRASTS = (
    ('jepa', 'supervised_long'), ('jepa', 'supervised_short'), ('jepa', 'reconstruction'),
    ('jepa_transfer', 'distillation'), ('jepa_transfer', 'supervised_long'),
)


def summarize(workspace):
    workspace = Path(workspace).resolve()
    checked = report(workspace)
    manifest = read_manifest(workspace)
    if checked['status'] != 'complete':
        raise ValueError('Scientific summary requires every declared worker case to be complete')
    rows = checked['rows']
    expected = {c['id'] for c in manifest['cases']}
    if len(rows) != len(expected) or {r['id'] for r in rows} != expected:
        raise ValueError('Report matrix does not match its frozen manifest')
    index = {(r['system'], r['benchmark'], r['label_fraction'], r['seed'], r['candidate'], r['arm']): r
             for r in rows}
    if len(index) != len(rows):
        raise ValueError('Duplicate study cell')
    summaries = []
    for engine in manifest['spec']['systems']:
        for benchmark in manifest['spec']['benchmarks']:
            for fraction in manifest['spec']['label_fractions']:
                for treatment, control in CONTRASTS:
                    if treatment not in manifest['spec']['arms']:
                        continue
                    seed_rows, ratios, worker_ratios, forward_ratios = [], [], [], []
                    candidate_effects = defaultdict(list)
                    for seed in manifest['spec']['seeds']:
                        pairs = []
                        for slot in range(1 if engine == 'contenders' else manifest['spec']['candidates']):
                            treated = index[engine, benchmark, fraction, seed, slot, treatment]['result']
                            reference = index[engine, benchmark, fraction, seed, slot, control]['result']
                            if treated['data'] != reference['data']:
                                raise ValueError('Data mismatch in contrast')
                            tm, rm = treated['metrics'], reference['metrics']
                            if tm['metric'] != rm['metric'] or tm['direction'] != rm['direction']:
                                raise ValueError('Incompatible metrics')
                            sign = 1 if tm['direction'] == 'maximize' else -1
                            gain = sign*(tm['validation']-rm['validation'])
                            if engine == 'contenders' and (
                                    tm['validation'] != rm['validation'] or
                                    tm['missing_input_validation'] != rm['missing_input_validation']):
                                raise ValueError('Repeated contender controls are not identical')
                            candidate_effects[slot].append(gain)
                            pairs.append(dict(treatment=tm['validation'], control=rm['validation'], gain=gain,
                                              robustness_gain=sign*(tm['missing_input_validation']-
                                                                    rm['missing_input_validation'])))
                            ratios.append(treated['wall_seconds']/reference['wall_seconds'])
                            worker_ratios.append(index[engine, benchmark, fraction, seed, slot, treatment]['worker_seconds']/
                                                 index[engine, benchmark, fraction, seed, slot, control]['worker_seconds'])
                            if engine != 'contenders':
                                if (treated['genome'] != reference['genome'] or
                                        treated['initial_weights_sha256'] != reference['initial_weights_sha256']):
                                    raise ValueError('Architecture/initialization mismatch')
                                forward_ratios.append(treated['encoder_forward_examples']/reference['encoder_forward_examples'])
                        seed_rows.append(dict(seed=seed, **{k: mean(p[k] for p in pairs) for k in pairs[0]}))
                    summaries.append(dict(engine=engine, benchmark=benchmark, label_fraction=fraction,
                        treatment=treatment, control=control, metric=tm['metric'], per_seed=seed_rows,
                        mean_treatment=mean(r['treatment'] for r in seed_rows),
                        mean_control=mean(r['control'] for r in seed_rows),
                        mean_gain=mean(r['gain'] for r in seed_rows),
                        seed_gain_range=[min(r['gain'] for r in seed_rows), max(r['gain'] for r in seed_rows)],
                        positive_seeds=sum(r['gain'] > 1e-12 for r in seed_rows),
                        mean_robustness_gain=mean(r['robustness_gain'] for r in seed_rows),
                        positive_robustness_seeds=sum(r['robustness_gain'] > 1e-12 for r in seed_rows),
                        candidate_mean_gains={str(k): mean(v) for k, v in candidate_effects.items()},
                        median_training_time_ratio=median(ratios), median_worker_time_ratio=median(worker_ratios),
                        median_encoder_forward_ratio=median(forward_ratios) if forward_ratios else None))
    diagnostics = []
    for engine in manifest['spec']['systems']:
        if engine == 'contenders':
            continue
        for arm in manifest['spec']['arms']:
            group = [r['result'] for r in rows if r['system'] == engine and r['arm'] == arm]
            ratios = []
            for fitted in group:
                losses = [p['loss'] for p in fitted['curve'] if p['phase'] == 'finetune']
                window = max(1, len(losses)//4)
                ratios.append(mean(losses[-window:])/max(mean(losses[-2*window:-window]), 1e-12))
            diagnostics.append(dict(engine=engine, arm=arm, fits=len(group),
                final_rank_range=[min(r['metrics']['effective_rank'] for r in group),
                                  max(r['metrics']['effective_rank'] for r in group)],
                final_std_range=[min(r['metrics']['mean_feature_std'] for r in group),
                                 max(r['metrics']['mean_feature_std'] for r in group)],
                pretrain_rank_range=([min(r['pretrain_diagnostics']['effective_rank'] for r in group),
                                      max(r['pretrain_diagnostics']['effective_rank'] for r in group)]
                                     if group[0]['pretrain_diagnostics'] else None),
                pretrain_std_range=([min(r['pretrain_diagnostics']['mean_feature_std'] for r in group),
                                     max(r['pretrain_diagnostics']['mean_feature_std'] for r in group)]
                                    if group[0]['pretrain_diagnostics'] else None),
                median_last_to_previous_quarter_training_loss=median(ratios)))
    # The identical raw-feature pool must reproduce exactly across every arm.
    contenders = [s for s in summaries if s['engine'] == 'contenders']
    if any(abs(s['mean_gain']) > 1e-12 or abs(s['mean_robustness_gain']) > 1e-12 for s in contenders):
        raise ValueError('Repeated contender controls are not identical')
    neural = [r['result'] for r in rows if r['system'] != 'contenders']
    source_rows = [r for r in rows if 'teacher_embeddings_sha256' in r['result']]
    result = dict(version=1, manifest_sha256=manifest['manifest_sha256'],
        producer=manifest['producer'], spec=manifest['spec'],
        report_sha256=hashlib.sha256((workspace/'report.json').read_bytes()).hexdigest(),
        evidence='descriptive validation only; candidate slots averaged within seed; no significance claim',
        worker_cases=len(rows), neural_fits=len(neural),
        contender_fits=sum(r['result']['fits'] for r in rows if r['system'] == 'contenders'),
        neural_updates=sum(r['updates'] for r in neural),
        worker_seconds=sum(r['worker_seconds'] for r in rows),
        all_replays_passed=all(r['recompiled_replay_passed'] and r['replay_passed'] for r in neural),
        contender_controls_identical=True, summaries=summaries, diagnostics=diagnostics,
        teacher_prior=dict(accounting='reported_prior; source fits counted once in actual campaign totals',
                           source_cases=len(source_rows), updates=sum(r['result']['updates'] for r in source_rows),
                           training_seconds=sum(r['result']['wall_seconds'] for r in source_rows),
                           worker_seconds=sum(r['worker_seconds'] for r in source_rows),
                           export_seconds=sum(r['result']['teacher_export_seconds'] for r in source_rows)),
        case_receipts=[dict(id=r['id'], result_sha256=r['result_sha256'], status=r['status']) for r in rows])
    conditions = workspace/'run-conditions.json'
    if conditions.exists():
        result['run_conditions'] = json.loads(conditions.read_text())
        result['run_conditions_sha256'] = hashlib.sha256(conditions.read_bytes()).hexdigest()
    return result


def markdown(result):
    lines = ['# Repeated JEPA evaluation', '',
             f"Completed {result['worker_cases']} worker cases / {result['neural_fits']+result['contender_fits']} fits. "
             f"All {result['neural_fits']} neural replays passed. Observed worker time: {result['worker_seconds']/60:.1f} minutes.", '',
             result['evidence'] + '.', '',
             'Accuracy gains are percentage points; positive favors the treatment. Range is across seed-level '
             'effects after averaging fixed candidates within each seed. It is not a confidence interval. '
             'Timing ratios exclude prior teacher training and reflect uncontrolled host load.', '']
    for treatment, control in CONTRASTS:
        groups = [s for s in result['summaries'] if s['treatment'] == treatment and s['control'] == control
                  and s['engine'] != 'contenders']
        if not groups:
            continue
        lines += ['', f'## {treatment} versus {control}', '',
            '| Engine | Dataset | Labels | Control accuracy | Treatment accuracy | Gain (pp) | Seed range (pp) | Positive seeds | Occlusion gain (pp) | Training-time ratio |',
            '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
        for s in groups:
            if s['metric'] != 'accuracy':
                raise ValueError('This table formatter currently requires classification metrics')
            low, high = s['seed_gain_range']
            lines.append(f"| {s['engine']} | {s['benchmark']} | {100*s['label_fraction']:.0f}% | "
                         f"{100*s['mean_control']:.2f}% | {100*s['mean_treatment']:.2f}% | "
                         f"{100*s['mean_gain']:+.2f} | [{100*low:+.2f}, {100*high:+.2f}] | "
                         f"{s['positive_seeds']}/{len(s['per_seed'])} | {100*s['mean_robustness_gain']:+.2f} | "
                         f"{s['median_training_time_ratio']:.2f}× |")
    lines += ['', '## Contender reference pool', '',
              'Raw-feature pool outcomes are identical across all six arms; these are not compute-matched controls.', '',
              '| Dataset | Labels | Mean validation accuracy |', '|---|---:|---:|']
    for s in result['summaries']:
        if s['engine'] == 'contenders' and s['treatment'] == 'jepa' and s['control'] == 'supervised_long':
            lines.append(f"| {s['benchmark']} | {100*s['label_fraction']:.0f}% | {100*s['mean_control']:.2f}% |")
    lines += ['', '## Representation and learning-curve diagnostics', '',
              'Full-input training probes. Rank ranges are descriptive; nonzero variance does not prove useful semantics. '
              'Loss ratio compares mean training loss in the final quarter of fine-tuning to the preceding quarter; '
              'it does not establish convergence or validation improvement.', '',
              '| Engine | Arm | Final effective rank range | Final feature std range | Median late loss ratio |',
              '|---|---|---:|---:|---:|']
    for d in result['diagnostics']:
        lines.append(f"| {d['engine']} | {d['arm']} | {d['final_rank_range'][0]:.2f}–{d['final_rank_range'][1]:.2f} | "
                     f"{d['final_std_range'][0]:.3f}–{d['final_std_range'][1]:.3f} | "
                     f"{d['median_last_to_previous_quarter_training_loss']:.3f} |")
    lines += ['', 'The JSON companion retains per-seed effects, candidate effects, forward-work ratios, teacher prior '
              'cost, producer identity and every case receipt hash. These datasets, small fixed architectures and '
              'training schedules do not establish general JEPA performance or protected-test generalization.', '']
    prior = result['teacher_prior']
    lines += ['## Teacher prior and compute', '',
              f"The frozen teacher used {prior['source_cases']} source fits, {prior['updates']} optimizer updates "
              f"and {prior['worker_seconds']:.1f} observed worker seconds "
              f"({prior['training_seconds']:.1f} training seconds; {prior['export_seconds']:.1f} export seconds). "
              'These source fits are counted once in campaign totals and must be included when assessing '
              'a transfer deployment without an existing teacher. The transfer timing ratios above exclude them.', '',
              'EMA-JEPA uses three encoder forwards per pretraining update and also backpropagates through '
              'both online views. When phase lengths are equal, it processes twice as many encoder forward '
              'examples overall as supervised-long and reconstruction. '
              'Equal optimizer updates therefore do not make this a compute-matched comparison.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.workspace)
    args.output.with_suffix('.json').write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False)+'\n')
    args.output.with_suffix('.md').write_text(markdown(result))
    print(f"Verified {result['worker_cases']} worker cases; wrote {args.output}.json and .md")


if __name__ == '__main__':
    main()
