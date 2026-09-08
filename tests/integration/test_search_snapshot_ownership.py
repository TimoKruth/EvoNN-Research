"""Persistent runner searches match restore-per-fit semantics across recovery."""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from evonn_shared.active_catalog import get_benchmark
from evonn_shared.runtime_journal import digest, encode, runner_search_snapshot
from prism.search import Search as Prism
from topograph.search import Search as Topograph
from stratograph.search import Search as Stratograph
from evonn_primordia.search import Search as Primordia


@pytest.mark.parametrize("search_type", [Prism, Topograph, Stratograph, Primordia])
def test_runner_snapshot_preserves_selection_inheritance_and_prior_states(search_type):
    definitions = [get_benchmark("iris_classification"), get_benchmark("wine_classification")]
    persistent = search_type(definitions, seed=42, population_size=2)
    prior = runner_search_snapshot(persistent)
    history = []
    for step in range(40):
        reference = search_type(definitions, seed=42, population_size=2, state=prior)
        benchmark = definitions[step % 2].id
        genomes, inheritances, weights = [], [], []
        for search in (persistent, reference):
            genome = search.candidate(benchmark)
            genomes.append(genome.model_dump(mode="json"))
            model = SimpleNamespace(weights={"w": np.zeros(4, dtype=np.float32)}, buffers={}, parameter_count=4)
            inheritances.append(search.cache.inherit(model, namespace="probe", identity=str(step % 11), topology="shape", family="group"))
            weights.append(model.weights["w"].copy())
            model.weights["w"][:] = step + 1
            search.cache.put("probe", str(step % 11), "shape", "group", model.weights)
            model.weights["w"][:] = -999
            if search.system == "topograph":
                search.progress = (step + 1) / 40
            search.observe(benchmark, genome, {"status": "ok" if step % 7 else "failed", "score": (step % 9) / 9,
                                              "parameter_count": 4, "updates": step % 4 + 1})
        assert genomes[0] == genomes[1]
        assert inheritances[0] == inheritances[1]
        np.testing.assert_array_equal(weights[0], weights[1])
        current = runner_search_snapshot(persistent)
        assert digest(current) == digest(reference.state())
        for old, sha in history:
            assert digest(old) == sha
        history.append((current, digest(current)))
        prior = current
        if step % 7 == 6:
            persistent = search_type(definitions, seed=42, population_size=2, state=json.loads(encode(prior)))
