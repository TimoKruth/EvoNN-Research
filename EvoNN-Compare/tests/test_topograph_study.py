"""No-fit checks for the explicitly requested Topograph-only staged study."""
import json
from types import SimpleNamespace

import numpy as np
import pytest
from evonn_compare import campaign as c, topograph_study as s


def test_narrow_explicit_scope_does_not_weaken_general_roster():
    spec = s.matrix('screening')[0]['spec']
    assert c.CampaignSpec.model_validate(spec).systems == ['topograph']
    for changes in ({'comparison_scope': 'all_engines'}, {'systems': list(c.SYSTEMS)},
                    {'topograph_variant': None}, {'enhanced': True}, {'prism_research': {}}):
        with pytest.raises(ValueError):
            c.CampaignSpec.model_validate({**spec, **changes})


def test_all_available_arms_and_stages_are_paired_and_disjoint():
    from topograph.experiments import INTERVENTIONS
    assert s.INTERVENTIONS == INTERVENTIONS
    assert len(s.ARMS) == len(set(s.ARMS)) == 19
    assert len(s.matrix('qualification')) == 38
    assert len(s.matrix('screening')) == 152
    assert len(s.matrix('confirmation', 'query')) == 128
    assert len(s.matrix('confirmation', 'next')) == 96
    assert sum(map(len, s.SEEDS.values())) == len({v for values in s.SEEDS.values() for v in values})
    for stage in ('qualification', 'screening'):
        rows = s.matrix(stage)
        assert rows == s.matrix(stage)
        assert len({(r['arm'], r['pack'], r['seed']) for r in rows}) == len(rows)
        for pack in s.PACKS:
            for seed in s.SEEDS[stage]:
                assert {r['arm'] for r in rows if r['pack'] == pack and r['seed'] == seed} == set(s.ARMS)
        assert all(r['spec']['budgets'] == [s.BUDGETS[stage]] for r in rows)


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    monkeypatch.setattr(c, 'identity', lambda: {'commit': 'a' * 40})
    monkeypatch.setattr(s, 'seed_audit', lambda: {'scope': 'fixture'})
    preparations = []
    def fake_prepare(root, spec, cache):
        root.mkdir(parents=True)
        value = dict(schema_version='evonn.campaign/v1', spec=spec.model_dump(mode='json'),
                     identity=c.identity(), cache=str(cache), datasets=[], workspace=str(root.absolute()))
        s.publish_json(root / 'campaign.json', s.signed(value))
        preparations.append((spec.pack, tuple(spec.seeds)))
    monkeypatch.setattr(c, 'prepare_plan', fake_prepare)
    monkeypatch.setattr(c, 'preflight', lambda root: {'status': 'passed'})
    root = tmp_path / 'study'
    result = s.prepare(root, tmp_path / 'cache')
    assert result['status'] == 'ready' and not result['training_started']
    assert result['prepared_runs'] == 190
    assert len(preparations) == 10  # per pack/seed, reused across 19 arms
    return root


def test_preparation_never_fits_and_freezes_policy_and_all_campaigns(prepared):
    plan = s.read_plan(prepared)
    assert len(plan['campaign_sha256']) == 190
    assert not list(prepared.rglob('runs'))
    path = prepared / plan['matrix'][0]['campaign'] / 'campaign.json'
    manifest = json.loads(path.read_text())
    manifest['cache'] = '/wrong-cache'
    manifest = s.signed({k: v for k, v in manifest.items() if k != 'sha256'})
    path.write_bytes(c.encoded(manifest))
    with pytest.raises(ValueError, match='campaign differs'):
        s.preflight(prepared)


def test_refreezing_changed_policy_is_rejected(prepared):
    path = prepared / 'study.json'
    plan = json.loads(path.read_text())
    plan['policy']['confidence'] = 'different rule after seeing results'
    plan = s.signed({k: v for k, v in plan.items() if k != 'sha256'})
    path.write_bytes(c.encoded(plan))
    with pytest.raises(ValueError, match='protocol'):
        s.read_plan(prepared)


