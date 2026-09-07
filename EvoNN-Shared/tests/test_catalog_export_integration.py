"""Production catalog metadata composed with test-only unsupported export fixtures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evonn_shared.catalog import list_benchmarks, load_parity_pack
from evonn_shared.exports import Manifest, Results, RunSummary, write_export


REPOSITORY = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures" / "valid"


@pytest.mark.parametrize("pack_name", ["tier1_core", "tier1_core_smoke", "tier_a_contract"])
def test_catalog_budget_export_composition_preserves_unsupported_visibility(
    pack_name: str, tmp_path: Path,
) -> None:
    """No dataset execution or scientific result is implied by these fixtures."""
    catalog = {item.id: item for item in list_benchmarks(shared_root=REPOSITORY / "shared-benchmarks")}
    pack = load_parity_pack(pack_name, shared_root=REPOSITORY / "shared-benchmarks")
    documents = [json.loads((FIXTURES / name).read_text()) for name in ("manifest.json", "results.json", "summary.json")]
    manifest, results, summary = documents
    count = len(pack.benchmarks)
    total = pack.budget_policy.evaluation_count
    reason = "Test-only contract composition; catalog datasets were not executed."
    for document in documents:
        document["run_id"] = f"contract-fixture.{pack_name}"
        document["pack_id"] = pack.pack_name
        document["budget"]["benchmark_surface"] = {
            "pack_id": pack.pack_name, "benchmark_count": count,
            "ladder_tier": pack.ladder_tier.value, "reductions": [], "subsets": [],
        }
        document["budget"]["evaluation"] = {"total": total, "stages": [{"name": "full", "evaluations": total}]}
        document["budget"]["training"]["total_cap"] = float(total)
        document["accounting"] = {
            "evaluation_count": total, "actual_evaluations": 0, "cached_evaluations": 0,
            "failed_evaluations": 0, "invalid_evaluations": 0, "resumed_from_run_id": None,
            "resumed_evaluations": 0, "partial_run": True,
            "evaluation_semantics": "Test fixture: no fit/evaluation attempts executed",
        }
    for document in (manifest, summary):
        document["status"] = "cancelled"
        document["status_reason"] = reason
        document["timing"]["ended_at"] = document["timing"]["started_at"]
        document["timing"]["elapsed_seconds"] = 0.0
    results["records"] = [
        {
            "benchmark_id": benchmark_id, "outcome_id": "unsupported_fixture",
            "task_kind": catalog[benchmark_id].task_kind.value,
            "metric": {"name": catalog[benchmark_id].primary_metric.name,
                       "direction": catalog[benchmark_id].primary_metric.direction.value, "value": None},
            "status": "unsupported", "reason": reason, "evaluation_count": 0,
            **{field: {"value": None, "provenance": "unavailable"}
               for field in ("parameter_count", "train_seconds", "model_bytes", "peak_memory_bytes")},
        }
        for benchmark_id in sorted(pack.benchmarks)
    ]
    for document in (results, summary):
        document["coverage"] = {"benchmark_count": count, "result_count": count,
                                "ok": 0, "failed": 0, "skipped": 0, "unsupported": count}
    summary["best_per_benchmark"] = []
    summary["aggregates"] = []
    summary["fairness_flags"] = [{"code": "contract_fixture_only", "severity": "warning",
                                  "message": reason, "benchmark_ids": sorted(pack.benchmarks)}]
    typed = tuple(model.model_validate_json(json.dumps(document))
                  for model, document in zip((Manifest, Results, RunSummary), documents, strict=True))
    output = tmp_path / "export"
    digests = write_export(output, *typed)
    for filename, model, expected, digest in zip(
        ("manifest.json", "results.json", "summary.json"), (Manifest, Results, RunSummary), typed,
        (digests.manifest_sha256, digests.results_sha256, digests.summary_sha256), strict=True,
    ):
        payload = (output / filename).read_bytes()
        assert model.model_validate_json(payload) == expected
        assert hashlib.sha256(payload).hexdigest() == digest
    decoded = Results.model_validate_json((output / "results.json").read_bytes())
    assert {record.benchmark_id for record in decoded.records} == set(pack.benchmarks)
    assert decoded.budget.evaluation.total in (16, 64)
    assert decoded.budget.benchmark_surface.ladder_tier == pack.ladder_tier
    assert decoded.coverage.unsupported == decoded.coverage.result_count == count
    assert decoded.accounting.actual_evaluations == 0
    assert decoded.accounting.partial_run is True
    for record in decoded.records:
        definition = catalog[record.benchmark_id]
        assert (record.task_kind, record.metric.name, record.metric.direction) == (
            definition.task_kind, definition.primary_metric.name, definition.primary_metric.direction,
        )
        assert record.metric.value is None


@pytest.mark.parametrize("mutation", ["none", "corrupt", "missing", "echo", "metric", "symlink"])
def test_read_export_validates_actual_portable_bytes(tmp_path, mutation):
    from evonn_shared.export_reader import read_export
    test_catalog_budget_export_composition_preserves_unsupported_visibility("tier1_core", tmp_path)
    root = tmp_path / "export"
    documents = {name: json.loads((root / (name + ".json")).read_text()) for name in ("manifest", "results", "summary")}
    manifest = documents["manifest"]
    references = [manifest["config_snapshot"], manifest["report_markdown"], *manifest["artifacts"]]
    for reference in references:
        payload = b"test-only artifact bytes"
        path = root / reference["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        reference["sha256"] = hashlib.sha256(payload).hexdigest()
    documents["summary"]["artifact_digests"] = sorted(references, key=lambda item: item["path"])
    if mutation == "echo":
        documents["summary"]["seed"] += 1
    if mutation == "metric":
        documents["results"]["records"][0]["metric"]["name"] = "wrong_metric"
    for name, document in documents.items():
        (root / (name + ".json")).write_text(json.dumps(document))
    if mutation == "corrupt":
        (root / "report.md").write_bytes(b"changed")
    if mutation == "missing":
        (root / "report.md").unlink()
    if mutation == "symlink":
        original = root / "manifest.json"
        actual = root / "manifest.actual"
        original.rename(actual)
        original.symlink_to(actual)
    before = {str(path): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    if mutation == "none":
        bundle = read_export(root)
        assert bundle.results.coverage.unsupported == 8
    else:
        with pytest.raises((ValueError, OSError)):
            read_export(root)
    assert before == {str(path): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_export_bundle_bounds_reference_count_before_reads_and_total_bytes(tmp_path, monkeypatch):
    from evonn_shared import export_reader
    test_read_export_validates_actual_portable_bytes(tmp_path, "none")
    root = tmp_path / "export"
    bundle = export_reader.read_export(root)
    count = len(bundle.summary.artifact_digests)
    total = sum((root / item.path).stat().st_size for item in bundle.summary.artifact_digests)
    assert count > 1
    original, calls = export_reader.read_verified_artifact, []
    def counted(*args, **kwargs):
        calls.append(kwargs["max_bytes"])
        return original(*args, **kwargs)
    monkeypatch.setattr(export_reader, "read_verified_artifact", counted)
    with pytest.raises(ValueError, match="artifact count"):
        export_reader.read_export(root, max_artifacts=count - 1)
    assert calls == []
    export_reader.read_export(root, max_artifacts=count, max_artifact_bytes=total)
    assert calls[-1] < calls[0]
    with pytest.raises(ValueError, match="limit"):
        export_reader.read_export(root, max_artifact_bytes=total - 1)
