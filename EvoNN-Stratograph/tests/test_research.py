"""Behavioral acceptance tests for the versioned, breadth-preserving upgrade."""
from copy import deepcopy
from random import Random
import json
import numpy as np
import pytest

from evonn_shared.active_catalog import get_benchmark
from stratograph.compiler import compile_genome
from stratograph.genome import HierarchicalGenome, seed_genome, clone_cell, specialize
from stratograph.genome_v2 import seed, mutate, collapse
from stratograph.research import ResearchPolicy
from stratograph.search import Search
from stratograph.search_v2 import LANES
from stratograph.training import TrainConfig, fit


def genome(*, evaluator='proxy', normalization='none', variant='shared', index=1, **options):
    return seed('classification', 4, Random(9), policy=ResearchPolicy(evaluator=evaluator, normalization=normalization, **options).model_dump(), variant=variant, index=index)


def model(g, **options):
    return compile_genome(g, (4,), 2, 'tabular', 'classification', seed=8, **options)


def test_legacy_codec_and_identity_remain_exact():
    g = seed_genome('classification', 4)
    assert 'execution' not in g.model_dump()
    assert all('projection_seed' not in n for c in g.model_dump()['cells'] for n in c['nodes'])
    assert g.genome_id == '6b32c052ba0434a2669565f38d7c3db29b2a7240054c1d85edf3681867010ef7'
    assert HierarchicalGenome.model_validate_json(g.model_dump_json()) == g


def test_local_activation_edit_preserves_every_projection_and_randomization_is_explicit():
    g = genome()
    a = model(g)
    h = specialize(g, g.cells[0].id, Random(1))
    b = model(h)
    assert set(a.fixed) == set(b.fixed)
    for key in a.fixed:
        np.testing.assert_array_equal(a.fixed[key], b.fixed[key])
    x = np.random.default_rng(3).normal(size=(16, 4)).astype(np.float32)
    assert not np.allclose(a.features(x), b.features(x))
    changed, _ = mutate(g, Random(1), operation='projection-randomize')
    c = model(changed)
    assert any(not np.array_equal(value, c.fixed[key]) for key, value in a.fixed.items())


@pytest.mark.parametrize('evaluator', ['proxy', 'trainable'])
def test_clone_preserves_function_then_specializes_independently(evaluator):
    g = genome(evaluator=evaluator)
    h = clone_cell(g, g.macro_nodes[-1].id)
    a, b = model(g), model(h)
    x = np.random.default_rng(3).normal(size=(16, 4)).astype(np.float32)
    np.testing.assert_array_equal(a.features(x), b.features(x))
    changed = specialize(h, h.macro_nodes[-1].cell_id, Random(1))
    assert not np.allclose(b.features(x), model(changed).features(x))
    if evaluator == 'trainable':
        assert len(b.weights) > len(a.weights)
        assert len({id(c) for c in a.executors.values()}) == 1
        assert len({id(c) for c in b.executors.values()}) == 2


@pytest.mark.parametrize('backend', ['numpy_fallback', 'mlx_native'])
def test_trainable_cell_gradient_matches_finite_difference_and_updates(backend):
    import platform
    if backend == 'mlx_native' and (platform.system() != 'Darwin' or platform.machine() != 'arm64'):
        pytest.skip('native MLX requires Apple Silicon')
    g = genome(evaluator='trainable', normalization='rms')
    a = model(g, backend=backend)
    x = np.random.default_rng(4).normal(size=(24, 4)).astype(np.float32)
    b = a.backend
    p = {key: b.array(v) for key, v in a.weights.items()}
    def loss(params):
        output = a.forward(params, b.array(x[:4]))
        return (output * output).mean()
    _, grads = b.gradients(loss, p)
    key = next(k for k in grads if k.startswith('cell.'))
    index = np.unravel_index(np.abs(grads[key]).argmax(), grads[key].shape)
    original = a.weights[key][index]
    values = []
    for offset in [-.001, .001]:
        weights = {k: v.copy() for k, v in a.weights.items()}
        weights[key][index] = original + offset
        values.append(float(b.numpy(loss({k: b.array(v) for k, v in weights.items()}))))
    assert grads[key][index] == pytest.approx((values[1] - values[0]) / .002, rel=.04, abs=.001)
    y = (x[:, 0] > 0).astype(np.int64)
    result = fit(a, x[:16], y[:16], x[16:], y[16:], task='classification', config=TrainConfig(epochs=3), seed=1)
    assert result['hierarchy_weights_changed']
    assert result['updates'] == 3


