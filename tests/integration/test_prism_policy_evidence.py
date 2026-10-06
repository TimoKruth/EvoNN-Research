"""Export validation must recognize frontier training without weakening checks."""

from copy import deepcopy
import os
from pathlib import Path
import subprocess
import sys

import pytest

from evonn_shared import engine_evidence as evidence
from evonn_shared.export_reader import read_export


VARIANTS = ("search_v2", "representation_v2", "regularized_v2", "averaged_v2",
            "calibrated_v2", "frontier_v2")


@pytest.fixture(scope="module")
def exported_search(tmp_path_factory):
    root = tmp_path_factory.mktemp("prism-policy-evidence")
    result = subprocess.run([
        sys.executable, "-m", "prism.cli", "run", "--variant", "search_v2",
        "--pack", "tier1_core_smoke", "--budget", "32", "--epochs", "4",
        "--population-size", "2", "--seed", "21600", "--timeout", "220",
        "--fit-timeout", "30", "--backend", os.environ.get("EVONN_TEST_BACKEND", "numpy_fallback"),
        "--output", str(root / "runs"), "--cache", str(root / "cache"),
    ], text=True, capture_output=True, timeout=240)
    assert result.returncode == 0, result.stderr
    bundle = read_export(Path(result.stdout.strip()))
    evidence.validate_engine_bundle(bundle, verify_cache=True)
    attempts = evidence.artifact_json(bundle, "attempts.json")["attempts"]
    assert all(row["status"] == "ok" for row in attempts)
    assert any(row["proposal"]["protected"] and row["inheritance"]["mode"] != "none" for row in attempts)
    return bundle


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("corruption", [None, "discount_protected", "inherit_fresh"])
def test_frontier_policy_validation(exported_search, monkeypatch, variant, corruption):
    bundle = exported_search
    original = evidence.artifact_json
    documents = {name: deepcopy(original(bundle, name)) for name in (
        bundle.manifest.config_snapshot.path, "state.json", "attempts.json", "engine_telemetry.json")}
    config = documents[bundle.manifest.config_snapshot.path]
    state = documents["state.json"]
    config["variant"] = state["config"]["variant"] = variant
    state["search"]["variant"] = variant
    documents["engine_telemetry.json"]["research_variant"] = variant
    attempts = documents["attempts.json"]["attempts"]
    if corruption == "discount_protected":
        row = next(r for r in attempts if r["proposal"]["protected"] and r["inheritance"]["mode"] != "none")
        row["allocated_epochs"] = 1
    elif corruption == "inherit_fresh":
        row = next(r for r in attempts if r["proposal"]["origin"] in {"initial", "fresh"})
        row["inheritance"]["mode"] = "exact"
        documents["engine_telemetry.json"]["inheritance"]["uses"] += 1
    state["attempts"] = deepcopy(attempts)
    monkeypatch.setattr(evidence, "artifact_json", lambda b, name: documents[name] if name in documents else original(b, name))
    if corruption is None:
        evidence.validate_engine_bundle(bundle)
    else:
        message = "inheritance ratio" if corruption == "discount_protected" else "fresh exploration inherited"
        with pytest.raises(ValueError, match=message):
            evidence.validate_engine_bundle(bundle)
