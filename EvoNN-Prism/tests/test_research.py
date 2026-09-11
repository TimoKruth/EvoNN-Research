from copy import deepcopy
import json
from random import Random

import numpy as np
import pytest

from evonn_shared.active_catalog import get_benchmark
from evonn_shared.canonical import canonical_sha256
from evonn_shared.runtime_journal import digest, runner_search_snapshot
from prism.compiler import compile_genome
from prism.genome import ModelGenome, BlockGene, compatible_families, mutate, crossover
from prism.research import allocate_training, architecture_identity
from prism.search import Search
from prism.training import TrainConfig, fit
from prism.weight_cache import PrismWeightCache


def test_historical_genome_identity_is_preserved():
    genome = ModelGenome(hidden_layers=(8,))
    legacy = genome.model_dump(mode="json", exclude={"blocks"})
    assert genome.genome_id == canonical_sha256(legacy, schema_version="prism.genome/v1", digest_field=None)


def test_protected_lineages_survive_weak_scores_and_archives_reenter_after_resume():
    definition = get_benchmark("shakespeare_byte_lm")
    search = Search([definition], seed=19, population_size=4)
    origins, protected, detached = [], set(), []
    for step in range(160):
        snapshot = runner_search_snapshot(search)
        saved = digest(snapshot)
        restored = Search([definition], seed=0, population_size=4, state=json.loads(json.dumps(snapshot)))
        genome = search.candidate(definition.id)
        assert restored.candidate(definition.id) == genome
        proposal = search.proposal(definition.id, genome)
        origins.append(proposal["origin"])
        if proposal["protected"]:
            protected.add(genome.family)
        # The forced slot always loses to the champion but must still develop.
        result = {"status": "ok", "score": 10 if step % 4 == 0 else -100 - step,
                  "parameter_count": 100, "updates": 1}
        for instance in (search, restored):
            instance.observe(definition.id, genome, result)
        assert digest(search.state()) == digest(restored.state())
        assert digest(snapshot) == saved
        detached.append((snapshot, saved))
        search = restored
    assert protected == set(compatible_families("text", "language_modeling"))
    assert {"nursery", "family_archive", "reservoir", "descriptor_archive", "fresh"} <= set(origins)
    assert len(search.benchmarks[definition.id]["reservoir"]) <= 16
    for snapshot, saved in detached:
        assert digest(snapshot) == saved


def test_two_member_population_still_visits_every_family():
    definition = get_benchmark("shakespeare_byte_lm")
    search = Search([definition], seed=4, population_size=2)
    families = set()
    for step in range(2 * 10):
        genome = search.candidate(definition.id)
        families.add(genome.family)
        search.observe(definition.id, genome, {"status": "ok", "score": -step, "parameter_count": 4})
    assert families == set(compatible_families("text", "language_modeling"))


def test_fixed_finalists_do_not_change_with_scores_or_resume():
    definition = get_benchmark("shakespeare_byte_lm")
    genome = ModelGenome(family="attention", hidden_layers=(8,))
    fixed = {definition.id: genome.model_dump(mode="json")}
    searches = [Search([definition], seed=seed, variant="training", fixed_genomes=fixed) for seed in (4, 9)]
    for step in range(17):
        for sign, search in zip((-1, 1), searches, strict=True):
            assert search.candidate(definition.id) == genome
            assert search.proposal(definition.id, genome)["protected"]
            search.observe(definition.id, genome, {"status": "ok", "score": sign * step, "parameter_count": 10})
        searches = [Search([definition], seed=0, state=json.loads(json.dumps(s.state()))) for s in searches]
    with pytest.raises(ValueError, match="complete benchmark"):
        Search([definition], seed=0, variant="training", fixed_genomes={})
    with pytest.raises(ValueError, match="training/open"):
        Search([definition], seed=0, variant="legacy", fixed_genomes=fixed)


def test_legacy_search_does_not_introduce_composition_or_archive_selection():
    definition = get_benchmark("shakespeare_byte_lm")
    search = Search([definition], seed=4, variant="legacy")
    for step in range(32):
        genome = search.candidate(definition.id)
        assert genome.family != "composite"
        search.observe(definition.id, genome, {"status": "ok", "score": -step, "parameter_count": 4})
    assert not search.benchmarks[definition.id]["reservoir"]
    with pytest.raises(ValueError, match="policy"):
        Search([definition], seed=4, variant="open", state=search.state())


