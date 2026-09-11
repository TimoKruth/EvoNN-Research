"""Package-local differentiated optimizer and evaluation runtime."""

from dataclasses import dataclass
from copy import deepcopy
import math
import time
import numpy as np
from evonn_shared.training import (
    regression_target_stats,
    standardize_regression_targets,
    restore_regression_predictions,
    calibrate_regression_predictions,
)


@dataclass(frozen=True)
class TrainConfig:
    epochs: int = 12
    batch_size: int = 64
    learning_rate: float = 0.003
    weight_decay: float = 0.01
    clip_norm: float = 1.0
    patience: int = 4
    warmup_fraction: float = 0.1
    schedule: str = "cosine"
    timeout: float = 120.0

    def __post_init__(self):
        for value in (self.epochs, self.batch_size, self.patience):
            if type(value) is not int or value < 1:
                raise ValueError("positive integer training limits required")
        values = (self.learning_rate, self.weight_decay, self.clip_norm, self.warmup_fraction, self.timeout)
        if not all(math.isfinite(v) for v in values):
            raise ValueError("finite training settings required")
        if not 0 < self.timeout <= 1800 or self.learning_rate <= 0 or self.clip_norm <= 0 or self.weight_decay < 0:
            raise ValueError("invalid training bounds")
        if not 0 <= self.warmup_fraction < 1 or self.schedule not in {"cosine", "constant"}:
            raise ValueError("invalid schedule")


def learning_rate(config, step, total):
    warmup = int(total * config.warmup_fraction)
    if step < warmup:
        return config.learning_rate * (0.1 + 0.9 * (step + 1) / max(1, warmup))
    if config.schedule == "constant":
        return config.learning_rate
    progress = (step - warmup) / max(1, total - warmup - 1)
    return config.learning_rate * (0.01 + 0.99 * (1 + math.cos(math.pi * progress)) / 2)


