from copy import deepcopy
import json

import pytest

from evonn_compare.audit import apply_admission, benchmark_audit
from evonn_compare.cases import Case, evaluate_case
from evonn_compare.evidence import aggregates, trend_rows, winners
from evonn_compare.quality import classify
from evonn_shared.telemetry import SeedOverlapPolicy


def test_direction_ceiling_ties_projects_recompute_and_no_superiority(tmp_path, export_factory):
    a = export_factory(tmp_path / "a", system="contenders", score=1.)
    b = export_factory(tmp_path / "b", system="prism", score=.9)
    c = export_factory(tmp_path / "c", system="topograph", score=1.)
    acceptance = evaluate_case(Case("tier1_core", 64, 42), [a, b, c])
    rows = [r for bundle in (a, b, c) for r in trend_rows(bundle, "case", acceptance)]
    all_winners = winners(rows)
    assert all(r["winners"] == ["contenders", "topograph"] for r in all_winners)
    assert any(r["ceiling_tie"] for r in all_winners)
    assert not any(r["superiority_evidence"] for r in all_winners)
    assert all(r["winners"] == ["topograph"] for r in winners(rows, projects_only=True))
    assert all(r["case_win"] for r in winners(rows, projects_only=True))


def test_case_mismatch_engine_only_and_all_operating_states(tmp_path, export_factory):
    a = export_factory(tmp_path / "a", system="prism")
    case = Case("tier1_core", 64, 42)
    state = evaluate_case(case, [a], no_contenders=True)
    assert state["engine_only"] and not state["external_floor_claim"]
    audit = {"scope": "decision_grade", "status": "passed", "repeatability": "low_and_mid_repeated",
             "pack": "tier1_core", "clean_runs": [{"run_id": "fixture_contenders_42", "budget": 64, "seed": 42}],
             "extended_coverage_complete": True, "admitted_run_ids": ["fixture_contenders_42"]}
    assert apply_admission(state, audit)["operating_state"] == "contract-fair"
    b = export_factory(tmp_path / "b")
    full = evaluate_case(case, [a, b])
    assert apply_admission(full, audit)["operating_state"] == "trusted-core"
    assert apply_admission(full, audit, extended_complete=True)["operating_state"] == "trusted-extended"
    unreplicated = {**audit, "admitted_run_ids": []}
    assert apply_admission(full, unreplicated)["operating_state"] == "contract-fair"
    wrong_audit = {**audit, "pack": "tier_a_contract"}
    assert apply_admission(full, wrong_audit)["operating_state"] == "contract-fair"
    assert evaluate_case(case, [b], cohort="reference")["operating_state"] == "reference"
    assert evaluate_case(Case("tier1_core", 64, 43), [b])["operating_state"] == "exploratory"
    changed = b.manifest.model_copy(update={"seeding": b.manifest.seeding.model_copy(update={"seed_overlap_policy": SeedOverlapPolicy.BENCHMARK_DISJOINT})})
    with_seed_difference = type(b)(b.root, changed, b.results, b.summary)
    assert any("seeding regimes" in reason for reason in evaluate_case(case, [a, with_seed_difference])["blockers"])


def test_seed_statistics_keep_duplicates_regimes_and_blocked_runs_separate(tmp_path, export_factory):
    a = export_factory(tmp_path / "a")
    acceptance = evaluate_case(Case("tier1_core", 64, 42), [a])
    row = trend_rows(a, "case", acceptance)[0]
    repeated = {**row, "case_id": "repeat", "run_id": "repeat", "value": .9}
    seeded = deepcopy(row)
    seeded.update(case_id="seeded", run_id="seeded")
    seeded["seeding"]["seeding_ladder"] = "direct"
    blocked = {**row, "case_id": "blocked", "run_id": "blocked", "accounting_state": "blocked", "value": 100.}
    stats = aggregates([row, repeated, seeded, blocked])
    assert len(stats["spread"]) == 3
    assert all(item["n"] <= 1 and item["ci95"] is None for item in stats["spread"])
    assert next(item for item in stats["spread"] if item["accounting_state"] == "blocked")["mean"] is None


def test_quality_levels_and_audit_do_not_promote_fixture_scores(tmp_path, export_factory):
    bundle = export_factory(tmp_path / "export")
    assert classify(bundle.root)["level"] == "L2"
    assert classify(bundle.root, propagated=True)["level"] == "L3"
    audit = benchmark_audit("tier1_core", [bundle], decision_grade=True)
    assert audit["blocker_count"] and audit["status"] == "blocked"
    (bundle.root / "summary.json").unlink()
    assert classify(bundle.root)["level"] == "L1"
    (bundle.root / "results.json").write_text(json.dumps({}))
    assert classify(bundle.root)["level"] == "L0"


def test_case_rejects_fractional_and_indivisible_budgets():
    for budget in (7, 3.5, True):
        with pytest.raises(ValueError):
            Case("tier1_core", budget, 42)