def test_partial_coverage_and_patient_allocation():
    def allocation(copied, **kwargs):
        return allocate_training(12, 1, {"mode": "partial", "copied_parameters": copied}, 100, **kwargs)
    assert allocation(1)[1] == 12
    assert allocation(100)[1] == 8
    assert allocation(100, protected=True)[1] == 12
    assert allocation(1, variant="legacy")[1] == 8
    assert allocate_training(12, 0, {"mode": "none", "copied_parameters": 0}, 100)[1] == 12
    assert allocate_training(12, 1, {"mode": "exact", "copied_parameters": 100,
                                     "source_needs_more_training": True}, 100)[1:] == (12, "learning_progress_full")


def test_executed_architecture_identity_ignores_training_and_inactive_fields():
    original = ModelGenome()
    optimizer_change = ModelGenome(learning_rate=.01, weight_decay=.02, kernel_size=5, num_experts=8)
    assert original.genome_id != optimizer_change.genome_id
    assert architecture_identity(original) == architecture_identity(optimizer_change)
    assert architecture_identity(original) != architecture_identity(ModelGenome(hidden_layers=(32,)))


def test_cli_freezes_all_experiment_options_and_explicit_flags_override_yaml(tmp_path, monkeypatch):
    import prism.cli as cli
    config = tmp_path / "config.yaml"
    config.write_text("variant: archive\ninheritance_policy: disabled\noptimizer_backend: native\noptimizer_policy: continue\n")
    captured = {}
    monkeypatch.setattr(cli, "run_engine", lambda search, **options: captured.update(options) or tmp_path)
    cli.main(["run", "--config", str(config), "--variant=training"])
    assert captured["variant"] == "training"
    assert captured["inheritance_policy"] == "disabled"
    assert captured["optimizer_policy"] == "continue"
    assert captured["optimizer_backend"] == "native"


def test_broad_mutation_reaches_nonlegacy_widths_and_reversible_depth():
    genome = ModelGenome(hidden_layers=(16, 16, 16))
    children = [mutate(genome, Random(s), ["mlp"], operator="width", broad=True)[0] for s in range(100)]
    assert any(max(g.hidden_layers) > 64 for g in children)
    assert any(any(w not in {8, 16, 32, 64} for w in g.hidden_layers) for g in children)
    depths = {len(mutate(genome, Random(s), ["mlp"], operator="depth", broad=True)[0].hidden_layers) for s in range(20)}
    assert depths == {2, 4}
    attention = ModelGenome(family="attention", embedding_dim=4, num_heads=4, position_encoding="none")
    for seed in range(100):
        child, _ = mutate(attention, Random(seed), ["attention"], operator="embedding", broad=True)
        assert child.embedding_dim % child.num_heads == 0


@pytest.mark.parametrize("backend", ["numpy_fallback", "mlx_native"])
def test_mixed_composition_trains_every_block_and_is_causal(backend):
    if backend == "mlx_native":
        pytest.importorskip("mlx.core")
    genome = ModelGenome(family="composite", embedding_dim=8, norm_type="none", activation="tanh",
                        blocks=[{"kind": kind, "skip_from": 0} for kind in ["conv1d", "gru", "attention", "sparse", "gated"]])
    model = compile_genome(genome, (5,), 7, "text", "language_modeling", backend=backend)
    b = model.backend
    x = np.array([[0, 1, 2, 3, 4], [1, 2, 3, 4, 5]])
    p = {k: b.array(v) for k, v in model.weights.items()}
    before = b.numpy(model.forward(p, b.array(x)))
    altered = x.copy()
    altered[:, -1] = 6
    after = b.numpy(model.forward(p, b.array(altered)))
    np.testing.assert_allclose(before[:, :-1], after[:, :-1], atol=1e-6)
    initial = deepcopy(model.weights)
    result = fit(model, x, (x + 1) % 7, x, (x + 1) % 7, task="language_modeling",
                 config=TrainConfig(epochs=2, batch_size=2, native_optimizer=True), seed=4)
    assert result["weights_changed"]
    for i, block in enumerate(genome.blocks):
        prefix = f"block{i}.{block.kind}."
        assert any(not np.array_equal(v, initial[k]) for k, v in model.weights.items() if k.startswith(prefix))


