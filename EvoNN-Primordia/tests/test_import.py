import evonn_primordia


def test_installed_package_identity() -> None:
    assert evonn_primordia.SYSTEM == "primordia"
    assert evonn_primordia.__version__ == "0.0.0"
