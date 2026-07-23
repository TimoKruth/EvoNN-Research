#!/usr/bin/env python3
"""Validate backend capability manifests against the immutable B0 contract."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from evonn_shared.backend_contract import EXPECTED_MANIFESTS


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_repository(repo_root: Path) -> list[str]:
    """Return deterministic diagnostics for all backend capability manifests."""
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
