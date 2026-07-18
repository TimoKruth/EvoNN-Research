import prism


def test_installed_package_identity() -> None:
    assert prism.SYSTEM == "prism"
    assert prism.__version__ == "0.0.0"
