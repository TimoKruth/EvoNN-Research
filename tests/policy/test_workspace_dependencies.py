from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / "scripts/policy/validate_workspace_dependencies.py"
WORKSPACE_MEMBERS = (
    "EvoNN-Shared",
    "EvoNN-Compare",
    "EvoNN-Contenders",
    "EvoNN-Prism",
    "EvoNN-Topograph",
    "EvoNN-Stratograph",
    "EvoNN-Primordia",
)


def _validator():
    assert VALIDATOR_PATH.is_file(), "workspace dependency validator is missing"
    spec = importlib.util.spec_from_file_location("workspace_dependencies", VALIDATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _copy_workspace_manifests(target: Path) -> None:
    for directory in WORKSPACE_MEMBERS:
        source = REPO_ROOT / directory / "pyproject.toml"
        destination = target / directory / "pyproject.toml"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_checked_in_dependencies_match_exact_workspace_contract() -> None:
    assert _validator().validate_repository(REPO_ROOT) == []


@pytest.mark.parametrize(
    ("directory", "old", "new"),
    (
        ("EvoNN-Prism", "numpy>=2.1,<3", "numpy>=2.2,<3"),
        (
            "EvoNN-Prism",
            "platform_machine == 'arm64'",
            "platform_machine == 'x86_64'",
        ),
        (
            "EvoNN-Topograph",
            '''    "numpy>=2.1,<3",\n    "mlx>=0.25,<1; sys_platform == 'darwin' and platform_machine == 'arm64'",''',
            '''    "mlx>=0.25,<1; sys_platform == 'darwin' and platform_machine == 'arm64'",\n    "numpy>=2.1,<3",''',
        ),
        ("EvoNN-Stratograph", '    "numpy>=2.1,<3",\n', ""),
        (
            "EvoNN-Primordia",
            '    "numpy>=2.1,<3",\n',
            '    "numpy>=2.1,<3",\n    "scipy>=1.15,<2",\n',
        ),
    ),
    ids=("version", "marker", "order", "missing", "extra"),
)
def test_validator_rejects_exact_dependency_array_mutations(
    tmp_path: Path, directory: str, old: str, new: str
) -> None:
    _copy_workspace_manifests(tmp_path)
    manifest = tmp_path / directory / "pyproject.toml"
    _replace(manifest, old, new)

    diagnostics = _validator().validate_repository(tmp_path)

    assert len(diagnostics) == 1
    assert f"{directory}/pyproject.toml" in diagnostics[0]
    assert "project.dependencies must be exactly" in diagnostics[0]


def test_validator_keeps_contenders_without_scikit_learn_until_phase_1(tmp_path: Path) -> None:
    _copy_workspace_manifests(tmp_path)
    manifest = tmp_path / "EvoNN-Contenders/pyproject.toml"
    _replace(
        manifest,
        'dependencies = ["evonn-shared"]',
        'dependencies = ["evonn-shared", "scikit-learn"]',
    )

    diagnostics = _validator().validate_repository(tmp_path)

    assert any("project.dependencies must be exactly" in diagnostic for diagnostic in diagnostics)
    assert any("scikit-learn must remain undeclared" in diagnostic for diagnostic in diagnostics)


def test_validator_cli_passes_from_another_directory(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "Workspace dependency policy: PASS (7 exact project dependency arrays)"
