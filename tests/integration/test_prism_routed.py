"""Post-study policies run, recover, validate and replay through the real CLI."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from evonn_shared import engine_evidence as evidence
from evonn_shared.export_reader import read_export
from evonn_shared.prism_policy import V3_VARIANTS, prism_policy_flags
from evonn_shared.active_catalog import get_benchmark


def invoke(*args):
    p = subprocess.run([sys.executable, "-m", "prism.cli", *map(str, args)], text=True, capture_output=True, timeout=240)
    assert p.returncode == 0, p.stdout + p.stderr
    return p.stdout.strip()


@pytest.mark.parametrize("variant", V3_VARIANTS)
def test_routed_variants_export_and_replay(tmp_path, variant, monkeypatch):
    recovery = variant == "aligned_v3"
    root = Path(invoke("run", "--variant", variant, "--pack", "tier1_core_smoke",
                       "--budget", 32 if recovery else 8, "--epochs", 2, "--population-size", 2,
                       "--stop-after", 31 if recovery else 8,
                       "--optimizer-policy", "continue", "--optimizer-backend", "native",
                       "--timeout", 220, "--fit-timeout", 30,
                       "--backend", os.environ.get("EVONN_TEST_BACKEND", "numpy_fallback"),
                       "--output", tmp_path / "runs", "--cache", tmp_path / "cache"))
    if recovery:
        control = tmp_path / "control" / root.name
        shutil.copytree(root, control)
        invoke("run", "--resume", control)
        failed = subprocess.run([sys.executable, "-m", "prism.cli", "run", "--resume", str(root),
                                 "--crash-at", "transaction", "--crash-step", "32"],
                                text=True, capture_output=True, timeout=240)
        assert failed.returncode < 0, failed.stderr
        invoke("run", "--resume", root)
        bundle = read_export(root / "symbiosis")
        a = evidence.artifact_json(bundle, "attempts.json")["attempts"]
        b = evidence.artifact_json(read_export(control / "symbiosis"), "attempts.json")["attempts"]
        assert [(r["genome_id"], r["score"], r["updates"]) for r in a] == [(r["genome_id"], r["score"], r["updates"]) for r in b]
    else:
        bundle = read_export(root)
    evidence.validate_engine_bundle(bundle, verify_cache=True)
    rows = evidence.artifact_json(bundle, "attempts.json")["attempts"]
    assert len(rows) == (32 if recovery else 8) and all(r["status"] == "ok" for r in rows)
    for row in rows:
        assert row["resolved_policy"] == prism_policy_flags(variant, task=get_benchmark(row["benchmark_id"]).task_kind.value)
    if recovery:
        assert any(r["selection_metric"] == "classification_error" for r in rows)
        assert any(r["inheritance"]["mode"] != "none" for r in rows)
    assert json.loads(invoke("research-report", bundle.root))["benchmarks"]
    invoke("replay", bundle.root.parent)
    # Re-signed/consistent JSON still must not be able to claim another policy.
    original = evidence.artifact_json
    docs = {name: deepcopy(original(bundle, name)) for name in ("state.json", "attempts.json")}
    docs["attempts.json"]["attempts"][0]["resolved_policy"]["archive"] ^= True
    docs["state.json"]["attempts"] = deepcopy(docs["attempts.json"]["attempts"])
    monkeypatch.setattr(evidence, "artifact_json", lambda b, n: docs[n] if n in docs else original(b, n))
    with pytest.raises(ValueError, match="resolved task policy"):
        evidence.validate_engine_bundle(bundle)
