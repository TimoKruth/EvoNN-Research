from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from evonn_shared.telemetry import (
    AggregateMetric,
    ArtifactReference,
    BackendClass,
    BenchmarkResult,
    BestResult,
    Coverage,
    FairnessFlag,
    FairnessSeverity,
    FloatMeasurement,
    IntegerMeasurement,
    MeasurementProvenance,
    MetricDirection,
    MetricValue,
    ResultStatus,
    RuntimeMetadata,
    SeedCostAccounting,
    SeedingLadder,
    SeedingMetadata,
    SeedOverlapPolicy,
    SystemId,
    TaskKind,
    RunTiming,
    WorkerTopology,
)


ENUMS = {
    SystemId: [
        ("PRISM", "prism"), ("TOPOGRAPH", "topograph"), ("STRATOGRAPH", "stratograph"),
        ("PRIMORDIA", "primordia"), ("CONTENDERS", "contenders"), ("EVONN", "evonn"),
        ("EVONN2", "evonn2"), ("HYBRID", "hybrid"),
    ],
    BackendClass: [
        ("MLX_NATIVE", "mlx_native"), ("NUMPY_FALLBACK", "numpy_fallback"),
        ("SKLEARN_CONTENDER", "sklearn_contender"), ("TORCH_OPTIONAL", "torch_optional"),
        ("UNSUPPORTED", "unsupported"),
    ],
    TaskKind: [
        ("CLASSIFICATION", "classification"), ("REGRESSION", "regression"),
        ("LANGUAGE_MODELING", "language_modeling"), ("FORECASTING", "forecasting"),
    ],
    MetricDirection: [("MAX", "max"), ("MIN", "min")],
    ResultStatus: [("OK", "ok"), ("FAILED", "failed"), ("SKIPPED", "skipped"), ("UNSUPPORTED", "unsupported")],
    MeasurementProvenance: [("MEASURED", "measured"), ("ESTIMATED", "estimated"), ("UNAVAILABLE", "unavailable")],
    SeedingLadder: [("NONE", "none"), ("DIRECT", "direct"), ("STAGED", "staged")],
    SeedOverlapPolicy: [
        ("BENCHMARK_DISJOINT", "benchmark-disjoint"),
        ("BENCHMARK_OVERLAPPING", "benchmark-overlapping"),
        ("FAMILY_OVERLAPPING", "family-overlapping"),
        ("UNKNOWN", "unknown"),
    ],
    SeedCostAccounting: [("FREE_PRIOR", "free_prior"), ("CHARGED_PRIOR", "charged_prior"), ("REPORTED_PRIOR", "reported_prior")],
    FairnessSeverity: [("INFO", "info"), ("WARNING", "warning"), ("BLOCKER", "blocker")],
}

PUBLIC_FIELDS = {
    RunTiming: {"started_at", "ended_at", "latest_checkpoint_at", "elapsed_seconds"},
    WorkerTopology: {"worker_count", "process_count", "threads_per_worker"},
    RuntimeMetadata: {"backend", "backend_version", "device_class", "precision_mode", "worker_topology", "host_fingerprint"},
    SeedingMetadata: {
        "seeding_enabled", "seeding_ladder", "seed_source_system", "seed_source_run_id",
        "seed_artifact_path", "seed_target_family", "seed_selected_family", "seed_rank",
        "seed_overlap_policy", "seed_cost_accounting", "seed_source_evaluations",
    },
    ArtifactReference: {"path", "sha256"},
    IntegerMeasurement: {"value", "provenance"},
    FloatMeasurement: {"value", "provenance"},
    MetricValue: {"name", "direction", "value"},
    BenchmarkResult: {
        "benchmark_id", "outcome_id", "task_kind", "metric", "status", "reason", "parameter_count",
        "train_seconds", "model_bytes", "peak_memory_bytes", "evaluation_count",
    },
    Coverage: {"benchmark_count", "result_count", "ok", "failed", "skipped", "unsupported"},
    BestResult: {"benchmark_id", "outcome_id", "metric_name", "direction", "value"},
    AggregateMetric: {"name", "direction", "value", "benchmark_count"},
    FairnessFlag: {"code", "severity", "message", "benchmark_ids"},
}

