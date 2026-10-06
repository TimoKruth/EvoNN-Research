"""Every Stratograph arm remains a portable all-engine comparison input."""
import pytest

from evonn_compare.campaign import CampaignSpec
from evonn_shared.hierarchy_policy import HierarchyResearchPolicy
from evonn_shared.hierarchy_presets import hierarchy_presets


@pytest.mark.parametrize('name', tuple(hierarchy_presets()))
def test_presets_roundtrip_and_require_full_roster(name):
    policy = hierarchy_presets()[name]
    spec = CampaignSpec(stratograph_research=policy)
    assert CampaignSpec.model_validate_json(spec.model_dump_json()) == spec
    assert HierarchyResearchPolicy.model_validate_json(policy.model_dump_json()) == policy
    with pytest.raises(ValueError, match='every engine'):
        CampaignSpec(stratograph_research=policy, systems=['stratograph'])


def test_generator_writes_separate_explicit_arms_without_overwriting(tmp_path):
    import json
    from evonn_compare import hierarchy_configs as module
    destination = tmp_path / 'specs'
    args = ['--output', str(destination), '--packs', 'tier_b_core_v2', 'language_breadth_v1',
            '--budgets', '16', '--seeds', '1601', '1602', '--arms', 'v2_reference', 'attention', 'hybrid']
    module.main(args)
    index = json.loads((destination / 'index.json').read_text())
    assert index['status'] == 'unexecuted_configuration_templates'
    assert index['total_runs'] == 60
    for name in index['specs']:
        campaign = CampaignSpec.model_validate_json((destination / f'{name}.json').read_text())
        assert set(campaign.systems) == {'prism', 'topograph', 'stratograph', 'primordia', 'contenders'}
    with pytest.raises(FileExistsError):
        module.main(args)
