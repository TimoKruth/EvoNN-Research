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
import uuid
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


def publish_new_file(path: Path, payload: bytes) -> None:
    """Publish complete bytes without replacing any existing destination.

    Requires local POSIX hard-link/fsync semantics and an application-owned
    directory. Stage and fsync first, then atomically link into the new name.
    A final directory-fsync failure means uncertain durability: the complete
    file is already visible. Never retry by overwriting or deleting that file.
    """
    if type(path) is not type(Path()) or type(payload) is not bytes:
        raise TypeError("publication requires a concrete Path and bytes")
    relative_parts(path.name)
    with open_directory(path.parent) as directory_fd:
        temporary = ".publish-" + uuid.uuid4().hex
        descriptor = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600, dir_fd=directory_fd,
        )
        primary = None
        try:
            try:
                write_all(descriptor, payload)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            os.link(temporary, path.name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd,
                    follow_symlinks=False)
        except BaseException as error:
            primary = error
            raise
        finally:
            try:
                os.unlink(temporary, dir_fd=directory_fd)
            except OSError as error:
                if primary is None:
                    raise
                primary.add_note(f"publication staging cleanup failed: {error}")
        os.fsync(directory_fd)
