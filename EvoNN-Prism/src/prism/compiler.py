"""Family compiler: the same differentiable architecture on MLX and NumPy."""

import math
import numpy as np
from .tensors import Backend
from .genome import compatible_families


class FamilyModel:
    def __init__(self, genome, input_shape, output_dim, modality, task, backend, seed, vocab_size=None):
        self.genome, self.input_shape, self.output_dim = genome, tuple(input_shape), output_dim
        self.modality, self.task, self.backend = modality, task, backend
        self.token_input = modality == "text"
        self.weights = {}
        self.buffers = {}
        rng = np.random.default_rng(seed)

        def weight(name, shape):
            self.weights[name] = (rng.standard_normal(shape) * math.sqrt(2 / shape[0])).astype(np.float32)

        def linear(name, incoming, outgoing):
            weight(name + ".w", (incoming, outgoing))
            self.weights[name + ".b"] = np.zeros(outgoing, np.float32)

        g, family = genome, genome.family
        if family in {"mlp", "sparse_mlp", "moe_mlp"}:
            incoming = math.prod(input_shape)
        elif "conv" in family:
            incoming = input_shape[-1] if len(input_shape) == (3 if "2d" in family else 2) else 1
        else:
            incoming = g.embedding_dim
            if self.token_input:
                weight("embedding", (vocab_size if vocab_size is not None else output_dim, incoming))
            else:
                linear("input", input_shape[-1] if len(input_shape) > 1 else 1, incoming)
        self.layer_names = []
        for i, width in enumerate(g.hidden_layers):
            name = f"layer{i}"
            self.layer_names.append(name)
            if "conv" in family:
                spatial = g.kernel_size ** (2 if "2d" in family else 1)
                if family.startswith("lite"):
                    weight(name + ".depthwise", (spatial, incoming))
                    linear(name, incoming, width)
                else:
                    linear(name, spatial * incoming, width)
                incoming = width
            elif family == "moe_mlp":
                linear(name + ".gate", incoming, g.num_experts)
                for e in range(g.num_experts):
                    linear(name + f".expert{e}", incoming, width)
                incoming = width
            elif family in {"mlp", "sparse_mlp"}:
                linear(name, incoming, width)
                incoming = width
            elif family == "gru":
                for gate in ("z", "r", "h"):
                    linear(name + "." + gate, incoming + width, width)
                incoming = width
            elif "state_space" in family:
                linear(name + ".input", incoming, width)
                self.weights[name + ".decay"] = rng.normal(0, 0.2, width).astype(np.float32)
                if family == "gated_state_space":
                    linear(name + ".gate", incoming, width)
                incoming = width
            elif family in {"attention", "sparse_attention", "causal_transformer"}:
                heads = g.num_heads
                kv_width = incoming // heads * (g.kv_heads if family == "causal_transformer" else heads)
                linear(name + ".q", incoming, incoming)
                linear(name + ".k", incoming, kv_width)
                linear(name + ".v", incoming, kv_width)
                linear(name + ".out", incoming, incoming)
                linear(name + ".ff1", incoming, width * g.ffn_ratio)
                linear(name + ".ff2", width * g.ffn_ratio, incoming)
            else:  # pointwise embedding network remains causal
                linear(name, incoming, width)
                incoming = width
        linear("head", incoming, output_dim)

    @property
    def parameter_count(self):
        return sum(v.size for v in self.weights.values())

    def forward(self, p, x, *, training=False, seed=0, return_features=False):
        b, g, family = self.backend, self.genome, self.genome.family
        rng = np.random.default_rng(seed)

        def linear(name, value):
            return value @ p[name + ".w"] + p[name + ".b"]

        def sparse(value):
            raw = np.abs(b.numpy(value))
            keep = max(1, int(raw.shape[-1] * (1 - g.activation_sparsity)))
            threshold = np.sort(raw, axis=-1)[..., -keep : -keep + 1] if keep > 1 else np.sort(raw, axis=-1)[..., -1:]
            return value * b.array(raw >= threshold)

        def finish(value):
            if g.norm_type == "batch":
                axes = tuple(range(value.ndim - 1))
                if training:
                    mean = value.mean(axis=axes, keepdims=True)
                    variance = ((value - mean) ** 2).mean(axis=axes, keepdims=True)
                    old = self.buffers[name] if name in self.buffers else None
                    observed = (b.numpy(mean).copy(), b.numpy(variance).copy())
                    self.buffers[name] = (
                        observed if old is None else tuple(0.9 * a + 0.1 * c for a, c in zip(old, observed))
                    )
                else:
                    stats = (
                        self.buffers[name]
                        if name in self.buffers
                        else (np.zeros(value.shape[-1]), np.ones(value.shape[-1]))
                    )
                    mean, variance = (b.array(v) for v in stats)
                value = (value - mean) / (variance + 1e-5) ** 0.5
            else:
                value = b.norm(value, g.norm_type)
            value = b.activate(value, g.activation)
            if training and g.dropout:
                value = value * b.array((rng.random(value.shape) >= g.dropout) / (1 - g.dropout))
            return value

        if family in {"mlp", "sparse_mlp", "moe_mlp"}:
            x = x.reshape((x.shape[0], -1))
        elif "conv2d" in family:
            shape = self.input_shape if len(self.input_shape) == 3 else (*self.input_shape, 1)
            x = x.reshape((x.shape[0], *shape))
        elif "conv1d" in family:
            x = x.reshape((x.shape[0], self.input_shape[0], -1))
        elif self.token_input:
            x = b.gather(p["embedding"], b.numpy(x).astype(np.int64))
        else:
            x = linear("input", x.reshape((x.shape[0], self.input_shape[0], -1)))
        if family in {"attention", "sparse_attention", "causal_transformer"} and g.position_encoding == "sinusoidal":
            positions = np.arange(x.shape[1])[:, None]
            frequencies = np.exp(-np.arange(x.shape[-1]) * math.log(10000) / x.shape[-1])
            encoding = np.where(
                np.arange(x.shape[-1]) % 2, np.cos(positions * frequencies), np.sin(positions * frequencies)
            )
            x = x + b.array(encoding)
        for name in self.layer_names:
            if "conv" in family:
                radius = g.kernel_size // 2
                offsets = (
                    [(dy, dx) for dy in range(-radius, radius + 1) for dx in range(-radius, radius + 1)]
                    if "2d" in family
                    else [(d,) for d in (range(1 - g.kernel_size, 1) if self.task == "language_modeling"
                                        else range(-radius, radius + 1))]
                )
                patches = []
                # Zero-padding expressed as masked gathers preserves input gradients.
                for offset in offsets:
                    value = x
                    for axis, delta in enumerate(offset, 1):
                        positions = np.arange(x.shape[axis]) + delta
                        valid = (positions >= 0) & (positions < x.shape[axis])
                        index = [slice(None)] * x.ndim
                        index[axis] = np.clip(positions, 0, x.shape[axis] - 1)
                        value = b.gather(value, tuple(index))
                        shape = [1] * x.ndim
                        shape[axis] = len(valid)
                        value = value * b.array(valid.reshape(shape))
                    patches.append(value)
                if family.startswith("lite"):
                    x = sum(value * p[name + ".depthwise"][i] for i, value in enumerate(patches))
                else:
                    x = b.concatenate(patches)
                x = finish(linear(name, x))
            elif family == "moe_mlp":
                logits = linear(name + ".gate", x)
                raw = b.numpy(logits)
                selected = np.argsort(raw, axis=-1)[..., -g.moe_top_k :]
                mask = np.zeros_like(raw)
                np.put_along_axis(mask, selected, 1, axis=-1)
                gates = b.softmax(logits) * b.array(mask)
                experts = [linear(name + f".expert{e}", x) * gates[..., e : e + 1] for e in range(g.num_experts)]
                x = finish(sum(experts))
            elif family == "gru":
                width = p[name + ".h.b"].shape[0]
                h, states = b.array(np.zeros((x.shape[0], width))), []
                for t in range(x.shape[1]):
                    joined = b.concatenate([x[:, t], h])
                    z, r = b.sigmoid(linear(name + ".z", joined)), b.sigmoid(linear(name + ".r", joined))
                    candidate = b.tanh(linear(name + ".h", b.concatenate([x[:, t], h * r])))
                    h = (1 - z) * h + z * candidate
                    states.append(h.reshape((x.shape[0], 1, width)))
                x = finish(b.concatenate(states, axis=1))
            elif "state_space" in family:
                projected = linear(name + ".input", x)
                decay = b.sigmoid(p[name + ".decay"])
                state, states = b.array(np.zeros((x.shape[0], projected.shape[-1]))), []
                gate = b.sigmoid(linear(name + ".gate", x)) if family == "gated_state_space" else None
                for t in range(x.shape[1]):
                    state = decay * state + (1 - decay) * projected[:, t]
                    value = state if gate is None else state * gate[:, t]
                    states.append(value.reshape((x.shape[0], 1, value.shape[-1])))
                x = finish(b.concatenate(states, axis=1))
                if family == "sparse_state_space":
                    x = sparse(x)
            elif family in {"attention", "sparse_attention", "causal_transformer"}:
                n, length, width = x.shape
                h, d = g.num_heads, width // g.num_heads
                kvh = g.kv_heads if family == "causal_transformer" else h
                q = linear(name + ".q", x).reshape((n, length, h, d)).transpose((0, 2, 1, 3))
                k = linear(name + ".k", x).reshape((n, length, kvh, d)).transpose((0, 2, 1, 3))
                v = linear(name + ".v", x).reshape((n, length, kvh, d)).transpose((0, 2, 1, 3))
                if g.position_encoding == "rope":
                    angle = np.arange(length)[:, None] / (10000 ** (np.arange(0, d, 2) / d))

                    def rotate(value):
                        a, c = value[..., : d // 2], value[..., d // 2 :]
                        return b.concatenate(
                            [
                                a * b.array(np.cos(angle)) - c * b.array(np.sin(angle)),
                                a * b.array(np.sin(angle)) + c * b.array(np.cos(angle)),
                            ]
                        )

                    q, k = rotate(q), rotate(k)
                if kvh != h:
                    k = b.concatenate([k[:, i : i + 1] for i in range(kvh) for _ in range(h // kvh)], axis=1)
                    v = b.concatenate([v[:, i : i + 1] for i in range(kvh) for _ in range(h // kvh)], axis=1)
                logits = q @ k.transpose((0, 1, 3, 2)) / math.sqrt(d)
                if self.task == "language_modeling" or family == "causal_transformer":
                    logits = logits + b.array(np.triu(np.full((length, length), -1e9), 1))
                attended = (b.softmax(logits) @ v).transpose((0, 2, 1, 3)).reshape((n, length, width))
                x = x + linear(name + ".out", attended)
                x = finish(x + linear(name + ".ff2", b.activate(linear(name + ".ff1", x), g.activation)))
                if family == "sparse_attention":
                    x = sparse(x)
            else:
                old = x
                x = finish(linear(name, x))
                if g.residual and old.shape == x.shape:
                    x = x + old
                if family == "sparse_mlp":
                    x = sparse(x)
        if return_features:
            return x
        if x.ndim > 2 and self.task != "language_modeling":
            x = x.mean(axis=tuple(range(1, x.ndim - 1)))
        return linear("head", x)


def compile_genome(
    genome,
    input_shape,
    output_dim,
    modality,
    task="classification",
    *,
    backend="numpy_fallback",
    device="cpu",
    seed=0,
    vocab_size=None,
):
    if modality == "text" and task != "language_modeling" and (type(vocab_size) is not int or vocab_size < 2):
        raise ValueError("text classification requires explicit vocab_size separate from output_dim")
    if task == "language_modeling" and genome.norm_type == "batch":
        raise ValueError("batch normalization is not causal; choose layer/rms/none for LM")
    if genome.family not in compatible_families(modality, task):
        raise ValueError("family incompatible with modality/task")
    if not input_shape or any(type(d) is not int or d <= 0 for d in input_shape) or output_dim < 1:
        raise ValueError("positive model dimensions required")
    if "conv2d" in genome.family and len(input_shape) not in {2, 3}:
        raise ValueError("image convolution requires spatial shape")
    if genome.family == "composite":
        from .composition import CompositeModel
        return CompositeModel(genome, input_shape, output_dim, modality, task, Backend(backend, device), seed, vocab_size)
    return FamilyModel(genome, input_shape, output_dim, modality, task, Backend(backend, device), seed, vocab_size)
