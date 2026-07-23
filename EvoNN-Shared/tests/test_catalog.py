from __future__ import annotations

from collections.abc import Callable, Sequence
import inspect
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import get_type_hints

import pytest
from pydantic import ValidationError
import yaml

import evonn_shared.catalog as catalog
from evonn_shared.budgets import ContractModel, LadderTier
from evonn_shared.canonical import canonical_sha256
from evonn_shared.catalog import (
    CATALOG_SCHEMA_VERSION,
    BenchmarkNotFoundError,
    BenchmarkPack,
    BenchmarkSpec,
    BenchmarkStatus,
    CanonicalIdEntry,
    CanonicalIdRegistry,
    CatalogError,
    CatalogRegistryMismatchError,
    CeilingTiePolicy,
    DuplicateCatalogDefinitionError,
    InputModality,
    InvalidCatalogIdentifierError,
    InvalidCatalogModelError,
    InvalidCatalogYamlError,
    MetricCeiling,
    PackBudgetPolicy,
    PackNotFoundError,
    PrimaryMetric,
    UnknownPackBenchmarkError,
    UnsafeCatalogPathError,
    get_benchmark,
    list_benchmarks,
    load_parity_pack,
    resolve_pack_path,
)
from evonn_shared.telemetry import MetricDirection, SystemId, TaskKind


FIXTURES = Path(__file__).parent / "fixtures" / "catalog"
CANONICAL_FIXTURE = FIXTURES / "canonical"
FALLBACK_FIXTURE = FIXTURES / "fallback-a"
FALLBACK_PACK_FIXTURE = FIXTURES / "fallback-packs"
INVALID_FIXTURE = FIXTURES / "invalid"
PRODUCTION_ROOT = Path(__file__).parents[2] / "shared-benchmarks"
HOSTILE_CONSTRUCTOR_SCALARS = (
    "9" * 5_000,
    "2026-99-99",
)
MALFORMED_ROOTS = (
    Path("bad\0root"),
    Path("bad\ud800root"),
)
EXPECTED_PUBLIC = {
    "CATALOG_SCHEMA_VERSION",
    "BenchmarkStatus",
    "InputModality",
    "CeilingTiePolicy",
    "PrimaryMetric",
    "MetricCeiling",
    "BenchmarkSpec",
    "CanonicalIdEntry",
    "CanonicalIdRegistry",
    "PackBudgetPolicy",
    "BenchmarkPack",
    "LadderTier",
    "TaskKind",
    "MetricDirection",
    "SystemId",
    "CatalogError",
    "InvalidCatalogIdentifierError",
    "UnsafeCatalogPathError",
    "DuplicateCatalogDefinitionError",
    "InvalidCatalogYamlError",
    "InvalidCatalogModelError",
    "CatalogRegistryMismatchError",
    "BenchmarkNotFoundError",
    "PackNotFoundError",
    "UnknownPackBenchmarkError",
    "get_benchmark",
    "list_benchmarks",
    "resolve_pack_path",
    "load_parity_pack",
}
PUBLIC_FIELDS = {
    PrimaryMetric: {"name", "direction"},
    MetricCeiling: {"value", "tie_policy"},
    BenchmarkSpec: {
        "schema_version",
        "id",
        "display_name",
        "status",
        "task_kind",
        "input_modality",
        "input_shape",
        "output_dim",
        "primary_metric",
        "ceiling",
        "budget_epochs",
        "runtime_class",
        "required_contenders",
        "tags",
    },
    CanonicalIdEntry: {"id", "definition_sha256"},
    CanonicalIdRegistry: {"schema_version", "entries"},
    PackBudgetPolicy: {"evaluation_count"},
    BenchmarkPack: {
        "schema_version",
        "pack_name",
        "ladder_tier",
        "benchmarks",
        "budget_policy",
        "symmetry",
        "modalities",
        "expected_local_runtime_class",
        "minimum_contenders",
        "suitability",
        "full_fidelity_local_safe",
    },
}


def benchmark_data(benchmark_id: str = "contract_model_classification", **changes: object) -> dict[str, object]:
    data: dict[str, object] = {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "id": benchmark_id,
        "display_name": "Contract Model Classification",
        "status": BenchmarkStatus.IMPLEMENTED,
        "task_kind": TaskKind.CLASSIFICATION,
        "input_modality": InputModality.TABULAR,
        "input_shape": (4,),
        "output_dim": 3,
        "primary_metric": {"name": "accuracy", "direction": MetricDirection.MAX},
        "ceiling": {"value": 1.0, "tie_policy": CeilingTiePolicy.NOT_EVIDENCE},
        "budget_epochs": 20,
        "runtime_class": "fast",
        "required_contenders": ("linear_contender", "tree_contender"),
        "tags": ("offline",),
    }
    data.update(changes)
    return data


def pack_data(pack_name: str = "contract_model_pack", **changes: object) -> dict[str, object]:
    data: dict[str, object] = {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "pack_name": pack_name,
        "ladder_tier": LadderTier.A,
        "benchmarks": ("contract_alpha", "contract_beta"),
        "budget_policy": {"evaluation_count": 4},
        "symmetry": "symmetric",
        "modalities": (InputModality.TABULAR,),
        "expected_local_runtime_class": "medium",
        "minimum_contenders": ("linear_contender", "tree_contender"),
        "suitability": "daily",
        "full_fidelity_local_safe": True,
    }
    data.update(changes)
    return data


def empty_root(path: Path) -> Path:
    (path / "catalog").mkdir(parents=True)
    (path / "suites" / "parity").mkdir(parents=True)
    (path / "catalog" / "canonical_ids.yaml").write_text(
        "schema_version: 1.0.0\nentries: []\n", encoding="utf-8"
    )
    return path


def copy_canonical_root(path: Path) -> Path:
    shutil.copytree(CANONICAL_FIXTURE, path)
    return path


def yaml_for_benchmark(benchmark_id: str, *, display_name: str | None = None) -> str:
    return f"""schema_version: 1.0.0
id: {benchmark_id}
display_name: {display_name or benchmark_id.replace("_", " ").title()}
status: implemented
task_kind: classification
input_modality: tabular
input_shape: [2]
output_dim: 2
primary_metric:
  name: accuracy
  direction: max
ceiling:
  value: 1.0
  tie_policy: not_evidence
budget_epochs: 2
runtime_class: fast
required_contenders: [linear_contender]
tags: []
"""


def yaml_for_pack(pack_name: str, benchmark_id: str) -> str:
    return f"""schema_version: 1.0.0
pack_name: {pack_name}
ladder_tier: A
benchmarks: [{benchmark_id}]
budget_policy:
  evaluation_count: 2
symmetry: symmetric
modalities: [tabular]
expected_local_runtime_class: fast
minimum_contenders: [linear_contender]
suitability: smoke
full_fidelity_local_safe: true
"""


def add_canonical_definition(root: Path, benchmark_id: str, *, text: str | None = None) -> None:
    definition = text or yaml_for_benchmark(benchmark_id)
    path = root / "catalog" / f"{benchmark_id}.yaml"
    path.write_text(definition, encoding="utf-8")
    parsed = yaml.safe_load(definition)
    digest = canonical_sha256(
        parsed,
        schema_version="evonn.catalog.benchmark/v1",
        digest_field=None,
    )
    registry = root / "catalog" / "canonical_ids.yaml"
    registry.write_text(
        "schema_version: 1.0.0\nentries:\n"
        f"  - id: {benchmark_id}\n    definition_sha256: {digest}\n",
        encoding="utf-8",
    )


