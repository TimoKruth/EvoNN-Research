"""Fixed baseline models; scaling is fitted on training rows only."""
from __future__ import annotations

from collections import Counter, defaultdict
import math

import numpy as np
from sklearn.ensemble import (
    ExtraTreesClassifier, ExtraTreesRegressor, HistGradientBoostingClassifier,
    HistGradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor,
)
from sklearn.kernel_approximation import Nystroem
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC, LinearSVR, SVC, SVR


class OptionalContenderUnavailable(RuntimeError):
    pass


class NGram:
    """Smoothed next-token counts, with no access to evaluation labels at fit."""
    def __init__(self, *, order: int = 2, alpha: float = 1.0, vocabulary_size: int = 256):
        if order not in (1, 2, 3) or not math.isfinite(alpha) or alpha <= 0 or vocabulary_size < 2:
            raise ValueError("invalid n-gram configuration")
        self.order, self.alpha, self.vocabulary_size = order, alpha, vocabulary_size
        self.counts = defaultdict(Counter)

    def _contexts(self, x):
        x = np.asarray(x)
        if x.ndim != 2 or x.shape[1] < self.order - 1 or x.dtype.kind not in "iu":
            raise ValueError("n-gram input must be integer context rows")
        if np.any(x < 0) or np.any(x >= self.vocabulary_size):
            raise ValueError("token outside declared vocabulary")
        return [tuple(row[-(self.order - 1):]) if self.order > 1 else () for row in x]

    def fit(self, x, y):
        contexts = self._contexts(x)
        y = np.asarray(y)
        if y.shape != (len(contexts),) or y.dtype.kind not in "iu" or np.any(y < 0) or np.any(y >= self.vocabulary_size):
            raise ValueError("one valid next-token target is required per context")
        self.counts.clear()
        for context, target in zip(contexts, y, strict=True):
            self.counts[context][int(target)] += 1
        return self

    def predict_proba(self, x):
        probabilities = []
        for context in self._contexts(x):
            counts = self.counts[context] if context in self.counts else {}
            # Scale before addition/summation to keep every finite alpha valid.
            scale = max(self.alpha, max(counts.values(), default=1))
            row = np.full(self.vocabulary_size, self.alpha / scale, dtype=np.float64)
            for token, count in counts.items():
                row[token] += count / scale
            probabilities.append(row / row.sum())
        return np.asarray(probabilities)

    def perplexity(self, x, y):
        probabilities = self.predict_proba(x)
        targets = np.asarray(y)
        if targets.shape != (len(probabilities),) or targets.dtype.kind not in "iu" or not len(targets):
            raise ValueError("one held-out token is required per context")
        if np.any(targets < 0) or np.any(targets >= self.vocabulary_size):
            raise ValueError("token outside declared vocabulary")
        return float(np.exp(-np.log(probabilities[np.arange(len(targets)), targets]).mean()))


def build_model(name: str, *, task: str, seed: int, input_shape: tuple[int, ...],
                train_rows: int, output_dim: int, parameters: dict | None = None):
    """Construct a model without inspecting any held-out values."""
    params = dict(parameters or {})
    if set(params) & {"random_state", "random_seed", "seed", "n_jobs", "thread_count", "nthread", "num_threads", "num_thread", "nthreads",
                      "device", "device_type", "task_type", "gpu_id", "gpu_device_id", "predictor", "tree_method", "allow_writing_files", "train_dir", "save_snapshot", "snapshot_file"}:
        raise ValueError("seed, device, worker and file output controls are owned by the run protocol")
    regression = task == "regression"
    if name in ("unigram_lm", "bigram_lm", "trigram_lm"):
        if task != "language_modeling":
            raise ValueError("n-gram requires language_modeling")
        order = {"unigram_lm": 1, "bigram_lm": 2, "trigram_lm": 3}[name]
        return NGram(order=order, vocabulary_size=output_dim, **params)
    if name in ("cnn_small", "transformer_lm_tiny"):
        try:
            from .torch_models import TorchFloor
            return TorchFloor(name, input_shape=input_shape, output_dim=output_dim, seed=seed, **params)
        except (ImportError, OSError) as error:
            raise OptionalContenderUnavailable(f"torch extra unavailable: {error}") from error
    if task not in ("classification", "regression"):
        raise ValueError(f"{name} does not support {task}")
    if name in ("extra_trees", "random_forest"):
        model_type = ((ExtraTreesRegressor if regression else ExtraTreesClassifier) if name == "extra_trees"
                      else (RandomForestRegressor if regression else RandomForestClassifier))
        return model_type(**{"n_estimators": 256, "random_state": seed, "n_jobs": 1, **params})
    if name == "hist_gb":
        return (HistGradientBoostingRegressor if regression else HistGradientBoostingClassifier)(
            **{"random_state": seed, **params})
    if name == "mlp_wide":
        return make_pipeline(StandardScaler(), (MLPRegressor if regression else MLPClassifier)(
            **{"hidden_layer_sizes": (256, 128), "max_iter": 180, "early_stopping": True,
               "random_state": seed, **params}))
    if name == "logistic":
        if regression:
            raise ValueError("logistic is classification-only")
        return make_pipeline(StandardScaler(), LogisticRegression(**{"max_iter": 500, "random_state": seed, **params}))
    if name == "ridge_or_linear":
        if not regression:
            raise ValueError("ridge_or_linear is regression-only")
        return make_pipeline(StandardScaler(), Ridge(**params))
    if name == "linear_svc":
        if regression:
            raise ValueError("linear_svc is classification-only")
        return make_pipeline(StandardScaler(), LinearSVC(**{"max_iter": 4000, "random_state": seed, **params}))
    if name in ("svm_nystroem_rbf", "svr_or_nystroem_svr"):
        components = min(256, max(32, int(np.prod(input_shape)) * 4), train_rows)
        final = LinearSVR if regression else LinearSVC
        return make_pipeline(StandardScaler(), Nystroem(kernel="rbf", gamma=0.5,
                             n_components=components, random_state=seed),
                             final(**{"C": 1.0, "max_iter": 4000, "random_state": seed, **params}))
    if name == "rbf_svm":
        return make_pipeline(StandardScaler(), (SVR if regression else SVC)(**{"C": 2.0, **params}))
    try:
        if name == "xgboost":
            from xgboost import XGBClassifier, XGBRegressor
            return (XGBRegressor if regression else XGBClassifier)(
                **{"n_estimators": 160, "max_depth": 6, "learning_rate": 0.05, "subsample": 0.9,
                   "colsample_bytree": 0.9, "n_jobs": 1, "random_state": seed, **params})
        if name == "lightgbm":
            from lightgbm import LGBMClassifier, LGBMRegressor
            return (LGBMRegressor if regression else LGBMClassifier)(
                **{"n_estimators": 160, "num_leaves": 63, "learning_rate": 0.05,
                   "n_jobs": 1, "random_state": seed, "verbosity": -1, **params})
        if name == "catboost":
            from catboost import CatBoostClassifier, CatBoostRegressor
            return (CatBoostRegressor if regression else CatBoostClassifier)(
                **{"iterations": 160, "depth": 6, "learning_rate": 0.05, "thread_count": 1,
                   "random_seed": seed, "verbose": False, "allow_writing_files": False, **params})
    except (ImportError, OSError) as error:
        raise OptionalContenderUnavailable(f"boosted extra unavailable for {name}: {error}") from error
    raise ValueError(f"Unknown contender: {name}")
