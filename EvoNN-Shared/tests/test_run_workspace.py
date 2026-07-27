from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from evonn_shared.run_store import STORE_FILENAME, ArtifactRow, open_run_store
from evonn_shared.run_workspace import (
    CANONICAL_DIRECTORIES,
    CANONICAL_FILES,
    CHECKPOINT_DIRNAME,
    REPORT_FILENAME,
    InvalidRunWorkspaceError,
    RunWorkspace,
    RunWorkspaceError,
    RunWorkspaceExistsError,
    RunWorkspaceNotFoundError,
    create_run_workspace,
    open_run_workspace,
    rebuild_report,
    verify_artifact_references,
    write_report,
)

RUN_ID = "run_0001"
SUMMARY = b'{"status":"completed"}\n'
CONFIG = b"engine: prism\n"


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _tree_digests(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): _digest(path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _populated(tmp_path: Path) -> RunWorkspace:
    workspace = create_run_workspace(tmp_path, RUN_ID)
    workspace.config_path.write_bytes(CONFIG)
    workspace.summary_path.write_bytes(SUMMARY)
    workspace.state_path.write_bytes(b'{"generation":3}\n')
    with open_run_store(workspace.root, RUN_ID, create=True) as store:
        store.set_metadata("engine", "prism")
        store.set_metadata("backend", "mlx")
        store.append_evaluation("iris", "mlp_baseline", "accuracy", 0.91)
        store.append_evaluation("iris", "evonn_prism", "accuracy", 0.9425)
        store.record_artifact("config.yaml", len(CONFIG), _digest(CONFIG))
        store.record_artifact("summary.json", len(SUMMARY), _digest(SUMMARY))
        write_report(workspace, store)
    return workspace


# --- creation and layout --------------------------------------------------


def test_creating_a_workspace_yields_the_canonical_skeleton(tmp_path: Path) -> None:
    workspace = create_run_workspace(tmp_path, RUN_ID)

    assert workspace.root == tmp_path / RUN_ID
    assert workspace.run_id == RUN_ID
    assert workspace.checkpoint_directory.is_dir()
    assert workspace.find_violations() == ()


def test_a_fresh_workspace_reports_every_canonical_file_missing(tmp_path: Path) -> None:
    workspace = create_run_workspace(tmp_path, RUN_ID)

    assert workspace.missing_canonical_files() == CANONICAL_FILES


def test_a_populated_workspace_reports_only_the_report_as_present(tmp_path: Path) -> None:
    workspace = _populated(tmp_path)

    assert workspace.missing_canonical_files() == ()


def test_creating_a_workspace_twice_is_refused(tmp_path: Path) -> None:
    create_run_workspace(tmp_path, RUN_ID)

    with pytest.raises(RunWorkspaceExistsError):
        create_run_workspace(tmp_path, RUN_ID)


def test_creating_under_a_missing_parent_is_refused(tmp_path: Path) -> None:
    with pytest.raises(RunWorkspaceNotFoundError):
        create_run_workspace(tmp_path / "absent", RUN_ID)


def test_creating_with_an_unsafe_run_id_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        create_run_workspace(tmp_path, "../escape")


def test_opening_a_missing_workspace_is_refused(tmp_path: Path) -> None:
    with pytest.raises(RunWorkspaceNotFoundError):
        open_run_workspace(tmp_path / "absent")


def test_a_workspace_root_must_be_a_concrete_path(tmp_path: Path) -> None:
    workspace = _populated(tmp_path)

    with pytest.raises(RunWorkspaceError):
        open_run_workspace(str(workspace.root))  # type: ignore[arg-type]


def test_a_missing_checkpoint_directory_is_a_violation(tmp_path: Path) -> None:
    workspace = create_run_workspace(tmp_path, RUN_ID)
    workspace.checkpoint_directory.rmdir()

    assert workspace.find_violations() == ((CHECKPOINT_DIRNAME, "canonical directory is missing"),)
    with pytest.raises(InvalidRunWorkspaceError):
        workspace.validate()


def test_a_symlinked_checkpoint_directory_is_a_violation(tmp_path: Path) -> None:
    workspace = create_run_workspace(tmp_path, RUN_ID)
    outside = tmp_path / "outside"
    outside.mkdir()
    workspace.checkpoint_directory.rmdir()
    workspace.checkpoint_directory.symlink_to(outside, target_is_directory=True)

    assert workspace.find_violations() == (
        (CHECKPOINT_DIRNAME, "canonical directory is a symbolic link"),
    )


def test_a_symlinked_canonical_file_is_a_violation(tmp_path: Path) -> None:
    workspace = _populated(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_bytes(SUMMARY)
    workspace.summary_path.unlink()
    workspace.summary_path.symlink_to(outside)

    assert ("summary.json", "canonical file is a symbolic link") in workspace.find_violations()


def test_a_canonical_file_that_is_a_directory_is_a_violation(tmp_path: Path) -> None:
    workspace = create_run_workspace(tmp_path, RUN_ID)
    workspace.summary_path.mkdir()

    assert ("summary.json", "canonical file is not a regular file") in workspace.find_violations()


def test_a_symlinked_workspace_root_is_a_violation(tmp_path: Path) -> None:
    workspace = _populated(tmp_path)
    link = tmp_path / "link"
    link.symlink_to(workspace.root, target_is_directory=True)

    with pytest.raises(InvalidRunWorkspaceError):
        open_run_workspace(link)


def test_violations_are_reported_in_a_stable_order(tmp_path: Path) -> None:
    workspace = create_run_workspace(tmp_path, RUN_ID)
    workspace.checkpoint_directory.rmdir()
    workspace.summary_path.mkdir()
    workspace.config_path.mkdir()

    assert workspace.find_violations() == (
        ("checkpoints", "canonical directory is missing"),
        ("config.yaml", "canonical file is not a regular file"),
        ("summary.json", "canonical file is not a regular file"),
    )


def test_the_canonical_layout_matches_the_documented_run_directory() -> None:
    assert CANONICAL_DIRECTORIES == ("checkpoints",)
    assert CANONICAL_FILES == (
        "config.yaml",
        STORE_FILENAME,
        "state.json",
        "summary.json",
        "report.md",
    )


# --- report rebuilding ----------------------------------------------------


def test_the_report_is_rebuilt_byte_for_byte_from_the_store(tmp_path: Path) -> None:
    """report.md is derived, so rebuilding it must reproduce it exactly."""

    workspace = _populated(tmp_path)
    original = workspace.report_path.read_text(encoding="utf-8")

    with open_run_store(workspace.root, RUN_ID) as store:
        rebuilt = rebuild_report(store)

    assert rebuilt == original


def test_the_report_contains_every_evaluation_and_artifact(tmp_path: Path) -> None:
    workspace = _populated(tmp_path)
    report = workspace.report_path.read_text(encoding="utf-8")

    assert "| 0 | iris | mlp_baseline | accuracy | 0.91 |" in report
    assert "| 1 | iris | evonn_prism | accuracy | 0.9425 |" in report
    assert f"| summary.json | {len(SUMMARY)} | {_digest(SUMMARY)} |" in report
    assert "| engine | prism |" in report


def test_an_empty_store_still_produces_a_complete_report(tmp_path: Path) -> None:
    workspace = create_run_workspace(tmp_path, RUN_ID)

    with open_run_store(workspace.root, RUN_ID, create=True) as store:
        report = rebuild_report(store)

    assert "No metadata recorded." in report
    assert "No evaluations recorded." in report
    assert "No artifacts recorded." in report


def test_report_cells_cannot_break_out_of_the_table(tmp_path: Path) -> None:
    """Metadata is caller-supplied text and must not be able to forge rows."""

    workspace = create_run_workspace(tmp_path, RUN_ID)

    with open_run_store(workspace.root, RUN_ID, create=True) as store:
        store.set_metadata("engine", "prism | injected | row")
        report = rebuild_report(store)

    assert "| engine | prism \\| injected \\| row |" in report
    assert len([line for line in report.splitlines() if line.startswith("| engine")]) == 1


def test_control_characters_are_refused_before_they_reach_a_report(tmp_path: Path) -> None:
    """The store, not the renderer, is where control characters are stopped.

    `_markdown_cell` still neutralises them for any caller that builds a store
    by other means, but nothing written through this API can carry them.
    """

    workspace = create_run_workspace(tmp_path, RUN_ID)

    with open_run_store(workspace.root, RUN_ID, create=True) as store:
        with pytest.raises(ValueError):
            store.set_metadata("engine", "prism\x07alarm")


def test_metric_values_render_in_a_round_tripping_form(tmp_path: Path) -> None:
    workspace = create_run_workspace(tmp_path, RUN_ID)

    with open_run_store(workspace.root, RUN_ID, create=True) as store:
        store.append_evaluation("iris", "mlp_baseline", "accuracy", 0.1 + 0.2)
        report = rebuild_report(store)

    assert repr(0.1 + 0.2) in report


# --- artifact verification ------------------------------------------------


def test_recorded_artifacts_verify_against_their_files(tmp_path: Path) -> None:
    workspace = _populated(tmp_path)

    with open_run_store(workspace.root, RUN_ID) as store:
        artifacts = store.artifacts()

    assert verify_artifact_references(workspace, artifacts) == ()


def test_verification_writes_nothing_at_all(tmp_path: Path) -> None:
    """Verification is a read of the evidence, never an edit to it."""

    workspace = _populated(tmp_path)
    with open_run_store(workspace.root, RUN_ID) as store:
        artifacts = store.artifacts()
    before = _tree_digests(workspace.root)

    verify_artifact_references(workspace, artifacts)

    assert _tree_digests(workspace.root) == before


def test_a_missing_artifact_is_reported(tmp_path: Path) -> None:
    workspace = _populated(tmp_path)
    with open_run_store(workspace.root, RUN_ID) as store:
        artifacts = store.artifacts()
    workspace.summary_path.unlink()

    assert verify_artifact_references(workspace, artifacts) == (
        ("summary.json", "artifact is missing"),
    )


def test_a_resized_artifact_is_reported(tmp_path: Path) -> None:
    workspace = _populated(tmp_path)
    with open_run_store(workspace.root, RUN_ID) as store:
        artifacts = store.artifacts()
    workspace.summary_path.write_bytes(SUMMARY + b"extra\n")

    findings = verify_artifact_references(workspace, artifacts)

    assert [path for path, _ in findings] == ["summary.json"]
    assert "artifact size is" in findings[0][1]


def test_a_corrupted_artifact_of_the_right_length_is_reported(tmp_path: Path) -> None:
    workspace = _populated(tmp_path)
    with open_run_store(workspace.root, RUN_ID) as store:
        artifacts = store.artifacts()
    workspace.summary_path.write_bytes(b"X" + SUMMARY[1:])

    findings = verify_artifact_references(workspace, artifacts)

    assert [path for path, _ in findings] == ["summary.json"]
    assert "artifact digest is" in findings[0][1]


def test_a_symlinked_artifact_is_reported_without_being_read(tmp_path: Path) -> None:
    workspace = _populated(tmp_path)
    with open_run_store(workspace.root, RUN_ID) as store:
        artifacts = store.artifacts()
    outside = tmp_path / "outside.json"
    outside.write_bytes(SUMMARY)
    workspace.summary_path.unlink()
    workspace.summary_path.symlink_to(outside)

    assert verify_artifact_references(workspace, artifacts) == (
        ("summary.json", "artifact is a symbolic link"),
    )


def test_an_artifact_replaced_by_a_directory_is_reported(tmp_path: Path) -> None:
    workspace = _populated(tmp_path)
    with open_run_store(workspace.root, RUN_ID) as store:
        artifacts = store.artifacts()
    workspace.summary_path.unlink()
    workspace.summary_path.mkdir()

    assert verify_artifact_references(workspace, artifacts) == (
        ("summary.json", "artifact is not a regular file"),
    )


def test_findings_are_reported_in_a_stable_order(tmp_path: Path) -> None:
    workspace = _populated(tmp_path)
    with open_run_store(workspace.root, RUN_ID) as store:
        artifacts = store.artifacts()
    workspace.summary_path.unlink()
    workspace.config_path.unlink()

    assert verify_artifact_references(workspace, artifacts) == (
        ("config.yaml", "artifact is missing"),
        ("summary.json", "artifact is missing"),
    )


def test_verifying_no_artifacts_finds_nothing(tmp_path: Path) -> None:
    workspace = create_run_workspace(tmp_path, RUN_ID)

    assert verify_artifact_references(workspace, ()) == ()


# --- end to end -----------------------------------------------------------


def test_a_run_directory_can_be_built_rebuilt_and_verified_without_mutation(tmp_path: Path) -> None:
    """The WP-0.7 acceptance path, end to end.

    Build a canonical run directory, rebuild report.md from the store, and
    verify every artifact reference — proving the rebuild reproduces the file
    exactly and that verification leaves every byte of evidence untouched.
    """

    workspace = _populated(tmp_path)
    workspace.validate()
    evidence = {
        path: digest
        for path, digest in _tree_digests(workspace.root).items()
        if path not in (REPORT_FILENAME, STORE_FILENAME)
    }

    with open_run_store(workspace.root, RUN_ID) as store:
        assert store.verify_evaluation_chain() == 2
        rebuilt = write_report(workspace, store)
        findings = verify_artifact_references(workspace, store.artifacts())

    assert findings == ()
    assert rebuilt == workspace.report_path.read_text(encoding="utf-8")
    assert {
        path: digest
        for path, digest in _tree_digests(workspace.root).items()
        if path not in (REPORT_FILENAME, STORE_FILENAME)
    } == evidence


def test_rebuilding_the_report_twice_changes_nothing(tmp_path: Path) -> None:
    workspace = _populated(tmp_path)
    first = workspace.report_path.read_bytes()

    with open_run_store(workspace.root, RUN_ID) as store:
        write_report(workspace, store)

    assert workspace.report_path.read_bytes() == first


def test_artifact_rows_survive_the_round_trip_unchanged(tmp_path: Path) -> None:
    workspace = _populated(tmp_path)

    with open_run_store(workspace.root, RUN_ID) as store:
        artifacts = store.artifacts()

    assert artifacts == (
        ArtifactRow(path="config.yaml", size_bytes=len(CONFIG), sha256=_digest(CONFIG)),
        ArtifactRow(path="summary.json", size_bytes=len(SUMMARY), sha256=_digest(SUMMARY)),
    )
