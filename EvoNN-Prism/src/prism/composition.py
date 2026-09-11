"""Shape-preserving block composition with causal text and acyclic skip edges.

Extend BLOCK_FAMILIES and genome.BLOCK_KINDS together, then qualify the new
constructor on both backends. State/weights are namespaced by block position
and kind, so partial inheritance never confuses unrelated block operators.
"""

import math
import numpy as np
from .compiler import FamilyModel
from .genome import ModelGenome

BLOCK_FAMILIES = {"dense": "embedding", "sparse": "embedding", "gated": "gated_state_space",
                  "conv1d": "conv1d", "conv2d": "conv2d", "gru": "gru",
                  "attention": "causal_transformer", "state_space": "state_space"}


class CompositeModel:
    def __init__(self, genome, input_shape, output_dim, modality, task, backend, seed, vocab_size=None):
        self.genome, self.input_shape, self.output_dim = genome, tuple(input_shape), output_dim
        self.modality, self.task, self.backend = modality, task, backend
        self.token_input = modality == "text"
        self.buffers, self.weights, self.executors = {}, {}, []
        if any(block.kind == "conv2d" for block in genome.blocks) and (modality != "image" or len(input_shape) not in {2, 3}):
            raise ValueError("conv2d composition requires a spatial image")
        rng = np.random.default_rng(seed)
        width = genome.embedding_dim
        if modality == "image":
            self.length, incoming = math.prod(input_shape[:2]), input_shape[2] if len(input_shape) == 3 else 1
        elif modality == "text":
            self.length, incoming = input_shape[0], vocab_size if vocab_size is not None else output_dim
        elif modality == "tabular":
            self.length, incoming = math.prod(input_shape), 1
        else:
            self.length, incoming = input_shape[0], math.prod(input_shape[1:])
        self.weights["stem.w"] = (rng.normal(size=(incoming, width)) * math.sqrt(2 / incoming)).astype(np.float32)
        self.weights["stem.b"] = np.zeros(width, np.float32)
        for i, block in enumerate(genome.blocks):
            values = genome.model_dump(exclude={"blocks"})
            values.update(family=BLOCK_FAMILIES[block.kind], hidden_layers=(width,), residual=False)
            local = ModelGenome.model_validate(values)
            shape = (*input_shape[:2], width) if block.kind == "conv2d" else (self.length, width)
            executor = FamilyModel(local, shape, width, "image" if block.kind == "conv2d" else "sequence",
                                   task, backend, int(rng.integers(0, 2**32)))
            # Feature mode does not execute a prediction head.
            executor.weights = {k: v for k, v in executor.weights.items() if not k.startswith("head.")}
            prefix = f"block{i}.{block.kind}."
            self.weights.update({prefix + k: v for k, v in executor.weights.items()})
            self.executors.append((prefix, executor))
        self.weights["head.w"] = (rng.normal(size=(width, output_dim)) * math.sqrt(2 / width)).astype(np.float32)
        self.weights["head.b"] = np.zeros(output_dim, np.float32)

    @property
    def parameter_count(self):
        return sum(v.size for v in self.weights.values())

    def forward(self, p, x, *, training=False, seed=0):
        b, width = self.backend, self.genome.embedding_dim
        if self.token_input:
            x = b.gather(p["stem.w"], b.numpy(x).astype(np.int64)) + p["stem.b"]
        else:
            x = x.reshape((x.shape[0], self.length, -1)) @ p["stem.w"] + p["stem.b"]
        states = [x]
        for i, (block, (prefix, executor)) in enumerate(zip(self.genome.blocks, self.executors, strict=True)):
            executor.buffers = {key.removeprefix(prefix): value for key, value in self.buffers.items()
                                if key.startswith(prefix)}
            value = x.reshape((x.shape[0], *self.input_shape[:2], width)) if block.kind == "conv2d" else x
            value = executor.forward({k: p[prefix + k] for k in executor.weights}, value,
                                     training=training, seed=(seed + i) % 2**32, return_features=True)
            x = value.reshape((value.shape[0], self.length, width))
            if block.kind == "sparse":
                raw = np.abs(b.numpy(x))
                keep = max(1, int(width * (1 - self.genome.activation_sparsity)))
                threshold = np.sort(raw, axis=-1)[..., -keep:][..., :1]
                x = x * b.array(raw >= threshold)
            if block.skip_from is not None:
                x = x + states[block.skip_from]
            self.buffers.update({prefix + key: value for key, value in executor.buffers.items()})
            states.append(x)
        if self.task != "language_modeling":
            x = x.mean(axis=1)
        return x @ p["head.w"] + p["head.b"]
