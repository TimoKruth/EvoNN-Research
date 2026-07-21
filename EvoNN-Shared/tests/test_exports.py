from __future__ import annotations

from copy import deepcopy
import datetime as dt
import errno
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

import pytest
from pydantic import ValidationError

from evonn_shared.budgets import LadderTier
from evonn_shared.exports import (
    EXPORT_SCHEMA_VERSION,
    MANIFEST_FILENAME,
    RESULTS_FILENAME,
    SUMMARY_FILENAME,
    ExportDigests,
    Manifest,
    Results,
    RunClass,
    RunStatus,
    RunSummary,
    write_export,
)
from evonn_shared.telemetry import (
    BackendClass,
    FairnessSeverity,
    MeasurementProvenance,
    MetricDirection,
    ResultStatus,
    SeedingLadder,
    SeedOverlapPolicy,
    SystemId,
    TaskKind,
)

UTC = dt.timezone.utc
FIXTURE_ROOT = Path(__file__).parent / "fixtures"
GOLDEN_ROOT = Path(__file__).parent / "golden" / "exports"


def budget_data() -> dict[str, object]:
    return {
        "evaluation": {"total": 4, "stages": ({"name": "full", "evaluations": 4},)},
        "wall_clock": {"target_seconds": 60.0},
        "training": {"unit": "epochs", "per_candidate": 1.0, "total_cap": 4.0},
        "hardware": {
            "device_class": "apple-m3",
            "cpu_count": 8,
            "accelerator_type": "mlx",
            "memory_ceiling_bytes": 16_000_000_000,
            "worker_count": 2,
        },
        "model_artifact": {
            "parameter_cap": 1_000,
            "model_bytes_cap": 4_000,
            "memory_target_bytes": 8_000,
            "latency_target_seconds": 0.25,
        },
        "benchmark_surface": {
            "pack_id": "core_pack",
            "benchmark_count": 2,
            "ladder_tier": LadderTier.B,
            "reductions": (),
            "subsets": (),
        },
        "fidelity": {
            "regime": "single stage",
            "stages": ({"name": "full", "description": "full fidelity"},),
            "promotion_rule": "all candidates",
        },
    }


def accounting_data() -> dict[str, object]:
    return {
        "evaluation_count": 4,
        "actual_evaluations": 4,
        "cached_evaluations": 0,
        "failed_evaluations": 0,
        "invalid_evaluations": 0,
        "resumed_from_run_id": None,
        "resumed_evaluations": 0,
        "partial_run": False,
        "evaluation_semantics": "one charged candidate attempt",
    }


def runtime_data() -> dict[str, object]:
    return {
        "backend": BackendClass.MLX_NATIVE,
        "backend_version": "1.0",
        "device_class": "apple-m3",
        "precision_mode": "float32",
        "worker_topology": {"worker_count": 2, "process_count": 1, "threads_per_worker": 4},
        "host_fingerprint": "a" * 64,
    }


def seeding_data() -> dict[str, object]:
    return {
        "seeding_enabled": False,
        "seeding_ladder": SeedingLadder.NONE,
        "seed_source_system": None,
        "seed_source_run_id": None,
        "seed_artifact_path": None,
        "seed_target_family": None,
        "seed_selected_family": None,
        "seed_rank": None,
        "seed_overlap_policy": SeedOverlapPolicy.UNKNOWN,
        "seed_cost_accounting": None,
        "seed_source_evaluations": None,
    }


def timing_data() -> dict[str, object]:
    return {
        "started_at": dt.datetime(2026, 7, 21, 10, 0, tzinfo=UTC),
        "ended_at": dt.datetime(2026, 7, 21, 10, 1, tzinfo=UTC),
        "latest_checkpoint_at": None,
        "elapsed_seconds": 60.0,
    }


def measurement(value: int | float | None, provenance: MeasurementProvenance) -> dict[str, object]:
    return {"value": value, "provenance": provenance}


def record_data(
    benchmark_id: str,
    *,
    outcome_id: str = "candidate_one",
    direction: MetricDirection = MetricDirection.MAX,
    value: float = 0.8,
    evaluations: int = 2,
) -> dict[str, object]:
    return {
        "benchmark_id": benchmark_id,
        "outcome_id": outcome_id,
        "task_kind": TaskKind.CLASSIFICATION,
        "metric": {"name": "score", "direction": direction, "value": value},
        "status": ResultStatus.OK,
        "reason": None,
        "parameter_count": measurement(100, MeasurementProvenance.MEASURED),
        "train_seconds": measurement(1.0, MeasurementProvenance.MEASURED),
        "model_bytes": measurement(400, MeasurementProvenance.MEASURED),
        "peak_memory_bytes": measurement(None, MeasurementProvenance.UNAVAILABLE),
        "evaluation_count": evaluations,
    }


def manifest_data() -> dict[str, object]:
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "system": SystemId.PRISM,
        "run_id": "run.2026-07-21",
        "pack_id": "core_pack",
        "seed": 42,
        "run_class": RunClass.LOCAL,
        "status": RunStatus.COMPLETED,
        "status_reason": None,
        "lab_spec_version": "2026.07",
        "git_commit": "b" * 40,
        "timing": timing_data(),
        "budget": budget_data(),
        "accounting": accounting_data(),
        "runtime": runtime_data(),
        "seeding": seeding_data(),
        "config_snapshot": {"path": "config/run.json", "sha256": "c" * 64},
        "report_markdown": {"path": "report.md", "sha256": "d" * 64},
        "artifacts": ({"path": "charts/score.json", "sha256": "e" * 64},),
    }


def results_data() -> dict[str, object]:
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "system": SystemId.PRISM,
        "run_id": "run.2026-07-21",
        "pack_id": "core_pack",
        "seed": 42,
        "budget": budget_data(),
        "accounting": accounting_data(),
        "runtime": runtime_data(),
        "seeding": seeding_data(),
        "records": (
            record_data("alpha_case", value=0.8),
            record_data("beta_case", direction=MetricDirection.MIN, value=0.2),
        ),
        "coverage": {"benchmark_count": 2, "result_count": 2, "ok": 2, "failed": 0, "skipped": 0, "unsupported": 0},
    }


def summary_data() -> dict[str, object]:
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "system": SystemId.PRISM,
        "run_id": "run.2026-07-21",
        "pack_id": "core_pack",
        "seed": 42,
        "status": RunStatus.COMPLETED,
        "status_reason": None,
        "timing": timing_data(),
        "budget": budget_data(),
        "accounting": accounting_data(),
        "runtime": runtime_data(),
        "seeding": seeding_data(),
        "coverage": {"benchmark_count": 2, "result_count": 2, "ok": 2, "failed": 0, "skipped": 0, "unsupported": 0},
        "best_per_benchmark": (
            {"benchmark_id": "alpha_case", "outcome_id": "candidate_one", "metric_name": "score", "direction": MetricDirection.MAX, "value": 0.8},
            {"benchmark_id": "beta_case", "outcome_id": "candidate_one", "metric_name": "score", "direction": MetricDirection.MIN, "value": 0.2},
        ),
        "aggregates": ({"name": "mean_score", "direction": MetricDirection.MAX, "value": 0.5, "benchmark_count": 2},),
        "fairness_flags": ({"code": "runtime_visible", "severity": FairnessSeverity.INFO, "message": "runtime disclosed", "benchmark_ids": ("alpha_case", "beta_case")},),
        "artifact_digests": (
            {"path": "charts/score.json", "sha256": "e" * 64},
            {"path": "config/run.json", "sha256": "c" * 64},
            {"path": "report.md", "sha256": "d" * 64},
        ),
    }


