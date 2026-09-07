"""Narrow train-only regression scaling and affine calibration."""

import math
import numpy as np


def regression_target_stats(y_train):
    values = np.asarray(y_train, dtype=np.float64).reshape(-1)
    if not values.size or not np.isfinite(values).all():
        raise ValueError("finite nonempty regression targets required")
    mean, std = float(values.mean()), float(values.std())
    if not math.isfinite(mean) or not math.isfinite(std):
        raise ValueError("regression target scale exceeds numeric range")
    return mean, std if std >= 1e-8 else 1.0


def standardize_regression_targets(y_train, mean, std):
    return ((np.asarray(y_train, dtype=np.float64) - mean) / std).astype(np.float32)


def restore_regression_predictions(y_pred, mean, std):
    return np.asarray(y_pred, dtype=np.float64) * std + mean


def calibrate_regression_predictions(*, train_pred, y_train, val_pred):
    x, y, v = (np.asarray(a, dtype=np.float64).reshape(-1) for a in (train_pred, y_train, val_pred))
    if x.size != y.size or not all(np.isfinite(a).all() for a in (x, y, v)):
        raise ValueError("finite aligned calibration inputs required")
    if x.size < 2 or x.std() < 1e-8:
        return v.copy()
    xc, yc = x - x.mean(), y - y.mean()
    slope = float(xc @ yc / (xc @ xc))
    result = (v - x.mean()) * slope + y.mean()
    if not np.isfinite(result).all():
        raise ValueError("nonfinite calibration result")
    return result


