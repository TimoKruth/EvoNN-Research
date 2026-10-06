"""Quality defaults must reach CLI/API execution without migrating saved policies."""
import json
from pathlib import Path

import pytest

from evonn_shared.hierarchy_presets import hierarchy_presets
from evonn_shared.engine_evidence import artifact_json, validate_engine_bundle
from evonn_shared.export_reader import read_export
from stratograph import cli, run
from stratograph.config import RunConfig
from stratograph.presets import DEFAULT_BACKEND, expand_preset
from stratograph.search import Search
from .test_research_runtime import invoke


@pytest.fixture
def capture(monkeypatch):
    calls = []
    def execute(search, **kwargs):
        calls.append(kwargs)
        return 'captured'
    monkeypatch.setattr(cli, 'run_engine', execute)
    return calls


def test_default_cli_config_and_quality_allocation_agree(capture, tmp_path):
    for args in (['run'], ['evolve'], ['run', '--preset', 'standard']):
        cli.main(args)
    path = tmp_path/'config.yaml'
    path.write_text('pack: tier1_core_smoke\n')
    cli.main(['run', '--config', str(path)])
    config = RunConfig()
    for call in capture:
        assert call['research'] == hierarchy_presets()['evolving'].model_dump(mode='json')
        assert call['budget'] == config.budget == 128
        assert call['epochs'] == config.epochs == 12
        assert call['fit_timeout'] == config.fit_timeout == 600
        assert call['timeout'] == config.timeout == 81240
        assert call['backend'] == config.backend == DEFAULT_BACKEND
    assert config.research.screen_epochs == 0
    assert config.research.inheritance == 'compatible'
    assert config.research.dropout == 0


@pytest.mark.parametrize('name', ['legacy', *hierarchy_presets()])
def test_explicit_presets_reach_engine(capture, name):
    cli.main(['run', '--preset='+name, '--budget', '16', '--epochs', '2', '--backend', 'numpy_fallback'])
    expected = None if name == 'legacy' else hierarchy_presets()[name].model_dump(mode='json')
    assert capture[0]['research'] == expected
    assert capture[0]['budget'] == 16 and capture[0]['epochs'] == 2
    assert capture[0]['backend'] == 'numpy_fallback'


def test_yaml_null_and_explicit_policy_override_defaults(capture, tmp_path):
    path = tmp_path/'legacy.yaml'
    path.write_text('research: null\nbudget: 8\ntimeout: 25\nfit_timeout: 5\n')
    cli.main(['run', '--config', str(path)])
    assert capture[-1]['research'] is None
    assert capture[-1]['timeout'] == 25 and capture[-1]['fit_timeout'] == 5
    policy = hierarchy_presets()['hybrid_dropout'].model_dump(mode='json')
    cli.main(['run', '--config', str(path), '--research', json.dumps(policy), '--budget', '16'])
    assert capture[-1]['research'] == policy and capture[-1]['budget'] == 16


@pytest.mark.parametrize('policy', [None, hierarchy_presets()['v2_reference'].model_dump(mode='json')])
def test_historical_resume_never_injects_new_policy_or_allocation(capture, tmp_path, policy):
    saved = dict(pack='tier1_core_smoke', total=8, seed=5, epochs=2, population_size=2,
                 backend='numpy_fallback', device='cpu', timeout=25, fit_timeout=5,
                 cache=str(tmp_path/'cache'), variant='shared')
    if policy is not None:
        saved['research'] = policy
    (tmp_path/'config.yaml').write_text(json.dumps(saved))
    cli.main(['run', '--resume', str(tmp_path)])
    call = capture[-1]
    assert call['research'] == policy and call['budget'] == 8
    assert call['timeout'] == 25 and call['fit_timeout'] == 5
    assert call['backend'] == 'numpy_fallback'
    with pytest.raises(SystemExit):
        cli.main(['run', '--resume', str(tmp_path), '--research',
                  json.dumps(hierarchy_presets()['evolving'].model_dump(mode='json'))])


@pytest.mark.parametrize('other', [['--research', 'null'], ['--config', 'file.yaml'], ['--resume', 'run']])
def test_ambiguous_preset_rejected(other):
    with pytest.raises(SystemExit):
        expand_preset(['run', '--preset', 'attention', *other])


@pytest.mark.parametrize('preset', ['standard', 'legacy'])
def test_new_defaults_and_legacy_resume_export_replay(tmp_path, preset):
    first = invoke('run', '--preset', preset, '--pack', 'tier1_core_smoke', '--budget', 8,
                   '--epochs', 2, '--timeout', 220, '--fit-timeout', 20,
                   '--output', tmp_path/'runs', '--cache', tmp_path/'cache', '--stop-after', 3)
    assert first.returncode == 0, first.stderr
    directory = Path(first.stdout.strip().splitlines()[-1])
    resumed = invoke('run', '--resume', directory)
    assert resumed.returncode == 0, resumed.stderr
    bundle = read_export(directory/'symbiosis')
    validate_engine_bundle(bundle, verify_cache=True)
    assert bundle.results.coverage.ok == 8
    config = artifact_json(bundle, 'config.yaml')
    if preset == 'standard':
        assert config['research'] == hierarchy_presets()['evolving'].model_dump(mode='json')
        assert all(a['epochs'] == a['allocated_epochs'] == 2
                   for a in artifact_json(bundle, 'attempts.json')['attempts'])
    else:
        assert 'research' not in config
    replay = invoke('replay', directory)
    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout)['status'] == 'passed'


def test_direct_api_uses_standard_and_restores_explicit_legacy(tmp_path):
    for name, options in [('standard', {}), ('legacy', {'research': None})]:
        directory = run.run_engine(Search, pack_name='tier1_core_smoke', budget=8, epochs=1,
                                   timeout=120, fit_timeout=20, output_parent=tmp_path/name,
                                   cache_root=tmp_path/'cache', stop_after=1, **options)
        saved = json.loads((directory/'config.yaml').read_text())
        assert saved.get('research') == (hierarchy_presets()['evolving'].model_dump(mode='json')
                                          if name == 'standard' else None)
        # Omitted changed defaults, including policy, must come from the saved run.
        exported = run.run_engine(Search, pack_name='tier1_core_smoke', epochs=1,
                                  cache_root=tmp_path/'cache', resume=directory)
        bundle = read_export(exported)
        validate_engine_bundle(bundle, verify_cache=True)
        assert bundle.results.coverage.ok == 8
