from random import Random
import numpy as np
import pytest
from evonn_primordia.genome import Primitive, PrimitiveGenome, caps, mutate
from evonn_primordia.compiler import compile_genome
from evonn_primordia.training import fit, TrainConfig


@pytest.mark.parametrize('backend', ['numpy_fallback', 'mlx_native'])
def test_all_primitive_weights_receive_real_training(backend):
    if backend == 'mlx_native':
        pytest.importorskip('mlx.core')
    genome = PrimitiveGenome(primitives=tuple(Primitive(operator=name) for name in ['dense','gate','sparse','residual']))
    model = compile_genome(genome, (3,), 2, 'tabular', 'classification', backend=backend)
    original = {key:value.copy() for key,value in model.weights.items()}
    rng = np.random.default_rng(1)
    x = rng.normal(size=(24,3)).astype(np.float32)
    y = (x[:,0]>0).astype(int)
    result = fit(model,x,y,x,y,task='classification',config=TrainConfig(epochs=2),seed=1)
    assert result['updates'] > 0 and result['weights_changed']
    assert all(not np.array_equal(value,model.weights[key]) for key,value in original.items())


def test_clamps_cost_pressure_and_causality():
    genome = PrimitiveGenome(width=24, primitives=(Primitive(),)*4)
    child, operation = mutate(genome,Random(2),task='language_modeling',modality='tokens',cheap=True)
    assert operation == 'cheapen' and child.width <= 12 and len(child.primitives)<=2
    assert caps('classification','tabular',16)['epochs']==3
    model = compile_genome(child,(4,),5,'tokens','language_modeling')
    b=model.backend
    parameters={key:b.array(value) for key,value in model.weights.items()}
    a=b.numpy(model.forward(parameters,b.array([[0,1,2,3]])))
    c=b.numpy(model.forward(parameters,b.array([[0,1,4,4]])))
    np.testing.assert_array_equal(a[:,:2],c[:,:2])
    with pytest.raises(ValueError):
        compile_genome(genome,(4,),5,'tokens','language_modeling')
