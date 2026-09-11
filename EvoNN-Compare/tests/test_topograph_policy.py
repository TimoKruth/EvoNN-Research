"""Research policy must be explicit and cannot narrow the campaign roster."""

import pytest
from evonn_compare import campaign as c


def test_topograph_research_requires_full_roster():
    with pytest.raises(ValueError, match="every engine"):
        c.CampaignSpec(systems=["topograph"], topograph_variant="open")
    spec = c.CampaignSpec(topograph_variant="open")
    assert set(spec.systems) == set(c.SYSTEMS)
    assert spec.model_dump(mode="json")["topograph_variant"] == "open"
    with pytest.raises(ValueError):
        c.CampaignSpec(topograph_variant="unknown")


def test_campaign_rejects_substituting_a_different_topograph_policy():
    spec = c.CampaignSpec(topograph_variant="open")
    case = c.Case(spec.pack, 16, 42)
    manifest = dict(
        spec=spec.model_dump(mode="json"), identity=dict(commit="a" * 40, source_sha256="b" * 64), cache="/cache"
    )
    config = dict(
        system="topograph",
        pack=case.pack,
        total=case.budget,
        seed=case.seed,
        backend=spec.backend,
        epochs=spec.epochs,
        timeout=spec.timeout,
        fit_timeout=spec.fit_timeout,
        population_size=4,
        device="cpu",
        source_sha256="b" * 64,
        cache="/cache",
        shared_root=str(c.ROOT / "shared-benchmarks"),
        benchmark_pooling=False,
        novelty_weight=0.0,
        git_commit="a" * 40,
        code_dirty=False,
        variant="open",
    )
    versions = {name: "fixture" for name in ("numpy", "scipy", "scikit-learn", "pandas", "openml")}
    manifest["identity"]["versions"] = versions
    config["dataset_versions"] = versions
    c.match_config(config, manifest, case, "topograph")
    config["variant"] = "broad"
    with pytest.raises(ValueError, match="Topograph research"):
        c.match_config(config, manifest, case, "topograph")
