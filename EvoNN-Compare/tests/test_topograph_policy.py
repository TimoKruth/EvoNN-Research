"""Research policy must be explicit and cannot narrow the campaign roster."""

import pytest
from evonn_compare import campaign as c


def test_new_plans_freeze_mixer_without_reinterpreting_historical_specs():
    from evonn_shared.topograph_policy import TopographResearchPolicy
    historical = c.CampaignSpec()
    updated = c.new_plan_defaults(historical)
    assert updated.topograph_variant == "next"
    assert updated.topograph_research == TopographResearchPolicy(adapters="mixer")
    assert historical.topograph_variant is None
    assert c.CampaignSpec.model_validate(historical.model_dump()).topograph_variant is None
    for variant in ("legacy", "next", "open"):
        explicit = c.new_plan_defaults(c.CampaignSpec(topograph_variant=variant))
        assert explicit.topograph_variant == variant and explicit.topograph_research is None


def test_topograph_research_requires_full_roster():
    with pytest.raises(ValueError, match="every engine"):
        c.CampaignSpec(systems=["topograph"], topograph_variant="open")
    spec = c.CampaignSpec(topograph_variant="open")
    assert set(spec.systems) == set(c.SYSTEMS)
    assert spec.model_dump(mode="json")["topograph_variant"] == "open"
    with pytest.raises(ValueError):
        c.CampaignSpec(topograph_variant="unknown")


@pytest.mark.parametrize("variant", ["open", "next"])
def test_campaign_rejects_substituting_a_different_topograph_policy(variant):
    spec = c.CampaignSpec(topograph_variant=variant)
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
        variant=variant,
    )
    versions = {name: "fixture" for name in ("numpy", "scipy", "scikit-learn", "pandas", "openml")}
    manifest["identity"]["versions"] = versions
    config["dataset_versions"] = versions
    if variant == "next":
        from evonn_shared.topograph_policy import TopographResearchPolicy
        config["research_options"] = TopographResearchPolicy().model_dump()
    c.match_config(config, manifest, case, "topograph")
    config["variant"] = "broad"
    with pytest.raises(ValueError, match="Topograph research"):
        c.match_config(config, manifest, case, "topograph")
    if variant == "next":
        config["variant"] = variant
        config["research_options"]["allocation"] = "full"
        with pytest.raises(ValueError, match="research options"):
            c.match_config(config, manifest, case, "topograph")


def test_next_campaign_policy_requires_next_variant_and_complete_roster():
    with pytest.raises(ValueError, match="variant next"):
        c.CampaignSpec(topograph_research={"adapters": "query"})
    with pytest.raises(ValueError, match="every engine"):
        c.CampaignSpec(systems=["topograph"], topograph_variant="next", topograph_research={"adapters": "query"})
    with pytest.raises(ValueError):
        c.CampaignSpec(topograph_variant="next", topograph_research={"parameter_cap": 2_000_001})


def test_next_options_separate_protocol_fingerprints(monkeypatch):
    from types import SimpleNamespace
    from evonn_compare import evidence
    config = {"variant": "next", "research_options": {"adapters": "query"}}
    monkeypatch.setattr(evidence, "artifact_json", lambda *args: config)
    bundle = SimpleNamespace(manifest=SimpleNamespace(
        runtime=SimpleNamespace(model_dump=lambda **kwargs: {}),
        system=SimpleNamespace(value="topograph"), config_snapshot=SimpleNamespace(path="config.yaml")))
    first = evidence.protocol_fingerprint(bundle)
    config["research_options"]["adapters"] = "mixer"
    assert evidence.protocol_fingerprint(bundle) != first
