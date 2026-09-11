"""Real breadth-policy fits, configuration roundtrip, evidence checks, and replay."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from evonn_shared import engine_evidence
from evonn_shared.export_reader import read_export


def test_breadth_lanes_are_executed_charged_and_exported(tmp_path, monkeypatch):
    config = tmp_path / "breadth.json"
    config.write_text(json.dumps(dict(pack="tier1_core_smoke", budget=96, epochs=2, seed=42,
                                      population_size=4, search_policy="breadth_v2", max_width=32, max_depth=6,
                                      backend=os.environ.get("EVONN_TEST_BACKEND", "numpy_fallback"),
                                      timeout=900, fit_timeout=60)))

    def invoke(*args):
        result = subprocess.run([sys.executable, "-m", "evonn_primordia.cli", *map(str, args)],
                                cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=960)
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    root = Path(invoke("run", "--config", config, "--output", tmp_path / "runs", "--cache", tmp_path / "cache")).parent
    bundle = read_export(root / "symbiosis")
    engine_evidence.validate_engine_bundle(bundle, verify_cache=True)
    trials = engine_evidence.artifact_json(bundle, "trial_records.json")
    assert len(trials) == 96 and all(t["status"] == "ok" and t["charged"] == 1 for t in trials)
    assert all(t["allocated_epochs"] == t["full_epochs"] == 2 and t["inherited_epoch_savings"] == 0 for t in trials)
    for benchmark in {t["benchmark_id"] for t in trials}:
        selected = [t for t in trials if t["benchmark_id"] == benchmark]
        assert {t["proposal"]["lane"] for t in selected} == {
            "founder", "quality", "novelty", "young", "reservoir", "fresh", "patient", "fresh_retrain", "cost"}
        assert all(t["inheritance"]["mode"] == "none" for t in selected if t["proposal"]["fresh"])
    assert all(t["epochs"] == 2 for t in trials if t["proposal"]["lane"] == "patient")
    assert json.loads(invoke("replay", root))["status"] == "passed"
    invoke("run", "--resume", root)  # Finished resume starts no new fits.
    assert len(json.loads((root / "trial_records.json").read_text())) == 96
    rejected = subprocess.run([sys.executable, "-m", "evonn_primordia.cli", "run", "--resume", str(root),
                               "--max-width", "33"], capture_output=True, text=True)
    assert rejected.returncode != 0 and "differs from saved run" in rejected.stderr
    read = engine_evidence.artifact_json
    changed = deepcopy(read(bundle, "seed_candidates.json"))
    changed[0]["encoding"]["format"] = "primordia.primitive/v1"
    with monkeypatch.context() as patch:
        patch.setattr(engine_evidence, "artifact_json", lambda b, name: changed if name == "seed_candidates.json" else read(b, name))
        with pytest.raises(ValueError):
            engine_evidence.validate_engine_bundle(bundle)
