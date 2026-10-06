import pytest

from evonn_compare.campaign import CampaignSpec
from evonn_compare.prism_followup import prepare, VARIANTS
from evonn_compare.prism_confidence import ARMS
from evonn_shared.prism_policy import PrismResearchPolicy, V3_VARIANTS


def test_followup_preserves_full_matrix_and_frozen_study(tmp_path):
    assert len(ARMS) == 11 and not set(ARMS) & set(V3_VARIANTS)
    base = CampaignSpec(seeds=[22601, 22602], budgets=[32, 64])
    assert prepare(base, tmp_path / "plans") == list(VARIANTS)
    for variant in VARIANTS:
        result = CampaignSpec.model_validate_json((tmp_path / "plans" / f"{variant}.json").read_text())
        assert result.prism_research.variant == variant
        assert set(result.systems) == {"prism", "topograph", "stratograph", "primordia", "contenders"}
        assert result.seeds == base.seeds and result.budgets == base.budgets
        assert result.model_dump(exclude={"prism_research"}) == base.model_dump(exclude={"prism_research"})


def test_followup_rejects_reused_seeds_and_missing_engine(tmp_path):
    for base, message in ((CampaignSpec(seeds=[21605]), "fresh seeds"),
                          (CampaignSpec(seeds=[22601], systems=["prism"]), "every arm")):
        with pytest.raises(ValueError, match=message):
            prepare(base, tmp_path / "plans")
        assert not (tmp_path / "plans").exists()


@pytest.mark.parametrize("variant", V3_VARIANTS)
def test_v3_cannot_reuse_historical_prism_only_exception(variant):
    with pytest.raises(ValueError, match="eleven original variants"):
        CampaignSpec(systems=["prism"], prism_version_study="user-requested-20260921",
                     prism_research=PrismResearchPolicy(variant=variant))
