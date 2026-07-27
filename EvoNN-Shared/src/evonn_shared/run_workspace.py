"""The canonical run directory: creation, validation, and rebuildable reports.

``report.md`` is derived, never authoritative. It is rebuilt byte-for-byte from
the run store, so a rebuild is a check on the evidence rather than an edit to
it: :func:`verify_artifact_references` reads the recorded artifacts and proves
their bytes still match without writing anything at all.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
from typing import Final
import unicodedata

from .run_store import STORE_FILENAME, ArtifactRow, RunStore
from .budgets import _run_id

CONFIG_FILENAME: Final = "config.yaml"
STATE_FILENAME: Final = "state.json"
SUMMARY_FILENAME: Final = "summary.json"
REPORT_FILENAME: Final = "report.md"
CHECKPOINT_DIRNAME: Final = "checkpoints"

CANONICAL_FILES: Final = (CONFIG_FILENAME, STORE_FILENAME, STATE_FILENAME, SUMMARY_FILENAME, REPORT_FILENAME)
CANONICAL_DIRECTORIES: Final = (CHECKPOINT_DIRNAME,)

_READ_CHUNK_BYTES: Final = 1024 * 1024


class RunWorkspaceError(ValueError):
    """Base class for deterministic run workspace errors."""

    code = "run_workspace_error"


class RunWorkspaceExistsError(RunWorkspaceError):
    code = "run_workspace_exists"


class RunWorkspaceNotFoundError(RunWorkspaceError):
    code = "run_workspace_not_found"


class InvalidRunWorkspaceError(RunWorkspaceError):
    code = "invalid_run_workspace"


def _require_path(value: object, label: str) -> Path:
    if type(value) is not type(Path()):
        raise RunWorkspaceError(f"{label} must be a concrete pathlib.Path")
    return value


class RunWorkspace:
    """One run's directory, with the canonical layout addressable by name."""

    def __init__(self, root: Path, run_id: str) -> None:
        self._root = _require_path(root, "run workspace root")
        self._run_id = _run_id(run_id)

    @property
    def root(self) -> Path:
        return self._root

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def config_path(self) -> Path:
        return self._root / CONFIG_FILENAME

    @property
    def store_path(self) -> Path:
        return self._root / STORE_FILENAME

    @property
    def state_path(self) -> Path:
        return self._root / STATE_FILENAME

    @property
    def summary_path(self) -> Path:
        return self._root / SUMMARY_FILENAME

    @property
    def report_path(self) -> Path:
        return self._root / REPORT_FILENAME

    @property
    def checkpoint_directory(self) -> Path:
        return self._root / CHECKPOINT_DIRNAME

    def find_violations(self) -> tuple[tuple[str, str], ...]:
        """Return deterministic (path, message) pairs for structural defects."""

        violations: list[tuple[str, str]] = []
        if self._root.is_symlink():
            return ((".", "run workspace root is a symbolic link"),)
        if not self._root.is_dir():
            return ((".", "run workspace root is not a directory"),)
        for name in CANONICAL_DIRECTORIES:
            path = self._root / name
            if path.is_symlink():
                violations.append((name, "canonical directory is a symbolic link"))
            elif not path.is_dir():
                violations.append((name, "canonical directory is missing"))
        for name in CANONICAL_FILES:
            path = self._root / name
            if path.is_symlink():
                violations.append((name, "canonical file is a symbolic link"))
            elif path.exists() and not path.is_file():
                violations.append((name, "canonical file is not a regular file"))
        return tuple(sorted(violations, key=lambda item: (item[0].encode("utf-8"), item[1])))

    def missing_canonical_files(self) -> tuple[str, ...]:
        """Name the canonical files a complete run would have but this one lacks."""

        return tuple(name for name in CANONICAL_FILES if not (self._root / name).is_file())

    def validate(self) -> None:
        violations = self.find_violations()
        if violations:
            path, message = violations[0]
            raise InvalidRunWorkspaceError(f"{message}: {path}")


def create_run_workspace(parent: Path, run_id: str) -> RunWorkspace:
    """Create an empty canonical run directory, refusing to reuse one."""

    resolved = _require_path(parent, "run workspace parent")
    identifier = _run_id(run_id)
    if not resolved.is_dir():
        raise RunWorkspaceNotFoundError(f"run workspace parent does not exist: {resolved}")
    root = resolved / identifier
    try:
        os.mkdir(root, 0o700)
    except FileExistsError as error:
        raise RunWorkspaceExistsError(f"run workspace already exists: {root}") from error
    except OSError as error:
        raise RunWorkspaceError(f"unable to create run workspace: {root}") from error
    for name in CANONICAL_DIRECTORIES:
        os.mkdir(root / name, 0o700)
    return RunWorkspace(root, identifier)


