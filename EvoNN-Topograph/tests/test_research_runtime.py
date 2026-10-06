"""Real subprocess/resume/export/replay checks, not a scientific comparison."""

from copy import deepcopy
import json
import platform
import subprocess
import sys

import pytest
from evonn_shared.engine_evidence import artifact_json, validate_engine_bundle
from evonn_shared.export_reader import read_export
from evonn_shared.topograph_policy import expected_epochs


def invoke(*args):
    return subprocess.run(
        [sys.executable, "-m", "topograph.cli", *map(str, args)], capture_output=True, text=True, timeout=240
    )


@pytest.mark.parametrize("backend", ["numpy_fallback", "mlx_native"])
@pytest.mark.parametrize("variant", ["open", "next"])
def test_research_real_resume_export_replay_and_policy_tamper(tmp_path, backend, variant):
    if backend == "mlx_native" and (platform.system() != "Darwin" or platform.machine() != "arm64"):
        pytest.skip("native MLX requires Apple Silicon")
    interruption = (
        ["--crash-at", "manifest", "--crash-step", 17] if backend == "numpy_fallback" else ["--stop-after", 17]
    )
    first = invoke(
        "run",
        "--variant",
        variant,
        "--pack",
        "tier1_core_smoke",
        "--budget",
        32,
        "--epochs",
        2,
        "--population-size",
        2,
        "--timeout",
        220,
        "--fit-timeout",
        20,
        "--backend",
        backend,
        "--output",
        tmp_path / "runs",
        "--cache",
        tmp_path / "cache",
        *interruption,
    )
    assert first.returncode == (-9 if backend == "numpy_fallback" else 0), first.stderr
    run = next((tmp_path / "runs").iterdir())
    changed = invoke("run", "--resume", run, "--variant", "mechanics")
    assert changed.returncode != 0 and "differs from saved run" in changed.stderr
    if variant == "next":
        changed = invoke("run", "--resume", run, "--research-options", json.dumps({"allocation": "full"}))
        assert changed.returncode != 0 and "differs from saved run" in changed.stderr
    resumed = invoke("run", "--resume", run)
    assert resumed.returncode == 0, resumed.stderr
    bundle = read_export(run / "symbiosis")
    validate_engine_bundle(bundle, verify_cache=True)
    assert bundle.results.coverage.ok == 32
    config = artifact_json(bundle, "config.yaml")
    state = artifact_json(bundle, "state.json")
    telemetry = artifact_json(bundle, "engine_telemetry.json")
    attempts = artifact_json(bundle, "attempts.json")["attempts"]
    assert all(a["genome"]["schema_version"] == 2 for a in attempts)
    assert any(a["proposal"]["actual"] for a in attempts)
    assert all(a["allocated_epochs"] == a["epochs"] for a in attempts if a["proposal"]["protected"])
    assert all(a["inheritance"]["mode"] == "none" for a in attempts if a["proposal"]["fresh"])
    assert telemetry["runtime_profile"]["coordinator"]["worker_roundtrip_seconds"] > 0
    assert telemetry["runtime_profile"]["missing_checkpoint_timings"] == ([17] if backend == "numpy_fallback" else [])
    replay = invoke("replay", run)
    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout)["status"] == "passed"
    forged = deepcopy(attempts[0])
    forged["genome"]["adapter_width"] = 24
    with pytest.raises(ValueError, match="identity"):
        expected_epochs(config, forged, state, telemetry)
    forged = deepcopy(attempts[0])
    forged["proposal"]["fresh"] = False
    with pytest.raises(ValueError, match="durable search"):
        expected_epochs(config, forged, state, telemetry)
    forged = deepcopy(attempts[0])
    forged["ancestral_training"]["updates"] += 1
    with pytest.raises(ValueError, match="ancestral"):
        expected_epochs(config, forged, state, telemetry)
    if variant == "next":
        forged_config = deepcopy(config)
        forged_config["research_options"]["label_smoothing"] = 0.0
        with pytest.raises(ValueError, match="options"):
            expected_epochs(forged_config, attempts[0], state, telemetry)
        forged = deepcopy(attempts[0])
        forged["training_policy"]["patience"] += 1
        with pytest.raises(ValueError, match="training policy"):
            expected_epochs(config, forged, state, telemetry)
        forged = deepcopy(attempts[0])
        forged["selected_epoch"] = forged["epochs"] + 1
        with pytest.raises(ValueError, match="selected checkpoint"):
            expected_epochs(config, forged, state, telemetry)


@pytest.mark.parametrize("adapter", ["query", "mixer"])
def test_next_language_export_and_replay(tmp_path, adapter):
    backend = "mlx_native" if platform.system() == "Darwin" and platform.machine() == "arm64" else "numpy_fallback"
    result = invoke("run", "--variant", "next", "--research-options", json.dumps({"adapters": adapter}),
                    "--pack", "tier_b_core_v2", "--budget", 16, "--epochs", 2,
                    "--timeout", 220, "--fit-timeout", 30, "--backend", backend,
                    "--output", tmp_path / "runs", "--cache", tmp_path / "cache")
    assert result.returncode == 0, result.stderr
    run = next((tmp_path / "runs").iterdir())
    bundle = read_export(run / "symbiosis")
    validate_engine_bundle(bundle, verify_cache=True)
    assert bundle.results.coverage.ok == 16
    attempts = artifact_json(bundle, "attempts.json")["attempts"]
    language = [a for a in attempts if a["benchmark_id"] == "shakespeare_byte_lm"]
    assert language and all(a["genome"]["input_adapter"] == "token_" + adapter for a in language)
    replay = invoke("replay", run)
    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout)["status"] == "passed"


def test_config_research_variant_is_not_dropped(tmp_path, monkeypatch):
    from topograph import cli

    config = tmp_path / "config.yaml"
    config.write_text("variant: training\n")
    calls = []
    monkeypatch.setattr(cli, "run_engine", lambda search, **kwargs: calls.append(kwargs) or tmp_path)
    cli.main(["run", "--config", str(config)])
    assert calls[0]["variant"] == "training"


def test_research_rejects_ignored_legacy_scalars(tmp_path):
    from topograph.run import run_engine
    from topograph.search import Search

    with pytest.raises(ValueError, match="task-local"):
        run_engine(Search, variant="open", novelty_weight=0.5, output_parent=tmp_path)
    assert not list(tmp_path.iterdir())
