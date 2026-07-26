"""Existence, size, and checksum validation for byte-level LM dataset caches.

Only the manifest is version controlled; the payload it describes is warmed
locally and must be proven to match before any LM claim may cite it. Path access
mirrors the frozen catalog loaders, so a symlink planted anywhere along a cache
root cannot redirect a read outside the tree that was named.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum
import errno
import hashlib
import os
from pathlib import Path
import re
import stat
from typing import Literal

from pydantic import Field, field_validator, model_validator

from . import benchmarks as _benchmarks
from .budgets import ContractModel, _canonical_id, _utf8_sorted_unique
from .catalog import (
    CatalogError,
    _close_descriptor,
    _directory_flags,
    _file_flags,
    _list_directory,
    _managed_descriptor,
    _parse_model,
    _read_file_at,
    _require_path,
    _require_platform_support,
    _safe_yaml_name,
)

LM_CACHE_SCHEMA_VERSION = "1.0.0"

_CACHE_DIRECTORY = "lm_cache"
_ENVIRONMENT_ROOT = "EVONN_LM_CACHE_DIR"
_MANIFEST_SUFFIX = ".yaml"
_READ_CHUNK_BYTES = 1024 * 1024
_MAX_PATH_BYTES = 512
_MAX_PATH_COMPONENTS = 8
_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,127}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class LmCacheDefect(StrEnum):
    MISSING = "missing"
    NOT_REGULAR_FILE = "not_regular_file"
    UNREADABLE = "unreadable"
    SIZE_MISMATCH = "size_mismatch"
    CHECKSUM_MISMATCH = "checksum_mismatch"


class LmCacheError(ValueError):
    """Base class for deterministic LM cache errors."""

    code = "lm_cache_error"


class UnsafeLmCachePathError(LmCacheError):
    code = "unsafe_lm_cache_path"


class InvalidLmCacheManifestError(LmCacheError):
    code = "invalid_lm_cache_manifest"


class LmCacheNotFoundError(LmCacheError):
    code = "lm_cache_not_found"


class LmCacheIdMismatchError(LmCacheError):
    code = "lm_cache_id_mismatch"


def _cache_relative_path(value: str, field_name: str) -> str:
    if len(value.encode("utf-8")) > _MAX_PATH_BYTES:
        raise ValueError(f"{field_name} must be at most {_MAX_PATH_BYTES} UTF-8 bytes")
    components = value.split("/")
    if not 1 <= len(components) <= _MAX_PATH_COMPONENTS:
        raise ValueError(f"{field_name} must have between 1 and {_MAX_PATH_COMPONENTS} components")
    for component in components:
        if _SAFE_COMPONENT.fullmatch(component) is None:
            raise ValueError(f"{field_name} components must be safe relative names")
    return value


class LmCacheArtifact(ContractModel):
    """One payload file a warmed cache must contain, byte for byte."""

    path: str
    size_bytes: int = Field(ge=0)
    sha256: str

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        return _cache_relative_path(value, "path")

    @field_validator("sha256")
    @classmethod
    def _validate_sha256(cls, value: str) -> str:
        if _SHA256_PATTERN.fullmatch(value) is None:
            raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
        return value


class LmCacheManifest(ContractModel):
    """The version-controlled description of one real LM dataset cache."""

    schema_version: Literal["1.0.0"]
    cache_id: str
    benchmark_ids: tuple[str, ...]
    artifacts: tuple[LmCacheArtifact, ...]

    @field_validator("cache_id")
    @classmethod
    def _validate_cache_id(cls, value: str) -> str:
        return _canonical_id(value, "cache_id")

    @field_validator("benchmark_ids")
    @classmethod
    def _validate_benchmark_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("benchmark_ids must not be empty")
        for benchmark_id in value:
            _canonical_id(benchmark_id, "benchmark_ids")
        return _utf8_sorted_unique(value, "benchmark_ids")

    @model_validator(mode="after")
    def _validate_artifacts(self) -> LmCacheManifest:
        if not self.artifacts:
            raise ValueError("artifacts must not be empty")
        paths = tuple(artifact.path for artifact in self.artifacts)
        _utf8_sorted_unique(paths, "artifacts")
        return self


class LmCacheFinding(ContractModel):
    """One artifact that does not match the manifest, with both observations."""

    path: str
    defect: LmCacheDefect
    expected: str
    observed: str


class LmCacheReport(ContractModel):
    """The verification outcome for one cache against one payload root."""

    cache_id: str
    checksums_verified: bool
    artifacts_checked: int = Field(ge=0)
    findings: tuple[LmCacheFinding, ...]

    @property
    def valid(self) -> bool:
        return not self.findings


def _translate(error: CatalogError) -> UnsafeLmCachePathError:
    """Re-raise a reused catalog path failure under the LM cache taxonomy."""

    return UnsafeLmCachePathError(str(error).replace("catalog", "LM cache"))


def _errno_name(error: OSError) -> str:
    """Name a failed read by errno symbol, which strerror does not do stably."""

    if error.errno is None:
        return "unknown_error"
    return errno.errorcode[error.errno] if error.errno in errno.errorcode else f"errno_{error.errno}"


def _require_cache_platform_support() -> None:
    """Fail loudly where no-follow descriptor access is unavailable.

    Without this the platform failure would surface as a failed root open and
    be misreported as an unwarmed cache.
    """

    try:
        _require_platform_support()
    except CatalogError as error:
        raise UnsafeLmCachePathError("descriptor-relative no-follow LM cache access is unsupported") from error


def _require_cache_path(value: object, label: str) -> Path:
    try:
        return _require_path(value, label)
    except CatalogError as error:
        raise _translate(error) from error


def _resolve_manifest_root(manifest_root: Path | None) -> Path:
    if manifest_root is not None:
        return _require_cache_path(manifest_root, "LM cache manifest root")
    return _require_cache_path(_benchmarks.resolve_data_root(), "repository shared root") / _CACHE_DIRECTORY


def _resolve_payload_root(payload_root: Path | None, manifest_root: Path | None) -> Path:
    if payload_root is not None:
        return _require_cache_path(payload_root, "LM cache payload root")
    if _ENVIRONMENT_ROOT in os.environ:
        value = os.environ[_ENVIRONMENT_ROOT]
        if value == "":
            raise UnsafeLmCachePathError(f"{_ENVIRONMENT_ROOT} must not be empty")
        return Path(value)
    return _resolve_manifest_root(manifest_root)


def _open_directory_chain(base_fd: int, components: tuple[str, ...], label: str) -> int:
    """Walk a relative directory chain, one no-follow descriptor at a time.

    Unlike the catalog helper this lets the ``OSError`` escape unwrapped. A
    cache that was never warmed and a cache whose directory was replaced by a
    symlink must not produce the same finding, and only the errno separates
    them.
    """

    descriptor = os.dup(base_fd)
    try:
        for component in components:
            child = os.open(component, _directory_flags(), dir_fd=descriptor)
            try:
                status = os.fstat(child)
                if not stat.S_ISDIR(status.st_mode):
                    raise NotADirectoryError(errno.ENOTDIR, os.strerror(errno.ENOTDIR), component)
            except BaseException as error:
                _close_descriptor(child, label, error)
                raise
            retired, descriptor = descriptor, -1
            try:
                _close_descriptor(retired, label)
            except BaseException as error:
                _close_descriptor(child, label, error)
                raise
            descriptor = child
        return descriptor
    except BaseException as error:
        if descriptor >= 0:
            _close_descriptor(descriptor, label, error)
        raise


def _open_root_path(path: Path, label: str) -> int:
    """Open a cache root from its anchor down, following no symlink on the way."""

    resolved = _require_cache_path(path, label)
    if resolved.is_absolute():
        anchor, parts = resolved.anchor, resolved.parts[1:]
    else:
        anchor, parts = ".", resolved.parts
    components = tuple(part for part in parts if part not in ("", "."))
    base = os.open(anchor, _directory_flags())
    primary: BaseException | None = None
    try:
        return _open_directory_chain(base, components, label)
    except BaseException as error:
        primary = error
        raise
    finally:
        _close_descriptor(base, label, primary)


@contextmanager
def _open_root(path: Path, label: str) -> Iterator[int]:
    try:
        descriptor = _open_root_path(path, label)
    except OSError as error:
        raise UnsafeLmCachePathError(f"unable to open {label} safely") from error
    with _managed_descriptor(descriptor, label) as opened:
        yield opened


def list_lm_caches(*, manifest_root: Path | None = None) -> tuple[str, ...]:
    """List the cache identifiers declared by manifests, in UTF-8 order."""

    root = _resolve_manifest_root(manifest_root)
    with _open_root(root, "LM cache manifest root") as root_fd:
        try:
            names = _list_directory(root_fd, "LM cache manifest root")
        except CatalogError as error:
            raise _translate(error) from error
        identifiers: list[str] = []
        for name in names:
            if not name.endswith(_MANIFEST_SUFFIX):
                continue
            stem = _safe_yaml_name(name)
            if stem is None:
                raise UnsafeLmCachePathError(f"unsafe LM cache manifest entry: {name!r}")
            identifiers.append(stem)
    return tuple(identifiers)


def load_lm_cache_manifest(cache_id: str, *, manifest_root: Path | None = None) -> LmCacheManifest:
    """Load and validate one manifest, requiring its filename to match its id."""

    if type(cache_id) is not str:
        raise LmCacheNotFoundError("cache_id must be a string")
    try:
        _canonical_id(cache_id, "cache_id")
    except ValueError as error:
        raise LmCacheNotFoundError("cache_id must be a canonical lowercase snake-case identifier") from error

    root = _resolve_manifest_root(manifest_root)
    filename = f"{cache_id}{_MANIFEST_SUFFIX}"
    with _open_root(root, "LM cache manifest root") as root_fd:
        try:
            payload = _read_file_at(root_fd, filename, filename, optional=True)
        except CatalogError as error:
            raise _translate(error) from error
        if payload is None:
            raise LmCacheNotFoundError(f"unknown LM cache: {cache_id}")
        try:
            manifest = _parse_model(payload, LmCacheManifest, filename)
        except CatalogError as error:
            raise InvalidLmCacheManifestError(f"LM cache manifest is invalid: {filename}") from error

    if manifest.cache_id != cache_id:
        raise LmCacheIdMismatchError(
            f"LM cache manifest declares {manifest.cache_id!r} but is stored as {filename!r}"
        )
    return manifest


def _hash_descriptor(descriptor: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    while True:
        chunk = os.read(descriptor, _READ_CHUNK_BYTES)
        if not chunk:
            break
        digest.update(chunk)
        total += len(chunk)
    return digest.hexdigest(), total


def _inspect_artifact(
    root_fd: int,
    artifact: LmCacheArtifact,
    *,
    verify_checksums: bool,
) -> LmCacheFinding | None:
    *directories, filename = artifact.path.split("/")
    label = f"LM cache artifact {artifact.path}"
    try:
        directory_fd = _open_directory_chain(root_fd, tuple(directories), label)
    except FileNotFoundError:
        return LmCacheFinding(
            path=artifact.path,
            defect=LmCacheDefect.MISSING,
            expected="present",
            observed="missing",
        )
    except OSError as error:
        return LmCacheFinding(
            path=artifact.path,
            defect=LmCacheDefect.UNREADABLE,
            expected="readable regular file",
            observed=_errno_name(error),
        )

    with _managed_descriptor(directory_fd, label):
        try:
            descriptor = os.open(filename, _file_flags(), dir_fd=directory_fd)
        except FileNotFoundError:
            return LmCacheFinding(
                path=artifact.path,
                defect=LmCacheDefect.MISSING,
                expected="present",
                observed="missing",
            )
        except OSError as error:
            return LmCacheFinding(
                path=artifact.path,
                defect=LmCacheDefect.UNREADABLE,
                expected="readable regular file",
                observed=_errno_name(error),
            )

        with _managed_descriptor(descriptor, label):
            try:
                status = os.fstat(descriptor)
            except OSError as error:
                return LmCacheFinding(
                    path=artifact.path,
                    defect=LmCacheDefect.UNREADABLE,
                    expected="readable regular file",
                    observed=_errno_name(error),
                )
            if not stat.S_ISREG(status.st_mode):
                return LmCacheFinding(
                    path=artifact.path,
                    defect=LmCacheDefect.NOT_REGULAR_FILE,
                    expected="regular file",
                    observed=stat.filemode(status.st_mode),
                )
            if status.st_size != artifact.size_bytes:
                return LmCacheFinding(
                    path=artifact.path,
                    defect=LmCacheDefect.SIZE_MISMATCH,
                    expected=str(artifact.size_bytes),
                    observed=str(status.st_size),
                )
            if not verify_checksums:
                return None
            try:
                observed_digest, read_bytes = _hash_descriptor(descriptor)
            except OSError as error:
                return LmCacheFinding(
                    path=artifact.path,
                    defect=LmCacheDefect.UNREADABLE,
                    expected="readable regular file",
                    observed=_errno_name(error),
                )

    # A cache warmed by a concurrent writer can shrink or grow between the stat
    # and the read, so the byte count that was actually hashed decides the size
    # verdict rather than the earlier stat.
    if read_bytes != artifact.size_bytes:
        return LmCacheFinding(
            path=artifact.path,
            defect=LmCacheDefect.SIZE_MISMATCH,
            expected=str(artifact.size_bytes),
            observed=str(read_bytes),
        )
    if observed_digest != artifact.sha256:
        return LmCacheFinding(
            path=artifact.path,
            defect=LmCacheDefect.CHECKSUM_MISMATCH,
            expected=artifact.sha256,
            observed=observed_digest,
        )
    return None


def verify_lm_cache(
    manifest: LmCacheManifest,
    *,
    payload_root: Path | None = None,
    manifest_root: Path | None = None,
    verify_checksums: bool = True,
) -> LmCacheReport:
    """Verify a warmed cache against its manifest and report every mismatch.

    Existence and size are always checked. Checksums are checked unless
    ``verify_checksums`` is false, which exists for cheap pre-flight checks over
    multi-gigabyte caches — never for evidence that backs an LM claim.
    """

    if not isinstance(manifest, LmCacheManifest):
        raise InvalidLmCacheManifestError("manifest must be an LmCacheManifest")
    _require_cache_platform_support()

    root = _resolve_payload_root(payload_root, manifest_root)
    findings: list[LmCacheFinding] = []
    label = "LM cache payload root"
    try:
        root_fd = _open_root_path(root, label)
    except FileNotFoundError:
        # An unwarmed cache has no payload root at all. That is an ordinary
        # "not warmed yet" answer for the caller, not a path-safety failure, so
        # it is reported as every artifact missing rather than raised.
        #
        # Only ENOENT is read that way. A no-follow open of a symlinked
        # directory raises ENOTDIR on macOS and ELOOP on Linux, so widening this
        # to any plausible-looking errno would give the two hosts different
        # verdicts for one planted symlink.
        findings = [
            LmCacheFinding(
                path=artifact.path,
                defect=LmCacheDefect.MISSING,
                expected="present",
                observed="missing",
            )
            for artifact in manifest.artifacts
        ]
    except OSError as error:
        raise UnsafeLmCachePathError(f"unable to open {label} safely") from error
    else:
        with _managed_descriptor(root_fd, label):
            for artifact in manifest.artifacts:
                finding = _inspect_artifact(root_fd, artifact, verify_checksums=verify_checksums)
                if finding is not None:
                    findings.append(finding)

    return LmCacheReport(
        cache_id=manifest.cache_id,
        checksums_verified=verify_checksums,
        artifacts_checked=len(manifest.artifacts),
        findings=tuple(findings),
    )


def validate_lm_cache(
    cache_id: str,
    *,
    payload_root: Path | None = None,
    manifest_root: Path | None = None,
    verify_checksums: bool = True,
) -> LmCacheReport:
    """Load a manifest by id and verify the warmed cache behind it."""

    manifest = load_lm_cache_manifest(cache_id, manifest_root=manifest_root)
    return verify_lm_cache(
        manifest,
        payload_root=payload_root,
        manifest_root=manifest_root,
        verify_checksums=verify_checksums,
    )


__all__ = [
    "LM_CACHE_SCHEMA_VERSION",
    "LmCacheArtifact",
    "LmCacheDefect",
    "LmCacheError",
    "LmCacheFinding",
    "LmCacheIdMismatchError",
    "LmCacheManifest",
    "LmCacheNotFoundError",
    "LmCacheReport",
    "InvalidLmCacheManifestError",
    "UnsafeLmCachePathError",
    "list_lm_caches",
    "load_lm_cache_manifest",
    "validate_lm_cache",
    "verify_lm_cache",
]
