"""Graph-driven differentiated mixed-precision models, without speedup claims."""

import math
import numpy as np
from .tensors import Backend


class QuantizedLinear:
    def __init__(self, bits=8, activation_bits=32):
        self.bits, self.activation_bits = bits, activation_bits

    def __call__(self, backend, x, weight, bias):
        return backend.quantize(x, self.activation_bits) @ backend.quantize(weight, self.bits) + bias


class BitLinear(QuantizedLinear):
    def __init__(self):
        super().__init__(1.58, 8)


class EvolvedModel:
    token_input = False

    def __init__(self, genome, input_shape, output_dim, backend, seed):
        self.genome, self.backend, self.input_shape, self.output_dim = genome, backend, tuple(input_shape), output_dim
        self.layers = genome.active_layers()
        self.weights, self.precisions = {}, {}
        self.buffers = {}
        self.experts = tuple(sorted(genome.experts, key=lambda e: e.innovation))
        nodes = {n.innovation: n for n in self.layers}
        self.edges = sorted(
            (
                e
                for e in genome.connections
                if e.enabled and e.target in nodes and (e.source == -1 or e.source in nodes)
            ),
            key=lambda e: e.innovation,
        )
        self.routing = {n.innovation: tuple(e for e in self.edges if e.target == n.innovation) for n in self.layers}
        rng = np.random.default_rng(seed)

        def linear(key, incoming, outgoing, bits):
            self.weights[key + ".w"] = (rng.standard_normal((incoming, outgoing)) * math.sqrt(2 / incoming)).astype(
                np.float32
            )
            self.weights[key + ".b"] = np.zeros(outgoing, np.float32)
            self.precisions[key + ".w"] = bits
            self.precisions[key + ".b"] = 32

        for edge in self.edges:
            target = nodes[edge.target]
            linear(
                f"edge{edge.innovation}",
                math.prod(input_shape) if edge.source == -1 else nodes[edge.source].width,
                target.width,
                target.weight_bits,
            )
        for node in self.layers:
            key, width = f"node{node.innovation}", node.width
            if node.operator in {"attention_lite", "transformer_lite"}:
                for part in ("q", "k", "v", "out"):
                    linear(key + "." + part, width // 4, width // 4, node.weight_bits)
                if node.operator == "transformer_lite":
                    linear(key + ".ff1", width, width * 2, node.weight_bits)
                    linear(key + ".ff2", width * 2, width, node.weight_bits)
            elif node.operator == "spatial":
                spec = next((c for c in genome.convolutions if c.layer == node.innovation), None)
                size = spec.kernel_size if spec else 3
                self.weights[key + ".kernel"] = (rng.standard_normal((size, size)) * math.sqrt(2 / size**2)).astype(
                    np.float32
                )
                self.precisions[key + ".kernel"] = node.weight_bits
            elif node.operator == "residual":
                linear(key + ".residual", width, width, node.weight_bits)
        last = nodes[genome.output]
        if genome.experts:
            linear("gate", last.width, len(genome.experts), last.weight_bits)
            for expert in self.experts:
                linear(f"expert{expert.innovation}.hidden", last.width, expert.width, last.weight_bits)
                linear(f"expert{expert.innovation}.out", expert.width, output_dim, last.weight_bits)
        else:
            linear("head", last.width, output_dim, last.weight_bits)

    @property
    def parameter_count(self):
        return sum(v.size for v in self.weights.values())

    @property
    def packed_bytes_estimate(self):
        return sum(math.ceil(v.size * self.precisions[k] / 8) for k, v in self.weights.items())

    def forward(self, p, x, *, training=False, seed=0):
        b = self.backend
        values = {-1: x.reshape((x.shape[0], -1))}

        def linear(key, value, activation_bits=32):
            return QuantizedLinear(self.precisions[key + ".w"], activation_bits)(b, value, p[key + ".w"], p[key + ".b"])

        for node in self.layers:
            key, n, width = f"node{node.innovation}", x.shape[0], node.width
            incoming = [
                linear(f"edge{e.innovation}", values[e.source], 8 if node.weight_bits == 1.58 else node.activation_bits)
                for e in self.routing[node.innovation]
            ]
            value = sum(incoming) / math.sqrt(len(incoming))
            value = b.norm(value, "layer")
            if node.operator in {"attention_lite", "transformer_lite"}:
                tokens, heads, dims = 4, node.heads, width // (4 * node.heads)
                z = value.reshape((n, tokens, width // tokens))
                q, k, v = [
                    linear(key + "." + name, z).reshape((n, tokens, heads, dims)).transpose((0, 2, 1, 3))
                    for name in ("q", "k", "v")
                ]
                attended = (
                    (b.softmax(q @ k.transpose((0, 1, 3, 2)) / math.sqrt(dims)) @ v)
                    .transpose((0, 2, 1, 3))
                    .reshape((n, tokens, width // tokens))
                )
                value = value + linear(key + ".out", attended).reshape((n, width))
                if node.operator == "transformer_lite":
                    value = value + linear(key + ".ff2", b.activate(linear(key + ".ff1", value), node.activation))
            elif node.operator == "spatial":
                side = int(math.sqrt(width))
                image = value.reshape((n, side, side))
                kernel = b.quantize(p[key + ".kernel"], node.weight_bits)
                radius = kernel.shape[0] // 2
                pieces = []
                for iy in range(kernel.shape[0]):
                    for ix in range(kernel.shape[1]):
                        ys, xs = np.arange(side) + iy - radius, np.arange(side) + ix - radius
                        mask = (ys[:, None] >= 0) & (ys[:, None] < side) & (xs[None, :] >= 0) & (xs[None, :] < side)
                        shifted = b.gather(
                            b.gather(image, (slice(None), np.clip(ys, 0, side - 1))),
                            (slice(None), slice(None), np.clip(xs, 0, side - 1)),
                        )
                        pieces.append(shifted * b.array(mask) * kernel[iy, ix])
                value = sum(pieces).reshape((n, width))
            elif node.operator == "residual":
                value = value + linear(key + ".residual", b.activate(value, node.activation))
            value = b.activate(value, node.activation)
            if node.operator == "sparse_dense":
                raw = np.abs(b.numpy(value))
                keep = max(1, int(width * (1 - node.sparsity)))
                value = value * b.array(raw >= np.sort(raw, axis=-1)[:, -keep][:, None])
            values[node.innovation] = b.quantize(value, node.activation_bits)
        output = values[self.genome.output]
        if self.genome.experts:
            logits = linear("gate", output) / self.genome.gate.temperature
            raw = b.numpy(logits)
            keep = np.argsort(raw, axis=-1)[:, -self.genome.gate.top_k :]
            mask = np.zeros_like(raw)
            np.put_along_axis(mask, keep, 1, axis=-1)
            gates = b.softmax(logits) * b.array(mask)
            return sum(
                linear(f"expert{e.innovation}.out", b.activate(linear(f"expert{e.innovation}.hidden", output), "gelu"))
                * gates[:, i : i + 1]
                for i, e in enumerate(self.experts)
            )
        return linear("head", output)


def compile_genome(
    genome,
    input_shape,
    output_dim,
    modality="tabular",
    task="classification",
    *,
    backend="numpy_fallback",
    device="cpu",
    seed=0,
):
    if task not in {"classification", "regression"} or modality not in {"tabular", "image", "sequence"}:
        raise ValueError("Phase-2 Topograph supports numeric classification/regression; text/LM is not implemented")
    if not input_shape or any(type(v) is not int or v <= 0 for v in input_shape) or output_dim < 1:
        raise ValueError("positive model dimensions required")
    return EvolvedModel(genome, input_shape, output_dim, Backend(backend, device), seed)
