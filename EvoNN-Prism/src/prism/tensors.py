"""Small reverse-mode NumPy substrate and explicit MLX dispatch.

Only numerical operations live here; genomes and search policies belong to engines.
The fallback differentiates the actual compiled model, including STE quantizers.
"""

from __future__ import annotations
import importlib.metadata
import platform
import numpy as np


def _unbroadcast(value, shape):
    while value.ndim > len(shape):
        value = value.sum(axis=0)
    for axis, size in enumerate(shape):
        if size == 1:
            value = value.sum(axis=axis, keepdims=True)
    return value.reshape(shape)


class Tensor:
    __array_priority__ = 1000

    def __init__(self, data, parents=()):
        self.data = np.asarray(data, dtype=np.float32)
        self.parents = parents
        self.grad = None

    @property
    def shape(self):
        return self.data.shape

    @property
    def ndim(self):
        return self.data.ndim

    def __add__(self, other):
        other = tensor(other)
        return Tensor(
            self.data + other.data,
            ((self, lambda g: _unbroadcast(g, self.shape)), (other, lambda g: _unbroadcast(g, other.shape))),
        )

    __radd__ = __add__

    def __neg__(self):
        return self * -1

    def __sub__(self, other):
        return self + -tensor(other)

    def __rsub__(self, other):
        return tensor(other) - self

    def __mul__(self, other):
        other = tensor(other)
        return Tensor(
            self.data * other.data,
            (
                (self, lambda g: _unbroadcast(g * other.data, self.shape)),
                (other, lambda g: _unbroadcast(g * self.data, other.shape)),
            ),
        )

    __rmul__ = __mul__

    def __pow__(self, power):
        return Tensor(self.data**power, ((self, lambda g: g * power * self.data ** (power - 1)),))

    def __truediv__(self, other):
        return self * tensor(other) ** -1

    def __rtruediv__(self, other):
        return tensor(other) * self**-1

    def __matmul__(self, other):
        other = tensor(other)
        return Tensor(
            self.data @ other.data,
            (
                (self, lambda g: _unbroadcast(g @ np.swapaxes(other.data, -1, -2), self.shape)),
                (other, lambda g: _unbroadcast(np.swapaxes(self.data, -1, -2) @ g, other.shape)),
            ),
        )

    def reshape(self, shape):
        return Tensor(self.data.reshape(shape), ((self, lambda g: g.reshape(self.shape)),))

    def transpose(self, axes):
        inverse = tuple(np.argsort(axes))
        return Tensor(self.data.transpose(axes), ((self, lambda g: g.transpose(inverse)),))

    def sum(self, axis=None, keepdims=False):
        axes = tuple(range(self.ndim)) if axis is None else ((axis,) if isinstance(axis, int) else axis)
        axes = tuple(a % self.ndim for a in axes)

        def back(g):
            if not keepdims:
                for a in sorted(axes):
                    g = np.expand_dims(g, a)
            return np.broadcast_to(g, self.shape)

        return Tensor(self.data.sum(axis=axis, keepdims=keepdims), ((self, back),))

    def mean(self, axis=None, keepdims=False):
        count = (
            self.data.size
            if axis is None
            else np.prod([self.shape[a] for a in ((axis,) if isinstance(axis, int) else axis)])
        )
        return self.sum(axis, keepdims) / float(count)

    def __getitem__(self, index):
        def back(g):
            result = np.zeros_like(self.data)
            np.add.at(result, index, g)
            return result

        return Tensor(self.data[index], ((self, back),))

    def backward(self):
        ordered, seen = [], set()

        def visit(node):
            if id(node) not in seen:
                seen.add(id(node))
                for parent, _ in node.parents:
                    visit(parent)
                ordered.append(node)

        visit(self)
        for node in ordered:
            node.grad = np.zeros_like(node.data)
        self.grad = np.ones_like(self.data)
        for node in reversed(ordered):
            for parent, gradient in node.parents:
                parent.grad += gradient(node.grad)


def tensor(value):
    return value if isinstance(value, Tensor) else Tensor(value)


