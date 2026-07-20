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


def test_empty_report_cannot_skip_report_validation(validator, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(validator, "_load_json", lambda _path: {})
    errors = validator.validate_repository(REPO_ROOT)
    assert any("B0 report schema_version" in error for error in errors)


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


def test_execution_plan_observation_heading_is_not_an_active_plan(validator, tmp_path: Path) -> None:
    log = tmp_path / "research/2026-07-17-observations.md"
    log.parent.mkdir(parents=True)
    log.write_text("# Execution plan observations\n\nStatus: active\n", encoding="utf-8")
    assert validator.find_active_execution_plans(tmp_path) == []
    assert validator.validate_plan_metadata(tmp_path) == []


def test_research_plan_like_paths_and_names_are_logs_unless_explicitly_typed(validator, tmp_path: Path) -> None:
    research_log = tmp_path / "research/EXECUTION_PLAN_OBSERVATIONS.md"
    research_log.parent.mkdir(parents=True)
    root_observations = tmp_path / "EXECUTION_PLAN_OBSERVATIONS.md"
    for path in (research_log, root_observations):
        path.write_text("# Execution Plan\n\nStatus: active\n", encoding="utf-8")
    assert validator.find_active_execution_plans(tmp_path) == []
    assert validator.validate_plan_metadata(tmp_path) == []
    assert validator.validate_root_plan_filenames(tmp_path) == []

    research_log.write_text(
        "---\ndocument_kind: execution_plan\nstatus: active\nauthoritative: true\n---\n# Execution Plan\n",
        encoding="utf-8",
    )
    assert validator.find_active_execution_plans(tmp_path) == [Path("research/EXECUTION_PLAN_OBSERVATIONS.md")]
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


def test_versioned_and_completed_archive_plan_names_require_metadata_without_false_positives(
    validator, tmp_path: Path
) -> None:
    archive = tmp_path / "archive"
    archive.mkdir()
    plan_candidates = (archive / "OLD_PLAN_v2.md", archive / "IMPLEMENTATION_CHECKLIST_DONE.md")
    for path in plan_candidates:
        path.write_text("archived work\n", encoding="utf-8")
    for name in ("LAB_PLAN_CRITIQUE.md", "EXECUTION_PLAN_OBSERVATIONS.md", "PLANNING_NOTES.md"):
        (archive / name).write_text("analysis only\n", encoding="utf-8")
    errors = validator.validate_archived_plans(tmp_path)
    assert all(any(path.name in error for error in errors) for path in plan_candidates)
    assert not any("CRITIQUE" in error or "OBSERVATIONS" in error or "PLANNING_NOTES" in error for error in errors)

    metadata = "---\ndocument_kind: execution_plan\nstatus: archived\nauthoritative: false\n---\n"
    for path in plan_candidates:
        path.write_text(metadata, encoding="utf-8")
    assert validator.validate_archived_plans(tmp_path) == []


def test_checked_in_provenance_is_remote_pinned_without_source_pin_changes(
    validator,
    manifest: dict,
) -> None:
    assert manifest["status"] == "active"
    assert manifest["authority_state"] == "remote-pinned"
    assert all(entry["origin_state"] == "authoritative-remote" for entry in manifest["sources"])
    assert all(
        entry["upstream_url"] == "https://github.com/TimoKruth/EvoNN-Research.git"
        for entry in manifest["sources"]
    )

    for entry, (source_id, expected) in zip(manifest["sources"], validator.EXPECTED_SOURCES.items()):
        assert entry["id"] == source_id
        for field in (
            "scope",
            "path",
            "normative_role",
            "source_commit",
            "declared_version",
            "imported_at",
            "git_object_type",
            "git_object_id",
            "consumer_acceptance_authority",
            "supersedes",
        ):
            assert type(entry[field]) is type(expected[field])
            assert entry[field] == expected[field]
        assert type(entry["content_digest"]["value"]) is type(expected["digest"])
        assert entry["content_digest"]["value"] == expected["digest"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("normative_role", "Forged but non-empty normative role"),
        ("imported_at", "2026-07-18T14:49:43Z"),
        ("supersedes", "forged-predecessor"),
    ],
)
def test_provenance_rejects_immutable_source_metadata_drift(
    validator,
    manifest: dict,
    field: str,
    value: str,
) -> None:
    drifted = copy.deepcopy(manifest)
    drifted["sources"][0][field] = value

    errors = validator.validate_provenance(drifted, REPO_ROOT)

    assert any("claude-spec" in error and field in error for error in errors)


