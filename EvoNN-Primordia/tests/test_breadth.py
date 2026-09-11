"""Scientific breadth, numerical semantics, and legacy identity contracts."""
import json
from random import Random

import numpy as np
import pytest

from evonn_shared.active_catalog import get_benchmark
from evonn_shared.weight_cache import WeightCache
from evonn_primordia.compiler import compile_genome
from evonn_primordia.genome import Primitive, PrimitiveGenome, fresh_genome, mutate_broad, BREADTH_OPERATORS
from evonn_primordia.search import Search
from evonn_primordia.training import TrainConfig, fit


def forward(model, x):
    b = model.backend
    return b.numpy(model.forward({k: b.array(v) for k, v in model.weights.items()}, b.array(x)))


def test_legacy_encoding_is_byte_semantically_unchanged():
    payload = dict(width=4, primitives=[dict(operator="dense", activation="tanh", merge="replace")],
                   learning_rate=.006, weight_decay=.001)
    genome = PrimitiveGenome.model_validate(payload)
    assert genome.model_dump(mode="json") == payload
    assert genome.genome_id == "a4b062ad4fa01483103901da28988a2a21e9c06a27595a4d55f6b86ab78e0eb8"
    with pytest.raises(ValueError, match="v1"):
        PrimitiveGenome(width=25, primitives=(Primitive(),))
    with pytest.raises(ValueError, match="v1"):
        PrimitiveGenome(primitives=(Primitive(operator="identity"),))


@pytest.mark.parametrize("backend", ["numpy_fallback", "mlx_native"])
def test_v2_growth_preserves_function_and_branched_lag_circuit_trains(backend):
    if backend == "mlx_native":
        pytest.importorskip("mlx.core")
    genome = PrimitiveGenome(version=2, width=16, primitives=(Primitive(), Primitive(operator="gate")),
                             temporal_mode="lag", temporal_lag=1)
    child, _ = mutate_broad(genome, Random(3), operation="grow")
    original = compile_genome(genome, (4,), 5, "tokens", "language_modeling", backend=backend, seed=8)
    grown = compile_genome(child, (4,), 5, "tokens", "language_modeling", backend=backend, seed=9)
    cache = WeightCache(2)
    cache.put("probe", genome.genome_id, "primitive", genome.family, original.weights)
    inherited = cache.inherit(grown, namespace="probe", identity=child.genome_id,
                                    topology="primitive", family=child.family, parents=[genome.genome_id])
    assert inherited["copied_parameters"] == grown.parameter_count
    x = np.array([[0, 1, 2, 3], [1, 0, 2, 3]], dtype=np.float32)
    np.testing.assert_allclose(forward(original, x), forward(grown, x), rtol=1e-6, atol=1e-7)
    assert not np.allclose(forward(original, x)[0, 2], forward(original, x)[1, 2])
    altered = x.copy()
    altered[:, 3] = 4
    np.testing.assert_array_equal(forward(original, x)[:, :3], forward(original, altered)[:, :3])
    branched = PrimitiveGenome(version=2, width=16, primitives=(Primitive(), Primitive(operator="sparse"), Primitive()),
                               sources=((0,), (0,), (1, 2)), sparse_offsets=(0, 2, 4), temporal_mode="lag")
    model = compile_genome(branched, (4,), 5, "tokens", "language_modeling", backend=backend)
    result = fit(model, x, x.astype(int), x, x.astype(int), task="language_modeling",
                 config=TrainConfig(epochs=2), seed=1)
    assert result["weights_changed"] and result["updates"] == 2
    assert len(result["behavior_descriptor"]) == 32
    assert len(result["validation_curve"]) == 2


def test_v2_rejects_cycles_dead_nodes_and_oversized_envelopes():
    for sources in [((1,), (1,)), ((0,), (0,)), ((0,), (1, 1))]:
        with pytest.raises(ValueError):
            PrimitiveGenome(version=2, primitives=(Primitive(), Primitive()), sources=sources)
    with pytest.raises(ValueError):
        Search([get_benchmark("iris_classification")], seed=1, max_width=257)
    for payload in [dict(version=True), dict(version=2, sparse_offsets=[True]),
                    dict(version=2, sources=[[0.0]])]:
        with pytest.raises(ValueError):
            PrimitiveGenome(primitives=(Primitive(),), **payload)


def test_motifs_can_duplicate_composed_subcircuits():
    genome = PrimitiveGenome(version=2, primitives=(Primitive(), Primitive(operator="gate"), Primitive(operator="sparse")))
    children = [mutate_broad(genome, Random(seed), operation="motif", max_depth=8)[0] for seed in range(12)]
    assert any(len(child.primitives) > len(genome.primitives) + 1 for child in children)
    for child in children:
        compile_genome(child, (4,), 2, "tabular", "classification")


def test_identity_primitive_still_obeys_product_merge():
    models = [compile_genome(PrimitiveGenome(version=2, primitives=(Primitive(operator="identity", merge=merge),)),
                             (2,), 2, "tabular", "classification", seed=9) for merge in ("replace", "product")]
    assert not np.allclose(forward(models[0], [[1., 2.]]), forward(models[1], [[1., 2.]]))