class Backend:
    def __init__(self, name="numpy_fallback", device="cpu"):
        if name not in {"numpy_fallback", "mlx_native"} or device not in {"cpu", "gpu"}:
            raise ValueError("explicit supported backend and device required")
        if name == "numpy_fallback" and device != "cpu":
            raise ValueError("NumPy fallback supports CPU only")
        self.name, self.device = name, device
        self.mx = None
        if name == "mlx_native":
            if platform.system() != "Darwin" or platform.machine() != "arm64":
                raise ValueError("mlx_native requires Apple Silicon")
            import mlx.core as mx

            self.mx = mx
            mx.set_default_device(mx.cpu if device == "cpu" else mx.gpu)
        self.version = importlib.metadata.version("numpy" if self.mx is None else "mlx")

    def array(self, value):
        return tensor(value) if self.mx is None else self.mx.array(value, dtype=self.mx.float32)

    def numpy(self, value):
        return value.data if isinstance(value, Tensor) else np.asarray(value)

    def stop(self, value):
        return Tensor(value.data) if self.mx is None else self.mx.stop_gradient(value)

    def exp(self, value):
        if self.mx is not None:
            return self.mx.exp(value)
        result = np.exp(value.data)
        return Tensor(result, ((value, lambda g: g * result),))

    def log(self, value):
        if self.mx is not None:
            return self.mx.log(value)
        return Tensor(np.log(value.data), ((value, lambda g: g / value.data),))

    def tanh(self, value):
        if self.mx is not None:
            return self.mx.tanh(value)
        result = np.tanh(value.data)
        return Tensor(result, ((value, lambda g: g * (1 - result * result)),))

    def sigmoid(self, value):
        return (self.tanh(value * 0.5) + 1) * 0.5

    def relu(self, value):
        if self.mx is not None:
            return self.mx.maximum(value, 0)
        return Tensor(np.maximum(value.data, 0), ((value, lambda g: g * (value.data > 0)),))

    def activate(self, value, name):
        if name == "relu":
            return self.relu(value)
        if name == "tanh":
            return self.tanh(value)
        if name == "silu":
            return value * self.sigmoid(value)
        if name == "gelu":
            return 0.5 * value * (1 + self.tanh(0.7978845608 * (value + 0.044715 * value**3)))
        raise ValueError("unknown activation")

    def softmax(self, value):
        # Max subtraction is a shift only; its derivative cancels in softmax.
        maximum = self.array(self.numpy(value).max(axis=-1, keepdims=True))
        exponent = self.exp(value - maximum)
        return exponent / exponent.sum(axis=-1, keepdims=True)

    def gather(self, value, index):
        if self.mx is not None:
            if isinstance(index, tuple):
                index = tuple(self.mx.array(i, dtype=self.mx.int32) if isinstance(i, np.ndarray) else i for i in index)
            elif isinstance(index, np.ndarray):
                index = self.mx.array(index, dtype=self.mx.int32)
        return value[index]

    def concatenate(self, values, axis=-1):
        if self.mx is not None:
            return self.mx.concatenate(values, axis=axis)
        axis %= values[0].ndim
        offset, parents = 0, []
        for value in values:
            selection = [slice(None)] * value.ndim
            selection[axis] = slice(offset, offset + value.shape[axis])
            selection = tuple(selection)
            parents.append((value, lambda g, index=selection: g[index]))
            offset += value.shape[axis]
        return Tensor(np.concatenate([v.data for v in values], axis=axis), tuple(parents))

    def norm(self, value, kind="layer"):
        if kind == "none":
            return value
        axes = tuple(range(value.ndim - 1)) if kind == "batch" else -1
        centered = value if kind == "rms" else value - value.mean(axis=axes, keepdims=True)
        return centered / (centered**2).mean(axis=axes, keepdims=True).__add__(1e-5).__pow__(0.5)

    def quantize(self, value, bits):
        raw = self.numpy(value)
        if bits == 16:
            quantized = raw.astype(np.float16).astype(np.float32)
        elif bits == 1.58:
            scale = max(float(np.mean(np.abs(raw))), 1e-8)
            quantized = np.clip(np.round(raw / scale), -1, 1) * scale
        elif bits in {4, 8}:
            levels = 2 ** (bits - 1) - 1
            scale = max(float(np.max(np.abs(raw))) / levels, 1e-8)
            quantized = np.clip(np.round(raw / scale), -levels, levels) * scale
        elif bits == 32:
            return value
        else:
            raise ValueError("unsupported precision")
        return value + self.stop(self.array(quantized) - value)

    def gradients(self, forward, parameters):
        if self.mx is not None:
            loss, gradients = self.mx.value_and_grad(forward)(parameters)
            import mlx.core as mx_sync

            mx_sync.eval(loss, gradients)
            return float(loss.item()), {k: np.asarray(v) for k, v in gradients.items()}
        loss = forward(parameters)
        loss.backward()
        return float(loss.data), {
            k: np.zeros_like(v.data) if v.grad is None else v.grad.copy() for k, v in parameters.items()
        }
