from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from evonn_shared.backend_contract import EXPECTED_MANIFESTS, PACKAGE_CONTRACTS

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / "scripts/policy/validate_backend_capabilities.py"
sys.path.insert(0, str(REPO_ROOT))


def _validator():
    assert VALIDATOR_PATH.is_file(), "backend capability validator is missing"
    from scripts.policy import validate_backend_capabilities

    return validate_backend_capabilities


def _copy_contract_surface(target: Path) -> None:
    for relative in EXPECTED_MANIFESTS:
        source = REPO_ROOT / relative
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    for package in PACKAGE_CONTRACTS:
        source = REPO_ROOT / package.directory / "pyproject.toml"
        destination = target / package.directory / "pyproject.toml"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def test_all_capability_manifests_match_package_metadata() -> None:
    assert _validator().validate_repository(REPO_ROOT) == []


def test_validator_detects_engine_dependency_drift(tmp_path: Path) -> None:
    _copy_contract_surface(tmp_path)
    manifest = tmp_path / "EvoNN-Prism/pyproject.toml"
    text = manifest.read_text(encoding="utf-8")
    manifest.write_text(text.replace("numpy>=2.1,<3", "numpy>=2.2,<3"), encoding="utf-8")

    diagnostics = _validator().validate_repository(tmp_path)

    assert any("EvoNN-Prism/pyproject.toml" in diagnostic and "dependencies" in diagnostic for diagnostic in diagnostics)


def test_validator_detects_manifest_dependency_condition_drift(tmp_path: Path) -> None:
    _copy_contract_surface(tmp_path)
    path = tmp_path / "EvoNN-Topograph/backend-capabilities.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["capabilities"][0]["dependency_condition"] = "MLX is available somehow."
    path.write_text(json.dumps(manifest), encoding="utf-8")

    diagnostics = _validator().validate_repository(tmp_path)

    assert any("EvoNN-Topograph/backend-capabilities.json" in diagnostic for diagnostic in diagnostics)


def test_validator_keeps_contenders_unimplemented_without_sklearn(tmp_path: Path) -> None:
    _copy_contract_surface(tmp_path)
    path = tmp_path / "EvoNN-Contenders/pyproject.toml"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace('dependencies = ["evonn-shared"]', 'dependencies = ["evonn-shared", "scikit-learn"]'), encoding="utf-8")

    diagnostics = _validator().validate_repository(tmp_path)

    assert any("scikit-learn" in diagnostic for diagnostic in diagnostics)
