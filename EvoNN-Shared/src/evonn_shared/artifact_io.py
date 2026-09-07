"""Bounded, descriptor-based verification of exported and cached artifacts."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from ._run_io import directory_flags, open_directory, open_regular_at, publish_new_file
from .telemetry import ArtifactReference
from .exports import _load_exclusive_rename


def create_artifact_directory(path: Path) -> Path:
    """Create missing components without traversing a symbolic link."""
    if ".." in path.parts:
        raise ValueError("directory traversal is not allowed")
    absolute = path.absolute()
    descriptor = os.open(absolute.anchor, directory_flags())
    try:
        for part in absolute.parts[1:]:
            try:
                os.mkdir(part, dir_fd=descriptor)
            except FileExistsError:
                pass
            child = os.open(part, directory_flags(), dir_fd=descriptor)
            previous, descriptor = descriptor, child
            os.close(previous)
    finally:
        os.close(descriptor)
    return absolute


def read_verified_artifact(
    root: Path, reference: ArtifactReference, *, size_bytes: int | None = None,
    max_bytes: int = 256 * 1024 * 1024,
) -> bytes:
    """Return the exact bytes checked; never reopen a verified pathname."""
    if type(max_bytes) is not int or max_bytes < 0:
        raise ValueError("max_bytes must be a nonnegative integer")
    if size_bytes is not None and (type(size_bytes) is not int or size_bytes < 0):
        raise ValueError("size_bytes must be a nonnegative integer")
    with open_directory(root) as directory_fd, open_regular_at(directory_fd, reference.path) as descriptor:
        observed_size = os.fstat(descriptor).st_size
        if observed_size > max_bytes or (size_bytes is not None and observed_size != size_bytes):
            raise ValueError(f"artifact size mismatch or limit exceeded: {reference.path}")
        pieces: list[bytes] = []
        total = 0
        while chunk := os.read(descriptor, min(1024 * 1024, max_bytes + 1 - total)):
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"artifact exceeds read limit: {reference.path}")
            pieces.append(chunk)
        payload = b"".join(pieces)
    if len(payload) != observed_size or hashlib.sha256(payload).hexdigest() != reference.sha256:
        raise ValueError(f"artifact content mismatch: {reference.path}")
    return payload


def publish_artifact(path: Path, payload: bytes) -> ArtifactReference:
    """Publish new bytes without overwriting an existing evidence file."""
    publish_new_file(path, payload)
    return ArtifactReference(path=path.name, sha256=hashlib.sha256(payload).hexdigest())


def publish_artifact_directory(staging: Path, destination: Path) -> None:
    """Publish a completed sibling directory without replacing prior evidence.

    Callers fsync each artifact while writing. Failure after rename means the
    directory may be visible with unconfirmed durability; never remove it as
    a pretend rollback. Application-owned POSIX directories are required.
    """
    if staging.absolute().parent != destination.absolute().parent or staging == destination:
        raise ValueError("publication requires distinct sibling directories")
    with open_directory(staging.parent) as parent_fd, open_directory(staging) as staging_fd:
        actual = os.fstat(staging_fd)
        named = os.stat(staging.name, dir_fd=parent_fd, follow_symlinks=False)
        if (actual.st_dev, actual.st_ino) != (named.st_dev, named.st_ino):
            raise ValueError("staging directory identity changed")
        os.fsync(staging_fd)
        _load_exclusive_rename()(parent_fd, staging.name, destination.name)
        os.fsync(parent_fd)


def append_artifact(path: Path, payload: bytes, *, expected_sha256: str, max_bytes: int = 128 * 1024 * 1024) -> None:
    """Append under caller-owned locking only if the existing bytes still match.

    An interrupted append may leave a partial record; readers must reject it,
    not silently truncate or repair evidence. The descriptor is never reopened.
    """
    from ._run_io import require_regular, write_all
    with open_directory(path.parent) as directory:
        fd = os.open(path.name, os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=directory)
        try:
            require_regular(os.fstat(fd), exclusive=True)
            if os.fstat(fd).st_size + len(payload) > max_bytes:
                raise ValueError("append artifact size limit exceeded")
            digest = hashlib.sha256()
            while chunk := os.read(fd, 1024 * 1024):
                digest.update(chunk)
            if digest.hexdigest() != expected_sha256:
                raise ValueError("append source changed")
            write_all(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
