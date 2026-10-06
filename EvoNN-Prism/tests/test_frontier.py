"""Numerical, selection and recovery contracts for opt-in frontier policies."""

from copy import deepcopy
import json
from random import Random

import numpy as np
import pytest

from evonn_shared.active_catalog import get_benchmark
from evonn_shared.prism_policy import PrismResearchPolicy
from evonn_shared.runtime_journal import digest
from prism.compiler import compile_genome
from prism.frontier import founder, refine
from prism.genome import ModelGenome, compatible_families, crossover, mutate
from prism.research import VARIANTS, architecture_identity, policy
from prism.search import Search
from prism.training import TrainConfig, fit


@pytest.mark.parametrize("variant", [v for v in VARIANTS if not v.endswith("_v3")])
def test_portable_policy_matches_engine_and_keeps_controls_separate(variant):
    assert PrismResearchPolicy(variant=variant).variant == variant
    enabled = policy(variant)
    components = ("search", "representation", "regularized", "averaged", "calibrated")
    assert sum(enabled[c] for c in components) == (5 if variant == "frontier_v2" else int(variant.endswith("_v2")))


@pytest.mark.parametrize("backend", ["numpy_fallback", "mlx_native"])
@pytest.mark.parametrize("kind", ["skip", "spatial", "prenorm"])
def test_new_representations_have_gradients_and_replayable_training(backend, kind):
    if backend == "mlx_native":
        pytest.importorskip("mlx.core")
    rng = np.random.default_rng(123)
    if kind == "skip":
        genome = ModelGenome(hidden_layers=(8,), input_skip=True, norm_type="none")
        shape, modality, task = (3,), "tabular", "classification"
    elif kind == "spatial":
        genome = ModelGenome(family="conv2d", hidden_layers=(4,), readout="spatial_pyramid", norm_type="none")
        shape, modality, task = (3, 5), "image", "classification"
    else:
        genome = ModelGenome(family="causal_transformer", hidden_layers=(8, 8), embedding_dim=8,
                             pre_norm=True, norm_type="rms", activation="gelu")
        shape, modality, task = (4,), "text", "language_modeling"
    model = compile_genome(genome, shape, 3, modality, task, backend=backend)
    x = rng.integers(0, 3, (8, *shape)) if modality == "text" else rng.normal(size=(8, *shape))
    y = np.arange(8) % 3
    b = model.backend
    p = {k: b.array(v) for k, v in model.weights.items()}
    _, gradients = b.gradients(lambda params: (model.forward(params, b.array(x)) ** 2).mean(), p)
    key = "input_skip.w" if kind == "skip" else "layer0.w" if kind == "spatial" else "layer0.q.w"
    assert np.max(np.abs(gradients[key])) > 1e-7
    # Check a real derivative in the newly affected computation path.
    index = np.unravel_index(np.abs(gradients[key]).argmax(), gradients[key].shape)
    values = []
    for sign in (-1, 1):
        perturbed = {k: v.copy() for k, v in model.weights.items()}
        perturbed[key][index] += sign * .002
        values.append(float(b.numpy((model.forward({k: b.array(v) for k, v in perturbed.items()}, b.array(x)) ** 2).mean())))
    assert gradients[key][index] == pytest.approx((values[1] - values[0]) / .004, rel=.03, abs=2e-3)
    before = deepcopy(model.weights)
    result = fit(model, x, y, x, y, task=task,
                 config=TrainConfig(epochs=2, batch_size=4, label_smoothing=.05, decay_policy="matrix",
                                    ema_decay=.9, native_optimizer=True), seed=3)
    assert result["updates"] == 4 and np.isfinite(result["score"])
    assert not np.array_equal(before[key], model.weights[key])
    restored = compile_genome(ModelGenome.model_validate_json(genome.model_dump_json()), shape, 3, modality, task, backend=backend)
    restored.weights, restored.buffers = deepcopy(model.weights), deepcopy(model.buffers)
    for instance in (model, restored):
        instance.prediction = b.numpy(instance.forward({k: b.array(v) for k, v in instance.weights.items()}, b.array(x)))
    np.testing.assert_array_equal(model.prediction, restored.prediction)
    if kind == "prenorm":
        other = x.copy()
        other[:, -1] = (other[:, -1] + 1) % 3
        altered = b.numpy(model.forward({k: b.array(v) for k, v in model.weights.items()}, b.array(other)))
        np.testing.assert_allclose(model.prediction[:, :-1], altered[:, :-1], atol=1e-6)


