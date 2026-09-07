"""Optional CPU CNN and causal next-token transformer floors."""
from __future__ import annotations

import math

import numpy as np
import torch
from torch import nn


class _CausalLanguageModel(nn.Module):
    def __init__(self, vocabulary_size: int, context_length: int, width: int = 64):
        super().__init__()
        self.embedding = nn.Embedding(vocabulary_size, width)
        self.position = nn.Embedding(context_length, width)
        layer = nn.TransformerEncoderLayer(width, 4, dim_feedforward=128, dropout=0.1, batch_first=True)
        self.encoder = nn.TransformerEncoder(layer, 2, enable_nested_tensor=False)
        self.output = nn.Linear(width, vocabulary_size)

    def forward(self, x):
        length = x.shape[1]
        positions = torch.arange(length, device=x.device)
        embedded = self.embedding(x) + self.position(positions)[None]
        mask = torch.triu(torch.ones(length, length, dtype=torch.bool, device=x.device), diagonal=1)
        return self.output(self.encoder(embedded, mask=mask)[:, -1])


class TorchFloor:
    def __init__(self, name: str, *, input_shape: tuple[int, ...], output_dim: int,
                 seed: int, epochs: int = 20, batch_size: int = 32, learning_rate: float = 0.001):
        if type(epochs) is not int or type(batch_size) is not int or epochs < 1 or batch_size < 1 or not math.isfinite(learning_rate) or learning_rate <= 0:
            raise ValueError("invalid torch training configuration")
        if name not in ("cnn_small", "transformer_lm_tiny") or output_dim < 2 or not input_shape or any(d < 1 for d in input_shape):
            raise ValueError("invalid torch model or dimensions")
        self.name, self.seed, self.epochs = name, seed, epochs
        self.input_shape, self.output_dim = input_shape, output_dim
        self.batch_size, self.learning_rate = batch_size, learning_rate
        self.model = None
        self.mean, self.scale = 0.0, 1.0

    def _tensor(self, x):
        if self.name == "transformer_lm_tiny":
            values = np.asarray(x)
            if values.ndim != 2 or values.shape[1:] != self.input_shape or values.dtype.kind not in "iu" or np.any(values < 0) or np.any(values >= self.output_dim):
                raise ValueError("transformer requires in-vocabulary integer contexts")
            return torch.as_tensor(values, dtype=torch.long)
        values = np.asarray(x)
        if not len(values) or int(np.prod(values.shape[1:])) != int(np.prod(self.input_shape)) or not np.isfinite(values).all():
            raise ValueError("CNN input rows must match declared finite image features")
        shape = self.input_shape
        if len(shape) == 1:
            side = math.isqrt(shape[0])
            if side * side != shape[0]:
                raise ValueError("CNN requires square image features")
            shape = (1, side, side)
        elif len(shape) == 2:
            shape = (1, *shape)
        if len(shape) != 3:
            raise ValueError("CNN requires channels, height and width")
        return (torch.as_tensor(np.asarray(x), dtype=torch.float32).reshape(-1, *shape) - self.mean) / self.scale

    def fit(self, x, y):
        y = np.asarray(y)
        if not len(x) or y.shape != (len(x),) or y.dtype.kind not in "iu" or np.any(y < 0) or np.any(y >= self.output_dim):
            raise ValueError("one in-vocabulary class/token target is required per row")
        if self.name == "cnn_small":
            self.mean = float(np.asarray(x).mean())
            self.scale = max(float(np.asarray(x).std()), 1e-6)
        features, targets = self._tensor(x), torch.as_tensor(y, dtype=torch.long)
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(self.seed)
            if self.name == "cnn_small":
                self.model = nn.Sequential(nn.Conv2d(features.shape[1], 32, 3, padding=1), nn.ReLU(),
                    nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.AdaptiveAvgPool2d((4, 4)),
                    nn.Flatten(), nn.Linear(64 * 4 * 4, 128), nn.ReLU(), nn.Linear(128, self.output_dim))
            elif self.name == "transformer_lm_tiny":
                self.model = _CausalLanguageModel(self.output_dim, features.shape[1])
            else:
                raise ValueError("unknown torch floor")
            optimizer = torch.optim.Adam(self.model.parameters(), lr=self.learning_rate)
            self.model.train()
            for _ in range(self.epochs):
                order = torch.randperm(len(features))
                for indices in order.split(self.batch_size):
                    optimizer.zero_grad(set_to_none=True)
                    loss = nn.functional.cross_entropy(self.model(features[indices]), targets[indices])
                    loss.backward()
                    optimizer.step()
        self.model.train(False)
        return self

    def predict_proba(self, x):
        if self.model is None:
            raise ValueError("model has not been fitted")
        with torch.no_grad():
            features = self._tensor(x)
            return torch.cat([self.model(batch).softmax(dim=1) for batch in features.split(self.batch_size)]).numpy()

    def predict(self, x):
        return self.predict_proba(x).argmax(axis=1)

    def perplexity(self, x, y):
        probabilities = self.predict_proba(x)
        targets = np.asarray(y)
        if targets.shape != (len(probabilities),) or not len(targets) or targets.dtype.kind not in "iu" or np.any(targets < 0) or np.any(targets >= self.output_dim):
            raise ValueError("one in-vocabulary held-out target per row required")
        values = probabilities[np.arange(len(targets)), targets]
        return float(np.exp(-np.log(np.maximum(values, np.finfo(np.float32).tiny)).mean()))