def models() -> tuple[Manifest, Results, RunSummary]:
    return (
        Manifest.model_validate(manifest_data()),
        Results.model_validate(results_data()),
        RunSummary.model_validate(summary_data()),
    )


def test_constants_enums_exact_fields_and_frozen_surface() -> None:
    assert EXPORT_SCHEMA_VERSION == "1.0.0"
    assert (MANIFEST_FILENAME, RESULTS_FILENAME, SUMMARY_FILENAME) == ("manifest.json", "results.json", "summary.json")
    assert [(member.name, member.value) for member in RunStatus] == [
        ("COMPLETED", "completed"), ("FAILED", "failed"), ("INTERRUPTED", "interrupted"),
        ("RESUMED", "resumed"), ("CANCELLED", "cancelled"),
    ]
    assert [(member.name, member.value) for member in RunClass] == [
        ("SMOKE", "smoke"), ("LOCAL", "local"), ("OVERNIGHT", "overnight"),
        ("WEEKEND", "weekend"), ("SPECIAL_STUDY", "special-study"),
    ]
    assert set(Manifest.model_fields) == {
        "schema_version", "system", "run_id", "pack_id", "seed", "run_class", "status", "status_reason",
        "lab_spec_version", "git_commit", "timing", "budget", "accounting", "runtime", "seeding",
        "config_snapshot", "report_markdown", "artifacts",
    }
    assert set(Results.model_fields) == {
        "schema_version", "system", "run_id", "pack_id", "seed", "budget", "accounting", "runtime",
        "seeding", "records", "coverage",
    }
    assert set(RunSummary.model_fields) == {
        "schema_version", "system", "run_id", "pack_id", "seed", "status", "status_reason", "timing", "budget",
        "accounting", "runtime", "seeding", "coverage", "best_per_benchmark", "aggregates", "fairness_flags",
        "artifact_digests",
    }
    assert set(ExportDigests.model_fields) == {"manifest_sha256", "results_sha256", "summary_sha256"}


def test_valid_models_build_and_are_frozen() -> None:
    manifest, results, summary = models()
    with pytest.raises(ValidationError):
        manifest.seed = 9
    with pytest.raises(ValidationError):
        results.records = ()
    with pytest.raises(ValidationError):
        summary.artifact_digests = ()


@pytest.mark.parametrize("model_type,data_factory", [(Manifest, manifest_data), (Results, results_data), (RunSummary, summary_data)])
def test_top_level_model_validate_json_accepts_arrays_and_round_trips(model_type: type[Manifest] | type[Results] | type[RunSummary], data_factory: object) -> None:
    assert callable(data_factory)
    data = data_factory()
    payload = json.dumps(data, default=lambda value: value.value if hasattr(value, "value") else value.isoformat().replace("+00:00", "Z"), separators=(",", ":")).encode()
    model = model_type.model_validate_json(payload)
    assert model_type.model_validate_json(model.model_dump_json()).model_dump() == model.model_dump()


@pytest.mark.parametrize("model_type,data_factory", [(Manifest, manifest_data), (Results, results_data), (RunSummary, summary_data)])
def test_wrong_schema_unknown_missing_and_b0_product_shapes_reject(model_type: type[Manifest] | type[Results] | type[RunSummary], data_factory: object) -> None:
    assert callable(data_factory)
    for mutate in ("schema", "unknown", "missing"):
        data = data_factory()
        if mutate == "schema":
            data["schema_version"] = "1.0.1"
        elif mutate == "unknown":
            data["unknown"] = True
        else:
            del data["run_id"]
        with pytest.raises(ValidationError):
            model_type.model_validate(data)
    with pytest.raises(ValidationError):
        model_type.model_validate({"schema_version": "b0-capability-v1", "capabilities": {}})
    with pytest.raises(ValidationError):
        model_type.model_validate({"schema_version": "claudex-product-v1", "evaluations": []})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("run_id", ""),
        ("run_id", "../escape"),
        ("run_id", "x" * 129),
        ("pack_id", "Bad-Pack"),
        ("lab_spec_version", " "),
        ("lab_spec_version", "bad\x00version"),
        ("git_commit", "B" * 40),
        ("git_commit", "b" * 39),
        ("git_commit", "g" * 40),
        ("run_class", "local"),
        ("system", "prism"),
    ],
)
def test_manifest_rejects_malformed_provenance_ids_and_python_enum_coercion(field: str, value: object) -> None:
    data = manifest_data()
    data[field] = value
    with pytest.raises(ValidationError):
        Manifest.model_validate(data)


@pytest.mark.parametrize("seed", [-1, 2**256, True, "42"])
def test_seed_strict_unsigned_256_domain(seed: object) -> None:
    data = manifest_data()
    data["seed"] = seed
    with pytest.raises(ValidationError):
        Manifest.model_validate(data)


@pytest.mark.parametrize("model_type,data_factory", [(Manifest, manifest_data), (RunSummary, summary_data)])
def test_status_reason_matrix(model_type: type[Manifest] | type[RunSummary], data_factory: object) -> None:
    assert callable(data_factory)
    completed = data_factory()
    completed["status_reason"] = "unexpected"
    with pytest.raises(ValidationError):
        model_type.model_validate(completed)
    for status in [RunStatus.FAILED, RunStatus.INTERRUPTED, RunStatus.RESUMED, RunStatus.CANCELLED]:
        data = data_factory()
        data["status"] = status
        data["status_reason"] = "stopped for test"
        assert model_type.model_validate(data).status is status
        data["status_reason"] = None
        with pytest.raises(ValidationError):
            model_type.model_validate(data)


@pytest.mark.parametrize(
    "factory,mutation",
    [
        (manifest_data, lambda data: data.update(pack_id="other_pack")),
        (results_data, lambda data: data["accounting"].update(evaluation_count=5, partial_run=True)),
        (summary_data, lambda data: data["runtime"]["worker_topology"].update(worker_count=1)),
        (summary_data, lambda data: data["runtime"].update(device_class="other-device")),
    ],
)
def test_each_document_validates_internal_echoes(factory: object, mutation: object) -> None:
    data = factory()
    mutation(data)
    model_type = Manifest if factory is manifest_data else Results if factory is results_data else RunSummary
    with pytest.raises(ValidationError):
        model_type.model_validate(data)


def test_manifest_artifact_paths_are_sorted_and_globally_unique() -> None:
    for artifacts in [
        ({"path": "z.json", "sha256": "e" * 64}, {"path": "a.json", "sha256": "f" * 64}),
        ({"path": "config/run.json", "sha256": "e" * 64},),
    ]:
        data = manifest_data()
        data["artifacts"] = artifacts
        with pytest.raises(ValidationError):
            Manifest.model_validate(data)


