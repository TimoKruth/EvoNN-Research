import numpy as np
import pytest
from random import Random
from topograph.genome import Genome, Innovations, seed_genome, OPERATORS, ExpertGene, GateConfig
from topograph.compiler import compile_genome
from topograph.search import mutate, select_parents, Scheduler
from topograph.training import fit, TrainConfig


@pytest.mark.parametrize("operator", OPERATORS)
@pytest.mark.parametrize("backend", ["numpy_fallback", "mlx_native"])
def test_every_graph_operator_trains(operator, backend):
    if backend == "mlx_native":
        pytest.importorskip("mlx.core")
    g = seed_genome(Innovations(), operator=operator)
    model = compile_genome(g, (4,), 2, backend=backend)
    rng = np.random.default_rng(4)
    x = rng.normal(size=(10, 4))
    y = np.arange(10) % 2
    r = fit(
        model, x[:8], y[:8], x[8:], y[8:], task="classification", config=TrainConfig(epochs=2, batch_size=8), seed=3
    )
    assert r["weights_changed"] and r["updates"] == 2


def test_speciation_materially_affects_reproduction():
    innovations = Innovations()
    population = [seed_genome(innovations, operator=op) for op in ("dense", "spatial", "dense", "spatial")]
    scores = [100, 1, 90, 0]
    protected = select_parents(population, scores, Random(1), 4, use_speciation=True)
    global_selection = select_parents(population, scores, Random(1), 4, use_speciation=False)
    assert protected != global_selection
    assert any(population[i].layers[0].operator == "spatial" for i in protected)
    assert all(population[i].layers[0].operator == "dense" for i in global_selection)


def test_mutation_stays_valid_and_scheduler_roundtrips():
    innovations = Innovations()
    g = seed_genome(innovations)
    rng = Random(5)
    schedule = Scheduler()
    for i in range(80):
        op = schedule.choose(i / 80, rng)
        child = mutate(g, rng, innovations, op)
        assert child.genome_id != g.genome_id
        assert Genome.model_validate_json(child.model_dump_json()).genome_id == child.genome_id
        schedule.observe(op, i % 2 == 0)
        g = child
    assert schedule.ema == Scheduler(schedule.ema).ema
    assert schedule.phase(0.1) == "explore" and schedule.phase(0.7) == "refine" and schedule.phase(0.99) == "polish"


def test_canonical_expert_order_and_gate_gradients():
    g = seed_genome(Innovations())
    data = g.model_dump()
    data.update(experts=[ExpertGene(innovation=10, width=8), ExpertGene(innovation=11, width=12)], gate=GateConfig())
    a = Genome.model_validate(data)
    data["experts"] = list(reversed(data["experts"]))
    c = Genome.model_validate(data)
    assert a.genome_id == c.genome_id
    ma, mc = (compile_genome(v, (4,), 2, seed=3) for v in (a, c))
    for key, value in ma.weights.items():
        np.testing.assert_array_equal(value, mc.weights[key])
    b = ma.backend
    p = {k: b.array(v) for k, v in ma.weights.items()}
    x = b.array(np.random.default_rng(4).normal(size=(8, 4)))
    _, grads = b.gradients(lambda weights: (ma.forward(weights, x) ** 2).mean(), p)
    assert np.linalg.norm(grads["gate.w"]) > 0


def test_memory_pool_limits_and_benchmark_pooling():
    from topograph.parallel import capacity
    from topograph.search import Search
    from evonn_shared.catalog import get_benchmark

    with pytest.raises(ValueError, match="memory budget"):
        capacity(data_bytes=1024, snapshot_bytes=1024, cpu_budget=4, memory_bytes=1024, job_count=4)
    assert capacity(data_bytes=1024, snapshot_bytes=1024, cpu_budget=2, memory_bytes=4 * 1024**3, job_count=8) == 2
    search = Search([get_benchmark("iris_classification")], seed=1, benchmark_pooling=True)
    search.pool_scores = {"a": {"accuracy": 0.9, "mse": -100}, "b": {"accuracy": 0.8, "mse": -10}}
    assert search.pooled_fitness("a", 0) == search.pooled_fitness("b", 0)
    search.pool_scores["a"]["mse"] = -1
    assert search.pooled_fitness("a", 0) > search.pooled_fitness("b", 0)


def test_champion_survives_crossover_and_pooling_keeps_failure_and_novelty():
    from topograph.search import Search
    from evonn_shared.catalog import get_benchmark

    benchmark = "iris_classification"
    search = Search([get_benchmark(benchmark)], seed=0, population_size=2, benchmark_pooling=True, novelty_weight=0.5)
    search.pool_scores = {"a": {benchmark: 1}, "b": {benchmark: 0}}
    entry = {"identity": "a", "status": "ok", "quality": 1, "novelty": 0}
    first = search.selection_fitness(entry)
    assert search.selection_fitness({**entry, "novelty": 10}) > first
    assert search.selection_fitness({**entry, "status": "failed", "novelty": 1e40}) == -1e30
    search.benchmark_pooling, search.novelty_weight = False, 0
    champion = seed_genome(search.innovations)
    wider = Genome.model_validate(
        {**champion.model_dump(), "layers": [{**n.model_dump(), "width": 32} for n in champion.layers]}
    )
    search.benchmarks[benchmark]["population"] = [g.model_dump(mode="json") for g in (champion, wider)]
    search.observe(benchmark, champion, {"status": "ok", "score": 100})
    search.observe(benchmark, wider, {"status": "ok", "score": 0})
    assert search.candidate(benchmark).genome_id == champion.genome_id


def test_text_classification_requires_a_separate_explicit_contract():
    with pytest.raises(ValueError, match="support"):
        compile_genome(seed_genome(Innovations()), (4,), 5, task="classification", modality="text")


def test_real_next_token_training_and_replay_perplexity():
    from topograph.run import perplexity_from_logits

    model = compile_genome(seed_genome(Innovations()), (4,), 5, task="language_modeling", modality="text")
    rng = np.random.default_rng(7)
    x = rng.integers(0, 5, size=(20, 4))
    y = (x[:, 0] + x[:, -1]) % 5
    result = fit(model, x, y, x, y, task="language_modeling", config=TrainConfig(epochs=2), seed=7)
    b = model.backend
    prediction = b.numpy(model.forward({k: b.array(v) for k, v in model.weights.items()}, b.array(x)))
    assert prediction.shape == (20, 5) and result["weights_changed"]
    assert perplexity_from_logits(prediction, y, b) == pytest.approx(-result["score"], rel=1e-6)


@pytest.mark.parametrize("backend", ["numpy_fallback", "mlx_native"])
@pytest.mark.parametrize("bits", [1.58, 4, 8])
def test_lm_quantization_is_independent_of_batch_neighbors(backend, bits):
    if backend == "mlx_native":
        pytest.importorskip("mlx.core")
    genome = seed_genome(Innovations())
    genome = Genome.model_validate(
        {
            **genome.model_dump(),
            "layers": [{**node.model_dump(), "weight_bits": bits, "activation_bits": 8} for node in genome.layers],
        }
    )
    model = compile_genome(genome, (4,), 5, task="language_modeling", modality="text", backend=backend)
    b = model.backend
    weights = {key: b.array(value) for key, value in model.weights.items()}

    def predict(contexts):
        return b.numpy(model.forward(weights, b.array(np.array(contexts))))[0]

    reference = predict([[1, 2, 3, 4]])
    for neighbor in ([0, 0, 0, 0], [4, 4, 4, 4]):
        np.testing.assert_allclose(predict([[1, 2, 3, 4], neighbor]), reference, rtol=1e-5, atol=1e-6)
