#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/_common.sh"

# One selection covers the whole Shared package and the root contract consumer.
# Standalone package and phase0-contract scripts remain independently usable.
uv lock --check
uv run --locked --all-packages --group dev ruff check \
    EvoNN-Shared/src EvoNN-Shared/tests tests/contracts/test_phase0_shared_interfaces.py
uv run --locked --all-packages --group dev pytest -q \
    EvoNN-Shared/tests tests/contracts/test_phase0_shared_interfaces.py
verify_python_package_identity evonn-shared evonn_shared shared
