"""Real fit/export integration and negative accounting boundaries."""
import hashlib
import io
import json
import subprocess
import time

import pytest
import numpy as np

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


@pytest.mark.parametrize("timeout", [float("inf"), float("nan"), -1, 1800.01])
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


@pytest.mark.parametrize("error", [FileNotFoundError("git"), subprocess.CalledProcessError(128, "git")])
def test_missing_git_provenance_fails_before_workspace_creation(tmp_path, monkeypatch, error):
    def unavailable(*args, **kwargs):
        raise error
    monkeypatch.setattr(runner.subprocess, "check_output", unavailable)
    with pytest.raises(ValueError, match="Git checkout"):
        runner.run_contenders(pack_name="tier1_core", budget=64, seed=42,
            output_parent=tmp_path / "runs", cache_root=tmp_path / "cache")
    assert not (tmp_path / "runs").exists()


@pytest.mark.parametrize("alpha", [5e-324, 10**400, "bad", None, float("nan"), float("inf"), -float("inf")])
def test_unrepresentable_ngram_alpha_is_invalid_before_fit(tmp_path, alpha):
    from evonn_contenders.worker import evaluate
    from evonn_shared.artifact_io import publish_artifact
    cache = tmp_path / "cache"
    cache.mkdir()
    artifacts = []
    for name, values in {
        "x_train": np.array([[0, 1, 2, 0], [1, 2, 0, 1]], dtype=np.float32),
        "y_train": np.array([1, 2], dtype=np.int64),
        "x_validation": np.array([[2, 0, 1, 2]], dtype=np.float32),
        "y_validation": np.array([0], dtype=np.int64),
    }.items():
        stream = io.BytesIO()
        np.save(stream, values, allow_pickle=False)
        payload = stream.getvalue()
        reference = publish_artifact(cache / f"{name}.npy", payload)
        artifacts.append({**reference.model_dump(mode="json"), "size_bytes": len(payload)})
    # Valid token inputs isolate invalid smoothing and its pre-fit accounting.
    request = {"model": "bigram_lm", "parameters": {"alpha": alpha}, "model_seed": 42,
               "task": "language_modeling", "input_shape": [4], "output_dim": 3,
               "data": {"cache_directory": str(cache), "cache_artifacts": artifacts},
               "attempt_started": str(tmp_path / "started")}
    result = evaluate(request)
    assert result["status"] == "failed" and result["invalid"] == 1 and result["charged"] == 0
    assert "n-gram" in result["reason"]
    assert not (tmp_path / "started").exists()


def test_overflowing_optional_probe_keeps_dataset_and_other_candidates_available(tmp_path, monkeypatch):
    import math
    from evonn_contenders import prepare
    original = prepare.build_model
    def probe(name, **kwargs):
        if name == "overflow_fixture":
            math.isfinite(kwargs["parameters"]["learning_rate"])
        return original(name, **kwargs)
    monkeypatch.setattr(prepare, "build_model", probe)
    result = prepare.prepare({"benchmark": "iris_classification", "seed": 42, "cache_root": str(tmp_path / "cache"),
        "shared_root": str(runner.shared_root()), "enhanced": True,
        "optional": {"bad": {"model": "overflow_fixture", "parameters": {"learning_rate": 10**400}},
                     "good": {"model": "logistic", "parameters": {}}}})
    assert result["status"] == "ok" and result["train_rows"] > 0
    assert result["available_optional"] == ["good"]
    invalid = result["optional_results"]["bad"]
    assert invalid["status"] == "failed" and invalid["invalid"] == 1 and invalid["charged"] == 0


def test_external_estimator_without_sklearn_constraints_and_custom_validator():
    from sklearn.base import BaseEstimator
    from sklearn.ensemble import ExtraTreesClassifier
    from sklearn.pipeline import Pipeline
    from evonn_contenders.worker import _validate_parameters
    class ExternalEstimator(BaseEstimator):
        pass
    # The inherited private sklearn helper is unusable for this valid protocol.
    with pytest.raises(AttributeError):ExternalEstimator()._validate_params()
    _validate_parameters(ExternalEstimator())
    class ExplicitValidator(ExternalEstimator):
        def _validate_params(self):
            raise ValueError('external validation retained')
    with pytest.raises(ValueError,match='external validation retained'):
        _validate_parameters(ExplicitValidator())
    with pytest.raises(ValueError):
        _validate_parameters(Pipeline([('estimator',ExtraTreesClassifier(n_estimators=-1))]))