UTC = dt.timezone.utc


def unseeded_data() -> dict[str, object]:
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


def seeded_data(**changes: object) -> dict[str, object]:
    data: dict[str, object] = {
        "seeding_enabled": True,
        "seeding_ladder": SeedingLadder.DIRECT,
        "seed_source_system": SystemId.PRISM,
        "seed_source_run_id": "prior.run",
        "seed_artifact_path": "seeds/prior.json",
        "seed_target_family": "target family",
        "seed_selected_family": "selected family",
        "seed_rank": 1,
        "seed_overlap_policy": SeedOverlapPolicy.BENCHMARK_DISJOINT,
        "seed_cost_accounting": SeedCostAccounting.FREE_PRIOR,
        "seed_source_evaluations": 0,
    }
    data.update(changes)
    return data


def measurement_data(value: int | float | None, provenance: MeasurementProvenance) -> dict[str, object]:
    return {"value": value, "provenance": provenance}


def result_data(**changes: object) -> dict[str, object]:
    data: dict[str, object] = {
        "benchmark_id": "alpha_case",
        "outcome_id": "candidate_one",
        "task_kind": TaskKind.CLASSIFICATION,
        "metric": {"name": "accuracy", "direction": MetricDirection.MAX, "value": 0.8},
        "status": ResultStatus.OK,
        "reason": None,
        "parameter_count": measurement_data(100, MeasurementProvenance.MEASURED),
        "train_seconds": measurement_data(1.5, MeasurementProvenance.MEASURED),
        "model_bytes": measurement_data(400, MeasurementProvenance.MEASURED),
        "peak_memory_bytes": measurement_data(None, MeasurementProvenance.UNAVAILABLE),
        "evaluation_count": 1,
    }
    data.update(changes)
    return data


def test_exact_enums_and_public_model_fields() -> None:
    for enum, expected in ENUMS.items():
        assert [(member.name, member.value) for member in enum] == expected
    for model, fields in PUBLIC_FIELDS.items():
        assert set(model.model_fields) == fields


def test_run_timing_accepts_exact_elapsed_to_end_or_checkpoint() -> None:
    start = dt.datetime(2026, 7, 21, 10, 0, tzinfo=UTC)
    end = dt.datetime(2026, 7, 21, 10, 2, tzinfo=UTC)
    timing = RunTiming(started_at=start, ended_at=end, latest_checkpoint_at=None, elapsed_seconds=120.0)
    assert timing.elapsed_seconds == 120.0

    checkpoint = dt.datetime(2026, 7, 21, 10, 1, tzinfo=UTC)
    timing = RunTiming(started_at=start, ended_at=None, latest_checkpoint_at=checkpoint, elapsed_seconds=60.0)
    assert timing.latest_checkpoint_at == checkpoint


@pytest.mark.parametrize(
    "changes",
    [
        {"started_at": dt.datetime(2026, 7, 21, 10, 0), "ended_at": dt.datetime(2026, 7, 21, 10, 1, tzinfo=UTC)},
        {"ended_at": dt.datetime(2026, 7, 21, 10, 1, tzinfo=dt.timezone(dt.timedelta(hours=1)))},
        {"ended_at": None, "latest_checkpoint_at": None},
        {"ended_at": dt.datetime(2026, 7, 21, 9, 59, tzinfo=UTC)},
        {"elapsed_seconds": -1.0},
        {"elapsed_seconds": float("nan")},
        {"elapsed_seconds": 61.0},
    ],
)
def test_run_timing_rejects_non_utc_missing_reversed_nonfinite_or_mismatched_values(changes: dict[str, object]) -> None:
    data: dict[str, object] = {
        "started_at": dt.datetime(2026, 7, 21, 10, 0, tzinfo=UTC),
        "ended_at": dt.datetime(2026, 7, 21, 10, 1, tzinfo=UTC),
        "latest_checkpoint_at": None,
        "elapsed_seconds": 60.0,
    }
    data.update(changes)
    with pytest.raises(ValidationError):
        RunTiming.model_validate(data)


