import json
from pathlib import Path

import pytest
import yaml

from topograph.config import RunConfig
from topograph.presets import expand_preset, preset_policy
from evonn_shared.topograph_policy import TopographResearchPolicy


def test_mixer_exactly_preserves_confirmed_settings():
    variant, policy = preset_policy("mixer")
    assert variant == "next"
    assert policy == TopographResearchPolicy(adapters="mixer")
    config = RunConfig.model_validate(yaml.safe_load(
        (Path(__file__).parents[1] / "configs/mixer.yaml").read_text()))
    assert config.variant == variant and config.research_options == policy
    expanded = expand_preset(["run", "--preset=mixer", "--seed", "17"])
    assert expanded[:3] == ["run", "--seed", "17"]
    assert json.loads(expanded[-1]) == policy.model_dump()


@pytest.mark.parametrize("flag", ["--config=x", "--variant=open", "--research-options={}", "--resume=x"])
def test_ambiguous_configuration_rejected(flag):
    with pytest.raises(SystemExit):
        expand_preset(["run", "--preset", "mixer", flag])


@pytest.mark.parametrize("argv", [["run"], ["run", "--resume", "old-run"], ["replay", "old-run"]])
def test_historical_commands_unchanged(argv):
    assert expand_preset(argv) == argv


def test_default_config_is_mixer_and_explicit_next_remains_diverse():
    assert RunConfig().research_options == preset_policy("mixer")[1]
    assert RunConfig.model_validate({"variant": None}).variant == "next"
    assert RunConfig(variant="legacy").research_options is None
    assert RunConfig(variant="open").variant == "open"
    assert RunConfig(variant="next").research_options is None
    custom = RunConfig(research_options={"allocation": "full"})
    assert custom.research_options.adapters == "mixer"
    assert custom.research_options.allocation == "full"


@pytest.mark.parametrize("selection,variant,adapter", [
    ([], "next", "mixer"), (["--preset", "legacy"], "legacy", None),
    (["--preset", "next"], "next", "diverse"), (["--variant", "open"], "open", None),
])
def test_cli_resolves_new_run_policy(monkeypatch, selection, variant, adapter):
    from topograph import cli
    calls = []
    monkeypatch.setattr(cli, "run_engine", lambda *args, **kw: calls.append(kw) or "/fixture")
    cli.main(["run", *selection])
    assert calls[0]["variant"] == variant
    assert (calls[0]["research_options"]["adapters"] if adapter else None) == adapter


def test_config_without_variant_uses_mixer(tmp_path, monkeypatch):
    from topograph import cli
    path = tmp_path / "run.json"
    path.write_text(json.dumps({"budget": 8, "pack": "tier1_core_smoke"}))
    calls = []
    monkeypatch.setattr(cli, "run_engine", lambda *args, **kw: calls.append(kw) or "/fixture")
    cli.main(["run", "--config", str(path)])
    assert calls[0]["research_options"]["adapters"] == "mixer"


@pytest.mark.parametrize("saved_policy", [{}, {"variant": "next", "research_options": TopographResearchPolicy().model_dump()}])
def test_resume_restores_saved_policy_including_unversioned_legacy(tmp_path, monkeypatch, saved_policy):
    from topograph import cli
    saved = dict(pack="tier1_core_smoke", total=8, seed=42, cache=str(tmp_path / "cache"),
                 backend="numpy_fallback", device="cpu", timeout=220., fit_timeout=20.,
                 epochs=2, population_size=2, benchmark_pooling=False, novelty_weight=0., **saved_policy)
    (tmp_path / "config.yaml").write_text(json.dumps(saved))
    calls = []
    monkeypatch.setattr(cli, "run_engine", lambda *args, **kw: calls.append(kw) or "/fixture")
    cli.main(["run", "--resume", str(tmp_path)])
    assert calls[0]["variant"] == saved.get("variant", "legacy")
    assert calls[0]["research_options"] == saved.get("research_options")
