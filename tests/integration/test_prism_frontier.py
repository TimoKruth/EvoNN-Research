"""Real frontier fits, interrupted recovery, portable exports and saved replay."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from evonn_shared.engine_evidence import artifact_json, validate_engine_bundle
from evonn_shared.export_reader import read_export


ROOT = Path(__file__).resolve().parents[2]


def invoke(*args):
    result = subprocess.run([sys.executable, "-m", "prism.cli", *map(str, args)], cwd=ROOT,
                            text=True, capture_output=True, timeout=240)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_frontier_recovers_at_transaction_boundary_and_replays(tmp_path):
    root = Path(invoke("run", "--variant", "frontier_v2", "--pack", "tier1_core_smoke",
                       "--budget", 8, "--epochs", 2, "--population-size", 2, "--stop-after", 7,
                       "--optimizer-policy", "continue", "--optimizer-backend", "native",
                       "--timeout", 220, "--fit-timeout", 30,
                       "--backend", os.environ.get("EVONN_TEST_BACKEND", "numpy_fallback"),
                       "--output", tmp_path / "prefix", "--cache", tmp_path / "cache"))
    control = tmp_path / "control" / root.name
    shutil.copytree(root, control)
    invoke("run", "--resume", control)
    failed = subprocess.run([sys.executable, "-m", "prism.cli", "run", "--resume", str(root),
                             "--crash-at", "transaction", "--crash-step", "8"], cwd=ROOT,
                            text=True, capture_output=True, timeout=240)
    assert failed.returncode < 0, failed.stderr
    invoke("run", "--resume", root)
    bundles = [read_export(path / "symbiosis") for path in (control, root)]
    attempts = []
    for bundle in bundles:
        validate_engine_bundle(bundle, verify_cache=True)
        rows = artifact_json(bundle, "attempts.json")["attempts"]
        assert len(rows) == 8 and all(row["status"] == "ok" for row in rows)
        assert all(row["ema_decay"] == .9 and row["decay_policy"] == "matrix" for row in rows)
        assert any(row["selection_metric"] == "calibrated_mse" for row in rows)
        attempts.append([(r["genome_id"], r["score"], r["updates"], r["selected_weight_source"]) for r in rows])
        assert json.loads(invoke("research-report", bundle.root))["benchmarks"]
        invoke("replay", bundle.root.parent)
    assert attempts[0] == attempts[1]
