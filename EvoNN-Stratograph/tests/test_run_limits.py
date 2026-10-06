"""Run allowance can cover a whole study cell without relaxing fit limits."""
import pytest
from stratograph.config import RunConfig
from stratograph import run


@pytest.mark.parametrize('timeout', [1801., 19800., 81240., 86400.])
def test_long_run_allowance_reaches_training_validation(timeout, monkeypatch):
    assert RunConfig(timeout=timeout).timeout == timeout
    class ReachedTraining(Exception):
        pass
    def stop(**kwargs):
        assert kwargs['timeout'] == 120.
        raise ReachedTraining
    monkeypatch.setattr(run, 'TrainConfig', stop)
    with pytest.raises(ReachedTraining):
        run.run_engine(None, timeout=timeout, fit_timeout=120.)


@pytest.mark.parametrize('field,value', [('timeout',86401.),('timeout',float('inf')),
                                       ('timeout',0.),('fit_timeout',1801.),('fit_timeout',float('nan'))])
def test_invalid_limits_still_rejected(field,value):
    with pytest.raises(ValueError):
        RunConfig(**{field:value})
    with pytest.raises(ValueError):
        run.run_engine(None,**{field:value})
