from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from evonn_shared.budgets import (
    BenchmarkSurfaceBudget,
    BudgetAccounting,
    BudgetDeclaration,
    ContractModel,
    EvaluationBudget,
    EvaluationStage,
    FidelityBudget,
    FidelityStage,
    HardwareEnvelope,
    LadderTier,
    ModelArtifactBudget,
    TrainingBudget,
    WallClockBudget,
)


PUBLIC_FIELDS = {
    EvaluationStage: {"name", "evaluations"},
    EvaluationBudget: {"total", "stages"},
    WallClockBudget: {"target_seconds"},
    TrainingBudget: {"unit", "per_candidate", "total_cap"},
    HardwareEnvelope: {
        "device_class",
        "cpu_count",
        "accelerator_type",
        "memory_ceiling_bytes",
        "worker_count",
    },
    ModelArtifactBudget: {
        "parameter_cap",
        "model_bytes_cap",
        "memory_target_bytes",
        "latency_target_seconds",
    },
    BenchmarkSurfaceBudget: {"pack_id", "benchmark_count", "ladder_tier", "reductions", "subsets"},
    FidelityStage: {"name", "description"},
    FidelityBudget: {"regime", "stages", "promotion_rule"},
    BudgetDeclaration: {
        "evaluation",
        "wall_clock",
        "training",
        "hardware",
        "model_artifact",
        "benchmark_surface",
        "fidelity",
    },
    BudgetAccounting: {
        "evaluation_count",
        "actual_evaluations",
        "cached_evaluations",
        "failed_evaluations",
        "invalid_evaluations",
        "resumed_from_run_id",
        "resumed_evaluations",
        "partial_run",
        "evaluation_semantics",
    },
}


def declaration_data() -> dict[str, object]:
    return {
        "evaluation": {
            "total": 10,
            "stages": (
                {"name": "screen", "evaluations": 4},
                {"name": "full", "evaluations": 6},
            ),
        },
        "wall_clock": {"target_seconds": 120.5},
        "training": {"unit": "epochs", "per_candidate": 2.0, "total_cap": 20.0},
        "hardware": {
            "device_class": "apple-m3",
            "cpu_count": 8,
            "accelerator_type": "mlx",
            "memory_ceiling_bytes": 16_000_000_000,
            "worker_count": 2,
        },
        "model_artifact": {
            "parameter_cap": 1_000_000,
            "model_bytes_cap": 4_000_000,
            "memory_target_bytes": 8_000_000,
            "latency_target_seconds": 0.25,
        },
        "benchmark_surface": {
            "pack_id": "core_pack",
            "benchmark_count": 2,
            "ladder_tier": LadderTier.B,
            "reductions": ("feature_reduction", "sample_reduction"),
            "subsets": ("first_fold", "second_fold"),
        },
        "fidelity": {
            "regime": "successive halving",
            "stages": (
                {"name": "low", "description": "low fidelity"},
                {"name": "high", "description": "full fidelity"},
            ),
            "promotion_rule": "top half advances",
        },
    }


def accounting_data(**changes: object) -> dict[str, object]:
    data: dict[str, object] = {
        "evaluation_count": 10,
        "actual_evaluations": 10,
        "cached_evaluations": 0,
        "failed_evaluations": 1,
        "invalid_evaluations": 2,
        "resumed_from_run_id": None,
        "resumed_evaluations": 0,
        "partial_run": False,
        "evaluation_semantics": "one charged candidate attempt",
    }
    data.update(changes)
    return data


def test_contract_model_policy_and_exact_public_fields() -> None:
    assert ContractModel.model_config == {"extra": "forbid", "frozen": True, "strict": True}
    for model, fields in PUBLIC_FIELDS.items():
        assert set(model.model_fields) == fields
    assert [(member.name, member.value) for member in LadderTier] == [
        ("A", "A"),
        ("B", "B"),
        ("C", "C"),
        ("D", "D"),
        ("E", "E"),
    ]


def test_valid_budget_preserves_semantic_stage_order_and_is_frozen() -> None:
    declaration = BudgetDeclaration.model_validate(declaration_data())

    assert tuple(stage.name for stage in declaration.evaluation.stages) == ("screen", "full")
    assert tuple(stage.name for stage in declaration.fidelity.stages) == ("low", "high")
    with pytest.raises(ValidationError):
        declaration.evaluation.total = 11
    with pytest.raises(ValidationError):
        declaration.fidelity.stages = ()


