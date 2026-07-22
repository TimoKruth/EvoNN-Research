from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / "scripts/policy/validate_repository_governance.py"
REPORT_PATH = REPO_ROOT / "governance/b0-report.json"
GUIDE_PATH = REPO_ROOT / "PARALLEL_WORK_GUIDE.md"
PLAN_PATH = REPO_ROOT / "CONSOLIDATED_PLAN.md"
CROSS_REVIEW_PATH = REPO_ROOT / "reviews/2026-07-18-b0-cross-review.md"
TASK_REPORT_PATH = REPO_ROOT / ".superpowers/sdd/task-6-report.md"
HOSTED_LINUX_PATH = (
    REPO_ROOT / "governance/evidence/b0/hosted/linux-runtime-probe.json"
)
HOSTED_MACOS_PATH = (
    REPO_ROOT / "governance/evidence/b0/hosted/macos-runtime-probe.json"
)
LEGACY_REPORT_REVISION = "cc067143fd3143eaba490c4dcc9f3765db1d70f2"
LEGACY_TRANSITION_MERGE = "e6117bc2f7c25d52b1bf0ea30361e25b2f2ddfe8"
PHASE0_APRIME = "b720ea6461c970e3875f8ef735e3e63cf680b660"
PHASE0_BINDING_PATHS = (
    "CONSOLIDATED_PLAN.md",
    "PARALLEL_WORK_GUIDE.md",
    "governance/phase0-interface-freeze.yaml",
    "reviews/2026-07-21-phase0-lane-a-producer-review.md",
    "reviews/2026-07-21-phase0-lane-b-consumer-review.md",
    "scripts/ci/b0-policy-checks.sh",
    "scripts/policy/validate_phase0_interface_freeze.py",
    "scripts/policy/validate_repository_governance.py",
    "tests/policy/test_b0_ci_bootstrap.py",
    "tests/policy/test_b0_integration_report.py",
    "tests/policy/test_phase0_interface_freeze.py",
    "tests/policy/test_repository_governance.py",
)
PHASE0_BINDING_MODES = {
    relative: "100755" if relative == "scripts/ci/b0-policy-checks.sh" else "100644"
    for relative in PHASE0_BINDING_PATHS
}
SCHEMA_2_B02_REQUIRED_EVIDENCE = frozenset(
    {
        "governance/authority-provenance.yaml",
        "governance/SPEC_UPGRADE_PROCESS.md",
        "governance/SPEC_TRACEABILITY.md",
        "governance/b0-report.json",
    }
)
SCHEMA_2_B05_REQUIRED_EVIDENCE = frozenset(
    {
        ".github/workflows/linux-trust.yml",
        ".github/workflows/macos-engines.yml",
        "scripts/ci/runtime_probe.py",
        "governance/b0-report.json",
        "governance/evidence/b0/hosted/linux-runtime-probe.json",
        "governance/evidence/b0/hosted/macos-runtime-probe.json",
    }
)
SCHEMA_2_B06_REQUIRED_EVIDENCE = frozenset(
    {
        "scripts/policy/validate_repository_governance.py",
        "tests/policy/test_repository_governance.py",
        "tests/policy/test_b0_integration_report.py",
        "tests/policy/test_b0_ci_bootstrap.py",
        "PARALLEL_WORK_GUIDE.md",
        "reviews/2026-07-18-b0-cross-review-addendum.md",
        "reviews/2026-07-19-b0-closure-review.md",
        "governance/b0-report.json",
    }
)

HOSTED_ARTIFACTS = (
    (
        HOSTED_LINUX_PATH,
        "f17ca8a8f35538d72c6a7585ef013a7e1f5d50484fcc08d85ac672745d371c00",
        "numpy",
        "stratograph",
        "B0 Linux trust lane",
        "29658842317",
        "Linux",
        "x86_64",
    ),
    (
        HOSTED_MACOS_PATH,
        "147e5c54a75bb9090eb3e94e06fe9c9f656ca751df12fdb5fc8950bf4398e157",
        "mlx",
        "prism",
        "B0 macOS engine lane",
        "29658842318",
        "Darwin",
        "arm64",
    ),
)

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


def _closed_state_documents(validator) -> tuple[dict, dict]:
    report = {
        "schema_version": "2.0.0",
        "overall_state": "closed",
        "blockers": {},
        "parallel_handoff_ready": True,
        "parallel_handoff_blockers": [],
        "next_transition": validator.B0_REPORT_CLOSED_NEXT_TRANSITION,
        "items": {
            item_id: {"state": "closed", "reason": None, "evidence_paths": ["x"]}
            for item_id in validator.REQUIRED_B0_ITEM_IDS
        },
    }
    status = {
        "status": "closed",
        "items": {
            item_id: {"status": "closed", "open_reason": None}
            for item_id in validator.REQUIRED_B0_ITEM_IDS
        },
    }
    return report, status


def _schema_2_mapping_errors(validator, report: dict, status: dict) -> list[str]:
    errors = validator.validate_b0_schema_2_state(report, status)
    repository = report.get("repository")
    evaluated_commit = (
        repository.get("evaluated_commit")
        if isinstance(repository, dict)
        else None
    )
    errors.extend(
        validator.validate_local_probe_evidence(
            report.get("local_runtime_probes"),
            REPO_ROOT,
            evaluated_commit,
        )
    )
    workflows = report.get("workflows")
    if isinstance(workflows, list):
        for index, workflow in enumerate(workflows):
            validator._closed_report_mapping(
                workflow,
                validator.B0_REPORT_WORKFLOW_FIELDS,
                f"B0 report workflows[{index}]",
                errors,
            )
    verification = validator._closed_report_mapping(
        report.get("verification"),
        validator.B0_REPORT_VERIFICATION_FIELDS,
        "B0 report verification",
        errors,
    )
    validator._closed_report_mapping(
        verification.get("summary"),
        validator.B0_REPORT_VERIFICATION_SUMMARY_FIELDS,
        "B0 report verification.summary",
        errors,
    )
    commands = verification.get("commands")
    if isinstance(commands, list):
        for index, command in enumerate(commands):
            validator._closed_report_mapping(
                command,
                validator.B0_REPORT_VERIFICATION_COMMAND_FIELDS,
                f"B0 report verification.commands[{index}]",
                errors,
            )
    return errors


def _schema_2_state_documents(validator) -> tuple[dict, dict]:
    report = copy.deepcopy(_report())
    status = copy.deepcopy(_status())
    report["schema_version"] = "2.0.0"
    report["repository"]["branch"] = "b0/close-gate"
    report["overall_state"] = "closed"
    report["blockers"] = {}
    report["parallel_handoff_ready"] = True
    report["parallel_handoff_blockers"] = []
    report["next_transition"] = validator.B0_REPORT_CLOSED_NEXT_TRANSITION
    report["hosted_runtime_probes"] = _hosted_entries(validator)
    for item in report["items"].values():
        item["state"] = "closed"
        item["reason"] = None
    report["items"]["B0.2"]["evidence_paths"] = sorted(
        {*report["items"]["B0.2"]["evidence_paths"], *SCHEMA_2_B02_REQUIRED_EVIDENCE}
    )
    report["items"]["B0.5"]["evidence_paths"] = sorted(
        {*report["items"]["B0.5"]["evidence_paths"], *SCHEMA_2_B05_REQUIRED_EVIDENCE}
    )
    report["items"]["B0.6"]["evidence_paths"] = sorted(
        {*report["items"]["B0.6"]["evidence_paths"], *SCHEMA_2_B06_REQUIRED_EVIDENCE}
    )

    status["status"] = "closed"
    for item in status["items"].values():
        item["status"] = "closed"
        item["open_reason"] = None
    return report, status


def test_schema_2_closed_state_requires_all_six_items_closed() -> None:
    validator = _validator()
    report, status = _closed_state_documents(validator)
    assert validator.validate_b0_closure_state(report, status) == []

    report["items"]["B0.5"]["state"] = "open"
    errors = validator.validate_b0_closure_state(report, status)
    assert any("B0.5" in error for error in errors)


def test_b0_closure_state_rejects_nonclosed_item() -> None:
    validator = _validator()
    report, status = _closed_state_documents(validator)
    report["items"]["B0.3"]["state"] = "locally_satisfied"

    errors = validator.validate_b0_closure_state(report, status)

    assert any("B0.3" in error and "closed" in error for error in errors)


def test_b0_closure_state_rejects_reason_on_closed_item() -> None:
    validator = _validator()
    report, status = _closed_state_documents(validator)
    report["items"]["B0.4"]["reason"] = "stale reason"

    errors = validator.validate_b0_closure_state(report, status)

    assert any("B0.4" in error and "reason" in error for error in errors)


def test_b0_closure_state_rejects_report_status_mismatch() -> None:
    validator = _validator()
    report, status = _closed_state_documents(validator)
    status["items"]["B0.1"]["status"] = "open"

    errors = validator.validate_b0_closure_state(report, status)

    assert any("B0.1" in error and "b0-status.yaml" in error for error in errors)


def test_b0_closure_state_rejects_nonempty_blockers() -> None:
    validator = _validator()
    report, status = _closed_state_documents(validator)
    report["blockers"] = {"B0.5": "stale"}

    errors = validator.validate_b0_closure_state(report, status)

    assert any("blockers" in error for error in errors)


def test_b0_closure_state_requires_parallel_handoff_ready() -> None:
    validator = _validator()
    report, status = _closed_state_documents(validator)
    report["parallel_handoff_ready"] = False

    errors = validator.validate_b0_closure_state(report, status)

    assert any("parallel_handoff_ready" in error for error in errors)


def test_b0_closure_state_rejects_handoff_blockers() -> None:
    validator = _validator()
    report, status = _closed_state_documents(validator)
    report["parallel_handoff_blockers"] = ["B0.5"]

    errors = validator.validate_b0_closure_state(report, status)

    assert any("parallel_handoff_blockers" in error for error in errors)


def test_b0_closure_state_requires_explicit_null_open_reason() -> None:
    validator = _validator()
    report, status = _closed_state_documents(validator)
    del status["items"]["B0.3"]["open_reason"]

    errors = validator.validate_b0_closure_state(report, status)

    assert any("B0.3" in error and "open_reason" in error for error in errors)


@pytest.mark.parametrize("schema_version", [[], {}])
def test_b0_report_rejects_non_string_schema_versions_without_git_work(
    schema_version,
    monkeypatch,
) -> None:
    validator = _validator()
    report = _report()
    report["schema_version"] = schema_version
    monkeypatch.setattr(
        validator,
        "_git",
        lambda *args: pytest.fail(f"invalid schema spawned Git: {args}"),
    )

    errors = validator.validate_b0_report(report, _status(), REPO_ROOT)

    assert any("schema_version" in error for error in errors)


def test_hosted_probe_helper_rejects_explicit_absence() -> None:
    validator = _validator()

    errors = validator.validate_hosted_probe_evidence(None, REPO_ROOT, _head())

    assert any("exactly two entries" in error for error in errors)


def test_checked_in_hosted_runtime_probe_bytes_and_identities_are_exact() -> None:
    for path, digest, backend, system, workflow, run_id, host_os, architecture in HOSTED_ARTIFACTS:
        content = path.read_bytes()
        assert hashlib.sha256(content).hexdigest() == digest
        probe = json.loads(content)
        assert probe["schema_version"] == "1.0.0"
        assert probe["probe_kind"] == "b0_runtime_backend_bootstrap"
        assert probe["status"] == "passed"
        assert probe["qualification"] == "bootstrap_probe_only"
        assert probe["backend"]["distribution"] == backend
        assert probe["system_under_test"] == system
        assert probe["workflow"] == {
            "name": workflow,
            "run_id": run_id,
            "attempt": "1",
        }
        assert probe["host"]["os_name"] == host_os
        assert probe["host"]["architecture"] == architecture
        assert (
            probe["repository_commit"]
            == "f68856f0c2fdf0ebc73671264b5a3ab0cff3b224"
        )


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
    ):
        assert required in text
    assert "Gate B0 is closed" in text
    assert "status: approved_pending_merge" in text
    assert "lane_authorization: false" in text
    assert "no Phase 0 lane branch exists" in text
    assert "protected PR merge → verify canonical merge → attestation" in text
    assert "WP-0.10 and the Phase 0 exit remain joint" in text
    assert "no Phase 0 lane branch may begin before" not in text
    for row in EXPECTED_LANE_ROWS:
        assert row in text


