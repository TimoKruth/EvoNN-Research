"""Current exact dependency contract for the EvoNN uv workspace."""

from __future__ import annotations

from typing import NamedTuple


class WorkspaceDependencyContract(NamedTuple):
    directory: str
    distribution: str
    dependencies: tuple[str, ...]


WORKSPACE_DEPENDENCY_CONTRACT_VERSION = "1.0.0"
ENGINE_DEPENDENCIES = (
    "evonn-shared",
    "numpy>=2.1,<3",
    "mlx>=0.25,<1; sys_platform == 'darwin' and platform_machine == 'arm64'",
)
WORKSPACE_DEPENDENCY_CONTRACTS = (
    WorkspaceDependencyContract(
        "EvoNN-Shared",
        "evonn-shared",
        (
            "pydantic>=2.11,<3",
            "PyYAML>=6.0.2,<7",
        ),
    ),
    WorkspaceDependencyContract("EvoNN-Compare", "evonn-compare", ("evonn-shared",)),
    WorkspaceDependencyContract("EvoNN-Contenders", "evonn-contenders", ("evonn-shared",)),
    WorkspaceDependencyContract("EvoNN-Prism", "evonn-prism", ENGINE_DEPENDENCIES),
    WorkspaceDependencyContract("EvoNN-Topograph", "evonn-topograph", ENGINE_DEPENDENCIES),
    WorkspaceDependencyContract("EvoNN-Stratograph", "evonn-stratograph", ENGINE_DEPENDENCIES),
    WorkspaceDependencyContract("EvoNN-Primordia", "evonn-primordia", ENGINE_DEPENDENCIES),
)
WORKSPACE_DEPENDENCY_BY_DIRECTORY = {
    package.directory: package for package in WORKSPACE_DEPENDENCY_CONTRACTS
}
WORKSPACE_DEPENDENCY_BY_DISTRIBUTION = {
    package.distribution: package for package in WORKSPACE_DEPENDENCY_CONTRACTS
}
