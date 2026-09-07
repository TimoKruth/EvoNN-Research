import numpy as np
import pytest
from evonn_shared.training import regression_target_stats, calibrate_regression_predictions

def test_regression_training_only_calibration_and_nonfinite_rejection():
    x = np.arange(5, dtype=float)
    y = 3 * x + 7
    np.testing.assert_allclose(
        calibrate_regression_predictions(train_pred=x, y_train=y, val_pred=np.array([10.0])), [37]
    )
    assert regression_target_stats(np.ones(4)) == (1, 1)
    with pytest.raises(ValueError):
        regression_target_stats(np.array([1, np.inf]))
