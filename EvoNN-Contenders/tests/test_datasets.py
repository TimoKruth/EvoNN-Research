import json
from pathlib import Path

import numpy as np
import pytest

from evonn_contenders.datasets import load_dataset, shared_root


@pytest.mark.parametrize("benchmark", ["iris_classification", "wine_classification", "breast_cancer",
    "moons_classification", "digits_image", "diabetes_regression", "friedman1_regression"])
def test_reviewed_legacy_split_and_verified_cache_replay(benchmark, tmp_path):
    first = load_dataset(benchmark, seed=42, cache_root=tmp_path)
    second = load_dataset(benchmark, seed=42, cache_root=tmp_path)
    for name in ("x_train", "y_train", "x_validation", "y_validation"):
        assert np.array_equal(getattr(first, name), getattr(second, name))
    binding = json.loads((shared_root() / "runtime/tier1_core_v1.json").read_text())["benchmarks"][benchmark]
    assert first.provenance["split_sha256"] == binding["reference_split_sha256"]
    assert first.x_train.dtype == np.float32
    assert first.provenance["catalog_status"] == "planned"
    assert first.provenance["runtime_ready"] is True


def test_corrupt_cache_is_rejected_without_repair(tmp_path):
    dataset = load_dataset("iris_classification", seed=42, cache_root=tmp_path)
    path = Path(dataset.provenance["cache_directory"]) / "x_train.npy"
    payload = path.read_bytes()
    path.write_bytes(payload[:-1] + bytes([payload[-1] ^ 1]))
    corrupted = path.read_bytes()
    with pytest.raises(ValueError, match="content mismatch"):
        load_dataset("iris_classification", seed=42, cache_root=tmp_path)
    assert path.read_bytes() == corrupted


def test_seed_changes_split_without_changing_canonical_definition(tmp_path):
    first = load_dataset("iris_classification", seed=42, cache_root=tmp_path)
    second = load_dataset("iris_classification", seed=43, cache_root=tmp_path)
    assert first.provenance["definition_sha256"] == second.provenance["definition_sha256"]
    assert first.provenance["raw_sha256"] == second.provenance["raw_sha256"]
    assert first.provenance["split_sha256"] != second.provenance["split_sha256"]


@pytest.mark.parametrize("name", ["moons_classification", "friedman1_regression"])
def test_generated_intermediates_may_differ_only_when_consumed_bytes_are_identical(tmp_path, monkeypatch, name):
    from evonn_contenders import datasets
    original = datasets._raw_data
    reference = datasets.load_dataset(name, seed=42, cache_root=tmp_path / "reference")
    def intermediate(binding, seed):
        x, y = original(binding, seed)
        x[0, 0] = np.nextafter(x[0, 0], np.inf)
        return x, y
    monkeypatch.setattr(datasets, "_raw_data", intermediate)
    reproduced = datasets.load_dataset(name, seed=42, cache_root=tmp_path / "reproduced")
    assert reproduced.provenance["raw_reference_match"] is False
    assert reproduced.provenance["split_sha256"] == reference.provenance["split_sha256"]
    def consumed_change(binding, seed):
        x, y = original(binding, seed)
        x[0, 0] += .01
        return x, y
    monkeypatch.setattr(datasets, "_raw_data", consumed_change)
    with pytest.raises(ValueError, match="split|Split"):
        datasets.load_dataset(name, seed=42, cache_root=tmp_path / "altered")