@pytest.mark.parametrize(
    ("source_id", "integer_alias"),
    [("claude-spec", 0), ("product-research-interop", 1)],
)
def test_provenance_rejects_boolean_integer_aliases_in_immutable_metadata(
    validator,
    manifest: dict,
    source_id: str,
    integer_alias: int,
) -> None:
    drifted = copy.deepcopy(manifest)
    source = next(entry for entry in drifted["sources"] if entry["id"] == source_id)
    source["consumer_acceptance_authority"] = integer_alias

    errors = validator.validate_provenance(drifted, REPO_ROOT)

    assert any(
        source_id in error and "consumer_acceptance_authority" in error
        for error in errors
    )


@pytest.mark.parametrize("content_digest", [None, [], "sha256:forged"])
def test_provenance_rejects_malformed_content_digest_without_crashing(
    validator,
    manifest: dict,
    content_digest,
) -> None:
    malformed = copy.deepcopy(manifest)
    malformed["sources"][0]["content_digest"] = content_digest

    errors = validator.validate_provenance(malformed, REPO_ROOT)

    assert any(
        "claude-spec" in error and "SHA-256 digest" in error for error in errors
    )


def test_provenance_pinned_source_reads_ignore_replacement_objects(
    validator,
    manifest: dict,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "replaced-authority"
    subprocess.run(
        ["git", "clone", "--quiet", "--no-local", str(REPO_ROOT), str(repository)],
        check=True,
        capture_output=True,
    )
    pinned = validator.PINNED_SOURCE_COMMIT
    git = [
        "git",
        "-C",
        str(repository),
        "-c",
        "user.name=policy-test",
        "-c",
        "user.email=policy@test",
    ]
    subprocess.run(
        [*git, "checkout", "--quiet", "--detach", pinned],
        check=True,
        capture_output=True,
    )
    (repository / "claude-spec/00-scope-and-goals.md").write_text(
        "forged specification bytes\n",
        encoding="utf-8",
    )
    (repository / "claude-spec/forged-only.md").write_text(
        "replacement-only path\n",
        encoding="utf-8",
    )
    (repository / "PROGRAM_CHARTER.md").write_text(
        "forged charter bytes\n",
        encoding="utf-8",
    )
    (repository / "claudex-spec/19-research-interop.md").write_text(
        "forged interop bytes\n",
        encoding="utf-8",
    )
    subprocess.run([*git, "add", "-A"], check=True, capture_output=True)
    subprocess.run(
        [*git, "commit", "--quiet", "-m", "forged source commit"],
        check=True,
        capture_output=True,
    )
    replacement_commit = subprocess.check_output(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    replacement_tree = subprocess.check_output(
        ["git", "-C", str(repository), "rev-parse", "HEAD:claude-spec"],
        text=True,
    ).strip()
    replacement_blob = subprocess.run(
        ["git", "-C", str(repository), "hash-object", "-w", "--stdin"],
        input=b"forged replacement blob\n",
        check=True,
        capture_output=True,
    ).stdout.decode().strip()
    replacements = {
        pinned: replacement_commit,
        validator.EXPECTED_SOURCES["claude-spec"]["git_object_id"]: replacement_blob,
        validator.EXPECTED_SOURCES["program-charter"]["git_object_id"]: replacement_tree,
        validator.EXPECTED_SOURCES["product-research-interop"]["git_object_id"]: replacement_tree,
    }
    for original, replacement in replacements.items():
        subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "update-ref",
                f"refs/replace/{original}",
                replacement,
            ],
            check=True,
            capture_output=True,
        )

    expected_tree = validator.EXPECTED_SOURCES["claude-spec"]["git_object_id"]
    assert subprocess.check_output(
        ["git", "-C", str(repository), "rev-parse", f"{pinned}:claude-spec"],
        text=True,
    ).strip() != expected_tree
    assert subprocess.check_output(
        [
            "git",
            "-C",
            str(repository),
            "--no-replace-objects",
            "rev-parse",
            f"{pinned}:claude-spec",
        ],
        text=True,
    ).strip() == expected_tree
    assert validator.validate_provenance(
        manifest,
        repository,
        check_worktree=False,
    ) == []

    protected_git = validator._git
    for vulnerable_subcommand in ("rev-parse", "cat-file", "ls-tree", "show"):
        def selectively_unprotected_git(repo_root: Path, *args: str) -> bytes:
            if args[:2] == ("--no-replace-objects", vulnerable_subcommand):
                args = args[1:]
            return protected_git(repo_root, *args)

        monkeypatch.setattr(validator, "_git", selectively_unprotected_git)
        errors = validator.validate_provenance(
            manifest,
            repository,
            check_worktree=False,
        )
        monkeypatch.setattr(validator, "_git", protected_git)

        assert errors, f"{vulnerable_subcommand} accepted replacement objects"


