"""Experimental next policy: semantics, gradients, selection, and durable controls."""
from copy import deepcopy
import json
from random import Random
from types import SimpleNamespace

import numpy as np
import pytest

from evonn_shared.active_catalog import get_benchmark
from evonn_shared.topograph_policy import TopographResearchPolicy
from topograph.research import next_allocation, progressing
from topograph.compiler_v2 import compile_genome, parameter_estimate
from topograph.genome import Innovations, seed_genome
from topograph.genome_v2 import GenomeV2
from topograph.operators import edit
from topograph.search_v2 import ResearchSearch
from topograph.training import TrainConfig, fit


def genome(adapter, heads=2):
    return GenomeV2.model_validate({**seed_genome(Innovations()).model_dump(),
                                   "input_adapter": adapter, "adapter_heads": heads})


def compile_text(adapter, backend="numpy_fallback", heads=2):
    return compile_genome(genome(adapter, heads), (12,), 7, "text", "language_modeling", backend=backend, seed=9)


@pytest.mark.parametrize("backend", ["numpy_fallback", "mlx_native"])
@pytest.mark.parametrize("heads", [1, 2, 4])
def test_last_query_matches_full_attention_outputs_and_gradients(backend, heads):
    if backend == "mlx_native":
        pytest.importorskip("mlx.core")
    full, compact = [compile_text(adapter, backend, heads) for adapter in ("token_attention", "token_query")]
    x = np.random.default_rng(2).integers(0, 7, size=(3, 12))
    outputs, gradients = [], []
    for model in (full, compact):
        b = model.backend
        p = {k: b.array(v) for k, v in model.weights.items()}
        outputs.append(b.numpy(model.forward(p, b.array(x))))
        _, grads = b.gradients(lambda w: (model.forward(w, b.array(x)) ** 2).mean(), p)
        gradients.append(grads)
    np.testing.assert_allclose(*outputs, rtol=2e-5, atol=2e-6)
    assert full.parameter_count == compact.parameter_count
    for name in gradients[0]:
        np.testing.assert_allclose(gradients[0][name], gradients[1][name], rtol=2e-4, atol=2e-6, err_msg=name)


@pytest.mark.parametrize("backend", ["numpy_fallback", "mlx_native"])
@pytest.mark.parametrize("adapter", ["token_query", "token_mixer"])
def test_compact_adapters_train_all_parameters_and_replay_unsmoothed_metric(adapter, backend):
    if backend == "mlx_native":
        pytest.importorskip("mlx.core")
    model = compile_text(adapter, backend)
    b = model.backend
    rng = np.random.default_rng(11)
    x = rng.integers(0, 7, size=(20, 12))
    y = x[:, 3]
    p = {k: b.array(v) for k, v in model.weights.items()}
    _, grads = b.gradients(lambda w: (model.forward(w, b.array(x)) ** 2).mean(), p)
    for key, value in grads.items():
        assert np.isfinite(value).all()
        if key.startswith("adapter."):
            assert np.linalg.norm(value) > 0, key
    definition = SimpleNamespace(input_shape=(12,), output_dim=7,
                                 task_kind=SimpleNamespace(value="language_modeling"),
                                 input_modality=SimpleNamespace(value="text"))
    assert parameter_estimate(model.genome, definition) == model.parameter_count
    result = fit(model, x, y, x, y, task="language_modeling", seed=9,
                 config=TrainConfig(epochs=3, batch_size=10, label_smoothing=0.1,
                                    decay="matrix", validation_batch_size=3))
    assert result["updates"] == 6 and result["weights_changed"]
    assert len(result["training_curve"]) == len(result["validation_curve"]) == 3
    assert result["training_objective"] == "smoothed_cross_entropy"
    assert result["validation_loss"] == ([result["initial_validation_loss"]] + result["validation_curve"])[result["selected_epoch"]]
    from topograph.run import perplexity_from_logits
    prediction = b.numpy(model.forward({k: b.array(v) for k, v in model.weights.items()}, b.array(x)))
    assert perplexity_from_logits(prediction, y, b) == pytest.approx(-result["score"], rel=1e-6)
    changed = x.copy()
    changed[:, 3] = (changed[:, 3] + 1) % 7
    assert not np.allclose(prediction, b.numpy(model.forward({k: b.array(v) for k, v in model.weights.items()}, b.array(changed))))


def test_progress_allocation_and_fresh_controls():
    settings = TopographResearchPolicy()
    assert progressing([2.0, 1.5, 1.0], 3)
    assert not progressing([1.0, 1.5, 1.6], 0)
    assert next_allocation(12, 100, 100, False, settings, True) == (12, "progress_full")
    assert next_allocation(12, 100, 100, False, settings, False) == (6, "coverage_discount")
    assert next_allocation(12, 100, 100, True, settings, False) == (12, "protected_full")
    assert next_allocation(12, 0, 100, False, settings, False)[0] == 12
    assert next_allocation(12, 100, 100, False, TopographResearchPolicy(allocation="full"))[0] == 12
    assert next_allocation(12, 100, 100, False, TopographResearchPolicy(allocation="coverage"), True)[0] == 6


