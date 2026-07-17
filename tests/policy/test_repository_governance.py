from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import subprocess

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / "scripts/policy/validate_repository_governance.py"


@pytest.fixture(scope="module")
def validator():
    assert VALIDATOR_PATH.is_file(), "repository governance validator is not installed"
    spec = importlib.util.spec_from_file_location("repository_governance", VALIDATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def manifest() -> dict:
    path = REPO_ROOT / "governance/authority-provenance.yaml"
    assert path.is_file(), "authority provenance manifest is not installed"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def b0_status() -> dict:
    return yaml.safe_load((REPO_ROOT / "governance/b0-status.yaml").read_text(encoding="utf-8"))


def test_repository_governance_policy_passes(validator) -> None:
    assert validator.validate_repository(REPO_ROOT) == []


def test_only_consolidated_plan_is_active_and_root_plan_names_are_allowlisted(validator) -> None:
    assert validator.find_active_execution_plans(REPO_ROOT) == [Path("CONSOLIDATED_PLAN.md")]
    assert not (REPO_ROOT / "LAB_PLAN.md").exists()
    assert validator.ALLOWED_ROOT_PLAN_FILENAMES == {"CONSOLIDATED_PLAN.md"}


def test_plan_scanner_excludes_pinned_and_archive_trees_but_checks_owned_docs(validator, tmp_path: Path) -> None:
    for excluded in ("claude-spec", "claudex-spec", "archive"):
        path = tmp_path / excluded / "DECOY_PLAN.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\ndocument_kind: execution_plan\nstatus: active\n---\n", encoding="utf-8")
    package = tmp_path / "packages/example"
    package.mkdir(parents=True)
    (package / "PLAN.md").write_text(
        "---\ndocument_kind: execution_plan\nstatus: active\nauthoritative: true\n---\n",
        encoding="utf-8",
    )
    (package / "CONTRADICTORY.md").write_text(
        "---\ndocument_kind: execution_plan\nstatus: active\nauthoritative: false\n---\n",
        encoding="utf-8",
    )
    (package / "GUIDE.md").write_text(
        "---\ndocument_kind: guide\nstatus: current\n---\n\n**Status:** Active execution plan\n",
        encoding="utf-8",
    )
    assert validator.find_active_execution_plans(tmp_path) == [
        Path("packages/example/CONTRADICTORY.md"),
        Path("packages/example/GUIDE.md"),
        Path("packages/example/PLAN.md"),
    ]


def test_unclassified_plan_like_project_docs_fail_closed(validator, tmp_path: Path) -> None:
    candidate = tmp_path / "packages/example/ALT_PLAN.md"
    candidate.parent.mkdir(parents=True)
    candidate.write_text("# Alternate Execution Plan\n\nStatus: active\n", encoding="utf-8")
    errors = validator.validate_plan_metadata(tmp_path)
    assert any("ALT_PLAN.md" in error and "frontmatter" in error for error in errors)
    assert validator.find_active_execution_plans(tmp_path) == [Path("packages/example/ALT_PLAN.md")]


def test_plan_scanner_does_not_classify_governance_or_research_prose_as_plans(validator, tmp_path: Path) -> None:
    samples = {
        "PROGRAM_CHARTER.md": "This charter is not an execution plan.",
        "VISION.md": "Vision and execution plan context only.",
        "SPECIFICATION.md": "Normative specification; no work packages.",
        "research/log.md": "Research log discussing the active execution plan.",
    }
    for relative, text in samples.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    assert validator.find_active_execution_plans(tmp_path) == []
    assert validator.validate_plan_metadata(tmp_path) == []


def test_archived_project_plans_must_be_explicitly_non_authoritative(validator, tmp_path: Path) -> None:
    archive = tmp_path / "archive"
    archive.mkdir()
    bad = archive / "OLD_PLAN.md"
    bad.write_text("---\ndocument_kind: execution_plan\nstatus: archived\n---\n", encoding="utf-8")
    assert validator.validate_archived_plans(tmp_path)
    bad.write_text(
        "---\ndocument_kind: execution_plan\nstatus: archived\nauthoritative: false\n---\n",
        encoding="utf-8",
    )
    assert validator.validate_archived_plans(tmp_path) == []


def test_provenance_manifest_matches_independent_trust_anchor(validator, manifest: dict) -> None:
    assert validator.validate_provenance(manifest, REPO_ROOT) == []
    entries = {entry["id"]: entry for entry in manifest["sources"]}
    assert set(entries) == set(validator.EXPECTED_SOURCES)
    for source_id, expected in validator.EXPECTED_SOURCES.items():
        entry = entries[source_id]
        for field in (
            "scope",
            "path",
            "source_commit",
            "declared_version",
            "git_object_type",
            "git_object_id",
            "consumer_acceptance_authority",
        ):
            assert entry[field] == expected[field]
        assert entry["content_digest"]["value"] == expected["digest"]


def test_local_only_authority_keeps_b02_open_and_requires_null_url(
    validator, manifest: dict, b0_status: dict
) -> None:
    assert manifest["authority_state"] == "local-only/provisional"
    assert "b0_2_status" not in manifest and "b0_2_open_reason" not in manifest
    duplicated_status = copy.deepcopy(manifest)
    duplicated_status["b0_2_status"] = "closed"
    duplicated_status["b0_2_open_reason"] = None
    assert any("gate status" in error for error in validator.validate_provenance(duplicated_status, REPO_ROOT))
    assert all(entry["origin_state"] == "local-only/provisional" for entry in manifest["sources"])
    assert all(entry["upstream_url"] is None for entry in manifest["sources"])
    assert b0_status["items"]["B0.2"] == {
        "status": "open",
        "open_reason": "authoritative_remote_url_absent",
        "evidence": "governance/authority-provenance.yaml is local-only/provisional with null upstream URLs",
    }
    assert validator.validate_b0_status(b0_status, manifest, REPO_ROOT) == []


