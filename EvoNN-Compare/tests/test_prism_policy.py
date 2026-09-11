from types import SimpleNamespace
from copy import deepcopy

import pytest
from evonn_compare import campaign, evidence
from evonn_shared.prism_policy import PrismResearchPolicy


def test_prism_experiments_require_every_engine_and_contenders():
    with pytest.raises(ValueError, match="every engine"):
        campaign.CampaignSpec(systems=["prism"], prism_research=PrismResearchPolicy())
    spec = campaign.CampaignSpec(prism_research=PrismResearchPolicy(variant="archive", inheritance_policy="disabled"))
    assert set(spec.systems) == {"prism", "topograph", "stratograph", "primordia", "contenders"}
    assert campaign.CampaignSpec.model_validate_json(spec.model_dump_json()) == spec
    with pytest.raises(ValueError):
        PrismResearchPolicy(variant="pruned")


def test_optimizer_and_inheritance_controls_do_not_merge_into_one_protocol(monkeypatch):
    config = {"source_sha256": "a" * 64, "epochs": 12, "population_size": 4, "fit_timeout": 90.,
              **PrismResearchPolicy().model_dump()}
    bundle = SimpleNamespace(manifest=SimpleNamespace(system=SimpleNamespace(value="prism"),
        runtime=SimpleNamespace(model_dump=lambda **kwargs: {"backend": "mlx_native"}),
        config_snapshot=SimpleNamespace(path="config.yaml")))
    monkeypatch.setattr(evidence, "artifact_json", lambda *args: config)
    original = evidence.protocol_fingerprint(bundle)
    for key, value in (("variant", "legacy"), ("inheritance_policy", "disabled"),
                       ("optimizer_policy", "continue"), ("optimizer_backend", "native")):
        before = deepcopy(config)
        config[key] = value
        assert evidence.protocol_fingerprint(bundle) != original
        config.clear()
        config.update(before)
