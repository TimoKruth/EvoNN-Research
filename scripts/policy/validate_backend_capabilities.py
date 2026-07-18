#!/usr/bin/env python3
"""Validate backend capability manifests against locked workspace metadata."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tomllib
from typing import Any

from evonn_shared.backend_contract import EXPECTED_MANIFESTS, PACKAGE_CONTRACTS


def _relative(repo_root: Path, path: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def validate_repository(repo_root: Path) -> list[str]:
    """Return deterministic diagnostics for all capability and dependency contracts."""
    root = repo_root.resolve()
    diagnostics: list[str] = []
    if len(EXPECTED_MANIFESTS) != 8:
        diagnostics.append("internal policy error: exactly eight backend manifests are required")

    for relative_path, expected in EXPECTED_MANIFESTS.items():
        path = root / relative_path
        try:
            actual = _load_json(path)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            diagnostics.append(f"{relative_path}: cannot load backend capability manifest: {exc}")
            continue
        if actual != expected:
            diagnostics.append(f"{relative_path}: manifest does not match the exact B0 backend capability contract")

    for package in PACKAGE_CONTRACTS:
        path = root / package.directory / "pyproject.toml"
        relative_path = _relative(root, path)
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
        if package.system == "contenders" and isinstance(dependencies, list):
            declared = " ".join(str(dependency).lower() for dependency in dependencies)
            if "scikit-learn" in declared or "sklearn" in declared:
                diagnostics.append(
                    f"{relative_path}: scikit-learn must remain undeclared until Contenders Phase 1 implementation"
                )

    return sorted(set(diagnostics), key=lambda item: item.encode("utf-8"))


def main(arguments: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if arguments is None else arguments)
    if len(argv) > 1:
        print("Usage: validate_backend_capabilities.py [REPOSITORY_ROOT]")
        return 2
    repo_root = Path(argv[0]).resolve() if argv else Path(__file__).resolve().parents[2]
    diagnostics = validate_repository(repo_root)
    if diagnostics:
        print(f"Backend capability policy: FAIL ({len(diagnostics)} violations)")
        for diagnostic in diagnostics:
            print(f"ERROR: {diagnostic}")
        return 1
    print("Backend capability policy: PASS (8 manifests, 4 dual-backend engine declarations)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
