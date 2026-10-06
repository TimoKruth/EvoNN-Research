"""Read the completed amended analysis; write a compact, source-bound summary.

Usage: .venv/bin/python reports/prism-confidence-20260921/summarize_results.py
No fitting or recomputation/change of the frozen statistical tests.
"""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / '.artifacts/prism-confidence-size-resume-20260923/study/analysis-0d2d6c47bc214729990ac0b56d50e5f9.json'
ARMS = ('legacy', 'archive', 'training', 'broad', 'open', 'search_v2', 'representation_v2',
        'regularized_v2', 'averaged_v2', 'calibrated_v2', 'frontier_v2')
TASKS = {'core128': ('banknote_classification', 'diabetes_regression', 'digits_image', 'shakespeare_byte_lm'),
         'core256': ('banknote_classification', 'diabetes_regression', 'digits_image', 'shakespeare_byte_lm'),
         'breadth128': ('aesop_context64_lm', 'delayed_copy_lm', 'shakespeare_byte_lm', 'shakespeare_context64_lm')}


def summarize(source=SOURCE):
    payload = source.read_bytes()
    data = json.loads(payload)
    if data['status'] != 'complete' or data['missing'] or data['completed'] != 1012:
        raise ValueError('completed fixed matrix required')
    expected = {(p, a, seed, task) for p, tasks in TASKS.items() for a in ARMS
                for seed in range(21601, 21631) for task in tasks}
    rows = data['rows']
    actual = [(r['panel'], r['arm'], r['seed'], r['benchmark']) for r in rows]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError('unexpected or incomplete per-task matrix')
    groups = defaultdict(list)
    for row in rows:
        groups[row['panel'], row['arm'], row['benchmark']].append(row)
    descriptions = []
    for (panel, arm, task), values in sorted(groups.items()):
        descriptions.append(dict(panel=panel, arm=arm, benchmark=task, n=len(values),
            direction=values[0]['direction'], metric_mean=mean(r['value'] for r in values),
            metric_median=median(r['value'] for r in values),
            winner_fit_seconds_mean=mean(r['training_seconds'] for r in values),
            winner_parameter_count_median=median(r['parameter_count'] for r in values)))
    stats = data['statistics']
    return dict(source=str(source.relative_to(ROOT)), source_sha256=hashlib.sha256(payload).hexdigest(),
        status=data['status'], completed=data['completed'], interpretation=data['interpretation'],
        inference={k: v for k, v in stats.items() if k != 'contrasts'},
        contrasts=[{k: v for k, v in c.items() if k != 'paired_effects'} for c in stats['contrasts']],
        per_task_descriptive=descriptions,
        cost_note='Winner-fit seconds describe only selected fits, not total search cost or equal-compute efficiency.',
        retained_continuation_cost=[{k: r[k] for k in ('charged_attempts', 'invalid_proposals', 'measured_train_seconds') if k in r}
                                    for r in data['retained_failure_cost']])


if __name__ == '__main__':
    target = Path(__file__).with_name('results-summary.json')
    target.write_text(json.dumps(summarize(), indent=2, sort_keys=True) + '\n')
    print(target)
