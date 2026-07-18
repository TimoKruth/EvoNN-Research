import stratograph


def test_installed_package_identity() -> None:
    assert stratograph.SYSTEM == "stratograph"
    assert stratograph.__version__ == "0.0.0"
