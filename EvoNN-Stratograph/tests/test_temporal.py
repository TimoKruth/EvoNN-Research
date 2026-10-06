"""Temporal reach, gradients, sharing and version compatibility, not quality claims."""
from copy import deepcopy
from random import Random
import platform

import numpy as np
import pytest

from stratograph.compiler import compile_genome
from stratograph.genome import HierarchicalGenome, clone_cell
from stratograph.genome_v2 import seed, mutate
from stratograph.research import ResearchPolicy
from stratograph.search import Search
from stratograph.training import TrainConfig, fit
from evonn_shared.active_catalog import get_benchmark


BACKENDS = ['numpy_fallback'] + (['mlx_native'] if platform.system() == 'Darwin' and platform.machine() == 'arm64' else [])


def make(mode='attention', backend='numpy_fallback', index=1, **kwargs):
    policy = ResearchPolicy(version=3, evaluator='trainable', normalization='rms',
                            temporal=mode, max_width=8, embedding_width=8, **kwargs)
    g = seed('language_modeling', 8, Random(9), policy=policy.model_dump(), index=index)
    return compile_genome(g, (8,), 5, 'sequence', 'language_modeling', backend=backend, seed=2)


def predict(model, x):
    b = model.backend
    return b.numpy(model.forward({k: b.array(v) for k, v in model.weights.items()}, b.array(x)))


def test_policy_roundtrip_keeps_v2_bytes_and_rejects_unversioned_options():
    old = ResearchPolicy()
    assert len(old.model_dump()) == 14
    assert ResearchPolicy.model_validate_json(old.model_dump_json()) == old
    assert 'temporal' not in old.model_dump()
    with pytest.raises(ValueError, match='version 3'):
        ResearchPolicy(temporal='attention')
    with pytest.raises(ValueError, match='trainable'):
        ResearchPolicy(version=3)
    new = ResearchPolicy(version=3, evaluator='trainable')
    assert ResearchPolicy.model_validate_json(new.model_dump_json()) == new


@pytest.mark.parametrize('backend', BACKENDS)
@pytest.mark.parametrize('mode', ['prefix', 'attention', 'dilated', 'hybrid'])
@pytest.mark.parametrize('position', ['none', 'sinusoidal', 'relative'])
def test_temporal_models_are_causal_and_replayable(backend, mode, position):
    a = make(mode, backend, position=position)
    x = np.array([[0, 1, 2, 3, 4, 0, 1, 2], [1, 0, 3, 2, 0, 4, 2, 1]], dtype=np.float32)
    changed = x.copy()
    changed[:, 4:] = 4
    np.testing.assert_allclose(predict(a, x)[:, :4], predict(a, changed)[:, :4], atol=1e-6, rtol=1e-6)
    restored = compile_genome(HierarchicalGenome.model_validate_json(a.genome.model_dump_json()),
                              (8,), 5, 'sequence', 'language_modeling', backend=backend, seed=99)
    restored.weights = deepcopy(a.weights)
    np.testing.assert_array_equal(predict(a, x), predict(restored, x))


@pytest.mark.parametrize('backend', BACKENDS)
@pytest.mark.parametrize('mode', ['attention', 'dilated', 'hybrid'])
def test_temporal_and_embedding_gradients_match_finite_differences(backend, mode):
    a = make(mode, backend, index=0)
    b = a.backend
    x = np.array([[0, 1, 2, 3, 4, 0, 1, 2]], dtype=np.float32)
    def loss(p):
        logits = a.forward(p, b.array(x))
        return (logits * logits).mean()
    _, grads = b.gradients(loss, {k: b.array(v) for k, v in a.weights.items()})
    keys = ['input.embedding'] + [k for k in grads if '.temporal.' in k or 'residual_gate' in k]
    for key in keys:
        index = np.unravel_index(np.abs(grads[key]).argmax(), grads[key].shape)
        assert np.isfinite(grads[key]).all()
        assert np.abs(grads[key]).max() > 1e-9, key
        losses = []
        for offset in [-.003, .003]:
            weights = deepcopy(a.weights)
            weights[key][index] += offset
            losses.append(float(b.numpy(loss({k: b.array(v) for k, v in weights.items()}))))
        assert grads[key][index] == pytest.approx((losses[1] - losses[0]) / .006, rel=.08, abs=2e-5), key