def test_consolidated_plan_records_closed_b0_and_exact_next_actions() -> None:
    text = PLAN_PATH.read_text(encoding="utf-8")
    b0_section = text.split("## Gate B0", 1)[1].split("## Phase 0", 1)[0]

    for item in ("B0.1", "B0.2", "B0.3", "B0.4", "B0.5", "B0.6"):
        assert f"- [x] **{item}**" in b0_section

    assert "authoritative_remote_url_absent" not in b0_section
    assert "hosted_ci_not_executed" not in b0_section
    assert "Gate B0 is closed" in b0_section
    assert "bootstrap_probe_only" in b0_section
    assert "not scientific" in b0_section
    assert "f68856f0c2fdf0ebc73671264b5a3ab0cff3b224" in b0_section
    assert "29658842317" in b0_section
    assert "29658842318" in b0_section
    assert "legacy open record until Commit B" not in b0_section
    assert "jointly freeze and record the Phase 0 interfaces" not in b0_section
    assert "approved_pending_merge" in b0_section
    assert "protected freeze PR" in b0_section
    assert "separate authorization attestation" in b0_section

    phase0_section = text.split("## Phase 0", 1)[1].split("## Phase 1", 1)[0]
    for item in ("WP-0.1", "WP-0.2", "WP-0.3", "WP-0.4", "WP-0.5", "WP-0.6", "WP-0.7", "WP-0.8", "WP-0.9", "WP-0.10"):
        assert f"- [ ] **{item}" in phase0_section

    next_actions = text.split("## Immediate Next Actions", 1)[1]
    assert "status: approved_pending_merge" in next_actions
    assert "lane_authorization: false" in next_actions
    assert "protected PR merge → verify canonical merge → attestation" in next_actions
    assert "only then create the Phase 0 lane and integration branches" in next_actions
    assert "WP-0.10 and the Phase 0 exit remain joint" in next_actions
    assert "Jointly freeze the Phase 0 interfaces" not in next_actions
    assert "Record the co-signed interface freeze" not in next_actions


def test_checked_in_b0_report_is_complete_and_valid() -> None:
    validator = _validator()
    report = _report()
    status = _status()

    assert validator.validate_b0_report(report, status, REPO_ROOT) == []

    if report["schema_version"] == "1.0.0":
        assert report["overall_state"] == "open"
        assert report["parallel_handoff_ready"] is False
        assert report["parallel_handoff_blockers"] == ["B0.2", "B0.5"]
    else:
        assert report["schema_version"] == "2.0.0"
        assert report["overall_state"] == "closed"
        assert report["blockers"] == {}
        assert report["parallel_handoff_ready"] is True
        assert report["parallel_handoff_blockers"] == []
        assert all(
            item["state"] == "closed"
            for item in report["items"].values()
        )
        assert report["hosted_runtime_probes"] == list(
            validator.B0_REPORT_HOSTED_PROBES
        )


def test_b0_report_fails_closed_for_false_closure_hosted_claims_and_status_drift() -> None:
    validator = _validator()
    report = _report()
    status = _status()

    wrong_gate_state = copy.deepcopy(report)
    if report["schema_version"] == "1.0.0":
        wrong_gate_state["overall_state"] = "closed"
        wrong_gate_state["parallel_handoff_ready"] = True
        wrong_gate_state["parallel_handoff_blockers"] = []
    else:
        wrong_gate_state["overall_state"] = "open"
        wrong_gate_state["parallel_handoff_ready"] = False
        wrong_gate_state["parallel_handoff_blockers"] = ["B0.5"]

    def validate_state(candidate: dict) -> list[str]:
        if report["schema_version"] == "1.0.0":
            return validator.validate_b0_report(candidate, status, REPO_ROOT)
        return validator.validate_b0_schema_2_state(candidate, status)

    errors = validate_state(wrong_gate_state)
    assert any("overall_state" in error for error in errors)
    assert any("parallel_handoff_ready" in error for error in errors)

    fabricated_hosted = copy.deepcopy(report)
    fabricated_hosted["hosted_run_id"] = "12345"
    errors = validate_state(fabricated_hosted)
    expected = "hosted evidence field" if report["schema_version"] == "1.0.0" else "unknown fields"
    assert any(expected in error for error in errors)

    drifted = copy.deepcopy(report)
    drifted["items"]["B0.3"]["state"] = "open"
    errors = validate_state(drifted)
    assert any("B0.3" in error and "b0-status.yaml" in error for error in errors)


def test_b0_report_schema_rejects_unknown_fields_at_every_nested_object_level() -> None:
    validator = _validator()
    report = _report()
    mutations: list[tuple[str, dict]] = []

    top = copy.deepcopy(report)
    top["hosted_evidence"] = {}
    mutations.append(("top-level", top))

    repository = copy.deepcopy(report)
    repository["repository"]["hosted_evidence"] = {}
    mutations.append(("repository", repository))

    item = copy.deepcopy(report)
    item["items"]["B0.1"]["unexpected"] = True
    mutations.append(("item", item))

    probe = copy.deepcopy(report)
    probe["local_runtime_probes"][0]["unexpected"] = True
    mutations.append(("probe", probe))

    workflow = copy.deepcopy(report)
    workflow["workflows"][0]["unexpected"] = True
    mutations.append(("workflow", workflow))

    verification = copy.deepcopy(report)
    verification["verification"]["unexpected"] = True
    mutations.append(("verification", verification))

    summary = copy.deepcopy(report)
    summary["verification"]["summary"]["unexpected"] = True
    mutations.append(("verification summary", summary))

    command = copy.deepcopy(report)
    command["verification"]["commands"][0]["unexpected"] = True
    mutations.append(("verification command", command))

    status = _status()
    for level, malformed in mutations:
        errors = (
            validator.validate_b0_report(malformed, status, REPO_ROOT)
            if report["schema_version"] == "1.0.0"
            else _schema_2_mapping_errors(validator, malformed, status)
        )
        assert any("unknown fields" in error for error in errors), level


def test_b0_report_requires_evaluated_commit_to_be_direct_parent_of_evidence_commit() -> None:
    validator = _validator()
    report = _report()
    head = subprocess.check_output(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], text=True).strip()
    tree = subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD^{tree}"], text=True
    ).strip()
    malformed = copy.deepcopy(report)
    malformed["repository"]["evaluated_commit"] = head
    malformed["repository"]["evaluated_tree"] = tree

    errors = validator.validate_b0_report(malformed, _status(), REPO_ROOT)

    assert any("direct parent" in error for error in errors)


def test_b0_report_rejects_a_merge_evidence_revision(tmp_path: Path) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    report, status, evidence_commit = _install_schema_2_evidence_revision(
        clone, validator
    )
    parent = subprocess.check_output(
        ["git", "-C", str(clone), "rev-parse", f"{evidence_commit}^"],
        text=True,
    ).strip()
    parent_tree = subprocess.check_output(
        ["git", "-C", str(clone), "rev-parse", f"{parent}^{{tree}}"],
        text=True,
    ).strip()
    evidence_tree = subprocess.check_output(
        ["git", "-C", str(clone), "rev-parse", f"{evidence_commit}^{{tree}}"],
        text=True,
    ).strip()
    git = [
        "git",
        "-C",
        str(clone),
        "-c",
        "user.name=policy-test",
        "-c",
        "user.email=policy@test",
    ]
    second_parent = subprocess.check_output(
        [*git, "commit-tree", parent_tree, "-p", parent, "-m", "side parent"],
        text=True,
    ).strip()
    merge_evidence = subprocess.check_output(
        [
            *git,
            "commit-tree",
            evidence_tree,
            "-p",
            parent,
            "-p",
            second_parent,
            "-m",
            "merge evidence revision",
        ],
        text=True,
    ).strip()
    subprocess.run(
        ["git", "-C", str(clone), "reset", "--hard", "--quiet", merge_evidence],
        check=True,
        capture_output=True,
    )

    errors = validator.validate_b0_report(report, status, clone)

    assert any("single-parent" in error for error in errors)


