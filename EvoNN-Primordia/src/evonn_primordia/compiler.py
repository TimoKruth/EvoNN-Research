"""Differentiable tiny circuits with explicit sparse masks and causal token inputs."""

import math
import numpy as np
from .genome import PrimitiveGenome, clamp
from .tensors import Backend


class CompiledPrimitive:
    evaluator_fidelity = "end_to_end_primitive"

    def __init__(
        self, genome, input_shape, output_dim, modality, task, *, backend="numpy_fallback", device="cpu", seed=0
    ):
        self.genome = PrimitiveGenome.model_validate(genome)
        if clamp(genome, task, modality) != genome:
            raise ValueError("primitive exceeds task architecture clamps")
        self.backend = Backend(backend, device)
        self.token_input = task == "language_modeling"
        self.input_shape, self.output_dim = tuple(input_shape), output_dim
        self.spatial = genome.spatial_mode != "flatten"
        if self.spatial and (modality != "image" or len(input_shape) not in (2, 3)):
            raise ValueError("spatial circuits require a two-dimensional image with optional channels")
        if not self.token_input and genome.temporal_mode in {"attention", "convolution", "multiscale"}:
            raise ValueError("learned temporal circuits require token inputs")
        width = genome.width
        rng = np.random.default_rng(seed)
        self.weights, self.buffers, self.masks = {}, {}, {}

        def weight(key, shape):
            self.weights[key] = (rng.normal(size=shape) / math.sqrt(shape[0])).astype(np.float32)

        input_dim = output_dim if self.token_input else math.prod(input_shape)
        output_width = width
        if self.spatial:
            height, columns = input_shape[:2]
            channels = input_shape[2] if len(input_shape) == 3 else 1
            # Gather zero-padded 3x3 neighborhoods; the projection is shared at every pixel.
            indices = []
            for row in range(height):
                for col in range(columns):
                    indices.append([(r * columns + c) if 0 <= r < height and 0 <= c < columns else height * columns
                                    for r in range(row - 1, row + 2) for c in range(col - 1, col + 2)])
            self.patch_indices = np.asarray(indices)
            input_dim = 9 * channels
            positions = height * columns
            if genome.spatial_mode == "conv_pool":
                pool = np.zeros((math.ceil(height / 2) * math.ceil(columns / 2), positions), np.float32)
                for row in range(height):
                    for col in range(columns):
                        pool[(row // 2) * math.ceil(columns / 2) + col // 2, row * columns + col] = 1
                self.pool = pool / pool.sum(axis=1, keepdims=True)
                positions = len(pool)
            output_width *= positions
        weight("input.w", (input_dim, width))
        self.weights["input.b"] = np.zeros(width, np.float32)
        if self.token_input and genome.temporal_mode == "attention":
            for name in ("q", "k", "v", "out"):
                weight("temporal." + name, (width, width))
            # Relative distance bias can learn retrieval without binding absolute positions.
            self.weights["temporal.bias"] = np.zeros(input_shape[0], np.float32)
        if self.token_input and genome.temporal_mode in {"convolution", "multiscale"}:
            self.lags = ([0, genome.temporal_dilation, 2 * genome.temporal_dilation, 4 * genome.temporal_dilation]
                         if genome.temporal_mode == "convolution" else [0, 1, 2, 4, 8, 16, 32])
            self.lags = [lag for lag in self.lags if lag < input_shape[0]]
            self.weights["temporal.kernel"] = (rng.normal(size=(len(self.lags), width)) / math.sqrt(len(self.lags))).astype(np.float32)
            weight("temporal.out", (width, width))
        for index, primitive in enumerate(genome.primitives):
            key = f"p{index}"
            if primitive.operator == "identity":
                continue
            weight(key + ".w", (width, width))
            self.weights[key + ".b"] = np.zeros(width, np.float32)
            if primitive.operator == "gate":
                weight(key + ".gate", (width, width))
            if primitive.operator == "sparse":
                # A structural local mask, independent of labels and run RNG.
                distances = (np.arange(width)[:, None] - np.arange(width)[None, :]) % width
                self.masks[key] = np.isin(distances, [v % width for v in genome.sparse_offsets]).astype(np.float32)
        weight("output.w", (output_width * (2 if genome.readout == "skip" else 1), output_dim))
        self.weights["output.b"] = np.zeros(output_dim, np.float32)

    @property
    def parameter_count(self):
        return sum(value.size for value in self.weights.values())

    def forward(self, parameters, features, *, training=False, seed=0):
        b = self.backend
        if self.token_input:
            tokens = b.numpy(features)
            if (
                tokens.ndim != 2
                or not np.isfinite(tokens).all()
                or np.any(tokens != np.floor(tokens))
                or np.any(tokens < 0)
                or np.any(tokens >= self.output_dim)
            ):
                raise ValueError("integer in-vocabulary token matrix required")
            # Token projection precedes strictly causal temporal processing.
            if self.genome.version >= 3:
                # Embedding lookup avoids a batch x context x vocabulary one-hot tensor.
                hidden = b.tanh(b.gather(parameters["input.w"], tokens.astype(np.int64)) + parameters["input.b"])
            else:
                x = b.array(np.eye(self.output_dim, dtype=np.float32)[tokens.astype(np.int64)])
                hidden = b.tanh(x @ parameters["input.w"] + parameters["input.b"])
        elif self.spatial:
            channels = self.input_shape[2] if len(self.input_shape) == 3 else 1
            x = features.reshape((features.shape[0], -1, channels))
            x = b.concatenate([x, b.array(np.zeros((x.shape[0], 1, channels), np.float32))], axis=1)
            patches = b.gather(x, (slice(None), self.patch_indices, slice(None)))
            x = patches.reshape((features.shape[0], len(self.patch_indices), 9 * channels))
            hidden = b.activate(x @ parameters["input.w"] + parameters["input.b"], "gelu")
        else:
            x = features.reshape((features.shape[0], -1))
            hidden = b.tanh(x @ parameters["input.w"] + parameters["input.b"])
        if self.token_input:
            length = hidden.shape[1]
            if self.genome.version >= 3 and length != self.input_shape[0]:
                raise ValueError("token context differs from compiled input shape")
            if self.genome.temporal_mode == "attention":
                normalized = self._rms(hidden)
                q, k, v = [normalized @ parameters["temporal." + name] for name in ("q", "k", "v")]
                distances = np.arange(length)[:, None] - np.arange(length)[None, :]
                bias = b.gather(parameters["temporal.bias"], np.maximum(distances, 0))
                logits = q @ k.transpose((0, 2, 1)) / math.sqrt(self.genome.width)
                logits = logits + bias + b.array(np.where(distances >= 0, 0., -1e9).astype(np.float32))
                hidden = hidden + (b.softmax(logits) @ v) @ parameters["temporal.out"]
            elif self.genome.temporal_mode in {"convolution", "multiscale"}:
                mixed = hidden * 0
                for index, lag in enumerate(self.lags):
                    shifted = b.array(np.eye(length, k=-lag, dtype=np.float32)) @ hidden
                    mixed = mixed + shifted * parameters["temporal.kernel"][index]
                hidden = hidden + b.activate(mixed, "gelu") @ parameters["temporal.out"]
            elif self.genome.temporal_mode == "lag":
                causal = np.eye(length, k=-self.genome.temporal_lag, dtype=np.float32)
                hidden = (hidden + b.array(causal) @ hidden) * 0.5
            else:
                causal = (
                    np.tril(np.ones((length, length), dtype=np.float32))
                    / np.arange(1, length + 1, dtype=np.float32)[:, None]
                )
                hidden = (hidden + b.array(causal) @ hidden) * 0.5
        states = [hidden]
        rng = np.random.default_rng(seed)
        for index, primitive in enumerate(self.genome.primitives):
            if self.genome.sources:
                refs = self.genome.sources[index]
                hidden = states[refs[0]]
                for ref in refs[1:]:
                    hidden = hidden + states[ref]
                hidden = hidden / len(refs)
            key = f"p{index}"
            if primitive.operator == "identity":
                value = hidden
            else:
                weight = parameters[key + ".w"]
                if primitive.operator == "sparse":
                    weight = weight * b.array(self.masks[key])
                normalized = self._rms(hidden) if self.genome.normalization == "rms" else hidden
                value = b.activate(normalized @ weight + parameters[key + ".b"], primitive.activation)
                if primitive.operator == "gate":
                    value = value * b.sigmoid(normalized @ parameters[key + ".gate"])
                elif primitive.operator == "residual":
                    value = ((value + hidden) * 0.5 if self.genome.version < 3 else
                             hidden + value / math.sqrt(2))
                if training and self.genome.dropout:
                    mask = (rng.random(value.shape) >= self.genome.dropout) / (1 - self.genome.dropout)
                    value = value * b.array(mask.astype(np.float32))
            if primitive.merge == "mean":
                value = (value + hidden) * 0.5
            elif primitive.merge == "product":
                value = value * b.tanh(hidden)
            hidden = value
            states.append(hidden)
        if self.genome.readout == "skip":
            hidden = b.concatenate([states[0], hidden], axis=-1)
        if self.spatial:
            if self.genome.spatial_mode == "conv_pool":
                hidden = b.array(self.pool) @ hidden
            hidden = hidden.reshape((hidden.shape[0], -1))
        return hidden @ parameters["output.w"] + parameters["output.b"]

    @staticmethod
    def _rms(value):
        return value * ((value * value).mean(axis=-1, keepdims=True) + 1e-5) ** -0.5


def compile_genome(genome, input_shape, output_dim, modality, task, **options):
    return CompiledPrimitive(genome, input_shape, output_dim, modality, task, **options)
