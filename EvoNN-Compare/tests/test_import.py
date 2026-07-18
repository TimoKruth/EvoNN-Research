import evonn_compare


def test_installed_package_identity() -> None:
    assert evonn_compare.SYSTEM == "compare"
    assert evonn_compare.__version__ == "0.0.0"
