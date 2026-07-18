import shutil
from pathlib import Path

import pytest

from evonn_shared.benchmarks import resolve_data_root, validate_data_skeleton


def test_repository_data_skeleton_is_valid() -> None:
    data_root = resolve_data_root()
    assert validate_data_skeleton(data_root) == data_root


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
