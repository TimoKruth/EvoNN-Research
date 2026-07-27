"""Crash-consistent publication of resumable engine checkpoints.

A checkpoint becomes authoritative at exactly one instant: the atomic
replacement of ``manifest.json``. Everything before that — staging the payload,
fsyncing it, renaming it into place — leaves the previously committed
checkpoint authoritative, so a crash at any transition resumes from the last
fully durable state rather than from a half-written one.

The publication is exposed as three separately callable steps rather than one
opaque call, so the crash boundaries the design depends on are the same
boundaries the tests drive.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
from typing import Literal

from pydantic import Field, field_validator

from .budgets import ContractModel, _canonical_id, _run_id
from .canonical import sha256_bytes
from .exports import (
    _close_owned_descriptor,
    _fsync_directory_fd,
    _load_exclusive_rename,
    _record_error,
    _same_file_identity,
    _write_file_at,
)

CHECKPOINT_SCHEMA_VERSION = "1.0.0"
MANIFEST_FILENAME = "manifest.json"

_PAYLOAD_SUFFIX = ".ckpt"
_MAX_MANIFEST_BYTES = 1024 * 1024
_READ_CHUNK_BYTES = 1024 * 1024
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class CheckpointError(ValueError):
    """Base class for deterministic checkpoint errors."""

    code = "checkpoint_error"


class UnsafeCheckpointPathError(CheckpointError):
    code = "unsafe_checkpoint_path"


class InvalidCheckpointManifestError(CheckpointError):
    code = "invalid_checkpoint_manifest"


class CheckpointNotFoundError(CheckpointError):
    code = "checkpoint_not_found"


class CorruptCheckpointError(CheckpointError):
    code = "corrupt_checkpoint"


class CheckpointSequenceError(CheckpointError):
    code = "checkpoint_sequence"


class CheckpointRecord(ContractModel):
    """The identity of one committed checkpoint payload."""

    checkpoint_id: str
    sequence: int = Field(ge=0)
    payload_path: str
    size_bytes: int = Field(ge=0)
    sha256: str
    previous_sha256: str | None

    @field_validator("checkpoint_id")
    @classmethod
    def _validate_checkpoint_id(cls, value: str) -> str:
        return _canonical_id(value, "checkpoint_id")

    @field_validator("payload_path")
    @classmethod
    def _validate_payload_path(cls, value: str) -> str:
        if not value.endswith(_PAYLOAD_SUFFIX):
            raise ValueError(f"payload_path must end in {_PAYLOAD_SUFFIX}")
        _canonical_id(value.removesuffix(_PAYLOAD_SUFFIX), "payload_path")
        return value

    @field_validator("sha256", "previous_sha256")
    @classmethod
    def _validate_digest(cls, value: str | None) -> str | None:
        if value is not None and _SHA256_PATTERN.fullmatch(value) is None:
            raise ValueError("digests must be 64 lowercase hexadecimal characters")
        return value


class CheckpointManifest(ContractModel):
    """The commit record naming the one authoritative checkpoint of a run."""

    schema_version: Literal["1.0.0"]
    run_id: str
    latest: CheckpointRecord

    @field_validator("run_id")
    @classmethod
    def _validate_run_id(cls, value: str) -> str:
        return _run_id(value)


def _require_directory(value: object, label: str) -> Path:
    if type(value) is not type(Path()):
        raise UnsafeCheckpointPathError(f"{label} must be a concrete pathlib.Path")
    return value


def _directory_flags() -> int:
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags


def _open_checkpoint_directory(directory: Path, label: str) -> int:
    resolved = _require_directory(directory, label)
    try:
        status = os.lstat(resolved)
    except OSError as error:
        raise UnsafeCheckpointPathError(f"unable to inspect {label} safely") from error
    if stat.S_ISLNK(status.st_mode):
        raise UnsafeCheckpointPathError(f"{label} must not be a symbolic link")
    try:
        descriptor = os.open(resolved, _directory_flags())
    except OSError as error:
        raise UnsafeCheckpointPathError(f"unable to open {label} safely") from error
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISDIR(opened.st_mode):
            raise UnsafeCheckpointPathError(f"{label} is not a directory")
        if not _same_file_identity(status, opened):
            raise UnsafeCheckpointPathError(f"{label} identity changed while opening")
        return descriptor
    except BaseException as error:
        raise _close_owned_descriptor(descriptor, error, f"{label} open cleanup") or error


def _open_file_at(directory_fd: int, filename: str, label: str) -> int | None:
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(filename, flags, dir_fd=directory_fd)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise UnsafeCheckpointPathError(f"unable to open {label} safely") from error
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise UnsafeCheckpointPathError(f"{label} is not a regular file")
        return descriptor
    except BaseException as error:
        raise _close_owned_descriptor(descriptor, error, f"{label} open cleanup") or error


def _read_file_at(directory_fd: int, filename: str, label: str, *, max_bytes: int | None = None) -> bytes | None:
    descriptor = _open_file_at(directory_fd, filename, label)
    if descriptor is None:
        return None
    primary: BaseException | None = None
    try:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, _READ_CHUNK_BYTES)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if max_bytes is not None and total > max_bytes:
                raise InvalidCheckpointManifestError(f"{label} exceeds its size limit")
        return b"".join(chunks)
    except BaseException as error:
        primary = error
        raise
    finally:
        closing = _close_owned_descriptor(descriptor, primary, f"{label} close")
        if primary is None and closing is not None:
            raise closing


def _digest_file_at(directory_fd: int, filename: str, label: str) -> tuple[str, int] | None:
    """Hash a file without holding it in memory, for payloads of any size."""

    descriptor = _open_file_at(directory_fd, filename, label)
    if descriptor is None:
        return None
    primary: BaseException | None = None
    try:
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(descriptor, _READ_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
        return digest.hexdigest(), total
    except BaseException as error:
        primary = error
        raise
    finally:
        closing = _close_owned_descriptor(descriptor, primary, f"{label} close")
        if primary is None and closing is not None:
            raise closing


def _serialize_manifest(manifest: CheckpointManifest) -> bytes:
    payload = manifest.model_dump(mode="json")
    text = json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
    return text.encode("utf-8") + b"\n"


def read_checkpoint_manifest(directory: Path) -> CheckpointManifest | None:
    """Return the committed manifest, or None when no checkpoint has committed."""

    label = "checkpoint directory"
    directory_fd = _open_checkpoint_directory(directory, label)
    primary: BaseException | None = None
    try:
        payload = _read_file_at(
            directory_fd,
            MANIFEST_FILENAME,
            "checkpoint manifest",
            max_bytes=_MAX_MANIFEST_BYTES,
        )
    except BaseException as error:
        primary = error
        raise
    finally:
        closing = _close_owned_descriptor(directory_fd, primary, f"{label} close")
        if primary is None and closing is not None:
            raise closing

    if payload is None:
        return None
    try:
        return CheckpointManifest.model_validate_json(payload)
    except ValueError as error:
        raise InvalidCheckpointManifestError("checkpoint manifest is invalid") from error


def load_latest_checkpoint(directory: Path) -> tuple[CheckpointRecord, bytes]:
    """Return the authoritative checkpoint, proving its bytes match the manifest."""

    manifest = read_checkpoint_manifest(directory)
    if manifest is None:
        raise CheckpointNotFoundError("no checkpoint has been committed")
    record = manifest.latest

    label = "checkpoint directory"
    directory_fd = _open_checkpoint_directory(directory, label)
    primary: BaseException | None = None
    try:
        payload = _read_file_at(directory_fd, record.payload_path, "checkpoint payload")
    except BaseException as error:
        primary = error
        raise
    finally:
        closing = _close_owned_descriptor(directory_fd, primary, f"{label} close")
        if primary is None and closing is not None:
            raise closing

    if payload is None:
        raise CorruptCheckpointError(f"committed checkpoint payload is missing: {record.payload_path}")
    if len(payload) != record.size_bytes:
        raise CorruptCheckpointError(
            f"committed checkpoint payload size is {len(payload)}, manifest declares {record.size_bytes}"
        )
    observed = hashlib.sha256(payload).hexdigest()
    if observed != record.sha256:
        raise CorruptCheckpointError(
            f"committed checkpoint payload digest is {observed}, manifest declares {record.sha256}"
        )
    return record, payload


class CheckpointPublication:
    """One checkpoint publication, advanced one durable step at a time.

    The three steps are separate because the crash boundaries between them are
    the guarantee. ``stage`` and ``commit_payload`` leave the previously
    committed checkpoint authoritative; only ``commit_manifest`` advances it.
    """

    def __init__(self, directory: Path, run_id: str, checkpoint_id: str, payload: bytes) -> None:
        if type(payload) is not bytes:
            raise TypeError("checkpoint payload must be bytes")
        self._directory = _require_directory(directory, "checkpoint directory")
        self._run_id = _run_id(run_id)
        self._checkpoint_id = _canonical_id(checkpoint_id, "checkpoint_id")
        self._payload = payload
        self._payload_path = f"{self._checkpoint_id}{_PAYLOAD_SUFFIX}"
        self._staging_name = f".{self._payload_path}.tmp-{secrets.token_hex(16)}"
        self._previous = read_checkpoint_manifest(directory)
        self._record = self._build_record()
        self._staged = False
        self._adopted = False
        self._payload_committed = False
        self._manifest_committed = False

    def _build_record(self) -> CheckpointRecord:
        if self._previous is None:
            sequence, previous_sha256 = 0, None
        else:
            previous = self._previous.latest
            if previous.checkpoint_id == self._checkpoint_id:
                raise CheckpointSequenceError(
                    f"checkpoint {self._checkpoint_id} is already the committed checkpoint"
                )
            if self._previous.run_id != self._run_id:
                raise CheckpointSequenceError(
                    f"checkpoint directory belongs to run {self._previous.run_id!r}, not {self._run_id!r}"
                )
            sequence, previous_sha256 = previous.sequence + 1, previous.sha256
        return CheckpointRecord(
            checkpoint_id=self._checkpoint_id,
            sequence=sequence,
            payload_path=self._payload_path,
            size_bytes=len(self._payload),
            sha256=sha256_bytes(self._payload),
            previous_sha256=previous_sha256,
        )

    @property
    def record(self) -> CheckpointRecord:
        return self._record

    def stage(self) -> None:
        """Write the payload durably under a staging name nothing reads."""

        if self._staged:
            raise CheckpointSequenceError("publication has already been staged")
        directory_fd = _open_checkpoint_directory(self._directory, "checkpoint directory")
        primary: BaseException | None = None
        try:
            existing = _digest_file_at(directory_fd, self._payload_path, "checkpoint payload")
            if existing is not None:
                # A crash between commit_payload and commit_manifest leaves an
                # uncommitted payload behind. Retrying the same checkpoint must
                # be able to finish it, so an identical payload is adopted; a
                # different one under the same id is a caller defect.
                if existing != (self._record.sha256, self._record.size_bytes):
                    raise CheckpointSequenceError(
                        f"checkpoint payload already exists with different bytes: {self._payload_path}"
                    )
                self._staged = True
                self._adopted = True
                self._payload_committed = True
                return
            _write_file_at(directory_fd, self._staging_name, self._payload)
            self._staged = True
        except BaseException as error:
            primary = error
            raise
        finally:
            closing = _close_owned_descriptor(directory_fd, primary, "staging close")
            if primary is None and closing is not None:
                raise closing

    def commit_payload(self) -> None:
        """Move the staged payload into place without touching the manifest.

        The payload is now durable and named, but no manifest references it, so
        the previously committed checkpoint is still the authoritative one.
        """

        if not self._staged:
            raise CheckpointSequenceError("publication has not been staged")
        if self._adopted:
            return
        if self._payload_committed:
            raise CheckpointSequenceError("payload has already been committed")
        exclusive_rename = _load_exclusive_rename()
        directory_fd = _open_checkpoint_directory(self._directory, "checkpoint directory")
        primary: BaseException | None = None
        try:
            exclusive_rename(directory_fd, self._staging_name, self._payload_path)
            self._payload_committed = True
            _fsync_directory_fd(directory_fd)
        except BaseException as error:
            primary = error
            raise
        finally:
            closing = _close_owned_descriptor(directory_fd, primary, "payload commit close")
            if primary is None and closing is not None:
                raise closing

    def commit_manifest(self) -> CheckpointRecord:
        """Replace the manifest, which is the instant the checkpoint commits."""

        if not self._payload_committed:
            raise CheckpointSequenceError("payload has not been committed")
        if self._manifest_committed:
            raise CheckpointSequenceError("manifest has already been committed")
        manifest = CheckpointManifest(
            schema_version=CHECKPOINT_SCHEMA_VERSION,
            run_id=self._run_id,
            latest=self._record,
        )
        if os.rename not in os.supports_dir_fd:
            raise UnsafeCheckpointPathError("descriptor-relative manifest replacement is unsupported")
        payload = _serialize_manifest(manifest)
        staging_name = f".{MANIFEST_FILENAME}.tmp-{secrets.token_hex(16)}"
        directory_fd = _open_checkpoint_directory(self._directory, "checkpoint directory")
        primary: BaseException | None = None
        try:
            _write_file_at(directory_fd, staging_name, payload)
            # A plain rename, not the exclusive one used for payloads: replacing
            # the manifest in a single step is exactly what makes the new
            # checkpoint authoritative, with no instant where none is.
            os.rename(
                staging_name,
                MANIFEST_FILENAME,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
            )
            self._manifest_committed = True
            _fsync_directory_fd(directory_fd)
            return self._record
        except BaseException as error:
            primary = error
            if not self._manifest_committed:
                try:
                    os.unlink(staging_name, dir_fd=directory_fd)
                except OSError as cleanup_error:
                    primary = _record_error(primary, cleanup_error, "manifest staging cleanup failed")
            raise primary
        finally:
            closing = _close_owned_descriptor(directory_fd, primary, "manifest commit close")
            if primary is None and closing is not None:
                raise closing


def publish_checkpoint(
    directory: Path,
    run_id: str,
    checkpoint_id: str,
    payload: bytes,
) -> CheckpointRecord:
    """Stage, commit, and make authoritative one checkpoint payload."""

    publication = CheckpointPublication(directory, run_id, checkpoint_id, payload)
    publication.stage()
    publication.commit_payload()
    return publication.commit_manifest()


def discard_orphaned_staging(directory: Path) -> tuple[str, ...]:
    """Remove staging files a crash left behind, in UTF-8 order.

    Staging names are never referenced by a manifest, so removing them cannot
    affect which checkpoint is authoritative.
    """

    label = "checkpoint directory"
    directory_fd = _open_checkpoint_directory(directory, label)
    primary: BaseException | None = None
    removed: list[str] = []
    try:
        names = sorted(os.listdir(directory_fd), key=lambda name: name.encode("utf-8"))
        for name in names:
            if not name.startswith(".") or ".tmp-" not in name:
                continue
            try:
                os.unlink(name, dir_fd=directory_fd)
            except FileNotFoundError:
                continue
            except OSError as error:
                raise UnsafeCheckpointPathError(f"unable to remove staging file: {name}") from error
            removed.append(name)
        if removed:
            _fsync_directory_fd(directory_fd)
        return tuple(removed)
    except BaseException as error:
        primary = error
        raise
    finally:
        closing = _close_owned_descriptor(directory_fd, primary, f"{label} close")
        if primary is None and closing is not None:
            raise closing


def create_checkpoint_directory(parent: Path, name: str = "checkpoints") -> Path:
    """Create an empty checkpoint directory, refusing to reuse an existing path."""

    resolved = _require_directory(parent, "checkpoint parent")
    _canonical_id(name.replace("-", "_"), "checkpoint directory name")
    directory_fd = _open_checkpoint_directory(resolved, "checkpoint parent")
    primary: BaseException | None = None
    try:
        try:
            os.mkdir(name, 0o700, dir_fd=directory_fd)
        except FileExistsError as error:
            raise UnsafeCheckpointPathError(f"checkpoint directory already exists: {name}") from error
        except OSError as error:
            raise UnsafeCheckpointPathError(f"unable to create checkpoint directory: {name}") from error
        _fsync_directory_fd(directory_fd)
        return resolved / name
    except BaseException as error:
        primary = error
        raise
    finally:
        closing = _close_owned_descriptor(directory_fd, primary, "checkpoint parent close")
        if primary is None and closing is not None:
            raise closing


__all__ = [
    "CHECKPOINT_SCHEMA_VERSION",
    "MANIFEST_FILENAME",
    "CheckpointError",
    "CheckpointManifest",
    "CheckpointNotFoundError",
    "CheckpointPublication",
    "CheckpointRecord",
    "CheckpointSequenceError",
    "CorruptCheckpointError",
    "InvalidCheckpointManifestError",
    "UnsafeCheckpointPathError",
    "create_checkpoint_directory",
    "discard_orphaned_staging",
    "load_latest_checkpoint",
    "publish_checkpoint",
    "read_checkpoint_manifest",
]
