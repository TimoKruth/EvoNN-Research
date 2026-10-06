"""Statistical and execution-design checks; these tests do not fit models."""

from copy import deepcopy
from contextlib import nullcontext
from itertools import product
import json

import numpy as np
import pytest
from scipy.stats import rankdata

from evonn_compare import campaign as c
from evonn_compare import prism_confidence as study
from evonn_compare.prism_confidence_stats import PRIMARY_TASKS, holm, inference, signed_rank, symmetric_effect
from evonn_shared.prism_policy import PrismResearchPolicy


def test_prism_exception_is_explicit_and_does_not_weaken_general_roster():
    with pytest.raises(ValueError, match="every engine"):
        c.CampaignSpec(systems=["prism"], prism_research=PrismResearchPolicy())
    values = dict(systems=["prism"], prism_research=PrismResearchPolicy(),
                  prism_version_study="user-requested-20260921")
    assert c.CampaignSpec(**values).systems == ["prism"]
    for change in ({"systems": ["prism", "topograph"]}, {"prism_research": None},
                   {"topograph_variant": "open"}, {"enhanced": True}):
        with pytest.raises(ValueError, match="exclusively Prism"):
            c.CampaignSpec(**{**values, **change})


def test_matrix_covers_every_variant_seed_panel_and_balances_order():
    rows = study.campaigns()
    plan = study.schedule(rows)
    assert len(rows) == 55 and len(plan) == 1012
    expected = {(panel, arm, seed) for panel in study.PANELS for arm in study.ARMS for seed in study.SEEDS}
    actual = [(r["panel"], r["arm"], r["seed"]) for r in plan if r["stage"] == "main"]
    assert set(actual) == expected and len(actual) == len(expected) == 990
    assert all(r["stage"] == "qualification" for r in plan[:22])
    assert study.QUALIFICATION_SEED not in study.SEEDS
    assert sum(len(r["spec"]["seeds"]) * r["spec"]["budgets"][0] for r in rows) == 169664
    by_path = {r["campaign"]: r for r in rows}
    for panel in study.PANELS:
        order = [[r["arm"] for r in plan if r["panel"] == panel and r["seed"] == seed] for seed in study.SEEDS]
        for arm in study.ARMS:
            counts = [sum(line[index] == arm for line in order) for index in range(len(study.ARMS))]
            assert max(counts) - min(counts) <= 1
    for row in rows:
        assert row["spec"]["systems"] == ["prism"]
        assert [e["seed"] for e in plan if e["campaign"] == row["campaign"]] == row["spec"]["seeds"]
    assert len(by_path) == len(rows)


@pytest.mark.parametrize("values", [[0, 0, 0], [1, 1, -1, 2, 0], [1, 2, 3, 4], [.1, -.2, .4, -.4, 1]])
def test_exact_signed_rank_matches_exhaustive_signs_with_ties(values):
    array = np.round(np.asarray(values), 12)
    array = array[array != 0]
    if not len(array):
        expected = 1.
    else:
        ranks = rankdata(np.abs(array))
        actual = min(ranks[array > 0].sum(), ranks[array < 0].sum())
        tails = [min(np.dot(signs, ranks), ranks.sum() - np.dot(signs, ranks))
                 for signs in product((0, 1), repeat=len(array))]
        expected = np.mean(np.asarray(tails) <= actual)
    assert signed_rank(values)["pvalue"] == pytest.approx(expected)


def test_holm_and_all_zero_handling_are_conservative():
    assert holm([.03, .001, .04]) == pytest.approx([.06, .003, .06])
    assert signed_rank([1] * 30)["pvalue"] == 2 / 2**30
    assert signed_rank([1e-14] * 30) == {"pvalue": 1., "nonzero_pairs": 0}
    assert symmetric_effect(10, 8, "min") > 0
    assert symmetric_effect(.8, .9, "max") > 0


def synthetic_rows(arms):
    return [{"panel": panel, "arm": arm, "seed": seed, "benchmark": task, "direction": "min",
             "value": 10. if arm == arms[0] else 8.}
            for panel, tasks in PRIMARY_TASKS.items() for arm in arms for seed in study.SEEDS for task in tasks]


def test_inference_rejects_missing_or_duplicate_cells_and_never_claims_ties_as_equivalence():
    arms = ["open", "frontier_v2"]
    rows = synthetic_rows(arms)
    result = inference(rows, arms, study.SEEDS)
    assert result["holm_family_size"] == 2
    assert all(c["supported_winner"] == "frontier_v2" for c in result["contrasts"])
    with pytest.raises(KeyError):
        inference(rows[:-1], arms, study.SEEDS)
    with pytest.raises(ValueError, match="duplicate"):
        inference(rows + [rows[0]], arms, study.SEEDS)
    for row in rows:
        row["value"] = 10.
    assert all(c["decision"] == "inconclusive" for c in inference(rows, arms, study.SEEDS)["contrasts"])


