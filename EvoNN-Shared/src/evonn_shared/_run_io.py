"""Small descriptor-based I/O primitives for application-owned run directories.

All directory components are opened without following symbolic links. These
helpers protect file operations, not against an actor with permission to
rename the opened directories or modify file contents in place. In particular
DuckDB must still open a validated pathname; it cannot consume our descriptor.
"""

from __future__ import annotations

from contextlib import contextmanager
import errno
import os
from pathlib import Path
import stat
from collections.abc import Iterator


def relative_parts(value: str) -> tuple[str, ...]:
    parts = tuple(value.split("/"))
    if any(part in ("", ".", "..") for part in parts) or "\\" in value or "\x00" in value:
        raise ValueError("path must use nonempty run-relative components without traversal")
    if ":" in parts[0]:
        raise ValueError("path must not contain a drive or URI prefix")
    return parts


def directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


@contextmanager
def open_directory(path: Path) -> Iterator[int]:
    """Walk from the absolute anchor; reject rather than resolve symlinks."""
    if ".." in path.parts:
        raise ValueError("directory traversal is not allowed")
    absolute = path.absolute()
    descriptor = os.open(absolute.anchor, directory_flags())
    try:
        for part in absolute.parts[1:]:
            child = os.open(part, directory_flags(), dir_fd=descriptor)
            previous, descriptor = descriptor, child
            os.close(previous)
        yield descriptor
    finally:
        os.close(descriptor)


def require_regular(status: os.stat_result, *, exclusive: bool = False) -> None:
    if not stat.S_ISREG(status.st_mode):
        raise OSError(errno.EINVAL, "file is not a regular file")
    if exclusive and status.st_nlink != 1:
        raise OSError(errno.EINVAL, "file must have exactly one hard link")


@contextmanager
def open_regular_at(directory_fd: int, path: str, *, exclusive: bool = False) -> Iterator[int]:
    parts = relative_parts(path)
    parent_fd = os.dup(directory_fd)
    try:
        for part in parts[:-1]:
            child = os.open(part, directory_flags(), dir_fd=parent_fd)
            previous, parent_fd = parent_fd, child
            os.close(previous)
        descriptor = os.open(
            parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=parent_fd
        )
        try:
            require_regular(os.fstat(descriptor), exclusive=exclusive)
            yield descriptor
        finally:
            os.close(descriptor)
    finally:
        os.close(parent_fd)


def validate_optional_file(directory_fd: int, name: str) -> bool:
    """Validate an existing mutable file before a pathname-only consumer opens it."""
    try:
        status = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    require_regular(status, exclusive=True)
    return True


def write_all(descriptor: int, payload: bytes) -> None:
    remaining = memoryview(payload)
    while remaining:
        count = os.write(descriptor, remaining)
        if count <= 0:
            raise OSError("file write made no progress")
        remaining = remaining[count:]
