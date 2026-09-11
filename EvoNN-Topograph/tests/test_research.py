"""Behavioral contracts for the opt-in search, representation and evidence changes."""

from copy import deepcopy
import json
from random import Random
import numpy as np
import pytest
from evonn_shared.active_catalog import get_benchmark
from topograph.genome import Innovations, seed_genome, ExpertGene, GateConfig
from topograph.genome_v2 import GenomeV2, parse_genome
from topograph.compiler import compile_genome as legacy_compile
from topograph.compiler_v2 import compile_genome, parameter_estimate
from topograph.operators import CORE, BROAD, edit, crossover, execution_topology
from topograph.search_v2 import ResearchSearch
from topograph.research import allocate_training
from topograph.training import fit, TrainConfig


def base(operator="dense"):
    innovations = Innovations()
    return GenomeV2.model_validate(seed_genome(innovations, operator=operator).model_dump()), innovations


def variant(genome, **values):
    return GenomeV2.model_validate({**genome.model_dump(), **values})


def test_legacy_identity_and_flat_execution_stay_unchanged():
    old = seed_genome(Innovations())
    assert old.genome_id == "fc95b7481fec2f90b4ef2aff179bbb3beb11f5476909a07c54dacbc3aca854e4"
    new = GenomeV2.model_validate(old.model_dump())
    assert parse_genome(old.model_dump()).genome_id == old.genome_id
    assert parse_genome(new.model_dump()).genome_id == new.genome_id != old.genome_id
    a, b = legacy_compile(old, (4,), 2, seed=5), compile_genome(new, (4,), 2, seed=5)
    x = np.random.default_rng(1).normal(size=(7, 4))
    predictions = [
        m.backend.numpy(m.forward({k: m.backend.array(v) for k, v in m.weights.items()}, m.backend.array(x)))
        for m in (a, b)
    ]
    np.testing.assert_array_equal(*predictions)


@pytest.mark.parametrize("operator", CORE + BROAD)
def test_registered_operations_have_reachable_valid_effects(operator):
    definition = get_benchmark("shakespeare_byte_lm")
    genome, innovations = base(
        {"sparsity": "sparse_dense", "heads": "attention_lite", "convolution": "spatial"}.get(operator, "dense")
    )
    rng = Random(7)
    if operator in {"skip", "enable_edge"}:
        genome, _ = edit(genome, rng, innovations, "split", definition, broad=True)
        if operator == "skip":
            genome, _ = edit(genome, rng, innovations, "split", definition, broad=True)
    if operator in {"disable_edge", "disable_node", "enable_node"}:
        genome, _ = edit(genome, rng, innovations, "branch", definition, broad=True)
        if operator == "enable_node":
            genome, _ = edit(genome, rng, innovations, "disable_node", definition, broad=True)
    if operator == "gate":
        genome = variant(genome, experts=[ExpertGene(innovation=100), ExpertGene(innovation=101)], gate=GateConfig())
    if operator in {"adapter_width", "adapter_heads"}:
        genome = variant(genome, input_adapter="token_attention")
    if operator == "widen":
        genome = variant(genome, layers=[{**n.model_dump(), "normalization": "none"} for n in genome.layers])
    result = edit(genome, rng, innovations, operator, definition, broad=True)
    assert result is not None, operator
    child, details = result
    assert child.genome_id != genome.genome_id
    assert details["actual"] == details["requested"] == operator
    model = compile_genome(
        child,
        definition.input_shape,
        definition.output_dim,
        definition.input_modality.value,
        definition.task_kind.value,
    )
    assert parameter_estimate(child, definition) == model.parameter_count
    if operator in {"split", "skip", "branch", "disable_edge", "enable_edge", "disable_node", "enable_node"}:
        assert details["topology_changed"]


def test_inapplicable_skip_does_not_become_a_learning_rate_mutation():
    genome, innovations = base()
    assert edit(genome, Random(1), innovations, "skip", get_benchmark("iris_classification")) is None


def test_crossover_imports_donor_structure():
    a, innovations = base()
    b, _ = edit(a, Random(1), innovations, "split", get_benchmark("iris_classification"))
    child, action = crossover(a, b, Random(2), innovations)
    assert action == "branch_import"
    assert len(child.active_layers()) == len(a.active_layers()) + len(b.active_layers())
    assert execution_topology(child) != execution_topology(a)


def test_champion_reserves_its_own_niche_without_overwriting_another():
    definition = get_benchmark("iris_classification")
    search = ResearchSearch([definition], seed=1, variant="mechanics")
    founders = [g["layers"][0]["operator"] for g in search.benchmarks[definition.id]["population"]]
    for score in (0, 1, 2, 100):
        search.observe(definition.id, search.candidate(definition.id), dict(status="ok", score=score))
    allocation = search.benchmarks[definition.id]["allocations"][-1]
    assert len(allocation["allocated"]) == 4 and not allocation["deferred"]
    records = search.benchmarks[definition.id]["records"]
    assert {records[g]["genome"]["layers"][0]["operator"] for group in allocation["allocated"] for g in group} == set(
        founders
    )
    assert search.candidate(definition.id).layers[0].operator == founders[-1]


