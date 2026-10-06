"""The preparation utility preserves all declared cells and other engine controls."""

import pytest

from evonn_compare.campaign import CampaignSpec
from evonn_compare import prism_frontier as planner
from evonn_shared.prism_policy import PrismResearchPolicy


def test_prepares_matched_complete_rosters_and_never_overwrites(tmp_path):
    base = CampaignSpec(pack="tier_b_core_v2", budgets=[64, 128], seeds=[1711, 1712],
                        prism_research=PrismResearchPolicy(optimizer_policy="continue"))
    output = tmp_path / "plans"
    assert planner.prepare(base, output) == list(planner.VARIANTS)
    original = base.model_dump(mode="json")
    for path in output.glob("*.json"):
        generated = CampaignSpec.model_validate_json(path.read_text()).model_dump(mode="json")
        assert generated["prism_research"]["variant"] == path.stem
        generated["prism_research"]["variant"] = original["prism_research"]["variant"]
        assert generated == original
    with pytest.raises(FileExistsError):
        planner.prepare(base, output)


def test_rejects_missing_engine_before_writing(tmp_path):
    base = CampaignSpec(systems=["prism", "contenders"])
    with pytest.raises(ValueError, match="every arm"):
        planner.prepare(base, tmp_path / "plans")
    assert not (tmp_path / "plans").exists()
