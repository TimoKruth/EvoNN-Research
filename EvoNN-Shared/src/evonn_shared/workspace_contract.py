"""Current exact dependency contract for the EvoNN uv workspace."""

from __future__ import annotations

from typing import NamedTuple


class WorkspaceDependencyContract(NamedTuple):
    directory: str
    distribution: str
    dependencies: tuple[str, ...]


WORKSPACE_DEPENDENCY_CONTRACT_VERSION = "4.0.0"
ENGINE_DEPENDENCIES = (
    "evonn-shared",
    "numpy>=2.1,<3",
    "mlx>=0.25,<1; sys_platform == 'darwin' and platform_machine == 'arm64'",
)
TRAINING_ENGINE_DEPENDENCIES = ("evonn-shared[datasets]", *ENGINE_DEPENDENCIES[1:])
WORKSPACE_DEPENDENCY_CONTRACTS = (
    WorkspaceDependencyContract(
        "EvoNN-Shared",
        "evonn-shared",
        (
            "numpy>=2.1,<3",
            "duckdb>=1.1,<2",
            "pydantic>=2.11,<3",
            "PyYAML>=6.0.2,<7",
        ),
    ),
    WorkspaceDependencyContract("EvoNN-Compare", "evonn-compare", ("evonn-shared", "numpy==2.4.4", "scipy==1.17.1")),
    WorkspaceDependencyContract("EvoNN-Contenders", "evonn-contenders", ("evonn-shared", "numpy==2.4.4", "scipy==1.17.1", "scikit-learn==1.8.0", "pandas==3.0.2", "openml==0.15.1", "PyYAML>=6.0.2,<7", "threadpoolctl==3.6.0",)),
    WorkspaceDependencyContract("EvoNN-Prism", "evonn-prism", TRAINING_ENGINE_DEPENDENCIES),
    WorkspaceDependencyContract("EvoNN-Topograph", "evonn-topograph", TRAINING_ENGINE_DEPENDENCIES),
    WorkspaceDependencyContract("EvoNN-Stratograph", "evonn-stratograph", ENGINE_DEPENDENCIES),
    WorkspaceDependencyContract("EvoNN-Primordia", "evonn-primordia", ENGINE_DEPENDENCIES),
)
WORKSPACE_DEPENDENCY_BY_DIRECTORY = {
    package.directory: package for package in WORKSPACE_DEPENDENCY_CONTRACTS
}
WORKSPACE_DEPENDENCY_BY_DISTRIBUTION = {
    package.distribution: package for package in WORKSPACE_DEPENDENCY_CONTRACTS
}