@pytest.mark.parametrize(
    "change",
    [
        "order", "duplicate", "coverage_total", "distinct_benchmarks", "declared_benchmarks", "evaluation_total",
        "task_kind", "metric_name", "direction",
    ],
)
def test_results_reject_order_duplicates_coverage_evaluation_and_same_benchmark_inconsistency(change: str) -> None:
    data = results_data()
    if change == "order":
        data["records"] = tuple(reversed(data["records"]))
    elif change == "duplicate":
        data["records"] = (data["records"][0], data["records"][0])
    elif change == "coverage_total":
        data["coverage"]["ok"] = 1
        data["coverage"]["failed"] = 1
    elif change == "distinct_benchmarks":
        data["coverage"]["benchmark_count"] = 1
    elif change == "declared_benchmarks":
        data["budget"]["benchmark_surface"]["benchmark_count"] = 3
    elif change == "evaluation_total":
        data["records"][0]["evaluation_count"] = 1
    else:
        second = deepcopy(data["records"][0])
        second["outcome_id"] = "candidate_two"
        if change == "task_kind":
            second["task_kind"] = TaskKind.REGRESSION
        elif change == "metric_name":
            second["metric"]["name"] = "other"
        else:
            second["metric"]["direction"] = MetricDirection.MIN
        data["records"] = (data["records"][0], second, data["records"][1])
        data["coverage"]["result_count"] = 3
        data["coverage"]["ok"] = 3
    with pytest.raises(ValidationError):
        Results.model_validate(data)


def test_summary_rejects_unsorted_or_duplicate_collections() -> None:
    fields = ["best_per_benchmark", "aggregates", "fairness_flags", "artifact_digests"]
    for field in fields:
        data = summary_data()
        first = deepcopy(data[field][0])
        if field == "best_per_benchmark":
            second = deepcopy(first) | {"benchmark_id": "aardvark"}
        elif field == "aggregates":
            second = deepcopy(first) | {"name": "a_metric"}
        elif field == "fairness_flags":
            second = deepcopy(first) | {"code": "a_flag"}
        else:
            second = deepcopy(first) | {"path": "a.json"}
        data[field] = (first, second)
        with pytest.raises(ValidationError):
            RunSummary.model_validate(data)
        data[field] = (first, first)
        with pytest.raises(ValidationError):
            RunSummary.model_validate(data)


def test_write_export_validates_all_cross_file_echoes_before_touching_filesystem(tmp_path: Path) -> None:
    manifest, results, summary = models()
    mismatches = [
        (manifest.model_copy(update={"system": SystemId.TOPOGRAPH}), results, summary),
        (manifest.model_copy(update={"run_id": "other"}), results, summary),
        (manifest.model_copy(update={"pack_id": "other_pack"}), results, summary),
        (manifest.model_copy(update={"seed": 43}), results, summary),
        (manifest.model_copy(update={"budget": manifest.budget.model_copy(update={"wall_clock": manifest.budget.wall_clock.model_copy(update={"target_seconds": 61.0})})}), results, summary),
        (manifest.model_copy(update={"accounting": manifest.accounting.model_copy(update={"invalid_evaluations": 1})}), results, summary),
        (manifest.model_copy(update={"runtime": manifest.runtime.model_copy(update={"backend_version": "2.0"})}), results, summary),
        (manifest.model_copy(update={"seeding": manifest.seeding.model_copy(update={"seed_overlap_policy": SeedOverlapPolicy.BENCHMARK_OVERLAPPING})}), results, summary),
        (manifest.model_copy(update={"status": RunStatus.FAILED, "status_reason": "failed"}), results, summary),
        (
            manifest.model_copy(update={"status": RunStatus.FAILED, "status_reason": "manifest reason"}),
            results,
            summary.model_copy(update={"status": RunStatus.FAILED, "status_reason": "summary reason"}),
        ),
        (
            manifest.model_copy(
                update={
                    "timing": manifest.timing.model_copy(
                        update={
                            "ended_at": manifest.timing.ended_at + dt.timedelta(seconds=1),
                            "elapsed_seconds": 61.0,
                        }
                    )
                }
            ),
            results,
            summary,
        ),
        (
            manifest,
            results,
            summary.model_copy(
                update={"coverage": summary.coverage.model_copy(update={"result_count": 3, "ok": 3})}
            ),
        ),
    ]
    for index, triple in enumerate(mismatches):
        destination = tmp_path / f"mismatch-{index}"
        with pytest.raises(ValueError):
            write_export(destination, *triple)
        assert not destination.exists()


def test_write_export_revalidates_copied_models_before_touching_filesystem(tmp_path: Path) -> None:
    manifest, results, summary = models()
    invalid_budget = manifest.budget.model_copy(
        update={"evaluation": manifest.budget.evaluation.model_copy(update={"total": 5})}
    )
    invalid_manifest = manifest.model_copy(update={"budget": invalid_budget})
    invalid_results = results.model_copy(update={"budget": invalid_budget})
    invalid_summary = summary.model_copy(update={"budget": invalid_budget})
    destination = tmp_path / "invalid-copies"

    with pytest.raises(ValidationError):
        write_export(destination, invalid_manifest, invalid_results, invalid_summary)
    assert not destination.exists()


def test_write_export_rejects_forged_best_and_artifact_union(tmp_path: Path) -> None:
    manifest, results, summary = models()
    forged_best = summary.model_copy(update={"best_per_benchmark": summary.best_per_benchmark[:-1]})
    with pytest.raises(ValueError):
        write_export(tmp_path / "best", manifest, results, forged_best)
    forged_artifacts = summary.model_copy(update={"artifact_digests": summary.artifact_digests[:-1]})
    with pytest.raises(ValueError):
        write_export(tmp_path / "artifacts", manifest, results, forged_artifacts)


def test_best_derivation_is_direction_aware_and_ties_choose_smallest_utf8_outcome(tmp_path: Path) -> None:
    manifest, results, summary = models()
    records = (
        results.records[0].model_copy(update={"outcome_id": "candidate_a", "metric": results.records[0].metric.model_copy(update={"value": 0.8})}),
        results.records[0].model_copy(update={"outcome_id": "candidate_b", "metric": results.records[0].metric.model_copy(update={"value": 0.8})}),
        results.records[1].model_copy(update={"outcome_id": "candidate_a", "metric": results.records[1].metric.model_copy(update={"value": 0.2})}),
        results.records[1].model_copy(update={"outcome_id": "candidate_b", "metric": results.records[1].metric.model_copy(update={"value": 0.3})}),
    )
    accounting = results.accounting.model_copy(update={"actual_evaluations": 8, "evaluation_count": 8})
    budget = results.budget.model_copy(update={"evaluation": results.budget.evaluation.model_copy(update={"total": 8, "stages": ()})})
    results = results.model_copy(update={
        "records": records,
        "accounting": accounting,
        "budget": budget,
        "coverage": results.coverage.model_copy(update={"result_count": 4, "ok": 4}),
    })
    manifest = manifest.model_copy(update={"accounting": accounting, "budget": budget})
    expected_best = (
        summary.best_per_benchmark[0].model_copy(update={"outcome_id": "candidate_a"}),
        summary.best_per_benchmark[1].model_copy(update={"outcome_id": "candidate_a"}),
    )
    summary = summary.model_copy(update={"accounting": accounting, "budget": budget, "coverage": results.coverage, "best_per_benchmark": expected_best})
    write_export(tmp_path / "tie", manifest, results, summary)


