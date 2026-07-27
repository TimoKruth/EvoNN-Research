"""Per-run DuckDB store with single-writer ownership and append-only evidence.

Ownership is decided by an exclusive advisory lock on ``run.lock``, never by
reading the lock record. The kernel releases an advisory lock when the holding
process dies, so acquiring it is proof that no live writer exists; a PID or a
hostname in a file proves nothing, since PIDs are recycled and records outlive
the processes that wrote them. The record exists to say *who* held the lock and
to make a recovered stale lock visible, not to decide the question.

Evaluation rows are append-only and hash-chained: each row's digest covers its
own content and the digest of the row before it, so editing, reordering or
removing an interior row is detectable. A chain alone cannot catch a truncated
tail — a shorter chain is still a valid chain — so the expected length and tip
are also recorded in the ``runs`` row, outside the chain they describe.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import socket
import stat
import sys
from typing import Any, Final, Literal
import uuid

import duckdb
from pydantic import Field, field_validator

from .budgets import ContractModel, _canonical_id, _human_text, _run_id
from .canonical import canonical_sha256

RUN_STORE_SCHEMA_VERSION: Final = "1.0.0"
STORE_FILENAME: Final = "metrics.duckdb"
LOCK_FILENAME: Final = "run.lock"

_EVALUATION_DOMAIN: Final = "evonn.run_store.evaluation/v1"
_GENESIS_DIGEST: Final = "0" * 64
_MAX_LOCK_RECORD_BYTES: Final = 64 * 1024

# One token per process, so a recycled PID never looks like the same writer.
_PROCESS_TOKEN: Final = uuid.uuid4().hex


class RunStoreError(ValueError):
    """Base class for deterministic run store errors."""

    code = "run_store_error"


class RunStoreLockedError(RunStoreError):
    code = "run_store_locked"


class RunStoreNotFoundError(RunStoreError):
    code = "run_store_not_found"


class RunStoreExistsError(RunStoreError):
    code = "run_store_exists"


class RunIdentityError(RunStoreError):
    code = "run_identity"


class EvaluationChainError(RunStoreError):
    code = "evaluation_chain"


class LockOwner(ContractModel):
    """Who holds the writer lock. Diagnostic only — the lock itself is truth."""

    host: str
    platform: str
    pid: int = Field(ge=0)
    process_token: str

    @field_validator("host", "platform")
    @classmethod
    def _validate_text(cls, value: str, info: Any) -> str:
        return _human_text(value, info.field_name)

    @field_validator("process_token")
    @classmethod
    def _validate_token(cls, value: str) -> str:
        if len(value) != 32 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("process_token must be 32 lowercase hexadecimal characters")
        return value


class RunRecord(ContractModel):
    """Run identity plus the evidence tip that makes truncation detectable."""

    schema_version: Literal["1.0.0"]
    run_id: str
    evaluation_count: int = Field(ge=0)
    evaluation_tip_sha256: str

    @field_validator("run_id")
    @classmethod
    def _validate_run_id(cls, value: str) -> str:
        return _run_id(value)

    @field_validator("evaluation_tip_sha256")
    @classmethod
    def _validate_tip(cls, value: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("evaluation_tip_sha256 must be 64 lowercase hexadecimal characters")
        return value


class EvaluationRow(ContractModel):
    """One immutable evaluation observation, chained to its predecessor."""

    sequence: int = Field(ge=0)
    benchmark_id: str
    contender_id: str
    metric_name: str
    metric_value: float
    previous_sha256: str
    row_sha256: str

    @field_validator("benchmark_id", "contender_id", "metric_name")
    @classmethod
    def _validate_identifier(cls, value: str, info: Any) -> str:
        return _canonical_id(value, info.field_name)


class ArtifactRow(ContractModel):
    """A run-relative artifact reference with the digest that proves its bytes."""

    path: str
    size_bytes: int = Field(ge=0)
    sha256: str

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        if value.startswith("/") or ".." in value.split("/") or not value:
            raise ValueError("path must be a nonempty run-relative path")
        return _human_text(value, "path")

    @field_validator("sha256")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
        return value


def _evaluation_digest(
    *,
    sequence: int,
    benchmark_id: str,
    contender_id: str,
    metric_name: str,
    metric_value: float,
    previous_sha256: str,
) -> str:
    return canonical_sha256(
        {
            "benchmark_id": benchmark_id,
            "contender_id": contender_id,
            "metric_name": metric_name,
            "metric_value": metric_value,
            "previous_sha256": previous_sha256,
            "sequence": sequence,
        },
        schema_version=_EVALUATION_DOMAIN,
        digest_field=None,
    )


def _require_path(value: object, label: str) -> Path:
    if type(value) is not type(Path()):
        raise RunStoreError(f"{label} must be a concrete pathlib.Path")
    return value


def _local_owner() -> LockOwner:
    return LockOwner(
        host=socket.gethostname() or "unknown-host",
        platform=sys.platform,
        pid=os.getpid(),
        process_token=_PROCESS_TOKEN,
    )


class RunStore:
    """A single-writer per-run metrics store.

    Instances are produced by :func:`open_run_store` and are only valid inside
    that context manager, which holds the writer lock for their whole lifetime.
    """

    def __init__(self, connection: duckdb.DuckDBPyConnection, run_id: str, recovered_stale_lock: bool) -> None:
        self._connection = connection
        self._run_id = run_id
        self._recovered_stale_lock = recovered_stale_lock

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def recovered_stale_lock(self) -> bool:
        """True when this writer took over a lock a dead process left behind."""

        return self._recovered_stale_lock

    def append_evaluation(
        self,
        benchmark_id: str,
        contender_id: str,
        metric_name: str,
        metric_value: float,
    ) -> EvaluationRow:
        """Append one evaluation, chaining it to the current last row."""

        if type(metric_value) is not float:
            raise RunStoreError("metric_value must be an exact float")
        rows = self._connection.execute(
            "SELECT sequence, row_sha256 FROM evaluations ORDER BY sequence DESC LIMIT 1"
        ).fetchall()
        if rows:
            sequence, previous_sha256 = int(rows[0][0]) + 1, str(rows[0][1])
        else:
            sequence, previous_sha256 = 0, _GENESIS_DIGEST
        row = EvaluationRow(
            sequence=sequence,
            benchmark_id=_canonical_id(benchmark_id, "benchmark_id"),
            contender_id=_canonical_id(contender_id, "contender_id"),
            metric_name=_canonical_id(metric_name, "metric_name"),
            metric_value=metric_value,
            previous_sha256=previous_sha256,
            row_sha256=_evaluation_digest(
                sequence=sequence,
                benchmark_id=benchmark_id,
                contender_id=contender_id,
                metric_name=metric_name,
                metric_value=metric_value,
                previous_sha256=previous_sha256,
            ),
        )
        self._connection.execute(
            "INSERT INTO evaluations VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                row.sequence,
                row.benchmark_id,
                row.contender_id,
                row.metric_name,
                row.metric_value,
                row.previous_sha256,
                row.row_sha256,
            ],
        )
        # The tip lives outside the chain on purpose. A hash chain proves nobody
        # edited, reordered or removed an interior row, but a truncated chain is
        # still a valid chain, so the expected length and tip must be recorded
        # somewhere the chain does not reach.
        self._connection.execute(
            "UPDATE runs SET evaluation_count = ?, evaluation_tip_sha256 = ?",
            [sequence + 1, row.row_sha256],
        )
        return row

    def evaluations(self) -> tuple[EvaluationRow, ...]:
        rows = self._connection.execute(
            "SELECT sequence, benchmark_id, contender_id, metric_name, metric_value,"
            " previous_sha256, row_sha256 FROM evaluations ORDER BY sequence"
        ).fetchall()
        return tuple(
            EvaluationRow(
                sequence=int(row[0]),
                benchmark_id=str(row[1]),
                contender_id=str(row[2]),
                metric_name=str(row[3]),
                metric_value=float(row[4]),
                previous_sha256=str(row[5]),
                row_sha256=str(row[6]),
            )
            for row in rows
        )

    def verify_evaluation_chain(self) -> int:
        """Prove no evaluation row was edited, reordered, added or removed."""

        record = self.run()
        expected_previous = _GENESIS_DIGEST
        count = 0
        for index, row in enumerate(self.evaluations()):
            if row.sequence != index:
                raise EvaluationChainError(
                    f"evaluation sequence {row.sequence} is out of order at position {index}"
                )
            if row.previous_sha256 != expected_previous:
                raise EvaluationChainError(
                    f"evaluation {row.sequence} does not chain to its predecessor"
                )
            recomputed = _evaluation_digest(
                sequence=row.sequence,
                benchmark_id=row.benchmark_id,
                contender_id=row.contender_id,
                metric_name=row.metric_name,
                metric_value=row.metric_value,
                previous_sha256=row.previous_sha256,
            )
            if recomputed != row.row_sha256:
                raise EvaluationChainError(f"evaluation {row.sequence} content does not match its digest")
            expected_previous = row.row_sha256
            count += 1
        if count != record.evaluation_count:
            raise EvaluationChainError(
                f"run store holds {count} evaluations, the run record expects {record.evaluation_count}"
            )
        if expected_previous != record.evaluation_tip_sha256:
            raise EvaluationChainError("evaluation chain tip does not match the run record")
        return count

    def record_artifact(self, path: str, size_bytes: int, sha256: str) -> ArtifactRow:
        artifact = ArtifactRow(path=path, size_bytes=size_bytes, sha256=sha256)
        self._connection.execute(
            "INSERT OR REPLACE INTO artifacts VALUES (?, ?, ?)",
            [artifact.path, artifact.size_bytes, artifact.sha256],
        )
        return artifact

    def artifacts(self) -> tuple[ArtifactRow, ...]:
        rows = self._connection.execute(
            "SELECT path, size_bytes, sha256 FROM artifacts ORDER BY path"
        ).fetchall()
        return tuple(
            ArtifactRow(path=str(row[0]), size_bytes=int(row[1]), sha256=str(row[2])) for row in rows
        )

    def set_metadata(self, key: str, value: str) -> None:
        self._connection.execute(
            "INSERT OR REPLACE INTO metadata VALUES (?, ?)",
            [_canonical_id(key, "key"), _human_text(value, "value")],
        )

    def metadata(self) -> Mapping[str, str]:
        rows = self._connection.execute("SELECT key, value FROM metadata ORDER BY key").fetchall()
        return {str(row[0]): str(row[1]) for row in rows}

    def run(self) -> RunRecord:
        rows = self._connection.execute(
            "SELECT schema_version, run_id, evaluation_count, evaluation_tip_sha256 FROM runs"
        ).fetchall()
        if len(rows) != 1:
            raise RunIdentityError(f"run store must describe exactly one run, found {len(rows)}")
        return RunRecord(
            schema_version=str(rows[0][0]),
            run_id=str(rows[0][1]),
            evaluation_count=int(rows[0][2]),
            evaluation_tip_sha256=str(rows[0][3]),
        )


_SCHEMA_STATEMENTS: Final = (
    "CREATE TABLE runs ("
    " schema_version TEXT NOT NULL,"
    " run_id TEXT NOT NULL PRIMARY KEY,"
    " evaluation_count BIGINT NOT NULL,"
    " evaluation_tip_sha256 TEXT NOT NULL)",
    "CREATE TABLE evaluations ("
    " sequence BIGINT NOT NULL PRIMARY KEY,"
    " benchmark_id TEXT NOT NULL,"
    " contender_id TEXT NOT NULL,"
    " metric_name TEXT NOT NULL,"
    " metric_value DOUBLE NOT NULL,"
    " previous_sha256 TEXT NOT NULL,"
    " row_sha256 TEXT NOT NULL UNIQUE)",
    "CREATE TABLE artifacts ("
    " path TEXT NOT NULL PRIMARY KEY,"
    " size_bytes BIGINT NOT NULL,"
    " sha256 TEXT NOT NULL)",
    "CREATE TABLE metadata (key TEXT NOT NULL PRIMARY KEY, value TEXT NOT NULL)",
)


def _acquire_writer_lock(directory: Path) -> tuple[int, bool]:
    """Take the exclusive writer lock, reporting whether it was stale.

    Returns the held descriptor. The caller owns it until release.
    """

    lock_path = directory / LOCK_FILENAME
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise RunStoreError("run lock is not a regular file")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RunStoreLockedError(
                f"another writer holds the run lock: {_describe_lock_holder(descriptor)}"
            ) from error
        # Reaching here means no live process held the lock. A record left in
        # the file therefore belonged to a process that died without releasing
        # it, which is exactly the stale case the caller may want to know about.
        stale = os.fstat(descriptor).st_size > 0
        record = _local_owner().model_dump_json().encode("utf-8") + b"\n"
        os.ftruncate(descriptor, 0)
        os.lseek(descriptor, 0, os.SEEK_SET)
        os.write(descriptor, record)
        os.fsync(descriptor)
        return descriptor, stale
    except BaseException:
        os.close(descriptor)
        raise


def _describe_lock_holder(descriptor: int) -> str:
    try:
        os.lseek(descriptor, 0, os.SEEK_SET)
        payload = os.read(descriptor, _MAX_LOCK_RECORD_BYTES)
    except OSError:
        return "owner unknown"
    if not payload:
        return "owner unrecorded"
    try:
        owner = LockOwner.model_validate_json(payload)
    except ValueError:
        return "owner unreadable"
    return f"host={owner.host} pid={owner.pid} process={owner.process_token}"


def read_lock_owner(directory: Path) -> LockOwner | None:
    """Read the recorded lock owner. This never implies the lock is held."""

    resolved = _require_path(directory, "run directory")
    try:
        payload = (resolved / LOCK_FILENAME).read_bytes()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise RunStoreError("unable to read the run lock record") from error
    if not payload:
        return None
    try:
        return LockOwner.model_validate_json(payload)
    except ValueError as error:
        raise RunStoreError("run lock record is invalid") from error


def _release_writer_lock(descriptor: int) -> None:
    try:
        os.ftruncate(descriptor, 0)
        os.fsync(descriptor)
        fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


@contextmanager
def open_run_store(directory: Path, run_id: str, *, create: bool = False) -> Iterator[RunStore]:
    """Open the run store for writing, holding the writer lock throughout.

    Exactly one process at a time may hold this. A second attempt raises
    :class:`RunStoreLockedError` rather than waiting, because a blocked writer
    is a design error here, not a queue.
    """

    resolved = _require_path(directory, "run directory")
    identifier = _run_id(run_id)
    if not resolved.is_dir():
        raise RunStoreNotFoundError(f"run directory does not exist: {resolved}")
    store_path = resolved / STORE_FILENAME
    exists = store_path.exists()
    if create and exists:
        raise RunStoreExistsError(f"run store already exists: {store_path}")
    if not create and not exists:
        raise RunStoreNotFoundError(f"run store does not exist: {store_path}")

    descriptor, stale = _acquire_writer_lock(resolved)
    connection: duckdb.DuckDBPyConnection | None = None
    try:
        connection = duckdb.connect(str(store_path))
        if create:
            for statement in _SCHEMA_STATEMENTS:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?)",
                [RUN_STORE_SCHEMA_VERSION, identifier, 0, _GENESIS_DIGEST],
            )
        store = RunStore(connection, identifier, stale)
        recorded = store.run()
        if recorded.run_id != identifier:
            raise RunIdentityError(
                f"run store belongs to run {recorded.run_id!r}, not {identifier!r}"
            )
        if recorded.schema_version != RUN_STORE_SCHEMA_VERSION:
            raise RunIdentityError(
                f"run store schema version is {recorded.schema_version!r},"
                f" expected {RUN_STORE_SCHEMA_VERSION!r}"
            )
        yield store
    finally:
        if connection is not None:
            connection.close()
        _release_writer_lock(descriptor)


__all__ = [
    "LOCK_FILENAME",
    "RUN_STORE_SCHEMA_VERSION",
    "STORE_FILENAME",
    "ArtifactRow",
    "EvaluationChainError",
    "EvaluationRow",
    "LockOwner",
    "RunIdentityError",
    "RunRecord",
    "RunStore",
    "RunStoreError",
    "RunStoreExistsError",
    "RunStoreLockedError",
    "RunStoreNotFoundError",
    "open_run_store",
    "read_lock_owner",
]
