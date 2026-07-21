from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "EvoNN-Shared/src/evonn_shared/backend_contract.py"
sys.path.insert(0, str(REPO_ROOT / "EvoNN-Shared/src"))


def _contract():
    assert CONTRACT_PATH.is_file(), "canonical backend contract module is missing"
    from evonn_shared import backend_contract

    return backend_contract


def test_canonical_contract_declares_exact_workspace_and_engine_sets() -> None:
    contract = _contract()

    assert [package.directory for package in contract.PACKAGE_CONTRACTS] == [
        "EvoNN-Shared",
        "EvoNN-Compare",
        "EvoNN-Contenders",
        "EvoNN-Prism",
        "EvoNN-Topograph",
        "EvoNN-Stratograph",
        "EvoNN-Primordia",
    ]
    assert [engine.system for engine in contract.ENGINE_CONTRACTS] == [
        "prism",
        "topograph",
        "stratograph",
        "primordia",
    ]
    assert len(contract.EXPECTED_MANIFESTS) == 8
    assert [package.dependencies for package in contract.PACKAGE_CONTRACTS] == [
        (),
        ("evonn-shared",),
        ("evonn-shared",),
        contract.ENGINE_DEPENDENCIES,
        contract.ENGINE_DEPENDENCIES,
        contract.ENGINE_DEPENDENCIES,
        contract.ENGINE_DEPENDENCIES,
    ]
    assert contract.ENGINE_DEPENDENCIES == (
        "evonn-shared",
        "numpy>=2.1,<3",
        "mlx>=0.25,<1; sys_platform == 'darwin' and platform_machine == 'arm64'",
    )


def test_canonical_engine_contract_keeps_bootstrap_claims_unqualified() -> None:
    contract = _contract()

    for engine in contract.ENGINE_CONTRACTS:
        expected = contract.EXPECTED_MANIFESTS[engine.manifest_path]
        assert expected["capabilities"] == [contract.MLX_CAPABILITY, contract.NUMPY_CAPABILITY]
        assert all(capability["implemented"] is False for capability in expected["capabilities"])
        assert expected["evidence"] == {
            "scientific": False,
            "portability": False,
            "producer_conformance": False,
        }