def test_success_writes_only_three_complete_files_with_digests_and_modes(tmp_path: Path) -> None:
    manifest, results, summary = models()
    before = (manifest.model_dump(), results.model_dump(), summary.model_dump())
    destination = tmp_path / "run-export"

    digests = write_export(destination, manifest, results, summary)

    assert sorted(path.name for path in destination.iterdir()) == [MANIFEST_FILENAME, RESULTS_FILENAME, SUMMARY_FILENAME]
    expected = {}
    for name in [MANIFEST_FILENAME, RESULTS_FILENAME, SUMMARY_FILENAME]:
        payload = (destination / name).read_bytes()
        assert payload.endswith(b"\n") and not payload.endswith(b"\n\n")
        assert stat.S_IMODE((destination / name).stat().st_mode) == 0o600
        expected[name] = hashlib.sha256(payload).hexdigest()
    assert digests == ExportDigests(
        manifest_sha256=expected[MANIFEST_FILENAME], results_sha256=expected[RESULTS_FILENAME], summary_sha256=expected[SUMMARY_FILENAME]
    )
    assert (manifest.model_dump(), results.model_dump(), summary.model_dump()) == before
    assert not list(tmp_path.glob(".run-export.tmp-*"))


def test_existing_destinations_and_missing_or_symlink_parent_are_refused(tmp_path: Path) -> None:
    manifest, results, summary = models()
    targets = []
    file_target = tmp_path / "file"
    file_target.write_text("keep", encoding="utf-8")
    targets.append(file_target)
    dir_target = tmp_path / "dir"
    dir_target.mkdir()
    targets.append(dir_target)
    symlink_target = tmp_path / "symlink"
    symlink_target.symlink_to(file_target)
    targets.append(symlink_target)
    dangling = tmp_path / "dangling"
    dangling.symlink_to(tmp_path / "missing-target")
    targets.append(dangling)
    for target in targets:
        with pytest.raises(FileExistsError):
            write_export(target, manifest, results, summary)
    assert file_target.read_text(encoding="utf-8") == "keep"

    with pytest.raises(FileNotFoundError):
        write_export(tmp_path / "missing" / "export", manifest, results, summary)
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(OSError):
        write_export(linked_parent / "export", manifest, results, summary)


@pytest.mark.parametrize("directory", ["not-a-path", Path("."), Path("..")])
def test_destination_requires_concrete_path_with_normal_final_name(directory: object) -> None:
    manifest, results, summary = models()
    with pytest.raises((TypeError, ValueError)):
        write_export(directory, manifest, results, summary)  # type: ignore[arg-type]


def test_real_native_exclusive_rename_collision_preserves_raced_destination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import evonn_shared.exports as exports

    manifest, results, summary = models()
    destination = tmp_path / "collision"
    native = exports._load_exclusive_rename()

    def collide(parent_fd: int, source_name: str, destination_name: str) -> None:
        os.mkdir(destination_name, 0o700, dir_fd=parent_fd)
        destination_fd = os.open(destination_name, os.O_RDONLY | os.O_DIRECTORY, dir_fd=parent_fd)
        try:
            marker_fd = os.open("marker", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=destination_fd)
            try:
                os.write(marker_fd, b"keep")
            finally:
                os.close(marker_fd)
        finally:
            os.close(destination_fd)
        native(parent_fd, source_name, destination_name)

    monkeypatch.setattr(exports, "_load_exclusive_rename", lambda: collide)
    with pytest.raises(FileExistsError):
        write_export(destination, manifest, results, summary)
    assert (destination / "marker").read_bytes() == b"keep"
    assert not list(tmp_path.glob(".collision.tmp-*"))


def test_serialization_failure_happens_before_any_filesystem_touch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import evonn_shared.exports as exports

    manifest, results, summary = models()
    monkeypatch.setattr(
        exports,
        "_serialize_document",
        lambda document: (_ for _ in ()).throw(ValueError("serialization failed")),
    )
    destination = tmp_path / "serialization-failure"
    with pytest.raises(ValueError, match="serialization failed"):
        write_export(destination, manifest, results, summary)
    assert not destination.exists()
    assert not list(tmp_path.glob(".serialization-failure.tmp-*"))


