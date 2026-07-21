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
    PackBudgetPolicy: {"evaluation_count", "symmetry"},
    BenchmarkPack: {"schema_version", "pack_name", "ladder_tier", "benchmarks", "budget_policy"},
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
        "budget_policy": {"evaluation_count": 4, "symmetry": "symmetric"},
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


def test_pack_model_order_uniqueness_symmetry_and_divisibility() -> None:
    assert BenchmarkPack.model_validate(pack_data()).benchmarks == ("contract_alpha", "contract_beta")
    for system in SystemId:
        policy = PackBudgetPolicy(evaluation_count=2, symmetry=f"leaning-{system.value}")
        assert policy.symmetry == f"leaning-{system.value}"
    invalid = [
        pack_data(benchmarks=()),
        pack_data(benchmarks=("contract_alpha", "contract_alpha")),
        pack_data(benchmarks=("bad-id",)),
        pack_data(budget_policy={"evaluation_count": 3, "symmetry": "symmetric"}),
        pack_data(budget_policy={"evaluation_count": 0, "symmetry": "symmetric"}),
        pack_data(budget_policy={"evaluation_count": 4, "symmetry": "leaning-unknown"}),
        pack_data(budget_policy={"evaluation_count": 4, "symmetry": "asymmetric"}),
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