def test_relative_attention_can_select_a_distant_lag_without_future_leakage():
    a = make(index=0)
    cell, node = a.genome.cells[0], a.genome.cells[0].nodes[0]
    prefix = f'cell.{cell.parameter_id}.{node.id}.temporal'
    for name in ('q', 'k'):
        a.weights[f'{prefix}.{name}'][:] = 0
    for name in ('v', 'out'):
        a.weights[f'{prefix}.{name}'][:] = np.eye(node.width)
    a.weights[f'{prefix}.relative_bias'][:] = -30
    a.weights[f'{prefix}.relative_bias'][5] = 30
    x = np.random.default_rng(4).normal(size=(2, 8, node.width)).astype(np.float32)
    b = a.backend
    output = b.numpy(a._temporal(b.array(x), cell, node, {k: b.array(v) for k, v in a.weights.items()}, False))
    np.testing.assert_allclose(output[:, 5:], x[:, :3], atol=1e-6)


def test_dilated_cell_can_select_an_ordered_lag():
    a = make('dilated', index=0)
    cell, node = a.genome.cells[0], a.genome.cells[0].nodes[0]
    prefix = f'cell.{cell.parameter_id}.{node.id}.temporal'
    a.weights[f'{prefix}.kernel'][:] = 0
    a.weights[f'{prefix}.kernel'][3] = 1  # taps 0, 1, 2, 4
    a.weights[f'{prefix}.conv_out'][:] = np.eye(node.width)
    x = np.random.default_rng(4).normal(size=(2, 8, node.width)).astype(np.float32)
    b = a.backend
    output = b.numpy(a._temporal(b.array(x), cell, node, {k: b.array(v) for k, v in a.weights.items()}, False))
    np.testing.assert_array_equal(output[:, 4:], x[:, :4])
    np.testing.assert_array_equal(output[:, :4], np.zeros_like(output[:, :4]))


@pytest.mark.parametrize('mode', ['attention', 'dilated', 'hybrid'])
def test_learned_clones_inherit_all_temporal_weights_and_keep_predictions(mode):
    definition = get_benchmark('shakespeare_byte_lm')
    policy = ResearchPolicy(version=3, evaluator='trainable', normalization='rms', temporal=mode)
    search = Search([definition], seed=1, research=policy)
    g = seed('language_modeling', 8, Random(9), policy=policy.model_dump(), index=1)
    a = search.compile(g, definition)
    rng = np.random.default_rng(7)
    for value in a.weights.values():
        value += rng.normal(0, .01, value.shape).astype(np.float32)
    search.remember(a, 'same-data')
    cloned = clone_cell(g, g.macro_nodes[-1].id)
    other = search.compile(cloned, definition)
    inherited = search.inherit(other, definition.id, 'same-data')
    assert inherited['copied_parameters'] == other.parameter_count
    x = rng.integers(0, a.output_dim, (2, *a.input_shape)).astype(np.float32)
    np.testing.assert_allclose(predict(a, x), predict(other, x), atol=1e-6)
    assert len({id(v) for v in other.weights.values()}) == len(other.weights)


def test_v3_control_is_numerically_identical_to_v2():
    p2 = ResearchPolicy(evaluator='trainable', normalization='rms')
    p3 = ResearchPolicy(**{**p2.model_dump(), 'version': 3}, temporal='prefix', embedding_width=0,
                        position='none', cell_normalization='none', residual_mode='legacy',
                        merge='mean', readout_skip=False, select_initial=False, weight_decay_scope='all')
    models = [compile_genome(seed('language_modeling', 8, Random(9), policy=p.model_dump(), index=1),
                            (8,), 5, 'sequence', 'language_modeling', seed=2) for p in (p2, p3)]
    x = np.random.default_rng(9).integers(0, 5, (6, 8)).astype(np.float32)
    assert models[0].weights.keys() == models[1].weights.keys()
    np.testing.assert_array_equal(predict(models[0], x), predict(models[1], x))
    results = [fit(m, x[:4], x[:4].astype(int), x[4:], x[4:].astype(int), task='language_modeling',
                   config=TrainConfig(epochs=2), seed=4) for m in models]
    assert results[0]['score'] == results[1]['score']


