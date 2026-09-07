"""Synthetic contract fixtures only; no model performance evidence."""
import hashlib
import json
from pathlib import Path

import pytest

from evonn_shared.catalog import get_benchmark, load_parity_pack
from evonn_shared.exports import Manifest, Results, RunSummary, write_export
from evonn_shared.export_reader import read_export


@pytest.fixture
def export_factory():
    def make(root, *, system="contenders", pack_name="tier1_core", budget=64, seed=42, score=.8, run_id=None):
        base = Path(__file__).resolve().parents[2] / "EvoNN-Shared/tests/fixtures/valid"
        manifest, results, summary = [json.loads((base / name).read_text()) for name in ("manifest.json", "results.json", "summary.json")]
        pack = load_parity_pack(pack_name)
        if budget % len(pack.benchmarks):
            raise ValueError("fixture budget must divide evenly across pack benchmarks")
        run_id = run_id or "fixture_" + system + "_" + str(seed)
        for document in (manifest, results, summary):
            document.update(system=system, run_id=run_id, pack_id=pack_name, seed=seed)
            document["budget"]["evaluation"] = {"total": budget, "stages": [{"name": "full", "evaluations": budget}]}
            document["budget"]["benchmark_surface"] = {"pack_id": pack_name, "benchmark_count": len(pack.benchmarks), "ladder_tier": pack.ladder_tier.value, "reductions": [], "subsets": []}
            document["accounting"] = {"evaluation_count": budget, "actual_evaluations": budget, "cached_evaluations": 0,
                "failed_evaluations": 0, "invalid_evaluations": 0, "resumed_from_run_id": None, "resumed_evaluations": 0,
                "partial_run": False, "evaluation_semantics": "synthetic contract fixture counts, no training"}
        for document in (manifest, summary):
            document.update(status="completed", status_reason=None)
        records, best = [], []
        for name in sorted(pack.benchmarks):
            definition = get_benchmark(name)
            value = score if definition.primary_metric.direction.value == "max" else 10 * (1-score)
            metric = {"name": definition.primary_metric.name, "direction": definition.primary_metric.direction.value, "value": float(value)}
            records.append({"benchmark_id": name, "outcome_id": "fixture", "task_kind": definition.task_kind.value,
                "metric": metric, "status": "ok", "reason": None, "evaluation_count": budget // len(pack.benchmarks),
                **{field: {"value": None, "provenance": "unavailable"} for field in ("parameter_count", "train_seconds", "model_bytes", "peak_memory_bytes")}})
            best.append({"benchmark_id": name, "outcome_id": "fixture", "metric_name": metric["name"], "direction": metric["direction"], "value": metric["value"]})
        results["records"] = records
        for document in (results, summary):
            document["coverage"] = {"benchmark_count": len(records), "result_count": len(records), "ok": len(records), "failed": 0, "skipped": 0, "unsupported": 0}
        summary.update(best_per_benchmark=best, aggregates=[], fairness_flags=[])
        config, report = b'{"fixture_only":true}\n', b'Fixture only. No model was trained.\n'
        manifest["config_snapshot"] = {"path": "config.yaml", "sha256": hashlib.sha256(config).hexdigest()}
        manifest["report_markdown"] = {"path": "report.md", "sha256": hashlib.sha256(report).hexdigest()}
        manifest["artifacts"] = []
        summary["artifact_digests"] = [manifest["config_snapshot"], manifest["report_markdown"]]
        typed = [model.model_validate_json(json.dumps(document)) for model, document in zip((Manifest, Results, RunSummary), (manifest, results, summary), strict=True)]
        root.parent.mkdir(parents=True, exist_ok=True)
        write_export(root, *typed)
        (root / "config.yaml").write_bytes(config)
        (root / "report.md").write_bytes(report)
        return read_export(root)
    return make


@pytest.fixture
def assume_engine_runtime_checked(monkeypatch):
    """Isolate comparison algebra from runtime acceptance for synthetic fixtures.

    Real runtime validation and rejection are exercised by Phase-2 integration
    tests. This fixture is deliberately opt-in, never an application bypass.
    """
    from evonn_compare import cases
    def accepted_fixture(bundle, **kwargs):
        assert json.loads((bundle.root / "config.yaml").read_text()) == {"fixture_only": True}
    monkeypatch.setattr(cases, "validate_engine_bundle", accepted_fixture)
