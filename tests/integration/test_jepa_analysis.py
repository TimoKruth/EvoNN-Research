"""Verify the study summary's units, seed grouping and control validation."""
import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def analyzer():
    path = Path(__file__).resolve().parents[2]/'research/jepa/analyze.py'
    spec = importlib.util.spec_from_file_location('jepa_analysis', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_report():
    from evonn_shared.jepa_experiment import SYSTEMS, ARMS, TRANSFER_ARMS
    specification = dict(systems=SYSTEMS, benchmarks=['digits'], label_fractions=[0.1],
                         seeds=[1, 2, 3], candidates=2, arms=ARMS+TRANSFER_ARMS)
    rows = []
    for engine in SYSTEMS:
        for seed in specification['seeds']:
            for candidate in range(1 if engine == 'contenders' else 2):
                for arm in specification['arms']:
                    gain = 0.01*seed + 0.02*candidate if arm == 'jepa' and engine != 'contenders' else 0
                    result = dict(data={'seed': seed}, genome={'slot': candidate}, initial_weights_sha256=str(candidate),
                        metrics=dict(metric='accuracy', direction='maximize', validation=0.5+gain,
                                     missing_input_validation=0.4+gain/2, effective_rank=4, mean_feature_std=1),
                        wall_seconds=4 if arm == 'jepa' else 2, encoder_forward_examples=128 if arm == 'jepa' else 64,
                        curve=[dict(phase='finetune', loss=v) for v in (4, 3, 2, 1)],
                        pretrain_diagnostics={'effective_rank': 3, 'mean_feature_std': 0.8},
                        updates=8, recompiled_replay_passed=True, replay_passed=True, fits=2)
                    rows.append(dict(id=str(len(rows)), result_sha256='test', status='ok', system=engine,
                                     benchmark='digits', seed=seed, candidate=candidate, label_fraction=0.1,
                                     arm=arm, worker_seconds=6, result=result))
    manifest = dict(spec=specification, manifest_sha256='test', producer={}, cases=[{'id': r['id']} for r in rows])
    return manifest, dict(status='complete', rows=rows)


def test_seed_range_and_percentage_point_rendering(tmp_path, monkeypatch, analyzer):
    manifest, report = fixture_report()
    (tmp_path/'report.json').write_text('{}')
    monkeypatch.setattr(analyzer, 'read_manifest', lambda _: manifest)
    monkeypatch.setattr(analyzer, 'report', lambda _: report)
    summary = analyzer.summarize(tmp_path)
    row = next(r for r in summary['summaries'] if r['engine']=='prism' and
               r['treatment']=='jepa' and r['control']=='supervised_long')
    assert row['mean_gain'] == pytest.approx(0.03)
    assert row['seed_gain_range'] == pytest.approx([0.02, 0.04])
    assert len(row['per_seed']) == 3
    assert row['positive_seeds'] == 3
    assert row['mean_robustness_gain'] == pytest.approx(0.015)
    assert row['median_training_time_ratio'] == 2
    assert row['median_encoder_forward_ratio'] == 2
    assert summary['neural_fits'] == 144
    assert summary['contender_fits'] == 36
    assert '| +3.00 | [+2.00, +4.00] | 3/3 | +1.50 | 2.00× |' in analyzer.markdown(summary)


def test_incomplete_evidence_cannot_be_summarized(tmp_path, monkeypatch, analyzer):
    manifest, report = fixture_report()
    report['status'] = 'incomplete'
    monkeypatch.setattr(analyzer, 'read_manifest', lambda _: manifest)
    monkeypatch.setattr(analyzer, 'report', lambda _: report)
    with pytest.raises(ValueError, match='every declared'):
        analyzer.summarize(tmp_path)


def test_control_mismatch_is_not_averaged_away(tmp_path, monkeypatch, analyzer):
    manifest, report = fixture_report()
    rows = [r for r in report['rows'] if r['system']=='contenders' and r['arm']=='jepa']
    rows[0]['result']['metrics']['validation'] += 0.1
    rows[1]['result']['metrics']['validation'] -= 0.1
    monkeypatch.setattr(analyzer, 'read_manifest', lambda _: manifest)
    monkeypatch.setattr(analyzer, 'report', lambda _: report)
    with pytest.raises(ValueError, match='contender controls'):
        analyzer.summarize(tmp_path)