def open_run_workspace(root: Path) -> RunWorkspace:
    """Open an existing run directory, validating its structure."""

    resolved = _require_path(root, "run workspace root")
    if not resolved.exists():
        raise RunWorkspaceNotFoundError(f"run workspace does not exist: {resolved}")
    workspace = RunWorkspace(resolved, resolved.name)
    workspace.validate()
    return workspace


def _markdown_cell(value: str) -> str:
    """Render text safely inside a markdown table cell."""

    escaped = value.replace("\\", "\\\\").replace("|", "\\|")
    return "".join(
        character if unicodedata.category(character) != "Cc" else " " for character in escaped
    )


def _metric(value: float) -> str:
    # repr gives the shortest round-tripping form, so a rebuilt report is
    # byte-identical to the one the same rows produced before.
    return repr(value)


def rebuild_report(store: RunStore) -> str:
    """Render the run report deterministically from stored evidence alone."""

    lines = [f"# Run {_markdown_cell(store.run_id)}", ""]

    metadata = store.metadata()
    lines.append("## Metadata")
    lines.append("")
    if metadata:
        lines.append("| key | value |")
        lines.append("| --- | --- |")
        lines.extend(f"| {_markdown_cell(key)} | {_markdown_cell(value)} |" for key, value in metadata.items())
    else:
        lines.append("No metadata recorded.")
    lines.append("")

    evaluations = store.evaluations()
    lines.append("## Evaluations")
    lines.append("")
    if evaluations:
        lines.append("| sequence | benchmark | contender | metric | value |")
        lines.append("| --- | --- | --- | --- | --- |")
        lines.extend(
            f"| {row.sequence} | {_markdown_cell(row.benchmark_id)} |"
            f" {_markdown_cell(row.contender_id)} | {_markdown_cell(row.metric_name)} |"
            f" {_metric(row.metric_value)} |"
            for row in evaluations
        )
    else:
        lines.append("No evaluations recorded.")
    lines.append("")

    artifacts = store.artifacts()
    lines.append("## Artifacts")
    lines.append("")
    if artifacts:
        lines.append("| path | bytes | sha256 |")
        lines.append("| --- | --- | --- |")
        lines.extend(
            f"| {_markdown_cell(row.path)} | {row.size_bytes} | {row.sha256} |" for row in artifacts
        )
    else:
        lines.append("No artifacts recorded.")
    lines.append("")

    return "\n".join(lines)


def write_report(workspace: RunWorkspace, store: RunStore) -> str:
    """Rebuild the report and write it into the workspace."""

    report = rebuild_report(store)
    workspace.report_path.write_text(report, encoding="utf-8")
    return report


def _digest_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(_READ_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
    return digest.hexdigest(), total


def verify_artifact_references(
    workspace: RunWorkspace,
    artifacts: tuple[ArtifactRow, ...],
) -> tuple[tuple[str, str], ...]:
    """Prove every recorded artifact still matches, writing nothing.

    Returns deterministic (path, message) pairs; empty means every recorded
    artifact is present with the recorded size and digest.
    """

    findings: list[tuple[str, str]] = []
    for artifact in artifacts:
        path = workspace.root / artifact.path
        if path.is_symlink():
            findings.append((artifact.path, "artifact is a symbolic link"))
            continue
        try:
            status = path.lstat()
        except FileNotFoundError:
            findings.append((artifact.path, "artifact is missing"))
            continue
        except OSError:
            findings.append((artifact.path, "artifact is unreadable"))
            continue
        if not stat.S_ISREG(status.st_mode):
            findings.append((artifact.path, "artifact is not a regular file"))
            continue
        if status.st_size != artifact.size_bytes:
            findings.append(
                (artifact.path, f"artifact size is {status.st_size}, recorded {artifact.size_bytes}")
            )
            continue
        observed, read_bytes = _digest_file(path)
        if read_bytes != artifact.size_bytes:
            findings.append(
                (artifact.path, f"artifact size is {read_bytes}, recorded {artifact.size_bytes}")
            )
        elif observed != artifact.sha256:
            findings.append((artifact.path, f"artifact digest is {observed}, recorded {artifact.sha256}"))
    return tuple(sorted(findings, key=lambda item: (item[0].encode("utf-8"), item[1])))


__all__ = [
    "CANONICAL_DIRECTORIES",
    "CANONICAL_FILES",
    "CHECKPOINT_DIRNAME",
    "CONFIG_FILENAME",
    "REPORT_FILENAME",
    "STATE_FILENAME",
    "SUMMARY_FILENAME",
    "InvalidRunWorkspaceError",
    "RunWorkspace",
    "RunWorkspaceError",
    "RunWorkspaceExistsError",
    "RunWorkspaceNotFoundError",
    "create_run_workspace",
    "open_run_workspace",
    "rebuild_report",
    "verify_artifact_references",
    "write_report",
]