def test_provenance_rejects_non_mapping_duplicate_and_incomplete_entries(validator, manifest: dict) -> None:
    malformed = copy.deepcopy(manifest)
    malformed["sources"].append("not-a-mapping")
    malformed["sources"].append({"id": "claude-spec"})
    malformed["b0_2_status"] = "closed"
    errors = validator.validate_provenance(malformed, REPO_ROOT)
    assert any("source entry" in error and "mapping" in error for error in errors)
    assert any("duplicate provenance source id: claude-spec" in error for error in errors)
    assert any("claude-spec" in error and "missing fields" in error for error in errors)
    assert any("gate status" in error for error in errors)


def test_synthetic_local_only_authority_keeps_b02_open(
    validator,
    manifest: dict,
    b0_status: dict,
) -> None:
    local = copy.deepcopy(manifest)
    local["status"] = "provisional"
    local["authority_state"] = "local-only/provisional"
    for entry in local["sources"]:
        entry["origin_state"] = "local-only/provisional"
        entry["upstream_url"] = None

    status = copy.deepcopy(b0_status)
    status["status"] = "open"
    status["items"]["B0.2"]["status"] = "open"
    status["items"]["B0.2"]["open_reason"] = "authoritative_remote_url_absent"

    assert validator.validate_b0_status(status, local, REPO_ROOT) == []


def test_b0_status_identity_and_required_item_shape_fail_closed(validator, manifest: dict, b0_status: dict) -> None:
    wrong_kind = copy.deepcopy(b0_status)
    wrong_kind["document_kind"] = "note"
    assert validator.validate_b0_status(wrong_kind, manifest, REPO_ROOT)

    wrong_gate = copy.deepcopy(b0_status)
    wrong_gate["gate"] = "B1"
    assert validator.validate_b0_status(wrong_gate, manifest, REPO_ROOT)

    non_mapping_items = copy.deepcopy(b0_status)
    non_mapping_items["items"] = []
    assert validator.validate_b0_status(non_mapping_items, manifest, REPO_ROOT)

    missing_item = copy.deepcopy(b0_status)
    del missing_item["items"]["B0.6"]
    assert validator.validate_b0_status(missing_item, manifest, REPO_ROOT)

    extra_item = copy.deepcopy(b0_status)
    extra_item["items"]["B0.7"] = {"status": "open"}
    assert validator.validate_b0_status(extra_item, manifest, REPO_ROOT)

    malformed_item = copy.deepcopy(b0_status)
    malformed_item["items"]["B0.1"] = "locally_satisfied"
    assert validator.validate_b0_status(malformed_item, manifest, REPO_ROOT)


def _b02_closed_b0_status() -> dict:
    return {
        "document_kind": "gate_status",
        "gate": "B0",
        "status": "open",
        "items": {
            "B0.1": {"status": "locally_satisfied"},
            "B0.2": {"status": "closed", "open_reason": None},
            "B0.3": {"status": "open", "open_reason": "unimplemented"},
            "B0.4": {"status": "open", "open_reason": "unimplemented"},
            "B0.5": {"status": "open", "open_reason": "unimplemented"},
            "B0.6": {"status": "locally_satisfied"},
        },
    }


def _configure_remote(repo: Path, url: str) -> None:
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", url], check=True)


def _remote_pinned_manifest(manifest: dict, url: str) -> dict:
    upgraded = copy.deepcopy(manifest)
    upgraded["status"] = "active"
    upgraded["authority_state"] = "remote-pinned"
    for entry in upgraded["sources"]:
        entry["origin_state"] = "authoritative-remote"
        entry["upstream_url"] = url
    return upgraded


def test_canonical_https_authority_matches_configured_ssh_origin(
    validator,
    manifest: dict,
    tmp_path: Path,
) -> None:
    _configure_remote(
        tmp_path,
        "git@github.com:TimoKruth/EvoNN-Research.git",
    )
    status = _b02_closed_b0_status()
    assert validator.validate_b0_status(status, manifest, tmp_path) == []


def test_b0_closure_rejects_a_noncanonical_real_remote(
    validator,
    manifest: dict,
    tmp_path: Path,
) -> None:
    url = "https://code.example.org/authority/evonn.git"
    _configure_remote(tmp_path, url)
    changed = _remote_pinned_manifest(manifest, url)
    errors = validator.validate_b0_status(
        _b02_closed_b0_status(),
        changed,
        tmp_path,
    )
    assert any("B0 authority URL" in error for error in errors)


