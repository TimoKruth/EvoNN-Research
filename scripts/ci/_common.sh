#!/usr/bin/env bash
set -euo pipefail

repo_root="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

run_python_package_checks() {
    local distribution="$1"
    local package_directory="$2"
    local module_name="$3"
    local system_name="$4"

    uv lock --check
    uv run --locked --all-packages --group dev ruff check "$package_directory/src" "$package_directory/tests"
    uv run --locked --all-packages --group dev pytest -q "$package_directory/tests"
    uv run --locked --all-packages --group dev python -c \
        "from importlib.metadata import version; import ${module_name} as package; assert version('${distribution}') == package.__version__ == '0.0.0'; assert package.SYSTEM == '${system_name}'"
}
