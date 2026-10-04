"""CLI compatibility and repeatable, modality-directed family exploration."""
import json
from copy import deepcopy

import pytest
from evonn_shared.active_catalog import get_benchmark
from evonn_shared.primordia_policy import RESEARCH_DEFAULTS
from evonn_shared.primordia_presets import ARMS, PRESETS
from evonn_primordia import cli
from evonn_primordia.experiments import specifications, SYSTEMS
from evonn_primordia.presets import preset_policy
from evonn_primordia.search import Search


def test_cli_standard_explicit_controls_and_config_compatibility(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(cli, 'run_engine', lambda *a, **kw: calls.append(kw))
    cli.main(['run'])
    assert all(calls[-1][k] == v for k, v in ARMS['full_steady'].items())
    cli.main(['run', '--preset', 'control'])
    assert all(calls[-1][k] == v for k, v in RESEARCH_DEFAULTS.items())
    cli.main(['run', '--architecture-policy=attention_v3'])
    assert calls[-1]['architecture_policy'] == 'attention_v3'
    assert calls[-1]['optimization_policy'] == calls[-1]['proposal_policy'] == 'v2'
    path = tmp_path / 'old.json'
    path.write_text(json.dumps({'budget': 8}))
    cli.main(['run', '--config', str(path)])
    assert all(calls[-1][k] == v for k, v in RESEARCH_DEFAULTS.items())
    cli.main(['run', '--search-policy', 'legacy_v1'])
    assert calls[-1]['search_policy'] == 'legacy_v1'
    for name in PRESETS:
        cli.main(['run', '--preset', name, '--max-width', '12'])
        policy = preset_policy(name)
        assert calls[-1]['max_width'] == 12
        assert all(calls[-1][k] == getattr(policy, k) for k in RESEARCH_DEFAULTS)
    for flag in ['--config=x', '--resume=x', '--optimization-policy=v2']:
        with pytest.raises(SystemExit):
            cli.main(['run', '--preset', 'standard', flag])


def test_resume_does_not_apply_new_defaults(monkeypatch, tmp_path):
    saved = dict(pack='tier1_core', total=8, seed=3, cache=str(tmp_path), backend='numpy_fallback',
                 device='cpu', timeout=100., fit_timeout=10., epochs=2, population_size=4,
                 search_policy='breadth_v2', max_width=12, max_depth=3)
    (tmp_path / 'config.yaml').write_text(json.dumps(saved))
    calls = []
    monkeypatch.setattr(cli, 'run_engine', lambda *a, **kw: calls.append(kw))
    cli.main(['run', '--resume', str(tmp_path)])
    assert all(calls[-1][k] == v for k, v in RESEARCH_DEFAULTS.items())
    assert calls[-1]['seed'] == 3
    with pytest.raises(SystemExit):
        cli.main(['run', '--resume', str(tmp_path), '--architecture-policy', 'portfolio_v4'])


@pytest.mark.parametrize('size', [2, 4, 7])
def test_portfolio_roundrobin_survives_failures_and_resume(size):
    definitions = [get_benchmark(b) for b in ['iris_classification', 'digits_image', 'shakespeare_byte_lm']]
    search = Search(definitions, seed=902, population_size=size, architecture_policy='portfolio_v4',
                    optimization_policy='steady_v3', proposal_policy='progress_v3', max_width=8, max_depth=3)
    fresh = {d.id: [] for d in definitions}
    for step in range(90):
        restored = Search(definitions, seed=99, population_size=size, state=json.loads(json.dumps(search.state())))
        for d in definitions:
            g = search.candidate(d.id)
            assert g == restored.candidate(d.id)
            assert g.version == (2 if d.input_modality.value == 'tabular' else 3)
            if search.proposal(d.id)['operator'] in {'founder', 'restart'}:
                fresh[d.id].append(g.temporal_mode if d.task_kind.value == 'language_modeling' else g.spatial_mode)
            result = dict(status='failed', reason='test failure') if step % 11 == 0 else dict(
                status='ok', score=float(step % 3), parameter_count=100, updates=2, validation_curve=[1., .9])
            search.observe(d.id, g, result)
            restored.observe(d.id, g, result)
        assert restored.state() == search.state()
    for name, families in [('digits_image', ('conv_pool', 'conv_flat')),
                           ('shakespeare_byte_lm', ('convolution', 'attention', 'multiscale'))]:
        assert len(fresh[name]) >= 6
        assert fresh[name] == [families[i % len(families)] for i in range(len(fresh[name]))]
    assert all(sum(v.values()) == 90 for v in search.telemetry()['portfolio_family_attempts'].values())
    damaged = deepcopy(search.state())
    del damaged['portfolio_counts']
    with pytest.raises(ValueError, match='portfolio'):
        Search(definitions, seed=1, population_size=size, state=damaged)


def test_new_comparisons_keep_all_engines_and_historical_matrix():
    assert len(ARMS) == 13
    assert preset_policy('standard') == preset_policy('full_steady')
    specs = specifications(pack='tier_b_core_v2', budgets=[128], seeds=[24001, 24002],
                           arms=['control', 'standard', 'portfolio', 'portfolio_stable'])
    assert all(v['systems'] == SYSTEMS and v['seeds'] == [24001, 24002] for v in specs.values())
