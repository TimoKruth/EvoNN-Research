"""Cached fitting and dispatch must not import data-preparation frameworks."""
import subprocess
import sys

import pytest


@pytest.mark.parametrize("module", ["prism.cli", "topograph.cli", "stratograph.cli", "evonn_primordia.cli", "evonn_compare.campaign_worker"])
def test_fit_and_dispatch_imports_exclude_dataset_preparation(module):
    script = f"import importlib, sys; importlib.import_module({module!r}); assert not ({{'sklearn', 'pandas', 'pyarrow'}} & sys.modules.keys())"
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