@pytest.mark.parametrize("helper_name", ["_open_file_at", "_write_all", "_flush_file", "_fsync_file", "_close_file"])
@pytest.mark.parametrize("target_call", [1, 2, 3])
def test_each_file_operation_fault_cleans_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    helper_name: str,
    target_call: int,
) -> None:
    import evonn_shared.exports as exports

    manifest, results, summary = models()
    original = getattr(exports, helper_name)
    calls = 0

    def fail_selected_call(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        if calls == target_call:
            raise OSError(f"injected {helper_name} failure {target_call}")
        return original(*args, **kwargs)

    monkeypatch.setattr(exports, helper_name, fail_selected_call)
    destination = tmp_path / f"{helper_name[1:]}-{target_call}"
    with pytest.raises(OSError, match="injected"):
        write_export(destination, manifest, results, summary)
    assert calls == target_call
    assert not destination.exists()
    assert not list(tmp_path.glob(f".{destination.name}.tmp-*"))


def test_pre_rename_faults_cleanup_only_owned_staging_and_leave_no_destination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import evonn_shared.exports as exports

    manifest, results, summary = models()
    helpers = ["_open_file_at", "_write_all", "_flush_file", "_fsync_file", "_close_file", "_fsync_directory_fd", "_load_exclusive_rename"]
    for index, helper in enumerate(helpers):
        destination = tmp_path / f"fault-{index}"
        original = getattr(exports, helper)
        if helper == "_load_exclusive_rename":
            monkeypatch.setattr(exports, helper, lambda: (_ for _ in ()).throw(OSError("rename unavailable")))
        else:
            monkeypatch.setattr(exports, helper, lambda *args, **kwargs: (_ for _ in ()).throw(OSError("injected")))
        with pytest.raises(OSError):
            write_export(destination, manifest, results, summary)
        assert not destination.exists()
        assert not list(tmp_path.glob(f".{destination.name}.tmp-*"))
        monkeypatch.setattr(exports, helper, original)


def test_parent_fsync_failure_raises_but_leaves_complete_destination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import evonn_shared.exports as exports

    manifest, results, summary = models()
    calls = 0
    original = exports._fsync_directory_fd

    def fail_parent(fd: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("parent fsync failed")
        original(fd)

    monkeypatch.setattr(exports, "_fsync_directory_fd", fail_parent)
    destination = tmp_path / "durability-uncertain"
    with pytest.raises(OSError, match="parent fsync failed"):
        write_export(destination, manifest, results, summary)
    assert sorted(path.name for path in destination.iterdir()) == [MANIFEST_FILENAME, RESULTS_FILENAME, SUMMARY_FILENAME]
    for filename in [MANIFEST_FILENAME, RESULTS_FILENAME, SUMMARY_FILENAME]:
        assert (destination / filename).read_bytes() == (GOLDEN_ROOT / filename).read_bytes()
    assert not list(tmp_path.glob(".durability-uncertain.tmp-*"))


def test_committed_valid_fixtures_parse_and_invalid_foreign_shapes_reject() -> None:
    model_files = [(Manifest, "manifest.json"), (Results, "results.json"), (RunSummary, "summary.json")]
    for model, filename in model_files:
        parsed = model.model_validate_json((FIXTURE_ROOT / "valid" / filename).read_bytes())
        assert model.model_validate_json(parsed.model_dump_json()).model_dump() == parsed.model_dump()
    for filename in ["wrong-schema.json", "b0-capability.json", "product-evaluation.json"]:
        payload = (FIXTURE_ROOT / "invalid" / filename).read_bytes()
        for model, _ in model_files:
            with pytest.raises(ValidationError):
                model.model_validate_json(payload)


def test_exact_golden_bytes_and_independently_pinned_raw_sha256_values(tmp_path: Path) -> None:
    expected_sha256 = {
        MANIFEST_FILENAME: "57db6c21ee4c036ee295d670de17b58d4266ba8c1a1da642ca94d6f8b6f5272b",
        RESULTS_FILENAME: "d2f22d1e7fcf79b079ca6dcba2bf609a94794b130126503c07a3f602bd09a643",
        SUMMARY_FILENAME: "c77705e5e8f668d97a6679863882fac9d6717d2ad545fc2e716f618b0974b2cc",
    }
    manifest, results, summary = models()
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_digests = write_export(first, manifest, results, summary)
    second_digests = write_export(second, manifest, results, summary)

    for filename, expected_digest in expected_sha256.items():
        golden = (GOLDEN_ROOT / filename).read_bytes()
        assert hashlib.sha256(golden).hexdigest() == expected_digest
        assert (first / filename).read_bytes() == golden
        assert (second / filename).read_bytes() == golden
    assert first_digests == second_digests == ExportDigests(
        manifest_sha256=expected_sha256[MANIFEST_FILENAME],
        results_sha256=expected_sha256[RESULTS_FILENAME],
        summary_sha256=expected_sha256[SUMMARY_FILENAME],
    )


def test_distinct_mapping_insertion_histories_produce_identical_golden_bytes(tmp_path: Path) -> None:
    normal_manifest, normal_results, normal_summary = models()

    def reverse_mapping(value: dict[str, object]) -> dict[str, object]:
        return dict(reversed(tuple(value.items())))

    reversed_manifest_data = reverse_mapping(manifest_data())
    reversed_manifest_data["budget"] = reverse_mapping(reversed_manifest_data["budget"])
    reversed_results_data = reverse_mapping(results_data())
    reversed_results_data["runtime"] = reverse_mapping(reversed_results_data["runtime"])
    reversed_summary_data = reverse_mapping(summary_data())
    reversed_summary_data["coverage"] = reverse_mapping(reversed_summary_data["coverage"])
    reversed_models = (
        Manifest.model_validate(reversed_manifest_data),
        Results.model_validate(reversed_results_data),
        RunSummary.model_validate(reversed_summary_data),
    )

    write_export(tmp_path / "normal-order", normal_manifest, normal_results, normal_summary)
    write_export(tmp_path / "reversed-order", *reversed_models)
    for filename in [MANIFEST_FILENAME, RESULTS_FILENAME, SUMMARY_FILENAME]:
        assert (tmp_path / "normal-order" / filename).read_bytes() == (tmp_path / "reversed-order" / filename).read_bytes()


def test_distinct_pythonhashseed_subprocesses_produce_identical_golden_bytes(tmp_path: Path) -> None:
    script = """
from pathlib import Path
from evonn_shared.exports import Manifest, Results, RunSummary, write_export
fixture = Path(__import__('sys').argv[1])
destination = Path(__import__('sys').argv[2])
write_export(
    destination,
    Manifest.model_validate_json((fixture / 'manifest.json').read_bytes()),
    Results.model_validate_json((fixture / 'results.json').read_bytes()),
    RunSummary.model_validate_json((fixture / 'summary.json').read_bytes()),
)
"""
    for seed in ["1", "987654"]:
        destination = tmp_path / f"seed-{seed}"
        environment = os.environ | {"PYTHONHASHSEED": seed}
        subprocess.run(
            [sys.executable, "-c", script, str(FIXTURE_ROOT / "valid"), str(destination)],
            check=True,
            cwd=Path(__file__).parents[2],
            env=environment,
        )
        for filename in [MANIFEST_FILENAME, RESULTS_FILENAME, SUMMARY_FILENAME]:
            assert (destination / filename).read_bytes() == (GOLDEN_ROOT / filename).read_bytes()


def test_every_export_model_rejects_each_missing_field_and_unknown_fields() -> None:
    cases = {
        Manifest: manifest_data(),
        Results: results_data(),
        RunSummary: summary_data(),
        ExportDigests: {"manifest_sha256": "a" * 64, "results_sha256": "b" * 64, "summary_sha256": "c" * 64},
    }
    for model, valid in cases.items():
        for field_name in model.model_fields:
            missing = deepcopy(valid)
            del missing[field_name]
            with pytest.raises(ValidationError):
                model.model_validate(missing)
        unknown = deepcopy(valid)
        unknown["unknown"] = "forbidden"
        with pytest.raises(ValidationError):
            model.model_validate(unknown)


def test_native_adapter_selects_exact_platform_primitive_flags_and_errno_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    import evonn_shared.exports as exports

    class FakeFunction:
        def __init__(self, error_number: int) -> None:
            self.error_number = error_number
            self.calls: list[tuple[object, ...]] = []
            self.argtypes: object = None
            self.restype: object = None

        def __call__(self, *args: object) -> int:
            self.calls.append(args)
            ctypes = exports.ctypes
            ctypes.set_errno(self.error_number)
            return -1

    class FakeLibrary:
        def __init__(self, error_number: int) -> None:
            self.renameat2 = FakeFunction(error_number)
            self.renameatx_np = FakeFunction(error_number)

    for platform, symbol_name, expected_flag in [("linux", "renameat2", 1), ("darwin", "renameatx_np", 0x00000004)]:
        library = FakeLibrary(errno.EEXIST)
        calls: list[tuple[object, object]] = []

        def fake_cdll(name: object, *, use_errno: bool) -> FakeLibrary:
            calls.append((name, use_errno))
            return library

        monkeypatch.setattr(exports.sys, "platform", platform)
        monkeypatch.setattr(exports.ctypes, "CDLL", fake_cdll)
        adapter = exports._load_exclusive_rename()
        with pytest.raises(FileExistsError):
            adapter(9, "stage", "dest")
        assert calls == [(None, True)]
        function = getattr(library, symbol_name)
        assert function.calls[0] == (9, b"stage", 9, b"dest", expected_flag)

    library = FakeLibrary(5)
    monkeypatch.setattr(exports.sys, "platform", "linux")
    monkeypatch.setattr(exports.ctypes, "CDLL", lambda name, use_errno: library)
    with pytest.raises(OSError) as error:
        exports._load_exclusive_rename()(9, "stage", "dest")
    assert error.value.errno == 5

    monkeypatch.setattr(exports.sys, "platform", "unsupported")
    with pytest.raises(OSError) as error:
        exports._load_exclusive_rename()
    assert error.value.errno == errno.ENOTSUP


def test_unsupported_platform_fails_closed_before_staging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import evonn_shared.exports as exports

    manifest, results, summary = models()
    monkeypatch.setattr(exports.sys, "platform", "unsupported")
    destination = tmp_path / "unsupported"
    with pytest.raises(OSError) as error:
        write_export(destination, manifest, results, summary)
    assert error.value.errno == errno.ENOTSUP
    assert not destination.exists()
    assert not list(tmp_path.glob(".unsupported.tmp-*"))


def test_generic_rename_failure_cleans_staging_and_preserves_absent_destination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import evonn_shared.exports as exports

    manifest, results, summary = models()

    def failing_rename(parent_fd: int, source_name: str, destination_name: str) -> None:
        raise OSError("rename failed")

    monkeypatch.setattr(exports, "_load_exclusive_rename", lambda: failing_rename)
    destination = tmp_path / "rename-failure"
    with pytest.raises(OSError, match="rename failed"):
        write_export(destination, manifest, results, summary)
    assert not destination.exists()
    assert not list(tmp_path.glob(".rename-failure.tmp-*"))


def test_cleanup_failure_is_not_allowed_to_hide_primary_rename_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import evonn_shared.exports as exports

    manifest, results, summary = models()
    original_rmdir = exports.os.rmdir
    monkeypatch.setattr(
        exports,
        "_load_exclusive_rename",
        lambda: lambda parent_fd, source_name, destination_name: (_ for _ in ()).throw(OSError("primary rename")),
    )
    monkeypatch.setattr(exports.os, "rmdir", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("cleanup rmdir")))
    destination = tmp_path / "cleanup-note"
    with pytest.raises(OSError, match="primary rename") as error:
        write_export(destination, manifest, results, summary)
    assert any("cleanup rmdir" in note for note in error.value.__notes__)
    debris = list(tmp_path.glob(".cleanup-note.tmp-*"))
    assert len(debris) == 1
    monkeypatch.setattr(exports.os, "rmdir", original_rmdir)
    original_rmdir(debris[0])


def test_staging_directory_is_mode_0700_before_native_publication(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import evonn_shared.exports as exports

    manifest, results, summary = models()
    native = exports._load_exclusive_rename()

    def inspect_then_rename(parent_fd: int, source_name: str, destination_name: str) -> None:
        source_status = os.stat(source_name, dir_fd=parent_fd, follow_symlinks=False)
        assert stat.S_IMODE(source_status.st_mode) == 0o700
        native(parent_fd, source_name, destination_name)

    monkeypatch.setattr(exports, "_load_exclusive_rename", lambda: inspect_then_rename)
    write_export(tmp_path / "mode-check", manifest, results, summary)


def test_writer_rejects_path_and_model_subclasses_before_dispatch(tmp_path: Path) -> None:
    manifest, results, summary = models()

    class ManifestSubclass(Manifest):
        pass

    class PathSubclass(type(Path())):
        pass

    hostile_manifest = ManifestSubclass.model_validate(manifest.model_dump())
    with pytest.raises(TypeError):
        write_export(tmp_path / "model-subclass", hostile_manifest, results, summary)
    with pytest.raises(TypeError):
        write_export(PathSubclass(tmp_path / "path-subclass"), manifest, results, summary)


def _assert_fd_closed(descriptor: int) -> None:
    with pytest.raises(OSError) as error:
        os.fstat(descriptor)
    assert error.value.errno == errno.EBADF


def _assert_fd_open_for(descriptor: int, path: Path) -> None:
    assert (os.fstat(descriptor).st_dev, os.fstat(descriptor).st_ino) == (path.stat().st_dev, path.stat().st_ino)


@pytest.mark.parametrize("raise_after_reuse", [False, True])
def test_raw_close_never_closes_reused_descriptor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    raise_after_reuse: bool,
) -> None:
    import evonn_shared.exports as exports

    manifest, results, summary = models()
    destination = tmp_path / f"raw-close-reuse-{raise_after_reuse}"
    replacement = tmp_path / f"raw-replacement-{raise_after_reuse}"
    parent_fd: int | None = None
    replacement_fd: int | None = None
    native = exports._load_exclusive_rename()

    def capture_parent(parent_descriptor: int, source_name: str, destination_name: str) -> None:
        nonlocal parent_fd
        parent_fd = parent_descriptor
        native(parent_descriptor, source_name, destination_name)

    def close_then_reuse(descriptor: int) -> None:
        nonlocal replacement_fd
        os.close(descriptor)
        if descriptor == parent_fd:
            replacement_fd = os.open(replacement, os.O_RDONLY | os.O_CREAT | os.O_CLOEXEC, 0o600)
            assert replacement_fd == descriptor
            if raise_after_reuse:
                raise OSError("raw close raised after reuse")

    monkeypatch.setattr(exports, "_load_exclusive_rename", lambda: capture_parent)
    monkeypatch.setattr(exports, "_close_descriptor", close_then_reuse)

    try:
        if raise_after_reuse:
            with pytest.raises(OSError, match="raw close raised after reuse"):
                write_export(destination, manifest, results, summary)
        else:
            write_export(destination, manifest, results, summary)
        assert replacement_fd is not None
        _assert_fd_open_for(replacement_fd, replacement)
        assert sorted(path.name for path in destination.iterdir()) == [
            MANIFEST_FILENAME,
            RESULTS_FILENAME,
            SUMMARY_FILENAME,
        ]
    finally:
        if replacement_fd is not None:
            try:
                os.close(replacement_fd)
            except OSError as error:
                if error.errno != errno.EBADF:
                    raise


@pytest.mark.parametrize("raise_after_reuse", [False, True])
def test_file_object_close_never_closes_reused_descriptor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    raise_after_reuse: bool,
) -> None:
    import evonn_shared.exports as exports

    manifest, results, summary = models()
    destination = tmp_path / f"file-close-reuse-{raise_after_reuse}"
    replacement = tmp_path / f"file-replacement-{raise_after_reuse}"
    replacement_fd: int | None = None

    def close_then_reuse(file: object) -> None:
        nonlocal replacement_fd
        descriptor = file.fileno()
        file.close()
        if replacement_fd is None:
            replacement_fd = os.open(replacement, os.O_RDONLY | os.O_CREAT | os.O_CLOEXEC, 0o600)
            assert replacement_fd == descriptor
            if raise_after_reuse:
                raise OSError("file close raised after reuse")

    monkeypatch.setattr(exports, "_close_file", close_then_reuse)

    try:
        if raise_after_reuse:
            with pytest.raises(OSError, match="file close raised after reuse"):
                write_export(destination, manifest, results, summary)
            assert not destination.exists()
        else:
            write_export(destination, manifest, results, summary)
        assert replacement_fd is not None
        _assert_fd_open_for(replacement_fd, replacement)
    finally:
        if replacement_fd is not None:
            try:
                os.close(replacement_fd)
            except OSError as error:
                if error.errno != errno.EBADF:
                    raise


