import shutil
from pathlib import Path

import pytest

from evonn_shared.benchmarks import find_data_skeleton_violations, resolve_data_root, validate_data_skeleton


def test_repository_data_skeleton_is_valid() -> None:
    data_root = resolve_data_root()
    assert validate_data_skeleton(data_root) == data_root


def test_symlinked_root_stops_before_external_content_inspection(tmp_path: Path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    (external / "runtime.py").write_text("eval('external')\n", encoding="utf-8")
    data_root = tmp_path / "shared-benchmarks"
    data_root.symlink_to(external, target_is_directory=True)

    assert find_data_skeleton_violations(data_root) == [
        (".", "symbolic link found in data-only skeleton")
    ]


def test_symlinked_descendant_is_not_inspected_after_diagnosis(tmp_path: Path) -> None:
    data_root = tmp_path / "shared-benchmarks"
    shutil.copytree(resolve_data_root(), data_root)
    external = tmp_path / "external-catalog"
    external.mkdir()
    (external / "runtime.py").write_text("eval('external')\n", encoding="utf-8")
    shutil.rmtree(data_root / "catalog")
    (data_root / "catalog").symlink_to(external, target_is_directory=True)

    violations = find_data_skeleton_violations(data_root)

    assert violations == [("catalog", "symbolic link found in data-only skeleton")]


def test_required_directory_replaced_by_file_is_rejected(tmp_path: Path) -> None:
    data_root = tmp_path / "shared-benchmarks"
    shutil.copytree(resolve_data_root(), data_root)
    shutil.rmtree(data_root / "catalog")
    (data_root / "catalog").write_text("not a directory\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Required shared benchmark directory is not a directory: catalog"):
        validate_data_skeleton(data_root)


def test_required_file_replaced_by_directory_is_rejected(tmp_path: Path) -> None:
    data_root = tmp_path / "shared-benchmarks"
    shutil.copytree(resolve_data_root(), data_root)
    (data_root / "README.md").unlink()
    (data_root / "README.md").mkdir()

    with pytest.raises(ValueError, match="Required shared benchmark file is not a file: README.md"):
        validate_data_skeleton(data_root)