def test_all_operators_remain_reachable_and_envelope_is_respected():
    rng = Random(91)
    genome = fresh_genome(rng, max_width=64, max_depth=12)
    widths, depths = set(), set()
    for index in range(480):
        genome, op = mutate_broad(genome, rng, max_width=64, max_depth=12,
                                  operation=BREADTH_OPERATORS[index % len(BREADTH_OPERATORS)])
        assert op == BREADTH_OPERATORS[index % len(BREADTH_OPERATORS)]
        assert PrimitiveGenome.model_validate(genome.model_dump(mode="json")) == genome
        assert 2 <= genome.width <= 64 and 1 <= len(genome.primitives) <= 12
        widths.add(genome.width)
        depths.add(len(genome.primitives))
        compile_genome(genome, (4,), 3, "image", "classification")
    assert max(widths) > 24 and max(depths) > 2


def test_weak_lineages_get_patient_and_young_slots_and_resume_is_exact():
    definition = get_benchmark("iris_classification")
    search = Search([definition], seed=13, population_size=4)
    seen = []
    weak_parents = set()
    for i in range(80):
        restored = Search([definition], seed=999, state=json.loads(json.dumps(search.state())))
        assert search.candidate(definition.id) == restored.candidate(definition.id)
        assert search.proposal(definition.id) == restored.proposal(definition.id)
        proposal = search.proposal(definition.id)
        seen.append(proposal["lane"])
        genome = search.candidate(definition.id)
        model = search.compile(genome, definition)
        if proposal["fresh"]:
            assert search.inherit(model, definition.id, "probe")["mode"] == "none"
        if proposal["lane"] in {"young", "patient", "reservoir"}:
            weak_parents.update(proposal["parents"])
        result = dict(status="ok", score=1 if i == 0 else -float(i), parameter_count=model.parameter_count,
                      updates=3, behavior_descriptor=[i / 80, (i % 7) / 7])
        for target in (search, restored):
            target.observe(definition.id, genome, result)
        assert search.state() == restored.state()
    assert set(seen) == {"founder", "quality", "novelty", "young", "reservoir", "fresh", "patient", "fresh_retrain", "cost"}
    assert len(weak_parents) > 8
    state = search.benchmarks[definition.id]
    assert len(state["archive"]) == 8 and len(state["reservoir"]) == 32
    assert state["exploration"]["lanes"]["patient"] > 0


def test_failed_candidates_remain_in_score_independent_retention():
    definition = get_benchmark("iris_classification")
    search = Search([definition], seed=9)
    genome = search.candidate(definition.id)
    search.observe(definition.id, genome, dict(status="failed", reason="training wall-clock cap reached"))
    state = search.benchmarks[definition.id]
    assert not state["archive"]
    assert state["reservoir"][0]["identity"] == genome.genome_id
    assert state["exploration"]["resource_deferred"] == 1


def test_learning_progress_floor_and_patient_budget():
    genome = PrimitiveGenome(version=2, primitives=(Primitive(),))
    x = np.zeros((8, 2), np.float32)
    y = np.zeros(8, int)
    for minimum, patience, expected in [(4, 1, 4), (4, 8, 8)]:
        model = compile_genome(genome, (2,), 2, "tabular", "classification")
        result = fit(model, x, y, x, y, task="classification", seed=0,
                     config=TrainConfig(epochs=8, min_epochs=minimum, patience=patience,
                                        learning_rate=1e-30, weight_decay=0))
        assert result["epochs"] == expected
        assert len(result["validation_curve"]) == expected


def test_legacy_search_state_remains_restorable():
    definition = get_benchmark("iris_classification")
    search = Search([definition], seed=13, search_policy="legacy_v1")
    assert "search_policy" not in search.state()
    restored = Search([definition], seed=999, state=json.loads(json.dumps(search.state())))
    assert restored.policy == "legacy_v1"
    assert restored.state() == search.state()


def test_fresh_retraining_cannot_overwrite_better_inherited_weights():
    definition = get_benchmark("iris_classification")
    search = Search([definition], seed=4)
    genome = search.candidate(definition.id)
    model = search.compile(genome, definition)
    for weight in model.weights.values():
        weight[:] = 1
    search.remember(model, "probe", dict(score=.9))
    for weight in model.weights.values():
        weight[:] = -1
    search.remember(model, "probe", dict(score=.2))
    entry = search.cache.entries["probe:" + genome.genome_id]
    assert all(np.all(np.asarray(weight) == 1) for weight in entry["weights"].values())
    restored = Search([definition], seed=9, state=json.loads(json.dumps(search.state())))
    assert restored.cache_quality == search.cache_quality


def test_missing_parent_does_not_inherit_unrelated_weights():
    definition = get_benchmark("iris_classification")
    search = Search([definition], seed=4)
    genome = search.candidate(definition.id)
    unrelated = fresh_genome(Random(7))
    model = search.compile(unrelated, definition)
    search.remember(model, "probe", dict(score=.9))
    search.benchmarks[definition.id]["proposal_meta"][0] = dict(lane="patient", fresh=False,
        parents=[genome.genome_id], operator="patient", baseline=0)
    model = search.compile(genome, definition)
    assert search.inherit(model, definition.id, "probe")["mode"] == "none"
