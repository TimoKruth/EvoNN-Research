"""Immutable B0 bootstrap identities, dependencies, and capability contract."""

from __future__ import annotations

from typing import Any, NamedTuple


class PackageContract(NamedTuple):
    directory: str
    distribution: str
    module: str
    system: str
    manifest_path: str
    runtime_role: str
    dependencies: tuple[str, ...]


# Historical B0 bootstrap expectations; current workspace truth lives in workspace_contract.
ENGINE_DEPENDENCIES = (
    "evonn-shared",
    "numpy>=2.1,<3",
    "mlx>=0.25,<1; sys_platform == 'darwin' and platform_machine == 'arm64'",
)
MLX_CONDITION = (
    "Declared as mlx>=0.25,<1 with the exact marker "
    "sys_platform == 'darwin' and platform_machine == 'arm64'; bootstrap probe only, not qualified."
)
NUMPY_CONDITION = "Declared as numpy>=2.1,<3 on all engine platforms; bootstrap probe only, not qualified."
FALSE_EVIDENCE = {
    "scientific": False,
    "portability": False,
    "producer_conformance": False,
}
MLX_CAPABILITY = {
    "id": "mlx_native",
    "platforms": ["darwin-arm64"],
    "implemented": False,
    "dependency": "mlx",
    "dependency_condition": MLX_CONDITION,
}
NUMPY_CAPABILITY = {
    "id": "numpy_fallback",
    "platforms": ["darwin", "linux"],
    "implemented": False,
    "dependency": "numpy",
    "dependency_condition": NUMPY_CONDITION,
}
PACKAGE_CONTRACTS = (
    PackageContract(
        "EvoNN-Shared",
        "evonn-shared",
        "evonn_shared",
        "shared",
        "EvoNN-Shared/backend-capabilities.json",
        "contract_substrate_non_execution",
        (),
    ),
    PackageContract(
        "EvoNN-Compare",
        "evonn-compare",
        "evonn_compare",
        "compare",
        "EvoNN-Compare/backend-capabilities.json",
        "orchestration_non_execution",
        ("evonn-shared",),
    ),
    PackageContract(
        "EvoNN-Contenders",
        "evonn-contenders",
        "evonn_contenders",
        "contenders",
        "EvoNN-Contenders/backend-capabilities.json",
        "contender_skeleton",
        ("evonn-shared",),
    ),
    PackageContract(
        "EvoNN-Prism",
        "evonn-prism",
        "prism",
        "prism",
        "EvoNN-Prism/backend-capabilities.json",
        "engine_skeleton",
        ENGINE_DEPENDENCIES,
    ),
    PackageContract(
        "EvoNN-Topograph",
        "evonn-topograph",
        "topograph",
        "topograph",
        "EvoNN-Topograph/backend-capabilities.json",
        "engine_skeleton",
        ENGINE_DEPENDENCIES,
    ),
    PackageContract(
        "EvoNN-Stratograph",
        "evonn-stratograph",
        "stratograph",
        "stratograph",
        "EvoNN-Stratograph/backend-capabilities.json",
        "engine_skeleton",
        ENGINE_DEPENDENCIES,
    ),
    PackageContract(
        "EvoNN-Primordia",
        "evonn-primordia",
        "evonn_primordia",
        "primordia",
        "EvoNN-Primordia/backend-capabilities.json",
        "engine_skeleton",
        ENGINE_DEPENDENCIES,
    ),
)
ENGINE_CONTRACTS = tuple(package for package in PACKAGE_CONTRACTS if package.runtime_role == "engine_skeleton")
CONTENDERS_CAPABILITY = {
    "id": "sklearn_contender",
    "platforms": ["darwin", "linux"],
    "implemented": False,
    "dependency": "scikit-learn",
    "dependency_condition": "Not declared in B0; no contender runtime is implemented or qualified.",
}
EXPECTED_MANIFESTS: dict[str, dict[str, Any]] = {
    package.manifest_path: {
        "schema_version": "1.0.0",
        "system": package.system,
        "runtime_role": package.runtime_role,
        "capabilities": (
            [MLX_CAPABILITY, NUMPY_CAPABILITY]
            if package.runtime_role == "engine_skeleton"
            else ([CONTENDERS_CAPABILITY] if package.system == "contenders" else [])
        ),
        "evidence": FALSE_EVIDENCE,
    }
    for package in PACKAGE_CONTRACTS
}
EXPECTED_MANIFESTS["shared-benchmarks/backend-capabilities.json"] = {
    "schema_version": "1.0.0",
    "system": "shared-benchmarks",
    "runtime_role": "data_only",
    "capabilities": [],
    "evidence": FALSE_EVIDENCE,
}
PACKAGE_BY_SYSTEM = {package.system: package for package in PACKAGE_CONTRACTS}
PACKAGE_BY_DISTRIBUTION = {package.distribution: package for package in PACKAGE_CONTRACTS}