def write_fallback(directory: Path, benchmark_id: str, *, text: str | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{benchmark_id}.yaml"
    path.write_text(text or yaml_for_benchmark(benchmark_id), encoding="utf-8")
    return path


def assert_catalog_error(
    expected_type: type[CatalogError],
    code: str,
    action: Callable[[], object],
) -> CatalogError:
    with pytest.raises(expected_type) as caught:
        action()
    assert caught.value.code == code
    return caught.value


def invoke_fallback_yaml(tmp_path: Path, benchmark_id: str, payload: bytes) -> None:
    root = empty_root(tmp_path / "root")
    fallback = tmp_path / "fallback"
    fallback.mkdir()
    (fallback / f"{benchmark_id}.yaml").write_bytes(payload)
    get_benchmark(benchmark_id, shared_root=root, fallback_catalog_dirs=(fallback,))


def hostile_yaml(complexity: str) -> bytes:
    if complexity == "depth":
        payload = f"value: {'[' * 400}0{']' * 400}\n".encode()
    else:
        payload = f"values: [{','.join(['x'] * 10_001)}]\n".encode()
    assert len(payload) < 1024 * 1024
    return payload


def assert_invalid_yaml_composer(action: Callable[[], object]) -> None:
    error = assert_catalog_error(
        InvalidCatalogYamlError,
        "invalid_catalog_yaml",
        action,
    )
    assert type(error) is InvalidCatalogYamlError
    assert type(error.__cause__) is yaml.composer.ComposerError


def test_constant_public_surface_exact_models_and_enums() -> None:
    assert CATALOG_SCHEMA_VERSION == "1.0.0"
    assert set(catalog.__all__) == EXPECTED_PUBLIC
    assert ContractModel.model_config == {"extra": "forbid", "frozen": True, "strict": True}
    for model, fields in PUBLIC_FIELDS.items():
        assert set(model.model_fields) == fields
    assert [(item.name, item.value) for item in BenchmarkStatus] == [
        ("PLANNED", "planned"),
        ("IMPLEMENTED", "implemented"),
        ("EXPERIMENTAL", "experimental"),
        ("DISABLED", "disabled"),
    ]
    assert [(item.name, item.value) for item in InputModality] == [
        ("TABULAR", "tabular"),
        ("IMAGE", "image"),
        ("TEXT", "text"),
        ("SEQUENCE", "sequence"),
    ]
    assert [(item.name, item.value) for item in CeilingTiePolicy] == [
        ("NOT_EVIDENCE", "not_evidence"),
        ("BEST_OBSERVED", "best_observed"),
    ]


def test_exact_loader_signatures_and_annotations() -> None:
    expected = {
        get_benchmark: [
            ("benchmark_id", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.empty),
            ("shared_root", inspect.Parameter.KEYWORD_ONLY, None),
            ("fallback_catalog_dirs", inspect.Parameter.KEYWORD_ONLY, ()),
        ],
        list_benchmarks: [
            ("shared_root", inspect.Parameter.KEYWORD_ONLY, None),
            ("fallback_catalog_dirs", inspect.Parameter.KEYWORD_ONLY, ()),
        ],
        resolve_pack_path: [
            ("pack_name", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.empty),
            ("shared_root", inspect.Parameter.KEYWORD_ONLY, None),
            ("fallback_pack_dirs", inspect.Parameter.KEYWORD_ONLY, ()),
        ],
        load_parity_pack: [
            ("pack_name", inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.empty),
            ("shared_root", inspect.Parameter.KEYWORD_ONLY, None),
            ("fallback_pack_dirs", inspect.Parameter.KEYWORD_ONLY, ()),
            ("fallback_catalog_dirs", inspect.Parameter.KEYWORD_ONLY, ()),
        ],
    }
    for function, parameters in expected.items():
        signature = inspect.signature(function)
        assert [(item.name, item.kind, item.default) for item in signature.parameters.values()] == parameters
    assert get_type_hints(get_benchmark) == {
        "benchmark_id": str,
        "shared_root": Path | None,
        "fallback_catalog_dirs": Sequence[Path],
        "return": BenchmarkSpec,
    }
    assert get_type_hints(list_benchmarks) == {
        "shared_root": Path | None,
        "fallback_catalog_dirs": Sequence[Path],
        "return": tuple[BenchmarkSpec, ...],
    }
    assert get_type_hints(resolve_pack_path) == {
        "pack_name": str,
        "shared_root": Path | None,
        "fallback_pack_dirs": Sequence[Path],
        "return": Path,
    }
    assert get_type_hints(load_parity_pack) == {
        "pack_name": str,
        "shared_root": Path | None,
        "fallback_pack_dirs": Sequence[Path],
        "fallback_catalog_dirs": Sequence[Path],
        "return": BenchmarkPack,
    }


def test_models_construct_valid_values_are_frozen_and_yaml_loads() -> None:
    spec = BenchmarkSpec.model_validate(benchmark_data())
    pack = BenchmarkPack.model_validate(pack_data())
    assert spec.required_contenders == ("linear_contender", "tree_contender")
    assert pack.benchmarks == ("contract_alpha", "contract_beta")
    with pytest.raises(ValidationError):
        spec.id = "changed"
    loaded = list_benchmarks(shared_root=CANONICAL_FIXTURE)
    assert [item.id for item in loaded] == ["contract_alpha_classification", "contract_beta_regression"]
    assert loaded[0].status is BenchmarkStatus.IMPLEMENTED
    assert loaded[1].ceiling.tie_policy is CeilingTiePolicy.BEST_OBSERVED


def test_python_lists_unknown_missing_schema_and_wrong_scalar_types_reject() -> None:
    with pytest.raises(ValidationError):
        BenchmarkSpec.model_validate(benchmark_data(input_shape=[4]))
    cases = [
        benchmark_data(schema_version="2.0.0"),
        benchmark_data(output_dim="3"),
        benchmark_data(output_dim=True),
        benchmark_data(unknown="forbidden"),
    ]
    missing = benchmark_data()
    del missing["schema_version"]
    cases.append(missing)
    for data in cases:
        with pytest.raises(ValidationError):
            BenchmarkSpec.model_validate(data)


def test_hostile_scalar_subclasses_reject_without_dispatch() -> None:
    class HostileStr(str):
        def encode(self, *args: object, **kwargs: object) -> bytes:
            raise AssertionError("must not dispatch")

    class HostileInt(int):
        def __index__(self) -> int:
            raise AssertionError("must not dispatch")

    class HostileFloat(float):
        def __float__(self) -> float:
            raise AssertionError("must not dispatch")

    for changes in (
        {"id": HostileStr("contract_model_classification")},
        {"output_dim": HostileInt(3)},
        {"ceiling": {"value": HostileFloat(1.0), "tie_policy": CeilingTiePolicy.NOT_EVIDENCE}},
    ):
        with pytest.raises(ValidationError):
            BenchmarkSpec.model_validate(benchmark_data(**changes))


@pytest.mark.parametrize(
    "value",
    ["", "_alpha", "alpha_", "alpha__beta", "Alpha", "alpha-beta", "alpha.beta", "../alpha", "a/b", "/alpha", "éclair"],
)
def test_every_canonical_identifier_grammar_rejection(value: str) -> None:
    for field in ("id", "runtime_class"):
        with pytest.raises(ValidationError):
            BenchmarkSpec.model_validate(benchmark_data(**{field: value}))
    with pytest.raises(ValidationError):
        PrimaryMetric(name=value, direction=MetricDirection.MAX)
    with pytest.raises(ValidationError):
        BenchmarkPack.model_validate(pack_data(pack_name=value))


def test_display_text_input_shape_counts_contenders_and_tags_validate() -> None:
    invalid_changes = [
        {"display_name": " "},
        {"display_name": "bad\x00text"},
        {"display_name": "bad\ud800text"},
        {"input_shape": ()},
        {"input_shape": (0,)},
        {"input_shape": (-1,)},
        {"input_shape": (True,)},
        {"output_dim": 0},
        {"budget_epochs": 0},
        {"required_contenders": ()},
        {"required_contenders": ("tree_contender", "linear_contender")},
        {"required_contenders": ("linear_contender", "linear_contender")},
        {"required_contenders": ("bad-id",)},
        {"tags": ("z_tag", "a_tag")},
        {"tags": ("offline", "offline")},
        {"tags": ("bad tag",)},
    ]
    for changes in invalid_changes:
        with pytest.raises(ValidationError):
            BenchmarkSpec.model_validate(benchmark_data(**changes))
    assert BenchmarkSpec.model_validate(benchmark_data(tags=())).tags == ()


def test_metric_direction_is_required_and_ceiling_state_matrix_is_exact() -> None:
    with pytest.raises(ValidationError):
        PrimaryMetric.model_validate({"name": "accuracy"})
    valid = [(1.0, CeilingTiePolicy.NOT_EVIDENCE), (None, CeilingTiePolicy.BEST_OBSERVED)]
    for value, policy in valid:
        assert MetricCeiling(value=value, tie_policy=policy).value == value
    invalid = [
        (None, CeilingTiePolicy.NOT_EVIDENCE),
        (1.0, CeilingTiePolicy.BEST_OBSERVED),
        (1, CeilingTiePolicy.NOT_EVIDENCE),
        (float("nan"), CeilingTiePolicy.NOT_EVIDENCE),
        (float("inf"), CeilingTiePolicy.NOT_EVIDENCE),
    ]
    for value, policy in invalid:
        with pytest.raises(ValidationError):
            MetricCeiling(value=value, tie_policy=policy)


def test_registry_order_uniqueness_digest_grammar_and_empty_registry() -> None:
    assert CanonicalIdRegistry(schema_version="1.0.0", entries=()).entries == ()
    for entries in (
        (
            {"id": "contract_beta", "definition_sha256": "b" * 64},
            {"id": "contract_alpha", "definition_sha256": "a" * 64},
        ),
        (
            {"id": "contract_alpha", "definition_sha256": "a" * 64},
            {"id": "contract_alpha", "definition_sha256": "b" * 64},
        ),
        ({"id": "contract_alpha", "definition_sha256": "A" * 64},),
        ({"id": "contract_alpha", "definition_sha256": "a" * 63},),
        ({"id": "contract_alpha", "definition_sha256": "g" * 64},),
    ):
        with pytest.raises(ValidationError):
            CanonicalIdRegistry(schema_version="1.0.0", entries=entries)


def test_definition_digest_ignores_yaml_format_comments_and_key_order(tmp_path: Path) -> None:
    root = empty_root(tmp_path / "root")
    benchmark_id = "contract_format_identity"
    first = yaml_for_benchmark(benchmark_id)
    add_canonical_definition(root, benchmark_id, text=first)
    expected = get_benchmark(benchmark_id, shared_root=root)
    alternate = """# same structured definition, deliberately reordered
id: contract_format_identity
schema_version: 1.0.0
display_name: Contract Format Identity
status: implemented
task_kind: classification
input_modality: tabular
input_shape:
  - 2
output_dim: 2
primary_metric: {direction: max, name: accuracy}
ceiling: {tie_policy: not_evidence, value: 1.0}
budget_epochs: 2
runtime_class: fast
required_contenders:
  - linear_contender
tags: []
"""
    (root / "catalog" / f"{benchmark_id}.yaml").write_text(alternate, encoding="utf-8")
    assert get_benchmark(benchmark_id, shared_root=root) == expected


@pytest.mark.parametrize("mutation", ["digest", "missing", "unregistered", "stem"])
def test_registry_digest_missing_unregistered_and_stem_mismatches_fail_closed(tmp_path: Path, mutation: str) -> None:
    root = copy_canonical_root(tmp_path / "root")
    alpha = root / "catalog" / "contract_alpha_classification.yaml"
    if mutation == "digest":
        alpha.write_text(alpha.read_text(encoding="utf-8").replace("Contract Alpha", "Changed Alpha"), encoding="utf-8")
    elif mutation == "missing":
        alpha.unlink()
    elif mutation == "unregistered":
        write_fallback(root / "catalog", "contract_unregistered")
    else:
        alpha.rename(root / "catalog" / "contract_wrong_stem.yaml")
    assert_catalog_error(
        CatalogRegistryMismatchError,
        "catalog_registry_mismatch",
        lambda: list_benchmarks(shared_root=root),
    )


def test_registry_is_required_and_unexpected_canonical_entries_fail_closed(tmp_path: Path) -> None:
    root = copy_canonical_root(tmp_path / "root")
    (root / "catalog" / "canonical_ids.yaml").unlink()
    assert_catalog_error(UnsafeCatalogPathError, "unsafe_catalog_path", lambda: list_benchmarks(shared_root=root))
    root = copy_canonical_root(tmp_path / "other")
    (root / "catalog" / "README.txt").write_text("unexpected\n", encoding="utf-8")
    assert_catalog_error(UnsafeCatalogPathError, "unsafe_catalog_path", lambda: list_benchmarks(shared_root=root))


def test_root_precedence_explicit_then_environment_then_repository_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    explicit = empty_root(tmp_path / "explicit")
    environment = empty_root(tmp_path / "environment")
    add_canonical_definition(explicit, "contract_explicit")
    add_canonical_definition(environment, "contract_environment")
    monkeypatch.setenv("EVONN_SHARED_BENCHMARKS_DIR", str(environment))
    assert [item.id for item in list_benchmarks(shared_root=explicit)] == ["contract_explicit"]
    assert [item.id for item in list_benchmarks()] == ["contract_environment"]
    monkeypatch.delenv("EVONN_SHARED_BENCHMARKS_DIR")
    assert list_benchmarks() == ()


def test_empty_environment_override_and_non_path_arguments_reject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVONN_SHARED_BENCHMARKS_DIR", "")
    assert_catalog_error(UnsafeCatalogPathError, "unsafe_catalog_path", list_benchmarks)
    monkeypatch.delenv("EVONN_SHARED_BENCHMARKS_DIR")
    root = empty_root(tmp_path / "root")
    for action in (
        lambda: list_benchmarks(shared_root=str(root)),  # type: ignore[arg-type]
        lambda: list_benchmarks(shared_root=root, fallback_catalog_dirs=(str(root),)),  # type: ignore[arg-type]
        lambda: resolve_pack_path("contract_pack", shared_root=root, fallback_pack_dirs=(str(root),)),  # type: ignore[arg-type]
    ):
        assert_catalog_error(UnsafeCatalogPathError, "unsafe_catalog_path", action)


@pytest.mark.parametrize(
    "malformed_root",
    MALFORMED_ROOTS,
    ids=("embedded_nul", "malformed_unicode"),
)
@pytest.mark.parametrize(
    "action_name",
    ("get_benchmark", "list_benchmarks", "resolve_pack_path", "load_parity_pack"),
)
def test_malformed_shared_root_uses_stable_path_error(
    malformed_root: Path,
    action_name: str,
) -> None:
    actions = {
        "get_benchmark": lambda: get_benchmark(
            "contract_missing",
            shared_root=malformed_root,
        ),
        "list_benchmarks": lambda: list_benchmarks(shared_root=malformed_root),
        "resolve_pack_path": lambda: resolve_pack_path(
            "contract_missing_pack",
            shared_root=malformed_root,
        ),
        "load_parity_pack": lambda: load_parity_pack(
            "contract_missing_pack",
            shared_root=malformed_root,
        ),
    }
    error = assert_catalog_error(
        UnsafeCatalogPathError,
        "unsafe_catalog_path",
        actions[action_name],
    )
    assert type(error) is UnsafeCatalogPathError
    expected_cause = ValueError if malformed_root == MALFORMED_ROOTS[0] else UnicodeEncodeError
    assert type(error.__cause__) is expected_cause


@pytest.mark.parametrize(
    "malformed_root",
    MALFORMED_ROOTS,
    ids=("embedded_nul", "malformed_unicode"),
)
@pytest.mark.parametrize(
    "action_name",
    ("get_benchmark", "list_benchmarks", "resolve_pack_path", "load_parity_pack"),
)
def test_malformed_fallback_directory_uses_stable_path_error(
    tmp_path: Path,
    malformed_root: Path,
    action_name: str,
) -> None:
    root = empty_root(tmp_path / "root")
    actions = {
        "get_benchmark": lambda: get_benchmark(
            "contract_missing",
            shared_root=root,
            fallback_catalog_dirs=(malformed_root,),
        ),
        "list_benchmarks": lambda: list_benchmarks(
            shared_root=root,
            fallback_catalog_dirs=(malformed_root,),
        ),
        "resolve_pack_path": lambda: resolve_pack_path(
            "contract_missing_pack",
            shared_root=root,
            fallback_pack_dirs=(malformed_root,),
        ),
        "load_parity_pack": lambda: load_parity_pack(
            "contract_missing_pack",
            shared_root=root,
            fallback_pack_dirs=(malformed_root,),
        ),
    }
    error = assert_catalog_error(
        UnsafeCatalogPathError,
        "unsafe_catalog_path",
        actions[action_name],
    )
    assert type(error) is UnsafeCatalogPathError
    expected_cause = ValueError if malformed_root == MALFORMED_ROOTS[0] else UnicodeEncodeError
    assert type(error.__cause__) is expected_cause


def test_canonical_wins_fallback_only_resolves_and_merged_list_is_sorted(tmp_path: Path) -> None:
    root = copy_canonical_root(tmp_path / "root")
    fallback = tmp_path / "fallback"
    shutil.copytree(FALLBACK_FIXTURE, fallback)
    write_fallback(fallback, "contract_alpha_classification", text=yaml_for_benchmark("contract_alpha_classification", display_name="Fallback Alpha"))
    assert get_benchmark(
        "contract_alpha_classification", shared_root=root, fallback_catalog_dirs=(fallback,)
    ).display_name == "Contract Alpha Classification"
    assert get_benchmark(
        "contract_fallback_sequence", shared_root=root, fallback_catalog_dirs=(fallback,)
    ).id == "contract_fallback_sequence"
    assert [item.id for item in list_benchmarks(shared_root=root, fallback_catalog_dirs=(fallback,))] == [
        "contract_alpha_classification",
        "contract_beta_regression",
        "contract_fallback_sequence",
    ]


def test_duplicate_fallback_definitions_directories_and_identity_aliases_fail(tmp_path: Path) -> None:
    root = empty_root(tmp_path / "root")
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_fallback(first, "contract_duplicate")
    write_fallback(second, "contract_duplicate")
    for directories in (
        (first, second),
        (first, first),
        (first, first / ".." / first.name),
    ):
        assert_catalog_error(
            DuplicateCatalogDefinitionError,
            "duplicate_catalog_definition",
            lambda directories=directories: list_benchmarks(shared_root=root, fallback_catalog_dirs=directories),
        )


def test_two_fallback_files_declaring_same_model_id_use_duplicate_error(tmp_path: Path) -> None:
    root = empty_root(tmp_path / "root")
    fallback = tmp_path / "fallback"
    write_fallback(fallback, "contract_first", text=yaml_for_benchmark("contract_same_model"))
    write_fallback(fallback, "contract_second", text=yaml_for_benchmark("contract_same_model"))
    assert_catalog_error(
        DuplicateCatalogDefinitionError,
        "duplicate_catalog_definition",
        lambda: list_benchmarks(shared_root=root, fallback_catalog_dirs=(fallback,)),
    )


def test_get_benchmark_rejects_differently_named_files_declaring_requested_id(
    tmp_path: Path,
) -> None:
    root = empty_root(tmp_path / "root")
    fallback = tmp_path / "fallback"
    write_fallback(fallback, "contract_target")
    write_fallback(
        fallback,
        "contract_shadow",
        text=yaml_for_benchmark("contract_target", display_name="Contract Shadow"),
    )
    assert_catalog_error(
        DuplicateCatalogDefinitionError,
        "duplicate_catalog_definition",
        lambda: get_benchmark(
            "contract_target",
            shared_root=root,
            fallback_catalog_dirs=(fallback,),
        ),
    )


def test_merged_listing_is_deterministic_under_creation_and_argument_order(tmp_path: Path) -> None:
    root = empty_root(tmp_path / "root")
    first = tmp_path / "first"
    second = tmp_path / "second"
    for benchmark_id in ("contract_zeta", "contract_alpha"):
        write_fallback(first, benchmark_id)
    for benchmark_id in ("contract_gamma", "contract_beta"):
        write_fallback(second, benchmark_id)
    forward = list_benchmarks(shared_root=root, fallback_catalog_dirs=(first, second))
    reverse = list_benchmarks(shared_root=root, fallback_catalog_dirs=(second, first))
    assert tuple(item.id for item in forward) == tuple(item.id for item in reverse) == (
        "contract_alpha",
        "contract_beta",
        "contract_gamma",
        "contract_zeta",
    )


def test_catalog_listing_is_deterministic_across_hash_seeds() -> None:
    script = f"""
from pathlib import Path
from evonn_shared.catalog import list_benchmarks
items = list_benchmarks(shared_root=Path({str(CANONICAL_FIXTURE)!r}), fallback_catalog_dirs=(Path({str(FALLBACK_FIXTURE)!r}),))
print(','.join(item.id for item in items))
"""
    outputs = []
    for seed in ("1", "987654"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = seed
        outputs.append(subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True, env=environment).stdout)
    assert outputs[0] == outputs[1]


@pytest.mark.parametrize(
    ("fixture_name", "benchmark_id"),
    [
        ("duplicate_top.yaml", "contract_invalid_duplicate"),
        ("duplicate_nested.yaml", "contract_invalid_duplicate_nested"),
    ],
)
def test_duplicate_yaml_keys_reject_at_every_mapping_level(tmp_path: Path, fixture_name: str, benchmark_id: str) -> None:
    payload = (INVALID_FIXTURE / fixture_name).read_bytes()
    assert_catalog_error(
        InvalidCatalogYamlError,
        "invalid_catalog_yaml",
        lambda: invoke_fallback_yaml(tmp_path, benchmark_id, payload),
    )


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"- not\n- a\n- mapping\n",
        b"schema_version: 1.0.0\n---\nschema_version: 1.0.0\n",
        b"value: &shared [one]\nother: *shared\n",
        b"display_name: 2026-01-01\n",
        b"display_name: !!python/object:builtins.object {}\n",
        b"display_name: \xff\n",
    ],
)
def test_empty_nonmapping_multiple_alias_unsupported_and_invalid_utf8_yaml_reject(tmp_path: Path, payload: bytes) -> None:
    assert_catalog_error(
        InvalidCatalogYamlError,
        "invalid_catalog_yaml",
        lambda: invoke_fallback_yaml(tmp_path, "contract_invalid_yaml", payload),
    )


