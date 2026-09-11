"""Package-local differentiated optimizer and evaluation runtime."""

from dataclasses import dataclass
from copy import deepcopy
import math
import time
import hashlib
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
    preserve_initial: bool = False
    minimum_epochs: int = 1
    native_optimizer: bool = False
    optimizer_policy: str = "restart"

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
        if type(self.minimum_epochs) is not int or not 1 <= self.minimum_epochs <= self.epochs:
            raise ValueError("minimum epochs must lie within the fit allowance")
        if self.optimizer_policy not in {"restart", "continue"}:
            raise ValueError("unknown optimizer policy")


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
    optimizer_step = 0
    inherited_optimizer = getattr(model, "optimizer_state", None)
    if config.optimizer_policy == "continue" and inherited_optimizer is not None:
        if inherited_optimizer["weights_sha256"] != weights_digest(model.weights):
            raise ValueError("optimizer state is not bound to starting weights")
        if inherited_optimizer["schema_version"] != 1 or type(inherited_optimizer["step"]) is not int or inherited_optimizer["step"] < 0:
            raise ValueError("invalid optimizer state version or step")
        for target, name in ((moments, "moments"), (variances, "variances")):
            if set(inherited_optimizer[name]) != set(target):
                raise ValueError("optimizer keys disagree with model")
            for key in target:
                value = np.asarray(inherited_optimizer[name][key], dtype=np.float32)
                if value.shape != target[key].shape or not np.isfinite(value).all() or (name == "variances" and (value < 0).any()):
                    raise ValueError("invalid optimizer array")
                target[key] = value
        optimizer_step = inherited_optimizer["step"]
    resumed_step = optimizer_step
    best = {k: v.copy() for k, v in model.weights.items()}
    best_buffers = deepcopy(model.buffers)
    best_loss, stale, updates, epochs_done = math.inf, 0, 0, 0
    best_epoch, initial_loss, curve = None, None, []
    best_moments, best_variances, best_step = deepcopy(moments), deepcopy(variances), optimizer_step
    total = config.epochs * math.ceil(len(x) / config.batch_size)
    initial_weights = {k: v.copy() for k, v in model.weights.items()}
    if config.preserve_initial:
        initial_loss = float(b.numpy(loss({k: b.array(v) for k, v in model.weights.items()}, xv, yv)))
        if not math.isfinite(initial_loss):
            raise ValueError("nonfinite initial validation loss")
        best_loss, best_epoch = initial_loss, 0
    native = config.native_optimizer and b.mx is not None
    if native:
        import mlx.core as mx_sync
        parameters = {k: b.array(v) for k, v in model.weights.items()}
        moments, variances = ({k: b.array(v) for k, v in values.items()} for values in (moments, variances))
    for epoch in range(config.epochs):
        order = rng.permutation(len(x))
        epoch_loss, batches = 0.0, 0
        for start in range(0, len(x), config.batch_size):
            if time.monotonic() >= deadline:
                raise TimeoutError("training wall-clock cap reached")
            indices = order[start : start + config.batch_size]
            if not native:
                parameters = {k: b.array(v) for k, v in model.weights.items()}
            mask_seed = int(rng.integers(0, 2**32))
            if native:
                mx = b.mx
                value, grads = mx.value_and_grad(lambda p: loss(p, x[indices], y[indices], True, mask_seed))(parameters)
                finite = mx.stack([mx.all(mx.isfinite(v)) for v in grads.values()]).all()
                norm = mx.sqrt(sum(mx.sum(v * v) for v in grads.values()))
                scale = mx.minimum(1.0, config.clip_norm / mx.maximum(norm, 1e-12))
                lr = learning_rate(config, updates, total)
                updates += 1
                optimizer_step += 1
                for key, grad in grads.items():
                    grad = grad * scale
                    moments[key] = .9 * moments[key] + .1 * grad
                    variances[key] = .999 * variances[key] + .001 * grad * grad
                    m, v = moments[key] / (1 - .9**optimizer_step), variances[key] / (1 - .999**optimizer_step)
                    parameters[key] = parameters[key] * (1 - lr * config.weight_decay) - lr * m / (mx.sqrt(v) + 1e-8)
                finite_weights = mx.stack([mx.all(mx.isfinite(v)) for v in parameters.values()]).all()
                mx_sync.eval(value, parameters, moments, variances, finite, finite_weights)
                if not math.isfinite(float(value.item())) or not bool(finite.item()) or not bool(finite_weights.item()):
                    raise ValueError("nonfinite native loss, gradient or optimizer weights")
                epoch_loss += float(value.item())
                batches += 1
                continue
            value, grads = b.gradients(lambda p: loss(p, x[indices], y[indices], True, mask_seed), parameters)
            if not math.isfinite(value) or not all(np.isfinite(v).all() for v in grads.values()):
                raise ValueError("nonfinite loss or gradient")
            norm = math.sqrt(sum(float(np.sum(v.astype(np.float64) ** 2)) for v in grads.values()))
            scale = min(1.0, config.clip_norm / max(norm, 1e-12))
            lr = learning_rate(config, updates, total)
            updates += 1
            optimizer_step += 1
            for key, grad in grads.items():
                grad = grad * scale
                moments[key] = 0.9 * moments[key] + 0.1 * grad
                variances[key] = 0.999 * variances[key] + 0.001 * grad * grad
                m, v = moments[key] / (1 - 0.9**optimizer_step), variances[key] / (1 - 0.999**optimizer_step)
                model.weights[key] = (
                    model.weights[key] * (1 - lr * config.weight_decay) - lr * m / (np.sqrt(v) + 1e-8)
                ).astype(np.float32)
            if not all(np.isfinite(v).all() for v in model.weights.values()):
                raise ValueError("nonfinite optimizer weights")
            epoch_loss += value
            batches += 1
        if native:
            model.weights = {k: np.asarray(b.numpy(v)).copy() for k, v in parameters.items()}
        parameters = {k: b.array(v) for k, v in model.weights.items()}
        value = float(b.numpy(loss(parameters, xv, yv)))
        if not math.isfinite(value):
            raise ValueError("nonfinite validation loss")
        epochs_done += 1
        curve.append({"epoch": epochs_done, "updates": updates, "training_loss": epoch_loss / max(1, batches),
                      "validation_loss": value, "seconds": time.monotonic() - started})
        if value < best_loss - 1e-8:
            best_loss, stale = value, 0
            best = {k: v.copy() for k, v in model.weights.items()}
            best_buffers = deepcopy(model.buffers)
            best_epoch, best_step = epochs_done, optimizer_step
            if config.optimizer_policy == "continue":
                best_moments, best_variances = ({k: np.asarray(b.numpy(v) if native else v).copy() for k, v in values.items()}
                                               for values in (moments, variances))
        else:
            stale += 1
            if stale >= config.patience and epochs_done >= config.minimum_epochs:
                break
    model.weights = best
    model.buffers = best_buffers
    model.optimizer_state = {"schema_version": 1, "step": best_step, "weights_sha256": weights_digest(best),
        "moments": {k: v.tolist() for k, v in best_moments.items()},
        "variances": {k: v.tolist() for k, v in best_variances.items()}} if config.optimizer_policy == "continue" else None
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
    return {
        "score": score,
        "epochs": epochs_done,
        "updates": updates,
        "validation_loss": best_loss,
        "initial_validation_loss": initial_loss,
        "best_epoch": best_epoch,
        "learning_curve": curve,
        "optimizer_resumed_step": resumed_step,
        "optimizer_best_step": best_step,
        "optimizer_backend": "mlx" if native else "numpy",
        "optimizer_continuation_semantics": "moments and bias-correction step; new fit schedule and batch stream",
        "behavior_bucket": str(tuple(np.round(np.mean(prediction, axis=tuple(range(prediction.ndim - 1)))).reshape(-1)[:4].astype(int))),
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


def weights_digest(weights):
    digest = hashlib.sha256()
    for key, value in sorted(weights.items()):
        array = np.asarray(value, dtype=np.float32)
        digest.update(key.encode() + str(array.shape).encode() + array.tobytes())
    return digest.hexdigest()