def test_b0_report_rejects_a_symlink_mode_frozen_report(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    report, status, evidence_commit = _install_schema_2_evidence_revision(
        clone, validator
    )
    replacement = _replace_evidence_report_with_symlink_mode(
        clone, evidence_commit
    )

    mode = subprocess.check_output(
        [
            "git",
            "-C",
            str(clone),
            "ls-tree",
            replacement,
            "--",
            "governance/b0-report.json",
        ],
        text=True,
    ).split()[0]
    assert mode == "120000"
    assert (clone / "governance/b0-report.json").read_bytes() == _git_show_bytes(
        clone, replacement, "governance/b0-report.json"
    )

    errors = validator.validate_b0_report(report, status, clone)

    assert any("frozen B0 report" in error and "regular file" in error for error in errors)


def test_b0_report_rejects_an_evidence_revision_with_a_fourth_changed_path(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    report, status, _ = _install_schema_2_evidence_revision(
        clone,
        validator,
        extra_evidence_path="unrelated.txt",
    )

    errors = validator.validate_b0_report(report, status, clone)

    assert any(
        "evidence-only commit diff" in error and "unrelated.txt" in error
        for error in errors
    )


def test_schema_2_report_remains_valid_on_descendants_of_the_evidence_commit(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    report, status, evidence_commit = _install_schema_2_evidence_revision(
        clone, validator
    )
    digest_path = "CONSOLIDATED_PLAN.md"
    frozen_digest_bytes = _git_show_bytes(clone, evidence_commit, digest_path)
    (clone / digest_path).write_text(
        "descendant plan bytes differ from frozen evidence\n",
        encoding="utf-8",
    )
    descendant = _commit_clone(clone, "later development commit")

    assert descendant != evidence_commit
    assert (clone / digest_path).read_bytes() != frozen_digest_bytes
    assert validator.validate_b0_report(report, status, clone) == []


def test_schema_2_report_ignores_live_status_and_authority_drift_on_descendants(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    report, status, evidence_commit = _install_schema_2_evidence_revision(
        clone, validator
    )
    live_status = copy.deepcopy(status)
    live_status["status"] = "open"
    live_status["items"]["B0.2"]["status"] = "open"
    live_status["items"]["B0.2"]["open_reason"] = (
        "authoritative_remote_url_absent"
    )
    (clone / "governance/b0-status.yaml").write_text(
        yaml.safe_dump(live_status, sort_keys=False),
        encoding="utf-8",
    )
    provenance_path = clone / "governance/authority-provenance.yaml"
    live_provenance = yaml.safe_load(provenance_path.read_bytes())
    live_provenance["status"] = "provisional"
    live_provenance["authority_state"] = "local-only/provisional"
    for entry in live_provenance["sources"]:
        entry["origin_state"] = "local-only/provisional"
        entry["upstream_url"] = None
    provenance_path.write_text(
        yaml.safe_dump(live_provenance, sort_keys=False),
        encoding="utf-8",
    )
    descendant = _commit_clone(clone, "drift live closure documents")

    assert descendant != evidence_commit
    assert validator.validate_b0_report(report, live_status, clone) == []


def test_schema_2_report_remains_valid_on_a_merge_tip(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    report, status, evidence_commit = _install_schema_2_evidence_revision(
        clone, validator
    )
    subprocess.run(
        ["git", "-C", str(clone), "checkout", "--quiet", "-b", "side"],
        check=True,
        capture_output=True,
    )
    (clone / "side.txt").write_text("side descendant\n", encoding="utf-8")
    _commit_clone(clone, "side descendant")
    subprocess.run(
        ["git", "-C", str(clone), "checkout", "--quiet", "--detach", evidence_commit],
        check=True,
        capture_output=True,
    )
    (clone / "mainline.txt").write_text("mainline descendant\n", encoding="utf-8")
    _commit_clone(clone, "mainline descendant")
    subprocess.run(
        [
            "git",
            "-C",
            str(clone),
            "-c",
            "user.name=policy-test",
            "-c",
            "user.email=policy@test",
            "merge",
            "--quiet",
            "--no-ff",
            "side",
            "-m",
            "merge descendants",
        ],
        check=True,
        capture_output=True,
    )
    merge_tip = subprocess.check_output(
        ["git", "-C", str(clone), "rev-parse", "HEAD"], text=True
    ).strip()

    assert len(
        subprocess.check_output(
            ["git", "-C", str(clone), "rev-list", "--parents", "-n", "1", merge_tip],
            text=True,
        ).split()
    ) == 3
    assert validator.validate_b0_report(report, status, clone) == []


def test_b0_report_r5_identity_ignores_git_replacement_objects(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    report, status, evidence_commit = _install_schema_2_evidence_revision(
        clone, validator
    )
    parent = subprocess.check_output(
        ["git", "-C", str(clone), "rev-parse", f"{evidence_commit}^"],
        text=True,
    ).strip()
    report["evaluated_at"] = "1970-01-01T00:00:00Z"
    _write_report(clone / "governance/b0-report.json", report)
    subprocess.run(
        ["git", "-C", str(clone), "add", "governance/b0-report.json"],
        check=True,
        capture_output=True,
    )
    forged_tree = subprocess.check_output(
        ["git", "-C", str(clone), "write-tree"], text=True
    ).strip()
    forged_commit = subprocess.check_output(
        [
            "git",
            "-C",
            str(clone),
            "-c",
            "user.name=policy-test",
            "-c",
            "user.email=policy@test",
            "commit-tree",
            forged_tree,
            "-p",
            parent,
            "-m",
            "forged replacement evidence",
        ],
        text=True,
    ).strip()
    subprocess.run(
        ["git", "-C", str(clone), "replace", evidence_commit, forged_commit],
        check=True,
        capture_output=True,
    )

    errors = validator.validate_b0_report(report, status, clone)

    assert any("working-tree content" in error for error in errors)


@pytest.mark.parametrize("graft_content", [b"# comment-only graft metadata\n", b"invalid graft metadata\n"])
def test_git_graft_guard_rejects_nonempty_metadata_in_linked_worktrees(
    tmp_path: Path,
    graft_content: bytes,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    linked = tmp_path / "linked-worktree"
    subprocess.run(
        ["git", "-C", str(clone), "worktree", "add", "--quiet", "--detach", str(linked), "HEAD"],
        check=True,
        capture_output=True,
    )
    grafts_path = _git_path(linked, "info/grafts")
    grafts_path.parent.mkdir(parents=True, exist_ok=True)
    grafts_path.write_bytes(graft_content)

    errors = validator._validate_no_git_grafts(linked)

    assert any("active Git graft metadata is forbidden" in error for error in errors)

    grafts_path.write_bytes(b"")
    assert validator._validate_no_git_grafts(linked) == []


def test_repository_validation_rejects_graft_that_masks_schema_and_r5_failures(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    report, _, evidence_commit = _install_schema_2_evidence_revision(clone, validator)
    schema_2_content = _git_show_bytes(
        clone, evidence_commit, "governance/b0-report.json"
    )
    legacy_content = _git_show_bytes(
        clone, LEGACY_REPORT_REVISION, "governance/b0-report.json"
    )
    report_path = clone / "governance/b0-report.json"
    report_path.write_bytes(legacy_content)
    _commit_clone(clone, "attempt schema downgrade")
    report_path.write_bytes(schema_2_content)
    restored = _commit_clone(clone, "restore schema 2 report")

    unmasked_errors = validator.validate_repository(clone)
    assert any("schema downgrade" in error for error in unmasked_errors)
    assert any("direct parent" in error for error in unmasked_errors)

    grafts_path = _git_path(clone, "info/grafts")
    grafts_path.parent.mkdir(parents=True, exist_ok=True)
    grafts_path.write_text(
        f"{restored} {report['repository']['evaluated_commit']}\n",
        encoding="ascii",
    )

    masked_errors = validator.validate_repository(clone)

    assert any(
        "active Git graft metadata is forbidden" in error
        for error in masked_errors
    ), masked_errors


def test_local_probe_parent_symlink_escape_is_rejected(tmp_path: Path) -> None:
    validator = _validator()
    report = _report()
    repository = tmp_path / "repository"
    external = tmp_path / "external-artifacts"
    repository.mkdir()
    artifact = external / "b0/local/numpy/b0-runtime-probe.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("{}\n", encoding="utf-8")
    (repository / ".artifacts").symlink_to(external, target_is_directory=True)

    errors = validator.validate_local_probe_evidence(
        copy.deepcopy(report["local_runtime_probes"]),
        repository,
        report["repository"]["evaluated_commit"],
    )

    assert any("symbolic link" in error or "escapes repository root" in error for error in errors)


def test_cross_review_is_preserved_and_branch_parallel_guide_wins_merge_conflict() -> None:
    validator = _validator()
    assert CROSS_REVIEW_PATH.is_file()
    assert validator.read_frontmatter(CROSS_REVIEW_PATH) == {
        "document_kind": "review",
        "status": "delivered",
        "authoritative": False,
        "subject": "gate_b0_cross_review",
        "reviewed_ref": "agent/b0-bootstrap @ 3ed735b",
        "reviewer": "lane-counterpart (Claude, planning agent)",
        "verdict": "approve_with_required_follow_up",
    }
    review = CROSS_REVIEW_PATH.read_text(encoding="utf-8")
    assert "Approve, with one required follow-up" in review
    task_report = TASK_REPORT_PATH.read_text(encoding="utf-8")
    assert "PARALLEL_WORK_GUIDE.md` add/add conflict" in task_report
    assert "branch version must win" in task_report
    assert "Do not merge or rebase during Task 6" in task_report


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


def test_every_checked_in_evidence_digest_is_recomputed(tmp_path: Path) -> None:
    validator = _validator()
    report = _report()
    evidence_paths = tuple(report["checked_in_evidence"])
    corrupt_digests = dict.fromkeys(evidence_paths, "0" * 64)

    if report["schema_version"] == "1.0.0":
        tampered = copy.deepcopy(report)
        tampered["checked_in_evidence"].update(corrupt_digests)
        errors = validator.validate_b0_report(tampered, _status(), REPO_ROOT)
    else:
        clone = _committed_clone(tmp_path)
        tampered, frozen_status, _ = _install_schema_2_evidence_revision(
            clone,
            validator,
            checked_in_evidence_overrides=corrupt_digests,
        )
        errors = validator.validate_b0_report(tampered, frozen_status, clone)

    for evidence_path in evidence_paths:
        assert any(
            evidence_path in error and "SHA-256" in error
            for error in errors
        ), evidence_path


def _hosted_entries(validator) -> list[dict]:
    return copy.deepcopy(list(validator.B0_REPORT_HOSTED_PROBES))


def _head() -> str:
    return subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def _committed_clone(tmp_path: Path) -> Path:
    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "--quiet", "--no-local", str(REPO_ROOT), str(clone)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(clone), "checkout", "--quiet", _head()],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(clone),
            "remote",
            "set-url",
            "origin",
            "git@github.com:TimoKruth/EvoNN-Research.git",
        ],
        check=True,
        capture_output=True,
    )
    return clone


def _historical_phase0_binding() -> str:
    revisions = [
        revision
        for revision in subprocess.check_output(
            [
                "git",
                "-C",
                str(REPO_ROOT),
                "--no-replace-objects",
                "log",
                "--diff-filter=A",
                "--format=%H",
                "HEAD",
                "--",
                "governance/phase0-interface-freeze.yaml",
            ],
            text=True,
        ).splitlines()
        if revision
    ]
    assert len(revisions) == 1, revisions
    binding = revisions[0]
    assert subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), "rev-parse", f"{binding}^"], text=True
    ).strip() == PHASE0_APRIME
    changed = set(
        subprocess.check_output(
            [
                "git",
                "-C",
                str(REPO_ROOT),
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                binding,
            ],
            text=True,
        ).splitlines()
    )
    assert changed == set(PHASE0_BINDING_PATHS)
    return binding


def _phase0_binding_clone(tmp_path: Path) -> Path:
    binding_source = _historical_phase0_binding()
    clone = tmp_path / "phase0-binding-clone"
    subprocess.run(
        ["git", "clone", "--quiet", "--no-local", str(REPO_ROOT), str(clone)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(clone), "checkout", "--quiet", "--detach", PHASE0_APRIME],
        check=True,
        capture_output=True,
    )
    for relative in PHASE0_BINDING_PATHS:
        entry = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "ls-tree", binding_source, "--", relative],
            text=True,
        ).strip().split()
        assert entry[:2] == [PHASE0_BINDING_MODES[relative], "blob"], (relative, entry)
        destination = clone / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(_git_show_bytes(REPO_ROOT, binding_source, relative))
        destination.chmod(0o755 if PHASE0_BINDING_MODES[relative] == "100755" else 0o644)
    binding = _commit_clone(clone, "synthetic Phase 0 binding")
    parent = subprocess.check_output(
        ["git", "-C", str(clone), "rev-parse", f"{binding}^"],
        text=True,
    ).strip()
    changed = {
        relative
        for relative in subprocess.check_output(
            [
                "git",
                "-C",
                str(clone),
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                binding,
            ],
            text=True,
        ).splitlines()
        if relative
    }
    assert parent == PHASE0_APRIME
    assert changed == set(PHASE0_BINDING_PATHS)
    subprocess.run(
        [
            "git",
            "-C",
            str(clone),
            "remote",
            "set-url",
            "origin",
            "git@github.com:TimoKruth/EvoNN-Research.git",
        ],
        check=True,
        capture_output=True,
    )
    return clone


def _commit_clone(clone: Path, message: str) -> str:
    git = [
        "git",
        "-C",
        str(clone),
        "-c",
        "user.name=policy-test",
        "-c",
        "user.email=policy@test",
    ]
    subprocess.run([*git, "add", "-A"], check=True, capture_output=True)
    return _commit_staged_clone(clone, message)


