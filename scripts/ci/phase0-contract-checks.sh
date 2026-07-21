#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$script_dir/_common.sh"

uv lock --check
uv run --locked --all-packages --group dev ruff check \
    tests/contracts/test_phase0_shared_interfaces.py \
    EvoNN-Shared/src/evonn_shared/canonical.py \
    EvoNN-Shared/src/evonn_shared/rng.py \
    EvoNN-Shared/src/evonn_shared/budgets.py \
    EvoNN-Shared/src/evonn_shared/telemetry.py \
    EvoNN-Shared/src/evonn_shared/exports.py \
    EvoNN-Shared/src/evonn_shared/catalog.py \
    EvoNN-Shared/tests/test_canonical.py \
    EvoNN-Shared/tests/test_rng.py \
    EvoNN-Shared/tests/test_budgets.py \
    EvoNN-Shared/tests/test_telemetry.py \
    EvoNN-Shared/tests/test_exports.py \
    EvoNN-Shared/tests/test_catalog.py
uv run --locked --all-packages --group dev pytest -q \
    tests/contracts/test_phase0_shared_interfaces.py \
    EvoNN-Shared/tests/test_canonical.py \
    EvoNN-Shared/tests/test_rng.py \
    EvoNN-Shared/tests/test_budgets.py \
    EvoNN-Shared/tests/test_telemetry.py \
    EvoNN-Shared/tests/test_exports.py \
    EvoNN-Shared/tests/test_catalog.py
