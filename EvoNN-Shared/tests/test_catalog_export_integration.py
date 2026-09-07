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
