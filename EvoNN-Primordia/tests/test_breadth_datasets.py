"""Owned loader parity, pinned corpus boundaries and corruption rejection."""

from copy import deepcopy
import hashlib
import json

import numpy as np
import pytest

from evonn_primordia import datasets as owned
from evonn_shared import datasets as shared

ARRAYS = ("x_train", "y_train", "x_validation", "y_validation")


def assert_parity(first, second):
    for name in ARRAYS:
        np.testing.assert_array_equal(getattr(first, name), getattr(second, name))
    assert first.provenance == second.provenance


@pytest.mark.parametrize("seed", [42, 1003, 1004])
def test_delayed_copy_matches_reviewed_shared_loader(seed, tmp_path):
    expected = shared.load_dataset("delayed_copy_lm", seed=seed, cache_root=tmp_path)
    observed = owned.load_dataset("delayed_copy_lm", seed=seed, cache_root=tmp_path)
    assert_parity(observed, expected)
    np.testing.assert_array_equal(observed.y_train, observed.x_train[:, 0])
    np.testing.assert_array_equal(observed.y_validation, observed.x_validation[:, 0])


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    # Exercise the actual catalog definition and byte-corpus branch with an
    # offline source. Production corpus hashes are checked by the bounded audit.
    _, original = shared.runtime_manifest("aesop_context64_lm", root=shared.shared_root())
    manifest = deepcopy(original)
    binding = manifest["benchmarks"]["aesop_context64_lm"]
    payload = bytes((i % 53 + 65) for i in range(4096))
    binding.update(
        source_sha256=hashlib.sha256(payload).hexdigest(), source_size_bytes=len(payload), content_byte_range=[53, 3000]
    )
    sources = tmp_path / "_sources"
    sources.mkdir()
    path = sources / binding["source_sha256"]
    path.write_bytes(payload)
    tokens = np.frombuffer(payload[53:3000], dtype=np.uint8).astype(np.int64)
    binding["reference_raw_sha256"] = shared.array_digest({"tokens": tokens})
    binding["reference_split_sha256"] = shared.array_digest(shared._text_split(tokens, binding, 42))
    document = json.dumps(manifest, sort_keys=True).encode()
    for module in (shared, owned):
        monkeypatch.setattr(module, "runtime_manifest", lambda *a, **k: (document, manifest))
    return binding, path, payload


@pytest.mark.parametrize("seed", [42, 1003, 1004])
def test_byte_corpus_matches_split_and_provenance_after_pinned_crop(corpus, seed, tmp_path):
    binding, _, payload = corpus
    np.testing.assert_array_equal(
        owned._text_tokens(binding, tmp_path), np.frombuffer(payload[53:3000], dtype=np.uint8)
    )
    expected = shared.load_dataset("aesop_context64_lm", seed=seed, cache_root=tmp_path)
    observed = owned.load_dataset("aesop_context64_lm", seed=seed, cache_root=tmp_path)
    assert_parity(observed, expected)
    assert observed.provenance["raw_reference_match"]


@pytest.mark.parametrize("bounds", [[True, 3000], [0.0, 3000], [-1, 3000], [20, 20], [20, 4097]])
def test_invalid_corpus_byte_range_is_rejected(corpus, bounds, tmp_path):
    binding, _, _ = corpus
    with pytest.raises(ValueError, match="pinned corpus byte range"):
        owned._text_tokens({**binding, "content_byte_range": bounds}, tmp_path)


def test_corrupt_source_is_rejected_before_crop_without_repair(corpus, tmp_path):
    binding, path, payload = corpus
    changed = b"!" + payload[1:]
    path.write_bytes(changed)
    with pytest.raises(ValueError, match="mismatch"):
        owned._text_tokens(binding, tmp_path)
    assert path.read_bytes() == changed


def test_corrupt_generated_cache_is_rejected_without_repair(tmp_path):
    dataset = owned.load_dataset("delayed_copy_lm", seed=42, cache_root=tmp_path)
    from pathlib import Path

    path = Path(dataset.provenance["cache_directory"]) / "x_train.npy"
    original = path.read_bytes()
    changed = original[:-1] + bytes([original[-1] ^ 1])
    path.write_bytes(changed)
    with pytest.raises(ValueError, match="mismatch"):
        owned.load_dataset("delayed_copy_lm", seed=42, cache_root=tmp_path)
    assert path.read_bytes() == changed
