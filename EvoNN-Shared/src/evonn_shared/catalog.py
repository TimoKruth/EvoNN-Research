"""Frozen benchmark catalog models and descriptor-safe YAML loaders."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from enum import StrEnum
import json
import math
import os
from pathlib import Path
import re
import stat
from typing import Any, Literal, TypeVar

from pydantic import Field, ValidationError, field_validator, model_validator
import yaml
from yaml.events import AliasEvent
from yaml.nodes import MappingNode

from . import benchmarks as _benchmarks
from .budgets import ContractModel, LadderTier, _canonical_id, _human_text, _utf8_sorted_unique
from .canonical import canonical_sha256
from .telemetry import MetricDirection, SystemId, TaskKind

CATALOG_SCHEMA_VERSION = "1.0.0"

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MAX_YAML_BYTES = 1024 * 1024
_DEFINITION_SCHEMA = "evonn.catalog.benchmark/v1"
_PATH_TYPE = type(Path())
_ENVIRONMENT_ROOT = "EVONN_SHARED_BENCHMARKS_DIR"
_HAS_OPEN_DIR_FD = os.open in os.supports_dir_fd


class BenchmarkStatus(StrEnum):
    PLANNED = "planned"
    IMPLEMENTED = "implemented"
    EXPERIMENTAL = "experimental"
    DISABLED = "disabled"


class InputModality(StrEnum):
    TABULAR = "tabular"
    IMAGE = "image"
    TEXT = "text"
    SEQUENCE = "sequence"


class CeilingTiePolicy(StrEnum):
    NOT_EVIDENCE = "not_evidence"
    BEST_OBSERVED = "best_observed"


class PrimaryMetric(ContractModel):
    name: str
    direction: MetricDirection

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return _canonical_id(value, "name")


class MetricCeiling(ContractModel):
    value: float | None
    tie_policy: CeilingTiePolicy

    @field_validator("value", mode="before")
    @classmethod
    def _strict_optional_float(cls, value: object) -> object:
        if value is not None and type(value) is not float:
            raise ValueError("ceiling value must be an exact float or None")
        return value

    @field_validator("value")
    @classmethod
    def _finite_optional_float(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("ceiling value must be finite when present")
        return value

    @model_validator(mode="after")
    def _validate_state(self) -> MetricCeiling:
        if self.value is None:
            if self.tie_policy is not CeilingTiePolicy.BEST_OBSERVED:
                raise ValueError("an unbounded metric must use best_observed")
        elif self.tie_policy is not CeilingTiePolicy.NOT_EVIDENCE:
            raise ValueError("a finite natural ceiling must use not_evidence")
        return self


class BenchmarkSpec(ContractModel):
    schema_version: Literal["1.0.0"]
    id: str
    display_name: str
    status: BenchmarkStatus
    task_kind: TaskKind
    input_modality: InputModality
    input_shape: tuple[int, ...]
    output_dim: int = Field(gt=0)
    primary_metric: PrimaryMetric
    ceiling: MetricCeiling
    budget_epochs: int = Field(gt=0)
    runtime_class: str
    required_contenders: tuple[str, ...]
    tags: tuple[str, ...]

    @field_validator("id", "runtime_class")
    @classmethod
    def _validate_identifier(cls, value: str, info: Any) -> str:
        return _canonical_id(value, info.field_name)

    @field_validator("display_name")
    @classmethod
    def _validate_display_name(cls, value: str) -> str:
        return _human_text(value, "display_name")

    @field_validator("input_shape")
    @classmethod
    def _validate_input_shape(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if not value:
            raise ValueError("input_shape must be nonempty")
        if any(type(dimension) is not int or dimension <= 0 for dimension in value):
            raise ValueError("input_shape dimensions must be exact positive integers")
        return value

    @field_validator("required_contenders", "tags")
    @classmethod
    def _validate_identifier_sets(cls, value: tuple[str, ...], info: Any) -> tuple[str, ...]:
        if info.field_name == "required_contenders" and not value:
            raise ValueError("required_contenders must be nonempty")
        for item in value:
            _canonical_id(item, info.field_name)
        return _utf8_sorted_unique(value, info.field_name)


class CanonicalIdEntry(ContractModel):
    id: str
    definition_sha256: str

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        return _canonical_id(value, "id")

    @field_validator("definition_sha256")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        if _SHA256_PATTERN.fullmatch(value) is None:
            raise ValueError("definition_sha256 must be exactly 64 lowercase hex characters")
        return value


class CanonicalIdRegistry(ContractModel):
    schema_version: Literal["1.0.0"]
    entries: tuple[CanonicalIdEntry, ...]

    @field_validator("entries")
    @classmethod
    def _validate_entries(cls, value: tuple[CanonicalIdEntry, ...]) -> tuple[CanonicalIdEntry, ...]:
        identifiers = tuple(item.id for item in value)
        _utf8_sorted_unique(identifiers, "registry entry IDs")
        return value


class PackBudgetPolicy(ContractModel):
    evaluation_count: int = Field(gt=0)
    symmetry: str

    @field_validator("symmetry")
    @classmethod
    def _validate_symmetry(cls, value: str) -> str:
        allowed = {"symmetric", *(f"leaning-{system.value}" for system in SystemId)}
        if value not in allowed:
            raise ValueError("symmetry must be symmetric or leaning-<system>")
        return value


class BenchmarkPack(ContractModel):
    schema_version: Literal["1.0.0"]
    pack_name: str
    ladder_tier: LadderTier
    benchmarks: tuple[str, ...]
    budget_policy: PackBudgetPolicy

    @field_validator("pack_name")
    @classmethod
    def _validate_pack_name(cls, value: str) -> str:
        return _canonical_id(value, "pack_name")

    @field_validator("benchmarks")
    @classmethod
    def _validate_benchmarks(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("pack benchmarks must be nonempty")
        for benchmark_id in value:
            _canonical_id(benchmark_id, "benchmarks")
        if len(value) != len(set(value)):
            raise ValueError("pack benchmarks must not contain duplicates")
        return value

    @model_validator(mode="after")
    def _validate_budget_divisibility(self) -> BenchmarkPack:
        if self.budget_policy.evaluation_count % len(self.benchmarks) != 0:
            raise ValueError("evaluation_count must divide evenly by the benchmark count")
        return self


class CatalogError(ValueError):
    """Base class for deterministic benchmark catalog errors."""

    code = "catalog_error"


class InvalidCatalogIdentifierError(CatalogError):
    code = "invalid_catalog_identifier"


class UnsafeCatalogPathError(CatalogError):
    code = "unsafe_catalog_path"


class DuplicateCatalogDefinitionError(CatalogError):
    code = "duplicate_catalog_definition"


class InvalidCatalogYamlError(CatalogError):
    code = "invalid_catalog_yaml"


class InvalidCatalogModelError(CatalogError):
    code = "invalid_catalog_model"


class CatalogRegistryMismatchError(CatalogError):
    code = "catalog_registry_mismatch"


class BenchmarkNotFoundError(CatalogError):
    code = "benchmark_not_found"


class PackNotFoundError(CatalogError):
    code = "pack_not_found"


class UnknownPackBenchmarkError(CatalogError):
    code = "unknown_pack_benchmark"


class _CatalogSafeLoader(yaml.SafeLoader):
    def compose_node(self, parent: Any, index: Any) -> Any:
        if self.check_event(AliasEvent):
            event = self.peek_event()
            raise yaml.composer.ComposerError(
                "while composing catalog YAML",
                event.start_mark,
                "aliases are not allowed",
                event.start_mark,
            )
        return super().compose_node(parent, index)

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[object, object]:
        if not isinstance(node, MappingNode):
            raise yaml.constructor.ConstructorError(
                None,
                None,
                "expected a mapping node",
                node.start_mark,
            )
        self.flatten_mapping(node)
        seen: set[object] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in seen
            except TypeError as error:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "mapping keys must be hashable",
                    key_node.start_mark,
                ) from error
            if duplicate:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"duplicate mapping key: {key!r}",
                    key_node.start_mark,
                )
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


_ModelT = TypeVar("_ModelT", bound=ContractModel)


def _invalid_identifier(_value: object, label: str) -> InvalidCatalogIdentifierError:
    return InvalidCatalogIdentifierError(f"invalid {label}")


def _validate_requested_identifier(value: object, label: str) -> str:
    if type(value) is not str:
        raise _invalid_identifier(value, label)
    try:
        return _canonical_id(value, label)
    except ValueError as error:
        raise _invalid_identifier(value, label) from error


def _require_path(value: object, label: str) -> Path:
    if type(value) is not _PATH_TYPE:
        raise UnsafeCatalogPathError(f"{label} must be a concrete pathlib.Path")
    return value


def _require_platform_support() -> None:
    if (
        not hasattr(os, "O_DIRECTORY")
        or not hasattr(os, "O_NOFOLLOW")
        or not _HAS_OPEN_DIR_FD
    ):
        raise UnsafeCatalogPathError("descriptor-relative no-follow catalog access is unsupported")


def _directory_flags() -> int:
    _require_platform_support()
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    return flags


def _file_flags() -> int:
    _require_platform_support()
    flags = os.O_RDONLY | os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    return flags


def _close_descriptor(descriptor: int, label: str, primary: BaseException | None = None) -> None:
    try:
        os.close(descriptor)
    except BaseException as error:
        if primary is not None:
            primary.add_note(f"{label} close failed without retry: {error!r}")
            return
        raise UnsafeCatalogPathError(f"failed to close {label}") from error


@contextmanager
def _managed_descriptor(descriptor: int, label: str) -> Iterator[int]:
    primary: BaseException | None = None
    try:
        yield descriptor
    except BaseException as error:
        primary = error
        raise
    finally:
        _close_descriptor(descriptor, label, primary)


def _open_directory_path(path: Path, label: str) -> int:
    path = _require_path(path, label)
    flags = _directory_flags()
    try:
        if path.is_absolute():
            descriptor = os.open(path.anchor, flags)
            components = path.parts[1:]
        else:
            descriptor = os.open(".", flags)
            components = path.parts
    except OSError as error:
        raise UnsafeCatalogPathError(f"unable to open {label} safely") from error

    active_descriptor: int | None = descriptor
    try:
        for component in components:
            if component in ("", "."):
                continue
            assert active_descriptor is not None
            try:
                next_descriptor = os.open(component, flags, dir_fd=active_descriptor)
            except OSError as error:
                raise UnsafeCatalogPathError(f"unable to open {label} safely") from error
            retired_descriptor = active_descriptor
            active_descriptor = None
            try:
                _close_descriptor(retired_descriptor, label)
            except BaseException as error:
                _close_descriptor(next_descriptor, label, error)
                raise
            active_descriptor = next_descriptor
        assert active_descriptor is not None
        if not stat.S_ISDIR(os.fstat(active_descriptor).st_mode):
            raise UnsafeCatalogPathError(f"{label} is not a directory")
        return active_descriptor
    except BaseException as error:
        if active_descriptor is not None:
            _close_descriptor(active_descriptor, label, error)
        raise


def _open_child_directory(parent_fd: int, name: str, label: str) -> int:
    try:
        descriptor = os.open(name, _directory_flags(), dir_fd=parent_fd)
    except OSError as error:
        raise UnsafeCatalogPathError(f"unable to open {label} safely") from error
    try:
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise UnsafeCatalogPathError(f"{label} is not a directory")
        return descriptor
    except BaseException as error:
        _close_descriptor(descriptor, label, error)
        raise


def _read_file_at(directory_fd: int, filename: str, label: str, *, optional: bool = False) -> bytes | None:
    try:
        descriptor = os.open(filename, _file_flags(), dir_fd=directory_fd)
    except FileNotFoundError:
        if optional:
            return None
        raise UnsafeCatalogPathError(f"required catalog file is missing: {label}") from None
    except OSError as error:
        raise UnsafeCatalogPathError(f"unable to open catalog file safely: {label}") from error

    with _managed_descriptor(descriptor, label):
        try:
            status = os.fstat(descriptor)
        except OSError as error:
            raise UnsafeCatalogPathError(f"unable to inspect catalog file safely: {label}") from error
        if not stat.S_ISREG(status.st_mode):
            raise UnsafeCatalogPathError(f"catalog file is not a regular file: {label}")
        if status.st_size > _MAX_YAML_BYTES:
            raise InvalidCatalogYamlError(f"catalog YAML exceeds size limit: {label}")
        chunks: list[bytes] = []
        total = 0
        while True:
            try:
                chunk = os.read(descriptor, min(65536, _MAX_YAML_BYTES + 1 - total))
            except OSError as error:
                raise UnsafeCatalogPathError(f"unable to read catalog file safely: {label}") from error
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > _MAX_YAML_BYTES:
                raise InvalidCatalogYamlError(f"catalog YAML exceeds size limit: {label}")
        return b"".join(chunks)


def _validate_yaml_types(value: object) -> None:
    value_type = type(value)
    if value is None or value_type in (bool, int, float, str):
        return
    if value_type is list:
        for item in value:
            _validate_yaml_types(item)
        return
    if value_type is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError("YAML mapping keys must be strings")
            _validate_yaml_types(item)
        return
    raise TypeError(f"unsupported YAML value type: {value_type.__module__}.{value_type.__qualname__}")


def _parse_yaml(payload: bytes, label: str) -> dict[str, object]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise InvalidCatalogYamlError(f"catalog YAML is not valid UTF-8: {label}") from error
    loader = _CatalogSafeLoader(text)
    try:
        value = loader.get_single_data()
    except yaml.YAMLError as error:
        raise InvalidCatalogYamlError(f"catalog YAML is invalid: {label}") from error
    finally:
        loader.dispose()
    if type(value) is not dict:
        raise InvalidCatalogYamlError(f"catalog YAML root must be a mapping: {label}")
    try:
        _validate_yaml_types(value)
    except TypeError as error:
        raise InvalidCatalogYamlError(f"catalog YAML contains unsupported values: {label}") from error
    return value


def _parse_model(payload: bytes, model: type[_ModelT], label: str) -> _ModelT:
    value = _parse_yaml(payload, label)
    try:
        json_payload = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, UnicodeEncodeError, ValueError) as error:
        raise InvalidCatalogYamlError(f"catalog YAML cannot be represented safely: {label}") from error
    try:
        return model.model_validate_json(json_payload)
    except ValidationError as error:
        raise InvalidCatalogModelError(f"catalog model validation failed: {label}") from error


def _safe_yaml_name(name: str) -> str | None:
    if not name.endswith(".yaml"):
        return None
    stem = name.removesuffix(".yaml")
    try:
        _canonical_id(stem, "filename")
    except ValueError:
        return None
    return stem if name == f"{stem}.yaml" else None


def _list_directory(directory_fd: int, label: str) -> tuple[str, ...]:
    try:
        names = os.listdir(directory_fd)
    except OSError as error:
        raise UnsafeCatalogPathError(f"unable to enumerate {label} safely") from error
    try:
        return tuple(sorted(names, key=lambda name: name.encode("utf-8")))
    except UnicodeEncodeError as error:
        raise UnsafeCatalogPathError(f"{label} contains a non-UTF-8 name") from error


def _definition_digest(spec: BenchmarkSpec) -> str:
    return canonical_sha256(
        spec.model_dump(mode="json"),
        schema_version=_DEFINITION_SCHEMA,
        digest_field=None,
    )


def _load_canonical_catalog(root_fd: int) -> dict[str, BenchmarkSpec]:
    catalog_fd = _open_child_directory(root_fd, "catalog", "canonical catalog")
    with _managed_descriptor(catalog_fd, "canonical catalog"):
        names = _list_directory(catalog_fd, "canonical catalog")
        if "canonical_ids.yaml" not in names:
            raise UnsafeCatalogPathError("required catalog file is missing: catalog/canonical_ids.yaml")
        definition_names: list[tuple[str, str]] = []
        for name in names:
            if name == "canonical_ids.yaml":
                continue
            stem = _safe_yaml_name(name)
            if stem is None:
                raise UnsafeCatalogPathError(f"unsafe canonical catalog entry: {name!r}")
            definition_names.append((name, stem))

        registry_payload = _read_file_at(
            catalog_fd,
            "canonical_ids.yaml",
            "catalog/canonical_ids.yaml",
        )
        assert registry_payload is not None
        registry = _parse_model(
            registry_payload,
            CanonicalIdRegistry,
            "catalog/canonical_ids.yaml",
        )
        definitions: dict[str, BenchmarkSpec] = {}
        for name, stem in definition_names:
            payload = _read_file_at(catalog_fd, name, f"catalog/{name}")
            assert payload is not None
            spec = _parse_model(payload, BenchmarkSpec, f"catalog/{name}")
            if spec.id != stem:
                raise CatalogRegistryMismatchError(
                    f"canonical filename/model ID mismatch: {stem}, {spec.id}"
                )
            definitions[spec.id] = spec

        registry_ids = tuple(entry.id for entry in registry.entries)
        registered = set(registry_ids)
        discovered = set(definitions)
        if registered != discovered:
            missing = sorted(registered - discovered, key=lambda item: item.encode("utf-8"))
            unregistered = sorted(discovered - registered, key=lambda item: item.encode("utf-8"))
            details: list[str] = []
            if missing:
                details.append(f"missing definitions: {', '.join(missing)}")
            if unregistered:
                details.append(f"unregistered definitions: {', '.join(unregistered)}")
            raise CatalogRegistryMismatchError("canonical registry mismatch: " + "; ".join(details))

        for entry in registry.entries:
            actual = _definition_digest(definitions[entry.id])
            if actual != entry.definition_sha256:
                raise CatalogRegistryMismatchError(
                    f"canonical definition digest mismatch: {entry.id}"
                )
        return definitions


def _resolve_shared_root(shared_root: Path | None) -> Path:
    if shared_root is not None:
        return _require_path(shared_root, "shared root")
    if _ENVIRONMENT_ROOT in os.environ:
        value = os.environ[_ENVIRONMENT_ROOT]
        if value == "":
            raise UnsafeCatalogPathError(f"{_ENVIRONMENT_ROOT} must not be empty")
        return Path(value)
    return _require_path(_benchmarks.resolve_data_root(), "repository shared root")


@contextmanager
def _open_fallback_directories(
    paths: Sequence[Path],
    kind: str,
) -> Iterator[tuple[tuple[Path, int], ...]]:
    if isinstance(paths, (str, bytes)) or not isinstance(paths, Sequence):
        raise UnsafeCatalogPathError(f"fallback {kind} directories must be a sequence of Path values")
    opened: list[tuple[Path, int]] = []
    identities: set[tuple[int, int]] = set()
    primary: BaseException | None = None
    try:
        for index, raw_path in enumerate(paths, start=1):
            path = _require_path(raw_path, f"fallback {kind} directory {index}")
            descriptor = _open_directory_path(path, f"fallback {kind} directory {index}")
            opened.append((path, descriptor))
            status = os.fstat(descriptor)
            identity = (status.st_dev, status.st_ino)
            if identity in identities:
                raise DuplicateCatalogDefinitionError(
                    f"duplicate fallback {kind} directory identity"
                )
            identities.add(identity)
        yield tuple(opened)
    except BaseException as error:
        primary = error
        raise
    finally:
        close_error = primary
        for _, descriptor in reversed(opened):
            try:
                _close_descriptor(
                    descriptor,
                    f"fallback {kind} directory",
                    close_error,
                )
            except BaseException as error:
                close_error = error
        if primary is None and close_error is not None:
            raise close_error


def _load_fallback_catalog(opened: tuple[tuple[Path, int], ...]) -> dict[str, BenchmarkSpec]:
    discovered: list[tuple[str, BenchmarkSpec]] = []
    for directory_index, (_, directory_fd) in enumerate(opened, start=1):
        for name in _list_directory(directory_fd, f"fallback catalog directory {directory_index}"):
            stem = _safe_yaml_name(name)
            if stem is None:
                raise UnsafeCatalogPathError(f"unsafe fallback catalog entry: {name!r}")
            payload = _read_file_at(
                directory_fd,
                name,
                f"fallback catalog {directory_index}/{name}",
            )
            assert payload is not None
            spec = _parse_model(
                payload,
                BenchmarkSpec,
                f"fallback catalog {directory_index}/{name}",
            )
            discovered.append((stem, spec))

    definitions: dict[str, BenchmarkSpec] = {}
    for _, spec in discovered:
        if spec.id in definitions:
            raise DuplicateCatalogDefinitionError(
                f"duplicate fallback benchmark definition: {spec.id}"
            )
        definitions[spec.id] = spec
    for stem, spec in discovered:
        if spec.id != stem:
            raise InvalidCatalogModelError(
                f"fallback filename/model ID mismatch: {stem}, {spec.id}"
            )
    return definitions


def get_benchmark(
    benchmark_id: str,
    *,
    shared_root: Path | None = None,
    fallback_catalog_dirs: Sequence[Path] = (),
) -> BenchmarkSpec:
    """Load one benchmark after fully validating the canonical registry."""

    benchmark_id = _validate_requested_identifier(benchmark_id, "benchmark ID")
    root = _resolve_shared_root(shared_root)
    root_fd = _open_directory_path(root, "shared root")
    with _managed_descriptor(root_fd, "shared root"):
        canonical = _load_canonical_catalog(root_fd)
    with _open_fallback_directories(fallback_catalog_dirs, "catalog") as fallbacks:
        if benchmark_id in canonical:
            return canonical[benchmark_id]
        fallback_catalog = _load_fallback_catalog(fallbacks)
        fallback = fallback_catalog[benchmark_id] if benchmark_id in fallback_catalog else None
    if fallback is None:
        raise BenchmarkNotFoundError(f"benchmark not found: {benchmark_id}")
    return fallback


def list_benchmarks(
    *,
    shared_root: Path | None = None,
    fallback_catalog_dirs: Sequence[Path] = (),
) -> tuple[BenchmarkSpec, ...]:
    """Return the deterministic merged canonical-wins benchmark view."""

    root = _resolve_shared_root(shared_root)
    root_fd = _open_directory_path(root, "shared root")
    with _managed_descriptor(root_fd, "shared root"):
        canonical = _load_canonical_catalog(root_fd)
    with _open_fallback_directories(fallback_catalog_dirs, "catalog") as fallbacks:
        merged = _load_fallback_catalog(fallbacks)
    merged.update(canonical)
    return tuple(merged[identifier] for identifier in sorted(merged, key=lambda item: item.encode("utf-8")))


def _load_fallback_packs(
    opened: tuple[tuple[Path, int], ...],
) -> dict[str, tuple[Path, BenchmarkPack]]:
    discovered: list[tuple[str, Path, BenchmarkPack]] = []
    for directory_index, (directory, directory_fd) in enumerate(opened, start=1):
        for name in _list_directory(directory_fd, f"fallback pack directory {directory_index}"):
            stem = _safe_yaml_name(name)
            if stem is None:
                raise UnsafeCatalogPathError(f"unsafe fallback pack entry: {name!r}")
            label = f"fallback pack {directory_index}/{name}"
            payload = _read_file_at(directory_fd, name, label)
            assert payload is not None
            pack = _parse_model(payload, BenchmarkPack, label)
            discovered.append((stem, directory / name, pack))

    packs: dict[str, tuple[Path, BenchmarkPack]] = {}
    for _, path, pack in discovered:
        if pack.pack_name in packs:
            raise DuplicateCatalogDefinitionError(
                f"duplicate fallback pack definition: {pack.pack_name}"
            )
        packs[pack.pack_name] = (path, pack)
    for stem, _, pack in discovered:
        if pack.pack_name != stem:
            raise InvalidCatalogModelError(
                f"pack filename/model name mismatch: {stem}, {pack.pack_name}"
            )
    return packs


def _select_pack(
    pack_name: str,
    *,
    shared_root: Path | None,
    fallback_pack_dirs: Sequence[Path],
) -> tuple[Path, BenchmarkPack]:
    root = _resolve_shared_root(shared_root)
    filename = f"{pack_name}.yaml"
    with _open_fallback_directories(fallback_pack_dirs, "pack") as fallbacks:
        root_fd = _open_directory_path(root, "shared root")
        with _managed_descriptor(root_fd, "shared root"):
            suites_fd = _open_child_directory(root_fd, "suites", "canonical suites directory")
            with _managed_descriptor(suites_fd, "canonical suites directory"):
                parity_fd = _open_child_directory(
                    suites_fd,
                    "parity",
                    "canonical parity directory",
                )
                with _managed_descriptor(parity_fd, "canonical parity directory"):
                    canonical_payload = _read_file_at(
                        parity_fd,
                        filename,
                        f"suites/parity/{filename}",
                        optional=True,
                    )
        if canonical_payload is not None:
            pack = _parse_model(
                canonical_payload,
                BenchmarkPack,
                f"suites/parity/{filename}",
            )
            if pack.pack_name != pack_name:
                raise InvalidCatalogModelError(
                    f"pack filename/model name mismatch: {pack_name}, {pack.pack_name}"
                )
            return root / "suites" / "parity" / filename, pack

        fallback_packs = _load_fallback_packs(fallbacks)
        selected = fallback_packs[pack_name] if pack_name in fallback_packs else None
        if selected is None:
            raise PackNotFoundError(f"pack not found: {pack_name}")
        return selected


def resolve_pack_path(
    pack_name: str,
    *,
    shared_root: Path | None = None,
    fallback_pack_dirs: Sequence[Path] = (),
) -> Path:
    """Return the validated lexical pack path; use load_parity_pack to read it safely."""

    pack_name = _validate_requested_identifier(pack_name, "pack name")
    path, _ = _select_pack(
        pack_name,
        shared_root=shared_root,
        fallback_pack_dirs=fallback_pack_dirs,
    )
    return path


def load_parity_pack(
    pack_name: str,
    *,
    shared_root: Path | None = None,
    fallback_pack_dirs: Sequence[Path] = (),
    fallback_catalog_dirs: Sequence[Path] = (),
) -> BenchmarkPack:
    """Freshly load a parity pack and validate every benchmark reference."""

    pack_name = _validate_requested_identifier(pack_name, "pack name")
    _, pack = _select_pack(
        pack_name,
        shared_root=shared_root,
        fallback_pack_dirs=fallback_pack_dirs,
    )
    available = {
        benchmark.id
        for benchmark in list_benchmarks(
            shared_root=shared_root,
            fallback_catalog_dirs=fallback_catalog_dirs,
        )
    }
    unknown = sorted(
        set(pack.benchmarks) - available,
        key=lambda item: item.encode("utf-8"),
    )
    if unknown:
        raise UnknownPackBenchmarkError(
            f"pack references unknown benchmarks: {', '.join(unknown)}"
        )
    return pack


__all__ = [
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
]
