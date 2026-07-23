from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "EvoNN-Shared/src/evonn_shared/workspace_contract.py"
sys.path.insert(0, str(REPO_ROOT / "EvoNN-Shared/src"))

EXPECTED_DEPENDENCY_CONTRACTS = (
    (
        "EvoNN-Shared",
        "evonn-shared",
        (
            "pydantic>=2.11,<3",
            "PyYAML>=6.0.2,<7",
        ),
    ),
    ("EvoNN-Compare", "evonn-compare", ("evonn-shared",)),
    ("EvoNN-Contenders", "evonn-contenders", ("evonn-shared",)),
    (
        "EvoNN-Prism",
        "evonn-prism",
        (
            "evonn-shared",
            "numpy>=2.1,<3",
            "mlx>=0.25,<1; sys_platform == 'darwin' and platform_machine == 'arm64'",
        ),
    ),
    (
        "EvoNN-Topograph",
        "evonn-topograph",
        (
            "evonn-shared",
            "numpy>=2.1,<3",
            "mlx>=0.25,<1; sys_platform == 'darwin' and platform_machine == 'arm64'",
        ),
    ),
    (
        "EvoNN-Stratograph",
        "evonn-stratograph",
        (
            "evonn-shared",
            "numpy>=2.1,<3",
            "mlx>=0.25,<1; sys_platform == 'darwin' and platform_machine == 'arm64'",
        ),
    ),
    (
        "EvoNN-Primordia",
        "evonn-primordia",
        (
            "evonn-shared",
            "numpy>=2.1,<3",
            "mlx>=0.25,<1; sys_platform == 'darwin' and platform_machine == 'arm64'",
        ),
    ),
)


def _contract():
    assert CONTRACT_PATH.is_file(), "canonical workspace dependency contract module is missing"
    return importlib.import_module("evonn_shared.workspace_contract")


def test_workspace_dependency_contract_has_exact_version_and_ordered_mapping() -> None:
    contract = _contract()

    assert contract.WORKSPACE_DEPENDENCY_CONTRACT_VERSION == "1.0.0"
    assert tuple(
        (package.directory, package.distribution, package.dependencies)
        for package in contract.WORKSPACE_DEPENDENCY_CONTRACTS
    ) == EXPECTED_DEPENDENCY_CONTRACTS


def test_workspace_dependency_contract_indexes_preserve_exact_contract_objects() -> None:
    contract = _contract()

    assert tuple(contract.WORKSPACE_DEPENDENCY_BY_DIRECTORY) == tuple(
        directory for directory, _, _ in EXPECTED_DEPENDENCY_CONTRACTS
    )
    assert tuple(contract.WORKSPACE_DEPENDENCY_BY_DISTRIBUTION) == tuple(
        distribution for _, distribution, _ in EXPECTED_DEPENDENCY_CONTRACTS
    )
    for package in contract.WORKSPACE_DEPENDENCY_CONTRACTS:
        assert contract.WORKSPACE_DEPENDENCY_BY_DIRECTORY[package.directory] is package
        assert contract.WORKSPACE_DEPENDENCY_BY_DISTRIBUTION[package.distribution] is package
