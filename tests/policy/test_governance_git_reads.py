"""Immutable reads may be reused only within one governance validation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def validator():
    spec = importlib.util.spec_from_file_location(
        "governance_git_reads", REPO_ROOT / "scripts/policy/validate_repository_governance.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repository(tmp_path):
    def create(name):
        root = tmp_path / name
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / "evidence.txt").write_text("original\n")
        commit(root)
        return root

    return create


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def commit(root):
    git(root, "add", "evidence.txt")
    git(root, "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-qm", "evidence")


@pytest.mark.parametrize("read_kind", ["blob", "tree"])
def test_repeated_immutable_reads_execute_once_per_validation(validator, repository, monkeypatch, read_kind):
    root = repository("source")
    head = git(root, "rev-parse", "HEAD").decode().strip()
    args = (
        ("--no-replace-objects", "cat-file", "blob", f"{head}:evidence.txt")
        if read_kind == "blob"
        else ("--no-replace-objects", "ls-tree", "-z", head, "--", "evidence.txt")
    )
    expected = validator._git(root, *args)
    original = validator.subprocess.check_output
    calls = []

    def counted(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(validator.subprocess, "check_output", counted)
    with validator._immutable_git_read_scope():
        assert validator._git(root, *args) == expected
        with validator._immutable_git_read_scope():
            assert validator._git(root, *args) == expected
    assert len(calls) == 1
    with validator._immutable_git_read_scope():
        assert validator._git(root, *args) == expected
    assert len(calls) == 2


def test_moving_head_and_index_are_read_again_inside_scope(validator, repository):
    root = repository("source")
    with validator._immutable_git_read_scope():
        assert validator._git(root, "--no-replace-objects", "cat-file", "blob", "HEAD:evidence.txt") == b"original\n"
        old_index = validator._git(root, "ls-files", "--stage")
        (root / "evidence.txt").write_text("changed\n")
        commit(root)
        assert validator._git(root, "--no-replace-objects", "cat-file", "blob", "HEAD:evidence.txt") == b"changed\n"
        assert validator._git(root, "ls-files", "--stage") != old_index


def test_immutable_reads_do_not_cross_repositories_or_hide_missing_objects(validator, repository):
    source = repository("source")
    empty = source.parent / "empty"
    git(source.parent, "init", "-q", str(empty))
    head = git(source, "rev-parse", "HEAD").decode().strip()
    args = ("--no-replace-objects", "cat-file", "blob", f"{head}:evidence.txt")
    with validator._immutable_git_read_scope():
        assert validator._git(source, *args) == b"original\n"
        with pytest.raises(subprocess.CalledProcessError):
            validator._git(empty, *args)


def test_failed_read_is_retried_and_scope_resets_after_exception(validator, repository, monkeypatch):
    root = repository("source")
    head = git(root, "rev-parse", "HEAD").decode().strip()
    args = ("--no-replace-objects", "cat-file", "blob", f"{head}:evidence.txt")
    original = validator.subprocess.check_output
    calls = 0

    def transient(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise subprocess.CalledProcessError(1, args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(validator.subprocess, "check_output", transient)
    with pytest.raises(RuntimeError, match="abort"):
        with validator._immutable_git_read_scope():
            with pytest.raises(subprocess.CalledProcessError):
                validator._git(root, *args)
            assert validator._git(root, *args) == b"original\n"
            raise RuntimeError("abort")
    assert validator._git(root, *args) == b"original\n"
    assert calls == 3


def test_later_validation_detects_removed_git_object(validator, repository):
    root = repository("source")
    blob = git(root, "rev-parse", "HEAD:evidence.txt").decode().strip()
    args = ("--no-replace-objects", "cat-file", "blob", blob)
    with validator._immutable_git_read_scope():
        assert validator._git(root, *args) == b"original\n"
    (root / ".git" / "objects" / blob[:2] / blob[2:]).unlink()
    with validator._immutable_git_read_scope():
        with pytest.raises(subprocess.CalledProcessError):
            validator._git(root, *args)