def test_raw_exceptional_close_preserves_same_inode_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import evonn_shared.exports as exports

    manifest, results, summary = models()
    destination = tmp_path / "raw-same-inode-reuse"
    parent_fd: int | None = None
    replacement_fd: int | None = None
    native = exports._load_exclusive_rename()

    def capture_parent(parent_descriptor: int, source_name: str, destination_name: str) -> None:
        nonlocal parent_fd
        parent_fd = parent_descriptor
        native(parent_descriptor, source_name, destination_name)

    def close_reopen_same_parent_then_raise(descriptor: int) -> None:
        nonlocal replacement_fd
        os.close(descriptor)
        if descriptor == parent_fd:
            replacement_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            assert replacement_fd == descriptor
            raise OSError("raw close raised after same-inode reuse")

    monkeypatch.setattr(exports, "_load_exclusive_rename", lambda: capture_parent)
    monkeypatch.setattr(exports, "_close_descriptor", close_reopen_same_parent_then_raise)

    try:
        with pytest.raises(OSError, match="raw close raised after same-inode reuse"):
            write_export(destination, manifest, results, summary)
        assert replacement_fd is not None
        _assert_fd_open_for(replacement_fd, tmp_path)
        assert sorted(path.name for path in destination.iterdir()) == [
            MANIFEST_FILENAME,
            RESULTS_FILENAME,
            SUMMARY_FILENAME,
        ]
    finally:
        if replacement_fd is not None:
            try:
                os.close(replacement_fd)
            except OSError as error:
                if error.errno != errno.EBADF:
                    raise