def test_temporal_mutation_is_switchable_and_roundtrips():
    a = make(evolve_temporal=True)
    g, seen = a.genome, set()
    rng = Random(4)
    for _ in range(100):
        g, _ = mutate(g, rng, operation='temporal')
        seen.add(g.execution['temporal'])
        HierarchicalGenome.model_validate_json(g.model_dump_json())
    assert seen == {'prefix', 'attention', 'dilated', 'hybrid'}
    with pytest.raises(ValueError, match='unavailable'):
        mutate(make().genome, rng, operation='temporal')


def test_initial_candidate_is_retained_when_updates_degrade_validation():
    a = make(index=0)
    # A perfect constant-class predictor, deliberately trained on the opposite label.
    a.weights['readout.w'][:] = 0
    a.weights['readout.b'][:] = [-8, 8, -8, -8, -8]
    x = np.zeros((4, 8), dtype=np.float32)
    result = fit(a, x, np.zeros((4, 8), dtype=int), x, np.ones((4, 8), dtype=int),
                 task='language_modeling', config=TrainConfig(epochs=3, learning_rate=.1), seed=1)
    assert result['selected_epoch'] == 0
    assert result['validation_loss'] == result['initial_validation_loss']
    assert result['updates'] == 3 and len(result['validation_curve']) == 3
    assert not result['weights_changed']


@pytest.mark.parametrize('backend', BACKENDS)
def test_attention_learns_a_distant_copy_from_training_examples(backend):
    policy = ResearchPolicy(version=3, evaluator='trainable', normalization='rms',
                            max_width=8, embedding_width=8, head_width=8)
    g = seed('language_modeling', 8, Random(9), policy=policy.model_dump(), index=0)
    a = compile_genome(g, (8,), 4, 'text', 'language_modeling', backend=backend, seed=2)
    x = np.random.default_rng(10).integers(0, 4, (128, 8)).astype(np.float32)
    y = x[:, 0].astype(int)  # final output must recall the first token
    result = fit(a, x[:96], y[:96], x[96:], y[96:], task='language_modeling',
                 config=TrainConfig(epochs=60, patience=60, learning_rate=.02, batch_size=32), seed=3)
    assert result['validation_loss'] < result['initial_validation_loss'] * .25
    assert result['embedding_weights_changed'] and result['hierarchy_weights_changed']
    assert result['updates'] == 180


@pytest.mark.parametrize('backend', BACKENDS)
def test_learned_macro_merge_is_differentiable(backend):
    a = make(backend=backend, index=2)
    data = a.genome.model_dump(mode='json')
    data['macro_edges'].append(dict(source='m0', target='m2'))
    a = compile_genome(HierarchicalGenome.model_validate(data), (8,), 5, 'text', 'language_modeling', backend=backend)
    b = a.backend
    x = np.random.default_rng(7).integers(0, 5, (3, 8)).astype(np.float32)
    def loss(p):
        v = a.forward(p, b.array(x))
        return (v * v).mean()
    _, grads = b.gradients(loss, {k: b.array(v) for k, v in a.weights.items()})
    key = next(k for k in grads if '.merge_macro.' in k)
    index = int(np.abs(grads[key]).argmax())
    assert abs(grads[key][index]) > 1e-7
    losses = []
    for offset in [-.003, .003]:
        weights = deepcopy(a.weights)
        weights[key][index] += offset
        losses.append(float(b.numpy(loss({k: b.array(v) for k, v in weights.items()}))))
    assert grads[key][index] == pytest.approx((losses[1] - losses[0]) / .006, rel=.08, abs=2e-5)


def test_changed_temporal_program_does_not_inherit_an_incompatible_head():
    definition = get_benchmark('shakespeare_byte_lm')
    a = make('attention')
    search = Search([definition], seed=1, research=a.policy)
    # Compile against the real definition so both representations have one namespace.
    a = search.compile(a.genome, definition)
    a.weights['head.w'][:] = .123
    a.weights['input.embedding'][:] = .456
    search.remember(a, 'same-data')
    data = a.genome.model_dump(mode='json')
    data['execution']['temporal'] = 'dilated'
    other = search.compile(HierarchicalGenome.model_validate(data), definition)
    initial = other.weights['head.w'].copy()
    assert search.inherit(other, definition.id, 'same-data')['mode'] == 'partial'
    np.testing.assert_array_equal(other.weights['head.w'], initial)
    np.testing.assert_array_equal(other.weights['input.embedding'], a.weights['input.embedding'])
