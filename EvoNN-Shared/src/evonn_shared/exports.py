"""Frozen run-export documents and atomic deterministic publication."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable
import ctypes
import errno
from enum import StrEnum
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .budgets import BudgetAccounting, BudgetDeclaration, ContractModel, _canonical_id, _human_text, _run_id
from .canonical import sha256_bytes
from .telemetry import (
    AggregateMetric,
    ArtifactReference,
    BenchmarkResult,
    BestResult,
    Coverage,
    FairnessFlag,
    MetricDirection,
    ResultStatus,
    RuntimeMetadata,
    SeedingMetadata,
    SystemId,
    RunTiming,
)

EXPORT_SCHEMA_VERSION = "1.0.0"
MANIFEST_FILENAME = "manifest.json"
RESULTS_FILENAME = "results.json"
SUMMARY_FILENAME = "summary.json"

_GIT_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_EXPORT_FILENAMES = (MANIFEST_FILENAME, RESULTS_FILENAME, SUMMARY_FILENAME)


class RunStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    RESUMED = "resumed"
    CANCELLED = "cancelled"


class RunClass(StrEnum):
    SMOKE = "smoke"
    LOCAL = "local"
    OVERNIGHT = "overnight"
    WEEKEND = "weekend"
    SPECIAL_STUDY = "special-study"


class _RunIdentity(ContractModel):
    schema_version: Literal["1.0.0"]
    system: SystemId
    run_id: str
    pack_id: str
    seed: int = Field(ge=0, lt=2**256)

    @field_validator("run_id")
    @classmethod
    def _validate_run_id(cls, value: str) -> str:
        return _run_id(value)

    @field_validator("pack_id")
    @classmethod
    def _validate_pack_id(cls, value: str) -> str:
        return _canonical_id(value, "pack_id")


class Manifest(_RunIdentity):
    run_class: RunClass
    status: RunStatus
    status_reason: str | None
    lab_spec_version: str
    git_commit: str
    timing: RunTiming
    budget: BudgetDeclaration
    accounting: BudgetAccounting
    runtime: RuntimeMetadata
    seeding: SeedingMetadata
    config_snapshot: ArtifactReference
    report_markdown: ArtifactReference
    artifacts: tuple[ArtifactReference, ...]

    @field_validator("lab_spec_version")
    @classmethod
    def _validate_spec_version(cls, value: str) -> str:
        return _human_text(value, "lab_spec_version")

    @field_validator("git_commit")
    @classmethod
    def _validate_git_commit(cls, value: str) -> str:
        if _GIT_COMMIT_PATTERN.fullmatch(value) is None:
            raise ValueError("git_commit must be exactly 40 lowercase hex characters")
        return value

    @field_validator("status_reason")
    @classmethod
    def _validate_reason(cls, value: str | None) -> str | None:
        return None if value is None else _human_text(value, "status_reason")

    @model_validator(mode="after")
    def _validate_manifest(self) -> Manifest:
        _validate_document_echoes(self)
        _validate_status_reason(self.status, self.status_reason)
        _validate_sorted_artifacts(self.artifacts, "artifacts")
        paths = (self.config_snapshot.path, self.report_markdown.path) + tuple(item.path for item in self.artifacts)
        if len(paths) != len(set(paths)):
            raise ValueError("manifest artifact paths must be globally unique")
        return self


class Results(_RunIdentity):
    budget: BudgetDeclaration
    accounting: BudgetAccounting
    runtime: RuntimeMetadata
    seeding: SeedingMetadata
    records: tuple[BenchmarkResult, ...]
    coverage: Coverage

    @model_validator(mode="after")
    def _validate_results(self) -> Results:
        _validate_document_echoes(self)
        _validate_results_records(self)
        return self


class RunSummary(_RunIdentity):
    status: RunStatus
    status_reason: str | None
    timing: RunTiming
    budget: BudgetDeclaration
    accounting: BudgetAccounting
    runtime: RuntimeMetadata
    seeding: SeedingMetadata
    coverage: Coverage
    best_per_benchmark: tuple[BestResult, ...]
    aggregates: tuple[AggregateMetric, ...]
    fairness_flags: tuple[FairnessFlag, ...]
    artifact_digests: tuple[ArtifactReference, ...]

    @field_validator("status_reason")
    @classmethod
    def _validate_reason(cls, value: str | None) -> str | None:
        return None if value is None else _human_text(value, "status_reason")

    @model_validator(mode="after")
    def _validate_summary(self) -> RunSummary:
        _validate_document_echoes(self)
        _validate_status_reason(self.status, self.status_reason)
        if self.coverage.benchmark_count != self.budget.benchmark_surface.benchmark_count:
            raise ValueError("summary coverage must equal the declared benchmark count")
        _validate_sorted_unique(self.best_per_benchmark, lambda item: item.benchmark_id, "best_per_benchmark")
        _validate_sorted_unique(self.aggregates, lambda item: item.name, "aggregates")
        _validate_sorted_unique(self.fairness_flags, lambda item: item.code, "fairness_flags")
        _validate_sorted_artifacts(self.artifact_digests, "artifact_digests")
        return self


class ExportDigests(ContractModel):
    manifest_sha256: str
    results_sha256: str
    summary_sha256: str

    @field_validator("manifest_sha256", "results_sha256", "summary_sha256")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        if _SHA256_PATTERN.fullmatch(value) is None:
            raise ValueError("export digests must be lowercase SHA-256 values")
        return value


def _validate_document_echoes(document: Any) -> None:
    if document.pack_id != document.budget.benchmark_surface.pack_id:
        raise ValueError("top-level pack_id must equal the budget pack_id")
    if document.budget.evaluation.total != document.accounting.evaluation_count:
        raise ValueError("declared evaluation total must equal the accounting envelope")
    if document.runtime.worker_topology.worker_count != document.budget.hardware.worker_count:
        raise ValueError("runtime worker count must equal the declared hardware worker count")
    if document.runtime.device_class != document.budget.hardware.device_class:
        raise ValueError("runtime device class must equal the declared hardware device class")


def _validate_status_reason(status: RunStatus, reason: str | None) -> None:
    if status is RunStatus.COMPLETED:
        if reason is not None:
            raise ValueError("completed runs must have null status_reason")
    elif reason is None:
        raise ValueError("non-completed runs require status_reason")


def _utf8_key(value: str) -> bytes:
    return value.encode("utf-8")


def _validate_sorted_unique(items: tuple[Any, ...], key: Callable[[Any], str], field_name: str) -> None:
    keys = tuple(key(item) for item in items)
    if keys != tuple(sorted(keys, key=_utf8_key)):
        raise ValueError(f"{field_name} must be UTF-8 sorted")
    if len(keys) != len(set(keys)):
        raise ValueError(f"{field_name} must not contain duplicate keys")


def _validate_sorted_artifacts(items: tuple[ArtifactReference, ...], field_name: str) -> None:
    _validate_sorted_unique(items, lambda item: item.path, field_name)


def _validate_results_records(results: Results) -> None:
    keys = tuple((record.benchmark_id, record.outcome_id) for record in results.records)
    ordered = tuple(sorted(keys, key=lambda key: (_utf8_key(key[0]), _utf8_key(key[1]))))
    if keys != ordered:
        raise ValueError("records must be UTF-8 sorted by benchmark and outcome")
    if len(keys) != len(set(keys)):
        raise ValueError("records must be unique by benchmark and outcome")

    counts = Counter(record.status for record in results.records)
    expected = {
        ResultStatus.OK: results.coverage.ok,
        ResultStatus.FAILED: results.coverage.failed,
        ResultStatus.SKIPPED: results.coverage.skipped,
        ResultStatus.UNSUPPORTED: results.coverage.unsupported,
    }
    if len(results.records) != results.coverage.result_count or any(counts[status] != count for status, count in expected.items()):
        raise ValueError("coverage must exactly match the visible records")
    distinct_benchmarks = len({record.benchmark_id for record in results.records})
    if results.coverage.benchmark_count != distinct_benchmarks:
        raise ValueError("coverage benchmark_count must equal distinct visible benchmarks")
    if results.coverage.benchmark_count != results.budget.benchmark_surface.benchmark_count:
        raise ValueError("coverage benchmark_count must equal the declared benchmark count")
    if sum(record.evaluation_count for record in results.records) != results.accounting.actual_evaluations:
        raise ValueError("record evaluation counts must sum to actual_evaluations")

    semantics: dict[str, tuple[object, str, MetricDirection]] = {}
    for record in results.records:
        current = (record.task_kind, record.metric.name, record.metric.direction)
        if record.benchmark_id not in semantics:
            semantics[record.benchmark_id] = current
        elif current != semantics[record.benchmark_id]:
            raise ValueError("all outcomes for a benchmark must share task and metric semantics")


def _derive_best(records: tuple[BenchmarkResult, ...]) -> tuple[BestResult, ...]:
    grouped: dict[str, list[BenchmarkResult]] = defaultdict(list)
    for record in records:
        if record.status is ResultStatus.OK:
            grouped[record.benchmark_id].append(record)
    best: list[BestResult] = []
    for benchmark_id in sorted(grouped, key=_utf8_key):
        candidates = grouped[benchmark_id]
        direction = candidates[0].metric.direction
        candidates.sort(key=lambda item: _utf8_key(item.outcome_id))
        if direction is MetricDirection.MAX:
            selected = max(candidates, key=lambda item: item.metric.value)
        else:
            selected = min(candidates, key=lambda item: item.metric.value)
        if selected.metric.value is None:
            raise AssertionError("ok result validation guarantees a metric value")
        best.append(
            BestResult(
                benchmark_id=selected.benchmark_id,
                outcome_id=selected.outcome_id,
                metric_name=selected.metric.name,
                direction=selected.metric.direction,
                value=selected.metric.value,
            )
        )
    return tuple(best)


def _manifest_artifact_union(manifest: Manifest) -> tuple[ArtifactReference, ...]:
    return tuple(
        sorted(
            (manifest.config_snapshot, manifest.report_markdown, *manifest.artifacts),
            key=lambda item: _utf8_key(item.path),
        )
    )


def _require_three_equal(label: str, first: object, second: object, third: object) -> None:
    if first != second or first != third:
        raise ValueError(f"cross-file {label} mismatch")


def _validate_cross_file(manifest: Manifest, results: Results, summary: RunSummary) -> None:
    _require_three_equal("system", manifest.system, results.system, summary.system)
    _require_three_equal("run_id", manifest.run_id, results.run_id, summary.run_id)
    _require_three_equal("pack_id", manifest.pack_id, results.pack_id, summary.pack_id)
    _require_three_equal("seed", manifest.seed, results.seed, summary.seed)
    _require_three_equal("budget", manifest.budget, results.budget, summary.budget)
    _require_three_equal("accounting", manifest.accounting, results.accounting, summary.accounting)
    _require_three_equal("runtime", manifest.runtime, results.runtime, summary.runtime)
    _require_three_equal("seeding", manifest.seeding, results.seeding, summary.seeding)
    if manifest.status != summary.status:
        raise ValueError("manifest/summary status mismatch")
    if manifest.status_reason != summary.status_reason:
        raise ValueError("manifest/summary status_reason mismatch")
    if manifest.timing != summary.timing:
        raise ValueError("manifest/summary timing mismatch")
    if results.coverage != summary.coverage:
        raise ValueError("results/summary coverage mismatch")
    if summary.best_per_benchmark != _derive_best(results.records):
        raise ValueError("summary best results do not match result derivation")
    if summary.artifact_digests != _manifest_artifact_union(manifest):
        raise ValueError("summary artifact digests do not match the manifest union")


def _serialize_document(document: ContractModel) -> bytes:
    payload = document.model_dump(mode="json")
    text = json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
    return text.encode("utf-8") + b"\n"


def _load_exclusive_rename() -> Callable[[int, str, str], None]:
    library = ctypes.CDLL(None, use_errno=True)
    if sys.platform.startswith("linux"):
        try:
            rename = library.renameat2
        except AttributeError as error:
            raise OSError(errno.ENOSYS, "renameat2 is unavailable") from error
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        flag = 1
    elif sys.platform == "darwin":
        try:
            rename = library.renameatx_np
        except AttributeError as error:
            raise OSError(errno.ENOSYS, "renameatx_np is unavailable") from error
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        flag = 0x00000004
    else:
        raise OSError(errno.ENOTSUP, f"exclusive directory publication is unsupported on {sys.platform}")

    def exclusive_rename(parent_fd: int, source_name: str, destination_name: str) -> None:
        result = rename(
            parent_fd,
            os.fsencode(source_name),
            parent_fd,
            os.fsencode(destination_name),
            flag,
        )
        if result == 0:
            return
        error_number = ctypes.get_errno()
        if error_number in (errno.EEXIST, errno.ENOTEMPTY):
            raise FileExistsError(error_number, os.strerror(error_number), destination_name)
        raise OSError(error_number, os.strerror(error_number), destination_name)

    return exclusive_rename


def _record_error(
    primary: BaseException | None,
    error: BaseException,
    context: str,
) -> BaseException:
    if primary is None:
        return error
    primary.add_note(f"{context}: {error!r}")
    return primary


def _descriptor_matches_status(
    descriptor: int,
    original_status: os.stat_result,
    primary: BaseException | None,
    context: str,
) -> tuple[bool | None, BaseException | None]:
    try:
        current_status = os.fstat(descriptor)
    except OSError as error:
        if error.errno == errno.EBADF:
            return False, primary
        return None, _record_error(primary, error, f"{context} identity check failed")
    except BaseException as error:
        return None, _record_error(primary, error, f"{context} identity check failed")
    if _same_file_identity(original_status, current_status):
        return True, primary
    if primary is not None:
        primary.add_note(f"{context}: descriptor {descriptor} was reused; fallback close skipped")
    return False, primary


def _close_descriptor(descriptor: int) -> None:
    os.close(descriptor)


def _close_owned_descriptor(
    descriptor: int,
    primary: BaseException | None,
    context: str,
) -> tuple[bool, BaseException | None]:
    original_status: os.stat_result | None = None
    try:
        original_status = os.fstat(descriptor)
    except OSError as error:
        if error.errno == errno.EBADF:
            return True, primary
        primary = _record_error(primary, error, f"{context} identity capture failed")
    except BaseException as error:
        primary = _record_error(primary, error, f"{context} identity capture failed")

    try:
        _close_descriptor(descriptor)
    except BaseException as error:
        primary = _record_error(primary, error, context)
    else:
        return True, primary

    if original_status is not None:
        matches, primary = _descriptor_matches_status(descriptor, original_status, primary, context)
        if matches is False:
            return True, primary
        if matches is True:
            try:
                os.close(descriptor)
            except BaseException as error:
                primary = _record_error(primary, error, f"{context} direct fallback failed")
            else:
                return True, primary
            matches, primary = _descriptor_matches_status(descriptor, original_status, primary, context)
            if matches is False:
                return True, primary

    leak_error = OSError(errno.EIO, f"{context} left descriptor {descriptor} ownership unresolved")
    primary = _record_error(primary, leak_error, context)
    return False, primary


def _open_file_at(directory_fd: int, filename: str) -> int:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(filename, flags, 0o600, dir_fd=directory_fd)
    primary: BaseException | None = None
    try:
        os.fchmod(descriptor, 0o600)
        if stat.S_IMODE(os.fstat(descriptor).st_mode) != 0o600:
            raise OSError(errno.EIO, f"failed to establish exact mode 0600 for {filename}")
        return descriptor
    except BaseException as error:
        primary = error
    closed, primary = _close_owned_descriptor(descriptor, primary, f"{filename} open cleanup")
    if not closed:
        primary.add_note(f"descriptor {descriptor} remains owned after failed file setup")
    raise primary


def _write_all(file: Any, payload: bytes) -> None:
    remaining = memoryview(payload)
    while remaining:
        written = file.write(remaining)
        if written is None or written <= 0:
            raise OSError(errno.EIO, "file write made no progress")
        remaining = remaining[written:]


def _flush_file(file: Any) -> None:
    file.flush()


def _fsync_file(file: Any) -> None:
    os.fsync(file.fileno())


def _close_file(file: Any) -> None:
    file.close()


def _close_owned_file(
    file: Any,
    descriptor: int,
    primary: BaseException | None,
) -> tuple[bool, BaseException | None]:
    original_status: os.stat_result | None = None
    try:
        original_status = os.fstat(descriptor)
    except OSError as error:
        if error.errno == errno.EBADF:
            return True, primary
        primary = _record_error(primary, error, "file close identity capture failed")
    except BaseException as error:
        primary = _record_error(primary, error, "file close identity capture failed")

    try:
        _close_file(file)
    except BaseException as error:
        primary = _record_error(primary, error, "file close failed")
    else:
        return True, primary

    if file.closed:
        return True, primary
    if original_status is not None:
        matches, primary = _descriptor_matches_status(descriptor, original_status, primary, "file close failed")
        if matches is False:
            return True, primary
        if matches is True:
            try:
                file.close()
            except BaseException as error:
                primary = _record_error(primary, error, "direct file-object close fallback failed")
            else:
                return True, primary
            if file.closed:
                return True, primary
            matches, primary = _descriptor_matches_status(descriptor, original_status, primary, "file close fallback")
            if matches is False:
                return True, primary
            if matches is True:
                try:
                    os.close(descriptor)
                except BaseException as error:
                    primary = _record_error(primary, error, "raw file descriptor fallback failed")
                else:
                    return True, primary
                matches, primary = _descriptor_matches_status(
                    descriptor,
                    original_status,
                    primary,
                    "raw file descriptor fallback",
                )
                if matches is False:
                    return True, primary

    leak_error = OSError(errno.EIO, f"file close left descriptor {descriptor} ownership unresolved")
    primary = _record_error(primary, leak_error, "file close failed")
    return False, primary


def _write_file_at(directory_fd: int, filename: str, payload: bytes) -> None:
    descriptor = _open_file_at(directory_fd, filename)
    file = None
    primary: BaseException | None = None
    try:
        file = os.fdopen(descriptor, "wb", buffering=0)
        _write_all(file, payload)
        _flush_file(file)
        _fsync_file(file)
    except BaseException as error:
        primary = error

    if file is not None:
        closed, primary = _close_owned_file(file, descriptor, primary)
        if closed:
            descriptor = -1
        file = None
    else:
        closed, primary = _close_owned_descriptor(descriptor, primary, f"{filename} fdopen cleanup")
        if closed:
            descriptor = -1
    if descriptor >= 0:
        primary = _record_error(
            primary,
            OSError(errno.EIO, f"descriptor {descriptor} remains open"),
            f"{filename} ownership failure",
        )
    if primary is not None:
        raise primary


def _fsync_directory_fd(directory_fd: int) -> None:
    os.fsync(directory_fd)


def _same_file_identity(first: os.stat_result, second: os.stat_result) -> bool:
    return (first.st_dev, first.st_ino) == (second.st_dev, second.st_ino)


def _staging_name_matches_fd(parent_fd: int, staging_name: str, staging_fd: int) -> bool:
    owned_status = os.fstat(staging_fd)
    try:
        named_status = os.stat(staging_name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return _same_file_identity(owned_status, named_status)


def _cleanup_staging(
    parent_fd: int,
    staging_name: str,
    staging_fd: int | None,
    created_status: os.stat_result | None,
    primary: BaseException,
) -> bool:
    if staging_fd is None:
        if created_status is None:
            primary.add_note(
                "staging descriptor and created identity were unavailable; no name-based cleanup "
                "was attempted"
            )
            return False
        try:
            named_status = os.stat(staging_name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return True
        except BaseException as error:
            primary.add_note(f"staging cleanup identity check failed: {error!r}")
            return False
        if not _same_file_identity(created_status, named_status):
            primary.add_note(
                "staging descriptor was not verified and the source name no longer identifies the "
                "created directory; replacement was preserved and an externally renamed empty "
                "owned staging directory may require operator cleanup"
            )
            return False
        try:
            os.rmdir(staging_name, dir_fd=parent_fd)
        except FileNotFoundError:
            return True
        except BaseException as error:
            primary.add_note(f"staging cleanup failed: {error!r}")
            return False
        return True

    for filename in _EXPORT_FILENAMES:
        try:
            os.unlink(filename, dir_fd=staging_fd)
        except FileNotFoundError:
            pass
        except BaseException as error:
            primary.add_note(f"staging cleanup failed: {error!r}")

    try:
        source_matches = _staging_name_matches_fd(parent_fd, staging_name, staging_fd)
    except BaseException as error:
        source_matches = False
        primary.add_note(f"staging cleanup identity check failed: {error!r}")
    if source_matches:
        try:
            os.rmdir(staging_name, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        except BaseException as error:
            primary.add_note(f"staging cleanup failed: {error!r}")
    else:
        primary.add_note(
            "staging source name no longer identifies the owned directory; "
            "replacement was preserved and an externally renamed empty owned staging directory "
            "may require operator cleanup"
        )

    closed, _ = _close_owned_descriptor(staging_fd, primary, "staging cleanup close failed")
    return closed


def _validate_destination(directory: object) -> tuple[Path, str]:
    if type(directory) is not type(Path()):
        raise TypeError("directory must be a concrete pathlib.Path")
    if directory.name in ("", ".", ".."):
        raise ValueError("directory must have a normal final name")
    return directory.parent, directory.name


def _validate_parent_status(status: os.stat_result, parent: Path) -> None:
    if stat.S_ISLNK(status.st_mode) or not stat.S_ISDIR(status.st_mode):
        raise NotADirectoryError(errno.ENOTDIR, "export parent must be a real directory", parent)
    if status.st_uid != os.geteuid():
        raise PermissionError(errno.EPERM, "export parent must be owned by the effective UID", parent)
    if status.st_mode & 0o022:
        raise PermissionError(errno.EPERM, "export parent must not be writable by group or others", parent)


def write_export(
    directory: Path,
    manifest: Manifest,
    results: Results,
    summary: RunSummary,
) -> ExportDigests:
    """Validate and atomically publish the three deterministic run-export files."""

    if type(manifest) is not Manifest or type(results) is not Results or type(summary) is not RunSummary:
        raise TypeError("write_export requires exact Manifest, Results, and RunSummary instances")
    manifest = Manifest.model_validate(manifest.model_dump())
    results = Results.model_validate(results.model_dump())
    summary = RunSummary.model_validate(summary.model_dump())
    _validate_cross_file(manifest, results, summary)
    payloads = {
        MANIFEST_FILENAME: _serialize_document(manifest),
        RESULTS_FILENAME: _serialize_document(results),
        SUMMARY_FILENAME: _serialize_document(summary),
    }
    digests = ExportDigests(
        manifest_sha256=sha256_bytes(payloads[MANIFEST_FILENAME]),
        results_sha256=sha256_bytes(payloads[RESULTS_FILENAME]),
        summary_sha256=sha256_bytes(payloads[SUMMARY_FILENAME]),
    )
    parent, destination_name = _validate_destination(directory)
    exclusive_rename = _load_exclusive_rename()

    parent_status = os.lstat(parent)
    _validate_parent_status(parent_status, parent)

    parent_flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_DIRECTORY"):
        parent_flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        parent_flags |= os.O_NOFOLLOW
    parent_fd: int | None = os.open(parent, parent_flags)
    staging_name = f".{destination_name}.tmp-{secrets.token_hex(16)}"
    staging_fd: int | None = None
    created_status: os.stat_result | None = None
    staging_owned = False
    staging_verified = False
    published = False
    try:
        opened_parent_status = os.fstat(parent_fd)
        _validate_parent_status(opened_parent_status, parent)
        if not _same_file_identity(parent_status, opened_parent_status):
            raise OSError(errno.ESTALE, "export parent identity changed while opening", parent)

        try:
            os.stat(destination_name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise FileExistsError(errno.EEXIST, "export destination already exists", destination_name)

        os.mkdir(staging_name, 0o700, dir_fd=parent_fd)
        staging_owned = True
        created_status = os.stat(staging_name, dir_fd=parent_fd, follow_symlinks=False)
        os.chmod(staging_name, 0o700, dir_fd=parent_fd, follow_symlinks=False)
        staging_flags = os.O_RDONLY | os.O_CLOEXEC
        if hasattr(os, "O_DIRECTORY"):
            staging_flags |= os.O_DIRECTORY
        if hasattr(os, "O_NOFOLLOW"):
            staging_flags |= os.O_NOFOLLOW
        staging_fd = os.open(staging_name, staging_flags, dir_fd=parent_fd)
        opened_staging_status = os.fstat(staging_fd)
        named_staging_status = os.stat(staging_name, dir_fd=parent_fd, follow_symlinks=False)
        if not _same_file_identity(created_status, opened_staging_status) or not _same_file_identity(
            opened_staging_status, named_staging_status
        ):
            raise OSError(errno.ESTALE, "opened staging directory is not the created inode")
        staging_verified = True
        os.fchmod(staging_fd, 0o700)
        if stat.S_IMODE(os.fstat(staging_fd).st_mode) != 0o700:
            raise OSError(errno.EIO, "failed to establish exact staging mode 0700")

        for filename in _EXPORT_FILENAMES:
            _write_file_at(staging_fd, filename, payloads[filename])
        _fsync_directory_fd(staging_fd)

        if not _staging_name_matches_fd(parent_fd, staging_name, staging_fd):
            raise OSError(errno.ESTALE, "staging source identity mismatch before publication")
        exclusive_rename(parent_fd, staging_name, destination_name)
        staging_owned = False
        published = True

        post_publication_error: BaseException | None = None
        staging_closed, post_publication_error = _close_owned_descriptor(
            staging_fd,
            post_publication_error,
            "post-rename staging close failed",
        )
        if staging_closed:
            staging_fd = None
        try:
            _fsync_directory_fd(parent_fd)
        except BaseException as error:
            post_publication_error = _record_error(
                post_publication_error,
                error,
                "parent directory fsync failed after publication",
            )
        if post_publication_error is not None:
            raise post_publication_error
        return digests
    except BaseException as error:
        if staging_owned and not published:
            cleanup_fd = staging_fd if staging_verified else None
            staging_closed = _cleanup_staging(parent_fd, staging_name, cleanup_fd, created_status, error)
            if staging_closed:
                staging_fd = None
        raise
    finally:
        active_error = sys.exception()
        final_error: BaseException | None = active_error
        if staging_fd is not None:
            staging_closed, final_error = _close_owned_descriptor(
                staging_fd,
                final_error,
                "final staging descriptor close failed",
            )
            if staging_closed:
                staging_fd = None
        if parent_fd is not None:
            parent_closed, final_error = _close_owned_descriptor(
                parent_fd,
                final_error,
                "parent close failed",
            )
            if parent_closed:
                parent_fd = None
        if active_error is None and final_error is not None:
            raise final_error


__all__ = [
    "EXPORT_SCHEMA_VERSION",
    "MANIFEST_FILENAME",
    "RESULTS_FILENAME",
    "SUMMARY_FILENAME",
    "ExportDigests",
    "Manifest",
    "Results",
    "RunClass",
    "RunStatus",
    "RunSummary",
    "write_export",
]
