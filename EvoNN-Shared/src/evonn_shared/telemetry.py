"""Frozen runtime, seeding, artifact, and result telemetry contracts."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
import math
import re
from typing import Any

from pydantic import Field, field_validator, model_validator

from .budgets import (
    ContractModel,
    _canonical_id,
    _finite,
    _human_text,
    _run_id,
    _utf8_sorted_unique,
)

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_RFC3339_UTC_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{6})?Z$"
)


class SystemId(StrEnum):
    PRISM = "prism"
    TOPOGRAPH = "topograph"
    STRATOGRAPH = "stratograph"
    PRIMORDIA = "primordia"
    CONTENDERS = "contenders"
    EVONN = "evonn"
    EVONN2 = "evonn2"
    HYBRID = "hybrid"


class BackendClass(StrEnum):
    MLX_NATIVE = "mlx_native"
    NUMPY_FALLBACK = "numpy_fallback"
    SKLEARN_CONTENDER = "sklearn_contender"
    TORCH_OPTIONAL = "torch_optional"
    UNSUPPORTED = "unsupported"


class TaskKind(StrEnum):
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    LANGUAGE_MODELING = "language_modeling"
    FORECASTING = "forecasting"


class MetricDirection(StrEnum):
    MAX = "max"
    MIN = "min"


class ResultStatus(StrEnum):
    OK = "ok"
    FAILED = "failed"
    SKIPPED = "skipped"
    UNSUPPORTED = "unsupported"


class MeasurementProvenance(StrEnum):
    MEASURED = "measured"
    ESTIMATED = "estimated"
    UNAVAILABLE = "unavailable"


class SeedingLadder(StrEnum):
    NONE = "none"
    DIRECT = "direct"
    STAGED = "staged"


class SeedOverlapPolicy(StrEnum):
    BENCHMARK_DISJOINT = "benchmark-disjoint"
    BENCHMARK_OVERLAPPING = "benchmark-overlapping"
    FAMILY_OVERLAPPING = "family-overlapping"
    UNKNOWN = "unknown"


class SeedCostAccounting(StrEnum):
    FREE_PRIOR = "free_prior"
    CHARGED_PRIOR = "charged_prior"
    REPORTED_PRIOR = "reported_prior"


class FairnessSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"


class RunTiming(ContractModel):
    started_at: dt.datetime
    ended_at: dt.datetime | None
    latest_checkpoint_at: dt.datetime | None
    elapsed_seconds: float = Field(ge=0)

    @field_validator("started_at", "ended_at", "latest_checkpoint_at", mode="before")
    @classmethod
    def _reject_datetime_subclasses(cls, value: object, info: Any) -> object:
        if info.mode == "json" and type(value) is str:
            if _RFC3339_UTC_PATTERN.fullmatch(value) is None:
                raise ValueError("timing markers must use canonical RFC 3339 UTC strings")
            try:
                return dt.datetime.fromisoformat(value[:-1] + "+00:00")
            except ValueError as error:
                raise ValueError("timing markers must use canonical RFC 3339 UTC strings") from error
        if value is not None and isinstance(value, dt.datetime) and type(value) is not dt.datetime:
            raise ValueError("datetime subclasses are not accepted")
        return value

    @field_validator("started_at", "ended_at", "latest_checkpoint_at")
    @classmethod
    def _validate_utc(cls, value: dt.datetime | None, info: Any) -> dt.datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() != dt.timedelta(0):
            raise ValueError(f"{info.field_name} must be timezone-aware UTC")
        return value

    @field_validator("elapsed_seconds", mode="before")
    @classmethod
    def _strict_elapsed_float(cls, value: object) -> object:
        if type(value) is not float:
            raise ValueError("elapsed_seconds must be a float")
        return value

    @field_validator("elapsed_seconds")
    @classmethod
    def _validate_elapsed_finite(cls, value: float) -> float:
        return _finite(value, "elapsed_seconds")

    @model_validator(mode="after")
    def _validate_markers(self) -> RunTiming:
        marker = self.ended_at if self.ended_at is not None else self.latest_checkpoint_at
        if marker is None:
            raise ValueError("ended_at or latest_checkpoint_at must be present")
        for present in (self.ended_at, self.latest_checkpoint_at):
            if present is not None and present < self.started_at:
                raise ValueError("timing markers must not precede started_at")
        if self.elapsed_seconds != (marker - self.started_at).total_seconds():
            raise ValueError("elapsed_seconds must exactly match the preferred timing marker")
        return self


class WorkerTopology(ContractModel):
    worker_count: int = Field(gt=0)
    process_count: int = Field(gt=0)
    threads_per_worker: int = Field(gt=0)

    @model_validator(mode="after")
    def _validate_processes(self) -> WorkerTopology:
        if self.process_count > self.worker_count:
            raise ValueError("process_count must not exceed worker_count")
        return self


class RuntimeMetadata(ContractModel):
    backend: BackendClass
    backend_version: str
    device_class: str
    precision_mode: str
    worker_topology: WorkerTopology
    host_fingerprint: str

    @field_validator("backend_version", "device_class", "precision_mode")
    @classmethod
    def _validate_text(cls, value: str, info: Any) -> str:
        return _human_text(value, info.field_name)

    @field_validator("host_fingerprint")
    @classmethod
    def _validate_fingerprint(cls, value: str) -> str:
        if _SHA256_PATTERN.fullmatch(value) is None:
            raise ValueError("host_fingerprint must be a lowercase SHA-256 digest")
        return value


class SeedingMetadata(ContractModel):
    seeding_enabled: bool
    seeding_ladder: SeedingLadder
    seed_source_system: SystemId | None
    seed_source_run_id: str | None
    seed_artifact_path: str | None
    seed_target_family: str | None
    seed_selected_family: str | None
    seed_rank: int | None
    seed_overlap_policy: SeedOverlapPolicy
    seed_cost_accounting: SeedCostAccounting | None
    seed_source_evaluations: int | None

    @field_validator("seed_source_run_id")
    @classmethod
    def _validate_source_run(cls, value: str | None) -> str | None:
        return None if value is None else _run_id(value, "seed_source_run_id")

    @field_validator("seed_artifact_path")
    @classmethod
    def _validate_seed_path(cls, value: str | None) -> str | None:
        return None if value is None else _artifact_path(value)

    @field_validator("seed_target_family", "seed_selected_family")
    @classmethod
    def _validate_family(cls, value: str | None, info: Any) -> str | None:
        return None if value is None else _human_text(value, info.field_name)

    @field_validator("seed_rank")
    @classmethod
    def _validate_rank(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("seed_rank must be positive when present")
        return value

    @field_validator("seed_source_evaluations")
    @classmethod
    def _validate_source_evaluations(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("seed_source_evaluations must be nonnegative when present")
        return value

    @model_validator(mode="after")
    def _validate_state(self) -> SeedingMetadata:
        provenance = (
            self.seed_source_system,
            self.seed_source_run_id,
            self.seed_artifact_path,
            self.seed_target_family,
            self.seed_selected_family,
            self.seed_rank,
            self.seed_cost_accounting,
            self.seed_source_evaluations,
        )
        if not self.seeding_enabled:
            if self.seeding_ladder is not SeedingLadder.NONE:
                raise ValueError("unseeded runs must use the none ladder")
            if self.seed_overlap_policy is not SeedOverlapPolicy.UNKNOWN:
                raise ValueError("unseeded runs must use unknown overlap policy")
            if any(value is not None for value in provenance):
                raise ValueError("unseeded runs must not hide seed provenance")
            return self
        if self.seeding_ladder not in (SeedingLadder.DIRECT, SeedingLadder.STAGED):
            raise ValueError("seeded runs must use direct or staged ladder")
        if any(value is None for value in provenance):
            raise ValueError("seeded runs require complete seed provenance and cost")
        allowed_sources = {
            SystemId.PRISM,
            SystemId.TOPOGRAPH,
            SystemId.STRATOGRAPH,
            SystemId.PRIMORDIA,
        }
        if self.seed_source_system not in allowed_sources:
            raise ValueError("seed source system is not an allowed research system")
        return self


def _artifact_path(value: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError("artifact path must contain valid UTF-8 text") from error
    if not value or "\x00" in value or "\\" in value or value.startswith("/"):
        raise ValueError("artifact path must be a nonempty relative POSIX path")
    components = value.split("/")
    if any(component in ("", ".", "..") for component in components):
        raise ValueError("artifact path components must be normalized and safe")
    return value


class ArtifactReference(ContractModel):
    path: str
    sha256: str

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        return _artifact_path(value)

    @field_validator("sha256")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        if _SHA256_PATTERN.fullmatch(value) is None:
            raise ValueError("sha256 must be exactly 64 lowercase hex characters")
        return value


class IntegerMeasurement(ContractModel):
    value: int | None
    provenance: MeasurementProvenance

    @model_validator(mode="after")
    def _validate_measurement(self) -> IntegerMeasurement:
        _validate_measurement_state(self.value, self.provenance)
        return self


class FloatMeasurement(ContractModel):
    value: float | None
    provenance: MeasurementProvenance

    @field_validator("value", mode="before")
    @classmethod
    def _strict_optional_float(cls, value: object) -> object:
        if value is not None and type(value) is not float:
            raise ValueError("measurement value must be a float or None")
        return value

    @model_validator(mode="after")
    def _validate_measurement(self) -> FloatMeasurement:
        _validate_measurement_state(self.value, self.provenance)
        return self


def _validate_measurement_state(value: int | float | None, provenance: MeasurementProvenance) -> None:
    if provenance is MeasurementProvenance.UNAVAILABLE:
        if value is not None:
            raise ValueError("unavailable measurements must have null value")
        return
    if value is None:
        raise ValueError("measured and estimated measurements require a value")
    if value < 0 or isinstance(value, float) and not math.isfinite(value):
        raise ValueError("measurement values must be finite and nonnegative")


class MetricValue(ContractModel):
    name: str
    direction: MetricDirection
    value: float | None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return _human_text(value, "name")

    @field_validator("value", mode="before")
    @classmethod
    def _strict_optional_float(cls, value: object) -> object:
        if value is not None and type(value) is not float:
            raise ValueError("metric value must be a float or None")
        return value

    @field_validator("value")
    @classmethod
    def _validate_finite(cls, value: float | None) -> float | None:
        return None if value is None else _finite(value, "value")


class BenchmarkResult(ContractModel):
    benchmark_id: str
    outcome_id: str
    task_kind: TaskKind
    metric: MetricValue
    status: ResultStatus
    reason: str | None
    parameter_count: IntegerMeasurement
    train_seconds: FloatMeasurement
    model_bytes: IntegerMeasurement
    peak_memory_bytes: IntegerMeasurement
    evaluation_count: int = Field(ge=0)

    @field_validator("benchmark_id", "outcome_id")
    @classmethod
    def _validate_id(cls, value: str, info: Any) -> str:
        return _canonical_id(value, info.field_name)

    @field_validator("reason")
    @classmethod
    def _validate_reason_text(cls, value: str | None) -> str | None:
        return None if value is None else _human_text(value, "reason")

    @model_validator(mode="after")
    def _validate_outcome(self) -> BenchmarkResult:
        if self.status is ResultStatus.OK:
            if self.metric.value is None or self.reason is not None:
                raise ValueError("ok results require a metric value and null reason")
        elif self.metric.value is not None or self.reason is None:
            raise ValueError("non-ok results require null metric value and nonempty reason")
        return self


class Coverage(ContractModel):
    benchmark_count: int = Field(ge=0)
    result_count: int = Field(ge=0)
    ok: int = Field(ge=0)
    failed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    unsupported: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_total(self) -> Coverage:
        if self.ok + self.failed + self.skipped + self.unsupported != self.result_count:
            raise ValueError("coverage status counts must sum exactly to result_count")
        return self


class BestResult(ContractModel):
    benchmark_id: str
    outcome_id: str
    metric_name: str
    direction: MetricDirection
    value: float

    @field_validator("benchmark_id", "outcome_id")
    @classmethod
    def _validate_id(cls, value: str, info: Any) -> str:
        return _canonical_id(value, info.field_name)

    @field_validator("metric_name")
    @classmethod
    def _validate_metric_name(cls, value: str) -> str:
        return _human_text(value, "metric_name")

    @field_validator("value", mode="before")
    @classmethod
    def _strict_float(cls, value: object) -> object:
        if type(value) is not float:
            raise ValueError("best value must be a float")
        return value

    @field_validator("value")
    @classmethod
    def _validate_finite(cls, value: float) -> float:
        return _finite(value, "value")


class AggregateMetric(ContractModel):
    name: str
    direction: MetricDirection
    value: float
    benchmark_count: int = Field(ge=0)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return _human_text(value, "name")

    @field_validator("value", mode="before")
    @classmethod
    def _strict_float(cls, value: object) -> object:
        if type(value) is not float:
            raise ValueError("aggregate value must be a float")
        return value

    @field_validator("value")
    @classmethod
    def _validate_finite(cls, value: float) -> float:
        return _finite(value, "value")


class FairnessFlag(ContractModel):
    code: str
    severity: FairnessSeverity
    message: str
    benchmark_ids: tuple[str, ...]

    @field_validator("code", "message")
    @classmethod
    def _validate_text(cls, value: str, info: Any) -> str:
        return _human_text(value, info.field_name)

    @field_validator("benchmark_ids")
    @classmethod
    def _validate_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for benchmark_id in value:
            _canonical_id(benchmark_id, "benchmark_ids")
        return _utf8_sorted_unique(value, "benchmark_ids")


__all__ = [
    "AggregateMetric",
    "ArtifactReference",
    "BackendClass",
    "BenchmarkResult",
    "BestResult",
    "Coverage",
    "FairnessFlag",
    "FairnessSeverity",
    "FloatMeasurement",
    "IntegerMeasurement",
    "MeasurementProvenance",
    "MetricDirection",
    "MetricValue",
    "ResultStatus",
    "RuntimeMetadata",
    "SeedCostAccounting",
    "SeedingLadder",
    "SeedingMetadata",
    "SeedOverlapPolicy",
    "SystemId",
    "TaskKind",
    "RunTiming",
    "WorkerTopology",
]
