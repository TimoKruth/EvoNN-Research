"""Primordia-owned dataset loading, with explicit runtime and cache provenance."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.metadata
import io
import os
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn import datasets as sklearn_datasets
from sklearn.model_selection import train_test_split

from evonn_shared.artifact_io import create_artifact_directory, publish_artifact, read_verified_artifact
from evonn_shared.benchmarks import resolve_data_root
from evonn_shared.canonical import canonical_sha256
from evonn_shared.catalog import BenchmarkSpec
from evonn_shared.active_catalog import get_benchmark
from evonn_shared.runtime_catalog import runtime_manifest
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
    if loader in {"openml_31", "openml_1462"}:
        import openml
        dataset_id = 31 if loader == "openml_31" else 1462
        target_name = "class" if loader == "openml_31" else "Class"
        dataset = openml.datasets.get_dataset(dataset_id, download_data=True)
        if dataset.default_target_attribute != target_name:
            raise ValueError("OpenML target changed")
        frame, target, _, _ = dataset.get_data(target=target_name)
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
    manifest_payload, manifest = runtime_manifest(benchmark_id, root=root)
    for package, version in manifest["versions"].items():
        if importlib.metadata.version(package) != version:
            raise ValueError(f"Dataset runtime version drift: {package}; expected {version}")
    binding = manifest["benchmarks"][benchmark_id]
    definition_digest = canonical_sha256(definition.model_dump(mode="json"),
                                        schema_version="evonn.catalog.benchmark/v1", digest_field=None)
    if definition_digest != binding["definition_sha256"]:
        raise ValueError("Runtime manifest and canonical benchmark definition disagree")
    if binding["loader"] == "shakespeare_bytes_v1":
        tokens = _text_tokens(binding, cache_root)
        raw_digest = array_digest({"tokens":tokens})
        arrays = _text_split(tokens, binding, seed)
    else:
        x, y = _raw_data(binding, seed)
        if x.ndim != 2 or x.shape[1] != int(np.prod(definition.input_shape)) or len(x) != len(y):
            raise ValueError("Dataset dimensions disagree with canonical definition")
        raw_digest = array_digest({"x": x, "y": y})
        arrays = _split(x, y, definition.task_kind.value, seed)
    generated = binding["loader"].startswith("make_")
    if not generated and raw_digest != binding["reference_raw_sha256"]:
        raise ValueError("Raw dataset differs from reviewed reference")
    split_digest = array_digest(arrays)
    if seed == 42 and split_digest != binding["reference_split_sha256"]:
        raise ValueError(f"Dataset split differs from reviewed reference: observed {split_digest}; expected {binding["reference_split_sha256"]}")
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
        "raw_sha256": raw_digest, "raw_reference_sha256": binding["reference_raw_sha256"],
        "raw_reference_match": raw_digest == binding["reference_raw_sha256"],
        "split_sha256": split_digest, "seed": seed,
        "split_policy": manifest["split_policy"], "cache_directory": str(cache.absolute()),
        "cache_artifacts": references, "checksums_verified_by": "evonn_shared.artifact_io",
        "catalog_status": definition.status.value, "runtime_ready": True,
        "scientific_qualification": False,
    }
    return Dataset(definition=definition, provenance=provenance, **validated)


def _text_tokens(binding, cache_root):
    root=cache_root/"_sources"
    create_artifact_directory(root)
    reference=ArtifactReference(path=binding["source_sha256"],sha256=binding["source_sha256"])
    try:
        payload=read_verified_artifact(root,reference,size_bytes=binding["source_size_bytes"])
    except FileNotFoundError:
        with urllib.request.urlopen(binding["source_url"],timeout=60) as response:
            payload=response.read(binding["source_size_bytes"]+1)
        if len(payload)!=binding["source_size_bytes"] or hashlib.sha256(payload).hexdigest()!=reference.sha256:
            raise ValueError("text source checksum/size drift")
        try:
            publish_artifact(root/reference.path,payload)
        except FileExistsError:
            pass
        payload=read_verified_artifact(root,reference,size_bytes=binding["source_size_bytes"])
    return np.frombuffer(payload,dtype=np.uint8).astype(np.int64)


def _text_split(tokens,binding,seed):
    # Split raw positions first. No overlapping windows cross train/validation/test.
    cut,held=(int(len(tokens)*fraction) for fraction in binding["split_fractions"])
    arrays={}
    for split,start,end,limit in [("train",0,cut,binding["train_limit"]),("validation",cut,held,binding["validation_limit"])]:
        positions=np.arange(start+binding["context"],end,binding["stride"])
        rng=np.random.default_rng(seed if split=="train" else 0)
        positions=np.sort(rng.choice(positions,size=min(limit,len(positions)),replace=False))
        arrays["x_"+split]=np.asarray([tokens[position-binding["context"]:position] for position in positions],dtype=np.float32)
        arrays["y_"+split]=tokens[positions]
    return arrays
