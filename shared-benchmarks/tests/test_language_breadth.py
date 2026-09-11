import hashlib
from pathlib import Path

import numpy as np

from evonn_shared.active_catalog import get_benchmark, load_parity_pack
from evonn_shared.canonical import canonical_sha256
from evonn_shared.datasets import _text_split, _text_tokens, load_dataset
from evonn_shared.runtime_catalog import runtime_manifest, CORE_RUNTIME_SHA256, PHASE4_RUNTIME_SHA256


ROOT = Path(__file__).resolve().parents[1]


def test_additive_breadth_definitions_are_pinned_without_changing_historical_runtime():
    assert hashlib.sha256((ROOT / "runtime/tier1_core_v1.json").read_bytes()).hexdigest() == CORE_RUNTIME_SHA256
    assert hashlib.sha256((ROOT / "runtime/phase4_v1.json").read_bytes()).hexdigest() == PHASE4_RUNTIME_SHA256
    pack = load_parity_pack("language_breadth_v1")
    assert "shakespeare_byte_lm" in pack.benchmarks
    assert not pack.full_fidelity_local_safe
    for name in pack.benchmarks:
        definition = get_benchmark(name)
        _, manifest = runtime_manifest(name)
        assert canonical_sha256(definition.model_dump(mode="json"), schema_version="evonn.catalog.benchmark/v1",
                                digest_field=None) == manifest["benchmarks"][name]["definition_sha256"]


def test_text_windows_never_cross_splits_or_consume_protected_test():
    _, manifest = runtime_manifest("aesop_context64_lm")
    binding = manifest["benchmarks"]["aesop_context64_lm"]
    tokens = np.arange(5000)
    a, b = (_text_split(tokens, binding, seed) for seed in (42, 43))
    assert a["x_train"].max() < 3500 and a["y_train"].max() < 3500
    assert a["x_validation"].min() >= 3500
    assert a["x_validation"].max() < 4250 and a["y_validation"].max() < 4250
    np.testing.assert_array_equal(a["x_validation"], b["x_validation"])
    np.testing.assert_array_equal(a["y_validation"], b["y_validation"])


def test_corpus_wrapper_is_excluded_by_pinned_byte_range(tmp_path):
    payload = b"HEADER-actual corpus-FOOTER"
    sha = hashlib.sha256(payload).hexdigest()
    (tmp_path / "_sources").mkdir()
    (tmp_path / "_sources" / sha).write_bytes(payload)
    binding = {"source_sha256": sha, "source_size_bytes": len(payload), "content_byte_range": [7, 20]}
    assert bytes(_text_tokens(binding, tmp_path).astype(np.uint8)) == b"actual corpus"


def test_memory_target_requires_the_first_token_and_has_reproducible_splits(tmp_path):
    a = load_dataset("delayed_copy_lm", seed=42, cache_root=tmp_path)
    b = load_dataset("delayed_copy_lm", seed=42, cache_root=tmp_path)
    c = load_dataset("delayed_copy_lm", seed=43, cache_root=tmp_path)
    assert a.x_train.shape == (1638, 64)
    np.testing.assert_array_equal(a.y_train, a.x_train[:, 0])
    np.testing.assert_array_equal(a.y_validation, a.x_validation[:, 0])
    assert np.mean(a.y_validation == a.x_validation[:, -1]) < .15
    assert a.provenance["split_sha256"] == b.provenance["split_sha256"] != c.provenance["split_sha256"]