def fit(model, x_train, y_train, x_validation, y_validation, *, task, config, seed):
    """Fit the compiled architecture; return best validation weights and measured work.

    Dropout/permutation randomness belongs to this evaluation's explicit stream.
    Validation labels select early-stop epoch, never preprocessing/calibration.
    """
    b = model.backend
    started, deadline = time.monotonic(), time.monotonic() + config.timeout
    rng = np.random.default_rng(seed)
    x = np.asarray(x_train, dtype=np.float32)
    xv = np.asarray(x_validation, dtype=np.float32)
    if not all(np.isfinite(v).all() for v in (x, xv, y_train, y_validation)):
        raise ValueError("training arrays must be finite")
    mean, std = x.mean(axis=0), x.std(axis=0)
    std = np.maximum(std, 1e-5)
    if model.token_input:
        mean, std = np.zeros_like(mean), np.ones_like(std)
    x, xv = (x - mean) / std, (xv - mean) / std
    if hasattr(model, "prepare_features"):
        model.prepare_features(x)
    regression = task == "regression"
    target_mean, target_std = regression_target_stats(y_train) if regression else (0, 1)
    y = (
        standardize_regression_targets(y_train, target_mean, target_std)
        if regression
        else np.asarray(y_train, dtype=np.int64)
    )
    yv = (
        standardize_regression_targets(y_validation, target_mean, target_std)
        if regression
        else np.asarray(y_validation, dtype=np.int64)
    )

    def loss(parameters, features, targets, training=False, mask_seed=0):
        logits = model.forward(parameters, b.array(features), training=training, seed=mask_seed)
        if task == "language_modeling" and targets.ndim == 1 and logits.ndim == 3:
            logits = logits[:, -1, :]
        if regression:
            return ((logits.reshape((-1,)) - b.array(targets.reshape(-1))) ** 2).mean()
        logits = logits.reshape((-1, logits.shape[-1]))
        shifted = logits - b.array(b.numpy(logits).max(axis=-1, keepdims=True))
        log_probs = shifted - b.log(b.exp(shifted).sum(axis=-1, keepdims=True))
        hot = np.eye(logits.shape[-1], dtype=np.float32)[targets.reshape(-1)]
        return -(b.array(hot) * log_probs).sum(axis=-1).mean()

    moments = {k: np.zeros_like(v) for k, v in model.weights.items()}
    variances = {k: np.zeros_like(v) for k, v in model.weights.items()}
    best = {k: v.copy() for k, v in model.weights.items()}
    best_buffers = deepcopy(model.buffers)
    best_loss, stale, updates, epochs_done = math.inf, 0, 0, 0
    total = config.epochs * math.ceil(len(x) / config.batch_size)
    initial_weights = {k: v.copy() for k, v in model.weights.items()}
    for epoch in range(config.epochs):
        order = rng.permutation(len(x))
        for start in range(0, len(x), config.batch_size):
            if time.monotonic() >= deadline:
                raise TimeoutError("training wall-clock cap reached")
            indices = order[start : start + config.batch_size]
            parameters = {k: b.array(v) for k, v in model.weights.items()}
            mask_seed = int(rng.integers(0, 2**32))
            value, grads = b.gradients(lambda p: loss(p, x[indices], y[indices], True, mask_seed), parameters)
            if not math.isfinite(value) or not all(np.isfinite(v).all() for v in grads.values()):
                raise ValueError("nonfinite loss or gradient")
            norm = math.sqrt(sum(float(np.sum(v.astype(np.float64) ** 2)) for v in grads.values()))
            scale = min(1.0, config.clip_norm / max(norm, 1e-12))
            lr = learning_rate(config, updates, total)
            updates += 1
            for key, grad in grads.items():
                grad = grad * scale
                moments[key] = 0.9 * moments[key] + 0.1 * grad
                variances[key] = 0.999 * variances[key] + 0.001 * grad * grad
                m, v = moments[key] / (1 - 0.9**updates), variances[key] / (1 - 0.999**updates)
                model.weights[key] = (
                    model.weights[key] * (1 - lr * config.weight_decay) - lr * m / (np.sqrt(v) + 1e-8)
                ).astype(np.float32)
            if not all(np.isfinite(v).all() for v in model.weights.values()):
                raise ValueError("nonfinite optimizer weights")
        parameters = {k: b.array(v) for k, v in model.weights.items()}
        value = float(b.numpy(loss(parameters, xv, yv)))
        if not math.isfinite(value):
            raise ValueError("nonfinite validation loss")
        epochs_done += 1
        if value < best_loss - 1e-8:
            best_loss, stale = value, 0
            best = {k: v.copy() for k, v in model.weights.items()}
            best_buffers = deepcopy(model.buffers)
        else:
            stale += 1
            if stale >= config.patience:
                break
    model.weights = best
    model.buffers = best_buffers
    parameters = {k: b.array(v) for k, v in best.items()}
    tick = time.perf_counter()
    prediction = b.numpy(model.forward(parameters, b.array(xv), training=False, seed=0))
    latency = time.perf_counter() - tick
    calibration = {"slope": 1.0, "intercept": 0.0}
    if regression:
        train_prediction = b.numpy(model.forward(parameters, b.array(x), training=False, seed=0))
        restored = restore_regression_predictions(train_prediction, target_mean, target_std).reshape(-1)
        yc = np.asarray(y_train, dtype=np.float64).reshape(-1)
        if restored.size >= 2 and restored.std() >= 1e-8:
            centered = restored - restored.mean()
            slope = float(centered @ (yc - yc.mean()) / (centered @ centered))
            calibration = {"slope": slope, "intercept": float(yc.mean() - slope * restored.mean())}
        prediction = calibrate_regression_predictions(
            train_pred=restore_regression_predictions(train_prediction, target_mean, target_std),
            y_train=y_train,
            val_pred=restore_regression_predictions(prediction, target_mean, target_std),
        )
        score = -float(np.mean((prediction.reshape(-1) - np.asarray(y_validation).reshape(-1)) ** 2))
    elif task == "language_modeling":
        score = -math.exp(best_loss)
    else:
        score = float(np.mean(prediction.argmax(axis=-1) == y_validation))
    if not math.isfinite(score):
        raise ValueError("nonfinite final score")
    result = {
        "score": score,
        "epochs": epochs_done,
        "updates": updates,
        "validation_loss": best_loss,
        "train_seconds": time.monotonic() - started,
        "latency_seconds": latency,
        "weights_changed": any(not np.array_equal(best[k], v) for k, v in initial_weights.items()),
        "preprocessing": {
            "feature_mean": mean.tolist(),
            "feature_std": std.tolist(),
            "target_mean": target_mean,
            "target_std": target_std,
            "calibration": calibration,
        },
    }

    if hasattr(model, 'policy'):
        # Training inputs only: behavioral diversity cannot consume protected labels.
        probe = b.numpy(model.forward(parameters, b.array(x[:16]), training=False, seed=0))
        signature = probe.reshape(-1)
        signature = np.array([part.mean() for part in np.array_split(signature, min(16, len(signature)))])
        signature -= signature.mean()
        signature /= max(float(np.linalg.norm(signature)), 1e-8)
        result['behavior'] = signature.tolist()
        result['evaluator_fidelity'] = model.evaluator_fidelity
        result['hierarchy_weights_changed'] = any(not np.array_equal(best[k], v) for k, v in initial_weights.items() if k.startswith('cell.'))
    return result
