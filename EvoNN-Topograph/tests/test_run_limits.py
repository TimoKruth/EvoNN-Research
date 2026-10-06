import math

import pytest
from topograph.config import RunConfig
from topograph.run import run_engine
from topograph.search import Search


def test_budget_derived_total_allowance_preserves_fit_cap():
    config = RunConfig(timeout=256 * (120 + 30) + 600)
    assert config.timeout == 39000 and config.fit_timeout == 120


@pytest.mark.parametrize('value', [0, -1, 43201, math.inf, math.nan])
def test_invalid_total_allowance_rejected(value, tmp_path):
    with pytest.raises(ValueError):
        RunConfig(timeout=value)
    with pytest.raises(ValueError, match='run limit'):
        run_engine(Search, output_parent=tmp_path, timeout=value)


def test_fit_cap_still_bounded():
    with pytest.raises(ValueError):
        RunConfig(fit_timeout=1801)
