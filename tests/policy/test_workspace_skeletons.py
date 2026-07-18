from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from evonn_shared.backend_contract import EXPECTED_MANIFESTS, PACKAGE_CONTRACTS

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGES = {
    package.directory: (package.distribution, package.module, package.system)
    for package in PACKAGE_CONTRACTS
}
PACKAGE_CONTRACT_BY_DIRECTORY = {package.directory: package for package in PACKAGE_CONTRACTS}
CHECK_SCRIPTS = {
    "shared-checks.sh",
    "benchmarks-checks.sh",
    "contenders-checks.sh",
    "compare-checks.sh",
    "prism-checks.sh",
    "topograph-checks.sh",
    "stratograph-checks.sh",
    "primordia-checks.sh",
}
ALL_CHECK_SCRIPTS = CHECK_SCRIPTS | {"b0-policy-checks.sh"}


def load_toml(path: Path) -> dict:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def test_root_is_python_313_uv_workspace_with_exact_members() -> None:
    metadata = load_toml(REPO_ROOT / "pyproject.toml")

    assert metadata["project"]["requires-python"] == ">=3.13"
    assert metadata["tool"]["uv"]["workspace"]["members"] == list(PACKAGES)
    assert "shared-benchmarks" not in metadata["tool"]["uv"]["workspace"]["members"]
    assert set(metadata["dependency-groups"]["dev"]) == {"pytest", "PyYAML", "ruff"}
    assert metadata["tool"]["uv"]["environments"] == [
        "sys_platform == 'darwin'",
        "sys_platform == 'linux'",
    ]


@pytest.mark.parametrize("directory,package", PACKAGES.items())
def test_package_metadata_and_installed_import_identity(directory: str, package: tuple[str, str, str]) -> None:
    distribution, module_name, system = package
    metadata = load_toml(REPO_ROOT / directory / "pyproject.toml")

    assert metadata["project"]["name"] == distribution
    assert metadata["project"]["requires-python"] == ">=3.13"
    assert metadata["build-system"]["build-backend"]
    contract = PACKAGE_CONTRACT_BY_DIRECTORY[directory]
    assert metadata["project"]["dependencies"] == list(contract.dependencies)
    if distribution != "evonn-shared":
        assert metadata["tool"]["uv"]["sources"]["evonn-shared"] == {"workspace": True}

    imported = importlib.import_module(module_name)
    assert imported.__version__ == "0.0.0"
    assert imported.SYSTEM == system


def test_shared_benchmarks_resolves_and_validates_data_only_layout() -> None:
    from evonn_shared.benchmarks import resolve_data_root, validate_data_skeleton

    data_root = resolve_data_root()
    assert data_root == REPO_ROOT / "shared-benchmarks"
    assert validate_data_skeleton(data_root) == data_root
    assert not (data_root / "pyproject.toml").exists()
    assert not list(data_root.rglob("__init__.py"))


def test_shared_benchmarks_rejects_python_package_markers(tmp_path: Path) -> None:
    from evonn_shared.benchmarks import validate_data_skeleton

    data_root = tmp_path / "shared-benchmarks"
    for relative in ("catalog", "suites/parity", "lm_cache", "migration", "tests"):
        (data_root / relative).mkdir(parents=True, exist_ok=True)
    (data_root / "README.md").write_text("data only\n", encoding="utf-8")
    (data_root / "backend-capabilities.json").write_text("{}\n", encoding="utf-8")
    (data_root / "tests/test_skeleton.py").write_text("", encoding="utf-8")
    marker = data_root / "catalog/__init__.py"
    marker.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="Python package marker"):
        validate_data_skeleton(data_root)


def test_all_backend_manifests_match_the_exact_truthful_b0_contract() -> None:
    assert len(EXPECTED_MANIFESTS) == 8
    for relative_path, expected in EXPECTED_MANIFESTS.items():
        manifest = json.loads((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
        assert manifest == expected, relative_path


def test_package_check_helper_rejects_unknown_distribution_identity(tmp_path: Path) -> None:
    common = REPO_ROOT / "scripts/ci/_common.sh"
    result = subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; run_python_package_checks missing-evonn-distribution EvoNN-Shared evonn_shared shared',
            "bash",
            str(common),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode != 0
    assert "missing-evonn-distribution" in result.stderr


@pytest.mark.all_check_scripts
def test_all_named_check_scripts_execute_real_locked_checks_from_another_directory(tmp_path: Path) -> None:
    scripts_dir = REPO_ROOT / "scripts/ci"
    scripts = {path.name: path for path in scripts_dir.glob("*-checks.sh")}
    assert set(scripts) == ALL_CHECK_SCRIPTS

    environment = os.environ.copy()
    environment["UV_PYTHON"] = sys.executable
    for name in sorted(CHECK_SCRIPTS):
        script = scripts[name]
        assert os.access(script, os.X_OK), f"{name} must be executable"
        result = subprocess.run(
            [str(script)],
            cwd=tmp_path,
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert result.returncode == 0, f"{name} failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def test_single_root_lockfile_is_current() -> None:
    internal_trees = {".git", ".claude", ".superpowers", ".venv", ".pytest_cache"}
    lockfiles = [
        path for path in REPO_ROOT.rglob("uv.lock") if not internal_trees.intersection(path.parts)
    ]
    assert lockfiles == [REPO_ROOT / "uv.lock"]
    subprocess.run(["uv", "lock", "--check"], cwd=REPO_ROOT, check=True, timeout=120)
