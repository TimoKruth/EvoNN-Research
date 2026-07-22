"""Frozen budget declarations and accounting contracts."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum, StrEnum
import math
import re
import unicodedata
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

_CANONICAL_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _reject_scalar_subclasses(value: object) -> None:
    if isinstance(value, Enum):
        return
    value_type = type(value)
    if isinstance(value, bool):
        if value_type is not bool:
            raise ValueError("boolean subclasses are not accepted")
        return
    if isinstance(value, int):
        if value_type is not int:
            raise ValueError("integer subclasses are not accepted")
        return
    if isinstance(value, float):
        if value_type is not float:
            raise ValueError("float subclasses are not accepted")
        return
    if isinstance(value, str):
        if value_type is not str:
            raise ValueError("string subclasses are not accepted")
        return
    if isinstance(value, Mapping):
        if value_type is not dict:
            raise ValueError("mapping subclasses are not accepted")
        for key, item in value.items():
            _reject_scalar_subclasses(key)
            _reject_scalar_subclasses(item)
        return
    if isinstance(value, (tuple, list)):
        if value_type not in (tuple, list):
            raise ValueError("sequence subclasses are not accepted")
        for item in value:
            _reject_scalar_subclasses(item)


def _json_arrays_to_tuples(value: object) -> object:
    value_type = type(value)
    if value_type is list:
        return tuple(_json_arrays_to_tuples(item) for item in value)
    if value_type is dict:
        return {key: _json_arrays_to_tuples(item) for key, item in value.items()}
    return value


def _human_text(value: str, field_name: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{field_name} must contain valid UTF-8 text") from error
    if not value.strip():
        raise ValueError(f"{field_name} must be nonempty after whitespace stripping")
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError(f"{field_name} must not contain control characters")
    return value


def _canonical_id(value: str, field_name: str) -> str:
    if _CANONICAL_ID_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a canonical lowercase snake-case identifier")
    return value


def _run_id(value: str, field_name: str = "run_id") -> str:
    if len(value) > 128 or _RUN_ID_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a safe run identifier of at most 128 characters")
    return value


def _finite(value: float, field_name: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{field_name} must be finite")
    return value


def _utf8_sorted_unique(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    for value in values:
        _human_text(value, field_name)
    ordered = tuple(sorted(values, key=lambda value: value.encode("utf-8")))
    if values != ordered:
        raise ValueError(f"{field_name} must be UTF-8 sorted")
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must not contain duplicates")
    return values


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    @model_validator(mode="before")
    @classmethod
    def _prepare_input(cls, value: object, info: ValidationInfo) -> object:
        _reject_scalar_subclasses(value)
        if info.mode == "json":
            return _json_arrays_to_tuples(value)
        return value


class LadderTier(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


class EvaluationStage(ContractModel):
    name: str
    evaluations: int = Field(ge=0)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return _human_text(value, "name")


class EvaluationBudget(ContractModel):
    total: int = Field(gt=0)
    stages: tuple[EvaluationStage, ...]

    @model_validator(mode="after")
    def _validate_stages(self) -> EvaluationBudget:
        names = tuple(stage.name for stage in self.stages)
        if len(names) != len(set(names)):
            raise ValueError("evaluation stage names must be unique")
        if self.stages and sum(stage.evaluations for stage in self.stages) != self.total:
            raise ValueError("evaluation stage counts must sum exactly to total")
        return self


class WallClockBudget(ContractModel):
    target_seconds: float = Field(gt=0)

    @field_validator("target_seconds", mode="before")
    @classmethod
    def _strict_float(cls, value: object) -> object:
        if type(value) is not float:
            raise ValueError("target_seconds must be a float")
        return value

    @field_validator("target_seconds")
    @classmethod
    def _validate_finite(cls, value: float) -> float:
        return _finite(value, "target_seconds")


class TrainingBudget(ContractModel):
    unit: str
    per_candidate: float = Field(ge=0)
    total_cap: float = Field(ge=0)

    @field_validator("unit")
    @classmethod
    def _validate_unit(cls, value: str) -> str:
        return _human_text(value, "unit")

    @field_validator("per_candidate", "total_cap", mode="before")
    @classmethod
    def _strict_float(cls, value: object) -> object:
        if type(value) is not float:
            raise ValueError("training budget values must be floats")
        return value

    @field_validator("per_candidate", "total_cap")
    @classmethod
    def _validate_finite(cls, value: float, info: Any) -> float:
        return _finite(value, info.field_name)


class HardwareEnvelope(ContractModel):
    device_class: str
    cpu_count: int = Field(gt=0)
    accelerator_type: str | None
    memory_ceiling_bytes: int | None
    worker_count: int = Field(gt=0)

    @field_validator("device_class")
    @classmethod
    def _validate_device_class(cls, value: str) -> str:
        return _human_text(value, "device_class")

    @field_validator("accelerator_type")
    @classmethod
    def _validate_accelerator(cls, value: str | None) -> str | None:
        return None if value is None else _human_text(value, "accelerator_type")

    @field_validator("memory_ceiling_bytes")
    @classmethod
    def _validate_memory(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("memory_ceiling_bytes must be positive when present")
        return value


class ModelArtifactBudget(ContractModel):
    parameter_cap: int | None
    model_bytes_cap: int | None
    memory_target_bytes: int | None
    latency_target_seconds: float | None

    @field_validator("parameter_cap", "model_bytes_cap", "memory_target_bytes")
    @classmethod
    def _validate_optional_integer(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("artifact integer targets must be positive when present")
        return value

    @field_validator("latency_target_seconds", mode="before")
    @classmethod
    def _strict_optional_float(cls, value: object) -> object:
        if value is not None and type(value) is not float:
            raise ValueError("latency_target_seconds must be a float or None")
        return value

    @field_validator("latency_target_seconds")
    @classmethod
    def _validate_latency(cls, value: float | None) -> float | None:
        if value is not None and (value <= 0 or not math.isfinite(value)):
            raise ValueError("latency_target_seconds must be positive and finite when present")
        return value


class BenchmarkSurfaceBudget(ContractModel):
    pack_id: str
    benchmark_count: int = Field(gt=0)
    ladder_tier: LadderTier
    reductions: tuple[str, ...]
    subsets: tuple[str, ...]

    @field_validator("pack_id")
    @classmethod
    def _validate_pack_id(cls, value: str) -> str:
        return _canonical_id(value, "pack_id")

    @field_validator("reductions", "subsets")
    @classmethod
    def _validate_ordered_values(cls, value: tuple[str, ...], info: Any) -> tuple[str, ...]:
        return _utf8_sorted_unique(value, info.field_name)


class FidelityStage(ContractModel):
    name: str
    description: str

    @field_validator("name", "description")
    @classmethod
    def _validate_text(cls, value: str, info: Any) -> str:
        return _human_text(value, info.field_name)


class FidelityBudget(ContractModel):
    regime: str
    stages: tuple[FidelityStage, ...]
    promotion_rule: str

    @field_validator("regime", "promotion_rule")
    @classmethod
    def _validate_text(cls, value: str, info: Any) -> str:
        return _human_text(value, info.field_name)

    @model_validator(mode="after")
    def _validate_stages(self) -> FidelityBudget:
        if not self.stages:
            raise ValueError("fidelity stages must be nonempty")
        names = tuple(stage.name for stage in self.stages)
        if len(names) != len(set(names)):
            raise ValueError("fidelity stage names must be unique")
        return self


class BudgetDeclaration(ContractModel):
    evaluation: EvaluationBudget
    wall_clock: WallClockBudget
    training: TrainingBudget
    hardware: HardwareEnvelope
    model_artifact: ModelArtifactBudget
    benchmark_surface: BenchmarkSurfaceBudget
    fidelity: FidelityBudget


class BudgetAccounting(ContractModel):
    evaluation_count: int = Field(ge=0)
    actual_evaluations: int = Field(ge=0)
    cached_evaluations: int = Field(ge=0)
    failed_evaluations: int = Field(ge=0)
    invalid_evaluations: int = Field(ge=0)
    resumed_from_run_id: str | None
    resumed_evaluations: int = Field(ge=0)
    partial_run: bool
    evaluation_semantics: str

    @field_validator("resumed_from_run_id")
    @classmethod
    def _validate_resume_id(cls, value: str | None) -> str | None:
        return None if value is None else _run_id(value, "resumed_from_run_id")

    @field_validator("evaluation_semantics")
    @classmethod
    def _validate_semantics(cls, value: str) -> str:
        return _human_text(value, "evaluation_semantics")

    @model_validator(mode="after")
    def _validate_accounting(self) -> BudgetAccounting:
        if self.failed_evaluations > self.actual_evaluations:
            raise ValueError("failed_evaluations must not exceed actual_evaluations")
        if self.actual_evaluations > self.evaluation_count:
            raise ValueError("actual_evaluations must not exceed evaluation_count")
        if self.resumed_evaluations > self.cached_evaluations:
            raise ValueError("resumed_evaluations must not exceed cached_evaluations")
        if self.actual_evaluations + self.cached_evaluations > self.evaluation_count:
            raise ValueError("actual and cached evaluations must not exceed evaluation_count")
        if (self.resumed_from_run_id is not None) != (self.resumed_evaluations > 0):
            raise ValueError("resume ID presence must match positive resumed evaluations")
        expected_partial = self.actual_evaluations + self.cached_evaluations < self.evaluation_count
        if self.partial_run != expected_partial:
            raise ValueError("partial_run must exactly reflect evaluation coverage")
        return self


__all__ = [
    "BenchmarkSurfaceBudget",
    "BudgetAccounting",
    "BudgetDeclaration",
    "ContractModel",
    "EvaluationBudget",
    "EvaluationStage",
    "FidelityBudget",
    "FidelityStage",
    "HardwareEnvelope",
    "LadderTier",
    "ModelArtifactBudget",
    "TrainingBudget",
    "WallClockBudget",
]
