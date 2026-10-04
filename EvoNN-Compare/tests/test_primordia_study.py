"""Scope exception, frozen preparation, paired inference and launch gates."""
from copy import deepcopy
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from evonn_compare import campaign as c, primordia_study as s
from evonn_shared.primordia_policy import PrimordiaResearchPolicy


def test_single_engine_exception_is_explicit_and_narrow():
    with pytest.raises(ValueError, match='every engine'):
        c.CampaignSpec(systems=['primordia'], primordia_research=PrimordiaResearchPolicy())
    for change in (dict(systems=['prism']), dict(primordia_research=None), dict(enhanced=True),
                   dict(topograph_variant='legacy'), dict(systems=list(c.SYSTEMS))):
        with pytest.raises(ValueError, match='variant scope'):
            c.CampaignSpec.model_validate({**s.specification('full', s.PACKS[0]).model_dump(), **change})
    assert s.specification('full', s.PACKS[0]).systems == ['primordia']


def test_matrix_schedule_budgets_and_frozen_family():
    rows = s.matrix()
    assert len(rows) == 52
    for phase, count, budget in [('qualification', 26, 64), ('comparison', 416, 256)]:
        selected = [row for row in rows if row['phase'] == phase]
        planned = {(r['arm'], r['pack'], seed) for r in selected for seed in r['spec']['seeds']}
        scheduled = [(r['arm'], r['pack'], r['seed']) for r in s.schedule(phase)]
        assert len(scheduled) == len(set(scheduled)) == count and set(scheduled) == planned
        assert all(r['spec']['budgets'] == [budget] and r['spec']['systems'] == ['primordia'] for r in selected)
    assert len(s.ARMS) * (len(s.ARMS) - 1) // 2 * len(s.ENDPOINTS) == 468
    assert not set(s.SEEDS) & {s.QUALIFICATION_SEED}
    assert 2 / 2**len(s.SEEDS) < .05 / 468


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    root = tmp_path / 'study'
    pinned = dict(commit='a' * 40)
    monkeypatch.setattr(c, 'identity', lambda: pinned)
    monkeypatch.setattr(s, 'seed_audit', lambda: {'requested': s.SEEDS})
    calls = []
    rows = s.matrix()
    monkeypatch.setattr(s, 'matrix', lambda: deepcopy(rows))
    # Matrix validation is covered above; avoid repeating expensive catalog validation
    # hundreds of times in protocol publication/tamper unit tests.
    monkeypatch.setattr(c, 'CampaignSpec', SimpleNamespace(model_validate=lambda payload: SimpleNamespace(**payload)))
    def process(command, timeout, log):
        assert command[1:4] == ['-m', 'evonn_compare.campaign_worker', 'prepare']
        name, seed, cache, output = command[4:]
        Path(output).write_text(json.dumps(dict(benchmark_id=name, seed=int(seed), cache_directory=cache)))
        calls.append(command)
    monkeypatch.setattr(c, '_bounded_process', process)
    monkeypatch.setattr(c, 'preflight', lambda directory: dict(manifest_sha256=c.read_manifest(directory)['sha256']))
    result = s.prepare(root, tmp_path / 'cache')
    assert result['training_started'] is False
    assert result['comparison_runs'] == 416 and result['fit_attempts'] == 108160
    assert len(calls) == 7 * 17  # Shared Shakespeare bridge split prepared only once.
    return root


def test_preparation_freezes_specs_and_dataset_manifest_hashes(prepared):
    plan = s.read_plan(prepared)
    assert len(plan['campaign_sha256']) == 52
    row = plan['matrix'][0]
    path = prepared / row['campaign'] / 'campaign.json'
    manifest = json.loads(path.read_text())
    manifest['cache'] = '/another-cache'
    manifest['sha256'] = c.sha({k: v for k, v in manifest.items() if k != 'sha256'})
    path.write_bytes(c.encoded(manifest))
    with pytest.raises(ValueError, match='campaign differs'):
        s.read_plan(prepared)


def test_protocol_edit_is_rejected_even_if_checksum_is_recomputed(prepared):
    path = prepared / 'study.json'
    plan = json.loads(path.read_text())
    plan['policy']['runs'] = 1
    plan['sha256'] = c.sha({k: v for k, v in plan.items() if k != 'sha256'})
    path.write_bytes(c.encoded(plan))
    with pytest.raises(ValueError, match='protocol'):
        s.read_plan(prepared)