@pytest.mark.parametrize("adapter", ["query", "mixer", "diverse", "legacy"])
def test_next_search_replays_exactly_and_keeps_adapter_choice(adapter):
    definition = get_benchmark("shakespeare_byte_lm")
    options = {"adapters": adapter}
    search = ResearchSearch([definition], seed=17, variant="next", research_options=options)
    clone = None
    seen = set()
    for step in range(36):
        if step == 11:
            clone = ResearchSearch([definition], seed=99, state=json.loads(json.dumps(search.state())),
                                   research_options=options)
        g = search.candidate(definition.id)
        seen.add(g.input_adapter)
        assert parameter_estimate(g, definition) <= search.settings.parameter_cap
        result = dict(status="ok", score=-2.0 + step / 100, parameter_count=parameter_estimate(g, definition),
                      outcome_id=f"a{step:04d}", validation_curve=[2, 1], selected_epoch=2)
        if clone:
            assert clone.candidate(definition.id) == g
            clone.observe(definition.id, g, deepcopy(result))
        search.observe(definition.id, g, deepcopy(result))
    assert search.state() == clone.state()
    if adapter in {"query", "mixer"}:
        assert seen == {"token_" + adapter}
    if adapter == "legacy":
        assert seen <= {"flat", "token_attention"}
    with pytest.raises(ValueError, match="saved search"):
        ResearchSearch([definition], seed=17, state=search.state(), research_options={"inheritance": "disabled"})


def test_disabled_inheritance_never_copies_and_progress_binds_source():
    definition = get_benchmark("iris_classification")
    for mode in ("enabled", "disabled"):
        search = ResearchSearch([definition], seed=5, variant="next", research_options={"inheritance": mode})
        parent = search.candidate(definition.id)
        model = search.compile(parent, definition)
        search.remember(model, "ns")
        search.observe(definition.id, parent, dict(status="ok", score=1, outcome_id="a0001", epochs=2,
                                                  updates=2, validation_curve=[2, 1], selected_epoch=2))
        state = search.benchmarks[definition.id]
        state["population"][state["cursor"]] = parent.model_dump(mode="json")
        state["proposals"][state["cursor"]] = search.proposal_record("champion", parents=[parent.genome_id])
        inheritance = search.inherit(search.compile(parent, definition, seed=2), definition.id, "ns")
        assert inheritance["mode"] == ("exact" if mode == "enabled" else "none")
        if mode == "enabled":
            assert inheritance["source_progress"] and inheritance["ancestor_attempts"] == ["a0001"]


def test_local_mutation_limits_size_and_learning_rate_jumps():
    g = genome("token_query")
    definition = get_benchmark("shakespeare_byte_lm")
    for i in range(12):
        child, _ = edit(g, Random(i), Innovations(), "width", definition, broad=True, local=True)
        assert abs(child.layers[0].width - g.layers[0].width) <= 8
        child, _ = edit(g, Random(i), Innovations(), "lr", definition, broad=True, local=True)
        assert 0.5 <= child.learning_rate / g.learning_rate <= 2


def test_cost_aware_selection_prefers_smaller_near_tie_in_same_species():
    definition = get_benchmark("iris_classification")
    parents = []
    for selection in ("quality", "cost_aware"):
        search = ResearchSearch([definition], seed=5, population_size=2, variant="next",
                                research_options={"selection": selection})
        state = search.benchmarks[definition.id]
        small = search.candidate(definition.id)
        wide = GenomeV2.model_validate({**small.model_dump(), "layers": [{**n.model_dump(), "width": n.width + 4} for n in small.layers]})
        state["population"] = [g.model_dump(mode="json") for g in (small, wide)]
        for g, score, size in ((small, 0.995, 100), (wide, 1.0, 200)):
            search.observe(definition.id, g, dict(status="ok", score=score, parameter_count=size))
        parents.append(state["proposals"][0]["parents"][0])
    assert parents == [wide.genome_id, small.genome_id]


def test_generated_interventions_validate_and_preserve_all_engine_roster(tmp_path):
    from topograph.config import RunConfig
    from topograph.experiments import configurations, main
    from evonn_compare.campaign import CampaignSpec
    for _, run, campaign in configurations():
        RunConfig.model_validate(run)
        spec = CampaignSpec.model_validate(campaign)
        assert set(spec.systems) == {"prism", "topograph", "stratograph", "primordia", "contenders"}
        assert spec.topograph_variant in {"open", "next"}
    target = tmp_path / "configs"
    main(["--output", str(target)])
    assert len(list(target.glob("*.campaign.json"))) == 14
    with pytest.raises(FileExistsError):
        main(["--output", str(target)])


def test_run_rejects_options_on_old_variant_before_writing(tmp_path):
    from topograph.run import run_engine
    from topograph.search import Search
    with pytest.raises(ValueError, match="variant next"):
        run_engine(Search, variant="open", research_options={}, output_parent=tmp_path)
    assert not list(tmp_path.iterdir())
