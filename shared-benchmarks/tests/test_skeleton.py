from evonn_shared.benchmarks import resolve_data_root, validate_data_skeleton


def test_repository_data_skeleton_is_valid() -> None:
    data_root = resolve_data_root()
    assert validate_data_skeleton(data_root) == data_root
