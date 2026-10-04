"""Numerical, causal, replay and search contracts for the opt-in research arms."""
import json
from random import Random

import numpy as np
import pytest

from evonn_shared.active_catalog import get_benchmark
from evonn_shared.primordia_policy import PrimordiaResearchPolicy
from evonn_primordia.compiler import compile_genome
from evonn_primordia.genome import Primitive, PrimitiveGenome, mutate_broad
from evonn_primordia.research import fresh_research, mutate_research
from evonn_primordia.search import Search
from evonn_primordia.training import TrainConfig, fit


def evaluate(model, x, **kwargs):
    b = model.backend
    return b.numpy(model.forward({k: b.array(v) for k, v in model.weights.items()}, b.array(x), **kwargs))


@pytest.mark.parametrize('backend', ['numpy_fallback', 'mlx_native'])
@pytest.mark.parametrize('mode', ['attention', 'convolution', 'multiscale'])
def test_temporal_gradients_causality_and_updates(backend, mode):
    if backend == 'mlx_native':
        pytest.importorskip('mlx.core')
    genome = PrimitiveGenome(version=3, width=6, primitives=(Primitive(operator='residual'),),
                             temporal_mode=mode, normalization='rms', readout='skip')
    model = compile_genome(genome, (8,), 5, 'tokens', 'language_modeling', backend=backend, seed=3)
    rng = np.random.default_rng(9)
    x = rng.integers(0, 5, size=(12, 8))
    altered = x.copy()
    altered[:, 5:] = (altered[:, 5:] + 1) % 5
    np.testing.assert_allclose(evaluate(model, x)[:, :5], evaluate(model, altered)[:, :5], atol=1e-6)
    original = {k: v.copy() for k, v in model.weights.items()}
    targets = np.roll(x, 2, axis=1)
    result = fit(model, x, targets, x, targets, task='language_modeling',
                 config=TrainConfig(epochs=3, learning_rate=.01), seed=1)
    assert result['updates'] == 3 and np.isfinite(result['score'])
    assert all(not np.array_equal(v, model.weights[k]) for k, v in original.items()), mode
    # Native and portable execution must agree on the exact trained snapshot.
    portable = compile_genome(genome, (8,), 5, 'tokens', 'language_modeling', seed=3)
    portable.weights = model.weights
    np.testing.assert_allclose(evaluate(model, x), evaluate(portable, x), rtol=2e-5, atol=2e-5)


@pytest.mark.parametrize('backend', ['numpy_fallback', 'mlx_native'])
@pytest.mark.parametrize('mode', ['conv_flat', 'conv_pool'])
def test_spatial_patch_gradients_pooling_and_training(backend, mode):
    if backend == 'mlx_native':
        pytest.importorskip('mlx.core')
    genome = PrimitiveGenome(version=3, width=4, primitives=(Primitive(operator='gate'),),
                             spatial_mode=mode, normalization='rms', readout='skip', dropout=.1)
    model = compile_genome(genome, (5, 7, 2), 3, 'image', 'classification', backend=backend, seed=3)
    x = np.random.default_rng(4).normal(size=(12, 5, 7, 2)).astype(np.float32)
    original = {k: v.copy() for k, v in model.weights.items()}
    y = np.arange(len(x)) % 3
    result = fit(model, x, y, x, y, task='classification', config=TrainConfig(epochs=2), seed=9)
    assert result['updates'] == 2
    assert all(not np.array_equal(v, model.weights[k]) for k, v in original.items())
    assert evaluate(model, x).shape == (12, 3)
    np.testing.assert_array_equal(evaluate(model, x, training=True, seed=4), evaluate(model, x, training=True, seed=4))
    assert not np.array_equal(evaluate(model, x, training=True, seed=4), evaluate(model, x, training=True, seed=5))
    portable = compile_genome(genome, (5, 7, 2), 3, 'image', 'classification', seed=3)
    portable.weights = model.weights
    np.testing.assert_allclose(evaluate(model, x), evaluate(portable, x), rtol=2e-5, atol=2e-5)