def synthetic(stage, nominee='query', gain=False):
    arms = s.ARMS if stage == 'screening' else set((*s.CONTROLS, nominee))
    rows = []
    for arm in arms:
        for i, seed in enumerate(s.SEEDS[stage]):
            for pack in s.PACKS:
                metrics = {task: (0.8 if direction == 1 else 100.)
                           for p, task, direction, _ in s.ENDPOINTS if p == pack}
                if gain and arm == nominee:
                    for p, task, direction, _ in s.ENDPOINTS:
                        if p == pack:
                            metrics[task] *= (1.1 + i / 2000) if direction == 1 else (0.85 - i / 2000)
                rows.append(dict(arm=arm, pack=pack, seed=seed, metrics=metrics))
    return rows


def test_nomination_is_deterministic_and_no_positive_effect_retains_open():
    assert s.choose_nominee(synthetic('screening'))[0] == 'open'
    candidate, scores = s.choose_nominee(synthetic('screening', gain=True))
    assert candidate == 'query' and scores['query'] > 0
    assert scores['open'] == 0


def test_inference_has_correct_direction_seed_units_and_three_test_family():
    contrasts = s.inference(synthetic('confirmation', gain=True), 'query')
    assert len(contrasts) == 3
    for row in contrasts:
        assert row['inference']['n'] == 16
        assert row['holm_pvalue'] <= .05
        assert row['decision'] == 'confirmed_aggregate_gain'
        assert row['inference']['simultaneous_ci'][0] > .01
        assert row['inference']['simultaneous_ci'][0] <= row['inference']['bootstrap_ci95'][0]
    tied = s.inference(synthetic('confirmation', nominee='next'), 'next')
    assert all(r['pvalue'] == 1 and r['holm_pvalue'] == 1 for r in tied)
    assert next(r for r in tied if r['control'] == 'next')['decision'] == 'self_control'


def test_inference_rejects_partial_duplicate_and_nonfinite_rows():
    rows = synthetic('confirmation')
    for changed in (rows[:-1], rows + rows[:1]):
        with pytest.raises(ValueError, match='complete unique'):
            s.inference(changed, 'query')
    rows[0]['metrics'][next(iter(rows[0]['metrics']))] = np.nan
    with pytest.raises(ValueError, match='nonfinite'):
        s.inference(rows, 'query')


def test_incomplete_qualification_blocks_screening_and_nomination(prepared, monkeypatch):
    monkeypatch.setattr(s, 'collect', lambda *args: {'status': 'incomplete'})
    monkeypatch.setattr(c, 'run_campaign', lambda *args, **kwargs: pytest.fail('no dispatch'))
    with pytest.raises(ValueError, match='prior stage incomplete'):
        s.run(prepared, 'screening')
    with pytest.raises(ValueError, match='complete qualification'):
        s.nominate(prepared)
    assert not (prepared / 'nomination.json').exists()


def test_nomination_is_immutable_and_confirmation_requires_binding(prepared, monkeypatch):
    results = synthetic('screening', gain=True)
    monkeypatch.setattr(s, 'collect', lambda *args: {'status': 'complete', 'results': results})
    nomination = s.nominate(prepared)
    assert nomination['nominee'] == 'query'
    with pytest.raises(ValueError, match='already frozen'):
        s.nominate(prepared)
    results[0]['metrics'][next(iter(results[0]['metrics']))] += .01
    with pytest.raises(ValueError, match='no longer binds'):
        s.prepare_confirmation(prepared)


def test_controller_dispatch_and_replay_limit(prepared, monkeypatch):
    plan = s.read_plan(prepared)
    rows = s.stage_rows(prepared, plan, 'qualification')[:2]
    monkeypatch.setattr(s, 'stage_rows', lambda *args: rows)
    complete = set()
    monkeypatch.setattr(c, 'adopted', lambda root, *args: (root / 'runs' / 'fixture', {'run_id': 'fixture'})
                        if root in complete else (None, None))
    monkeypatch.setattr(c, 'run_campaign', lambda root, **kwargs: complete.add(root))
    calls = []
    def replay(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=json.dumps({'status': 'passed'}))
    monkeypatch.setattr(s.subprocess, 'run', replay)
    monkeypatch.setattr(s, 'collect', lambda *args: {'status': 'incomplete', 'results': []})
    s.run(prepared, 'qualification', max_runs=1)
    assert len(complete) == len(calls) == 1
    assert calls[0][1:4] == ['-m', 'topograph.cli', 'replay']
    assert len(list(prepared.rglob('winner-replay.json'))) == 1
