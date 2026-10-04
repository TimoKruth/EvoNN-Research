"""Summarize the frozen completed study; no fitting or new statistical tests."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).resolve().parent / 'evidence.json'
SOURCE_SHA256 = 'fd4d7e7cd0e1c76a41944bd9dfa90d96048f037c4ee3b5e70f5098c1aff6109b'


def summarize(source=SOURCE):
    payload = source.read_bytes()
    if hashlib.sha256(payload).hexdigest() != SOURCE_SHA256:
        raise ValueError('completed study report differs from the reviewed evidence')
    report = json.loads(payload)
    assert report['status'] == 'complete' and report['comparison_complete'] == 416
    assert report['qualification_complete'] == 26 and report['missing'] == []
    inference, rows = report['inference'], report['rows']
    assert inference['family_size'] == len(inference['contrasts']) == 468
    arms = sorted({r['arm'] for r in rows})
    packs = ['tier_b_core_v2', 'language_breadth_v1']
    keys = [(r['arm'], r['pack'], r['seed']) for r in rows]
    assert len(arms) == 13 and len(keys) == len(set(keys)) == 416
    assert set(keys) == {(a, p, s) for a in arms for p in packs for s in range(23101, 23117)}
    comparisons = []
    for c in inference['contrasts']:
        assert c['n'] == 16
        if c['before'] != 'control' or c['after'] != 'full_steady':
            continue
        values = {}
        for arm in ['control', 'full_steady']:
            values[arm] = mean(r['scores'][c['benchmark']] for r in rows if r['arm'] == arm and r['pack'] == c['pack'])
        comparisons.append({**c, 'raw_means': values})
    assert len(comparisons) == 6
    return dict(source=str(source.relative_to(ROOT)), source_sha256=hashlib.sha256(payload).hexdigest(),
                comparison_complete=416, qualification_complete=26,
                interpretation=report['interpretation'], family_size=468,
                decisions=dict(Counter(c['decision'] for c in inference['contrasts'])),
                standard_vs_control=comparisons,
                total_measured_train_seconds={a: sum(r['train_seconds'] for r in rows if r['arm'] == a) for a in arms})


def main():
    result = summarize()
    folder = Path(__file__).parent
    (folder / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    lines = ['# Primordia completed-study findings — October 4, 2026', '',
             'All 416 comparisons and 26 qualifications completed, covering 13 presets, 16 paired seeds and two packs. '
             'This is within-Primordia validation evidence; it neither ranks other engines nor measures protected-test generalization.', '',
             '## Tested standard: full_steady', '',
             '`standard` is an exact policy alias for the tested `full_steady` configuration: expressive_v3 representations, '
             'steady_v3 training, progress_v3 proposals and enabled inheritance. It is a practical default choice, not an overall '
             'winner declared by the protocol. It preserves the combination that performed well across image and language tasks.', '',
             '| Endpoint | Control mean | Standard mean | Paired improvement | Simultaneous 95% interval | Decision |',
             '|---|---:|---:|---:|---:|---|']
    for c in result['standard_vs_control']:
        means = c['raw_means']
        lo, hi = c['simultaneous_ci95']
        if c['effect_scale'] == 'accuracy_difference':
            raw = [f'{100 * means[a]:.2f}%' for a in ['control', 'full_steady']]
            effect, interval = f"{100*c['mean_effect']:+.2f} pp", f'[{100*lo:+.2f}, {100*hi:+.2f}] pp'
        else:
            raw = [f'{means[a]:.4f}' for a in ['control', 'full_steady']]
            effect = f"{100 * (1-math.exp(-c['mean_effect'])):.2f}% reduction"
            interval = f'[{100*(1-math.exp(-lo)):.2f}, {100*(1-math.exp(-hi)):.2f}]%'
        lines.append(f"| {c['benchmark']} | {raw[0]} | {raw[1]} | {effect} | {interval} | {c['decision']} |")
    ratio = result['total_measured_train_seconds']['full_steady'] / result['total_measured_train_seconds']['control']
    lines += ['', 'Banknote accuracy was 100% for every arm and is outside the six-endpoint inferential family.', '',
              'The intervals are the frozen approximate simultaneous bootstrap intervals across 468 contrasts; decisions also '
              'require Holm-adjusted exact sign-flip p ≤ 0.05 and the predeclared materiality threshold. '
              'Loss reductions transform the paired mean log ratio, so they differ from ratios of arithmetic means. '
              'The regression contrast has Holm p ≈ 0.033 but fails the materiality/interval gate and remains inconclusive.', '',
              f'Standard recorded {ratio:.2f}× the control\'s total training seconds across the 32 runs. This is descriptive: '
              'the continuation mixes producer revisions and timeout caps, and concurrent host use affects timing. '
              'It establishes no equal-wall-time efficiency claim.', '',
              '## Implemented choices', '',
              '- Bare fresh CLI runs use standard. Explicit configs, low-level APIs, campaign controls and historical resumes retain their prior semantics.',
              '- All 13 historical presets remain selectable. The original experiment roster and artifacts are unchanged.',
              '- Experimental `portfolio` and `portfolio_stable` repeatedly introduce convolution, attention and multiscale language founders, '
              'and pooled/flat spatial image founders. Family allocation depends only on task/modality, not benchmark ID or observed winners.',
              '- Portfolio tabular proposals retain v2 representations. Each portfolio keeps its named optimizer/search settings; '
              'this is not a claim that all tabular behavior matches control.',
              '- Exploration counters survive checkpoints; exports verify family accounting and recurring fresh-family allocation against the ledger.', '',
              'Attention solved delayed copy but its natural-language improvements were inconclusive; convolution/multiscale improved '
              'natural language but did not solve delayed copy. The portfolio keeps both opportunities. It is a new hypothesis, '
              'not a measured improvement. Full versus steady/cold comparisons do not justify declaring a universal winner or disabling inheritance.', '',
              '## Next comparison', '',
              'Compare control, standard, portfolio and portfolio_stable on fresh paired seeds. Each new declared case must run '
              'Prism, Topograph, Stratograph, Primordia and Contenders. Existing study seeds are development evidence and must not '
              'serve as fresh confirmation. Include quality, failures, actual optimizer updates and measured training time. '
              'No new study was launched by this implementation.', '',
              '## Reproduction', '',
              'Run `.venv/bin/python reports/primordia-confidence-20261004/analyze.py` to regenerate this summary from the frozen report.', '',
              f"Source: `{result['source']}`", '', f"SHA-256: `{result['source_sha256']}`", '']
    (folder / 'README.md').write_text('\n'.join(lines))
    print(folder)


if __name__ == '__main__':
    main()