def test_composition_validates_cycles_modalities_and_variation():
    with pytest.raises(ValueError, match="cycles"):
        ModelGenome(family="composite", blocks=[BlockGene(kind="dense", skip_from=1)])
    image = ModelGenome(family="composite", embedding_dim=8, blocks=[{"kind": "conv2d"}, {"kind": "attention"}])
    model = compile_genome(image, (4, 4), 3, "image")
    b = model.backend
    assert model.forward({k: b.array(v) for k, v in model.weights.items()}, b.array(np.ones((2, 4, 4)))).shape == (2, 3)
    with pytest.raises(ValueError, match="spatial"):
        compile_genome(image, (4,), 3, "text", "language_modeling")
    genome = ModelGenome(family="composite")
    rng = Random(15)
    seen = set()
    for step in range(100):
        child, op = mutate(genome, rng, compatible_families("text", "language_modeling"),
                           operator=["block_add", "block_remove", "block_rewire", "block_kind"][step % 4],
                           broad=True, task="language_modeling")
        seen.update(b.kind for b in child.blocks)
        child = crossover(child, genome, rng, broad=True, task="language_modeling")
        compile_genome(child, (4,), 7, "text", "language_modeling")
        genome = child
    assert "conv2d" not in seen
    assert {"attention", "conv1d", "gru"} <= seen


def test_exact_continuation_retains_starting_checkpoint_when_training_worsens(monkeypatch):
    model = compile_genome(ModelGenome(norm_type="none"), (2,), 2, "tabular")
    x, y = np.zeros((4, 2)), np.zeros(4, dtype=int)
    model.weights["head.b"][:] = [5, -5]
    before = deepcopy(model.weights)
    def harmful_gradient(forward, parameters):
        grads = {k: np.zeros_like(v.data) for k, v in parameters.items()}
        grads["head.b"][:] = [1, -1]
        return 0.0, grads
    monkeypatch.setattr(model.backend, "gradients", harmful_gradient)
    result = fit(model, x, y, x, y, task="classification",
                 config=TrainConfig(epochs=3, preserve_initial=True, weight_decay=0, learning_rate=.1), seed=1)
    assert result["best_epoch"] == 0
    assert len(result["learning_curve"]) == 3
    for key in before:
        np.testing.assert_array_equal(model.weights[key], before[key])


def test_optimizer_moments_resume_only_with_exact_bound_weights():
    genome = ModelGenome(hidden_layers=(8,), norm_type="none")
    model = compile_genome(genome, (2,), 2, "tabular")
    x, y = np.ones((4, 2)), np.zeros(4, dtype=int)
    config = TrainConfig(epochs=1, optimizer_policy="continue", schedule="constant", warmup_fraction=0)
    fit(model, x, y, x, y, task="classification", config=config, seed=1)
    cache = PrismWeightCache(2)
    cache.put("context", genome.genome_id, "mlp", "mlp", model.weights, model.buffers, model.optimizer_state)
    exact = compile_genome(genome, (2,), 2, "tabular", seed=9)
    info = cache.inherit(exact, namespace="context", identity=genome.genome_id, topology="mlp", family="mlp")
    assert info["mode"] == "exact"
    result = fit(exact, x, y, x, y, task="classification", config=config, seed=1)
    assert result["optimizer_resumed_step"] == 1
    assert result["optimizer_best_step"] == 2
    uninterrupted = compile_genome(genome, (2,), 2, "tabular")
    fit(uninterrupted, x, y, x, y, task="classification",
        config=TrainConfig(epochs=2, schedule="constant", warmup_fraction=0), seed=1)
    for key in exact.weights:
        np.testing.assert_allclose(exact.weights[key], uninterrupted.weights[key], rtol=1e-6, atol=1e-7)
    partial = compile_genome(ModelGenome(hidden_layers=(12,), norm_type="none"), (2,), 2, "tabular")
    cache.inherit(partial, namespace="context", identity="other", topology="mlp", family="mlp")
    assert partial.optimizer_state is None
    exact.weights["head.b"][0] += 1
    with pytest.raises(ValueError, match="bound"):
        fit(exact, x, y, x, y, task="classification", config=config, seed=1)
    assert cache.entry_bytes == sum(cache.sizes.values())


def test_native_optimizer_agrees_with_numpy_adam_on_fixed_fit():
    pytest.importorskip("mlx.core")
    x = np.random.default_rng(5).normal(size=(16, 4))
    y = np.arange(16) % 3
    models = [compile_genome(ModelGenome(hidden_layers=(8,), norm_type="none"), (4,), 3, "tabular", backend="mlx_native") for _ in range(2)]
    for native, model in zip((False, True), models, strict=True):
        fit(model, x, y, x, y, task="classification", config=TrainConfig(epochs=3, batch_size=8, native_optimizer=native), seed=4)
    for key in models[0].weights:
        np.testing.assert_allclose(models[0].weights[key], models[1].weights[key], rtol=2e-4, atol=2e-6)
