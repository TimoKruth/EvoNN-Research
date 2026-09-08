"""Read-only ingestion of complete portable export bundles."""
from dataclasses import dataclass
import os
from pathlib import Path

from ._run_io import open_directory, open_regular_at
from .artifact_io import read_verified_artifact
from .active_catalog import get_benchmark, load_parity_pack
from .exports import Manifest, Results, RunSummary, _validate_cross_file


def read_document(root: Path, name: str, *, limit: int = 16 * 1024 * 1024) -> bytes:
    """Read one bounded regular file without following symlinks."""
    with open_directory(root) as directory, open_regular_at(directory, name) as descriptor:
        if os.fstat(descriptor).st_size > limit:
            raise ValueError(f"document exceeds limit: {name}")
        pieces, count = [], 0
        while chunk := os.read(descriptor, min(1024 * 1024, limit + 1 - count)):
            count += len(chunk)
            if count > limit:
                raise ValueError(f"document exceeds limit: {name}")
            pieces.append(chunk)
    return b"".join(pieces)


@dataclass(frozen=True)
class ExportBundle:
    root: Path
    manifest: Manifest
    results: Results
    summary: RunSummary


def validate_canonical_results(manifest: Manifest, results: Results, *, shared_root: Path | None = None) -> None:
    pack = load_parity_pack(manifest.pack_id, shared_root=shared_root)
    if set(record.benchmark_id for record in results.records) != set(pack.benchmarks):
        raise ValueError("export must explicitly cover every canonical pack benchmark")
    if manifest.budget.benchmark_surface.benchmark_count != len(pack.benchmarks):
        raise ValueError("benchmark count differs from canonical pack")
    if manifest.budget.benchmark_surface.ladder_tier != pack.ladder_tier:
        raise ValueError("ladder tier differs from canonical pack")
    for record in results.records:
        definition = get_benchmark(record.benchmark_id, shared_root=shared_root)
        if (record.task_kind != definition.task_kind or record.metric.name != definition.primary_metric.name
                or record.metric.direction != definition.primary_metric.direction):
            raise ValueError("canonical task or metric semantics changed")


def read_export(root: Path, *, shared_root: Path | None = None,
                max_artifacts: int = 1024, max_artifact_bytes: int = 1024 * 1024 * 1024) -> ExportBundle:
    """Verify echoes and bytes with at most 1024 artifacts / 1 GiB total by default."""
    if type(max_artifacts) is not int or max_artifacts < 0 or type(max_artifact_bytes) is not int or max_artifact_bytes < 0:
        raise ValueError("bundle limits must be nonnegative integers")
    manifest = Manifest.model_validate_json(read_document(root, "manifest.json"))
    results = Results.model_validate_json(read_document(root, "results.json"))
    summary = RunSummary.model_validate_json(read_document(root, "summary.json"))
    _validate_cross_file(manifest, results, summary)
    validate_canonical_results(manifest, results, shared_root=shared_root)
    if len(summary.artifact_digests) > max_artifacts:
        raise ValueError("bundle artifact count exceeds limit")
    remaining = max_artifact_bytes
    for reference in summary.artifact_digests:
        payload = read_verified_artifact(root, reference, max_bytes=min(256 * 1024 * 1024, remaining))
        remaining -= len(payload)
    return ExportBundle(root.absolute(), manifest, results, summary)
