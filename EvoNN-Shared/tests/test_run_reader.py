"""A verified read-only consumer must never recover or rewrite source evidence."""

import hashlib
import os

import duckdb
import pytest

from evonn_shared import run_store as module


@pytest.fixture
def root(tmp_path):
    path = tmp_path / "source"
    path.mkdir()
    with module.open_run_store(path, "source", create=True) as store:
        store.append_evaluation("synthetic_reference", "noop", "score", 0.5)
        store.set_metadata("purpose", "reader test")
    return path


def digest_tree(root):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()}


def test_reader_verifies_without_source_changes_or_writer_methods(root):
    before = digest_tree(root)
    with module.open_run_reader(root, "source") as reader:
        assert reader.run_id == "source"
        assert reader.run().evaluation_count == reader.verify_evaluation_chain() == 1
        assert reader.evaluations()[0].metric_value == 0.5
        assert reader.metadata() == {"purpose": "reader test"}
        assert reader.artifacts() == ()
        for method in ("append_evaluation", "set_metadata", "record_artifact"):
            assert not hasattr(reader, method)
    assert digest_tree(root) == before


def test_multiple_readers_share_lock_but_exclude_writer(root):
    with module.open_run_reader(root, "source") as first:
        with module.open_run_reader(root, "source") as second:
            assert first.evaluations() == second.evaluations()
            with pytest.raises(module.RunStoreLockedError):
                with module.open_run_store(root, "source"):
                    pytest.fail("writer acquired lock while readers were active")
    with module.open_run_store(root, "source") as writer:
        writer.append_evaluation("synthetic_reference", "noop", "score", 0.7)


def test_active_writer_excludes_reader(root):
    with module.open_run_store(root, "source"):
        with pytest.raises(module.RunStoreLockedError):
            with module.open_run_reader(root, "source"):
                pytest.fail("reader acquired lock while writer was active")


@pytest.mark.parametrize("statement", [
    "UPDATE evaluations SET metric_value=0.9",
    "DELETE FROM evaluations",
    "UPDATE runs SET evaluation_tip_sha256='wrong'",
])
def test_reader_rejects_corruption_without_repair(root, statement):
    with duckdb.connect(str(root / module.STORE_FILENAME)) as connection:
        connection.execute(statement)
    before = digest_tree(root)
    with pytest.raises(ValueError):
        with module.open_run_reader(root, "source"):
            pytest.fail("corrupted evidence was yielded")
    assert digest_tree(root) == before


def test_wrong_identity_and_missing_files_do_not_create_or_repair(root):
    with pytest.raises(module.RunIdentityError):
        with module.open_run_reader(root, "different"):
            pytest.fail("wrong run accepted")
    (root / module.LOCK_FILENAME).unlink()
    before = digest_tree(root)
    with pytest.raises(module.RunStoreNotFoundError):
        with module.open_run_reader(root, "source"):
            pytest.fail("missing lock was created")
    assert digest_tree(root) == before


def test_reader_refuses_wal_and_leaves_recovery_to_writer(root):
    (root / (module.STORE_FILENAME + ".wal")).write_bytes(b"unrecovered")
    before = digest_tree(root)
    with pytest.raises(module.RunStoreError, match="WAL"):
        with module.open_run_reader(root, "source"):
            pytest.fail("unrecovered store accepted")
    assert digest_tree(root) == before


@pytest.mark.parametrize("name", [module.STORE_FILENAME, module.LOCK_FILENAME])
@pytest.mark.parametrize("kind", ["symlink", "hardlink"])
def test_reader_rejects_aliased_files(root, name, kind):
    target = root / name
    outside = root.parent / name
    target.rename(outside)
    if kind == "symlink":
        target.symlink_to(outside)
    else:
        os.link(outside, target)
    before = outside.read_bytes()
    with pytest.raises(module.RunStoreError):
        with module.open_run_reader(root, "source"):
            pytest.fail("aliased source accepted")
    assert outside.read_bytes() == before


def test_reader_connection_is_enforced_read_only(root, monkeypatch):
    original = duckdb.connect
    flags = []

    def readonly(*args, **kwargs):
        flags.append(kwargs)
        assert kwargs == {"read_only": True}
        connection = original(*args, **kwargs)
        with pytest.raises(duckdb.InvalidInputException, match="read-only"):
            connection.execute("DELETE FROM evaluations")
        return connection

    monkeypatch.setattr(duckdb, "connect", readonly)
    with module.open_run_reader(root, "source"):
        pass
    assert flags == [{"read_only": True}]


def test_exception_releases_reader_lock(root):
    with pytest.raises(RuntimeError):
        with module.open_run_reader(root, "source"):
            raise RuntimeError("consumer failed")
    with module.open_run_store(root, "source"):
        pass
