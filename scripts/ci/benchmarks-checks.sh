#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/_common.sh"

uv lock --check
uv run --locked --all-packages --group dev ruff check \
    EvoNN-Shared/src/evonn_shared/benchmarks.py shared-benchmarks/tests/test_skeleton.py
uv run --locked --all-packages --group dev pytest -q shared-benchmarks/tests/test_skeleton.py
uv run --locked --all-packages --group dev python -c \
    "from evonn_shared.benchmarks import resolve_data_root, validate_data_skeleton; root = resolve_data_root(); assert validate_data_skeleton(root) == root"