def test_strict_python_rejects_coercions_bools_and_hostile_subclasses() -> None:
    class HostileInt(int):
        def __index__(self) -> int:
            raise AssertionError("must not dispatch")

    class HostileFloat(float):
        def __float__(self) -> float:
            raise AssertionError("must not dispatch")

    class HostileStr(str):
        def strip(self, *args: object, **kwargs: object) -> str:
            raise AssertionError("must not dispatch")

    invalid = [
        {"total": "10", "stages": ()},
        {"total": True, "stages": ()},
        {"total": HostileInt(10), "stages": ()},
    ]
    for data in invalid:
        with pytest.raises(ValidationError):
            EvaluationBudget.model_validate(data)
    with pytest.raises(ValidationError):
        WallClockBudget.model_validate({"target_seconds": HostileFloat(1.0)})
    with pytest.raises(ValidationError):
        EvaluationStage.model_validate({"name": HostileStr("stage"), "evaluations": 1})


def test_json_arrays_are_accepted_for_tuple_fields_but_python_lists_are_not() -> None:
    parsed = EvaluationBudget.model_validate_json(
        b'{"total":3,"stages":[{"name":"only","evaluations":3}]}'
    )
    assert parsed.stages == (EvaluationStage(name="only", evaluations=3),)

    with pytest.raises(ValidationError):
        EvaluationBudget.model_validate({"total": 3, "stages": [{"name": "only", "evaluations": 3}]})


@pytest.mark.parametrize(
    "data",
    [
        {"total": 0, "stages": ()},
        {"total": 3, "stages": ({"name": "", "evaluations": 3},)},
        {"total": 3, "stages": ({"name": "same", "evaluations": 1}, {"name": "same", "evaluations": 2})},
        {"total": 3, "stages": ({"name": "only", "evaluations": 2},)},
        {"total": 3, "stages": ({"name": "only", "evaluations": -1},)},
    ],
)
def test_evaluation_budget_rejects_invalid_totals_names_and_stage_sums(data: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        EvaluationBudget.model_validate(data)


def test_zero_stage_evaluation_budget_is_valid() -> None:
    assert EvaluationBudget(total=3, stages=()).stages == ()


@pytest.mark.parametrize("value", [0.0, -1.0, float("nan"), float("inf"), float("-inf")])
def test_wall_clock_requires_positive_finite_seconds(value: float) -> None:
    with pytest.raises(ValidationError):
        WallClockBudget(target_seconds=value)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("unit", " "),
        ("per_candidate", -0.1),
        ("per_candidate", float("nan")),
        ("total_cap", -0.1),
        ("total_cap", float("inf")),
    ],
)
def test_training_budget_validates_text_and_nonnegative_finite_values(field: str, value: object) -> None:
    data: dict[str, object] = {"unit": "epochs", "per_candidate": 0.0, "total_cap": 0.0}
    data[field] = value
    with pytest.raises(ValidationError):
        TrainingBudget.model_validate(data)


@pytest.mark.parametrize(
    ("field", "value"),
    [("cpu_count", 0), ("worker_count", 0), ("memory_ceiling_bytes", 0)],
)
def test_hardware_envelope_requires_positive_counts_and_optional_memory(field: str, value: int) -> None:
    data = deepcopy(declaration_data()["hardware"])
    assert isinstance(data, dict)
    data[field] = value
    with pytest.raises(ValidationError):
        HardwareEnvelope.model_validate(data)


def test_cpu_only_hardware_is_explicitly_valid() -> None:
    data = deepcopy(declaration_data()["hardware"])
    assert isinstance(data, dict)
    data["accelerator_type"] = None
    data["memory_ceiling_bytes"] = None
    assert HardwareEnvelope.model_validate(data).accelerator_type is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("parameter_cap", 0),
        ("model_bytes_cap", -1),
        ("memory_target_bytes", 0),
        ("latency_target_seconds", 0.0),
        ("latency_target_seconds", float("nan")),
    ],
)
def test_model_artifact_optional_targets_are_positive_when_present(field: str, value: object) -> None:
    data = deepcopy(declaration_data()["model_artifact"])
    assert isinstance(data, dict)
    data[field] = value
    with pytest.raises(ValidationError):
        ModelArtifactBudget.model_validate(data)


def test_model_artifact_allows_explicitly_unenforced_targets() -> None:
    model = ModelArtifactBudget(
        parameter_cap=None,
        model_bytes_cap=None,
        memory_target_bytes=None,
        latency_target_seconds=None,
    )
    assert all(value is None for value in model.__dict__.values())