def test_training_only_statistics_survive_serialization_and_batch_changes():
    g = genome(normalization='train_standard')
    a = model(g)
    train = np.random.default_rng(3).normal(size=(20, 4)).astype(np.float32)
    a.prepare_features(train)
    raw = a.features(train)
    mean, std = a.buffers['hierarchy_standard_v2']
    np.testing.assert_allclose(mean, raw.mean(axis=0))
    np.testing.assert_allclose(std, np.maximum(raw.std(axis=0), 1e-5))
    saved = deepcopy(a.buffers)
    x = train[:2]
    p = {k: a.backend.array(v) for k, v in a.weights.items()}
    left = a.backend.numpy(a.forward(p, a.backend.array(x)))
    right = a.backend.numpy(a.forward(p, a.backend.array(np.concatenate([x, train * 100]))))[:2]
    np.testing.assert_allclose(left, right, rtol=1e-5, atol=1e-6)
    other = model(HierarchicalGenome.model_validate_json(g.model_dump_json()))
    other.buffers = {k: tuple(np.asarray(v, dtype=np.float32) for v in values) for k, values in json.loads(json.dumps({k: [v.tolist() for v in vs] for k, vs in saved.items()})).items()}
    np.testing.assert_allclose(left, other.backend.numpy(other.forward(p, other.backend.array(x))), rtol=1e-6)
    del other.buffers['hierarchy_standard_v2']
    with pytest.raises(ValueError, match='missing'):
        other.forward(p, other.backend.array(x))


@pytest.mark.parametrize('evaluator', ['proxy', 'trainable'])
@pytest.mark.parametrize('normalization', ['none', 'rms', 'train_standard'])
def test_lm_remains_causal_across_representations(evaluator, normalization):
    policy = ResearchPolicy(evaluator=evaluator, normalization=normalization, readout='all', residual=True)
    g = seed('language_modeling', 4, Random(9), policy=policy.model_dump(), index=2)
    a = compile_genome(g, (4,), 8, 'sequence', 'language_modeling')
    x = np.array([[1, 2, 3, 4], [2, 1, 4, 6]], dtype=np.float32)
    a.prepare_features(x)
    y = x.copy()
    y[:, 2:] = 7
    p = {k: a.backend.array(v) for k, v in a.weights.items()}
    left = a.backend.numpy(a.forward(p, a.backend.array(x)))
    right = a.backend.numpy(a.forward(p, a.backend.array(y)))
    np.testing.assert_allclose(left[:, :2], right[:, :2], rtol=1e-6, atol=1e-6)


@pytest.mark.parametrize('variant', ['shared', 'flat', 'unshared', 'no-clone', 'no-motif-bias'])
def test_reachable_structures_and_mutation_stress(variant):
    g = genome(variant=variant)
    rng = Random(13)
    widths, primitives, counts = set(), set(), set()
    for _ in range(500):
        g, _ = mutate(g, rng, motif_bank=g.cells)
        HierarchicalGenome.model_validate_json(g.model_dump_json())
        widths.update(n.width for c in g.cells for n in c.nodes)
        primitives.update(n.primitive for c in g.cells for n in c.nodes)
        counts.add(len(g.macro_nodes))
        if variant == 'unshared':
            assert g.reuse_ratio == 0
    assert max(widths) > 32
    assert {'projection', 'identity', 'gate', 'sequence', 'residual'} <= primitives
    if variant != 'flat':
        assert 1 in counts and max(counts) > 1
    else:
        assert counts == {1}


def test_exploration_slots_revisit_weak_candidates_and_resume_identically():
    definition = get_benchmark('iris_classification')
    search = Search([definition], seed=1, research=ResearchPolicy(), population_size=4)
    resumed = None
    weak_revisited = False
    for step in range(64):
        g = search.candidate(definition.id)
        st = search.benchmarks[definition.id]
        proposal = st['proposal_metadata'][st['cursor']]
        weak_revisited |= proposal['lane'].startswith('revisit_') and proposal.get('baseline') == 0
        result = dict(status='ok', score=float(step % 4), parameter_count=2, behavior=[float(step % 3), 0.])
        if resumed is not None:
            assert resumed.candidate(definition.id) == g
            resumed.observe(definition.id, g, result)
        search.observe(definition.id, g, result)
        if step == 20:
            resumed = Search([definition], seed=99, research=None, state=deepcopy(search.state()))
        if resumed is not None:
            assert resumed.state() == search.state()
    counts = search.telemetry()['selection_counts'][definition.id]
    assert set(LANES) <= set(counts)
    assert any(entry['quality'] == 0 for entry in search.benchmarks[definition.id]['reservoir'])
    assert counts['revisit_random'] > 0 and counts['fresh'] > 0
    assert weak_revisited


