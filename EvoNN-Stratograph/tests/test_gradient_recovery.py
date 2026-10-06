"""Backward overflow recovery preserves finite updates and existing fit bounds."""
import math
import platform
import time
import numpy as np
import pytest
from stratograph.tensors import Backend
from stratograph.training import finite_gradients

BACKENDS=['numpy_fallback'] + (['mlx_native'] if platform.system()=='Darwin' and platform.machine()=='arm64' else [])


@pytest.mark.parametrize('name',BACKENDS)
def test_recovers_large_finite_mathematical_gradient_before_clipping(name):
    b=Backend(name)
    parameters={'x':b.array([0.])}
    def forward(p):
        return ((p['x']*1e20)*1e20+1).sum()
    with np.errstate(over='ignore',invalid='ignore'):
        value,grads,recovered=finite_gradients(b,forward,parameters,deadline=time.monotonic()+10)
    assert value==1.
    assert recovered
    assert grads['x'].dtype==np.float64
    np.testing.assert_allclose(grads['x'],[1e40],rtol=1e-6)
    norm=math.sqrt(sum(float(np.sum(v*v)) for v in grads.values()))
    clipped=(grads['x']/norm).astype(np.float32)
    np.testing.assert_array_equal(clipped,[1.])
    np.testing.assert_array_equal(b.numpy(parameters['x']),[0.])


def test_finite_gradients_return_original_objects_without_reexecution():
    original={'w':np.array([3.],dtype=np.float32)}
    class Counting:
        calls=0
        def gradients(self,forward,parameters):
            self.calls+=1
            return 2.,original
    b=Counting()
    value,grads,recovered=finite_gradients(b,None,{},deadline=time.monotonic()+10)
    assert value==2. and grads is original and not recovered and b.calls==1


@pytest.mark.parametrize('loss',[float('inf'),float('nan')])
def test_nonfinite_forward_loss_is_not_hidden(loss):
    class Broken:
        def gradients(self,forward,parameters):
            return loss,{'x':np.array([0.])}
    with pytest.raises(ValueError,match='nonfinite loss'):
        finite_gradients(Broken(),None,{},deadline=time.monotonic()+10)


def test_recovery_has_one_retry_and_existing_deadline_bounds():
    class Broken:
        calls=0
        def gradients(self,forward,parameters):
            self.calls+=1
            return 1.,{'x':np.array([float('nan')])}
        precise_gradients=gradients
    b=Broken()
    with pytest.raises(ValueError,match='float64 recovery'):
        finite_gradients(b,None,{},deadline=time.monotonic()+10)
    assert b.calls==2
    with pytest.raises(TimeoutError,match='wall-clock cap'):
        finite_gradients(b,None,{},deadline=time.monotonic()-1)
    assert b.calls==3


@pytest.mark.parametrize('name',BACKENDS)
def test_precision_context_is_restored_after_exception(name):
    b=Backend(name)
    native=b.mx
    def fail(parameters):
        assert b.mx is None and b.dtype==np.float64 and b.stable_backward
        assert parameters['x'].data.dtype==np.float64
        raise RuntimeError('probe')
    with pytest.raises(RuntimeError,match='probe'):
        b.precise_gradients(fail,{'x':b.array([1.])})
    assert b.mx is native and b.dtype==np.float32 and not b.stable_backward