def test_archive_sources_and_operator_history_survive_exact_resume():
    definition = get_benchmark("iris_classification")
    search = ResearchSearch([definition], seed=13, variant="open")
    clone = None
    for step in range(64):
        if step == 19:
            clone = ResearchSearch([definition], seed=999, state=json.loads(json.dumps(search.state())))
        genome = search.candidate(definition.id)
        result = dict(status="ok", score=float(step % 3), outcome_id=f"a{step}", behavior_descriptor=[step / 64] * 16)
        if clone:
            assert clone.candidate(definition.id).genome_id == genome.genome_id
            assert clone.proposal(definition.id) == search.proposal(definition.id)
            clone.observe(definition.id, clone.candidate(definition.id), deepcopy(result))
        search.observe(definition.id, genome, deepcopy(result))
    assert search.state() == clone.state()
    state = search.benchmarks[definition.id]
    assert {"diversity", "uncertain", "reservoir", "immigrant", "fresh_control"} <= state["source_counts"].keys()
    assert len(state["records"]) == len(set(state["trace"]))
    assert state["elite"] is not None
    assert state["quality_cells"] and state["behavior_cells"] and state["pareto"]
    assert state["reservoir"] and all(g in state["records"] for g in state["reservoir"])


@pytest.mark.parametrize("operation", ["split", "branch", "widen"])
def test_parent_directed_inheritance_and_conservative_morphisms(operation):
    definition = get_benchmark("iris_classification")
    search = ResearchSearch([definition], seed=1, variant="open")
    parent, innovations = base()
    if operation == "widen":
        parent = variant(parent, layers=[{**n.model_dump(), "normalization": "none"} for n in parent.layers])
    s = search.benchmarks[definition.id]
    s["population"][0] = parent.model_dump(mode="json")
    model = search.compile(parent, definition, seed=3)
    search.remember(model, "namespace")
    search.observe(
        definition.id, parent, dict(status="ok", score=0.5, outcome_id="parent", epochs=4, updates=8, train_seconds=1)
    )
    child, details = edit(parent, Random(4), innovations, operation, definition, broad=True)
    s["population"][s["cursor"]] = child.model_dump(mode="json")
    s["proposals"][s["cursor"]] = search.proposal_record("species", parents=[parent.genome_id])
    s["proposals"][s["cursor"]].update(details)
    target = search.compile(child, definition, seed=8)
    result = search.inherit(target, definition.id, "namespace")
    assert result["mode"] == "partial" and result["copied_parameters"] > 0
    assert result["source_genome"] == parent.genome_id
    assert result["ancestor_attempts"] == ["parent"]
    if operation != "split":
        assert result["preservation_probe"]["passed"]
        x = np.random.default_rng(1).normal(size=(8, 4))
        outputs = [
            m.backend.numpy(m.forward({k: m.backend.array(v) for k, v in m.weights.items()}, m.backend.array(x)))
            for m in (model, target)
        ]
        np.testing.assert_allclose(*outputs, rtol=1e-5, atol=1e-6)
    s["proposals"][s["cursor"]]["fresh"] = True
    assert search.inherit(search.compile(child, definition), definition.id, "namespace")["mode"] == "none"


def test_low_coverage_does_not_receive_the_same_discount_as_full_transfer():
    low = dict(mode="partial", copied_parameters=3)
    high = dict(mode="partial", copied_parameters=100)
    assert allocate_training(12, 1, low, 100, variant="training")[1] == 12
    assert allocate_training(12, 1, high, 100, variant="training")[1] == 6
    assert allocate_training(12, 1, high, 100, protected=True, variant="training")[1] == 12


def test_weight_ancestry_is_isolated_even_for_identical_genomes_on_two_tasks():
    from topograph.search import architecture_id

    definitions = [get_benchmark(b) for b in ("iris_classification", "wine_classification")]
    search = ResearchSearch(definitions, seed=3, variant="open")
    genome, _ = base()
    for definition in definitions:
        search.benchmarks[definition.id]["population"][0] = genome.model_dump(mode="json")
        model = search.compile(genome, definition)
        search.remember(model, definition.id)
    for i, definition in enumerate(definitions):
        search.observe(definition.id, genome, dict(status="ok", score=0.5, outcome_id=f"candidate_{i:06d}"))
    for i, definition in enumerate(definitions):
        assert search.cache_history[definition.id + ":" + architecture_id(genome)] == [f"candidate_{i:06d}"]


@pytest.mark.parametrize("backend", ["numpy_fallback", "mlx_native"])
@pytest.mark.parametrize(
    "adapter,shape,modality,task",
    [("token_attention", (4,), "text", "language_modeling"), ("spatial", (4, 4), "image", "classification")],
)
def test_adapters_train_and_replay_with_nonzero_adapter_gradients(backend, adapter, shape, modality, task):
    if backend == "mlx_native":
        pytest.importorskip("mlx.core")
    genome, _ = base()
    genome = variant(genome, input_adapter=adapter, adapter_width=8, adapter_heads=2)
    model = compile_genome(genome, shape, 3, modality, task, backend=backend)
    rng = np.random.default_rng(4)
    x = rng.integers(0, 3, size=(12, *shape)) if modality == "text" else rng.normal(size=(12, *shape))
    old = deepcopy(model.weights)
    result = fit(
        model,
        x,
        np.arange(12) % 3,
        x,
        np.arange(12) % 3,
        task=task,
        config=TrainConfig(epochs=2, protected=True),
        seed=4,
    )
    assert result["epochs"] == 2 and len(result["validation_curve"]) == 2
    assert len(result["behavior_descriptor"]) == 16
    assert any(not np.array_equal(old[k], v) for k, v in model.weights.items() if k.startswith("adapter."))
    b = model.backend
    parameters = {k: b.array(v) for k, v in model.weights.items()}
    _, gradients = b.gradients(lambda p: (model.forward(p, b.array(x)) ** 2).mean(), parameters)
    assert all(np.linalg.norm(gradients[k]) > 0 for k in gradients if k.startswith("adapter."))
