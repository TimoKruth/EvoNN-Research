"""Real fit/export integration and negative accounting boundaries."""
import hashlib
import json
import subprocess
import time

import pytest

from evonn_contenders import runner
from evonn_shared.export_reader import read_export


def test_real_isolated_fit_portable_export_and_missing_data_accounting(tmp_path, monkeypatch):
    original = runner._prepare
    def one_dataset(request, directory, deadline):
        if request["benchmark"] != "iris_classification":
            raise OSError("deliberately unavailable fixture source")
        return original(request, directory, deadline)
    monkeypatch.setattr(runner, "_prepare", one_dataset)
    exported = runner.run_contenders(pack_name="tier1_core_smoke", budget=8, seed=42,
        output_parent=tmp_path / "runs", cache_root=tmp_path / "cache", timeout=30, fit_timeout=20)
    before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in exported.iterdir()}
    bundle = read_export(exported)
    assert bundle.manifest.status.value == "failed"
    assert bundle.manifest.accounting.actual_evaluations == 1
    assert bundle.manifest.accounting.failed_evaluations == 0
    assert bundle.manifest.accounting.partial_run
    assert len(bundle.summary.best_per_benchmark) == 1
    assert bundle.summary.best_per_benchmark[0].value >= .85
    assert bundle.results.coverage.failed == 7
    ledger = json.loads((exported / "attempts.json").read_text())
    assert sum(item["charged"] for item in ledger["attempts"]) == 1
    assert all("model_artifact" not in item for item in ledger["attempts"])
    assert before == {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in exported.iterdir()}
    (exported / "attempts.json").write_text("{}")
    with pytest.raises(ValueError, match="content mismatch"):
        read_export(exported)


@pytest.mark.parametrize("started,charged", [(False, 0), (True, 1)])
def test_worker_timeout_charges_only_started_fit(tmp_path, monkeypatch, started, charged):
    marker = tmp_path / "started"
    if started:
        marker.write_bytes(b"started")
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("worker", 1, output=b"diagnostic")
    monkeypatch.setattr(runner.subprocess, "run", timeout)
    result = runner._worker({"attempt_started": str(marker)}, tmp_path, time.monotonic() + 5, 1)
    assert result["status"] == "failed" and result["charged"] == charged
    assert (tmp_path / "worker.log").read_bytes() == b"diagnostic"


@pytest.mark.parametrize("timeout", [float("inf"), float("nan"), -1])
def test_nonfinite_or_nonpositive_limits_fail_before_creating_run(tmp_path, timeout):
    with pytest.raises(ValueError, match="time limits"):
        runner.run_contenders(pack_name="tier1_core", budget=64, seed=42,
            output_parent=tmp_path / "runs", cache_root=tmp_path / "cache", timeout=timeout)
    assert not (tmp_path / "runs").exists()


def test_preparation_deadline_covers_loader_process(tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        assert kwargs["timeout"] < .2
        raise subprocess.TimeoutExpired("prepare", .1)
    monkeypatch.setattr(runner.subprocess, "run", timeout)
    with pytest.raises(ValueError, match="preparation.*time limit"):
        runner._prepare({}, tmp_path, time.monotonic() + .1)
    with pytest.raises(ValueError, match="before data preparation"):
        runner._prepare({}, tmp_path / "unused", time.monotonic() - 1)
    assert not (tmp_path / "unused").exists()


def test_invalid_sklearn_parameters_do_not_start_or_charge_fit(tmp_path):
    from evonn_contenders.datasets import load_dataset
    from evonn_contenders.worker import evaluate, backend_provenance
    data = load_dataset("iris_classification", seed=42, cache_root=tmp_path / "cache")
    request = {"model": "extra_trees", "parameters": {"n_estimators": 0}, "model_seed": 42,
               "task": "classification", "input_shape": [4], "output_dim": 3,
               "data": data.provenance, "attempt_started": str(tmp_path / "started")}
    result = evaluate(request)
    assert result["status"] == "failed" and result["invalid"] == 1 and result["charged"] == 0
    assert not (tmp_path / "started").exists()
    assert backend_provenance("extra_trees") == {"package": "scikit-learn", "version": "1.8.0", "device": "cpu"}
