"""Regression coverage for transactional records and run-directory boundaries."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys

import duckdb
import pytest

from evonn_shared import run_store, run_workspace
from evonn_shared.run_store import ArtifactRow, EvaluationChainError, RunStoreError, open_run_store
from evonn_shared.run_workspace import RunWorkspace, RunWorkspaceError, verify_artifact_references, write_report


class FailingConnection:
    def __init__(self, connection, prefix):
        self.connection = connection
        self.prefix = prefix

    def execute(self, sql, *args):
        if sql.startswith(self.prefix):
            raise RuntimeError("injected database failure")
        return self.connection.execute(sql, *args)

    def close(self):
        self.connection.close()


def test_failed_append_rolls_back_and_next_append_can_commit(tmp_path):
    with open_run_store(tmp_path, "run", create=True) as store:
        first = store.append_evaluation("iris", "baseline", "accuracy", 0.5)
        connection = store._connection
        store._connection = FailingConnection(connection, "UPDATE runs SET")
        with pytest.raises(RuntimeError, match="injected"):
            store.append_evaluation("iris", "baseline", "accuracy", 0.9)
        store._connection = connection
        assert store.evaluations() == (first,)
        assert store.verify_evaluation_chain() == 1
        assert store.append_evaluation("iris", "baseline", "accuracy", 0.8).sequence == 1
    with open_run_store(tmp_path, "run") as store:
        assert store.verify_evaluation_chain() == 2


def test_killed_writer_during_append_preserves_previous_committed_chain(tmp_path):
    with open_run_store(tmp_path, "run", create=True) as store:
        first = store.append_evaluation("iris", "baseline", "accuracy", 0.5)
    script = '''
import os, signal, sys
from pathlib import Path
from evonn_shared.run_store import open_run_store
class KillOnTipUpdate:
    def __init__(self, connection):
        self.connection = connection
    def execute(self, sql, *args):
        if sql.startswith("UPDATE runs SET"):
            os.kill(os.getpid(), signal.SIGKILL)
        return self.connection.execute(sql, *args)
with open_run_store(Path(sys.argv[1]), "run") as store:
    store._connection = KillOnTipUpdate(store._connection)
    store.append_evaluation("iris", "baseline", "accuracy", 0.9)
'''
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path)], timeout=30, capture_output=True)
    assert result.returncode == -9, result.stderr.decode()
    with open_run_store(tmp_path, "run") as store:
        assert store.recovered_stale_lock
        assert store.evaluations() == (first,)
        assert store.verify_evaluation_chain() == 1


def test_schema_creation_rolls_back_all_tables_on_failure(tmp_path, monkeypatch):
    connect = duckdb.connect
    monkeypatch.setattr(run_store.duckdb, "connect", lambda *a, **kw: FailingConnection(
        connect(*a, **kw), "CREATE TABLE artifacts"
    ))
    with pytest.raises(RuntimeError, match="injected"):
        with open_run_store(tmp_path, "run", create=True):
            pytest.fail("incomplete schema must never be yielded")
    with connect(str(tmp_path / run_store.STORE_FILENAME)) as connection:
        assert connection.execute("SHOW TABLES").fetchall() == []
    assert run_store.read_lock_owner(tmp_path) is None


def test_corrupt_evidence_is_rejected_before_writer_is_yielded(tmp_path):
    with open_run_store(tmp_path, "run", create=True) as store:
        store.append_evaluation("iris", "baseline", "accuracy", 0.5)
    with duckdb.connect(str(tmp_path / run_store.STORE_FILENAME)) as connection:
        connection.execute("DELETE FROM evaluations")
    with pytest.raises(EvaluationChainError):
        with open_run_store(tmp_path, "run"):
            pytest.fail("corrupt evidence must not be available for continuation")
    assert run_store.read_lock_owner(tmp_path) is None


@pytest.mark.parametrize("name", ["run.lock", "metrics.duckdb", "metrics.duckdb.wal"])
@pytest.mark.parametrize("kind", ["symlink", "hardlink"])
def test_storage_links_cannot_modify_external_files(tmp_path, name, kind):
    directory = tmp_path / "run"
    directory.mkdir()
    target = tmp_path / "external"
    target.write_bytes(b"must remain intact")
    link = directory / name
    if kind == "symlink":
        link.symlink_to(target)
    else:
        os.link(target, link)
    with pytest.raises(RunStoreError):
        with open_run_store(directory, "run", create=name != "metrics.duckdb"):
            pytest.fail("linked storage must be refused")
    assert target.read_bytes() == b"must remain intact"


def test_read_lock_owner_rejects_oversized_file(tmp_path):
    (tmp_path / "run.lock").write_bytes(b" " * (64 * 1024 + 1))
    with pytest.raises(RunStoreError):
        run_store.read_lock_owner(tmp_path)


def test_symlinked_parent_cannot_create_run_storage(tmp_path):
    outside = tmp_path / "outside"
    (outside / "run").mkdir(parents=True)
    link = tmp_path / "linked"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(RunStoreError):
        with open_run_store(link / "run", "run", create=True):
            pytest.fail("symlinked parent must be refused")
    assert list((outside / "run").iterdir()) == []


def test_artifact_in_symlinked_subdirectory_is_rejected(tmp_path):
    directory = tmp_path / "run"
    directory.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    payload = b"external evidence"
    (outside / "result").write_bytes(payload)
    (directory / "linked").symlink_to(outside, target_is_directory=True)
    artifact = ArtifactRow(path="linked/result", size_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    assert verify_artifact_references(RunWorkspace(directory, "run"), (artifact,))


def test_regular_nested_artifact_still_verifies(tmp_path):
    (tmp_path / "nested").mkdir()
    payload = b"valid evidence"
    (tmp_path / "nested/result").write_bytes(payload)
    artifact = ArtifactRow(path="nested/result", size_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    assert verify_artifact_references(RunWorkspace(tmp_path, "run"), (artifact,)) == ()


def test_report_symlink_cannot_modify_external_file(tmp_path):
    directory = tmp_path / "run"
    directory.mkdir()
    target = tmp_path / "external"
    target.write_bytes(b"unchanged")
    (directory / "report.md").symlink_to(target)
    with open_run_store(directory, "run", create=True) as store:
        with pytest.raises(RunWorkspaceError):
            write_report(RunWorkspace(directory, "run"), store)
    assert target.read_bytes() == b"unchanged"


def test_report_write_failure_preserves_previous_report(tmp_path, monkeypatch):
    workspace = RunWorkspace(tmp_path, "run")
    workspace.report_path.write_bytes(b"previous report")
    def fail_fsync(descriptor):
        raise OSError("injected fsync failure")
    with open_run_store(tmp_path, "run", create=True) as store:
        with monkeypatch.context() as patch:
            patch.setattr(os, "fsync", fail_fsync)
            with pytest.raises(RunWorkspaceError):
                write_report(workspace, store)
        assert workspace.report_path.read_bytes() == b"previous report"
    assert not list(tmp_path.glob(".report-*.tmp"))


def test_report_refuses_a_different_run_identity(tmp_path):
    with open_run_store(tmp_path, "run", create=True) as store:
        with pytest.raises(RunWorkspaceError):
            write_report(RunWorkspace(tmp_path, "other"), store)
    assert not (tmp_path / "report.md").exists()


def test_symlinked_parent_cannot_create_a_workspace(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "linked"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(RunWorkspaceError):
        run_workspace.create_run_workspace(link, "run")
    assert list(outside.iterdir()) == []


def test_artifact_verification_uses_the_opened_file_after_name_replacement(tmp_path, monkeypatch):
    payload = b"valid evidence"
    artifact_path = tmp_path / "result"
    artifact_path.write_bytes(payload)
    outside = tmp_path / "outside"
    outside.write_bytes(b"different external bytes")
    artifact = ArtifactRow(path="result", size_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    digest_file = run_workspace._digest_file
    def replace_then_hash(descriptor, expected_size):
        artifact_path.unlink()
        artifact_path.symlink_to(outside)
        return digest_file(descriptor, expected_size)
    monkeypatch.setattr(run_workspace, "_digest_file", replace_then_hash)
    # The verified observation is the original opened inode, never the link target.
    assert verify_artifact_references(RunWorkspace(tmp_path, "run"), (artifact,)) == ()


def test_close_error_still_releases_the_writer_lock(tmp_path, monkeypatch):
    connect = duckdb.connect
    class CloseErrorConnection(FailingConnection):
        def close(self):
            self.connection.close()
            raise RuntimeError("injected close failure")
    with monkeypatch.context() as patch:
        patch.setattr(run_store.duckdb, "connect", lambda *a, **kw: CloseErrorConnection(connect(*a, **kw), "never"))
        with pytest.raises(RuntimeError, match="close failure"):
            with open_run_store(tmp_path, "run", create=True):
                pass
    with open_run_store(tmp_path, "run") as store:
        assert store.verify_evaluation_chain() == 0


@pytest.mark.parametrize("path", ["./result", "nested//result", "result/", "C:/result", "nested\\result"])
def test_artifact_paths_reject_ambiguous_components(path):
    with pytest.raises(ValueError):
        ArtifactRow(path=path, size_bytes=0, sha256="a" * 64)