def test_incomplete_qualification_blocks_comparison_without_dispatch(tmp_path, monkeypatch):
    monkeypatch.setattr(s, 'preflight', lambda root: {})
    monkeypatch.setattr(s, 'collect', lambda root, phase: ([], [{'reason': 'missing'}]))
    monkeypatch.setattr(c, 'run_campaign', lambda *a, **kw: pytest.fail('must not dispatch'))
    with pytest.raises(ValueError, match='26 qualification'):
        s.run(tmp_path, phase='comparison')


def test_controller_run_limit_and_failed_fit_stop(tmp_path, monkeypatch):
    monkeypatch.setattr(s, 'preflight', lambda root: {})
    items = s.schedule('qualification')[:2]
    monkeypatch.setattr(s, 'schedule', lambda phase: items)
    monkeypatch.setattr(c, 'read_manifest', lambda root: {})
    launched, replayed = [], []
    def adopted(root, manifest, case, system):
        return ((root / 'run', {'run_id': 'probe'}) if root in launched else (None, None))
    monkeypatch.setattr(c, 'adopted', adopted)
    def dispatch(root, **kwargs):
        assert kwargs['max_runs'] == 1
        launched.append(root)
        return dict(new_runs=1)
    monkeypatch.setattr(c, 'run_campaign', dispatch)
    monkeypatch.setattr(s, 'read_export', lambda root: SimpleNamespace())
    attempts = [dict(status='ok', charged=1) for _ in range(64)]
    monkeypatch.setattr(s, 'artifact_json', lambda *args: attempts)
    monkeypatch.setattr(s, 'replay_slot', lambda *args: replayed.append(args))
    assert s.run(tmp_path, phase='qualification', max_runs=1) == dict(status='paused', new_runs=1)
    assert len(launched) == len(replayed) == 1
    attempts[0]['status'] = 'failed'
    with pytest.raises(ValueError, match='failed/uncharged'):
        s.run(tmp_path, phase='qualification')
    assert len(launched) == 1  # Existing failure is not replaced.


def synthetic_rows(gain=False):
    rows = []
    for arm in s.ARMS:
        for pack in s.PACKS:
            for index, seed in enumerate(s.SEEDS):
                scores = {}
                for p, benchmark, direction, _ in s.ENDPOINTS:
                    if p == pack:
                        scores[benchmark] = .8 if direction == 'max' else 100.
                        if gain and arm == 'full':
                            scores[benchmark] = (.90 + .005 * math.sin(index) if direction == 'max'
                                                 else 80. + math.sin(index))
                rows.append(dict(arm=arm, pack=pack, seed=seed, scores=scores))
    return rows


def test_paired_inference_detects_consistent_effect_with_family_correction():
    result = s.inference(synthetic_rows(gain=True))
    assert result['family_size'] == 468 and result['permutations'] == 65536
    assert result['overall_winner'] is None
    control = [r for r in result['contrasts'] if r['before'] == 'control' and r['after'] == 'full']
    assert len(control) == 6
    assert all(r['decision'] == 'after_supported_material_gain' for r in control)
    assert all(r['pvalue'] == 2 / 65536 and r['holm_pvalue'] <= .05 for r in control)
    assert all(r['simultaneous_ci95'][0] > r['materiality'] for r in control)
    ties = [r for r in result['contrasts'] if r['before'] == 'control' and r['after'] == 'attention']
    assert all(r['decision'] == 'observed_exact_tie' and r['pvalue'] == 1 for r in ties)


def test_no_partial_pairs_duplicates_or_nonfinite_scores():
    rows = synthetic_rows()
    for changed in (rows[:-1], rows + rows[:1]):
        with pytest.raises(ValueError, match='complete unique'):
            s.inference(changed)
    changed = deepcopy(rows)
    changed[0]['scores']['digits_image'] = np.nan
    with pytest.raises(ValueError, match='invalid endpoint'):
        s.inference(changed)


def test_report_has_no_inference_when_any_required_slot_is_missing(prepared, monkeypatch):
    monkeypatch.setattr(s, 'collect', lambda root, phase: ([], [{'reason': 'not run'}]))
    monkeypatch.setattr(s, 'inference', lambda rows: pytest.fail('partial evidence must not produce inference'))
    result = s.report(prepared)
    payload = json.loads(Path(result['report']).read_text())
    assert payload['status'] == 'incomplete' and payload['inference'] is None