def test_explicit_exporter_blocker_and_evaluation_semantics_propagate(tmp_path, export_factory):
    from evonn_shared.telemetry import FairnessFlag
    bundle = export_factory(tmp_path / "export")
    flag = FairnessFlag.model_validate_json(json.dumps({"code": "invalid_surface", "severity": "blocker",
        "benchmark_ids": [], "message": "unverified data reduction"}))
    summary = bundle.summary.model_copy(update={"fairness_flags": (flag,)})
    changed = type(bundle)(bundle.root, bundle.manifest, bundle.results, summary)
    acceptance = evaluate_case(Case("tier1_core", 64, 42), [changed])
    assert acceptance["operating_state"] == "exploratory"
    assert any("unverified data reduction" in reason for reason in acceptance["blockers"])
    rows = trend_rows(changed, "blocked", acceptance)
    assert rows[0]["evaluation_semantics"] == bundle.manifest.accounting.evaluation_semantics
    assert rows[0]["fairness_flags"][0]["severity"] == "blocker"


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "status"])
def test_audit_requires_exact_unique_attempt_projection(tmp_path, export_factory, monkeypatch, mutation):
    from evonn_compare import audit
    from evonn_shared.benchmarks import resolve_data_root
    from evonn_shared.canonical import canonical_sha256
    from evonn_shared.rng import derive_stream, StreamName
    versions = json.loads((resolve_data_root() / "runtime/tier1_core_v1.json").read_text())["versions"]
    bundle = export_factory(tmp_path / "export", budget=8)
    attempts = [{"benchmark_id": record.benchmark_id, "outcome_id": record.outcome_id,
                 "contender_id": "extra_trees", "family": "extra_trees", "parameters": {},
                 "status": "ok", "reason": None, "score": record.metric.value, "charged": 1, "invalid": 0}
                for record in bundle.results.records]
    for attempt in attempts:
        attempt["backend"] = {"package": "scikit-learn", "version": versions["scikit-learn"], "device": "cpu"}
        attempt["model_seed"] = int(canonical_sha256({"stream": str(derive_stream(bundle.manifest.seed, StreamName.INIT)),
            "benchmark": attempt["benchmark_id"], "outcome": attempt["outcome_id"]}, schema_version="evonn-contender-init-v1", digest_field=None)[:8], 16)
    if mutation == "duplicate":
        attempts[-1] = dict(attempts[0])
    elif mutation == "missing":
        attempts.pop()
    else:
        attempts[0]["status"] = "skipped"
    documents = {
        "config.yaml": {"dataset_versions": versions, "git_commit": bundle.manifest.git_commit, "seed": bundle.manifest.seed, "code_dirty": False,
                        "pools": {"models": {"extra_trees": {"model": "extra_trees", "parameters": {}}}}},
        "attempts.json": {"accounting": bundle.manifest.accounting.model_dump(mode="json"), "attempts": attempts},
        "dataset_provenance.json": [],
    }
    monkeypatch.setattr(audit, "artifact_json", lambda b, name: documents[name])
    result = audit.benchmark_audit("tier1_core", [bundle])
    expected = {"duplicate": "duplicate attempt", "missing": "every exported outcome", "status": "status/reason/charge"}[mutation]
    assert any(expected in reason for reason in result["blockers"])
    assert result["clean_runs"] == []


def test_seed_groups_keep_full_budget_envelopes_separate(tmp_path, export_factory):
    a = export_factory(tmp_path / "a")
    b = export_factory(tmp_path / "b", seed=43)
    changed_budget = b.manifest.budget.model_copy(update={"wall_clock": b.manifest.budget.wall_clock.model_copy(update={"target_seconds": 123.0})})
    changed = type(b)(b.root, b.manifest.model_copy(update={"budget": changed_budget}), b.results, b.summary)
    rows = trend_rows(a, "a", evaluate_case(Case("tier1_core", 64, 42), [a]))
    rows += trend_rows(changed, "b", evaluate_case(Case("tier1_core", 64, 43), [changed]))
    stats = aggregates(rows)
    assert len(stats["spread"]) == 16 and all(item["n"] == 1 for item in stats["spread"])


def test_runtime_presets_require_exact_unique_evidence_bindings(monkeypatch):
    from evonn_compare import cases
    import json
    receipt = {"runtime_presets": {"local": {"pack": "tier1_core", "budget": 64, "run_ids": ["present", "missing"]}},
               "runs": [{"run_id": "present", "pack": "tier1_core", "budget": 64, "status": "completed"}] * 2}
    monkeypatch.setattr(cases, "read_document", lambda *a: json.dumps(receipt).encode())
    with pytest.raises(ValueError, match="unique"):
        cases.resolve_preset("local")
    receipt["runs"] = receipt["runs"][:1]
    with pytest.raises(ValueError, match="incomplete"):
        cases.resolve_preset("local")
    receipt["runtime_presets"]["local"]["run_ids"] = ["present"]
    assert cases.resolve_preset("local") == ("tier1_core", 64)