def test_timing_json_uses_rfc3339_z_and_accepts_it() -> None:
    timing = RunTiming.model_validate_json(
        b'{"started_at":"2026-07-21T10:00:00Z","ended_at":"2026-07-21T10:01:00Z",'
        b'"latest_checkpoint_at":null,"elapsed_seconds":60.0}'
    )
    assert timing.model_dump_json().count("Z") == 2


@pytest.mark.parametrize("changes", [{"worker_count": 0}, {"process_count": 0}, {"threads_per_worker": 0}, {"worker_count": 1, "process_count": 2}])
def test_worker_topology_requires_positive_consistent_counts(changes: dict[str, int]) -> None:
    data = {"worker_count": 2, "process_count": 1, "threads_per_worker": 4} | changes
    with pytest.raises(ValidationError):
        WorkerTopology.model_validate(data)


def test_runtime_requires_text_sha256_and_closed_backend() -> None:
    runtime = RuntimeMetadata(
        backend=BackendClass.MLX_NATIVE,
        backend_version="1.0",
        device_class="apple-m3",
        precision_mode="float32",
        worker_topology=WorkerTopology(worker_count=2, process_count=1, threads_per_worker=4),
        host_fingerprint="a" * 64,
    )
    assert runtime.backend is BackendClass.MLX_NATIVE
    for fingerprint in ["A" * 64, "a" * 63, "g" * 64]:
        data = runtime.model_dump()
        data["host_fingerprint"] = fingerprint
        with pytest.raises(ValidationError):
            RuntimeMetadata.model_validate(data)


def test_unseeded_state_is_exact() -> None:
    assert SeedingMetadata.model_validate(unseeded_data()).model_dump() == unseeded_data()


@pytest.mark.parametrize("ladder", [SeedingLadder.DIRECT, SeedingLadder.STAGED])
@pytest.mark.parametrize("cost", list(SeedCostAccounting))
def test_seeded_direct_and_staged_states_accept_every_cost_mode(ladder: SeedingLadder, cost: SeedCostAccounting) -> None:
    seeded = SeedingMetadata.model_validate(seeded_data(seeding_ladder=ladder, seed_cost_accounting=cost))
    assert seeded.seed_overlap_policy is SeedOverlapPolicy.BENCHMARK_DISJOINT