@pytest.mark.parametrize(
    "scalar",
    HOSTILE_CONSTRUCTOR_SCALARS,
    ids=("large_decimal", "invalid_timestamp"),
)
@pytest.mark.parametrize("action_name", ("get_benchmark", "list_benchmarks", "load_parity_pack"))
def test_benchmark_constructor_exceptions_use_stable_yaml_error(
    tmp_path: Path,
    scalar: str,
    action_name: str,
) -> None:
    root = empty_root(tmp_path / "root")
    benchmark_id = "contract_hostile_benchmark"
    fallback_catalog = tmp_path / "fallback-catalog"
    write_fallback(
        fallback_catalog,
        benchmark_id,
        text=yaml_for_benchmark(benchmark_id, display_name=scalar),
    )
    fallback_pack = tmp_path / "fallback-pack"
    fallback_pack.mkdir()
    pack_name = "contract_hostile_pack"
    (fallback_pack / f"{pack_name}.yaml").write_text(
        yaml_for_pack(pack_name, benchmark_id),
        encoding="utf-8",
    )
    actions = {
        "get_benchmark": lambda: get_benchmark(
            benchmark_id,
            shared_root=root,
            fallback_catalog_dirs=(fallback_catalog,),
        ),
        "list_benchmarks": lambda: list_benchmarks(
            shared_root=root,
            fallback_catalog_dirs=(fallback_catalog,),
        ),
        "load_parity_pack": lambda: load_parity_pack(
            pack_name,
            shared_root=root,
            fallback_pack_dirs=(fallback_pack,),
            fallback_catalog_dirs=(fallback_catalog,),
        ),
    }
    error = assert_catalog_error(
        InvalidCatalogYamlError,
        "invalid_catalog_yaml",
        actions[action_name],
    )
    assert type(error) is InvalidCatalogYamlError
    assert type(error.__cause__) is ValueError


