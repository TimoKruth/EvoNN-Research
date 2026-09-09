"""One isolated, timeout-bounded contender fit/evaluation process."""
from __future__ import annotations

import io
import importlib.metadata
import json
import math
from pathlib import Path
import pickle
import resource
import sys
import time
import warnings

import numpy as np
from sklearn.base import BaseEstimator
from sklearn.metrics import accuracy_score, mean_squared_error
from threadpoolctl import threadpool_limits

from evonn_shared.artifact_io import publish_artifact, read_verified_artifact
from evonn_shared.telemetry import ArtifactReference
from .models import OptionalContenderUnavailable, build_model


def _validate_parameters(model):
    if hasattr(model, "_validate_params"):
        # XGBoost/LightGBM inherit BaseEstimator's private helper without
        # sklearn's constraint metadata. Their own fit validates parameters.
        # Keep sklearn constraints and explicit third-party validators active.
        inherited_helper = getattr(type(model), "_validate_params", None) is BaseEstimator._validate_params
        if not inherited_helper or hasattr(model, "_parameter_constraints"):
            model._validate_params()
    if hasattr(model, "steps"):
        for _, step in model.steps:
            _validate_parameters(step)


def backend_provenance(name):
    package = {"xgboost": "xgboost", "lightgbm": "lightgbm", "catboost": "catboost",
               "cnn_small": "torch", "transformer_lm_tiny": "torch"}
    distribution = package[name] if name in package else "scikit-learn"
    if name.endswith("gram_lm"):
        distribution = "evonn-contenders"
    return {"package": distribution, "version": importlib.metadata.version(distribution), "device": "cpu"}



def evaluate(request: dict) -> dict:
    """Only fit receives training labels; metric computation receives held-out labels."""
    arrays = {}
    for item in request["data"]["cache_artifacts"]:
        reference = ArtifactReference(path=item["path"], sha256=item["sha256"])
        payload = read_verified_artifact(Path(request["data"]["cache_directory"]), reference,
                                         size_bytes=item["size_bytes"])
        arrays[Path(item["path"]).stem] = np.load(io.BytesIO(payload), allow_pickle=False)
    try:
        if request["task"] == "language_modeling":
            for name in ("x_train", "x_validation"):
                value=arrays[name]
                if not np.isfinite(value).all() or np.any(value!=np.floor(value)) or np.any(value<0) or np.any(value>=request["output_dim"]):
                    raise ValueError("invalid integer token context")
                arrays[name]=value.astype(np.int64)
        model = build_model(request["model"], task=request["task"], seed=request["model_seed"],
                            input_shape=tuple(request["input_shape"]), output_dim=request["output_dim"],
                            train_rows=len(arrays["x_train"]), parameters=request["parameters"])
        _validate_parameters(model)
        backend = backend_provenance(request["model"])
    except OptionalContenderUnavailable as error:
        return {"status": "skipped", "reason": str(error), "charged": 0, "invalid": 0}
    except (ValueError, TypeError, OverflowError) as error:
        return {"status": "failed", "reason": f"invalid configuration: {error}", "charged": 0, "invalid": 1}
    publish_artifact(Path(request["attempt_started"]), b"fit/eval attempt charged\n")
    started = time.monotonic()
    try:
        with warnings.catch_warnings(record=True) as recorded, threadpool_limits(limits=1):
            warnings.simplefilter("always")
            model.fit(arrays["x_train"], arrays["y_train"])
            train_seconds = time.monotonic() - started
            if request["metric"] == "perplexity":
                score = model.perplexity(arrays["x_validation"], arrays["y_validation"])
            else:
                prediction = model.predict(arrays["x_validation"])
                if request["metric"] == "accuracy":
                    score = float(accuracy_score(arrays["y_validation"], prediction))
                elif request["metric"] == "mse":
                    score = float(mean_squared_error(arrays["y_validation"], prediction))
                else:
                    raise ValueError("unknown declared metric")
            if not math.isfinite(score):
                raise ValueError("nonfinite evaluation metric")
        payload = pickle.dumps(model, protocol=5)
        if len(payload) > 256 * 1024 * 1024:
            raise ValueError("serialized contender exceeds artifact limit")
        model_reference = publish_artifact(Path(request["model_output"]), payload)
        estimator = model.steps[-1][1] if hasattr(model, "steps") else model
        parameter_count = None
        if hasattr(estimator, "coefs_"):
            parameter_count = sum(int(array.size) for array in (*estimator.coefs_, *estimator.intercepts_))
        elif hasattr(estimator, "coef_"):
            parameter_count = int(estimator.coef_.size + np.asarray(estimator.intercept_).size)
        elif getattr(estimator, "model", None) is not None:
            parameter_count = sum(parameter.numel() for parameter in estimator.model.parameters())
        usage = resource.getrusage(resource.RUSAGE_SELF)
        iterations = getattr(estimator, "n_iter_", getattr(estimator, "n_estimators", getattr(estimator, "epochs", None)))
        if iterations is not None:
            iterations = int(np.max(iterations))
        return {
            "status": "ok", "reason": None, "charged": 1, "invalid": 0, "score": score, "backend": backend,
            "train_seconds": train_seconds, "model_bytes": len(payload), "parameter_count": parameter_count,
            "peak_memory_bytes": int(usage.ru_maxrss * (1 if sys.platform == "darwin" else 1024)),
            "memory_scope": "isolated worker process peak RSS, including interpreter and imported libraries",
            "training_iterations_or_trees": iterations, "training_rows": len(arrays["x_train"]),
            "warnings": sorted({str(item.message) for item in recorded}),
            "model_artifact": model_reference.model_dump(mode="json"),
        }
    except Exception as error:
        return {"status": "failed", "reason": f"fit/evaluation failed: {type(error).__name__}: {error}",
                "charged": 1, "invalid": 0, "train_seconds": time.monotonic() - started}


def main() -> int:
    request_path, output_path = map(Path, sys.argv[1:])
    request = json.loads(request_path.read_text())
    result = evaluate(request)
    publish_artifact(output_path, (json.dumps(result, sort_keys=True, allow_nan=False) + "\n").encode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