def test_file_exceptional_close_preserves_same_inode_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import evonn_shared.exports as exports

    manifest, results, summary = models()
    destination = tmp_path / "file-same-inode-reuse"
    replacement_fd: int | None = None
    replacement_status: os.stat_result | None = None
    captured_file: object | None = None

    def close_reopen_same_file_then_raise(file: object) -> None:
        nonlocal captured_file, replacement_fd, replacement_status
        captured_file = file
        descriptor = file.fileno()
        replacement_status = os.fstat(descriptor)
        staged_file = next(tmp_path.glob(".file-same-inode-reuse.tmp-*/manifest.json"))
        os.close(descriptor)
        replacement_fd = os.open(staged_file, os.O_RDONLY | os.O_CLOEXEC)
        assert replacement_fd == descriptor
        raise OSError("file close raised after same-inode reuse")

    monkeypatch.setattr(exports, "_close_file", close_reopen_same_file_then_raise)

    try:
        with pytest.raises(OSError, match="file close raised after same-inode reuse"):
            write_export(destination, manifest, results, summary)
        assert replacement_fd is not None and replacement_status is not None
        assert (os.fstat(replacement_fd).st_dev, os.fstat(replacement_fd).st_ino) == (
            replacement_status.st_dev,
            replacement_status.st_ino,
        )
        assert not destination.exists()
        assert not list(tmp_path.glob(".file-same-inode-reuse.tmp-*"))
    finally:
        if captured_file is not None and not captured_file.closed:
            captured_file.close()
        elif replacement_fd is not None:
            try:
                os.close(replacement_fd)
            except OSError as error:
                if error.errno != errno.EBADF:
                    raise


def test_source_name_replacement_is_detected_without_publishing_or_deleting_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import evonn_shared.exports as exports

    manifest, results, summary = models()
    destination = tmp_path / "source-swap"
    moved_owned = tmp_path / "externally-moved-owned"
    original_fsync = exports._fsync_directory_fd
    swapped = False
    replacement_name: str | None = None

    def swap_after_staging_fsync(descriptor: int) -> None:
        nonlocal swapped, replacement_name
        original_fsync(descriptor)
        if swapped:
            return
        candidates = list(tmp_path.glob(".source-swap.tmp-*"))
        assert len(candidates) == 1
        owned_name = candidates[0]
        replacement_name = owned_name.name
        os.rename(owned_name, moved_owned)
        owned_name.mkdir(mode=0o700)
        (owned_name / "attacker-marker").write_bytes(b"replacement")
        swapped = True

    monkeypatch.setattr(exports, "_fsync_directory_fd", swap_after_staging_fsync)

    with pytest.raises(OSError, match="staging source identity mismatch") as error:
        write_export(destination, manifest, results, summary)

    assert swapped and replacement_name is not None
    assert not destination.exists()
    replacement = tmp_path / replacement_name
    assert (replacement / "attacker-marker").read_bytes() == b"replacement"
    assert sorted(moved_owned.iterdir()) == []
    assert any("externally renamed empty owned staging directory" in note for note in error.value.__notes__)


