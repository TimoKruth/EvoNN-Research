from __future__ import annotations

from pathlib import Path

from evonn_shared.catalog import BenchmarkStatus, InputModality, list_benchmarks, load_parity_pack


SHARED_ROOT = Path(__file__).parents[1]
EXPECTED_BENCHMARK_IDS = (
    "breast_cancer",
    "credit_g_classification",
    "diabetes_regression",
    "digits_image",
    "friedman1_regression",
    "iris_classification",
    "moons_classification",
    "wine_classification",
)
EXPECTED_PACK_BENCHMARKS = (
    "iris_classification",
    "wine_classification",
    "breast_cancer",
    "moons_classification",
    "digits_image",
    "diabetes_regression",
    "friedman1_regression",
    "credit_g_classification",
)
EXPECTED_PACK_BUDGETS = {
    "tier1_core": 64,
    "tier1_core_smoke": 16,
    "tier_a_contract": 64,
}


def test_phase0_catalog_has_the_authoritative_eight_benchmarks() -> None:
    benchmarks = list_benchmarks(shared_root=SHARED_ROOT)

    assert tuple(benchmark.id for benchmark in benchmarks) == EXPECTED_BENCHMARK_IDS
    assert {benchmark.status for benchmark in benchmarks} == {BenchmarkStatus.PLANNED}
    assert all("catalog_only" in benchmark.tags for benchmark in benchmarks)


def test_phase0_required_packs_load_the_same_immutable_benchmark_identities() -> None:
    for pack_name, evaluation_count in EXPECTED_PACK_BUDGETS.items():
        pack = load_parity_pack(pack_name, shared_root=SHARED_ROOT)

        assert pack.benchmarks == EXPECTED_PACK_BENCHMARKS
        assert pack.budget_policy.evaluation_count == evaluation_count
        assert pack.budget_policy.evaluation_count % len(pack.benchmarks) == 0
        assert pack.modalities == (InputModality.IMAGE, InputModality.TABULAR)
        assert pack.minimum_contenders


def test_phase0_smoke_pack_reduces_budget_without_redefining_datasets() -> None:
    core = load_parity_pack("tier1_core", shared_root=SHARED_ROOT)
    smoke = load_parity_pack("tier1_core_smoke", shared_root=SHARED_ROOT)

    assert smoke.benchmarks == core.benchmarks
    assert smoke.budget_policy.evaluation_count < core.budget_policy.evaluation_count