@pytest.mark.parametrize(
    "changes",
    [
        {"pack_id": "Bad-Pack"},
        {"benchmark_count": 0},
        {"reductions": ("z", "a")},
        {"reductions": ("same", "same")},
        {"subsets": ("",)},
        {"subsets": ("é", "z")},
    ],
)
def test_benchmark_surface_validates_id_count_and_utf8_sorted_unique_sets(changes: dict[str, object]) -> None:
    data = deepcopy(declaration_data()["benchmark_surface"])
    assert isinstance(data, dict)
    data.update(changes)
    with pytest.raises(ValidationError):
        BenchmarkSurfaceBudget.model_validate(data)


def test_empty_reductions_and_subsets_explicitly_mean_none() -> None:
    data = deepcopy(declaration_data()["benchmark_surface"])
    assert isinstance(data, dict)
    data["reductions"] = ()
    data["subsets"] = ()
    surface = BenchmarkSurfaceBudget.model_validate(data)
    assert surface.reductions == surface.subsets == ()


@pytest.mark.parametrize(
    "changes",
    [
        {"regime": ""},
        {"stages": ()},
        {"stages": ({"name": "x", "description": "one"}, {"name": "x", "description": "two"})},
        {"stages": ({"name": "x", "description": "\x00"},)},
        {"promotion_rule": "  "},
    ],
)
def test_fidelity_validates_nonempty_unique_ordered_stages(changes: dict[str, object]) -> None:
    data = deepcopy(declaration_data()["fidelity"])
    assert isinstance(data, dict)
    data.update(changes)
    with pytest.raises(ValidationError):
        FidelityBudget.model_validate(data)


@pytest.mark.parametrize(
    "changes",
    [
        {"evaluation_count": -1},
        {"actual_evaluations": -1},
        {"cached_evaluations": -1},
        {"failed_evaluations": -1},
        {"invalid_evaluations": -1},
        {"resumed_evaluations": -1},
        {"failed_evaluations": 11},
        {"actual_evaluations": 11, "failed_evaluations": 0, "partial_run": False},
        {"actual_evaluations": 8, "cached_evaluations": 3, "failed_evaluations": 0, "partial_run": False},
        {"cached_evaluations": 2, "resumed_evaluations": 3, "resumed_from_run_id": "prior"},
        {"resumed_from_run_id": "prior", "resumed_evaluations": 0},
        {"resumed_from_run_id": None, "resumed_evaluations": 1, "cached_evaluations": 1},
        {"actual_evaluations": 9, "partial_run": False},
        {"actual_evaluations": 10, "partial_run": True},
        {"evaluation_semantics": ""},
    ],
)
def test_accounting_rejects_each_invariant_violation(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        BudgetAccounting.model_validate(accounting_data(**changes))


@pytest.mark.parametrize(
    "data",
    [
        accounting_data(),
        accounting_data(actual_evaluations=7, failed_evaluations=0, partial_run=True),
        accounting_data(actual_evaluations=7, cached_evaluations=3, failed_evaluations=0),
        accounting_data(
            actual_evaluations=5,
            cached_evaluations=3,
            failed_evaluations=0,
            resumed_from_run_id="prior.run",
            resumed_evaluations=3,
            partial_run=True,
        ),
    ],
)
def test_accounting_accepts_full_partial_cached_and_resumed_cases(data: dict[str, object]) -> None:
    assert BudgetAccounting.model_validate(data).evaluation_count == 10


def test_unknown_and_missing_fields_are_rejected() -> None:
    data = accounting_data(unknown=1)
    with pytest.raises(ValidationError):
        BudgetAccounting.model_validate(data)
    data = accounting_data()
    del data["evaluation_count"]
    with pytest.raises(ValidationError):
        BudgetAccounting.model_validate(data)


def test_every_budget_model_rejects_each_missing_field_and_unknown_fields() -> None:
    declaration = declaration_data()
    cases: dict[type[ContractModel], dict[str, object]] = {
        EvaluationStage: {"name": "stage", "evaluations": 1},
        EvaluationBudget: {"total": 1, "stages": ({"name": "stage", "evaluations": 1},)},
        WallClockBudget: {"target_seconds": 1.0},
        TrainingBudget: {"unit": "epochs", "per_candidate": 1.0, "total_cap": 1.0},
        HardwareEnvelope: deepcopy(declaration["hardware"]),
        ModelArtifactBudget: deepcopy(declaration["model_artifact"]),
        BenchmarkSurfaceBudget: deepcopy(declaration["benchmark_surface"]),
        FidelityStage: {"name": "full", "description": "full fidelity"},
        FidelityBudget: deepcopy(declaration["fidelity"]),
        BudgetDeclaration: declaration,
        BudgetAccounting: accounting_data(),
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