@pytest.mark.parametrize('temporal,spatial', [('attention', 'flatten'), ('convolution', 'flatten'), ('prefix_mean', 'conv_pool')])
def test_new_paths_match_finite_difference(temporal, spatial):
    tokens = spatial == 'flatten'
    genome = PrimitiveGenome(version=3, width=3, primitives=(Primitive(operator='residual'),),
                             temporal_mode=temporal, spatial_mode=spatial, normalization='rms', readout='skip')
    x = np.array([[0, 1, 2, 3]]) if tokens else np.arange(9, dtype=np.float32).reshape(1, 3, 3) / 9
    model = compile_genome(genome, (4,) if tokens else (3, 3), 4, 'tokens' if tokens else 'image',
                           'language_modeling' if tokens else 'classification', seed=5)
    b = model.backend
    _, gradients = b.gradients(lambda p: (model.forward(p, b.array(x)) ** 2).mean(),
                                {k: b.array(v) for k, v in model.weights.items()})
    for key in model.weights:
        index = np.unravel_index(np.argmax(np.abs(gradients[key])), gradients[key].shape)
        before = model.weights[key][index].copy()
        values = []
        for delta in (.001, -.001):
            model.weights[key][index] = before + delta
            values.append(float(np.mean(evaluate(model, x) ** 2)))
        model.weights[key][index] = before
        numeric = (values[0] - values[1]) / .002
        np.testing.assert_allclose(gradients[key][index], numeric, rtol=.03, atol=.002, err_msg=key)


def test_initial_checkpoint_selection_keeps_best_but_charges_updates():
    genome = PrimitiveGenome(version=3, width=2, primitives=(Primitive(operator='identity'),))
    model = compile_genome(genome, (2,), 2, 'tabular', 'classification')
    model.weights['input.w'] = np.eye(2, dtype=np.float32)
    model.weights['output.w'] = np.eye(2, dtype=np.float32) * 3
    x = np.array([[1., 0.], [0., 1.]] * 8, dtype=np.float32)
    correct = np.array([0, 1] * 8)
    original = {k: v.copy() for k, v in model.weights.items()}
    result = fit(model, x, 1 - correct, x, correct, task='classification', seed=1,
                 config=TrainConfig(epochs=4, min_epochs=4, select_initial=True, learning_rate=.05))
    assert result['initial_checkpoint_selected'] and result['selected_epoch'] == 0
    assert result['updates'] == result['epochs'] == 4
    assert result['score'] == 1 and not result['weights_changed']
    assert all(np.array_equal(v, model.weights[k]) for k, v in original.items())
    assert result['validation_loss'] <= min(result['validation_curve'])


def test_v3_identity_growth_preserves_function_with_semantic_inheritance():
    definition = get_benchmark('iris_classification')
    search = Search([definition], seed=4, architecture_policy='expressive_v3')
    parent = search.candidate(definition.id)
    original = search.compile(parent, definition, seed=3)
    search.remember(original, 'probe', dict(score=.4))
    child, _ = mutate_broad(parent, Random(1), operation='grow')
    model = search.compile(child, definition, seed=12)
    inherited = search._inherit_v3(model, 'probe', [parent.genome_id])
    assert inherited['copied_parameters'] == model.parameter_count
    x = np.random.default_rng(5).normal(size=(4, 4))
    np.testing.assert_allclose(evaluate(original, x), evaluate(model, x), atol=1e-6)
    changed = PrimitiveGenome.model_validate({**parent.model_dump(), 'readout': 'skip' if parent.readout == 'last' else 'last'})
    model = search.compile(changed, definition, seed=13)
    output = model.weights['output.b'].copy()
    search._inherit_v3(model, 'probe', [parent.genome_id])
    np.testing.assert_array_equal(output, model.weights['output.b'])


@pytest.mark.parametrize('architecture', ['v2', 'temporal_v3', 'spatial_v3', 'expressive_v3',
                                        'attention_v3', 'convolution_v3', 'multiscale_v3', 'conv_flat_v3', 'conv_pool_v3'])
