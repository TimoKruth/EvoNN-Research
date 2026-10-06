import importlib.util
from copy import deepcopy
import json
import numpy as np
import pytest
from evonn_shared.active_catalog import get_benchmark
from evonn_shared.runtime_journal import runner_search_snapshot
from prism.genome import ModelGenome, BlockGene
from prism.search import Search
from prism.training import TrainConfig, fit


pytestmark = pytest.mark.skipif(importlib.util.find_spec("mlx") is None, reason="native MLX parameter-constraint qualification")


def place(search, definition, genome):
    state = search.benchmarks[definition.id]
    state["population"][state["cursor"]] = genome.model_dump(mode="json")
    state["parents"][genome.genome_id] = ["parent"]
    state["operators"][genome.genome_id] = ("morph_widen", 1.0)
    state["proposals"][genome.genome_id] = dict(
        origin="population",
        parents=["parent"],
        operator="morph_widen",
        changed_fields=["hidden_layers"],
        protected=False,
    )


def test_small_candidate_is_bitwise_unchanged():
    d = get_benchmark("digits_image")
    s = Search([d], seed=7, variant="broad")
    g = s.candidate(d.id)
    before = deepcopy(s.state())
    raw = s.compile(g, d, backend="mlx_native", device="cpu", seed=91)
    effective, model = s.compile_candidate(g, d, backend="mlx_native", device="cpu", seed=91)
    assert effective == g and s.state() == before
    for k in raw.weights:
        np.testing.assert_array_equal(raw.weights[k], model.weights[k])


@pytest.mark.parametrize(
    "genome",
    [
        ModelGenome(family="conv2d", hidden_layers=(200, 214, 214, 214), kernel_size=5),
        ModelGenome(family="conv2d", hidden_layers=(256,) * 6, kernel_size=5),
        ModelGenome(
            family="composite",
            hidden_layers=(256,) * 6,
            embedding_dim=256,
            kernel_size=5,
            blocks=tuple(BlockGene(kind="conv2d") for _ in range(6)),
        ),
    ],
)
def test_oversize_constraint_is_deterministic_resumable_and_preserves_lineage(genome):
    d = get_benchmark("digits_image")
    s = Search([d], seed=7, variant="broad")
    place(s, d, genome)
    rng = s.rng.getstate()
    snapshot = runner_search_snapshot(s)
    other = Search([d], seed=0, state=json.loads(json.dumps(snapshot)))
    g, m = s.compile_candidate(genome, d, backend="mlx_native", device="cpu", seed=91)
    g2, m2 = other.compile_candidate(genome, d, backend="mlx_native", device="cpu", seed=91)
    assert m.parameter_count <= 2_000_000 and g == g2 and g.family == genome.family
    assert s.rng.getstate() == rng and s.candidate(d.id) == g
    assert s.proposal(d.id, g) == other.proposal(d.id, g2)
    p = s.proposal(d.id, g)
    assert p["parents"] == ["parent"] and not p["protected"]
    assert p["runtime_constraint"]["original_genome_id"] == genome.genome_id
    assert p["runtime_constraint"]["original_parameters"] > 2_000_000
    assert s.benchmarks[d.id]["operators"][g.genome_id][0] == "runtime_constraint"
    for k in m.weights:
        np.testing.assert_array_equal(m.weights[k], m2.weights[k])
    restored = Search([d], seed=0, state=json.loads(json.dumps(runner_search_snapshot(s))))
    assert restored.candidate(d.id) == g and restored.proposal(d.id, g) == p


def test_repaired_real_failure_trains_natively():
    d = get_benchmark("digits_image")
    s = Search([d], seed=7, variant="broad")
    original = ModelGenome(
        family="conv2d",
        hidden_layers=(200, 214, 214, 214),
        kernel_size=5,
        activation="gelu",
        norm_type="rms",
        weight_decay=0.06449128223802368,
    )
    place(s, d, original)
    g, m = s.compile_candidate(original, d, backend="mlx_native", device="cpu", seed=4131429670)
    rng = np.random.default_rng(5)
    x = rng.normal(size=(8, *d.input_shape)).astype(np.float32)
    y = np.arange(8) % d.output_dim
    result = fit(
        m, x, y, x, y, task="classification", config=TrainConfig(epochs=1, batch_size=4, timeout=120), seed=4131429670
    )
    assert result["updates"] == 2 and result["weights_changed"] and np.isfinite(result["score"])


def test_fixed_architecture_is_never_silently_changed():
    d = get_benchmark("digits_image")
    g = ModelGenome(family="conv2d", hidden_layers=(256,) * 6, kernel_size=5)
    s = Search([d], seed=7, variant="open", fixed_genomes={d.id: g.model_dump(mode="json")})
    with pytest.raises(ValueError, match="fixed architecture"):
        s.compile_candidate(g, d, backend="mlx_native", device="cpu", seed=91)
    assert s.candidate(d.id) == g