@pytest.mark.parametrize(
    "scalar",
    HOSTILE_CONSTRUCTOR_SCALARS,
    ids=("large_decimal", "invalid_timestamp"),
)
@pytest.mark.parametrize("action_name", ("resolve_pack_path", "load_parity_pack"))
def test_pack_constructor_exceptions_use_stable_yaml_error(
    tmp_path: Path,
    scalar: str,
    action_name: str,
) -> None:
    root = empty_root(tmp_path / "root")
    fallback_pack = tmp_path / "fallback-pack"
    fallback_pack.mkdir()
    pack_name = "contract_hostile_pack"
    (fallback_pack / f"{pack_name}.yaml").write_text(
        yaml_for_pack(scalar, "contract_hostile_benchmark"),
        encoding="utf-8",
    )
    actions = {
        "resolve_pack_path": lambda: resolve_pack_path(
            pack_name,
            shared_root=root,
            fallback_pack_dirs=(fallback_pack,),
        ),
        "load_parity_pack": lambda: load_parity_pack(
            pack_name,
            shared_root=root,
            fallback_pack_dirs=(fallback_pack,),
        ),
    }
    error = assert_catalog_error(
        InvalidCatalogYamlError,
        "invalid_catalog_yaml",
        actions[action_name],
    )
    assert type(error) is InvalidCatalogYamlError
    assert type(error.__cause__) is ValueError