def test_inheritance_does_not_copy_head_across_changed_features():
    definition = get_benchmark('iris_classification')
    search = Search([definition], seed=1, research=ResearchPolicy(evaluator='trainable', normalization='none'))
    g = search.candidate(definition.id)
    a = search.compile(g, definition)
    for value in a.weights.values():
        value[:] = .123
    search.remember(a, 'test')
    changed = specialize(g, g.cells[0].id, Random(1))
    b = search.compile(changed, definition)
    initial_head = b.weights['head.w'].copy()
    inherited = search.inherit(b, definition.id, 'test')
    assert inherited['mode'] == 'partial'
    np.testing.assert_array_equal(b.weights['head.w'], initial_head)
    assert any(np.all(value == .123) for key, value in b.weights.items() if key.startswith('cell.'))
    c = search.compile(g, definition)
    assert search.inherit(c, definition.id, 'test')['mode'] == 'exact'
    assert all(np.all(v == .123) for v in c.weights.values())


def test_macro_collapse_and_expansion_are_both_available():
    g = genome()
    h = collapse(g, g.output)
    assert len(h.macro_nodes) == 1
    expanded, _ = mutate(h, Random(1), operation='expand')
    assert len(expanded.macro_nodes) == 2


def test_unsharing_alone_preserves_initial_features():
    shared, unshared = genome(variant='shared'), genome(variant='unshared')
    x = np.random.default_rng(3).normal(size=(8, 4)).astype(np.float32)
    np.testing.assert_array_equal(model(shared).features(x), model(unshared).features(x))


def test_representation_ablation_can_freeze_normalization_and_readout():
    g = genome(evolve_representation=False)
    for operation in ('representation', 'head'):
        with pytest.raises(ValueError, match='unavailable'):
            mutate(g, Random(1), operation=operation)
    policy = ResearchPolicy(max_macro_nodes=1, max_cell_nodes=1, max_width=4)
    g = seed('classification', 4, Random(1), policy=policy.model_dump(), index=5)
    for _ in range(100):
        g, _ = mutate(g, Random(_))
        assert len(g.macro_nodes) == 1 and all(len(c.nodes) == 1 for c in g.cells)


def test_diagnostics_detect_screening_rank_reversal_without_claiming_causality():
    from evonn_shared.hierarchy_diagnostics import research_diagnostics
    g = genome().model_dump(mode='json')
    rows = []
    for index, (identity, score, reduction) in enumerate([('a', .8, 1), ('b', .7, 1), ('a', .81, 0), ('b', .9, 0)]):
        rows.append(dict(benchmark_id='x', genome=g, genome_id=identity, outcome_id=str(index), status='ok',
                         score=score, screen_epoch_reduction=reduction, allocated_epochs=2-reduction,
                         charged=1, updates=3, research_evaluation={'lane': 'revisit_random'}))
    panel = research_diagnostics(rows)['benchmarks']['x']
    assert panel['screening_rank_check'] == dict(paired_genotypes=2, comparable_pairs=1, reversals=1, status='available')
    assert panel['fits_charged'] == 4 and panel['optimizer_updates'] == 12


def test_learned_clone_inheritance_preserves_predictions_and_normalization():
    definition = get_benchmark('iris_classification')
    search = Search([definition], seed=1, research=ResearchPolicy(evaluator='trainable'))
    g = seed('classification', 4, Random(9), policy=search.research.model_dump(), index=1)
    a = search.compile(g, definition)
    x = np.random.default_rng(4).normal(size=(20, 4)).astype(np.float32)
    y = (x[:, 0] > 0).astype(np.int64)
    fit(a, x[:16], y[:16], x[16:], y[16:], task='classification', config=TrainConfig(epochs=2), seed=5)
    search.remember(a, 'same-data')
    cloned = clone_cell(g, g.macro_nodes[-1].id)
    b = search.compile(cloned, definition)
    inherited = search.inherit(b, definition.id, 'same-data')
    assert inherited['copied_parameters'] == b.parameter_count
    b.prepare_features(x * 100)  # inherited same-namespace statistics must remain frozen
    for key in a.buffers:
        for before, after in zip(a.buffers[key], b.buffers[key]):
            np.testing.assert_array_equal(before, after)
    left = a.backend.numpy(a.forward({k: a.backend.array(v) for k, v in a.weights.items()}, a.backend.array(x)))
    right = b.backend.numpy(b.forward({k: b.backend.array(v) for k, v in b.weights.items()}, b.backend.array(x)))
    np.testing.assert_array_equal(left, right)
    # Independent clone storage: changing the cloned matrix cannot change its sibling.
    cloned_key = next(k for k in b.weights if k.startswith('cell.' + cloned.cells[-1].parameter_id))
    sibling_key = next(k for k in b.weights if k.startswith('cell.' + cloned.cells[0].parameter_id))
    before = b.weights[sibling_key].copy()
    b.weights[cloned_key][:] = 0
    np.testing.assert_array_equal(before, b.weights[sibling_key])
