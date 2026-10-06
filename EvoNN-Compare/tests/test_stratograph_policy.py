"""Freeze the quality default only for new plans; historical null means legacy."""
import json
from pathlib import Path

import pytest
from evonn_compare import campaign as c
from evonn_shared.hierarchy_presets import hierarchy_presets


def test_new_plan_freezes_evolving_and_preserves_explicit_controls(tmp_path, monkeypatch):
    spec = c.CampaignSpec(seeds=[42])
    monkeypatch.setattr(c, 'identity', lambda: {'commit': 'a'*40})
    monkeypatch.setattr(c, 'preflight', c.read_manifest)
    monkeypatch.setattr(c, '_bounded_process', lambda command, *a, **k: Path(command[-1]).write_text('{}'))
    manifest = c.prepare_plan(tmp_path/'campaign', spec, tmp_path/'cache')
    assert manifest['spec']['stratograph_research'] == hierarchy_presets()['evolving'].model_dump(mode='json')
    assert spec.stratograph_research is None
    assert c.CampaignSpec.model_validate({}).stratograph_research is None
    for policy in [None, *hierarchy_presets().values()]:
        assert c.new_plan_defaults(c.CampaignSpec(stratograph_research=policy)).stratograph_research == policy


@pytest.mark.parametrize('policy', [None, hierarchy_presets()['evolving'], hierarchy_presets()['v2_reference']])
def test_dispatch_always_pins_policy_including_historical_legacy(tmp_path, monkeypatch, policy):
    spec = c.CampaignSpec(seeds=[42], stratograph_research=policy)
    serialized = spec.model_dump(mode='json')
    if policy is None:
        serialized.pop('stratograph_research')
    manifest = dict(schema_version='evonn.campaign/v1', spec=serialized, identity={}, cache='/cache',
                    datasets=[], workspace=str(tmp_path))
    manifest['sha256'] = c.sha(manifest)
    (tmp_path/'campaign.json').write_bytes(c.encoded(manifest))
    monkeypatch.setattr(c, 'preflight', lambda root: None)
    finished = {c.slot_id(case, system): dict(system=system, run_id=system, export='fixture', documents=[])
                for case, system in c.slots(spec) if system != 'stratograph'}
    monkeypatch.setattr(c, 'adopted', lambda root, manifest, case, system: (None, finished.get(c.slot_id(case, system))))
    def dispatch(command, *args, **kwargs):
        event = json.loads(Path(command[-2]).read_bytes())
        argv = event['details']['command']
        assert json.loads(argv[argv.index('--research')+1]) == (policy.model_dump(mode='json') if policy else None)
        finished[event['slot']] = dict(system='stratograph', run_id='stratograph', export='fixture', documents=[])
    monkeypatch.setattr(c, '_bounded_process', dispatch)
    monkeypatch.setattr(c, 'workspace_report', lambda root: {})
    assert c.run_campaign(tmp_path, max_runs=1)['new_runs'] == 1
