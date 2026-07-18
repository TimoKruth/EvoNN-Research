import evonn_shared


def test_installed_package_identity() -> None:
    assert evonn_shared.SYSTEM == "shared"
    assert evonn_shared.__version__ == "0.0.0"