def test_staging_open_identity_mismatch_preserves_unverified_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import evonn_shared.exports as exports

    manifest, results, summary = models()
    destination = tmp_path / "staging-open-swap"
    moved_owned = tmp_path / "externally-moved-before-open"
    actual_open = exports.os.open
    swapped = False
    replacement: Path | None = None

    def swap_before_staging_open(
        path: object,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal swapped, replacement
        if not swapped and isinstance(path, str) and path.startswith(".staging-open-swap.tmp-"):
            replacement = tmp_path / path
            os.rename(replacement, moved_owned)
            replacement.mkdir(mode=0o700)
            (replacement / MANIFEST_FILENAME).write_bytes(b"replacement manifest")
            (replacement / "attacker-marker").write_bytes(b"replacement")
            swapped = True
        return actual_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(exports.os, "open", swap_before_staging_open)

    with pytest.raises(OSError, match="opened staging directory is not the created inode") as error:
        write_export(destination, manifest, results, summary)

    assert swapped and replacement is not None
    assert not destination.exists()
    assert (replacement / MANIFEST_FILENAME).read_bytes() == b"replacement manifest"
    assert (replacement / "attacker-marker").read_bytes() == b"replacement"
    assert sorted(moved_owned.iterdir()) == []
    assert any("staging descriptor was not verified" in note for note in error.value.__notes__)


def test_same_inode_staging_open_failure_removes_owned_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import evonn_shared.exports as exports

    manifest, results, summary = models()
    destination = tmp_path / "staging-open-emfile"
    actual_open = exports.os.open
    staging_open_attempted = False

    def fail_staging_open(
        path: object,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal staging_open_attempted
        if isinstance(path, str) and path.startswith(".staging-open-emfile.tmp-"):
            staging_open_attempted = True
            raise OSError(errno.EMFILE, "staging open exhausted descriptors")
        return actual_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(exports.os, "open", fail_staging_open)

    with pytest.raises(OSError, match="staging open exhausted descriptors") as error:
        write_export(destination, manifest, results, summary)

    assert error.value.errno == errno.EMFILE
    assert staging_open_attempted
    assert not destination.exists()
    assert not list(tmp_path.glob(".staging-open-emfile.tmp-*"))


def test_post_rename_staging_close_failure_still_attempts_parent_fsync(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import evonn_shared.exports as exports

    manifest, results, summary = models()
    staging_fd: int | None = None
    staging_close_attempts = 0
    fsync_calls: list[int] = []
    original_fsync = exports._fsync_directory_fd

    def track_fsync(descriptor: int) -> None:
        nonlocal staging_fd
        fsync_calls.append(descriptor)
        if staging_fd is None:
            staging_fd = descriptor
        original_fsync(descriptor)

    def fail_staging_close(descriptor: int) -> None:
        nonlocal staging_close_attempts
        if descriptor == staging_fd:
            staging_close_attempts += 1
            raise OSError("post-rename staging close failed")
        os.close(descriptor)

    monkeypatch.setattr(exports, "_fsync_directory_fd", track_fsync)
    monkeypatch.setattr(exports, "_close_descriptor", fail_staging_close, raising=False)
    destination = tmp_path / "post-close"

    try:
        with pytest.raises(OSError, match="post-rename staging close failed"):
            write_export(destination, manifest, results, summary)

        assert len(fsync_calls) == 2
        assert staging_close_attempts == 1
        assert staging_fd is not None
        os.fstat(staging_fd)
        assert sorted(path.name for path in destination.iterdir()) == [
            MANIFEST_FILENAME,
            RESULTS_FILENAME,
            SUMMARY_FILENAME,
        ]
    finally:
        if staging_fd is not None:
            os.close(staging_fd)


def test_post_rename_close_and_parent_fsync_errors_are_aggregated_deterministically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import evonn_shared.exports as exports

    manifest, results, summary = models()
    staging_fd: int | None = None
    staging_close_attempts = 0
    fsync_calls = 0
    original_fsync = exports._fsync_directory_fd

    def fail_parent_fsync(descriptor: int) -> None:
        nonlocal staging_fd, fsync_calls
        fsync_calls += 1
        if fsync_calls == 1:
            staging_fd = descriptor
            original_fsync(descriptor)
            return
        raise OSError("parent fsync also failed")

    def fail_staging_close(descriptor: int) -> None:
        nonlocal staging_close_attempts
        if descriptor == staging_fd:
            staging_close_attempts += 1
            raise OSError("post-rename staging close primary")
        os.close(descriptor)

    monkeypatch.setattr(exports, "_fsync_directory_fd", fail_parent_fsync)
    monkeypatch.setattr(exports, "_close_descriptor", fail_staging_close, raising=False)
    destination = tmp_path / "post-close-and-fsync"

    try:
        with pytest.raises(OSError, match="post-rename staging close primary") as error:
            write_export(destination, manifest, results, summary)

        assert fsync_calls == 2
        assert staging_close_attempts == 1
        assert staging_fd is not None
        os.fstat(staging_fd)
        assert any("parent fsync also failed" in note for note in error.value.__notes__)
        assert sorted(path.name for path in destination.iterdir()) == [
            MANIFEST_FILENAME,
            RESULTS_FILENAME,
            SUMMARY_FILENAME,
        ]
    finally:
        if staging_fd is not None:
            os.close(staging_fd)


def test_restrictive_umask_still_produces_exact_staging_and_file_modes(tmp_path: Path) -> None:
    private_parent = tmp_path / "private-parent"
    private_parent.mkdir(mode=0o700)
    script = """
import os
from pathlib import Path
from evonn_shared.exports import Manifest, Results, RunSummary, write_export
fixture = Path(__import__('sys').argv[1])
parent = Path(__import__('sys').argv[2])
os.umask(0o777)
write_export(
    parent / 'umask-export',
    Manifest.model_validate_json((fixture / 'manifest.json').read_bytes()),
    Results.model_validate_json((fixture / 'results.json').read_bytes()),
    RunSummary.model_validate_json((fixture / 'summary.json').read_bytes()),
)
assert (parent / 'umask-export').stat().st_mode & 0o777 == 0o700
for filename in ('manifest.json', 'results.json', 'summary.json'):
    assert (parent / 'umask-export' / filename).stat().st_mode & 0o777 == 0o600
"""
    subprocess.run(
        [sys.executable, "-c", script, str(FIXTURE_ROOT / "valid"), str(private_parent)],
        check=True,
        cwd=Path(__file__).parents[2],
    )


def test_parent_wrong_owner_is_rejected_before_staging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import evonn_shared.exports as exports

    manifest, results, summary = models()
    parent = tmp_path / "wrong-owner"
    parent.mkdir(mode=0o700)
    actual_lstat = exports.os.lstat

    def wrong_owner_lstat(path: object) -> os.stat_result:
        status = actual_lstat(path)
        if Path(path) == parent:
            values = list(status)
            values[4] = os.geteuid() + 1
            return os.stat_result(values)
        return status

    monkeypatch.setattr(exports.os, "lstat", wrong_owner_lstat)
    with pytest.raises(PermissionError, match="effective UID"):
        write_export(parent / "export", manifest, results, summary)
    assert list(parent.iterdir()) == []


@pytest.mark.parametrize("mode", [0o720, 0o702])
def test_group_or_other_writable_parent_is_rejected_before_staging(tmp_path: Path, mode: int) -> None:
    manifest, results, summary = models()
    parent = tmp_path / f"writable-{mode:o}"
    parent.mkdir(mode=0o700)
    parent.chmod(mode)
    try:
        with pytest.raises(PermissionError, match="group or others"):
            write_export(parent / "export", manifest, results, summary)
        assert list(parent.iterdir()) == []
    finally:
        parent.chmod(0o700)


def test_file_close_failure_is_not_retried_and_test_closes_indeterminate_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import evonn_shared.exports as exports

    manifest, results, summary = models()
    captured: list[object] = []

    def fail_before_file_close(file: object) -> None:
        captured.append(file)
        raise OSError("file close primary")

    monkeypatch.setattr(exports, "_close_file", fail_before_file_close)
    with pytest.raises(OSError, match="file close primary"):
        write_export(tmp_path / "file-close-no-retry", manifest, results, summary)

    assert len(captured) == 1
    file = captured[0]
    descriptor = file.fileno()
    os.fstat(descriptor)
    file.close()
    _assert_fd_closed(descriptor)


def test_staging_cleanup_close_failure_is_not_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import evonn_shared.exports as exports

    manifest, results, summary = models()
    staging_fd: int | None = None
    close_attempts = 0
    original_fsync = exports._fsync_directory_fd

    def capture_staging(descriptor: int) -> None:
        nonlocal staging_fd
        staging_fd = descriptor
        original_fsync(descriptor)

    def fail_staging_close(descriptor: int) -> None:
        nonlocal close_attempts
        if descriptor == staging_fd:
            close_attempts += 1
            raise OSError("staging cleanup close")
        os.close(descriptor)

    monkeypatch.setattr(exports, "_fsync_directory_fd", capture_staging)
    monkeypatch.setattr(exports, "_close_descriptor", fail_staging_close, raising=False)
    monkeypatch.setattr(
        exports,
        "_load_exclusive_rename",
        lambda: lambda parent_fd, source_name, destination_name: (_ for _ in ()).throw(OSError("rename primary")),
    )

    try:
        with pytest.raises(OSError, match="rename primary") as error:
            write_export(tmp_path / "cleanup-close-no-retry", manifest, results, summary)

        assert close_attempts == 1
        assert any("staging cleanup close" in note for note in error.value.__notes__)
        assert staging_fd is not None
        os.fstat(staging_fd)
    finally:
        if staging_fd is not None:
            os.close(staging_fd)


def test_parent_close_failure_is_not_retried_and_preserves_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import evonn_shared.exports as exports

    manifest, results, summary = models()
    parent_fd: int | None = None
    close_attempts = 0
    native = exports._load_exclusive_rename()

    def capture_parent(parent_descriptor: int, source_name: str, destination_name: str) -> None:
        nonlocal parent_fd
        parent_fd = parent_descriptor
        native(parent_descriptor, source_name, destination_name)

    def fail_parent_close(descriptor: int) -> None:
        nonlocal close_attempts
        if descriptor == parent_fd:
            close_attempts += 1
            raise OSError("parent close primary")
        os.close(descriptor)

    monkeypatch.setattr(exports, "_load_exclusive_rename", lambda: capture_parent)
    monkeypatch.setattr(exports, "_close_descriptor", fail_parent_close, raising=False)
    destination = tmp_path / "parent-close-no-retry"

    try:
        with pytest.raises(OSError, match="parent close primary"):
            write_export(destination, manifest, results, summary)

        assert close_attempts == 1
        assert parent_fd is not None
        os.fstat(parent_fd)
        assert sorted(path.name for path in destination.iterdir()) == [
            MANIFEST_FILENAME,
            RESULTS_FILENAME,
            SUMMARY_FILENAME,
        ]
    finally:
        if parent_fd is not None:
            os.close(parent_fd)