def _closed_b0_status() -> dict:
    return {
        "document_kind": "gate_status",
        "gate": "B0",
        "items": {
            "B0.1": {"status": "locally_satisfied"},
            "B0.2": {"status": "closed", "open_reason": None},
            "B0.6": {"status": "locally_satisfied"},
        },
    }


def _configure_remote(repo: Path, url: str) -> None:
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", url], check=True)


def test_configured_real_remote_can_close_b02_without_changing_source_pin_or_digest(
    validator, manifest: dict, tmp_path: Path
) -> None:
    remote_url = "https://code.example.org/authority/evonn.git"
    _configure_remote(tmp_path, remote_url)
    upgraded = copy.deepcopy(manifest)
    upgraded["authority_state"] = "remote-pinned"
    for entry in upgraded["sources"]:
        entry["origin_state"] = "authoritative-remote"
        entry["upstream_url"] = remote_url
    before = [(e["source_commit"], e["git_object_id"], e["content_digest"]) for e in manifest["sources"]]
    after = [(e["source_commit"], e["git_object_id"], e["content_digest"]) for e in upgraded["sources"]]
    assert before == after
    assert validator.validate_b0_status(_closed_b0_status(), upgraded, tmp_path) == []


def test_unknown_inconsistent_or_unconfigured_remote_authority_fails_closed(
    validator, manifest: dict, tmp_path: Path
) -> None:
    configured_url = "https://code.example.org/authority/evonn.git"
    _configure_remote(tmp_path, configured_url)
    unknown = copy.deepcopy(manifest)
    unknown["authority_state"] = "remote-ish"
    for entry in unknown["sources"]:
        entry["origin_state"] = "authoritative-remote"
        entry["upstream_url"] = configured_url
    assert validator.validate_b0_status(_closed_b0_status(), unknown, tmp_path)

    inconsistent = copy.deepcopy(unknown)
    inconsistent["authority_state"] = "remote-pinned"
    inconsistent["sources"][0]["origin_state"] = "local-only/provisional"
    assert validator.validate_b0_status(_closed_b0_status(), inconsistent, tmp_path)

    fake = copy.deepcopy(inconsistent)
    for entry in fake["sources"]:
        entry["origin_state"] = "authoritative-remote"
        entry["upstream_url"] = "https://fake.example.invalid/not-configured.git"
    errors = validator.validate_b0_status(_closed_b0_status(), fake, tmp_path)
    assert any("configured Git remote" in error for error in errors)


def test_source_change_without_provenance_update_fails(validator, tmp_path: Path) -> None:
    tree = tmp_path / "authority"
    tree.mkdir()
    source = tree / "source.txt"
    source.write_text("pinned bytes\n", encoding="utf-8")
    manifest = {
        "sources": [
            {
                "id": "synthetic-authority",
                "scope": "directory",
                "path": "authority/",
                "content_digest": {
                    "algorithm": "sha256",
                    "value": validator.canonical_tree_digest_from_worktree(tree),
                },
            }
        ]
    }
    assert validator.validate_working_tree_digests(manifest, tmp_path) == []
    source.write_text("changed bytes\n", encoding="utf-8")
    errors = validator.validate_working_tree_digests(manifest, tmp_path)
    assert any("synthetic-authority" in error and "digest" in error for error in errors)


def test_only_product_interop_has_consumer_acceptance_authority(manifest: dict) -> None:
    authoritative = [entry["id"] for entry in manifest["sources"] if entry["consumer_acceptance_authority"]]
    assert authoritative == ["product-research-interop"]


def test_upgrade_and_traceability_controls_are_machine_readable(validator) -> None:
    upgrade = validator.read_frontmatter(REPO_ROOT / "governance/SPEC_UPGRADE_PROCESS.md")
    assert upgrade["upgrade_policy"] == {
        "review_vehicle": "pull_request",
        "review_required": True,
        "required_evidence": [
            "source_diff",
            "new_provenance",
            "traceability_impact",
            "supersession_statement",
            "policy_test_results",
        ],
        "forbidden_references": ["floating_branch", "floating_tag", "latest"],
        "pin_update": "atomic_with_validator_trust_anchor",
    }
    traceability = validator.read_frontmatter(REPO_ROOT / "governance/SPEC_TRACEABILITY.md")
    assert [source["path"] for source in traceability["governing_sources"]] == [
        "claude-spec/",
        "PROGRAM_CHARTER.md",
        "claudex-spec/19-research-interop.md",
    ]
    assert traceability["interop_authorization"] == {
        "lab_producer_authorizes_product_behavior": False,
        "real_product_influence_requires": ["I1", "I2"],
        "product_acceptance_authority": "claudex-spec/19-research-interop.md",
    }
    assert traceability["installed_execution_plan"] == "CONSOLIDATED_PLAN.md"


def test_consolidated_plan_frontmatter_matches_normative_b0_repository_model(validator) -> None:
    metadata = validator.read_frontmatter(REPO_ROOT / "CONSOLIDATED_PLAN.md")
    assert metadata["document_kind"] == "execution_plan"
    assert metadata["status"] == "active"
    assert metadata["revision"] == 2
    assert metadata["b0_repository_model"] == validator.EXPECTED_B0_REPOSITORY_MODEL