@pytest.mark.parametrize(
    ("content", "needle"),
    [
        (b'{"schema_version": "1.0.0", "schema_version": "2.0.0"}\n', "duplicate JSON key"),
        (b'{"schema_version": "1.0.0", "value": NaN}\n', "non-standard JSON constant"),
    ],
)
def test_governance_cli_rejects_non_strict_report_json(
    tmp_path: Path,
    content: bytes,
    needle: str,
) -> None:
    clone = _committed_clone(tmp_path)
    shutil.copy2(VALIDATOR_PATH, clone / "scripts/policy/validate_repository_governance.py")
    (clone / "governance/b0-report.json").write_bytes(content)

    result = subprocess.run(
        [sys.executable, str(clone / "scripts/policy/validate_repository_governance.py")],
        cwd=clone,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert needle in result.stdout


def test_governance_cli_reports_pathological_report_nesting_without_traceback(
    tmp_path: Path,
) -> None:
    clone = _committed_clone(tmp_path)
    shutil.copy2(VALIDATOR_PATH, clone / "scripts/policy/validate_repository_governance.py")
    (clone / "governance/b0-report.json").write_bytes(
        ("[" * 10000 + "0" + "]" * 10000).encode()
    )

    result = subprocess.run(
        [sys.executable, str(clone / "scripts/policy/validate_repository_governance.py")],
        cwd=clone,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "cannot load B0 integration report" in result.stdout
    assert "Traceback" not in result.stderr


def test_governance_cli_rejects_parser_accepted_deep_frozen_report_without_traceback(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    report, _, _ = _install_schema_2_evidence_revision(clone, validator)
    nested_digest: object = "not-a-digest"
    for _ in range(900):
        nested_digest = [nested_digest]
    first_path = next(iter(report["checked_in_evidence"]))
    report["checked_in_evidence"][first_path] = nested_digest
    _write_report(clone / "governance/b0-report.json", report)
    _commit_clone(clone, "install deeply nested frozen report value")
    shutil.copy2(
        VALIDATOR_PATH,
        clone / "scripts/policy/validate_repository_governance.py",
    )

    result = subprocess.run(
        [sys.executable, str(clone / "scripts/policy/validate_repository_governance.py")],
        cwd=clone,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "must record a SHA-256 digest" in result.stdout
    assert "Traceback" not in result.stderr


def test_exact_json_comparison_handles_cyclic_caller_containers() -> None:
    validator = _validator()
    actual: list[object] = []
    expected: list[object] = []
    actual.append(actual)
    expected.append(expected)

    assert validator._exact_json_value(actual, expected)
    assert not validator._exact_json_value(actual, [[]])


def _commit_staged_clone(clone: Path, message: str) -> str:
    git = [
        "git",
        "-C",
        str(clone),
        "-c",
        "user.name=policy-test",
        "-c",
        "user.email=policy@test",
    ]
    subprocess.run(
        [*git, "commit", "--quiet", "-m", message],
        check=True,
        capture_output=True,
    )
    return subprocess.check_output(
        ["git", "-C", str(clone), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def _git_show_bytes(repository: Path, revision: str, relative: str) -> bytes:
    return subprocess.check_output(
        ["git", "-C", str(repository), "show", f"{revision}:{relative}"]
    )


def _git_path(repository: Path, relative: str) -> Path:
    raw_path = subprocess.check_output(
        ["git", "-C", str(repository), "rev-parse", "--git-path", relative],
        text=True,
    ).strip()
    path = Path(raw_path)
    return path if path.is_absolute() else repository / path


def _write_report(path: Path, report: dict) -> bytes:
    content = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    path.write_bytes(content)
    return content


def _install_three_file_implementation_parent(
    clone: Path,
    task_report_content: bytes,
) -> tuple[str, str, bytes]:
    current_head = subprocess.check_output(
        ["git", "-C", str(clone), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    (clone / "implementation-marker.txt").write_text(
        f"schema transition implementation parent for {current_head}\n",
        encoding="utf-8",
    )
    status_path = clone / "governance/b0-status.yaml"
    interim_status = yaml.safe_load(status_path.read_bytes())
    interim_status["checked_in_at"] = "1970-01-01T00:00:00Z"
    status_path.write_text(
        yaml.safe_dump(interim_status, sort_keys=False),
        encoding="utf-8",
    )
    parent = _commit_clone(clone, "prepare schema transition implementation parent")
    parent_tree = subprocess.check_output(
        ["git", "-C", str(clone), "rev-parse", f"{parent}^{{tree}}"],
        text=True,
    ).strip()
    return parent, parent_tree, task_report_content


def _checked_in_evidence_digests(
    clone: Path,
    validator,
    report: dict,
    parent: str,
    child_bytes: dict[str, bytes],
) -> dict[str, str]:
    local_artifact_paths = {
        probe["artifact_path"] for probe in validator.B0_REPORT_LOCAL_PROBES.values()
    }
    referenced_paths = {
        path
        for item in report["items"].values()
        for path in item["evidence_paths"]
        if path not in {"governance/b0-report.json", *local_artifact_paths}
    }
    referenced_paths.update(workflow["path"] for workflow in report["workflows"])
    referenced_paths.update(
        {"CONSOLIDATED_PLAN.md", "PARALLEL_WORK_GUIDE.md", "governance/b0-status.yaml"}
    )
    return {
        relative: hashlib.sha256(
            child_bytes[relative]
            if relative in child_bytes
            else _git_show_bytes(clone, parent, relative)
        ).hexdigest()
        for relative in sorted(referenced_paths)
    }


def _install_schema_2_evidence_revision(
    clone: Path,
    validator,
    *,
    frozen_status_content: bytes | None = None,
    frozen_provenance_content: bytes | None = None,
    extra_evidence_path: str | None = None,
    checked_in_evidence_overrides: dict[str, str] | None = None,
) -> tuple[dict, dict, str]:
    report_path = clone / "governance/b0-report.json"
    status_path = clone / "governance/b0-status.yaml"
    task_report_path = clone / ".superpowers/sdd/task-6-report.md"
    closure_review_path = clone / "reviews/2026-07-19-b0-closure-review.md"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    status = yaml.safe_load(status_path.read_text(encoding="utf-8"))
    task_report_content = task_report_path.read_bytes()
    if frozen_provenance_content is not None:
        (clone / "governance/authority-provenance.yaml").write_bytes(
            frozen_provenance_content
        )
    if not closure_review_path.exists():
        closure_review_path.write_text(
            "# Gate B0 Closure Review\n\nFixture closure review evidence.\n",
            encoding="utf-8",
        )
    parent, parent_tree, original_task_report = _install_three_file_implementation_parent(
        clone,
        task_report_content,
    )

    report["schema_version"] = "2.0.0"
    report["repository"]["branch"] = "b0/close-gate"
    report["repository"]["evaluated_commit"] = parent
    report["repository"]["evaluated_tree"] = parent_tree
    report["overall_state"] = "closed"
    report["blockers"] = {}
    report["parallel_handoff_ready"] = True
    report["parallel_handoff_blockers"] = []
    report["next_transition"] = validator.B0_REPORT_CLOSED_NEXT_TRANSITION
    report["hosted_runtime_probes"] = copy.deepcopy(
        list(validator.B0_REPORT_HOSTED_PROBES)
    )
    for item in report["items"].values():
        item["state"] = "closed"
        item["reason"] = None
    report["items"]["B0.2"]["evidence_paths"] = sorted(
        {*report["items"]["B0.2"]["evidence_paths"], *SCHEMA_2_B02_REQUIRED_EVIDENCE}
    )
    report["items"]["B0.5"]["evidence_paths"] = sorted(
        {*report["items"]["B0.5"]["evidence_paths"], *SCHEMA_2_B05_REQUIRED_EVIDENCE}
    )
    report["items"]["B0.6"]["evidence_paths"] = sorted(
        {*report["items"]["B0.6"]["evidence_paths"], *SCHEMA_2_B06_REQUIRED_EVIDENCE}
    )

    status["status"] = "closed"
    for item in status["items"].values():
        item["status"] = "closed"
        item["open_reason"] = None
    status_content = frozen_status_content or yaml.safe_dump(
        status, sort_keys=False
    ).encode()
    final_task_report = original_task_report + b"\nSchema 2 closure evidence.\n"
    report["checked_in_evidence"] = _checked_in_evidence_digests(
        clone,
        validator,
        report,
        parent,
        {
            "governance/b0-status.yaml": status_content,
            ".superpowers/sdd/task-6-report.md": final_task_report,
        },
    )
    if checked_in_evidence_overrides is not None:
        report["checked_in_evidence"].update(checked_in_evidence_overrides)
    _write_report(report_path, report)
    status_path.write_bytes(status_content)
    task_report_path.write_bytes(final_task_report)
    if extra_evidence_path is not None:
        extra_path = clone / extra_evidence_path
        extra_path.parent.mkdir(parents=True, exist_ok=True)
        extra_path.write_text("unrelated evidence revision change\n", encoding="utf-8")
    evidence_commit = _commit_clone(clone, "install schema 2 closure evidence")
    changed = subprocess.check_output(
        ["git", "-C", str(clone), "diff", "--name-only", f"{parent}..{evidence_commit}"],
        text=True,
    ).splitlines()
    expected_paths = set(validator.B0_EVIDENCE_ONLY_PATHS)
    if extra_evidence_path is not None:
        expected_paths.add(extra_evidence_path)
    assert set(changed) == expected_paths
    return report, status, evidence_commit


def _replace_evidence_report_with_symlink_mode(
    clone: Path,
    evidence_commit: str,
) -> str:
    report_path = "governance/b0-report.json"
    report_content = _git_show_bytes(clone, evidence_commit, report_path)
    report_blob = subprocess.run(
        ["git", "-C", str(clone), "hash-object", "-w", "--stdin"],
        input=report_content,
        check=True,
        capture_output=True,
    ).stdout.decode().strip()
    subprocess.run(
        [
            "git",
            "-C",
            str(clone),
            "update-index",
            "--add",
            "--cacheinfo",
            f"120000,{report_blob},{report_path}",
        ],
        check=True,
        capture_output=True,
    )
    tree = subprocess.check_output(
        ["git", "-C", str(clone), "write-tree"], text=True
    ).strip()
    parent = subprocess.check_output(
        ["git", "-C", str(clone), "rev-parse", f"{evidence_commit}^"],
        text=True,
    ).strip()
    replacement = subprocess.check_output(
        [
            "git",
            "-C",
            str(clone),
            "-c",
            "user.name=policy-test",
            "-c",
            "user.email=policy@test",
            "commit-tree",
            tree,
            "-p",
            parent,
            "-m",
            "install symlink-mode schema 2 evidence",
        ],
        text=True,
    ).strip()
    subprocess.run(
        ["git", "-C", str(clone), "update-ref", "HEAD", replacement],
        check=True,
        capture_output=True,
    )
    worktree_report = clone / report_path
    worktree_report.unlink()
    worktree_report.write_bytes(report_content)
    return replacement


def _install_fresh_schema_1_side_parent(clone: Path) -> str:
    subprocess.run(
        [
            "git",
            "-C",
            str(clone),
            "checkout",
            "--quiet",
            "-b",
            "fresh-schema-1-side",
            LEGACY_REPORT_REVISION,
        ],
        check=True,
        capture_output=True,
    )
    report_path = clone / "governance/b0-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["evaluated_at"] = "1970-01-01T00:00:00Z"
    _write_report(report_path, report)
    return _commit_clone(clone, "record fresh schema 1 side-parent revision")


def _merge_ours(clone: Path, revision: str, message: str) -> str:
    subprocess.run(
        [
            "git",
            "-C",
            str(clone),
            "-c",
            "user.name=policy-test",
            "-c",
            "user.email=policy@test",
            "merge",
            "--quiet",
            "--no-ff",
            "-s",
            "ours",
            revision,
            "-m",
            message,
        ],
        check=True,
        capture_output=True,
    )
    return subprocess.check_output(
        ["git", "-C", str(clone), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def _copy_historical_legacy_transition_merge(clone: Path) -> str:
    revision = subprocess.check_output(
        [
            "git",
            "-C",
            str(clone),
            "--no-replace-objects",
            "rev-list",
            "--parents",
            "-n",
            "1",
            LEGACY_TRANSITION_MERGE,
        ],
        text=True,
    ).split()
    tree = subprocess.check_output(
        [
            "git",
            "-C",
            str(clone),
            "--no-replace-objects",
            "rev-parse",
            f"{LEGACY_TRANSITION_MERGE}^{{tree}}",
        ],
        text=True,
    ).strip()
    message = subprocess.check_output(
        [
            "git",
            "-C",
            str(clone),
            "--no-replace-objects",
            "show",
            "-s",
            "--format=%B",
            LEGACY_TRANSITION_MERGE,
        ],
        text=True,
    )
    copied = subprocess.run(
        [
            "git",
            "-C",
            str(clone),
            "-c",
            "user.name=policy-test",
            "-c",
            "user.email=policy@test",
            "commit-tree",
            tree,
            "-p",
            revision[1],
            "-p",
            revision[2],
            "-F",
            "-",
        ],
        input=message,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert copied != LEGACY_TRANSITION_MERGE
    assert subprocess.check_output(
        ["git", "-C", str(clone), "rev-parse", f"{copied}^{{tree}}"],
        text=True,
    ).strip() == tree
    assert subprocess.check_output(
        ["git", "-C", str(clone), "rev-list", "--parents", "-n", "1", copied],
        text=True,
    ).split()[1:] == revision[1:]
    assert subprocess.check_output(
        ["git", "-C", str(clone), "show", "-s", "--format=%B", copied],
        text=True,
    ).rstrip("\n") == message.rstrip("\n")
    return copied


def _commit_report_merge(
    clone: Path,
    *,
    first_parent: str,
    second_parent: str,
    report_revision: str,
    message: str,
) -> str:
    assert subprocess.check_output(
        ["git", "-C", str(clone), "rev-parse", "HEAD"],
        text=True,
    ).strip() == first_parent
    subprocess.run(
        [
            "git",
            "-C",
            str(clone),
            "checkout",
            "--quiet",
            report_revision,
            "--",
            "governance/b0-report.json",
        ],
        check=True,
        capture_output=True,
    )
    tree = subprocess.check_output(
        ["git", "-C", str(clone), "write-tree"], text=True
    ).strip()
    merge = subprocess.check_output(
        [
            "git",
            "-C",
            str(clone),
            "-c",
            "user.name=policy-test",
            "-c",
            "user.email=policy@test",
            "commit-tree",
            tree,
            "-p",
            first_parent,
            "-p",
            second_parent,
            "-m",
            message,
        ],
        text=True,
    ).strip()
    subprocess.run(
        ["git", "-C", str(clone), "update-ref", "HEAD", merge, first_parent],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(clone), "reset", "--quiet", "--hard", merge],
        check=True,
        capture_output=True,
    )
    return merge


def _install_fresh_schema_1_evidence_revision(clone: Path, validator) -> tuple[dict, dict, str]:
    report_path = clone / "governance/b0-report.json"
    status_path = clone / "governance/b0-status.yaml"
    task_report_path = clone / ".superpowers/sdd/task-6-report.md"
    report = json.loads(
        _git_show_bytes(clone, LEGACY_REPORT_REVISION, "governance/b0-report.json")
    )
    status = yaml.safe_load(
        _git_show_bytes(clone, LEGACY_REPORT_REVISION, "governance/b0-status.yaml")
    )
    task_report_content = _git_show_bytes(
        clone, LEGACY_REPORT_REVISION, ".superpowers/sdd/task-6-report.md"
    )
    parent, parent_tree, original_task_report = _install_three_file_implementation_parent(
        clone,
        task_report_content,
    )
    report["repository"]["evaluated_commit"] = parent
    report["repository"]["evaluated_tree"] = parent_tree
    status_content = yaml.safe_dump(status, sort_keys=False).encode()
    final_task_report = original_task_report + b"\nFresh schema 1 transition evidence.\n"
    report["checked_in_evidence"] = _checked_in_evidence_digests(
        clone,
        validator,
        report,
        parent,
        {
            "governance/b0-status.yaml": status_content,
            ".superpowers/sdd/task-6-report.md": final_task_report,
        },
    )
    _write_report(report_path, report)
    status_path.write_bytes(status_content)
    task_report_path.write_bytes(final_task_report)
    evidence_commit = _commit_clone(clone, "regenerate schema 1 transition evidence")
    return report, status, evidence_commit


def test_schema_2_public_validation_uses_frozen_evidence_commit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    report, status, evidence_commit = _install_schema_2_evidence_revision(clone, validator)
    hosted_path = report["hosted_runtime_probes"][0]["artifact_path"]
    frozen_hosted_bytes = _git_show_bytes(clone, evidence_commit, hosted_path)
    (clone / hosted_path).write_text(
        '{"descendant": "hosted bytes differ from frozen evidence"}\n',
        encoding="utf-8",
    )
    descendant = _commit_clone(clone, "descendant after frozen evidence")
    assert descendant != evidence_commit
    assert (clone / hosted_path).read_bytes() != frozen_hosted_bytes
    original = validator.validate_hosted_probe_evidence
    calls = []

    def record_call(entries, repo_root, frozen_commit):
        calls.append((entries, repo_root, frozen_commit))
        return original(entries, repo_root, frozen_commit)

    monkeypatch.setattr(validator, "validate_hosted_probe_evidence", record_call)

    assert validator.validate_b0_report(report, status, clone) == []
    assert calls == [(report["hosted_runtime_probes"], clone, evidence_commit)]


def test_schema_2_closure_uses_frozen_status_not_a_closed_descendant(
    tmp_path: Path,
    monkeypatch,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    frozen_open_status = copy.deepcopy(_status())
    frozen_open_status["status"] = "open"
    for item in frozen_open_status["items"].values():
        item["status"] = "closed"
        item["open_reason"] = None
    frozen_open_status["items"]["B0.2"]["status"] = "open"
    frozen_open_status["items"]["B0.2"]["open_reason"] = (
        "authoritative_remote_url_absent"
    )
    frozen_open_status_content = yaml.safe_dump(
        frozen_open_status,
        sort_keys=False,
    ).encode()
    report, closed_status, evidence_commit = _install_schema_2_evidence_revision(
        clone,
        validator,
        frozen_status_content=frozen_open_status_content,
    )
    live_status_content = yaml.safe_dump(closed_status, sort_keys=False).encode()
    (clone / "governance/b0-status.yaml").write_bytes(live_status_content)
    descendant = _commit_clone(clone, "close status after frozen evidence")
    original_loader = validator._committed_yaml_mapping
    loaded_statuses = []

    def record_status_load(repo_root, revision, relative, label):
        result = original_loader(repo_root, revision, relative, label)
        if relative == "governance/b0-status.yaml":
            loaded_statuses.append((repo_root, revision, result))
        return result

    monkeypatch.setattr(validator, "_committed_yaml_mapping", record_status_load)

    assert descendant != evidence_commit
    assert _git_show_bytes(
        clone, evidence_commit, "governance/b0-status.yaml"
    ) == frozen_open_status_content
    assert (clone / "governance/b0-status.yaml").read_bytes() == live_status_content
    assert live_status_content != frozen_open_status_content

    errors = validator.validate_b0_report(report, closed_status, clone)

    assert loaded_statuses == [
        (clone, evidence_commit, (frozen_open_status, None))
    ]
    assert set(errors) == {
        "governance/b0-status.yaml top-level status must be closed for schema 2.0.0",
        "governance/b0-status.yaml B0.2 status must be closed for schema 2.0.0",
        "governance/b0-status.yaml B0.2 closed open_reason must be null",
        "B0 report B0.2 state does not match governance/b0-status.yaml",
        "remote-pinned authority must close B0.2 and clear its open reason",
    }


def test_schema_2_closure_uses_frozen_authority_not_a_pinned_descendant(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    provenance_path = clone / "governance/authority-provenance.yaml"
    remote_provenance = provenance_path.read_bytes()
    local_provenance = yaml.safe_load(remote_provenance)
    local_provenance["status"] = "provisional"
    local_provenance["authority_state"] = "local-only/provisional"
    for entry in local_provenance["sources"]:
        entry["origin_state"] = "local-only/provisional"
        entry["upstream_url"] = None
    provenance_path.write_text(
        yaml.safe_dump(local_provenance, sort_keys=False),
        encoding="utf-8",
    )
    report, status, evidence_commit = _install_schema_2_evidence_revision(
        clone, validator
    )
    provenance_path.write_bytes(remote_provenance)
    descendant = _commit_clone(clone, "pin authority after frozen evidence")

    assert descendant != evidence_commit
    errors = validator.validate_b0_report(report, status, clone)

    assert any("frozen B0 authority" in error or "local-only authority" in error for error in errors)


def test_schema_2_closure_rejects_frozen_authority_immutable_metadata_drift(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    provenance_path = clone / "governance/authority-provenance.yaml"
    provenance = yaml.safe_load(provenance_path.read_bytes())
    source = provenance["sources"][0]
    source["normative_role"] = "Forged but non-empty normative role"
    source["imported_at"] = "2026-07-18T14:49:43Z"
    frozen_provenance_content = yaml.safe_dump(
        provenance, sort_keys=False
    ).encode()
    report, status, evidence_commit = _install_schema_2_evidence_revision(
        clone,
        validator,
        frozen_provenance_content=frozen_provenance_content,
    )

    assert _git_show_bytes(
        clone, evidence_commit, "governance/authority-provenance.yaml"
    ) == frozen_provenance_content
    errors = validator.validate_b0_report(report, status, clone)

    assert any("claude-spec" in error and "normative_role" in error for error in errors)
    assert any("claude-spec" in error and "imported_at" in error for error in errors)


@pytest.mark.parametrize(
    ("source_id", "integer_alias"),
    [("claude-spec", 0), ("product-research-interop", 1)],
)
def test_schema_2_closure_rejects_frozen_authority_boolean_integer_aliases(
    tmp_path: Path,
    source_id: str,
    integer_alias: int,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    provenance_path = clone / "governance/authority-provenance.yaml"
    provenance = yaml.safe_load(provenance_path.read_bytes())
    source = next(entry for entry in provenance["sources"] if entry["id"] == source_id)
    source["consumer_acceptance_authority"] = integer_alias
    frozen_provenance_content = yaml.safe_dump(
        provenance, sort_keys=False
    ).encode()
    report, status, _ = _install_schema_2_evidence_revision(
        clone,
        validator,
        frozen_provenance_content=frozen_provenance_content,
    )

    errors = validator.validate_b0_report(report, status, clone)

    assert any(
        source_id in error and "consumer_acceptance_authority" in error
        for error in errors
    )


@pytest.mark.parametrize("content_digest", [None, [], "sha256:forged"])
def test_schema_2_closure_rejects_malformed_frozen_authority_content_digest(
    tmp_path: Path,
    content_digest,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    provenance_path = clone / "governance/authority-provenance.yaml"
    provenance = yaml.safe_load(provenance_path.read_bytes())
    provenance["sources"][0]["content_digest"] = content_digest
    frozen_provenance_content = yaml.safe_dump(
        provenance, sort_keys=False
    ).encode()
    report, status, evidence_commit = _install_schema_2_evidence_revision(
        clone,
        validator,
        frozen_provenance_content=frozen_provenance_content,
    )

    assert _git_show_bytes(
        clone, evidence_commit, "governance/authority-provenance.yaml"
    ) == frozen_provenance_content
    errors = validator.validate_b0_report(report, status, clone)

    assert any(
        "claude-spec" in error and "SHA-256 digest" in error for error in errors
    )


def test_schema_2_closure_rejects_duplicate_keys_in_frozen_status_yaml(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    closed_status = copy.deepcopy(_status())
    closed_status["status"] = "closed"
    for item in closed_status["items"].values():
        item["status"] = "closed"
        item["open_reason"] = None
    frozen_status_content = (
        yaml.safe_dump(closed_status, sort_keys=False).encode()
        + b"status: open\n"
    )
    report, status, evidence_commit = _install_schema_2_evidence_revision(
        clone,
        validator,
        frozen_status_content=frozen_status_content,
    )
    (clone / "governance/b0-status.yaml").write_text(
        yaml.safe_dump(status, sort_keys=False),
        encoding="utf-8",
    )
    descendant = _commit_clone(clone, "replace malformed frozen status")

    assert descendant != evidence_commit
    errors = validator.validate_b0_report(report, status, clone)

    assert any("frozen B0 status" in error and "duplicate YAML key" in error for error in errors)


def test_schema_2_mapping_must_match_the_frozen_evidence_report(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    report, status, _ = _install_schema_2_evidence_revision(clone, validator)
    report["evaluated_at"] = "1970-01-01T00:00:00Z"

    errors = validator.validate_b0_report(report, status, clone)

    assert any("mapping" in error and "frozen evidence" in error for error in errors)


def test_schema_2_fixture_builds_an_exact_three_file_child_from_closed_base(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    closed_report, closed_status, _ = _install_schema_2_evidence_revision(
        clone, validator
    )
    assert validator.validate_b0_report(closed_report, closed_status, clone) == []

    report, status, evidence_commit = _install_schema_2_evidence_revision(
        clone, validator
    )
    parent = subprocess.check_output(
        ["git", "-C", str(clone), "rev-parse", f"{evidence_commit}^"], text=True
    ).strip()
    changed = subprocess.check_output(
        ["git", "-C", str(clone), "diff", "--name-only", f"{parent}..{evidence_commit}"],
        text=True,
    ).splitlines()
    parent_report = json.loads(
        _git_show_bytes(clone, parent, "governance/b0-report.json")
    )

    assert parent_report["schema_version"] == "2.0.0"
    assert set(changed) == set(validator.B0_EVIDENCE_ONLY_PATHS)
    assert validator.validate_b0_report(report, status, clone) == []


def test_schema_2_rejects_missing_or_extra_top_level_fields() -> None:
    validator = _validator()
    report, status = _schema_2_state_documents(validator)

    missing = copy.deepcopy(report)
    del missing["hosted_runtime_probes"]
    missing_errors = validator.validate_b0_schema_2_state(missing, status)
    assert any("missing required fields" in error for error in missing_errors)

    unknown = copy.deepcopy(report)
    unknown["unexpected"] = True
    unknown_errors = validator.validate_b0_schema_2_state(unknown, status)
    assert any("unknown fields" in error for error in unknown_errors)


def test_schema_2_rejects_explicit_null_hosted_runtime_probes() -> None:
    validator = _validator()
    report, status = _schema_2_state_documents(validator)
    report["hosted_runtime_probes"] = None

    errors = validator.validate_b0_schema_2_state(report, status)

    assert any("hosted_runtime_probes" in error for error in errors)


def test_schema_2_rejects_missing_or_extra_hosted_entry_fields() -> None:
    validator = _validator()
    report, status = _schema_2_state_documents(validator)

    missing = copy.deepcopy(report)
    del missing["hosted_runtime_probes"][0]["run_attempt"]
    missing_errors = validator.validate_b0_schema_2_state(missing, status)
    assert any("missing required fields" in error for error in missing_errors)

    unknown = copy.deepcopy(report)
    unknown["hosted_runtime_probes"][0]["unexpected"] = True
    unknown_errors = validator.validate_b0_schema_2_state(unknown, status)
    assert any("unknown fields" in error for error in unknown_errors)


def test_schema_2_public_validation_rejects_status_identity_drift() -> None:
    validator = _validator()
    report, status = _schema_2_state_documents(validator)
    status["document_kind"] = "report"
    status["gate"] = "B1"

    errors = validator.validate_b0_schema_2_state(report, status)

    assert any("document_kind" in error for error in errors)
    assert any("gate" in error for error in errors)


def test_schema_2_public_validation_rejects_non_mapping_status() -> None:
    validator = _validator()
    report, _ = _schema_2_state_documents(validator)

    errors = validator.validate_b0_schema_2_state(report, [])

    assert any("status" in error and "mapping" in error for error in errors)


def test_schema_2_requires_the_closure_branch() -> None:
    validator = _validator()
    report, status = _schema_2_state_documents(validator)
    report["repository"]["branch"] = "wrong-branch"

    errors = validator.validate_b0_schema_2_state(report, status)

    assert any("repository.branch" in error and "b0/close-gate" in error for error in errors)


@pytest.mark.parametrize("item_id", ["B0.1", "B0.3", "B0.4"])
def test_schema_2_restricts_report_self_reference_to_permitted_items(
    item_id: str,
) -> None:
    validator = _validator()
    report, status = _schema_2_state_documents(validator)
    report["items"][item_id]["evidence_paths"].append(
        "governance/b0-report.json"
    )

    errors = validator.validate_b0_schema_2_state(report, status)

    assert any(item_id in error and "self-reference" in error for error in errors)


def test_schema_2_permits_b06_report_attribution_with_canonical_evidence() -> None:
    validator = _validator()
    report, status = _schema_2_state_documents(validator)

    errors = validator.validate_b0_schema_2_state(report, status)

    assert not any("B0.6" in error for error in errors)


def test_schema_1_rejects_report_self_reference(tmp_path: Path) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    report = json.loads(
        _git_show_bytes(clone, LEGACY_REPORT_REVISION, "governance/b0-report.json")
    )
    status = yaml.safe_load(
        _git_show_bytes(clone, LEGACY_REPORT_REVISION, "governance/b0-status.yaml")
    )
    report["items"]["B0.2"]["evidence_paths"].append(
        "governance/b0-report.json"
    )

    errors = validator.validate_b0_report(report, status, clone)

    assert any("schema 1.0.0" in error and "self-reference" in error for error in errors)


def test_schema_1_dispatch_skips_hosted_probe_validation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    report = json.loads(
        _git_show_bytes(clone, LEGACY_REPORT_REVISION, "governance/b0-report.json")
    )
    status = yaml.safe_load(
        _git_show_bytes(clone, LEGACY_REPORT_REVISION, "governance/b0-status.yaml")
    )
    calls = []
    monkeypatch.setattr(
        validator,
        "validate_hosted_probe_evidence",
        lambda *args: calls.append(args) or ["must not be called"],
    )

    validator.validate_b0_report(report, status, clone)

    assert calls == []


@pytest.mark.parametrize(
    ("item_id", "required_path"),
    [
        *[("B0.2", path) for path in sorted(SCHEMA_2_B02_REQUIRED_EVIDENCE)],
        *[("B0.5", path) for path in sorted(SCHEMA_2_B05_REQUIRED_EVIDENCE)],
        *[("B0.6", path) for path in sorted(SCHEMA_2_B06_REQUIRED_EVIDENCE)],
    ],
)
def test_schema_2_names_each_missing_required_item_evidence_path(
    item_id: str,
    required_path: str,
) -> None:
    validator = _validator()
    report, status = _schema_2_state_documents(validator)
    report["items"][item_id]["evidence_paths"].remove(required_path)

    errors = validator.validate_b0_schema_2_state(report, status)

    assert any(
        item_id in error and "required evidence" in error and required_path in error
        for error in errors
    )


@pytest.mark.parametrize("item_id", ["B0.2", "B0.5", "B0.6"])
def test_schema_2_report_self_reference_cannot_replace_canonical_item_evidence(
    item_id: str,
) -> None:
    validator = _validator()
    report, status = _schema_2_state_documents(validator)
    report["items"][item_id]["evidence_paths"] = ["governance/b0-report.json"]

    errors = validator.validate_b0_schema_2_state(report, status)

    assert any(item_id in error and "required evidence" in error for error in errors)


@pytest.mark.parametrize(
    "hosted_path",
    [
        "governance/evidence/b0/hosted/linux-runtime-probe.json",
        "governance/evidence/b0/hosted/macos-runtime-probe.json",
    ],
)
def test_schema_2_requires_hosted_artifacts_to_be_attributed_to_b05(
    hosted_path: str,
) -> None:
    validator = _validator()
    report, status = _schema_2_state_documents(validator)
    report["items"]["B0.5"]["evidence_paths"].remove(hosted_path)

    errors = validator.validate_b0_schema_2_state(report, status)

    assert any("B0.5" in error and hosted_path in error for error in errors)


def test_schema_1_mapping_must_match_the_frozen_transition_record() -> None:
    validator = _validator()
    report = json.loads(
        _git_show_bytes(REPO_ROOT, LEGACY_REPORT_REVISION, "governance/b0-report.json")
    )
    status = yaml.safe_load(
        _git_show_bytes(REPO_ROOT, LEGACY_REPORT_REVISION, "governance/b0-status.yaml")
    )
    report["evaluated_at"] = "1970-01-01T00:00:00Z"

    errors = validator.validate_b0_report(report, status, REPO_ROOT)

    assert any("exact frozen transition record" in error for error in errors)


def test_schema_1_is_limited_to_the_frozen_transition_revision(tmp_path: Path) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    report, status, _ = _install_fresh_schema_1_evidence_revision(clone, validator)

    errors = validator.validate_b0_report(report, status, clone)

    assert any(LEGACY_REPORT_REVISION in error for error in errors)
    assert not any(
        needle in error
        for error in errors
        for needle in (
            "must be the direct parent",
            "evidence-only commit diff",
            "working-tree content",
            "checked-in evidence SHA-256",
        )
    )


def test_schema_2_cannot_downgrade_to_legacy_after_a_closed_evidence_revision(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    _install_schema_2_evidence_revision(clone, validator)
    legacy_content = _git_show_bytes(
        clone, LEGACY_REPORT_REVISION, "governance/b0-report.json"
    )
    (clone / "governance/b0-report.json").write_bytes(legacy_content)
    _commit_clone(clone, "attempt schema downgrade")
    report = json.loads(legacy_content)
    status = yaml.safe_load(
        _git_show_bytes(clone, LEGACY_REPORT_REVISION, "governance/b0-status.yaml")
    )

    errors = validator.validate_b0_report(report, status, clone)

    assert any("schema downgrade" in error for error in errors)


def test_schema_2_history_rejects_a_restored_schema_2_tip_after_downgrade(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    _, _, evidence_commit = _install_schema_2_evidence_revision(clone, validator)
    schema_2_content = _git_show_bytes(
        clone, evidence_commit, "governance/b0-report.json"
    )
    legacy_content = _git_show_bytes(
        clone, LEGACY_REPORT_REVISION, "governance/b0-report.json"
    )
    report_path = clone / "governance/b0-report.json"
    report_path.write_bytes(legacy_content)
    _commit_clone(clone, "attempt schema downgrade")
    report_path.write_bytes(schema_2_content)
    _commit_clone(clone, "restore schema 2 report")
    report = json.loads(schema_2_content)
    status = yaml.safe_load(
        (clone / "governance/b0-status.yaml").read_text(encoding="utf-8")
    )

    errors = validator.validate_b0_report(report, status, clone)

    assert any("schema downgrade" in error for error in errors)


def test_schema_history_accepts_the_exact_historical_legacy_transition_merge() -> None:
    validator = _validator()
    assert validator.B0_REPORT_LEGACY_TRANSITION_MERGE == LEGACY_TRANSITION_MERGE
    parents = subprocess.check_output(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "--no-replace-objects",
            "rev-list",
            "--parents",
            "-n",
            "1",
            LEGACY_TRANSITION_MERGE,
        ],
        text=True,
    ).split()

    assert parents[1:] == [
        "f084f3ccb830d8049a7275d8ed66b1f7e7673b53",
        LEGACY_REPORT_REVISION,
    ]
    assert subprocess.check_output(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "--no-replace-objects",
            "rev-parse",
            f"{LEGACY_TRANSITION_MERGE}^{{tree}}",
        ],
        text=True,
    ).strip() == subprocess.check_output(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "--no-replace-objects",
            "rev-parse",
            f"{LEGACY_REPORT_REVISION}^{{tree}}",
        ],
        text=True,
    ).strip()
    assert validator._validate_b0_schema_history(
        REPO_ROOT,
        validator.B0_REPORT_SCHEMA_VERSION,
    ) == []


def test_schema_history_rejects_a_fresh_copy_of_the_legacy_transition_merge(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    copied_transition = _copy_historical_legacy_transition_merge(clone)
    subprocess.run(
        ["git", "-C", str(clone), "checkout", "--quiet", "--detach", _head()],
        check=True,
        capture_output=True,
    )
    report, status, _ = _install_schema_2_evidence_revision(clone, validator)
    _merge_ours(clone, copied_transition, "merge copied legacy transition history")

    report_errors = validator.validate_b0_report(report, status, clone)
    repository_errors = validator.validate_repository(clone)

    assert any(
        "schema 1.0.0 is permitted only" in error and copied_transition in error
        for error in report_errors
    ), report_errors
    assert any(
        "schema 1.0.0 is permitted only" in error and copied_transition in error
        for error in repository_errors
    ), repository_errors


def test_schema_history_rejects_merge_downgrade_from_nonfirst_parent_report(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    _, _, schema_2_tip = _install_schema_2_evidence_revision(clone, validator)
    downgrade_merge = _commit_report_merge(
        clone,
        first_parent=schema_2_tip,
        second_parent=LEGACY_REPORT_REVISION,
        report_revision=LEGACY_REPORT_REVISION,
        message="merge pinned legacy report as a downgrade",
    )
    assert _git_show_bytes(
        clone, downgrade_merge, "governance/b0-report.json"
    ) != _git_show_bytes(clone, schema_2_tip, "governance/b0-report.json")
    assert _git_show_bytes(
        clone, downgrade_merge, "governance/b0-report.json"
    ) == _git_show_bytes(clone, LEGACY_REPORT_REVISION, "governance/b0-report.json")

    report, status, _ = _install_schema_2_evidence_revision(clone, validator)

    report_errors = validator.validate_b0_report(report, status, clone)
    repository_errors = validator.validate_repository(clone)

    assert any("schema downgrade" in error for error in report_errors), report_errors
    assert any("schema downgrade" in error for error in repository_errors), repository_errors


def test_historical_phase0_binding_fixture_survives_aprime_repairable_bytes(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _phase0_binding_clone(tmp_path)
    relative = "tests/policy/test_repository_governance.py"
    (clone / relative).write_bytes(_git_show_bytes(clone, PHASE0_APRIME, relative))
    _commit_clone(clone, "restore repairable Phase 0 path to A-prime bytes")

    assert validator._validate_phase0_interface_freeze(clone) == []


def test_b0_schema_history_allows_carrier_and_reattestation_while_aggregate_rejects_historical_evidence_mutation(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _phase0_binding_clone(tmp_path)
    report, status, schema_2_tip = _install_schema_2_evidence_revision(clone, validator)
    carrier_merge = _commit_report_merge(
        clone,
        first_parent=schema_2_tip,
        second_parent=LEGACY_REPORT_REVISION,
        report_revision=schema_2_tip,
        message="carry first-parent schema 2 report through merge",
    )
    assert _git_show_bytes(
        clone, carrier_merge, "governance/b0-report.json"
    ) == _git_show_bytes(clone, schema_2_tip, "governance/b0-report.json")
    assert _git_show_bytes(
        clone, carrier_merge, "governance/b0-report.json"
    ) != _git_show_bytes(clone, LEGACY_REPORT_REVISION, "governance/b0-report.json")
    expected_aggregate_errors = {
        "Phase 0 interface freeze validator: historical B0 evidence must remain "
        "mode/object-identical to canonical base: .superpowers/sdd/task-6-report.md",
        "Phase 0 interface freeze validator: historical B0 evidence must remain "
        "mode/object-identical to canonical base: governance/b0-report.json",
        "Phase 0 interface freeze validator: historical B0 evidence must remain "
        "mode/object-identical to canonical base: governance/b0-status.yaml",
    }

    assert validator.validate_b0_report(report, status, clone) == []
    assert set(validator.validate_repository(clone)) == expected_aggregate_errors

    reattested_report, reattested_status, _ = _install_schema_2_evidence_revision(
        clone, validator
    )

    assert validator.validate_b0_report(reattested_report, reattested_status, clone) == []
    assert set(validator.validate_repository(clone)) == expected_aggregate_errors


def test_schema_2_downgrade_latch_uses_the_version_marker_alone(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    report_path = clone / "governance/b0-report.json"
    legacy_content = _git_show_bytes(
        clone, LEGACY_REPORT_REVISION, "governance/b0-report.json"
    )
    report_path.write_text('{"schema_version": "2.0.0"}\n', encoding="utf-8")
    _commit_clone(clone, "record minimal schema 2 marker")
    report_path.write_bytes(legacy_content)
    _commit_clone(clone, "attempt downgrade after schema 2 marker")
    report = json.loads(legacy_content)
    status = yaml.safe_load(
        _git_show_bytes(clone, LEGACY_REPORT_REVISION, "governance/b0-status.yaml")
    )

    errors = validator.validate_b0_report(report, status, clone)

    assert any("schema downgrade" in error for error in errors)


def test_schema_2_downgrade_latch_scans_merged_side_parent_history(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    subprocess.run(
        ["git", "-C", str(clone), "checkout", "--quiet", "--detach", LEGACY_REPORT_REVISION],
        check=True,
        capture_output=True,
    )
    base = subprocess.check_output(
        ["git", "-C", str(clone), "rev-parse", "HEAD"], text=True
    ).strip()
    subprocess.run(
        ["git", "-C", str(clone), "checkout", "--quiet", "-b", "schema-marker"],
        check=True,
    )
    report_path = clone / "governance/b0-report.json"
    report_path.write_text('{"schema_version": "2.0.0"}\n', encoding="utf-8")
    _commit_clone(clone, "record side-parent schema 2 marker")
    subprocess.run(
        ["git", "-C", str(clone), "checkout", "--quiet", "--detach", base],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(clone),
            "-c",
            "user.name=policy-test",
            "-c",
            "user.email=policy@test",
            "merge",
            "--quiet",
            "--no-ff",
            "-s",
            "ours",
            "schema-marker",
            "-m",
            "merge hidden schema marker",
        ],
        check=True,
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    status = yaml.safe_load((clone / "governance/b0-status.yaml").read_text(encoding="utf-8"))

    errors = validator.validate_b0_report(report, status, clone)

    assert any("schema downgrade" in error for error in errors)


@pytest.mark.parametrize("after_schema_2_closure", [False, True])
def test_schema_history_rejects_fresh_schema_1_revision_hidden_by_ours_merge(
    tmp_path: Path,
    after_schema_2_closure: bool,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    fresh_schema_1 = _install_fresh_schema_1_side_parent(clone)

    if after_schema_2_closure:
        subprocess.run(
            ["git", "-C", str(clone), "checkout", "--quiet", "--detach", _head()],
            check=True,
            capture_output=True,
        )
        report, status, _ = _install_schema_2_evidence_revision(clone, validator)
    else:
        subprocess.run(
            [
                "git",
                "-C",
                str(clone),
                "checkout",
                "--quiet",
                "--detach",
                LEGACY_REPORT_REVISION,
            ],
            check=True,
            capture_output=True,
        )
        report = json.loads(
            _git_show_bytes(clone, LEGACY_REPORT_REVISION, "governance/b0-report.json")
        )
        status = yaml.safe_load(
            _git_show_bytes(clone, LEGACY_REPORT_REVISION, "governance/b0-status.yaml")
        )

    _merge_ours(clone, fresh_schema_1, "merge hidden fresh schema 1 report")

    errors = validator.validate_b0_report(report, status, clone)

    assert any(
        "schema 1.0.0" in error
        and LEGACY_REPORT_REVISION in error
        and fresh_schema_1 in error
        for error in errors
    ), errors


def test_schema_history_allows_side_descendant_that_carries_historical_report(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    subprocess.run(
        [
            "git",
            "-C",
            str(clone),
            "checkout",
            "--quiet",
            "-b",
            "unchanged-report-side",
            LEGACY_REPORT_REVISION,
        ],
        check=True,
        capture_output=True,
    )
    (clone / "unrelated-side.txt").write_text("unrelated side change\n", encoding="utf-8")
    side = _commit_clone(clone, "carry historical report unchanged")
    subprocess.run(
        [
            "git",
            "-C",
            str(clone),
            "checkout",
            "--quiet",
            "--detach",
            LEGACY_REPORT_REVISION,
        ],
        check=True,
        capture_output=True,
    )
    _merge_ours(clone, side, "merge unchanged historical report descendant")
    report = json.loads(
        _git_show_bytes(clone, LEGACY_REPORT_REVISION, "governance/b0-report.json")
    )
    status = yaml.safe_load(
        _git_show_bytes(clone, LEGACY_REPORT_REVISION, "governance/b0-status.yaml")
    )

    errors = validator.validate_b0_report(report, status, clone)

    assert not any("schema 1.0.0 is permitted only" in error for error in errors)


def test_schema_1_validation_requires_complete_history_in_a_shallow_clone(
    tmp_path: Path,
) -> None:
    validator = _validator()
    shallow = tmp_path / "shallow"
    subprocess.run(
        [
            "git",
            "clone",
            "--quiet",
            "--depth",
            "1",
            f"file://{REPO_ROOT}",
            str(shallow),
        ],
        check=True,
        capture_output=True,
    )
    report = json.loads(
        _git_show_bytes(shallow, LEGACY_REPORT_REVISION, "governance/b0-report.json")
        if subprocess.run(
            ["git", "-C", str(shallow), "cat-file", "-e", LEGACY_REPORT_REVISION],
            capture_output=True,
        ).returncode
        == 0
        else REPORT_PATH.read_bytes()
    )
    report["schema_version"] = "1.0.0"

    errors = validator.validate_b0_report(report, _status(), shallow)

    assert any("full history" in error or "shallow" in error for error in errors)


@pytest.mark.parametrize("malformed_schema_version", [[], {}])
def test_schema_2_history_scan_skips_deleted_and_malformed_snapshots(
    tmp_path: Path,
    malformed_schema_version,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    report_path = clone / "governance/b0-report.json"
    report_path.write_text('{"schema_version": "2.0.0"}\n', encoding="utf-8")
    _commit_clone(clone, "record schema 2 marker")
    report_path.unlink()
    _commit_clone(clone, "delete report snapshot")
    report_path.write_text('{"schema_version":', encoding="utf-8")
    _commit_clone(clone, "record malformed report snapshot")
    report_path.write_text(
        json.dumps({"schema_version": malformed_schema_version}) + "\n",
        encoding="utf-8",
    )
    _commit_clone(clone, "record malformed schema declaration")
    legacy_content = _git_show_bytes(
        clone, LEGACY_REPORT_REVISION, "governance/b0-report.json"
    )
    report_path.write_bytes(legacy_content)
    _commit_clone(clone, "attempt downgrade after malformed history")
    report = json.loads(legacy_content)
    status = yaml.safe_load(
        _git_show_bytes(clone, LEGACY_REPORT_REVISION, "governance/b0-status.yaml")
    )

    errors = validator.validate_b0_report(report, status, clone)

    assert any("schema downgrade" in error for error in errors)


def test_checked_in_evidence_rejects_a_committed_symlink(tmp_path: Path) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    relative = "research/logs/2026-07-18-dynamic-import-policy.md"
    evidence_path = clone / relative
    evidence_path.unlink()
    evidence_path.symlink_to("forged-policy.md")
    _commit_clone(clone, "replace checked-in evidence with symlink")
    report, status, _ = _install_schema_2_evidence_revision(clone, validator)

    errors = validator.validate_b0_report(report, status, clone)

    assert any(relative in error and "regular file" in error for error in errors)


def _root_commit_for_tree(repository: Path, treeish: str) -> str:
    tree = subprocess.check_output(
        ["git", "-C", str(repository), "rev-parse", f"{treeish}^{{tree}}"],
        text=True,
    ).strip()
    return subprocess.check_output(
        [
            "git",
            "-C",
            str(repository),
            "-c",
            "user.name=policy-test",
            "-c",
            "user.email=policy@test",
            "commit-tree",
            tree,
            "-m",
            "unrelated evidence root",
        ],
        text=True,
    ).strip()


def _write_probe(path: Path, probe: dict) -> str:
    content = (json.dumps(probe, indent=2, sort_keys=True) + "\n").encode()
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def _patch_canonical_entry(monkeypatch, validator, index: int, **updates: str) -> None:
    canonical = copy.deepcopy(list(validator.B0_REPORT_HOSTED_PROBES))
    canonical[index].update(updates)
    monkeypatch.setattr(validator, "B0_REPORT_HOSTED_PROBES", tuple(canonical))


def _set_probe_value(probe: dict, path: tuple[str | int, ...], value) -> None:
    target = probe
    for component in path[:-1]:
        target = target[component]
    target[path[-1]] = value


def test_hosted_probe_entries_are_exactly_linux_then_macos(validator=None) -> None:
    validator = _validator()
    entries = _hosted_entries(validator)
    assert validator.validate_hosted_probe_evidence(entries, REPO_ROOT, _head()) == []

    for malformed in (
        entries[:1],
        [*entries, copy.deepcopy(entries[0])],
        [copy.deepcopy(entries[1]), copy.deepcopy(entries[0])],
        [copy.deepcopy(entries[0]), copy.deepcopy(entries[0])],
    ):
        assert validator.validate_hosted_probe_evidence(
            malformed, REPO_ROOT, _head()
        )


@pytest.mark.parametrize("probe_index", [0, 1])
def test_hosted_probe_entry_schema_is_closed(probe_index: int) -> None:
    validator = _validator()
    entries = _hosted_entries(validator)

    missing = copy.deepcopy(entries)
    del missing[probe_index]["run_attempt"]
    assert any(
        "missing required fields" in error
        for error in validator.validate_hosted_probe_evidence(
            missing, REPO_ROOT, _head()
        )
    )

    unknown = copy.deepcopy(entries)
    unknown[probe_index]["unexpected"] = True
    assert any(
        "unknown fields" in error
        for error in validator.validate_hosted_probe_evidence(
            unknown, REPO_ROOT, _head()
        )
    )


@pytest.mark.parametrize("probe_index", [0, 1])
@pytest.mark.parametrize(
    ("field", "value", "needle"),
    [
        ("workflow_name", "wrong workflow", "workflow"),
        ("run_id", "1", "run_id"),
        ("run_attempt", "2", "run_attempt"),
        (
            "run_url",
            "https://github.com/TimoKruth/EvoNN-Research/actions/runs/1",
            "run_url",
        ),
        ("event", "pull_request", "event"),
        ("branch", "feature", "branch"),
        ("conclusion", "failure", "conclusion"),
        ("backend", "forged", "backend"),
        ("system", "forged", "system"),
        ("host_os", "forged", "host_os"),
        ("host_architecture", "forged", "host_architecture"),
        ("repository_commit", "0" * 40, "repository_commit"),
        ("execution_scope", "local", "execution_scope"),
        ("evidence_scope", "scientific", "evidence_scope"),
        ("qualification", "backend_qualified", "qualification"),
    ],
)
def test_hosted_probe_report_claim_drift_fails_closed(
    probe_index: int,
    field: str,
    value: str,
    needle: str,
) -> None:
    validator = _validator()
    entries = _hosted_entries(validator)
    entries[probe_index][field] = value
    errors = validator.validate_hosted_probe_evidence(
        entries, REPO_ROOT, _head()
    )
    assert any(needle in error for error in errors)


def test_hosted_probe_linux_macos_artifacts_cannot_be_swapped() -> None:
    validator = _validator()
    entries = _hosted_entries(validator)
    for field in ("artifact_path", "sha256"):
        entries[0][field], entries[1][field] = entries[1][field], entries[0][field]

    errors = validator.validate_hosted_probe_evidence(entries, REPO_ROOT, _head())

    assert any("numpy" in error and "artifact_path" in error for error in errors)
    assert any("mlx" in error and "artifact_path" in error for error in errors)


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "/tmp/probe.json",
        "../probe.json",
        "governance//evidence/b0/hosted/linux-runtime-probe.json",
    ],
)
def test_hosted_probe_rejects_absolute_parent_and_non_normalized_paths(
    unsafe_path: str,
) -> None:
    validator = _validator()
    entries = _hosted_entries(validator)
    entries[0]["artifact_path"] = unsafe_path

    errors = validator.validate_hosted_probe_evidence(entries, REPO_ROOT, _head())

    assert any("normalized repository-relative path" in error for error in errors)


@pytest.mark.parametrize(
    "unsafe_path",
    ["governance/evidence/b0/hosted/probe\0.json", "governance/\ud800/probe.json"],
)
def test_committed_regular_file_rejects_nul_and_unencodable_paths(
    unsafe_path: str,
) -> None:
    validator = _validator()

    content, error = validator._committed_regular_file(
        REPO_ROOT, _head(), unsafe_path, "hosted artifact"
    )

    assert content is None
    assert error and "path" in error


def test_committed_regular_file_converts_subprocess_argument_errors(
    monkeypatch,
) -> None:
    validator = _validator()

    def fail_git(*args):
        raise ValueError("invalid subprocess argument")

    monkeypatch.setattr(validator, "_git", fail_git)

    content, error = validator._committed_regular_file(
        REPO_ROOT, _head(), "governance/b0-report.json", "hosted artifact"
    )

    assert content is None
    assert error and "cannot be resolved" in error


@pytest.mark.parametrize(
    "raw_tree",
    [b"100644 blob deadbeef\t\xff\0", b"malformed\tgovernance\0"],
)
def test_committed_regular_file_converts_tree_record_errors(
    monkeypatch,
    raw_tree: bytes,
) -> None:
    validator = _validator()
    monkeypatch.setattr(validator, "_git", lambda *args: raw_tree)

    content, error = validator._committed_regular_file(
        REPO_ROOT, _head(), "governance/b0-report.json", "hosted artifact"
    )

    assert content is None
    assert error and "Git tree entry" in error


def test_committed_regular_file_rejects_a_missing_entry(tmp_path: Path) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    relative = validator.B0_REPORT_HOSTED_PROBES[0]["artifact_path"]
    (clone / relative).unlink()
    evidence_commit = _commit_clone(clone, "remove hosted artifact")

    content, error = validator._committed_regular_file(
        clone, evidence_commit, relative, "hosted artifact"
    )

    assert content is None
    assert error and "missing or ambiguous" in error


def test_committed_regular_file_rejects_a_submodule_entry(tmp_path: Path) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    relative = validator.B0_REPORT_HOSTED_PROBES[0]["artifact_path"]
    (clone / relative).unlink()
    subprocess.run(
        [
            "git",
            "-C",
            str(clone),
            "update-index",
            "--add",
            "--cacheinfo",
            f"160000,{validator.B0_CLOSURE_HOSTED_COMMIT},{relative}",
        ],
        check=True,
        capture_output=True,
    )
    evidence_commit = _commit_staged_clone(clone, "replace hosted artifact with gitlink")

    content, error = validator._committed_regular_file(
        clone, evidence_commit, relative, "hosted artifact"
    )

    assert content is None
    assert error and "committed regular file" in error


def test_committed_regular_file_rejects_a_directory_final_entry(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    relative = validator.B0_REPORT_HOSTED_PROBES[0]["artifact_path"]
    artifact = clone / relative
    artifact.unlink()
    artifact.mkdir()
    (artifact / "nested.json").write_text("{}\n", encoding="utf-8")
    evidence_commit = _commit_clone(clone, "replace hosted artifact with directory")

    content, error = validator._committed_regular_file(
        clone, evidence_commit, relative, "hosted artifact"
    )

    assert content is None
    assert error and "committed regular file" in error


@pytest.mark.parametrize("install_replacement", [False, True])
def test_hosted_probe_requires_closure_commit_ancestry(
    tmp_path: Path,
    install_replacement: bool,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    unrelated_evidence = _root_commit_for_tree(clone, "HEAD")
    if install_replacement:
        subprocess.run(
            ["git", "-C", str(clone), "replace", unrelated_evidence, _head()],
            check=True,
            capture_output=True,
        )

    errors = validator.validate_hosted_probe_evidence(
        _hosted_entries(validator), clone, unrelated_evidence
    )

    assert any("ancestor" in error for error in errors)


def test_committed_regular_file_ignores_git_replacement_objects(
    tmp_path: Path,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    relative = validator.B0_REPORT_HOSTED_PROBES[0]["manifest_path"]
    (clone / relative).write_text("forged manifest\n", encoding="utf-8")
    replacement = _commit_clone(clone, "forge replacement manifest")
    subprocess.run(
        ["git", "-C", str(clone), "replace", validator.B0_CLOSURE_HOSTED_COMMIT, replacement],
        check=True,
        capture_output=True,
    )
    expected = subprocess.check_output(
        [
            "git",
            "-C",
            str(clone),
            "cat-file",
            "blob",
            f"{validator.B0_CLOSURE_HOSTED_COMMIT}:{relative}",
        ],
        env={**os.environ, "GIT_NO_REPLACE_OBJECTS": "1"},
    )

    content, error = validator._committed_regular_file(
        clone,
        validator.B0_CLOSURE_HOSTED_COMMIT,
        relative,
        "hosted manifest",
    )

    assert error is None
    assert content == expected


@pytest.mark.parametrize("replace_parent", [False, True])
def test_hosted_probe_rejects_a_committed_symlink_component(
    tmp_path: Path,
    replace_parent: bool,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    hosted = clone / "governance/evidence/b0/hosted"
    if replace_parent:
        shutil.rmtree(hosted)
        hosted.symlink_to("../../..")
    else:
        artifact = hosted / "linux-runtime-probe.json"
        artifact.unlink()
        artifact.symlink_to("macos-runtime-probe.json")
    evidence_commit = _commit_clone(clone, "replace hosted evidence with symlink")

    errors = validator.validate_hosted_probe_evidence(
        _hosted_entries(validator), clone, evidence_commit
    )

    assert any(
        "symbolic-link" in error or "committed regular file" in error
        for error in errors
    )


@pytest.mark.parametrize("probe_index", [0, 1])
def test_hosted_probe_rejects_tampered_bytes_with_original_digest(
    tmp_path: Path,
    probe_index: int,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    artifact_path = clone / validator.B0_REPORT_HOSTED_PROBES[probe_index]["artifact_path"]
    probe = json.loads(artifact_path.read_text(encoding="utf-8"))
    probe["status"] = "failed"
    _write_probe(artifact_path, probe)
    evidence_commit = _commit_clone(clone, "tamper hosted evidence bytes")

    errors = validator.validate_hosted_probe_evidence(
        _hosted_entries(validator), clone, evidence_commit
    )

    assert any("SHA-256" in error for error in errors)


@pytest.mark.parametrize("probe_index", [0, 1])
def test_hosted_probe_rejects_tampered_bytes_even_when_digest_is_updated(
    tmp_path: Path,
    monkeypatch,
    probe_index: int,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    artifact_path = clone / validator.B0_REPORT_HOSTED_PROBES[probe_index]["artifact_path"]
    probe = json.loads(artifact_path.read_text(encoding="utf-8"))
    probe["system_under_test"] = "forged-system"
    digest = _write_probe(artifact_path, probe)
    evidence_commit = _commit_clone(clone, "tamper hosted evidence identity")
    _patch_canonical_entry(monkeypatch, validator, probe_index, sha256=digest)

    errors = validator.validate_hosted_probe_evidence(
        _hosted_entries(validator), clone, evidence_commit
    )

    backend = validator.B0_REPORT_HOSTED_PROBES[probe_index]["backend"]
    assert any(backend in error and "system" in error for error in errors)


@pytest.mark.parametrize("probe_index", [0, 1])
@pytest.mark.parametrize(
    ("path", "value", "needle"),
    [
        (("status",), "failed", "status"),
        (("qualification",), "backend_qualified", "qualification"),
        (("operation", "validated"), False, "validated"),
        (("operation", "actual"), 13.0, "actual"),
        (("manifest", "sha256"), "0" * 64, "manifest.sha256"),
    ],
)
def test_hosted_probe_internal_claim_mutations_fail_closed(
    tmp_path: Path,
    monkeypatch,
    probe_index: int,
    path: tuple[str, ...],
    value,
    needle: str,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    artifact_path = clone / validator.B0_REPORT_HOSTED_PROBES[probe_index]["artifact_path"]
    probe = json.loads(artifact_path.read_text(encoding="utf-8"))
    target = probe
    for component in path[:-1]:
        target = target[component]
    target[path[-1]] = value
    digest = _write_probe(artifact_path, probe)
    evidence_commit = _commit_clone(clone, f"mutate hosted claim {'.'.join(path)}")
    _patch_canonical_entry(monkeypatch, validator, probe_index, sha256=digest)

    errors = validator.validate_hosted_probe_evidence(
        _hosted_entries(validator), clone, evidence_commit
    )

    assert any(needle in error for error in errors)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("operation", "validated"), 1),
        (("operation", "actual"), 14),
        (("operation", "input"), [1, 2, 3]),
        (("operation", "unexpected"), "drift"),
    ],
)
def test_hosted_probe_operation_is_an_exact_closed_typed_mapping(
    tmp_path: Path,
    monkeypatch,
    path: tuple[str | int, ...],
    value,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    artifact_path = clone / validator.B0_REPORT_HOSTED_PROBES[0]["artifact_path"]
    probe = json.loads(artifact_path.read_text(encoding="utf-8"))
    _set_probe_value(probe, path, value)
    digest = _write_probe(artifact_path, probe)
    evidence_commit = _commit_clone(clone, "mutate exact hosted operation")
    _patch_canonical_entry(monkeypatch, validator, 0, sha256=digest)

    errors = validator.validate_hosted_probe_evidence(
        _hosted_entries(validator), clone, evidence_commit
    )

    assert any("operation" in error for error in errors)


@pytest.mark.parametrize("probe_index", [0, 1])
@pytest.mark.parametrize(
    ("path", "value", "needle"),
    [
        (("backend", "class"), "forged", "backend.class"),
        (("device_class",), "forged", "device_class"),
        (("evidence", "class"), "scientific", "evidence.class"),
        (("evidence", "statement"), "qualified", "evidence.statement"),
        (("package_under_test",), "forged-package", "package_under_test"),
        (("packages_validated", 0, "module"), "forged_module", "packages_validated"),
        (("precision_mode",), "float16", "precision_mode"),
        (("workers", "count"), 2, "workers"),
        (("host", "kernel"), "forged-kernel", "host"),
        (("workflow", "unexpected"), True, "semantic"),
        (("manifest", "unexpected"), True, "semantic"),
        (("unexpected",), True, "semantic"),
    ],
)
def test_hosted_probe_semantic_claim_drift_survives_outer_digest_repin(
    tmp_path: Path,
    monkeypatch,
    probe_index: int,
    path: tuple[str | int, ...],
    value,
    needle: str,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    artifact_path = clone / validator.B0_REPORT_HOSTED_PROBES[probe_index]["artifact_path"]
    probe = json.loads(artifact_path.read_text(encoding="utf-8"))
    _set_probe_value(probe, path, value)
    digest = _write_probe(artifact_path, probe)
    evidence_commit = _commit_clone(clone, "mutate hosted semantic claim")
    _patch_canonical_entry(monkeypatch, validator, probe_index, sha256=digest)

    errors = validator.validate_hosted_probe_evidence(
        _hosted_entries(validator), clone, evidence_commit
    )

    assert any(needle in error for error in errors)


@pytest.mark.parametrize("probe_index", [0, 1])
@pytest.mark.parametrize(
    ("original", "replacement", "duplicate_key"),
    [
        (
            b'  "status": "passed",',
            b'  "status": "failed",\n  "status": "passed",',
            "status",
        ),
        (
            b'  "operation": {\n    "actual": 14.0,',
            b'  "operation": {\n    "actual": 13.0,\n    "actual": 14.0,',
            "actual",
        ),
    ],
)
def test_hosted_probe_raw_duplicate_json_keys_fail_closed(
    tmp_path: Path,
    monkeypatch,
    probe_index: int,
    original: bytes,
    replacement: bytes,
    duplicate_key: str,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    artifact_path = clone / validator.B0_REPORT_HOSTED_PROBES[probe_index]["artifact_path"]
    content = artifact_path.read_bytes()
    assert content.count(original) == 1
    content = content.replace(original, replacement)
    artifact_path.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    evidence_commit = _commit_clone(clone, "install duplicate hosted JSON key")
    _patch_canonical_entry(monkeypatch, validator, probe_index, sha256=digest)

    errors = validator.validate_hosted_probe_evidence(
        _hosted_entries(validator), clone, evidence_commit
    )

    assert any(
        "duplicate JSON key" in error and duplicate_key in error
        for error in errors
    )


@pytest.mark.parametrize("probe_index", [0, 1])
@pytest.mark.parametrize("constant", [b"NaN", b"Infinity", b"-Infinity"])
def test_hosted_probe_non_standard_json_constants_fail_closed(
    tmp_path: Path,
    monkeypatch,
    probe_index: int,
    constant: bytes,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    artifact_path = clone / validator.B0_REPORT_HOSTED_PROBES[probe_index]["artifact_path"]
    content = artifact_path.read_bytes()
    original = b'    "actual": 14.0,'
    assert content.count(original) == 1
    content = content.replace(original, b'    "actual": ' + constant + b',')
    artifact_path.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    evidence_commit = _commit_clone(clone, "install non-standard hosted JSON constant")
    _patch_canonical_entry(monkeypatch, validator, probe_index, sha256=digest)

    errors = validator.validate_hosted_probe_evidence(
        _hosted_entries(validator), clone, evidence_commit
    )

    assert any("non-standard JSON constant" in error for error in errors)


@pytest.mark.parametrize("probe_index", [0, 1])
def test_hosted_probe_pathological_json_nesting_fails_closed(
    tmp_path: Path,
    monkeypatch,
    probe_index: int,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    artifact_path = clone / validator.B0_REPORT_HOSTED_PROBES[probe_index]["artifact_path"]
    content = ("[" * 10000 + "0" + "]" * 10000).encode()
    artifact_path.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    evidence_commit = _commit_clone(clone, "install pathologically nested hosted JSON")
    _patch_canonical_entry(monkeypatch, validator, probe_index, sha256=digest)

    errors = validator.validate_hosted_probe_evidence(
        _hosted_entries(validator), clone, evidence_commit
    )

    assert any("nesting" in error or "valid JSON" in error for error in errors)


@pytest.mark.parametrize("probe_index", [0, 1])
def test_hosted_probe_oversized_json_integer_fails_closed(
    tmp_path: Path,
    monkeypatch,
    probe_index: int,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    artifact_path = clone / validator.B0_REPORT_HOSTED_PROBES[probe_index]["artifact_path"]
    content = artifact_path.read_bytes()
    original = b'    "actual": 14.0,'
    assert content.count(original) == 1
    content = content.replace(original, b'    "actual": ' + b"1" * 5000 + b",")
    artifact_path.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    evidence_commit = _commit_clone(clone, "install oversized hosted JSON integer")
    _patch_canonical_entry(monkeypatch, validator, probe_index, sha256=digest)

    errors = validator.validate_hosted_probe_evidence(
        _hosted_entries(validator), clone, evidence_commit
    )

    assert any("strict JSON" in error or "valid JSON" in error for error in errors)


def test_hosted_probe_malformed_repository_commit_type_fails_closed() -> None:
    validator = _validator()
    entries = _hosted_entries(validator)
    entries[0]["repository_commit"] = []

    errors = validator.validate_hosted_probe_evidence(entries, REPO_ROOT, _head())

    assert any("repository_commit" in error for error in errors)


def test_hosted_probes_must_target_one_shared_closure_commit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    validator = _validator()
    clone = _committed_clone(tmp_path)
    different_commit = _head()
    artifact_path = clone / validator.B0_REPORT_HOSTED_PROBES[0]["artifact_path"]
    probe = json.loads(artifact_path.read_text(encoding="utf-8"))
    probe["repository_commit"] = different_commit
    digest = _write_probe(artifact_path, probe)
    evidence_commit = _commit_clone(clone, "retarget hosted evidence commit")
    _patch_canonical_entry(
        monkeypatch,
        validator,
        0,
        repository_commit=different_commit,
        sha256=digest,
    )

    errors = validator.validate_hosted_probe_evidence(
        _hosted_entries(validator), clone, evidence_commit
    )

    assert any("shared B0 closure commit" in error for error in errors)
