import numpy as np
import pytest
from random import Random
from prism.genome import ModelGenome, FAMILIES, compatible_families, mutate, crossover
from prism.compiler import compile_genome
from prism.training import fit, TrainConfig


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("backend", ["numpy_fallback", "mlx_native"])
def test_every_family_trains_actual_model(family, backend):
    if backend == "mlx_native":
        pytest.importorskip("mlx.core")
    modality = FAMILIES[family][0]
    shape = {"tabular": (4,), "image": (4, 4), "sequence": (4, 2), "text": (4,)}[modality]
    rng = np.random.default_rng(7)
    x = rng.integers(0, 5, size=(10, *shape)) if modality == "text" else rng.normal(size=(10, *shape))
    y = np.arange(10) % 3
    model = compile_genome(
        ModelGenome(family=family, hidden_layers=(8,)), shape, 3, modality, backend=backend, vocab_size=5
    )
    result = fit(
        model, x[:8], y[:8], x[8:], y[8:], task="classification", config=TrainConfig(epochs=2, batch_size=8), seed=2
    )
    assert result["weights_changed"] and result["updates"] == 2
    assert np.isfinite(result["score"])


@pytest.mark.parametrize("family", compatible_families("text", "language_modeling"))
def test_language_models_are_causal(family):
    model = compile_genome(ModelGenome(family=family, hidden_layers=(8,)), (5,), 7, "text", "language_modeling")
    b = model.backend
    p = {k: b.array(v) for k, v in model.weights.items()}
    a = np.array([[1, 2, 3, 4, 5]])
    c = a.copy()
    c[0, -1] = 6
    before = b.numpy(model.forward(p, b.array(a)))
    after = b.numpy(model.forward(p, b.array(c)))
    np.testing.assert_allclose(before[:, :-1], after[:, :-1], rtol=0, atol=0)
    with pytest.raises(ValueError, match="not causal"):
        compile_genome(ModelGenome(family=family, norm_type="batch"), (5,), 7, "text", "language_modeling")


def test_batchnorm_uses_training_stats_for_singleton_inference():
    rng = np.random.default_rng(3)
    x = rng.normal(size=(20, 4))
    y = np.arange(20) % 2
    model = compile_genome(ModelGenome(norm_type="batch"), (4,), 2, "tabular")
    fit(model, x[:16], y[:16], x[16:], y[16:], task="classification", config=TrainConfig(epochs=2), seed=4)
    b = model.backend
    p = {k: b.array(v) for k, v in model.weights.items()}
    batch = b.numpy(model.forward(p, b.array(x)))
    single = np.concatenate([b.numpy(model.forward(p, b.array(row[None, :]))) for row in x])
    np.testing.assert_allclose(batch, single, rtol=1e-5, atol=1e-6)
    assert not np.allclose(single[0], single[1])


def test_deep_frozen_identity_and_variation():
    g = ModelGenome(hidden_layers=[8, 16])
    before = g.genome_id
    with pytest.raises(TypeError):
        g.hidden_layers[0] = 9
    assert ModelGenome.model_validate_json(g.model_dump_json()).genome_id == before
    rng = Random(31)
    for _ in range(100):
        child, op = mutate(g, rng, compatible_families("tabular"))
        assert child.genome_id != g.genome_id
        child = crossover(child, g, rng, rng.choice(["splice", "uniform"]))
        assert child.family in compatible_families("tabular")
        g = child


@pytest.mark.parametrize("operator", ["morph_widen", "morph_deepen"])
def test_network_morphism_preserves_function_before_retraining(operator):
    from prism.search import preserve_morphism

    parent = ModelGenome(hidden_layers=(8, 8), activation="relu", norm_type="none")
    child, actual = mutate(parent, Random(4), ["mlp"], operator=operator)
    assert actual == operator
    original = compile_genome(parent, (4,), 3, "tabular", seed=4)
    changed_model = compile_genome(child, (4,), 3, "tabular", seed=7)
    preserve_morphism(changed_model, original.weights, operator)
    x = np.random.default_rng(9).normal(size=(20, 4))
    b = original.backend
    before = b.numpy(original.forward({k: b.array(v) for k, v in original.weights.items()}, b.array(x)))
    after = b.numpy(changed_model.forward({k: b.array(v) for k, v in changed_model.weights.items()}, b.array(x)))
    np.testing.assert_allclose(before, after, rtol=1e-6, atol=1e-6)
    _, name = mutate(ModelGenome(hidden_layers=(8,) * 6), Random(2), ["mlp"], operator="morph_deepen")
    assert name != "morph_deepen"


@pytest.mark.parametrize("backend", ["numpy_fallback", "mlx_native"])
def test_real_causal_language_model_training_reports_perplexity(backend):
    if backend == "mlx_native":
        pytest.importorskip("mlx.core")
    x = np.array([[0, 1, 2, 3], [1, 2, 3, 0], [2, 3, 0, 1], [3, 0, 1, 2]])
    y = (x + 1) % 4
    model = compile_genome(
        ModelGenome(family="causal_transformer", hidden_layers=(8,)),
        (4,),
        4,
        "text",
        "language_modeling",
        backend=backend,
    )
    result = fit(model, x, y, x, y, task="language_modeling", config=TrainConfig(epochs=2, batch_size=4), seed=4)
    assert result["weights_changed"] and result["updates"] == 2
    assert np.isfinite(result["score"]) and result["score"] <= -1


def test_language_model_variation_never_introduces_batchnorm():
    rng = Random(73)
    parent = ModelGenome(family="causal_transformer", hidden_layers=(8,), norm_type="batch")
    for _ in range(80):
        child, _ = mutate(parent, rng, compatible_families("text", "language_modeling"), task="language_modeling")
        child = crossover(child, parent, rng, task="language_modeling")
        assert child.norm_type != "batch"
        compile_genome(child, (5,), 7, "text", "language_modeling")
        parent = child


def test_rope_mutation_respects_head_width():
    parent = ModelGenome(
        family="causal_transformer", embedding_dim=4, num_heads=4, kv_heads=1, position_encoding="none"
    )
    for seed in range(20):
        child, _ = mutate(parent, Random(seed), ["causal_transformer"], operator="position", task="language_modeling")
        assert child.position_encoding != "rope"
        compile_genome(child, (5,), 7, "text", "language_modeling")