def test_spatial_readout_distinguishes_location_with_identical_global_mean():
    genome = ModelGenome(family="conv2d", hidden_layers=(4,), norm_type="none", readout="spatial_pyramid")
    model = compile_genome(genome, (4, 4), 1, "image")
    for weights in model.weights.values():
        weights[:] = 0
    model.weights["layer0.w"][4, :] = 1  # center of 3x3 kernel
    model.weights["head.w"][4:8, :] = 1  # top-left cell, following global mean
    x = np.zeros((2, 4, 4))
    x[0, 0, 0] = x[1, 3, 3] = 1
    b = model.backend
    result = b.numpy(model.forward({k: b.array(v) for k, v in model.weights.items()}, b.array(x)))
    assert result[0, 0] == 1 and result[1, 0] == 0


@pytest.mark.parametrize("benchmark", ["iris_classification", "digits_image", "shakespeare_byte_lm"])
@pytest.mark.parametrize("size", [2, 4])
def test_frontier_resume_is_exact_and_never_excludes_a_family(benchmark, size):
    definition = get_benchmark(benchmark)
    search = Search([definition], seed=4, population_size=size, variant="frontier_v2")
    protected, origins = set(), set()
    for step in range(size * 32):
        genome = search.candidate(benchmark)
        proposal = search.proposal(benchmark, genome)
        origins.add(proposal["origin"])
        if proposal["protected"]:
            protected.add(genome.family)
        restored = Search([definition], seed=0, population_size=size, state=json.loads(json.dumps(search.state())))
        assert genome == restored.candidate(benchmark)
        result = {"status": "ok", "score": -step if proposal["protected"] else 1., "parameter_count": 100,
                  "epochs": 3, "best_epoch": 1, "updates": 3}
        for instance in (search, restored):
            instance.observe(benchmark, genome, result)
        assert digest(search.state()) == digest(restored.state())
        search = restored
    assert protected == set(compatible_families(definition.input_modality.value, definition.task_kind.value))
    assert "plateau_refinement" in origins
    if size > 2:
        assert "quality_archive" in origins


def test_extended_variation_stays_valid_and_reaches_both_architecture_controls():
    rng = Random(20)
    seen = {"input_skip": set(), "readout": set(), "pre_norm": set()}
    for modality, task in (("tabular", "classification"), ("image", "classification"), ("text", "language_modeling")):
        allowed = compatible_families(modality, task)
        for family in allowed:
            parent = founder(family, rng, representation=True)
            for step in range(60):
                child, _ = refine(parent, rng, allowed, task=task, representation=True, stats={})
                for field in seen:
                    seen[field].add(getattr(child, field))
                assert child.genome_id != parent.genome_id
                crossed = crossover(child, parent, rng, task=task, broad=True)
                mutated, _ = mutate(crossed, rng, allowed, task=task, broad=True)
                ModelGenome.model_validate(mutated.model_dump())
                parent = child
    assert seen == {"input_skip": {True, False}, "readout": {"mean", "spatial_pyramid"}, "pre_norm": {True, False}}
    assert architecture_identity(ModelGenome()) != architecture_identity(ModelGenome(input_skip=True))


def test_ema_selection_resets_moments_and_uses_unsmoothed_validation(monkeypatch):
    model = compile_genome(ModelGenome(norm_type="none"), (2,), 2, "tabular")
    x, y = np.zeros((4, 2)), np.zeros(4, dtype=int)
    model.weights["head.b"][:] = [2, -2]
    def harmful_gradient(forward, parameters):
        grads = {k: np.zeros_like(v.data) for k, v in parameters.items()}
        grads["head.b"][:] = [1, -1]
        return 0., grads
    monkeypatch.setattr(model.backend, "gradients", harmful_gradient)
    result = fit(model, x, y, x, y, task="classification", seed=1,
                 config=TrainConfig(epochs=2, ema_decay=.9, weight_decay=0, learning_rate=.1,
                                    optimizer_policy="continue", label_smoothing=.2))
    assert result["selected_weight_source"] == "ema"
    assert model.optimizer_state is None
    assert result["optimizer_reset_reason"] == "averaged_weights_have_no_matching_moments"
    logits = model.weights["head.b"]
    expected = np.log(np.exp(logits - logits.max()).sum()) - logits[0] + logits.max()
    assert result["validation_loss"] == pytest.approx(expected, abs=1e-6)


