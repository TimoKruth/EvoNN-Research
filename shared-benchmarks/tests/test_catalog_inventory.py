from __future__ import annotations

import json
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


def test_pack_floor_covers_every_member_requirement() -> None:
    definitions = {item.id: item for item in list_benchmarks(shared_root=SHARED_ROOT)}
    for pack_name in EXPECTED_PACK_BUDGETS:
        pack = load_parity_pack(pack_name, shared_root=SHARED_ROOT)
        required = set().union(*(definitions[item].required_contenders for item in pack.benchmarks))
        assert set(pack.minimum_contenders) == required


def test_provenance_does_not_promote_catalog_metadata_to_runtime_evidence() -> None:
    provenance = json.loads((SHARED_ROOT / "provenance" / "tier_a_catalog_v1.json").read_text())
    assert provenance["commit"] == "3652e0a32a907b51fb26a56fa9650ba258cb9054"
    assert provenance["status"] == "proposal_not_admitted"
    assert len({source["path"] for source in provenance["sources"]}) == 10
    assert provenance["historical_split"]["protected_test_split"] is None
    assert provenance["runtime_admission_blockers"]
