import evonn_contenders


def test_installed_package_identity() -> None:
    assert evonn_contenders.SYSTEM == "contenders"
    assert evonn_contenders.__version__ == "0.0.0"
