from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / "scripts/policy/validate_repository_governance.py"
REPORT_PATH = REPO_ROOT / "governance/b0-report.json"
GUIDE_PATH = REPO_ROOT / "PARALLEL_WORK_GUIDE.md"
PLAN_PATH = REPO_ROOT / "CONSOLIDATED_PLAN.md"

EXPECTED_LANE_ROWS = (
    "| 0 | WP-0.2, 0.3, 0.4, 0.5 | WP-0.1, 0.6, 0.7, 0.8, 0.9 | WP-0.10 integrity gate + phase exit |",
    "| 1 | WP-1.1, 1.2, 1.7, 1.8 | WP-1.3, 1.4, 1.5, 1.6 | phase-exit fair-matrix run |",
    "| 2 | WP-2.1–2.4 | WP-2.5–2.9 | WP-2.10 + exit cohort |",
    "| 3 | WP-3.1, 3.4 | WP-3.2, 3.3 | WP-3.5 + phase exit |",
    "| 4 | WP-4.1–4.4 | WP-4.5, 4.6, 4.7 | WP-4.8 + exit cohort |",
    "| 5 | WP-5.1, 5.2 | WP-5.3 | WP-5.4 transfer proof campaign |",
    "| 6 | WP-6.1, 6.2 | WP-6.3, 6.4 | WP-6.5 portfolio statuses + WP-6.6 L-SCI |",
    "| 7 | WP-7.1, 7.2 | WP-7.3, 7.4 | WP-7.5 release governance + phase exit |",
)


def _validator():
    spec = importlib.util.spec_from_file_location("repository_governance_b0", VALIDATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _status() -> dict:
    return yaml.safe_load((REPO_ROOT / "governance/b0-status.yaml").read_text(encoding="utf-8"))


def _report() -> dict:
    assert REPORT_PATH.is_file(), "machine-readable Gate B0 report is not installed"
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def test_parallel_work_guide_is_non_authoritative_and_records_exact_lane_model() -> None:
    validator = _validator()
    assert GUIDE_PATH.is_file(), "parallel-work guide is not installed"
    metadata = validator.read_frontmatter(GUIDE_PATH)
    assert metadata == {
        "document_kind": "guide",
        "status": "current",
        "authoritative": False,
    }
    assert validator.find_active_execution_plans(REPO_ROOT) == [Path("CONSOLIDATED_PLAN.md")]
    assert validator.validate_plan_metadata(REPO_ROOT) == []

    text = GUIDE_PATH.read_text(encoding="utf-8")
    for required in (
        "Level 1 — Lab and Product repositories",
        "real artifact influence waits for Lab I1 and Product I2",
        "fixtures and co-signed schemas allow parallel build",
        "Level 2 — Lab phase lanes",
        "freeze interfaces → parallel lanes → cross-review → joint integration → joint gate",
        "B0, Foundation Integrity Gate, phase exits, transfer proof, L-SCI, portfolio status, and release governance",
        "first lane split is not authorized",
        "first safe parallel point is Phase 0",
    ):
        assert required in text
    for row in EXPECTED_LANE_ROWS:
        assert row in text


def test_consolidated_plan_records_truthful_open_b0_and_exact_next_actions() -> None:
    text = PLAN_PATH.read_text(encoding="utf-8")
    b0_section = text.split("## Gate B0", 1)[1].split("## Phase 0", 1)[0]
    for item in ("B0.1", "B0.3", "B0.4", "B0.6"):
        assert f"- [x] **{item}**" in b0_section
    for item in ("B0.2", "B0.5"):
        assert f"- [ ] **{item}**" in b0_section
    assert "authoritative_remote_url_absent" in b0_section
    assert "hosted_ci_not_executed" in b0_section
    assert "Gate B0 exit remains open; Phase 0 cannot begin" in b0_section

    next_actions = text.split("## Immediate Next Actions", 1)[1]
    expected_actions = (
        "Create the authoritative repository remote.",
        "Update provenance and close B0.2",
        "Run both hosted workflows, collect their uploaded artifacts, and close B0.5",
        "Rerun joint Gate B0 integration",
        "freeze the Phase 0 interfaces and split Lane A/Lane B",
    )
    positions = [next_actions.index(action) for action in expected_actions]
    assert positions == sorted(positions)
    assert "Expand **WP-0.1**" not in next_actions


def test_checked_in_b0_report_is_complete_and_valid() -> None:
    validator = _validator()
    report = _report()
    assert validator.validate_b0_report(report, _status(), REPO_ROOT) == []
    assert report["schema_version"] == "1.0.0"
    assert report["report_kind"] == "gate_b0_integration"
    assert report["overall_state"] == "open"
    assert report["parallel_handoff_ready"] is False
    assert report["parallel_handoff_blockers"] == ["B0.2", "B0.5"]
    assert report["blockers"] == {
        "B0.2": "authoritative_remote_url_absent",
        "B0.5": "hosted_ci_not_executed",
    }
    assert set(report["items"]) == {"B0.1", "B0.2", "B0.3", "B0.4", "B0.5", "B0.6"}
    assert [probe["backend"] for probe in report["local_runtime_probes"]] == ["numpy", "mlx"]
    assert all(probe["evidence_scope"] == "local_bootstrap_only" for probe in report["local_runtime_probes"])
    assert all(probe["optional_local_evidence"] is True for probe in report["local_runtime_probes"])


def test_b0_report_fails_closed_for_false_closure_hosted_claims_and_status_drift() -> None:
    validator = _validator()
    report = _report()
    status = _status()

    falsely_closed = copy.deepcopy(report)
    falsely_closed["overall_state"] = "closed"
    falsely_closed["parallel_handoff_ready"] = True
    falsely_closed["parallel_handoff_blockers"] = []
    errors = validator.validate_b0_report(falsely_closed, status, REPO_ROOT)
    assert any("overall_state" in error for error in errors)
    assert any("parallel_handoff_ready" in error for error in errors)

    fabricated_hosted = copy.deepcopy(report)
    fabricated_hosted["hosted_run_id"] = "12345"
    errors = validator.validate_b0_report(fabricated_hosted, status, REPO_ROOT)
    assert any("hosted evidence field" in error for error in errors)

    drifted = copy.deepcopy(report)
    drifted["items"]["B0.3"]["state"] = "open"
    errors = validator.validate_b0_report(drifted, status, REPO_ROOT)
    assert any("B0.3" in error and "b0-status.yaml" in error for error in errors)


def test_local_probe_evidence_is_optional_but_digest_checked_when_present(tmp_path: Path) -> None:
    validator = _validator()
    report = _report()
    entries = copy.deepcopy(report["local_runtime_probes"])

    assert validator.validate_local_probe_evidence(entries, tmp_path, report["repository"]["evaluated_commit"]) == []

    artifact = tmp_path / entries[0]["artifact_path"]
    artifact.parent.mkdir(parents=True)
    artifact.write_text("{}\n", encoding="utf-8")
    errors = validator.validate_local_probe_evidence(entries, tmp_path, report["repository"]["evaluated_commit"])
    assert any("SHA-256" in error for error in errors)


def test_every_checked_in_evidence_digest_is_recomputed() -> None:
    validator = _validator()
    report = _report()
    tampered = copy.deepcopy(report)
    first_path = next(iter(tampered["checked_in_evidence"]))
    tampered["checked_in_evidence"][first_path] = "0" * 64
    errors = validator.validate_b0_report(tampered, _status(), REPO_ROOT)
    assert any(first_path in error and "SHA-256" in error for error in errors)