@pytest.mark.parametrize(
    "data",
    [
        seeded_data(seeding_ladder=SeedingLadder.NONE),
        unseeded_data() | {"seeding_ladder": SeedingLadder.DIRECT},
        unseeded_data() | {"seed_source_run_id": "hidden"},
        seeded_data(seed_source_system=None),
        seeded_data(seed_source_system=SystemId.CONTENDERS),
        seeded_data(seed_source_system=SystemId.EVONN),
        seeded_data(seed_rank=0),
        seeded_data(seed_cost_accounting=None),
        seeded_data(seed_source_evaluations=None),
        seeded_data(seed_source_evaluations=-1),
    ],
)
def test_seeding_state_matrix_rejects_invalid_combinations(data: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SeedingMetadata.model_validate(data)


def test_seeded_unknown_overlap_is_explicitly_accepted() -> None:
    assert SeedingMetadata.model_validate(seeded_data(seed_overlap_policy=SeedOverlapPolicy.UNKNOWN)).seed_overlap_policy is SeedOverlapPolicy.UNKNOWN


@pytest.mark.parametrize("path", ["", "/absolute", "a\\b", "a//b", "a/./b", "a/../b", "trailing/", "nul\x00path"])
def test_artifact_paths_reject_nonrelative_or_unnormalized_values(path: str) -> None:
    with pytest.raises(ValidationError):
        ArtifactReference(path=path, sha256="a" * 64)


@pytest.mark.parametrize("digest", ["a" * 63, "A" * 64, "g" * 64])
def test_artifact_digest_must_be_lowercase_sha256(digest: str) -> None:
    with pytest.raises(ValidationError):
        ArtifactReference(path="artifact.json", sha256=digest)


@pytest.mark.parametrize("model", [IntegerMeasurement, FloatMeasurement])
@pytest.mark.parametrize(
    ("value", "provenance", "valid"),
    [
        (0, MeasurementProvenance.MEASURED, True),
        (1, MeasurementProvenance.ESTIMATED, True),
        (None, MeasurementProvenance.UNAVAILABLE, True),
        (None, MeasurementProvenance.MEASURED, False),
        (1, MeasurementProvenance.UNAVAILABLE, False),
        (-1, MeasurementProvenance.ESTIMATED, False),
    ],
)
def test_measurement_provenance_value_matrix(model: type[IntegerMeasurement] | type[FloatMeasurement], value: object, provenance: MeasurementProvenance, valid: bool) -> None:
    data_value = float(value) if model is FloatMeasurement and value is not None else value
    if valid:
        assert model(value=data_value, provenance=provenance).provenance is provenance
    else:
        with pytest.raises(ValidationError):
            model(value=data_value, provenance=provenance)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_float_measurements_reject_nonfinite_values(value: float) -> None:
    with pytest.raises(ValidationError):
        FloatMeasurement(value=value, provenance=MeasurementProvenance.MEASURED)


@pytest.mark.parametrize(
    ("status", "metric_value", "reason"),
    [
        (ResultStatus.OK, 0.8, None),
        (ResultStatus.FAILED, None, "training failed"),
        (ResultStatus.SKIPPED, None, "not selected"),
        (ResultStatus.UNSUPPORTED, None, "backend unsupported"),
    ],
)
def test_benchmark_result_status_matrix_accepts_all_four_visible_outcomes(status: ResultStatus, metric_value: float | None, reason: str | None) -> None:
    data = result_data(status=status, reason=reason, metric={"name": "accuracy", "direction": MetricDirection.MAX, "value": metric_value})
    assert BenchmarkResult.model_validate(data).status is status


@pytest.mark.parametrize(
    "changes",
    [
        {"status": ResultStatus.OK, "reason": "unexpected"},
        {"status": ResultStatus.OK, "metric": {"name": "accuracy", "direction": MetricDirection.MAX, "value": None}},
        {"status": ResultStatus.FAILED, "reason": None, "metric": {"name": "accuracy", "direction": MetricDirection.MAX, "value": None}},
        {"status": ResultStatus.SKIPPED, "reason": " ", "metric": {"name": "accuracy", "direction": MetricDirection.MAX, "value": None}},
        {"status": ResultStatus.FAILED, "reason": "failed", "metric": {"name": "accuracy", "direction": MetricDirection.MAX, "value": 0.2}},
        {"benchmark_id": "Bad-ID"},
        {"outcome_id": "../bad"},
        {"evaluation_count": -1},
    ],
)
def test_benchmark_result_rejects_invalid_status_ids_and_counts(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        BenchmarkResult.model_validate(result_data(**changes))


def test_task_kinds_and_metric_directions_are_accepted() -> None:
    for task_kind in TaskKind:
        for direction in MetricDirection:
            result = BenchmarkResult.model_validate(result_data(task_kind=task_kind, metric={"name": "score", "direction": direction, "value": 1.0}))
            assert result.task_kind is task_kind


@pytest.mark.parametrize(
    "changes",
    [
        {"ok": 2},
        {"benchmark_count": -1},
        {"result_count": -1},
        {"failed": -1},
    ],
)
def test_coverage_requires_nonnegative_counts_and_exact_status_sum(changes: dict[str, int]) -> None:
    data = {"benchmark_count": 1, "result_count": 1, "ok": 1, "failed": 0, "skipped": 0, "unsupported": 0} | changes
    with pytest.raises(ValidationError):
        Coverage.model_validate(data)


def test_best_aggregate_and_fairness_shapes_validate_finite_sorted_values() -> None:
    best = BestResult(benchmark_id="alpha", outcome_id="one", metric_name="score", direction=MetricDirection.MAX, value=1.0)
    aggregate = AggregateMetric(name="mean_score", direction=MetricDirection.MAX, value=0.5, benchmark_count=1)
    flag = FairnessFlag(code="cached_work", severity=FairnessSeverity.WARNING, message="cache used", benchmark_ids=("alpha", "beta"))
    assert best.value == 1.0 and aggregate.benchmark_count == 1 and flag.benchmark_ids == ("alpha", "beta")

    with pytest.raises(ValidationError):
        AggregateMetric(name="mean_score", direction=MetricDirection.MAX, value=float("nan"), benchmark_count=1)
    with pytest.raises(ValidationError):
        FairnessFlag(code="cached_work", severity=FairnessSeverity.WARNING, message="cache used", benchmark_ids=("beta", "alpha"))
    with pytest.raises(ValidationError):
        FairnessFlag(code="cached_work", severity=FairnessSeverity.WARNING, message="cache used", benchmark_ids=("alpha", "alpha"))


def test_every_telemetry_model_rejects_each_missing_field_and_unknown_fields() -> None:
    timing = {
        "started_at": dt.datetime(2026, 7, 21, 10, 0, tzinfo=UTC),
        "ended_at": dt.datetime(2026, 7, 21, 10, 1, tzinfo=UTC),
        "latest_checkpoint_at": None,
        "elapsed_seconds": 60.0,
    }
    topology = {"worker_count": 2, "process_count": 1, "threads_per_worker": 4}
    cases: dict[type[object], dict[str, object]] = {
        RunTiming: timing,
        WorkerTopology: topology,
        RuntimeMetadata: {
            "backend": BackendClass.MLX_NATIVE,
            "backend_version": "1.0",
            "device_class": "apple-m3",
            "precision_mode": "float32",
            "worker_topology": topology,
            "host_fingerprint": "a" * 64,
        },
        SeedingMetadata: unseeded_data(),
        ArtifactReference: {"path": "artifact.json", "sha256": "a" * 64},
        IntegerMeasurement: measurement_data(1, MeasurementProvenance.MEASURED),
        FloatMeasurement: measurement_data(1.0, MeasurementProvenance.MEASURED),
        MetricValue: {"name": "score", "direction": MetricDirection.MAX, "value": 1.0},
        BenchmarkResult: result_data(),
        Coverage: {"benchmark_count": 1, "result_count": 1, "ok": 1, "failed": 0, "skipped": 0, "unsupported": 0},
        BestResult: {"benchmark_id": "alpha", "outcome_id": "one", "metric_name": "score", "direction": MetricDirection.MAX, "value": 1.0},
        AggregateMetric: {"name": "mean_score", "direction": MetricDirection.MAX, "value": 1.0, "benchmark_count": 1},
        FairnessFlag: {"code": "visible", "severity": FairnessSeverity.INFO, "message": "visible", "benchmark_ids": ("alpha",)},
    }
    for model, valid in cases.items():
        for field_name in model.model_fields:
            missing = dict(valid)
            del missing[field_name]
            with pytest.raises(ValidationError):
                model.model_validate(missing)
        unknown = dict(valid)
        unknown["unknown"] = "forbidden"
        with pytest.raises(ValidationError):
            model.model_validate(unknown)


def test_invalid_utf8_surrogates_and_hostile_scalar_subclasses_reject_without_dispatch() -> None:
    class HostileStr(str):
        def split(self, *args: object, **kwargs: object) -> list[str]:
            raise AssertionError("must not dispatch")

    class HostileFloat(float):
        def __float__(self) -> float:
            raise AssertionError("must not dispatch")

    with pytest.raises(ValidationError):
        ArtifactReference(path="bad\ud800path", sha256="a" * 64)
    with pytest.raises(ValidationError):
        ArtifactReference(path=HostileStr("artifact.json"), sha256="a" * 64)
    with pytest.raises(ValidationError):
        FloatMeasurement(value=HostileFloat(1.0), provenance=MeasurementProvenance.MEASURED)
