from random import Random
import numpy as np
import pytest

from stratograph.compiler import compile_genome
from stratograph.genome import seed_genome,clone_cell,specialize
from stratograph.training import TrainConfig,fit


def test_shared_executors_process_different_inputs_and_clone_preserves_features():
    g=seed_genome('classification',4)
    model=compile_genome(g,(4,),2,'tabular','classification',seed=9)
    assert len({id(executor) for executor in model.executors.values()})==1
    cell=next(iter(model.cells.values()))
    assert not np.allclose(cell(np.ones((3,4))),cell(np.zeros((3,4))))
    x=np.random.default_rng(0).normal(size=(8,4)).astype(np.float32)
    clone=clone_cell(g,g.macro_nodes[-1].id)
    copied=compile_genome(clone,(4,),2,'tabular','classification',seed=9)
    np.testing.assert_array_equal(model.features(x),copied.features(x))
    changed=specialize(clone,clone.macro_nodes[-1].cell_id,Random(2))
    other=compile_genome(changed,(4,),2,'tabular','classification',seed=9)
    assert not np.allclose(copied.features(x),other.features(x))


@pytest.mark.parametrize('backend',['numpy_fallback','mlx_native'])
def test_proxy_head_has_real_gradients_and_lm_is_causal(backend):
    import platform
    if backend=='mlx_native' and (platform.system()!='Darwin' or platform.machine()!='arm64'):
        pytest.skip('native MLX requires Apple Silicon')
    g=seed_genome('classification',4)
    model=compile_genome(g,(4,),2,'tabular','classification',backend=backend,seed=1)
    x=np.random.default_rng(2).normal(size=(48,4)).astype(np.float32)
    y=(x[:,0]>0).astype(np.int64)
    before={key:value.copy() for key,value in model.weights.items()}
    result=fit(model,x[:32],y[:32],x[32:],y[32:],task='classification',config=TrainConfig(epochs=3),seed=7)
    assert result['updates']>0
    assert any(not np.array_equal(before[key],value) for key,value in model.weights.items())
    assert model.evaluator_fidelity=='hierarchy_features_trained_head'
    lm=compile_genome(seed_genome('language_modeling',4),(4,),8,'sequence','language_modeling',backend=backend)
    a=np.array([[1,2,3,4]],dtype=np.float32)
    b=np.array([[1,2,7,6]],dtype=np.float32)
    weights={key:lm.backend.array(value) for key,value in lm.weights.items()}
    left=lm.backend.numpy(lm.forward(weights,lm.backend.array(a)))
    right=lm.backend.numpy(lm.forward(weights,lm.backend.array(b)))
    np.testing.assert_allclose(left[:,:2],right[:,:2],atol=1e-6)
    assert not np.allclose(left[:,2:],right[:,2:])
