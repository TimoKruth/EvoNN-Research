import numpy as np
import pytest
from prism.tensors import Backend


def test_reverse_mode_matches_finite_difference_with_broadcast_and_gathers():
    b = Backend()
    rng = np.random.default_rng(1)
    raw = rng.normal(size=(3, 2)).astype("f")
    x = rng.normal(size=(4, 3)).astype("f")

    def loss(p):
        z = b.tanh(b.array(x) @ p["w"])
        return (b.gather(z, (np.array([1, 1, 3]), slice(None))) ** 2).mean()

    value, grads = b.gradients(loss, {"w": b.array(raw)})
    for i in np.ndindex(raw.shape):
        high = raw.copy()
        low = raw.copy()
        high[i] += 0.002
        low[i] -= 0.002
        finite = (float(b.numpy(loss({"w": b.array(high)}))) - float(b.numpy(loss({"w": b.array(low)})))) / 0.004
        assert grads["w"][i] == pytest.approx(finite, abs=5e-5)


@pytest.mark.parametrize("bits", [1.58, 4, 8, 16])
def test_quantization_values_and_identity_ste(bits):
    b = Backend()
    raw = np.array([[-0.9, 0, 0.4], [0.1, -0.3, 0.8]], dtype="f")
    _, grads = b.gradients(lambda p: b.quantize(p["w"], bits).sum(), {"w": b.array(raw)})
    np.testing.assert_array_equal(grads["w"], np.ones_like(raw))
    assert np.isfinite(b.numpy(b.quantize(b.array(np.zeros((2, 2))), bits))).all()
    if bits == 1.58:
        assert len(np.unique(b.numpy(b.quantize(b.array(raw), bits)))) <= 3