@pytest.mark.parametrize("complexity", ("depth", "nodes"))
@pytest.mark.parametrize("action_name", ("get_benchmark", "list_benchmarks", "load_parity_pack"))
def test_hostile_benchmark_complexity_is_bounded_during_composition(
    tmp_path: Path,
    complexity: str,
    action_name: str,
) -> None:
    root = empty_root(tmp_path / "root")
    benchmark_id = "contract_hostile_benchmark"
    fallback_catalog = tmp_path / "fallback-catalog"
    fallback_catalog.mkdir()
    (fallback_catalog / f"{benchmark_id}.yaml").write_bytes(hostile_yaml(complexity))
    fallback_pack = tmp_path / "fallback-pack"
    fallback_pack.mkdir()
    pack_name = "contract_hostile_pack"
    (fallback_pack / f"{pack_name}.yaml").write_text(
        yaml_for_pack(pack_name, benchmark_id),
        encoding="utf-8",
    )
    actions = {
        "get_benchmark": lambda: get_benchmark(
            benchmark_id,
            shared_root=root,
            fallback_catalog_dirs=(fallback_catalog,),
        ),
        "list_benchmarks": lambda: list_benchmarks(
            shared_root=root,
            fallback_catalog_dirs=(fallback_catalog,),
        ),
        "load_parity_pack": lambda: load_parity_pack(
            pack_name,
            shared_root=root,
            fallback_pack_dirs=(fallback_pack,),
            fallback_catalog_dirs=(fallback_catalog,),
        ),
    }
    assert_invalid_yaml_composer(actions[action_name])


@pytest.mark.parametrize("complexity", ("depth", "nodes"))
@pytest.mark.parametrize("action_name", ("get_benchmark", "list_benchmarks", "load_parity_pack"))
def test_hostile_canonical_registry_complexity_is_bounded_during_composition(
    tmp_path: Path,
    complexity: str,
    action_name: str,
) -> None:
    root = empty_root(tmp_path / "root")
    (root / "catalog" / "canonical_ids.yaml").write_bytes(hostile_yaml(complexity))
    pack_name = "contract_hostile_registry_pack"
    (root / "suites" / "parity" / f"{pack_name}.yaml").write_text(
        yaml_for_pack(pack_name, "contract_missing"),
        encoding="utf-8",
    )
    actions = {
        "get_benchmark": lambda: get_benchmark("contract_missing", shared_root=root),
        "list_benchmarks": lambda: list_benchmarks(shared_root=root),
        "load_parity_pack": lambda: load_parity_pack(pack_name, shared_root=root),
    }
    assert_invalid_yaml_composer(actions[action_name])


@pytest.mark.parametrize("complexity", ("depth", "nodes"))
@pytest.mark.parametrize("action_name", ("resolve_pack_path", "load_parity_pack"))
def test_hostile_pack_complexity_is_bounded_during_composition(
    tmp_path: Path,
    complexity: str,
    action_name: str,
) -> None:
    root = empty_root(tmp_path / "root")
    pack_name = "contract_hostile_pack"
    (root / "suites" / "parity" / f"{pack_name}.yaml").write_bytes(hostile_yaml(complexity))
    actions = {
        "resolve_pack_path": lambda: resolve_pack_path(pack_name, shared_root=root),
        "load_parity_pack": lambda: load_parity_pack(pack_name, shared_root=root),
    }
    assert_invalid_yaml_composer(actions[action_name])


@pytest.mark.parametrize("exception_type", (MemoryError, KeyboardInterrupt, SystemExit))
def test_loader_preserves_non_yaml_control_flow_exceptions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exception_type: type[BaseException],
) -> None:
    root = empty_root(tmp_path / "root")

    def raise_exception(_loader: object) -> object:
        raise exception_type("injected")

    monkeypatch.setattr(catalog._CatalogSafeLoader, "get_single_data", raise_exception)
    with pytest.raises(exception_type) as caught:
        get_benchmark("contract_missing", shared_root=root)
    assert type(caught.value) is exception_type


def test_oversized_yaml_rejects_before_model_validation(tmp_path: Path) -> None:
    payload = b"#" * (1024 * 1024 + 1)
    assert_catalog_error(
        InvalidCatalogYamlError,
        "invalid_catalog_yaml",
        lambda: invoke_fallback_yaml(tmp_path, "contract_oversized", payload),
    )


