"""Repository-local access to the data-only shared benchmark skeleton."""

from __future__ import annotations

from pathlib import Path

_DATA_DIRECTORY = "shared-benchmarks"
_REQUIRED_DIRECTORIES = ("catalog", "suites/parity", "lm_cache", "migration", "tests")
_REQUIRED_FILES = ("README.md", "backend-capabilities.json", "tests/test_skeleton.py")
_PACKAGE_MARKERS = ("__init__.py",)
_PACKAGE_METADATA = ("pyproject.toml", "setup.py", "setup.cfg")


def resolve_data_root(repository_root: Path | None = None) -> Path:
    """Resolve the repository's shared benchmark data directory."""
    root = repository_root.resolve() if repository_root is not None else Path(__file__).resolve().parents[3]
    return root / _DATA_DIRECTORY


def find_data_skeleton_violations(data_root: Path | None = None) -> list[tuple[str, str]]:
    """Return deterministic path/message pairs for invalid data-only content."""
    root = (data_root or resolve_data_root()).absolute()
    violations: list[tuple[str, str]] = []
    if root.is_symlink():
        violations.append((".", "symbolic link found in data-only skeleton"))
    for path in root.rglob("*"):
        if path.is_symlink():
            violations.append((path.relative_to(root).as_posix(), "symbolic link found in data-only skeleton"))
    for relative in _REQUIRED_DIRECTORIES:
        if not (root / relative).is_dir():
            violations.append((relative, "Required shared benchmark directory is not a directory"))
    for relative in _REQUIRED_FILES:
        if not (root / relative).is_file():
            violations.append((relative, "Required shared benchmark file is not a file"))
    for marker in _PACKAGE_MARKERS:
        for path in root.rglob(marker):
            violations.append((path.relative_to(root).as_posix(), "Python package marker found in data-only skeleton"))
    for marker in _PACKAGE_METADATA:
        for path in root.rglob(marker):
            violations.append((path.relative_to(root).as_posix(), "Python package metadata found in data-only skeleton"))
    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        if path.name not in _PACKAGE_MARKERS and (not relative.parts or relative.parts[0] != "tests"):
            violations.append((relative.as_posix(), "runtime Python file found in data-only skeleton"))
    return sorted(violations, key=lambda item: (item[0].encode("utf-8"), item[1]))


def validate_data_skeleton(data_root: Path | None = None) -> Path:
    """Validate the required B0 layout and reject runtime package content."""
    root = (data_root or resolve_data_root()).absolute()
    violations = find_data_skeleton_violations(root)
    if violations:
        message, paths = violations[0][1], [path for path, detail in violations if detail == violations[0][1]]
        raise ValueError(f"{message}: {', '.join(paths)}")
    return root


__all__ = ["find_data_skeleton_violations", "resolve_data_root", "validate_data_skeleton"]
