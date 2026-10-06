"""Legacy mutation admission must preserve the runtime fit-count contract."""
from copy import deepcopy

import pytest
from evonn_shared.active_catalog import get_benchmark
from topograph import search as s
from topograph.genome import Genome, Innovations, seed_genome, OPERATORS


def oversized():
    # Two raw context projections at width 64 exceed two million parameters.
    return Genome.model_validate(dict(
        layers=[dict(innovation=0, order=0., width=64), dict(innovation=2, order=1., width=64)],
        connections=[dict(innovation=1, source=-1, target=0),
                     dict(innovation=3, source=0, target=2),
                     dict(innovation=4, source=-1, target=2)], output=2))


@pytest.mark.parametrize('operator', OPERATORS)
def test_estimate_matches_actual_legacy_compiler(operator):
    definition = get_benchmark('shakespeare_context64_lm')
    genome = seed_genome(Innovations(), operator=operator)
    model = s.Search([definition], seed=7).compile(genome, definition,
                                                 backend='numpy_fallback', device='cpu', seed=7)
    assert s.parameter_estimate(s.GenomeV2.model_validate(genome.model_dump()), definition) == model.parameter_count
    assert s.within_parameter_cap(genome, definition)


def test_oversized_mutation_retains_valid_parent_and_records_rejection(monkeypatch):
    definition = get_benchmark('shakespeare_context64_lm')
    assert not s.within_parameter_cap(oversized(), definition)
    search = s.Search([definition], seed=7)
    prior = deepcopy(search.benchmarks[definition.id]['population'])
    monkeypatch.setattr(s, 'mutate', lambda *args: oversized())
    for _ in range(search.size):
        search.observe(definition.id, search.candidate(definition.id), dict(status='ok', score=-1.))
    state = search.benchmarks[definition.id]
    assert state['resource_rejections'] == 3
    assert all(g in prior for g in state['population'])
    assert all(s.within_parameter_cap(Genome.model_validate(g), definition) for g in state['population'])
    assert search.telemetry()['resource_rejections'][definition.id] == 3