def test_remote_pinned_provenance_requires_active_status_and_canonical_urls(
    validator,
    manifest: dict,
) -> None:
    canonical = _remote_pinned_manifest(manifest, validator.B0_CLOSURE_AUTHORITY_URL)
    assert validator.validate_provenance(canonical, REPO_ROOT) == []

    provisional = copy.deepcopy(canonical)
    provisional["status"] = "provisional"
    assert any("status" in error for error in validator.validate_provenance(provisional, REPO_ROOT))

    noncanonical = _remote_pinned_manifest(manifest, "https://code.example.org/authority/evonn.git")
    assert any("B0 authority URL" in error for error in validator.validate_provenance(noncanonical, REPO_ROOT))


def test_commit_a_allows_only_the_historical_b02_open_state_when_closure_pending(
    validator,
    manifest: dict,
    b0_status: dict,
) -> None:
    assert validator.validate_b0_status(
        b0_status,
        manifest,
        REPO_ROOT,
        closure_pending=True,
    ) == []
    assert validator.validate_b0_status(b0_status, manifest, REPO_ROOT)

    changed = copy.deepcopy(b0_status)
    changed["items"]["B0.2"]["evidence"] = "not the historical closure-transition evidence"
    assert validator.validate_b0_status(
        changed,
        manifest,
        REPO_ROOT,
        closure_pending=True,
    )


def test_b0_report_schema_versions_distinguish_legacy_transition_from_closure(validator) -> None:
    assert validator.B0_REPORT_LEGACY_SCHEMA_VERSION == "1.0.0"
    assert validator.B0_REPORT_SCHEMA_VERSION == "2.0.0"
    assert validator.B0_REPORT_CLOSED_NEXT_TRANSITION == (
        "The team must jointly freeze the Phase 0 interfaces before creating "
        "Lane A and Lane B implementation branches."
    )


def test_overall_b0_closes_only_when_all_six_items_are_closed(validator, manifest: dict, tmp_path: Path) -> None:
    remote_url = "https://github.com/TimoKruth/EvoNN-Research.git"
    _configure_remote(tmp_path, remote_url)
    upgraded = _remote_pinned_manifest(manifest, remote_url)

    falsely_closed = _b02_closed_b0_status()
    falsely_closed["status"] = "closed"
    assert validator.validate_b0_status(falsely_closed, upgraded, tmp_path)

    fully_closed = _b02_closed_b0_status()
    fully_closed["status"] = "closed"
    for item in fully_closed["items"].values():
        item["status"] = "closed"
        item["open_reason"] = None
    assert validator.validate_b0_status(fully_closed, upgraded, tmp_path) == []


@pytest.mark.parametrize(
    "local_url",
    [
        "file:/tmp/evonn.git",
        "file:///tmp/evonn.git",
        "/tmp/evonn.git",
        "../evonn.git",
        "localhost:/tmp/evonn.git",
        "127.0.0.1:/tmp/evonn.git",
    ],
)
def test_local_or_file_git_remotes_cannot_close_b02(validator, manifest: dict, tmp_path: Path, local_url: str) -> None:
    _configure_remote(tmp_path, local_url)
    upgraded = _remote_pinned_manifest(manifest, local_url)
    errors = validator.validate_b0_status(_b02_closed_b0_status(), upgraded, tmp_path)
    assert any("authoritative HTTPS or SSH URL" in error for error in errors)


def test_unknown_inconsistent_or_unconfigured_remote_authority_fails_closed(
    validator, manifest: dict, tmp_path: Path
) -> None:
    configured_url = "https://github.com/TimoKruth/EvoNN-Research.git"
    _configure_remote(tmp_path, configured_url)
    unknown = copy.deepcopy(manifest)
    unknown["authority_state"] = "remote-ish"
    for entry in unknown["sources"]:
        entry["origin_state"] = "authoritative-remote"
        entry["upstream_url"] = configured_url
    assert validator.validate_b0_status(_b02_closed_b0_status(), unknown, tmp_path)

    inconsistent = copy.deepcopy(unknown)
    inconsistent["authority_state"] = "remote-pinned"
    inconsistent["sources"][0]["origin_state"] = "local-only/provisional"
    assert validator.validate_b0_status(_b02_closed_b0_status(), inconsistent, tmp_path)

    fake = copy.deepcopy(inconsistent)
    for entry in fake["sources"]:
        entry["origin_state"] = "authoritative-remote"
        entry["upstream_url"] = "https://fake.example.invalid/not-configured.git"
    errors = validator.validate_b0_status(_b02_closed_b0_status(), fake, tmp_path)
    assert any("B0 authority URL" in error for error in errors)

    subprocess.run(["git", "-C", str(tmp_path), "remote", "remove", "origin"], check=True)
    errors = validator.validate_b0_status(_b02_closed_b0_status(), manifest, tmp_path)
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
