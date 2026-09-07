"""Complete-or-absent evidence output with no overwrite of prior artifacts."""

from concurrent.futures import ThreadPoolExecutor
import os
import stat

import pytest

from evonn_shared import _run_io as io


def test_new_publication_is_complete_private_and_has_no_staging_files(tmp_path):
    destination = tmp_path / "evidence.json"
    io.publish_new_file(destination, b'{"complete":true}\n')
    assert destination.read_bytes() == b'{"complete":true}\n'
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert destination.stat().st_nlink == 1
    assert list(tmp_path.iterdir()) == [destination]


@pytest.mark.parametrize("kind", ["regular", "symlink", "hardlink", "directory"])
def test_existing_destination_is_never_overwritten(tmp_path, kind):
    source = tmp_path / "keep"
    source.write_bytes(b"original")
    destination = tmp_path / "output"
    if kind == "regular":
        destination.write_bytes(b"original")
    elif kind == "symlink":
        destination.symlink_to(source)
    elif kind == "hardlink":
        os.link(source, destination)
    else:
        destination.mkdir()
    with pytest.raises(FileExistsError):
        io.publish_new_file(destination, b"replacement")
    assert source.read_bytes() == b"original"
    if kind != "directory":
        assert destination.read_bytes() == b"original"
    assert not list(tmp_path.glob(".publish-*"))


def test_partial_stage_write_is_never_visible_at_final_name(tmp_path, monkeypatch):
    destination = tmp_path / "output"

    def fail(descriptor, payload):
        os.write(descriptor, payload[:3])
        assert not destination.exists()
        raise OSError("injected write failure")

    monkeypatch.setattr(io, "write_all", fail)
    with pytest.raises(OSError, match="write failure"):
        io.publish_new_file(destination, b"complete payload")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("phase", ["file", "directory"])
def test_fsync_failure_reports_publication_boundary(tmp_path, monkeypatch, phase):
    destination = tmp_path / "output"
    original = os.fsync

    def fail(descriptor):
        is_directory = stat.S_ISDIR(os.fstat(descriptor).st_mode)
        if is_directory == (phase == "directory"):
            raise OSError("injected fsync failure")
        original(descriptor)

    monkeypatch.setattr(io.os, "fsync", fail)
    with pytest.raises(OSError, match="fsync failure"):
        io.publish_new_file(destination, b"complete")
    assert destination.exists() == (phase == "directory")
    if destination.exists():
        assert destination.read_bytes() == b"complete"
    assert not list(tmp_path.glob(".publish-*"))


def test_concurrent_publishers_have_exactly_one_winner(tmp_path):
    destination = tmp_path / "output"

    def publish(payload):
        try:
            io.publish_new_file(destination, payload)
            return True
        except FileExistsError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(publish, [b"first", b"second"]))
    assert sorted(results) == [False, True]
    assert destination.read_bytes() in (b"first", b"second")
    assert not list(tmp_path.glob(".publish-*"))


def test_symlink_parent_is_refused_without_external_mutation(tmp_path):
    parent = tmp_path / "real"
    parent.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(parent, target_is_directory=True)
    with pytest.raises(OSError):
        io.publish_new_file(alias / "output", b"unsafe")
    assert list(parent.iterdir()) == []
