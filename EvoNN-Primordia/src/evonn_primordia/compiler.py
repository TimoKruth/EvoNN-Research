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
        width = genome.width
        rng = np.random.default_rng(seed)
        self.weights, self.buffers, self.masks = {}, {}, {}

        def weight(key, shape):
            self.weights[key] = (rng.normal(size=shape) / math.sqrt(shape[0])).astype(np.float32)

        weight("input.w", (output_dim if self.token_input else math.prod(input_shape), width))
        self.weights["input.b"] = np.zeros(width, np.float32)
        for index, primitive in enumerate(genome.primitives):
            key = f"p{index}"
            weight(key + ".w", (width, width))
            self.weights[key + ".b"] = np.zeros(width, np.float32)
            if primitive.operator == "gate":
                weight(key + ".gate", (width, width))
            if primitive.operator == "sparse":
                # A structural local mask, independent of labels and run RNG.
                self.masks[key] = ((np.arange(width)[:, None] - np.arange(width)[None, :]) % width < 2).astype(
                    np.float32
                )
        weight("output.w", (width, output_dim))
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
            # Each position observes its own token only, never future targets.
            x = b.array(np.eye(self.output_dim, dtype=np.float32)[tokens.astype(np.int64)])
        else:
            x = features.reshape((features.shape[0], -1))
        hidden = b.tanh(x @ parameters["input.w"] + parameters["input.b"])
        if self.token_input:
            length = hidden.shape[1]
            causal = (
                np.tril(np.ones((length, length), dtype=np.float32))
                / np.arange(1, length + 1, dtype=np.float32)[:, None]
            )
            hidden = (hidden + b.array(causal) @ hidden) * 0.5
        for index, primitive in enumerate(self.genome.primitives):
            key = f"p{index}"
            weight = parameters[key + ".w"]
            if primitive.operator == "sparse":
                weight = weight * b.array(self.masks[key])
            value = b.activate(hidden @ weight + parameters[key + ".b"], primitive.activation)
            if primitive.operator == "gate":
                value = value * b.sigmoid(hidden @ parameters[key + ".gate"])
            elif primitive.operator == "residual":
                value = (value + hidden) * 0.5
            if primitive.merge == "mean":
                value = (value + hidden) * 0.5
            elif primitive.merge == "product":
                value = value * b.tanh(hidden)
            hidden = value
        return hidden @ parameters["output.w"] + parameters["output.b"]


def compile_genome(genome, input_shape, output_dim, modality, task, **options):
    return CompiledPrimitive(genome, input_shape, output_dim, modality, task, **options)
