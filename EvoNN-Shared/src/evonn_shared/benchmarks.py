"""Repository-local access to the data-only shared benchmark skeleton."""

from __future__ import annotations

from pathlib import Path

_DATA_DIRECTORY = "shared-benchmarks"
_REQUIRED_DIRECTORIES = ("catalog", "suites/parity", "lm_cache", "migration", "tests")
_REQUIRED_FILES = ("README.md", "backend-capabilities.json", "tests/test_skeleton.py")
_PACKAGE_MARKERS = ("__init__.py", "pyproject.toml", "setup.py", "setup.cfg")


def resolve_data_root(repository_root: Path | None = None) -> Path:
    """Resolve the repository's shared benchmark data directory."""
    root = repository_root.resolve() if repository_root is not None else Path(__file__).resolve().parents[3]
    return root / _DATA_DIRECTORY


def validate_data_skeleton(data_root: Path | None = None) -> Path:
    """Validate the required B0 layout and reject runtime package content."""
    root = (data_root or resolve_data_root()).resolve()
    invalid_directories = [relative for relative in _REQUIRED_DIRECTORIES if not (root / relative).is_dir()]
    if invalid_directories:
        raise ValueError(
            f"Required shared benchmark directory is not a directory: {', '.join(invalid_directories)}"
        )

    invalid_files = [relative for relative in _REQUIRED_FILES if not (root / relative).is_file()]
    if invalid_files:
        raise ValueError(f"Required shared benchmark file is not a file: {', '.join(invalid_files)}")

    package_markers = sorted(path.relative_to(root).as_posix() for marker in _PACKAGE_MARKERS for path in root.rglob(marker))
    if package_markers:
        raise ValueError(f"Python package marker found in data-only skeleton: {', '.join(package_markers)}")

    unexpected_python = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*.py")
        if path.relative_to(root).as_posix() != "tests/test_skeleton.py"
    )
    if unexpected_python:
        raise ValueError(f"Runtime Python file found in data-only skeleton: {', '.join(unexpected_python)}")
    return root


__all__ = ["resolve_data_root", "validate_data_skeleton"]
