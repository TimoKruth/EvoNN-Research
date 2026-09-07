"""Tiny optional fixtures exercise image and causal LM floors, never benchmark claims."""
import numpy as np
import pytest

torch = pytest.importorskip("torch")
from evonn_contenders.models import build_model  # noqa: E402


def test_optional_image_and_lm_fit_heldout_and_invalid_targets():
    prior_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        rng = np.random.default_rng(42)
        y = np.repeat(np.array([0, 1], dtype=np.int64), 8)
        x = (y[:, None] + rng.normal(0, .05, (16, 64))).astype(np.float32)
        heldout = (y[:, None] + rng.normal(0, .05, (16, 64))).astype(np.float32)
        assert not set(map(tuple, x)) & set(map(tuple, heldout))
        cnn = build_model("cnn_small", task="classification", seed=42, input_shape=(64,), train_rows=16,
                          output_dim=2, parameters={"epochs": 3, "batch_size": 8})
        cnn.fit(x, y)
        assert cnn.mean == float(x.mean())
        assert (cnn.predict(heldout) == y).mean() >= .9
        # A binary transition process emits the opposite of its last token.
        contexts = np.array([[0, a, b] for a in (0, 1) for b in (0, 1)] * 4, dtype=np.int64)
        validation = np.array([[1, a, b] for a in (0, 1) for b in (0, 1)], dtype=np.int64)
        targets, validation_targets = 1 - contexts[:, -1], 1 - validation[:, -1]
        assert not set(map(tuple, contexts)) & set(map(tuple, validation))
        lm = build_model("transformer_lm_tiny", task="language_modeling", seed=42, input_shape=(3,), train_rows=16,
                         output_dim=2, parameters={"epochs": 3, "batch_size": 8})
        lm.fit(contexts, targets)
        assert lm.perplexity(validation, validation_targets) < 1.5
        with pytest.raises(ValueError, match="held-out"):
            lm.perplexity(validation, np.array([-1] * 4))
    finally:
        torch.set_num_threads(prior_threads)