def test_research_search_roundtrip_and_all_scheduled_lanes(architecture):
    definitions = [get_benchmark(name) for name in ('iris_classification', 'digits_image', 'shakespeare_byte_lm')]
    search = Search(definitions, seed=53, architecture_policy=architecture, proposal_policy='progress_v3',
                    optimization_policy='stable_v3', max_width=16, max_depth=4)
    restored = Search(definitions, seed=999, state=json.loads(json.dumps(search.state())))
    lanes = set()
    for index in range(56):
        for definition in definitions:
            a, b = search.candidate(definition.id), restored.candidate(definition.id)
            assert a == b
            lanes.add(search.proposal(definition.id)['lane'])
            model = search.compile(a, definition)
            assert a.width <= 16 and len(a.primitives) <= 4
            result = dict(status='ok', score=index % 7, parameter_count=model.parameter_count, updates=3,
                          validation_curve=[1., 1. - (index % 5) / 10])
            search.observe(definition.id, a, result)
            restored.observe(definition.id, b, result)
        assert search.state() == restored.state()
        if index % 7 == 0:
            restored = Search(definitions, seed=999, state=json.loads(json.dumps(search.state())))
    assert {'elite', 'progress', 'recombine', 'fresh', 'reservoir', 'young', 'patient', 'fresh_retrain', 'cost', 'novelty'} <= lanes


@pytest.mark.parametrize('policy,benchmark,field,expected', [
    ('attention_v3', 'shakespeare_byte_lm', 'temporal_mode', 'attention'),
    ('convolution_v3', 'shakespeare_byte_lm', 'temporal_mode', 'convolution'),
    ('multiscale_v3', 'shakespeare_byte_lm', 'temporal_mode', 'multiscale'),
    ('conv_flat_v3', 'digits_image', 'spatial_mode', 'conv_flat'),
    ('conv_pool_v3', 'digits_image', 'spatial_mode', 'conv_pool')])
def test_fixed_family_arms_stay_fixed_under_mutation(policy, benchmark, field, expected):
    rng, definition = Random(6), get_benchmark(benchmark)
    genome = fresh_research(rng, definition, policy, max_width=16, max_depth=4)
    for _ in range(80):
        assert getattr(genome, field) == expected
        genome, _ = mutate_research(genome, rng, definition, policy, max_width=16, max_depth=4)


def test_legacy_serialization_and_invalid_combinations():
    v2 = PrimitiveGenome(version=2, primitives=(Primitive(),))
    assert not {'normalization', 'spatial_mode', 'dropout', 'readout', 'temporal_dilation'} & v2.model_dump().keys()
    for data in (dict(temporal_mode='attention'), dict(spatial_mode='conv_flat'), dict(readout='skip')):
        with pytest.raises(ValueError, match='v3'):
            PrimitiveGenome(version=2, primitives=(Primitive(),), **data)
    with pytest.raises(ValueError, match='legacy'):
        PrimordiaResearchPolicy(search_policy='legacy_v1', architecture_policy='expressive_v3')
    search = Search([get_benchmark('iris_classification')], seed=1, inheritance_policy='disabled')
    model = search.compile(search.candidate('iris_classification'), get_benchmark('iris_classification'))
    search.remember(model, 'probe', dict(score=1.))
    assert search.inherit(model, 'iris_classification', 'probe')['mode'] == 'none'


def test_stable_cache_can_progress_through_accuracy_ties():
    definition = get_benchmark('iris_classification')
    search = Search([definition], seed=3, optimization_policy='stable_v3')
    model = search.compile(search.candidate(definition.id), definition)
    key = 'probe:' + model.genome.genome_id
    for weight in model.weights.values():
        weight[:] = 1
    search.remember(model, 'probe', dict(score=.8, validation_loss=.5))
    for weight in model.weights.values():
        weight[:] = 2
    search.remember(model, 'probe', dict(score=.8, validation_loss=.4))
    assert search.cache_loss[key] == .4
    assert all(np.all(np.asarray(v) == 2) for v in search.cache.entries[key]['weights'].values())
    for weight in model.weights.values():
        weight[:] = 3
    search.remember(model, 'probe', dict(score=.7, validation_loss=.3))
    assert search.cache_loss[key] == .4
    restored = Search([definition], seed=99, state=json.loads(json.dumps(search.state())))
    assert restored.cache_loss == search.cache_loss
