import topograph


def test_installed_package_identity() -> None:
    assert topograph.SYSTEM == "topograph"
    assert topograph.__version__ == "0.0.0"
