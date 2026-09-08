"""Real fits across a killed process boundary; no synthetic score substitution."""

from copy import deepcopy
import os
import hashlib
import json
from pathlib import Path
import shutil
import signal
import subprocess
import sys

import pytest
from evonn_shared.checkpoints import load_latest_checkpoint
from evonn_shared.export_reader import read_export
from evonn_shared.run_store import open_run_reader
from evonn_shared import engine_evidence
from evonn_compare.cases import Case, evaluate_case
from evonn_compare.evidence import trend_rows
from evonn_compare.quality import classify

REPO = Path(__file__).resolve().parents[2]


def invoke(system, *arguments):
    return subprocess.run(
        [sys.executable, "-m", ("evonn_primordia" if system == "primordia" else system) + ".cli", *map(str, arguments)],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=240,
    )


def clone_prefix(source, parent):
    parent.mkdir()
    target = parent / source.name
    shutil.copytree(source, target)
    return target


def state(root):
    _, payload = load_latest_checkpoint(root / "checkpoints")
    return json.loads(payload)


@pytest.mark.parametrize("system", ["prism", "topograph", "stratograph", "primordia"])
def test_real_resume_kill_boundaries_export_and_report(system, tmp_path, monkeypatch):
    result = invoke(
        system,
        "evolve",
        "--pack",
        "tier1_core_smoke",
        "--budget",
        8,
        "--population-size",
        2,
        "--epochs",
        2,
        "--timeout",
        220,
        "--fit-timeout",
        20,
        "--backend",
        os.environ.get("EVONN_TEST_BACKEND", "numpy_fallback"),
        "--output",
        tmp_path / "prefix",
        "--cache",
        tmp_path / "cache",
        "--stop-after",
        7,
    )
    assert result.returncode == 0, result.stderr
    prefix = Path(result.stdout.strip().splitlines()[-1])
    original_rows = None
    with open_run_reader(prefix, prefix.name) as reader:
        original_rows = reader.evaluations()
    baseline = clone_prefix(prefix, tmp_path / "baseline")
    completed = invoke(system, "evolve", "--resume", baseline)
    assert completed.returncode == 0, completed.stderr
    expected = state(baseline)
    bundle = read_export(baseline / "symbiosis")
    engine_evidence.validate_engine_bundle(bundle, verify_cache=True)
    if system in {"stratograph", "primordia"}:
        _phase4_artifact_checks(system, baseline, bundle, monkeypatch)
    hidden_cache = tmp_path / "cache_hidden"
    (tmp_path / "cache").rename(hidden_cache)
    try:
        engine_evidence.validate_engine_bundle(bundle, verify_cache=True)
        replayed = invoke(system, "replay", baseline)
        assert replayed.returncode == 0, replayed.stderr
    finally:
        hidden_cache.rename(tmp_path / "cache")
    acceptance = evaluate_case(Case("tier1_core_smoke", 8, 42), [bundle], no_contenders=True)
    assert acceptance["operating_state"] == "contract-fair", acceptance
    propagated = trend_rows(bundle, "real_fixture", acceptance)
    assert all(row["inheritance"] is not None and row["latency_seconds"] is not None for row in propagated)
    assert classify(bundle.root, propagated=True)["level"] == "L3"
    reader = engine_evidence.artifact_json
    documents = {
        name: reader(bundle, name)
        for name in ("config.yaml", "state.json", "attempts.json", "engine_telemetry.json", "dataset_provenance.json")
    }
    for attack in (
        "empty_telemetry",
        "false_raw",
        "boolean_charge",
        "false_measurement",
        "false_dataset_digest",
        "fake_cache_credits",
    ):
        altered = deepcopy(documents)
        if attack == "empty_telemetry":
            for key in engine_evidence.MANDATORY_TELEMETRY[system]:
                altered["engine_telemetry.json"][key] = None
        elif attack == "false_raw":
            altered["dataset_provenance.json"][0]["raw_sha256"] = "0" * 64
        elif attack == "false_dataset_digest":
            altered["state.json"]["dataset_sha256"] = "0" * 64
        elif attack == "fake_cache_credits":
            altered["attempts.json"]["accounting"]["cached_evaluations"] += 1
        else:
            key, value = ("charged", True) if attack == "boolean_charge" else ("model_bytes", 0)
            altered["attempts.json"]["attempts"][0][key] = value
            altered["state.json"]["attempts"][0][key] = value
        with monkeypatch.context() as patched:
            patched.setattr(
                engine_evidence,
                "artifact_json",
                lambda current, name: altered[name] if name in altered else reader(current, name),
            )
            with pytest.raises((ValueError, TypeError, KeyError)):
                engine_evidence.validate_engine_bundle(bundle, verify_cache=True)
    for boundary in ("worker", "transaction", "row", "stage", "payload", "manifest"):
        root = clone_prefix(prefix, tmp_path / boundary)
        killed = invoke(system, "evolve", "--resume", root, "--crash-at", boundary, "--crash-step", 8)
        assert killed.returncode == -signal.SIGKILL, (boundary, killed.stderr)
        resumed = invoke(system, "evolve", "--resume", root)
        assert resumed.returncode == 0, (boundary, resumed.stderr)
        actual = state(root)
        assert actual["search"] == expected["search"]
        assert actual["tip"] == expected["tip"]
        assert [a["metric_value"] for a in actual["attempts"]] == [a["metric_value"] for a in expected["attempts"]]
        with open_run_reader(root, root.name) as reader:
            assert reader.evaluations()[:7] == original_rows
        bundle = read_export(root / "symbiosis")
        assert bundle.manifest.status.value == "completed"
        assert bundle.manifest.accounting.actual_evaluations + bundle.manifest.accounting.cached_evaluations == 8
        before = hashlib.sha256((root / "report.md").read_bytes()).hexdigest()
        rebuilt = invoke(system, "report", root)
        assert rebuilt.returncode == 0, rebuilt.stderr
        assert hashlib.sha256((root / "report.md").read_bytes()).hexdigest() == before
        again = invoke(system, "symbiosis-export", root)
        assert again.returncode == 0, again.stderr
    drift = invoke(system, "evolve", "--resume", baseline, "--seed", 99)
    assert drift.returncode != 0 and "differs" in drift.stderr


