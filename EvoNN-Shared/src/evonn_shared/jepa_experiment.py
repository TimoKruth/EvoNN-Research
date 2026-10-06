"""Additive pilot contracts and deterministic data; no engine training implementation.

These research receipts are deliberately distinct from canonical benchmark exports.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

SYSTEMS = ('prism', 'topograph', 'stratograph', 'primordia', 'contenders')
ARMS = ('supervised_short', 'supervised_long', 'reconstruction', 'jepa')
TRANSFER_ARMS = ('distillation', 'jepa_transfer')
MODULES = dict(zip(SYSTEMS, ('prism', 'topograph', 'stratograph', 'evonn_primordia', 'evonn_contenders')))


class PilotSpec(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    version: Literal[1] = 1
    systems: tuple[str, ...] = SYSTEMS
    arms: tuple[str, ...] = ARMS
    transfer_teacher: Literal['prism'] | None = None
    benchmarks: tuple[Literal['digits', 'breast_cancer', 'diabetes'], ...] = ('digits', 'breast_cancer')
    seeds: tuple[StrictInt, ...] = (131, 137, 149)
    label_fractions: tuple[float, ...] = (0.1, 1.0)
    candidates: int = Field(default=2, ge=1, le=8, strict=True)
    pretrain_steps: int = Field(default=32, ge=1, le=256, strict=True)
    finetune_steps: int = Field(default=32, ge=1, le=256, strict=True)
    batch_size: int = Field(default=32, ge=4, le=128, strict=True)
    latent_dim: int = Field(default=16, ge=4, le=64, strict=True)
    learning_rate: float = Field(default=0.001, gt=0, le=0.03)
    mask_fraction: float = Field(default=0.5, ge=0.1, le=0.9)
    ema_decay: float = Field(default=0.99, ge=0, lt=1)
    variance_weight: float = Field(default=1.0, gt=0, le=10)
    covariance_weight: float = Field(default=0.04, ge=0, le=10)
    backend: Literal['numpy_fallback', 'mlx_native'] = 'numpy_fallback'
    device: Literal['cpu', 'gpu'] = 'cpu'
    fit_timeout: float = Field(default=90, ge=1, le=300)

    @model_validator(mode='after')
    def validate_matrix(self):
        expected_arms = ARMS + TRANSFER_ARMS if self.transfer_teacher else ARMS
        if self.systems != SYSTEMS or self.arms != expected_arms:
            raise ValueError('pilot requires the complete ordered five-system matrix and all controls')
        for values in (self.benchmarks, self.seeds, self.label_fractions):
            if not values or len(set(values)) != len(values):
                raise ValueError('matrix dimensions must be nonempty and unique')
        if len(self.seeds) > 16 or len(self.label_fractions) > 4:
            raise ValueError('pilot matrix exceeds its bounded envelope')
        if any(type(s) is not int or not 0 <= s < 2**32 for s in self.seeds):
            raise ValueError('uint32 seeds required')
        if any(not 0 < fraction <= 1 for fraction in self.label_fractions):
            raise ValueError('label fractions must be in (0, 1]')
        if self.backend == 'numpy_fallback' and self.device != 'cpu':
            raise ValueError('NumPy requires CPU')
        return self


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    """Replace one derived receipt atomically, including interrupted-run receipts."""
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')
    temporary.replace(path)


def load_data(benchmark, seed, fraction):
    """Local sklearn data, new pilot split IDs, train-only transforms and label selection.

    The 20% validation partition is used for candidate selection. There is no test
    claim or canonical catalog access. Withheld training labels are never returned.
    """
    from sklearn import datasets
    from sklearn.model_selection import train_test_split
    loaders = {'digits': datasets.load_digits, 'breast_cancer': datasets.load_breast_cancer,
               'diabetes': datasets.load_diabetes}
    dataset = loaders[benchmark]()
    x, y = dataset.data.astype(np.float32), dataset.target
    regression = benchmark == 'diabetes'
    train, validation = train_test_split(np.arange(len(x)), test_size=0.2, random_state=seed,
                                        stratify=None if regression else y)
    rng = np.random.default_rng(seed)
    if regression:
        labeled = rng.permutation(len(train))[:max(2, int(np.ceil(len(train) * fraction))) ]
    else:
        # At least one example per class; actual label count/fraction is disclosed.
        labeled = np.concatenate([rng.permutation(np.flatnonzero(y[train] == c))[
            :max(1, int(np.ceil(np.sum(y[train] == c) * fraction)))] for c in np.unique(y[train])])
    mean, scale = x[train].mean(0), np.maximum(x[train].std(0), 1e-5)
    values = (x - mean) / scale
    labels = y[train[labeled]]
    target_mean = float(labels.mean()) if regression else 0.0
    target_scale = max(float(labels.std()), 1e-5) if regression else 1.0
    provenance = dict(benchmark='jepa_pilot_' + benchmark + '_v1', seed=seed,
                      split_sha256=digest({'train': train.tolist(), 'validation': validation.tolist()}),
                      label_sha256=digest(train[labeled].tolist()), requested_label_fraction=fraction,
                      actual_label_fraction=len(labeled)/len(train), training_rows=len(train),
                      labeled_rows=len(labeled), validation_rows=len(validation),
                      validation_label_access='all; candidate selection only', test_access=False,
                      raw_sha256=hashlib.sha256(x.tobytes() + y.tobytes()).hexdigest())
    return dict(x=values[train].astype(np.float32), labeled=labeled,
                y=((labels-target_mean)/target_scale).astype(np.float32) if regression else labels.astype(np.int64),
                xv=values[validation].astype(np.float32), yv=y[validation],
                output_dim=1 if regression else len(np.unique(y)), regression=regression,
                target_mean=target_mean, target_scale=target_scale, provenance=provenance)


def masks(rng, count, width, fraction, benchmark):
    """Disjoint nonempty views; spatial rectangular occlusion for 8x8 digits."""
    keep = np.ones((count, width), dtype=np.float32)
    if benchmark == 'digits':
        height = max(1, min(7, round(np.sqrt(fraction) * 8)))
        breadth = max(1, min(7, round(fraction * 64 / height)))
        for row in keep:
            top, left = rng.integers(0, 9-height), rng.integers(0, 9-breadth)
            row.reshape(8, 8)[top:top+height, left:left+breadth] = 0
    else:
        hidden = max(1, min(width-1, round(width * fraction)))
        for row in keep:
            row[rng.choice(width, hidden, replace=False)] = 0
    return keep
