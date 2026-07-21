#!/usr/bin/env python3
"""Validate exact current dependencies for every EvoNN workspace package."""

from __future__ import annotations

from pathlib import Path
import sys
import tomllib
from typing import Any

from evonn_shared.workspace_contract import WORKSPACE_DEPENDENCY_CONTRACTS


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def validate_repository(repo_root: Path) -> list[str]:
    """Return deterministic diagnostics for all current workspace dependencies."""
    root = repo_root.resolve()
    diagnostics: list[str] = []

    for package in WORKSPACE_DEPENDENCY_CONTRACTS:
        relative_path = f"{package.directory}/pyproject.toml"
        path = root / relative_path
        try:
            metadata = _load_toml(path)
            project = metadata["project"]
            dependencies = project["dependencies"]
        except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError) as exc:
            diagnostics.append(f"{relative_path}: cannot load project dependencies: {exc}")
            continue
        expected_dependencies = list(package.dependencies)
        if dependencies != expected_dependencies:
            diagnostics.append(
                f"{relative_path}: project.dependencies must be exactly {expected_dependencies!r}; found {dependencies!r}"
            )
        if package.distribution == "evonn-contenders" and isinstance(dependencies, list):
            declared = " ".join(str(dependency).lower() for dependency in dependencies)
            if "scikit-learn" in declared or "sklearn" in declared:
                diagnostics.append(
                    f"{relative_path}: scikit-learn must remain undeclared until Contenders Phase 1 implementation"
                )

    return sorted(set(diagnostics), key=lambda item: item.encode("utf-8"))


def main(arguments: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if arguments is None else arguments)
    if len(argv) > 1:
        print("Usage: validate_workspace_dependencies.py [REPOSITORY_ROOT]")
        return 2
    repo_root = Path(argv[0]).resolve() if argv else Path(__file__).resolve().parents[2]
    diagnostics = validate_repository(repo_root)
    if diagnostics:
        print(f"Workspace dependency policy: FAIL ({len(diagnostics)} violations)")
        for diagnostic in diagnostics:
            print(f"ERROR: {diagnostic}")
        return 1
    print("Workspace dependency policy: PASS (7 exact project dependency arrays)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
