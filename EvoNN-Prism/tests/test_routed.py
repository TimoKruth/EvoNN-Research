"""Task routing, score-aligned checkpoints and frozen historical behavior."""
import json

import numpy as np
import pytest

from evonn_shared.active_catalog import get_benchmark
from evonn_shared.prism_policy import PrismResearchPolicy, V3_VARIANTS
from evonn_shared.runtime_journal import digest
from prism.config import RunConfig
from prism.research import policy, allocate_training
from prism.search import Search
from prism.tensors import Backend
from prism.training import TrainConfig, fit


@pytest.mark.parametrize("variant", V3_VARIANTS)
def test_task_routing_is_explicit_and_portable(variant):
    assert RunConfig(variant=variant).variant == PrismResearchPolicy(variant=variant).variant
    with pytest.raises(ValueError, match="task kind"):
        policy(variant)
    language = policy(variant, task="language_modeling")
    assert language == {**policy("broad"), "aligned": False}
    for task in ("classification", "regression"):
        actual = policy(variant, task=task)
        expected = policy("frontier_v2")
        if variant != "routed_v3":
            expected.update(regularized=False, averaged=False)
        assert actual == {**expected, "aligned": variant == "aligned_v3" and task == "classification"}
    inheritance = {"mode": "partial", "copied_parameters": 50}
    for task, control in (("regression", "frontier_v2"), ("language_modeling", "broad")):
        assert allocate_training(12, 0, inheritance, 100, variant=variant, task=task) == allocate_training(12, 0, inheritance, 100, variant=control)


@pytest.mark.parametrize("variant", V3_VARIANTS)
@pytest.mark.parametrize("benchmark,control", [("iris_classification", "frontier_v2"), ("shakespeare_byte_lm", "broad")])
def test_routed_search_matches_control_and_resumes_exactly(variant, benchmark, control):
    definition = get_benchmark(benchmark)
    candidate = Search([definition], seed=7, population_size=4, variant=variant)
    historical = Search([definition], seed=7, population_size=4, variant=control)
    for step in range(80):
        genome = candidate.candidate(benchmark)
        assert genome == historical.candidate(benchmark)
        assert candidate.proposal(benchmark, genome) == historical.proposal(benchmark, genome)
        restored = Search([definition], seed=0, population_size=4, state=json.loads(json.dumps(candidate.state())))
        result = {"status": "ok", "score": -step, "parameter_count": 100, "epochs": 2, "best_epoch": 1, "updates": 2}
        for search in (candidate, historical, restored):
            search.observe(benchmark, genome, result)
        assert digest(candidate.state()) == digest(restored.state())
        candidate = restored
    with pytest.raises(ValueError, match="policy"):
        Search([definition], seed=0, state=candidate.state(), variant="open")


def test_mixed_pack_resolves_each_task_independently():
    definitions = [get_benchmark(x) for x in ("iris_classification", "diabetes_regression", "shakespeare_byte_lm")]
    search = Search(definitions, seed=4, variant="aligned_v3")
    for step in range(40):
        for d in definitions:
            genome = search.candidate(d.id)
            search.observe(d.id, genome, {"status": "ok", "score": -step, "parameter_count": 100})
    restored = Search(definitions, seed=0, state=json.loads(json.dumps(search.state())))
    assert restored.telemetry()["resolved_policies"] == search.policies
    assert search.policies[definitions[0].id]["aligned"]
    assert not search.policies[definitions[1].id]["aligned"]
    assert not search.policies[definitions[2].id]["archive"]
    with pytest.raises(ValueError, match="complete benchmark"):
        Search(definitions, seed=0, variant="aligned_v3", fixed_genomes={})


class CheckpointModel:
    token_input = False
    def __init__(self, initial):
        self.backend = Backend("numpy_fallback", "cpu")
        self.weights = {"logits": np.array(initial, dtype=np.float32)}
        self.buffers = {}
    def forward(self, parameters, features, **kwargs):
        return parameters["logits"]


def scripted_fit(monkeypatch, checkpoints, *, aligned, initial=None):
    model = CheckpointModel(initial if initial is not None else [[0., 0.], [0., 0.]])
    sequence = iter(checkpoints)
    def gradients(fn, parameters):
        model.weights["logits"] = np.asarray(next(sequence), dtype=np.float32)
        return 1., {"logits": np.zeros((2, 2), dtype=np.float32)}
    monkeypatch.setattr(model.backend, "gradients", gradients)
    result = fit(model, np.zeros((2, 1)), np.zeros(2, dtype=int), np.zeros((2, 1)), np.zeros(2, dtype=int),
                 task="classification", seed=0,
                 config=TrainConfig(epochs=len(checkpoints), weight_decay=0, classification_selection=aligned,
                                    preserve_initial=initial is not None))
    return model, result


def test_accuracy_selection_beats_lower_cross_entropy_and_breaks_ties(monkeypatch):
    checkpoints = [[[4., 0.], [0., .1]], [[.1, 0.], [.1, 0.]], [[.2, 0.], [.2, 0.]]]
    _, old = scripted_fit(monkeypatch, checkpoints, aligned=False)
    model, aligned = scripted_fit(monkeypatch, checkpoints, aligned=True)
    assert old["best_epoch"] == 1 and old["score"] == .5
    assert aligned["best_epoch"] == 3 and aligned["score"] == 1.
    assert aligned["selection_loss"] == 0 and aligned["selection_metric"] == "classification_error"
    assert aligned["selection_tiebreaker"] == "validation_loss"
    np.testing.assert_array_equal(model.weights["logits"], np.asarray(checkpoints[-1], dtype=np.float32))


def test_aligned_selection_preserves_stronger_inherited_checkpoint(monkeypatch):
    initial = [[1., 0.], [1., 0.]]
    model, result = scripted_fit(monkeypatch, [[[.1, 0.], [.1, 0.]], [[4., 0.], [0., .1]]], aligned=True, initial=initial)
    assert result["best_epoch"] == 0 and result["score"] == 1.
    np.testing.assert_array_equal(model.weights["logits"], initial)