@pytest.mark.parametrize("system", ["prism", "topograph", "stratograph", "primordia"])
def test_resume_after_reproduction_and_trained_inheritance(system, tmp_path):
    result = invoke(
        system,
        "evolve",
        "--pack",
        "tier1_core_smoke",
        "--budget",
        32,
        "--population-size",
        2,
        "--epochs",
        2,
        "--timeout",
        600,
        "--fit-timeout",
        20,
        "--backend",
        os.environ.get("EVONN_TEST_BACKEND", "numpy_fallback"),
        "--output",
        tmp_path / "prefix",
        "--cache",
        tmp_path / "cache",
        "--stop-after",
        17,
    )
    assert result.returncode == 0, result.stderr
    prefix = Path(result.stdout.strip().splitlines()[-1])
    checkpoint = state(prefix)
    assert all(v["generation"] >= 1 for v in checkpoint["search"]["benchmarks"].values())
    assert any(a["inheritance"]["mode"] != "none" for a in checkpoint["attempts"])
    baseline = clone_prefix(prefix, tmp_path / "baseline")
    finished = invoke(system, "evolve", "--resume", baseline)
    assert finished.returncode == 0, finished.stderr
    interrupted = clone_prefix(prefix, tmp_path / "interrupted")
    killed = invoke(system, "evolve", "--resume", interrupted, "--crash-at", "transaction", "--crash-step", 18)
    assert killed.returncode == -signal.SIGKILL, killed.stderr
    resumed = invoke(system, "evolve", "--resume", interrupted)
    assert resumed.returncode == 0, resumed.stderr
    expected, actual = state(baseline), state(interrupted)
    assert actual["search"] == expected["search"]
    assert actual["tip"] == expected["tip"]
    assert [a["metric_value"] for a in actual["attempts"]] == [a["metric_value"] for a in expected["attempts"]]
    assert any(a["inheritance"]["mode"] != "none" for a in actual["attempts"])
    engine_evidence.validate_engine_bundle(read_export(interrupted / "symbiosis"), verify_cache=True)


def _phase4_artifact_checks(system,root,bundle,monkeypatch):
    reader=engine_evidence.artifact_json
    names=("motif_analysis.json","lm_diagnostics.json") if system=="stratograph" else ("seed_candidates.json","primitive_bank.json","search_leaders.json")
    original={name:reader(bundle,name) for name in names}
    attacks=["motif","lm"] if system=="stratograph" else ["empty","quality","source","genome","bank","leaders"]
    for attack in attacks:
        changed=deepcopy(original)
        if attack=="motif":
            changed["motif_analysis.json"]["global_frequency"]={"invented":99999}
        elif attack=="lm":
            changed["lm_diagnostics.json"]=[{"native_transfer_proven":True,"broad_claim_ready":True}]
        elif attack=="empty":
            changed["seed_candidates.json"]=[]
        elif attack in {"quality","source","genome"}:
            from evonn_shared.seed_artifact import seal_seed
            payload=changed["seed_candidates.json"][0]
            del payload["checksum"]
            if attack=="quality":
                payload["quality"]["value"]=99999.
            elif attack=="source":
                payload["source"]["seed"]+=1
            else:
                payload["encoding"]["genome"]["width"]+=1
            changed["seed_candidates.json"][0]=seal_seed(payload)
        elif attack=="bank":
            changed["primitive_bank.json"]["entries"]=[]
        else:
            changed["search_leaders.json"]["benchmarks"]={}
        with monkeypatch.context() as patched:
            patched.setattr(engine_evidence,"artifact_json",lambda current,name:changed[name] if name in changed else reader(current,name))
            with pytest.raises(ValueError):
                engine_evidence.validate_engine_bundle(bundle)
    if system=="primordia":
        bank=root/"primitive_bank.json"
        expected=bank.read_bytes()
        bank.unlink()
        rebuilt=invoke(system,"inspect",root)
        assert rebuilt.returncode==0,rebuilt.stderr
        assert bank.read_bytes()==expected
        context=root/"bank_context.json"
        saved=context.read_bytes()
        payload=json.loads(saved)
        payload["config"]["seed"]+=1
        context.write_text(json.dumps(payload))
        try:
            rejected=invoke(system,"inspect",root)
            assert rejected.returncode!=0 and "differs from immutable export" in rejected.stderr
        finally:
            context.write_bytes(saved)