def test_unknown_yaml_fields_and_wrong_yaml_scalar_types_are_model_errors(tmp_path: Path) -> None:
    unknown = (INVALID_FIXTURE / "unknown_field.yaml").read_bytes()
    assert_catalog_error(
        InvalidCatalogModelError,
        "invalid_catalog_model",
        lambda: invoke_fallback_yaml(tmp_path, "contract_invalid_unknown", unknown),
    )
    wrong = yaml_for_benchmark("contract_wrong_scalar").replace("output_dim: 2", 'output_dim: "2"').encode()
    assert_catalog_error(
        InvalidCatalogModelError,
        "invalid_catalog_model",
        lambda: invoke_fallback_yaml(tmp_path / "wrong", "contract_wrong_scalar", wrong),
    )


def test_invalid_requested_names_reject_before_any_filesystem_lookup() -> None:
    missing = Path("/definitely/not/present")
    for value in ("../bad", "bad/name", "/absolute", "bad-name", ""):
        assert_catalog_error(
            InvalidCatalogIdentifierError,
            "invalid_catalog_identifier",
            lambda value=value: get_benchmark(value, shared_root=missing),
        )
        assert_catalog_error(
            InvalidCatalogIdentifierError,
            "invalid_catalog_identifier",
            lambda value=value: resolve_pack_path(value, shared_root=missing),
        )


def test_invalid_requested_identifier_does_not_dispatch_hostile_repr() -> None:
    class HostileIdentifier:
        def __repr__(self) -> str:
            raise AssertionError("must not dispatch")

    assert_catalog_error(
        InvalidCatalogIdentifierError,
        "invalid_catalog_identifier",
        lambda: get_benchmark(HostileIdentifier()),  # type: ignore[arg-type]
    )


def test_unknown_benchmark_and_pack_have_stable_distinct_errors(tmp_path: Path) -> None:
    root = empty_root(tmp_path / "root")
    benchmark_error = assert_catalog_error(
        BenchmarkNotFoundError,
        "benchmark_not_found",
        lambda: get_benchmark("contract_missing", shared_root=root),
    )
    pack_error = assert_catalog_error(
        PackNotFoundError,
        "pack_not_found",
        lambda: resolve_pack_path("contract_missing", shared_root=root),
    )
    assert str(benchmark_error) == "benchmark not found: contract_missing"
    assert str(pack_error) == "pack not found: contract_missing"


def test_complete_spec_shaped_pack_dictionary_validates() -> None:
    pack = BenchmarkPack.model_validate(pack_data())
    assert pack == BenchmarkPack(
        schema_version="1.0.0",
        pack_name="contract_model_pack",
        ladder_tier=LadderTier.A,
        benchmarks=("contract_alpha", "contract_beta"),
        budget_policy=PackBudgetPolicy(evaluation_count=4),
        symmetry="symmetric",
        modalities=(InputModality.TABULAR,),
        expected_local_runtime_class="medium",
        minimum_contenders=("linear_contender", "tree_contender"),
        suitability="daily",
        full_fidelity_local_safe=True,
    )


def test_pack_fixtures_load_with_exact_admission_declarations() -> None:
    canonical = load_parity_pack("contract_parity_pack", shared_root=CANONICAL_FIXTURE)
    assert canonical.ladder_tier is LadderTier.A
    assert canonical.benchmarks == (
        "contract_beta_regression",
        "contract_alpha_classification",
    )
    assert canonical.budget_policy.evaluation_count == 4
    assert canonical.symmetry == "symmetric"
    assert canonical.modalities == (InputModality.TABULAR,)
    assert canonical.expected_local_runtime_class == "medium"
    assert canonical.minimum_contenders == ("linear_contender", "tree_contender")
    assert canonical.suitability == "daily"
    assert canonical.full_fidelity_local_safe is True

    fallback = load_parity_pack(
        "contract_fallback_pack",
        shared_root=CANONICAL_FIXTURE,
        fallback_pack_dirs=(FALLBACK_PACK_FIXTURE,),
        fallback_catalog_dirs=(FALLBACK_FIXTURE,),
    )
    assert fallback.ladder_tier is LadderTier.B
    assert fallback.benchmarks == ("contract_fallback_sequence",)
    assert fallback.budget_policy.evaluation_count == 2
    assert fallback.symmetry == "leaning-prism"
    assert fallback.modalities == (InputModality.SEQUENCE,)
    assert fallback.expected_local_runtime_class == "slow"
    assert fallback.minimum_contenders == ("linear_contender",)
    assert fallback.suitability == "overnight"
    assert fallback.full_fidelity_local_safe is False


@pytest.mark.parametrize(
    "field",
    (
        "schema_version",
        "pack_name",
        "ladder_tier",
        "benchmarks",
        "budget_policy",
        "symmetry",
        "modalities",
        "expected_local_runtime_class",
        "minimum_contenders",
        "suitability",
        "full_fidelity_local_safe",
    ),
)
def test_every_pack_field_is_mandatory(field: str) -> None:
    data = pack_data()
    del data[field]
    with pytest.raises(ValidationError):
        BenchmarkPack.model_validate(data)


def test_obsolete_nested_symmetry_shape_rejects() -> None:
    data = pack_data(budget_policy={"evaluation_count": 4, "symmetry": "symmetric"})
    del data["symmetry"]
    with pytest.raises(ValidationError):
        BenchmarkPack.model_validate(data)


def test_pack_literal_symmetry_and_boolean_state_matrix_is_exact() -> None:
    for symmetry in ("symmetric", *(f"leaning-{system.value}" for system in SystemId)):
        assert BenchmarkPack.model_validate(pack_data(symmetry=symmetry)).symmetry == symmetry
    for runtime_class in ("fast", "medium", "slow"):
        pack = BenchmarkPack.model_validate(
            pack_data(expected_local_runtime_class=runtime_class)
        )
        assert pack.expected_local_runtime_class == runtime_class
    for suitability in ("smoke", "daily", "overnight", "special-study"):
        pack = BenchmarkPack.model_validate(pack_data(suitability=suitability))
        assert pack.suitability == suitability
    for local_safe in (True, False):
        pack = BenchmarkPack.model_validate(
            pack_data(full_fidelity_local_safe=local_safe)
        )
        assert pack.full_fidelity_local_safe is local_safe


@pytest.mark.parametrize(
    "modalities",
    (
        (),
        (InputModality.TABULAR, InputModality.TABULAR),
        (InputModality.TABULAR, InputModality.IMAGE),
    ),
)
def test_pack_modalities_reject_empty_duplicate_and_unsorted_values(
    modalities: tuple[InputModality, ...],
) -> None:
    with pytest.raises(ValidationError):
        BenchmarkPack.model_validate(pack_data(modalities=modalities))


def test_pack_modalities_accept_all_values_in_utf8_order() -> None:
    modalities = tuple(sorted(InputModality, key=lambda item: item.value.encode("utf-8")))
    assert BenchmarkPack.model_validate(pack_data(modalities=modalities)).modalities == modalities


@pytest.mark.parametrize(
    "minimum_contenders",
    (
        (),
        ("linear_contender", "linear_contender"),
        ("tree_contender", "linear_contender"),
        ("bad-id",),
    ),
)
def test_pack_minimum_contenders_reject_invalid_sets(
    minimum_contenders: tuple[str, ...],
) -> None:
    with pytest.raises(ValidationError):
        BenchmarkPack.model_validate(
            pack_data(minimum_contenders=minimum_contenders)
        )


