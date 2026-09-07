"""The eight historical datasets, with explicit runtime and cache provenance."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn import datasets as sklearn_datasets
from sklearn.model_selection import train_test_split

from evonn_shared.artifact_io import create_artifact_directory, publish_artifact, read_verified_artifact
from evonn_shared.benchmarks import resolve_data_root
from evonn_shared.canonical import canonical_sha256
from evonn_shared.catalog import BenchmarkSpec, get_benchmark
from evonn_shared.telemetry import ArtifactReference


RUNTIME_MANIFEST_SHA256 = "c649dbc90ee017a34fb91722e7e238baa56a8de30a068e81bd7998dcd1a924a4"


@dataclass(frozen=True)
class Dataset:
    definition: BenchmarkSpec
    x_train: np.ndarray
    y_train: np.ndarray
    x_validation: np.ndarray
    y_validation: np.ndarray
    provenance: dict


def shared_root() -> Path:
    value = os.environ.get("EVONN_SHARED_BENCHMARKS_DIR")
    if value == "":
        raise ValueError("EVONN_SHARED_BENCHMARKS_DIR must not be empty")
    return Path(value) if value is not None else resolve_data_root()


def array_digest(arrays: dict[str, np.ndarray]) -> str:
    return canonical_sha256(
        {name: {"dtype": array.dtype.str, "shape": tuple(array.shape),
                "bytes": np.ascontiguousarray(array).tobytes()} for name, array in arrays.items()},
        schema_version="evonn-dataset-arrays-v1", digest_field=None,
    )


def _raw_data(binding: dict, seed: int) -> tuple[np.ndarray, np.ndarray]:
    loader = binding["loader"]
    if loader == "openml_31":
        import openml
        dataset = openml.datasets.get_dataset(31, download_data=True)
        if dataset.default_target_attribute != "class":
            raise ValueError("OpenML 31 target changed")
        frame, target, _, _ = dataset.get_data(target="class")
        for column in frame.columns:
            if getattr(frame[column].dtype, "name", "") == "category" or frame[column].dtype == object:
                frame[column] = pd.Categorical(frame[column]).codes.astype(np.float32)
        x = np.nan_to_num(frame.to_numpy(dtype=np.float32, na_value=np.nan), nan=0.0)
        y = target.to_numpy()
        if y.dtype.kind in {"U", "S", "O"}:
            labels = {value: index for index, value in enumerate(sorted(set(y)))}
            y = np.asarray([labels[value] for value in y], dtype=np.int64)
        else:
            y = y.astype(np.int64, copy=False)
        return x, y
    loaders = {
        "load_iris": sklearn_datasets.load_iris, "load_wine": sklearn_datasets.load_wine,
        "load_breast_cancer": sklearn_datasets.load_breast_cancer,
        "load_digits": sklearn_datasets.load_digits, "load_diabetes": sklearn_datasets.load_diabetes,
    }
    if loader in loaders:
        data = loaders[loader]()
        return data.data, data.target
    if loader == "make_moons":
        return sklearn_datasets.make_moons(**binding["parameters"], random_state=seed)
    if loader == "make_friedman1":
        return sklearn_datasets.make_friedman1(**binding["parameters"], random_state=seed)
    raise ValueError(f"No runtime loader for {loader}")


def _split(x: np.ndarray, y: np.ndarray, task: str, seed: int) -> dict[str, np.ndarray]:
    train_x, validation_x, train_y, validation_y = train_test_split(
        x, y, test_size=0.2, random_state=seed, stratify=y if task == "classification" else None,
    )
    dtype = np.float32 if task == "regression" else np.int64
    return {"x_train": train_x.astype(np.float32), "y_train": train_y.astype(dtype),
            "x_validation": validation_x.astype(np.float32), "y_validation": validation_y.astype(dtype)}


def load_dataset(benchmark_id: str, *, seed: int, cache_root: Path, root: Path | None = None) -> Dataset:
    """Preserve canonical semantics; validate regenerated cache bytes before use.

    The reviewed seed-42 digests anchor reference behavior. Other seeds use the
    same pinned generator/split algorithm and record their distinct content IDs.
    Catalog metadata stays frozen; readiness is conveyed by this runtime proof.
    """
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("dataset seed must be an integer in [0, 2**32)")
    root = root if root is not None else shared_root()
    definition = get_benchmark(benchmark_id, shared_root=root)
    manifest_payload = read_verified_artifact(
        root, ArtifactReference(path="runtime/tier1_core_v1.json", sha256=RUNTIME_MANIFEST_SHA256),
        max_bytes=256 * 1024,
    )
    manifest = json.loads(manifest_payload)
    for package, version in manifest["versions"].items():
        if importlib.metadata.version(package) != version:
            raise ValueError(f"Dataset runtime version drift: {package}; expected {version}")
    binding = manifest["benchmarks"][benchmark_id]
    definition_digest = canonical_sha256(definition.model_dump(mode="json"),
                                        schema_version="evonn.catalog.benchmark/v1", digest_field=None)
    if definition_digest != binding["definition_sha256"]:
        raise ValueError("Runtime manifest and canonical benchmark definition disagree")
    x, y = _raw_data(binding, seed)
    if x.ndim != 2 or x.shape[1] != int(np.prod(definition.input_shape)) or len(x) != len(y):
        raise ValueError("Dataset dimensions disagree with canonical definition")
    raw_digest = array_digest({"x": x, "y": y})
    generated = binding["loader"].startswith("make_")
    if (not generated or seed == 42) and raw_digest != binding["reference_raw_sha256"]:
        raise ValueError("Raw dataset differs from reviewed reference")
    arrays = _split(x, y, definition.task_kind.value, seed)
    split_digest = array_digest(arrays)
    if seed == 42 and split_digest != binding["reference_split_sha256"]:
        raise ValueError("Dataset split differs from reviewed reference")
    cache = cache_root / benchmark_id / split_digest
    create_artifact_directory(cache)
    references = []
    validated = {}
    for name, array in arrays.items():
        buffer = io.BytesIO()
        np.save(buffer, array, allow_pickle=False)
        payload = buffer.getvalue()
        reference = ArtifactReference(path=name + ".npy", sha256=hashlib.sha256(payload).hexdigest())
        try:
            publish_artifact(cache / reference.path, payload)
        except FileExistsError:
            pass
        checked = read_verified_artifact(cache, reference, size_bytes=len(payload))
        validated[name] = np.load(io.BytesIO(checked), allow_pickle=False)
        references.append({**reference.model_dump(mode="json"), "size_bytes": len(payload)})
    provenance = {
        "benchmark_id": benchmark_id, "definition_sha256": definition_digest,
        "runtime_manifest_sha256": hashlib.sha256(manifest_payload).hexdigest(),
        "raw_sha256": raw_digest, "split_sha256": split_digest, "seed": seed,
        "split_policy": manifest["split_policy"], "cache_directory": str(cache.absolute()),
        "cache_artifacts": references, "checksums_verified_by": "evonn_shared.artifact_io",
        "catalog_status": definition.status.value, "runtime_ready": True,
        "scientific_qualification": False,
    }
    return Dataset(definition=definition, provenance=provenance, **validated)