def test_plan_integrity_rejects_outcome_dependent_matrix_changes(tmp_path, monkeypatch):
    rows = study.campaigns()
    manifests = {row["campaign"]: {"spec": row["spec"], "identity": {"commit": "a" * 40},
                                   "sha256": str(i)} for i, row in enumerate(rows)}
    value = {"schema_version": "evonn.prism-confidence-study/v1", "policy": study.policy(),
             "identity": {"commit": "a" * 40}, "campaigns": rows, "schedule": study.schedule(rows),
             "campaign_hashes": {key: v["sha256"] for key, v in manifests.items()}}
    monkeypatch.setattr(c, "read_manifest", lambda path: manifests[str(path.relative_to(tmp_path))])
    def publish(document):
        (tmp_path / "study.json").write_text(json.dumps({**document, "sha256": c.sha(document)}))
    publish(value)
    assert study.read_plan(tmp_path)["policy"] == study.policy()
    changed = deepcopy(value)
    changed["schedule"].pop()
    publish(changed)
    with pytest.raises(ValueError, match="frozen"):
        study.read_plan(tmp_path)


def test_controller_qualifies_every_arm_before_main_and_stops_on_failure(tmp_path, monkeypatch):
    rows = study.campaigns()
    plan = {"campaigns": rows, "schedule": study.schedule(rows)}
    receipts = {row["campaign"]: {} for row in rows}
    by_path = {row["campaign"]: row for row in rows}
    calls, replayed = [], []
    monkeypatch.setattr(study, "preflight", lambda root: {})
    monkeypatch.setattr(study, "read_plan", lambda root: plan)
    monkeypatch.setattr(study, "completed_receipts", lambda *args: deepcopy(receipts))
    monkeypatch.setattr(c, "lease", lambda path: nullcontext())
    monkeypatch.setattr(c, "read_manifest", lambda path: {})
    monkeypatch.setattr(study, "adopt_scheduled", lambda *args: False)
    def events(workspace, manifest):
        key = str(workspace.relative_to(tmp_path))
        return [{"kind": "complete", "slot": identifier, "details": reference}
                for identifier, reference in receipts[key].items()]
    monkeypatch.setattr(c, "events", events)
    def dispatch(workspace, **options):
        key = str(workspace.relative_to(tmp_path))
        row = by_path[key]
        assert row["stage"] == "qualification"
        entry = next(e for e in plan["schedule"] if e["campaign"] == key)
        _, identifier = study.slot(row, entry)
        calls.append(key)
        receipts[key][identifier] = {"run_id": identifier}
        return {"new_runs": 1}
    monkeypatch.setattr(c, "run_campaign", dispatch)
    monkeypatch.setattr(study, "replay", lambda root, row, entry: replayed.append(row["campaign"]))
    result = study.run(tmp_path, qualification_only=True)
    assert result["status"] == "qualification_complete" and len(calls) == len(replayed) == 22
    calls.clear()
    assert study.run(tmp_path, qualification_only=True)["new_runs"] == 0
    assert calls == []
    receipts[rows[0]["campaign"]].clear()
    def failure(*args, **kwargs):
        calls.append("failed")
        raise ValueError("retained failure")
    monkeypatch.setattr(c, "run_campaign", failure)
    with pytest.raises(ValueError, match="retained failure"):
        study.run(tmp_path)
    assert calls == ["failed"]


def test_partial_study_cannot_publish_inference(tmp_path, monkeypatch):
    rows = study.campaigns()
    plan = {"campaigns": rows, "schedule": study.schedule(rows)}
    monkeypatch.setattr(study, "read_plan", lambda root: plan)
    monkeypatch.setattr(study, "completed_receipts", lambda *args: {r["campaign"]: {} for r in rows})
    monkeypatch.setattr(study, "inference", lambda *args: pytest.fail("must not peek at incomplete results"))
    result = study.analyze(tmp_path)
    assert result["status"] == "incomplete" and result["missing_runs"] == 1012
    assert not (tmp_path / "analysis.json").exists()


def test_orphan_export_adoption_never_dispatches_a_later_seed(tmp_path, monkeypatch):
    history, appended = [], []
    monkeypatch.setattr(c, "lease", lambda path: nullcontext())
    monkeypatch.setattr(c, "read_manifest", lambda path: {})
    monkeypatch.setattr(c, "events", lambda *args: history)
    monkeypatch.setattr(c, "active_dispatch", lambda *args: None)
    monkeypatch.setattr(c, "adopted", lambda *args: (tmp_path, {"run_id": "retained"}))
    monkeypatch.setattr(c, "append_event", lambda *args: appended.append(args))
    monkeypatch.setattr(c, "run_campaign", lambda *args, **kwargs: pytest.fail("orphan adoption must not dispatch"))
    case = c.Case("tier_b_core_v2", 128, 21601)
    assert study.adopt_scheduled(tmp_path, case)
    assert appended[0][3:5] == (c.slot_id(case, "prism"), "complete")