@pytest.mark.parametrize(
    "changes",
    (
        {"expected_local_runtime_class": "weekend"},
        {"suitability": "local"},
        {"suitability": "weekend"},
        {"full_fidelity_local_safe": "true"},
        {"full_fidelity_local_safe": 0},
        {"full_fidelity_local_safe": 1},
        {"symmetry": "leaning-unknown"},
        {"symmetry": "asymmetric"},
    ),
)
def test_pack_rejects_unknown_literals_and_nonboolean_fidelity(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        BenchmarkPack.model_validate(pack_data(**changes))


def test_pack_benchmarks_and_evaluation_count_rules_are_preserved() -> None:
    invalid = [
        pack_data(benchmarks=()),
        pack_data(benchmarks=("contract_alpha", "contract_alpha")),
        pack_data(benchmarks=("bad-id",)),
        pack_data(budget_policy={"evaluation_count": 3}),
        pack_data(budget_policy={"evaluation_count": 0}),
    ]
    for data in invalid:
        with pytest.raises(ValidationError):
            BenchmarkPack.model_validate(data)


def test_pack_canonical_precedence_fallback_resolution_and_validated_path(tmp_path: Path) -> None:
    root = copy_canonical_root(tmp_path / "root")
    fallback = tmp_path / "fallback-packs"
    shutil.copytree(FALLBACK_PACK_FIXTURE, fallback)
    shutil.copy(
        CANONICAL_FIXTURE / "suites" / "parity" / "contract_parity_pack.yaml",
        fallback / "contract_parity_pack.yaml",
    )
    canonical_path = root / "suites" / "parity" / "contract_parity_pack.yaml"
    assert resolve_pack_path("contract_parity_pack", shared_root=root, fallback_pack_dirs=(fallback,)) == canonical_path
    assert load_parity_pack("contract_parity_pack", shared_root=root, fallback_pack_dirs=(fallback,)).ladder_tier is LadderTier.A
    assert resolve_pack_path("contract_fallback_pack", shared_root=root, fallback_pack_dirs=(fallback,)) == fallback / "contract_fallback_pack.yaml"


def test_duplicate_fallback_packs_malformed_and_stem_name_mismatch_reject(tmp_path: Path) -> None:
    root = empty_root(tmp_path / "root")
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    pack_text = (FALLBACK_PACK_FIXTURE / "contract_fallback_pack.yaml").read_text(encoding="utf-8")
    (first / "contract_fallback_pack.yaml").write_text(pack_text, encoding="utf-8")
    (second / "contract_fallback_pack.yaml").write_text(pack_text, encoding="utf-8")
    assert_catalog_error(
        DuplicateCatalogDefinitionError,
        "duplicate_catalog_definition",
        lambda: resolve_pack_path("contract_fallback_pack", shared_root=root, fallback_pack_dirs=(first, second)),
    )
    (second / "contract_fallback_pack.yaml").unlink()
    (first / "contract_fallback_pack.yaml").write_text(pack_text.replace("pack_name: contract_fallback_pack", "pack_name: contract_wrong_name"), encoding="utf-8")
    assert_catalog_error(
        InvalidCatalogModelError,
        "invalid_catalog_model",
        lambda: resolve_pack_path("contract_fallback_pack", shared_root=root, fallback_pack_dirs=(first,)),
    )
    (first / "contract_fallback_pack.yaml").write_text("schema_version: 1.0.0\n", encoding="utf-8")
    assert_catalog_error(
        InvalidCatalogModelError,
        "invalid_catalog_model",
        lambda: resolve_pack_path("contract_fallback_pack", shared_root=root, fallback_pack_dirs=(first,)),
    )


def test_fallback_pack_loaders_reject_differently_named_files_declaring_requested_name(
    tmp_path: Path,
) -> None:
    root = copy_canonical_root(tmp_path / "root")
    fallback = tmp_path / "fallback"
    fallback.mkdir()
    pack_text = (
        CANONICAL_FIXTURE / "suites" / "parity" / "contract_parity_pack.yaml"
    ).read_text(encoding="utf-8").replace(
        "pack_name: contract_parity_pack",
        "pack_name: contract_target_pack",
    )
    (fallback / "contract_target_pack.yaml").write_text(pack_text, encoding="utf-8")
    (fallback / "contract_shadow_pack.yaml").write_text(pack_text, encoding="utf-8")
    actions = (
        lambda: resolve_pack_path(
            "contract_target_pack",
            shared_root=root,
            fallback_pack_dirs=(fallback,),
        ),
        lambda: load_parity_pack(
            "contract_target_pack",
            shared_root=root,
            fallback_pack_dirs=(fallback,),
        ),
    )
    for action in actions:
        assert_catalog_error(
            DuplicateCatalogDefinitionError,
            "duplicate_catalog_definition",
            action,
        )


def test_unknown_pack_benchmark_references_are_utf8_sorted(tmp_path: Path) -> None:
    root = empty_root(tmp_path / "root")
    pack_path = root / "suites" / "parity" / "contract_unknown_pack.yaml"
    pack_path.write_text(
        """schema_version: 1.0.0
pack_name: contract_unknown_pack
ladder_tier: A
benchmarks: [contract_zeta, contract_alpha]
budget_policy:
  evaluation_count: 2
symmetry: symmetric
modalities: [tabular]
expected_local_runtime_class: fast
minimum_contenders: [linear_contender]
suitability: smoke
full_fidelity_local_safe: true
""",
        encoding="utf-8",
    )
    error = assert_catalog_error(
        UnknownPackBenchmarkError,
        "unknown_pack_benchmark",
        lambda: load_parity_pack("contract_unknown_pack", shared_root=root),
    )
    assert str(error) == "pack references unknown benchmarks: contract_alpha, contract_zeta"


def test_pack_references_resolve_across_canonical_and_fallback_catalogs(tmp_path: Path) -> None:
    root = copy_canonical_root(tmp_path / "root")
    fallback_catalog = tmp_path / "fallback-catalog"
    shutil.copytree(FALLBACK_FIXTURE, fallback_catalog)
    fallback_pack = tmp_path / "fallback-pack"
    fallback_pack.mkdir()
    (fallback_pack / "contract_mixed_pack.yaml").write_text(
        """schema_version: 1.0.0
pack_name: contract_mixed_pack
ladder_tier: B
benchmarks: [contract_alpha_classification, contract_fallback_sequence]
budget_policy:
  evaluation_count: 4
symmetry: symmetric
modalities: [sequence, tabular]
expected_local_runtime_class: medium
minimum_contenders: [linear_contender, tree_contender]
suitability: daily
full_fidelity_local_safe: false
""",
        encoding="utf-8",
    )
    pack = load_parity_pack(
        "contract_mixed_pack",
        shared_root=root,
        fallback_pack_dirs=(fallback_pack,),
        fallback_catalog_dirs=(fallback_catalog,),
    )
    assert pack.benchmarks == ("contract_alpha_classification", "contract_fallback_sequence")


def test_symlink_root_intermediate_and_final_file_reject(tmp_path: Path) -> None:
    real = copy_canonical_root(tmp_path / "real")
    linked_root = tmp_path / "linked-root"
    linked_root.symlink_to(real, target_is_directory=True)
    assert_catalog_error(UnsafeCatalogPathError, "unsafe_catalog_path", lambda: list_benchmarks(shared_root=linked_root))

    root = empty_root(tmp_path / "root")
    shutil.rmtree(root / "catalog")
    (root / "catalog").symlink_to(real / "catalog", target_is_directory=True)
    assert_catalog_error(UnsafeCatalogPathError, "unsafe_catalog_path", lambda: list_benchmarks(shared_root=root))

    root = empty_root(tmp_path / "root-file")
    fallback = tmp_path / "fallback"
    fallback.mkdir()
    outside = tmp_path / "outside.yaml"
    outside.write_text(yaml_for_benchmark("contract_linked"), encoding="utf-8")
    (fallback / "contract_linked.yaml").symlink_to(outside)
    assert_catalog_error(
        UnsafeCatalogPathError,
        "unsafe_catalog_path",
        lambda: get_benchmark("contract_linked", shared_root=root, fallback_catalog_dirs=(fallback,)),
    )


def test_file_directory_and_nonregular_replacements_reject(tmp_path: Path) -> None:
    root = empty_root(tmp_path / "root")
    shutil.rmtree(root / "catalog")
    (root / "catalog").write_text("not a directory\n", encoding="utf-8")
    assert_catalog_error(UnsafeCatalogPathError, "unsafe_catalog_path", lambda: list_benchmarks(shared_root=root))

    root = empty_root(tmp_path / "root-file")
    fallback = tmp_path / "fallback"
    fallback.mkdir()
    (fallback / "contract_directory.yaml").mkdir()
    assert_catalog_error(
        UnsafeCatalogPathError,
        "unsafe_catalog_path",
        lambda: get_benchmark("contract_directory", shared_root=root, fallback_catalog_dirs=(fallback,)),
    )

    if hasattr(os, "mkfifo"):
        fifo = fallback / "contract_fifo.yaml"
        os.mkfifo(fifo)
        assert_catalog_error(
            UnsafeCatalogPathError,
            "unsafe_catalog_path",
            lambda: get_benchmark("contract_fifo", shared_root=root, fallback_catalog_dirs=(fallback,)),
        )


def test_discovered_file_replaced_by_symlink_before_open_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = empty_root(tmp_path / "root")
    fallback = tmp_path / "fallback"
    target = write_fallback(fallback, "contract_race")
    outside = tmp_path / "outside.yaml"
    outside.write_text(yaml_for_benchmark("contract_race", display_name="Outside Bytes"), encoding="utf-8")
    real_open = catalog.os.open
    replaced = False

    def racing_open(path: object, flags: int, mode: int = 0o777, *, dir_fd: int | None = None) -> int:
        nonlocal replaced
        if path == "contract_race.yaml" and dir_fd is not None and not replaced:
            replaced = True
            target.unlink()
            target.symlink_to(outside)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(catalog.os, "open", racing_open)
    assert_catalog_error(
        UnsafeCatalogPathError,
        "unsafe_catalog_path",
        lambda: list_benchmarks(shared_root=root, fallback_catalog_dirs=(fallback,)),
    )
    assert replaced


def test_intermediate_descriptor_close_failure_is_never_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = empty_root(tmp_path / "root")
    real_close = catalog.os.close
    close_counts: dict[int, int] = {}
    failed_descriptor: int | None = None

    def failing_close(descriptor: int) -> None:
        nonlocal failed_descriptor
        close_counts[descriptor] = close_counts.get(descriptor, 0) + 1
        if failed_descriptor is None:
            failed_descriptor = descriptor
            raise OSError("injected close failure")
        real_close(descriptor)

    monkeypatch.setattr(catalog.os, "close", failing_close)
    assert_catalog_error(
        UnsafeCatalogPathError,
        "unsafe_catalog_path",
        lambda: list_benchmarks(shared_root=root),
    )
    monkeypatch.undo()
    assert failed_descriptor is not None
    assert close_counts[failed_descriptor] == 1
    try:
        real_close(failed_descriptor)
    except OSError:
        pass


@pytest.mark.parametrize(
    "target",
    ["root", "catalog", "fallback", "fallback_identity"],
)
def test_directory_fstat_failures_use_stable_catalog_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
) -> None:
    root = empty_root(tmp_path / "root")
    fallback = tmp_path / "fallback"
    fallback.mkdir()
    target_path = {
        "root": root,
        "catalog": root / "catalog",
        "fallback": fallback,
        "fallback_identity": fallback,
    }[target]
    target_identity = (target_path.stat().st_dev, target_path.stat().st_ino)
    real_fstat = catalog.os.fstat
    target_calls = 0

    def failing_fstat(descriptor: int) -> os.stat_result:
        nonlocal target_calls
        status = real_fstat(descriptor)
        if (status.st_dev, status.st_ino) == target_identity:
            target_calls += 1
            if target != "fallback_identity" or target_calls == 2:
                raise OSError("injected directory fstat failure")
        return status

    monkeypatch.setattr(catalog.os, "fstat", failing_fstat)

    def action() -> None:
        if target in {"fallback", "fallback_identity"}:
            list_benchmarks(
                shared_root=root,
                fallback_catalog_dirs=(fallback,),
            )
        else:
            list_benchmarks(shared_root=root)

    assert_catalog_error(
        UnsafeCatalogPathError,
        "unsafe_catalog_path",
        action,
    )