def test_calibrated_selection_matches_final_metric_and_only_uses_training_targets():
    rng = np.random.default_rng(4)
    x = rng.normal(size=(32, 3))
    y = 20 + 3 * x[:, 0] - x[:, 1]
    genome = ModelGenome(hidden_layers=(8,), input_skip=True, norm_type="none")
    model = compile_genome(genome, (3,), 1, "tabular", "regression")
    result = fit(model, x[:24], y[:24], x[24:], y[24:], task="regression", seed=3,
                 config=TrainConfig(epochs=5, calibrated_selection=True, ema_decay=.9))
    assert result["selection_metric"] == "calibrated_mse"
    assert result["selection_loss"] == pytest.approx(-result["score"], rel=1e-6)
    assert result["selection_loss"] == min(row["selection_loss"] for row in result["learning_curve"])
    # With a fixed single epoch, changing validation labels cannot change training
    # weights or the train-fitted calibration coefficients.
    models = [compile_genome(genome, (3,), 1, "tabular", "regression") for _ in range(2)]
    results = [fit(m, x[:24], y[:24], x[24:], y[24:] + offset, task="regression", seed=3,
                   config=TrainConfig(epochs=1, calibrated_selection=True)) for m, offset in zip(models, (0, 100))]
    assert results[0]["preprocessing"]["calibration"] == results[1]["preprocessing"]["calibration"]
    for key in models[0].weights:
        np.testing.assert_array_equal(models[0].weights[key], models[1].weights[key])


@pytest.mark.parametrize("values", [{"ema_decay": float("nan")}, {"label_smoothing": 1.}, {"decay_policy": "unknown"}])
def test_invalid_training_policies_fail(values):
    with pytest.raises(ValueError):
        TrainConfig(**values)


def test_representation_ablation_only_changes_new_genes_at_initialization():
    definition = get_benchmark("digits_image")
    controls = Search([definition], seed=17, variant="open")
    experimental = Search([definition], seed=17, variant="representation_v2")
    for a, b in zip(controls.benchmarks[definition.id]["population"], experimental.benchmarks[definition.id]["population"], strict=True):
        assert {k: v for k, v in a.items() if k not in {"input_skip", "readout", "pre_norm"}} == {
            k: v for k, v in b.items() if k not in {"input_skip", "readout", "pre_norm"}}


def test_matrix_decay_preserves_bias_when_gradients_are_zero(monkeypatch):
    model = compile_genome(ModelGenome(norm_type="none"), (2,), 2, "tabular")
    model.weights["head.b"][:] = 1
    initial = deepcopy(model.weights)
    monkeypatch.setattr(model.backend, "gradients", lambda loss, p: (0., {k: np.zeros_like(v.data) for k, v in p.items()}))
    fit(model, np.ones((4, 2)), np.zeros(4, int), np.ones((4, 2)), np.zeros(4, int),
        task="classification", seed=1, config=TrainConfig(epochs=1, decay_policy="matrix", weight_decay=.1))
    np.testing.assert_array_equal(model.weights["head.b"], initial["head.b"])
    assert not np.array_equal(model.weights["head.w"], initial["head.w"])


@pytest.mark.parametrize("task", ["classification", "regression"])
def test_frontier_training_matches_between_native_and_numpy_optimizers(task):
    pytest.importorskip("mlx.core")
    rng = np.random.default_rng(41)
    x = rng.normal(size=(16, 3))
    y = np.arange(16) % 3 if task == "classification" else x[:, 0] * 4 + 2
    models = [compile_genome(ModelGenome(input_skip=True, norm_type="none"), (3,),
                             3 if task == "classification" else 1, "tabular", task, backend="mlx_native") for _ in range(2)]
    results = [fit(model, x, y, x, y, task=task, seed=7,
                   config=TrainConfig(epochs=3, batch_size=8, native_optimizer=native, ema_decay=.9,
                                      label_smoothing=.05, decay_policy="matrix", calibrated_selection=True))
               for model, native in zip(models, (False, True), strict=True)]
    assert results[0]["selected_weight_source"] == results[1]["selected_weight_source"]
    assert results[0]["score"] == pytest.approx(results[1]["score"], rel=2e-4, abs=2e-5)
    for key in models[0].weights:
        np.testing.assert_allclose(models[0].weights[key], models[1].weights[key], rtol=3e-4, atol=3e-6)
