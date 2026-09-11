"""Campaign controls and repeated-seed identities must bind Primordia policies."""
from copy import deepcopy
from types import SimpleNamespace
import json
from pathlib import Path

import pytest
from evonn_compare import campaign as c, evidence
from evonn_shared.primordia_policy import PrimordiaResearchPolicy
from evonn_primordia.config import RunConfig


def test_policy_defaults_match_producer_and_require_full_roster():
    defaults = PrimordiaResearchPolicy().model_dump()
    assert {key: RunConfig().model_dump()[key] for key in defaults} == defaults
    with pytest.raises(ValueError, match='every engine'):
        c.CampaignSpec(systems=['primordia'], primordia_research=defaults)
    for value in (dict(max_width=True), dict(max_depth=33), dict(search_policy='unknown')):
        with pytest.raises(ValueError):
            PrimordiaResearchPolicy(**value)


@pytest.fixture
def binding():
    spec = c.CampaignSpec()
    case = c.Case(spec.pack, 16, 42)
    versions = {n: 'fixture' for n in ('numpy', 'scipy', 'scikit-learn', 'pandas', 'openml')}
    manifest = dict(spec=spec.model_dump(mode='json'),
                    identity=dict(commit='a'*40, source_sha256='b'*64, versions=versions), cache='/cache')
    config = dict(system='primordia', pack=case.pack, total=case.budget, seed=case.seed,
                  backend=spec.backend, epochs=spec.epochs, timeout=spec.timeout,
                  fit_timeout=spec.fit_timeout, population_size=4, device='cpu', source_sha256='b'*64,
                  cache='/cache', shared_root=str(c.ROOT/'shared-benchmarks'), git_commit='a'*40,
                  code_dirty=False, dataset_versions=versions, evaluator_fidelity='end_to_end_primitive',
                  **PrimordiaResearchPolicy().model_dump(),
                  training_policy=PrimordiaResearchPolicy().training_policy)
    return manifest, case, config


@pytest.mark.parametrize('change', [dict(search_policy='legacy_v1', training_policy='legacy/v1'),
    dict(max_width=256), dict(max_depth=32), dict(training_policy='legacy/v1')])
def test_adoption_and_seed_fingerprint_bind_policy(binding, monkeypatch, change):
    manifest, case, config = binding
    c.match_config(config, manifest, case, 'primordia')
    bundle = SimpleNamespace(manifest=SimpleNamespace(system=SimpleNamespace(value='primordia'),
        runtime=SimpleNamespace(model_dump=lambda **kwargs: {'backend': 'mlx_native'}),
        config_snapshot=SimpleNamespace(path='config.yaml')))
    monkeypatch.setattr(evidence, 'artifact_json', lambda *args: config)
    fingerprint = evidence.protocol_fingerprint(bundle)
    config.update(change)
    with pytest.raises(ValueError, match='Primordia research'):
        c.match_config(config, manifest, case, 'primordia')
    assert evidence.protocol_fingerprint(bundle) != fingerprint


def test_explicit_control_and_historical_config(binding):
    manifest, case, config = binding
    original = deepcopy(config)
    policy = PrimordiaResearchPolicy(search_policy='legacy_v1', max_width=24, max_depth=4)
    manifest['spec']['primordia_research'] = policy.model_dump()
    config.update(**policy.model_dump(), training_policy=policy.training_policy)
    c.match_config(config, manifest, case, 'primordia')
    with pytest.raises(ValueError):
        c.match_config(original, manifest, case, 'primordia')
    for key in (*policy.model_dump(), 'training_policy'):
        config.pop(key)
    with pytest.raises(ValueError):
        c.match_config(config, manifest, case, 'primordia')
    manifest['spec'].pop('primordia_research')
    c.match_config(config, manifest, case, 'primordia')


def test_new_plan_freezes_primordia_defaults(tmp_path, monkeypatch):
    spec = c.CampaignSpec(seeds=[42])
    monkeypatch.setattr(c, 'identity', lambda: {'commit': 'a'*40})
    monkeypatch.setattr(c, 'preflight', c.read_manifest)
    def prepare(command, *args, **kwargs):
        Path(command[-1]).write_text('{}')
    monkeypatch.setattr(c, '_bounded_process', prepare)
    manifest = c.prepare_plan(tmp_path/'campaign', spec, tmp_path/'cache')
    assert manifest['spec']['primordia_research'] == PrimordiaResearchPolicy().model_dump()
    assert spec.primordia_research is None


def test_dispatch_roundtrips_explicit_primordia_controls(tmp_path, monkeypatch):
    policy = PrimordiaResearchPolicy(search_policy='legacy_v1', max_width=24, max_depth=4)
    spec = c.CampaignSpec(seeds=[42], primordia_research=policy)
    manifest = dict(schema_version='evonn.campaign/v1', spec=spec.model_dump(mode='json'),
                    identity={}, cache='/cache', datasets=[], workspace=str(tmp_path))
    manifest['sha256'] = c.sha(manifest)
    (tmp_path/'campaign.json').write_bytes(c.encoded(manifest))
    monkeypatch.setattr(c, 'preflight', lambda root: None)
    # Other systems were already completed; only the Primordia slot dispatches.
    finished = {c.slot_id(case, system): {'system': system, 'run_id': system, 'export': 'fixture', 'documents': []}
                for case, system in c.slots(spec) if system != 'primordia'}
    monkeypatch.setattr(c, 'adopted', lambda root, manifest, case, system: (None, finished.get(c.slot_id(case, system))))
    def dispatch(command, *args, **kwargs):
        event = json.loads(Path(command[-2]).read_bytes())
        argv = event['details']['command']
        for key, value in policy.model_dump().items():
            assert argv[argv.index('--' + key.replace('_', '-')) + 1] == str(value)
        finished[event['slot']] = dict(system='primordia', run_id='primordia', export='fixture', documents=[])
    monkeypatch.setattr(c, '_bounded_process', dispatch)
    monkeypatch.setattr(c, 'workspace_report', lambda root: {})
    assert c.run_campaign(tmp_path, max_runs=1)['new_runs'] == 1