def test_fallback_cleanup_closes_every_descriptor_once_after_close_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = empty_root(tmp_path / "root")
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    identities = {
        "first": (first.stat().st_dev, first.stat().st_ino),
        "second": (second.stat().st_dev, second.stat().st_ino),
    }
    real_close = catalog.os.close
    close_counts = {"first": 0, "second": 0}
    failed = False

    def failing_close(descriptor: int) -> None:
        nonlocal failed
        status = os.fstat(descriptor)
        identity = (status.st_dev, status.st_ino)
        for name, expected in identities.items():
            if identity == expected:
                close_counts[name] += 1
        if identity == identities["second"] and not failed:
            failed = True
            raise OSError("injected fallback close failure")
        real_close(descriptor)

    monkeypatch.setattr(catalog.os, "close", failing_close)
    assert_catalog_error(
        UnsafeCatalogPathError,
        "unsafe_catalog_path",
        lambda: list_benchmarks(shared_root=root, fallback_catalog_dirs=(first, second)),
    )
    monkeypatch.undo()
    assert close_counts == {"first": 1, "second": 1}
    for descriptor in range(3, 256):
        try:
            status = os.fstat(descriptor)
        except OSError:
            continue
        if (status.st_dev, status.st_ino) in identities.values():
            real_close(descriptor)


def test_resolve_pack_path_is_lexical_and_load_rechecks_replacement(tmp_path: Path) -> None:
    root = copy_canonical_root(tmp_path / "root")
    resolved = resolve_pack_path("contract_parity_pack", shared_root=root)
    outside = tmp_path / "outside-pack.yaml"
    outside.write_text(resolved.read_text(encoding="utf-8"), encoding="utf-8")
    resolved.unlink()
    resolved.symlink_to(outside)
    assert_catalog_error(
        UnsafeCatalogPathError,
        "unsafe_catalog_path",
        lambda: load_parity_pack("contract_parity_pack", shared_root=root),
    )


def test_production_data_only_catalog_is_exactly_empty_and_no_pack_was_invented() -> None:
    registry = PRODUCTION_ROOT / "catalog" / "canonical_ids.yaml"
    assert registry.read_bytes() == b"schema_version: 1.0.0\nentries: []\n"
    assert sorted(path.name for path in (PRODUCTION_ROOT / "catalog").iterdir()) == ["canonical_ids.yaml"]
    assert list((PRODUCTION_ROOT / "suites" / "parity").glob("*.yaml")) == []
    assert list_benchmarks(shared_root=PRODUCTION_ROOT) == ()


def test_committed_registry_mismatch_fixture_fails_with_registry_code(tmp_path: Path) -> None:
    root = tmp_path / "root"
    shutil.copytree(INVALID_FIXTURE / "registry-mismatch", root)
    (root / "suites" / "parity").mkdir(parents=True)
    assert_catalog_error(
        CatalogRegistryMismatchError,
        "catalog_registry_mismatch",
        lambda: list_benchmarks(shared_root=root),
    )
