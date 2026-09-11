"""Optional token/spatial adapters; existing flat DAG operators remain available."""

import math
import numpy as np
from .compiler import EvolvedModel, compile_genome as compile_legacy
from .tensors import Backend


def parameter_estimate(genome, definition):
    """Exact shape arithmetic before allocating weights; includes biases and gates."""
    output = definition.output_dim
    incoming = math.prod(definition.input_shape)
    count = 0
    if genome.input_adapter == "token_attention":
        width = genome.adapter_width
        count += output * width + incoming * width + 4 * width**2
        incoming = width
    elif genome.input_adapter == "spatial":
        count += 36 + incoming * 4 * genome.adapter_width
        incoming = genome.adapter_width
    elif definition.task_kind.value == "language_modeling" and definition.input_modality.value == "text":
        incoming *= output
    nodes = {n.innovation: n for n in genome.active_layers()}
    for edge in genome.connections:
        if edge.enabled and edge.target in nodes and (edge.source == -1 or edge.source in nodes):
            width = nodes[edge.target].width
            count += (incoming if edge.source == -1 else nodes[edge.source].width) * width + width
            count += int(edge.trainable_scale)
    for node in nodes.values():
        w = node.width
        if node.operator in ("attention_lite", "transformer_lite"):
            count += 4 * ((w // 4) ** 2 + w // 4)
            if node.operator == "transformer_lite":
                count += 4 * w * w + 3 * w
        elif node.operator == "residual":
            count += w * w + w
        elif node.operator == "spatial":
            count += next((c.kernel_size for c in genome.convolutions if c.layer == node.innovation), 3) ** 2
    width = nodes[genome.output].width
    if genome.experts:
        count += (width + 1) * len(genome.experts)
        count += sum((width + 1) * e.width + (e.width + 1) * output for e in genome.experts)
    else:
        count += (width + 1) * output
    return count


class AdaptedModel(EvolvedModel):
    def __init__(self, genome, input_shape, output_dim, backend, seed, modality, task):
        self.original_shape = tuple(input_shape)
        self.adapter = genome.input_adapter
        self.is_text = task == "language_modeling" and modality == "text"
        width = genome.adapter_width
        if self.adapter == "token_attention" and not self.is_text:
            raise ValueError("token adapter requires next-token text input")
        if self.adapter == "spatial" and (modality != "image" or len(input_shape) != 2):
            raise ValueError("spatial adapter requires a two-dimensional image")
        super().__init__(genome, (width,), output_dim, backend, seed, token_input=False)
        self.token_input = self.is_text
        rng = np.random.default_rng(seed ^ 0xADAF7)

        def parameter(name, shape, scale):
            self.weights["adapter." + name] = (rng.standard_normal(shape) * scale).astype(np.float32)
            self.precisions["adapter." + name] = 32

        if self.adapter == "token_attention":
            parameter("embedding", (output_dim, width), 0.1)
            parameter("position", (math.prod(input_shape), width), 0.01)
            for part in ("q", "k", "v", "out"):
                parameter(part, (width, width), 1 / math.sqrt(width))
        else:
            parameter("kernel", (3, 3, 4), 1 / 3)
            parameter("projection", (math.prod(input_shape) * 4, width), 1 / math.sqrt(math.prod(input_shape) * 4))

    def prepare_input(self, p, x):
        b, width = self.backend, self.genome.adapter_width
        n = x.shape[0]
        if self.adapter == "token_attention":
            raw = b.numpy(x)
            if (
                raw.ndim != 2
                or raw.shape[1] != math.prod(self.original_shape)
                or not np.isfinite(raw).all()
                or np.any(raw != np.floor(raw))
                or np.any(raw < 0)
                or np.any(raw >= self.output_dim)
            ):
                raise ValueError("integer in-vocabulary context matrix required")
            z = b.gather(p["adapter.embedding"], raw.astype(np.int32)) + p["adapter.position"]
            length, heads = z.shape[1], self.genome.adapter_heads
            q, k, v = [
                (z @ p["adapter." + part]).reshape((n, length, heads, width // heads)).transpose((0, 2, 1, 3))
                for part in ("q", "k", "v")
            ]
            # Every token is history; the scored target never enters this adapter.
            attention = b.softmax(q @ k.transpose((0, 1, 3, 2)) / math.sqrt(width // heads)) @ v
            attention = attention.transpose((0, 2, 1, 3)).reshape((n, length, width))
            return b.gather(z + attention @ p["adapter.out"], (slice(None), -1, slice(None)))
        h, w = self.original_shape
        pixels = x.reshape((n, h, w))
        channels = []
        for c in range(4):
            pieces = []
            for iy in range(3):
                for ix in range(3):
                    ys, xs = np.arange(h) + iy - 1, np.arange(w) + ix - 1
                    mask = (ys[:, None] >= 0) & (ys[:, None] < h) & (xs[None, :] >= 0) & (xs[None, :] < w)
                    shifted = b.gather(
                        b.gather(pixels, (slice(None), np.clip(ys, 0, h - 1))),
                        (slice(None), slice(None), np.clip(xs, 0, w - 1)),
                    )
                    pieces.append(shifted * b.array(mask) * p["adapter.kernel"][iy, ix, c])
            channels.append(b.activate(sum(pieces), "gelu").reshape((n, h * w)))
        return b.concatenate(channels) @ p["adapter.projection"]


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
    if genome.input_adapter == "flat":
        return compile_legacy(
            genome, input_shape, output_dim, modality, task, backend=backend, device=device, seed=seed
        )
    if not input_shape or any(type(v) is not int or v <= 0 for v in input_shape) or output_dim < 1:
        raise ValueError("positive model dimensions required")
    return AdaptedModel(genome, input_shape, output_dim, Backend(backend, device), seed, modality, task)
