from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / "scripts/policy/validate_phase0_interface_freeze.py"
RECORD_PATH = REPO_ROOT / "governance/phase0-interface-freeze.yaml"
APRIME = "b720ea6461c970e3875f8ef735e3e63cf680b660"
APRIME_TREE = "f1c5742c2581d270af05714b5ef8514c3f49d996"
CANONICAL_BASE = "b22316d3dea7e0f01ee8aa359f4786897b0680ba"
ALLOWED_BINDING_PATHS = (
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
REVIEW_DIGESTS = {
    "reviews/2026-07-21-phase0-lane-a-producer-review.md": (
        "9299b5a0e3aef5ac5d2dabe053ca205783f15920605dde57d6b5964f69a66833"
    ),
    "reviews/2026-07-21-phase0-lane-b-consumer-review.md": (
        "f82e42b230fb60f8d1e58d9f072f3aba43f2375fe9578a4854987fbc0291072c"
    ),
}
DIGESTS = {
    "canonical_digest_rng": "1806b230d6d218154898f5db8eae4089ffda07bfdf8c395d3523946a2f9fb7bc",
    "export_models": "b18bcdcc8fd8e4cbb6d9dfb1f82c0d998a1f3fedce927991d79388139c2275fc",
    "catalog_loaders": "81cf090ba61b1bfb1bdbf4a5e74c9fe46bfe34f36dcc5c44f72cd4f5cb33edc5",
}


@pytest.fixture(scope="module")
def validator():
    assert VALIDATOR_PATH.is_file(), "Phase 0 interface freeze validator is not installed"
    spec = importlib.util.spec_from_file_location("phase0_interface_freeze", VALIDATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repository: Path, *args: str, text: bool = True) -> str | bytes:
    return subprocess.check_output(
        ["git", "-C", str(repository), "--no-replace-objects", *args],
        text=text,
    )


def _commit(repository: Path, message: str) -> str:
    command = [
        "git",
        "-C",
        str(repository),
        "-c",
        "user.name=policy-test",
        "-c",
        "user.email=policy@test",
    ]
    subprocess.run([*command, "add", "-A"], check=True, capture_output=True)
    subprocess.run([*command, "commit", "--quiet", "-m", message], check=True, capture_output=True)
    return str(_git(repository, "rev-parse", "HEAD")).strip()


def _binding_clone(tmp_path: Path, *, omit_path: str | None = None) -> Path:
    clone = tmp_path / "binding-clone"
    subprocess.run(
        ["git", "clone", "--quiet", "--no-local", str(REPO_ROOT), str(clone)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(clone), "checkout", "--quiet", "--detach", APRIME],
        check=True,
        capture_output=True,
    )
    for relative in ALLOWED_BINDING_PATHS:
        if relative == omit_path:
            continue
        source = REPO_ROOT / relative
        assert source.is_file(), relative
        destination = clone / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    binding = _commit(clone, "synthetic Phase 0 binding")
    assert str(_git(clone, "rev-parse", f"{binding}^")).strip() == APRIME
    return clone


def _record(repository: Path) -> dict:
    loaded = yaml.safe_load((repository / "governance/phase0-interface-freeze.yaml").read_bytes())
    assert isinstance(loaded, dict)
    return loaded


def _assert_valid(validator, repository: Path) -> dict:
    record = _record(repository)
    assert validator.validate_phase0_interface_freeze(repository, record) == []
    return record


def _write_record(repository: Path, record: dict) -> None:
    (repository / "governance/phase0-interface-freeze.yaml").write_text(
        yaml.safe_dump(record, sort_keys=False),
        encoding="utf-8",
    )


def test_checked_in_record_and_synthetic_binding_are_valid(validator, tmp_path: Path) -> None:
    clone = _binding_clone(tmp_path)
    record = _assert_valid(validator, clone)
    assert list(record) == list(validator.TOP_LEVEL_FIELDS)
    assert [surface["surface_id"] for surface in record["frozen_surfaces"]] == list(DIGESTS)
    assert [surface["sha256"] for surface in record["frozen_surfaces"]] == list(DIGESTS.values())


def test_review_transcriptions_are_byte_exact() -> None:
    for relative, expected in REVIEW_DIGESTS.items():
        content = (REPO_ROOT / relative).read_bytes()
        assert hashlib.sha256(content).hexdigest() == expected


@pytest.mark.parametrize(
    ("payload", "needle"),
    [
        (b"schema_version: 1.0.0\nschema_version: 2.0.0\n", "duplicate YAML key"),
        (b"value: &anchor [1]\nother: *anchor\n", "aliases and anchors are forbidden"),
        (b"---\na: 1\n---\nb: 2\n", "exactly one YAML document"),
        (b"!!python/object:builtins.object {}\n", "custom YAML tags are forbidden"),
        (b"value: \x00\n", "NUL"),
        (b"\xff\n", "UTF-8"),
        (b"- not\n- a\n- mapping\n", "root must be a mapping"),
    ],
)
def test_strict_yaml_rejections(validator, tmp_path: Path, payload: bytes, needle: str) -> None:
    path = tmp_path / "record.yaml"
    path.write_bytes(payload)
    with pytest.raises(ValueError, match=needle):
        validator.load_phase0_interface_freeze(path)


def test_strict_yaml_rejects_depth_nodes_and_size(validator, tmp_path: Path) -> None:
    cases = (
        ("depth", ("x: " + "[" * 65 + "0" + "]" * 65 + "\n").encode(), "depth"),
        ("nodes", ("x: [" + ",".join("0" for _ in range(10_001)) + "]\n").encode(), "node"),
        ("size", b"x: " + b"a" * (1024 * 1024) + b"\n", "size"),
    )
    for name, payload, needle in cases:
        path = tmp_path / f"{name}.yaml"
        path.write_bytes(payload)
        with pytest.raises(ValueError, match=needle):
            validator.load_phase0_interface_freeze(path)


@pytest.mark.parametrize(
    ("mutation", "needle"),
    [
        (lambda value: value.pop("freeze_id"), "missing fields"),
        (lambda value: value.__setitem__("unexpected", True), "unknown fields"),
        (lambda value: value.__setitem__("phase", True), "phase must be exact integer 0"),
        (lambda value: value.__setitem__("schema_version", "1.0.1"), "schema_version"),
        (lambda value: value.__setitem__("freeze_id", "phase0-interface-freeze-v2"), "freeze_id"),
        (lambda value: value.__setitem__("canonical_base_commit", "0" * 40), "canonical_base_commit"),
        (lambda value: value.__setitem__("approved_commit", "25882c03da8e3af25eb15b9b6ee04059e827ed43"), "approved_commit"),
        (lambda value: value.__setitem__("approved_tree", "0" * 40), "approved_tree"),
        (lambda value: value.__setitem__("digest_method", "canonical-sha256-file-set-v2"), "digest_method"),
        (lambda value: value.__setitem__("status", "approved"), "status"),
    ],
)
def test_top_level_schema_mutations_are_specific(
    validator,
    tmp_path: Path,
    mutation,
    needle: str,
) -> None:
    clone = _binding_clone(tmp_path)
    record = _assert_valid(validator, clone)
    mutation(record)
    errors = validator.validate_phase0_interface_freeze(clone, record)
    assert any(needle in error for error in errors), errors


@pytest.mark.parametrize(
    ("mutation", "needle"),
    [
        (lambda value: value["frozen_surfaces"].pop(), "exactly three surfaces"),
        (lambda value: value["frozen_surfaces"].append(copy.deepcopy(value["frozen_surfaces"][0])), "exactly three surfaces"),
        (lambda value: value["frozen_surfaces"].reverse(), "surface order"),
        (lambda value: value["frozen_surfaces"][0].__setitem__("direction", "lane_b_to_lane_a"), "direction"),
        (lambda value: value["frozen_surfaces"][0].__setitem__("version_id", "1.0.1"), "version_id"),
        (lambda value: value["frozen_surfaces"][0].__setitem__("sha256", "0" * 64), "sha256"),
        (lambda value: value["frozen_surfaces"][2].__setitem__("sha256", "1e69cdb4" + "0" * 56), "sha256"),
        (lambda value: value["frozen_surfaces"][0]["frozen_paths"].pop(), "frozen_paths"),
        (lambda value: value["frozen_surfaces"][0]["frozen_paths"].append("forged.txt"), "frozen_paths"),
        (lambda value: value["frozen_surfaces"][0]["frozen_paths"].reverse(), "frozen_paths"),
        (lambda value: value["frozen_surfaces"][0]["frozen_paths"].append(value["frozen_surfaces"][0]["frozen_paths"][0]), "frozen_paths"),
        (lambda value: value["frozen_surfaces"][0]["public_modules"].reverse(), "public_modules"),
        (lambda value: value["frozen_surfaces"][0]["public_modules"][0]["public_symbols"].reverse(), "public_symbols"),
        (lambda value: value["frozen_surfaces"][0]["public_modules"][0]["callable_signatures"].reverse(), "callable_signatures"),
        (lambda value: value["frozen_surfaces"][0]["source_documents"].reverse(), "source_documents"),
    ],
)
def test_surface_inventory_mutations_are_specific(
    validator,
    tmp_path: Path,
    mutation,
    needle: str,
) -> None:
    clone = _binding_clone(tmp_path)
    record = _assert_valid(validator, clone)
    mutation(record)
    errors = validator.validate_phase0_interface_freeze(clone, record)
    assert any(needle in error for error in errors), errors


def test_self_consistent_malicious_path_and_digest_are_rejected(validator, tmp_path: Path) -> None:
    clone = _binding_clone(tmp_path)
    record = _assert_valid(validator, clone)
    surface = record["frozen_surfaces"][0]
    surface["frozen_paths"] = ["CONSOLIDATED_PLAN.md"]
    content = _git(clone, "show", f"{APRIME}:CONSOLIDATED_PLAN.md", text=False)
    blob_digest = hashlib.sha256(content).hexdigest()
    surface["sha256"] = hashlib.sha256(
        f"{blob_digest}  CONSOLIDATED_PLAN.md\n".encode()
    ).hexdigest()
    errors = validator.validate_phase0_interface_freeze(clone, record)
    assert any("canonical frozen_paths" in error for error in errors)


@pytest.mark.parametrize(
    ("mutation", "needle"),
    [
        (lambda value: value["reviews"].pop(), "exactly two review records"),
        (lambda value: value["reviews"].reverse(), "review order"),
        (lambda value: value["reviews"][0].__setitem__("lane", "lane_b"), "lane"),
        (lambda value: value["reviews"][0].__setitem__("role", "lane_b_contract_owner"), "role"),
        (lambda value: value["reviews"][0].__setitem__("reviewer", value["reviews"][1]["reviewer"]), "reviewer"),
        (lambda value: value["reviews"][0].__setitem__("subject", value["reviews"][1]["subject"]), "subject"),
        (lambda value: value["reviews"][0].__setitem__("reviewed_commit", "25882c03da8e3af25eb15b9b6ee04059e827ed43"), "reviewed_commit"),
        (lambda value: value["reviews"][0].__setitem__("evidence_path", value["reviews"][1]["evidence_path"]), "evidence_path"),
        (lambda value: value["reviews"][0].__setitem__("evidence_sha256", "0" * 64), "evidence_sha256"),
        (lambda value: value["reviews"][0].__setitem__("decision", "changes_required"), "decision"),
        (lambda value: value["reviews"][0].__setitem__("independent_review", False), "independent_review"),
        (lambda value: value["reviews"][0]["findings"].__setitem__("minor", 1), "findings"),
        (lambda value: value["reviews"][0]["reviewed_digests"].__setitem__("catalog_loaders", "1e69cdb4" + "0" * 56), "reviewed_digests"),
    ],
)
def test_review_record_mutations_are_specific(
    validator,
    tmp_path: Path,
    mutation,
    needle: str,
) -> None:
    clone = _binding_clone(tmp_path)
    record = _assert_valid(validator, clone)
    mutation(record)
    errors = validator.validate_phase0_interface_freeze(clone, record)
    assert any(needle in error for error in errors), errors


@pytest.mark.parametrize(
    ("mutation", "needle"),
    [
        (lambda value: value["amendment_rule"].__setitem__("requires_joint_mini_review", False), "amendment_rule"),
        (lambda value: value["merge_verification"].__setitem__("canonical_merge_commit", "0" * 40), "pending merge"),
        (lambda value: value["merge_verification"].__setitem__("verified_at", "2026-07-21T00:00:00Z"), "pending merge"),
        (lambda value: value["lane_authorization"].__setitem__("authorized", True), "lane_authorization"),
        (lambda value: value["lane_authorization"].__setitem__("reason", "authorized"), "lane_authorization"),
    ],
)
def test_pending_and_amendment_mutations_are_specific(
    validator,
    tmp_path: Path,
    mutation,
    needle: str,
) -> None:
    clone = _binding_clone(tmp_path)
    record = _assert_valid(validator, clone)
    mutation(record)
    errors = validator.validate_phase0_interface_freeze(clone, record)
    assert any(needle in error for error in errors), errors


def test_frozen_worktree_byte_mode_symlink_and_missing_drift_fail(validator, tmp_path: Path) -> None:
    mutations = ("bytes", "mode", "symlink", "missing")
    for mutation in mutations:
        clone = _binding_clone(tmp_path / mutation)
        _assert_valid(validator, clone)
        path = clone / "EvoNN-Shared/src/evonn_shared/canonical.py"
        if mutation == "bytes":
            path.write_bytes(path.read_bytes() + b"# drift\n")
        elif mutation == "mode":
            path.chmod(0o755)
        elif mutation == "symlink":
            path.unlink()
            path.symlink_to("rng.py")
        else:
            path.unlink()
        errors = validator.validate_phase0_interface_freeze(clone)
        assert any("working-tree frozen path" in error for error in errors), (mutation, errors)


def test_shared_contract_drift_invalidates_all_three_surfaces(validator, tmp_path: Path) -> None:
    clone = _binding_clone(tmp_path)
    _assert_valid(validator, clone)
    path = clone / "tests/contracts/test_phase0_shared_interfaces.py"
    path.write_bytes(path.read_bytes() + b"# drift\n")
    errors = validator.validate_phase0_interface_freeze(clone)
    assert sum("tests/contracts/test_phase0_shared_interfaces.py" in error for error in errors) >= 1
    assert all(any(surface in error for error in errors) for surface in DIGESTS)


def test_both_review_bytes_mode_symlink_missing_and_uncommitted_only_fail(
    validator,
    tmp_path: Path,
) -> None:
    for relative in REVIEW_DIGESTS:
        other_relative = next(item for item in REVIEW_DIGESTS if item != relative)
        review_tmp_path = tmp_path / Path(relative).stem
        for mutation in ("bytes", "mode", "symlink", "missing", "uncommitted"):
            clone = _binding_clone(review_tmp_path / mutation)
            _assert_valid(validator, clone)
            path = clone / relative
            if mutation == "bytes":
                path.write_bytes(path.read_bytes() + b"drift\n")
            elif mutation == "mode":
                path.chmod(0o755)
            elif mutation == "symlink":
                path.unlink()
                path.symlink_to(Path(other_relative).name)
            elif mutation == "missing":
                path.unlink()
            else:
                subprocess.run(
                    ["git", "-C", str(clone), "rm", "--quiet", relative],
                    check=True,
                )
                path.write_bytes((REPO_ROOT / relative).read_bytes())
            errors = validator.validate_phase0_interface_freeze(clone)
            assert any("review" in error and relative in error for error in errors), (
                relative,
                mutation,
                errors,
            )


def test_historical_b0_evidence_byte_and_mode_drift_fail(validator, tmp_path: Path) -> None:
    for mutation in ("bytes", "mode"):
        clone = _binding_clone(tmp_path / mutation)
        _assert_valid(validator, clone)
        relative = "governance/b0-status.yaml"
        path = clone / relative
        if mutation == "bytes":
            path.write_bytes(path.read_bytes() + b"# forged\n")
        else:
            path.chmod(0o755)
        _commit(clone, f"mutate historical evidence {mutation}")
        errors = validator.validate_phase0_interface_freeze(clone)
        assert any("historical B0 evidence" in error for error in errors), errors


def test_prohibited_lane_refs_fail_while_unauthorized(validator, tmp_path: Path) -> None:
    clone = _binding_clone(tmp_path)
    _assert_valid(validator, clone)
    subprocess.run(
        ["git", "-C", str(clone), "branch", "agent/p0-lane-a-forbidden"],
        check=True,
    )
    errors = validator.validate_phase0_interface_freeze(clone)
    assert any("prohibited Phase 0 ref" in error for error in errors)


def test_ordinary_descendant_may_change_repairable_binding_file(
    validator,
    tmp_path: Path,
) -> None:
    clone = _binding_clone(tmp_path)
    _assert_valid(validator, clone)
    binding = str(
        _git(
            clone,
            "log",
            "-1",
            "--format=%H",
            "--",
            "governance/phase0-interface-freeze.yaml",
        )
    ).strip()
    repairable_path = clone / "tests/policy/test_repository_governance.py"
    repairable_path.write_bytes(
        repairable_path.read_bytes() + b"\n# repaired on an ordinary descendant\n"
    )
    _commit(clone, "repair repository governance test")

    assert validator.validate_phase0_interface_freeze(clone) == []
    for relative in (*REVIEW_DIGESTS, "governance/phase0-interface-freeze.yaml"):
        assert _git(clone, "rev-parse", f"{binding}:{relative}") == _git(
            clone, "rev-parse", f"HEAD:{relative}"
        )


def test_pending_record_bytes_and_mode_remain_bound(validator, tmp_path: Path) -> None:
    relative = "governance/phase0-interface-freeze.yaml"
    for mutation in ("bytes", "mode"):
        clone = _binding_clone(tmp_path / mutation)
        _assert_valid(validator, clone)
        path = clone / relative
        if mutation == "bytes":
            path.write_bytes(path.read_bytes() + b"# unauthorized pending-state drift\n")
        else:
            path.chmod(0o755)
        _commit(clone, f"mutate pending record {mutation}")

        errors = validator.validate_phase0_interface_freeze(clone)
        assert any(
            "Phase 0 record binding bytes/mode must be preserved at HEAD" in error
            for error in errors
        ), errors


def test_record_mutation_requires_strict_verified_transition(validator, tmp_path: Path) -> None:
    clone = _binding_clone(tmp_path)
    _assert_valid(validator, clone)
    record = _record(clone)
    record["status"] = "merged_verified"
    _write_record(clone, record)
    _commit(clone, "attempt incomplete verified transition")

    errors = validator.validate_phase0_interface_freeze(clone)
    assert any(
        "verified merge_verification must target main with verified status" in error
        for error in errors
    ), errors
    assert any("verified canonical_merge_commit" in error for error in errors), errors
    assert any("verified_at must be strict UTC" in error for error in errors), errors
    assert any("verified lane_authorization" in error for error in errors), errors


def test_binding_commit_requires_exact_parent_and_inventory(validator, tmp_path: Path) -> None:
    clone = _binding_clone(tmp_path)
    _assert_valid(validator, clone)
    (clone / "extra.txt").write_text("extra\n", encoding="utf-8")
    _commit(clone, "unrelated descendant")
    assert validator.validate_phase0_interface_freeze(clone) == []

    record_path = clone / "governance/phase0-interface-freeze.yaml"
    record_path.unlink()
    _commit(clone, "delete binding record")
    errors = validator.validate_phase0_interface_freeze(clone)
    assert any("binding bytes" in error or "record" in error for error in errors)


def test_binding_commit_rejects_wrong_parent_merge_extra_and_missing_paths(validator, tmp_path: Path) -> None:
    canonical = _binding_clone(tmp_path / "canonical")
    record = _record(canonical)
    binding = str(_git(canonical, "log", "-1", "--format=%H", "--", "governance/phase0-interface-freeze.yaml")).strip()
    parent = str(_git(canonical, "rev-parse", f"{binding}^")).strip()
    tree = str(_git(canonical, "rev-parse", f"{binding}^{{tree}}")).strip()
    git = ["git", "-C", str(canonical), "-c", "user.name=policy-test", "-c", "user.email=policy@test"]

    side = str(
        subprocess.check_output([*git, "commit-tree", str(_git(canonical, "rev-parse", f"{parent}^{{tree}}")).strip(), "-p", parent, "-m", "side"], text=True)
    ).strip()
    merge = str(
        subprocess.check_output([*git, "commit-tree", tree, "-p", parent, "-p", side, "-m", "merge binding"], text=True)
    ).strip()
    subprocess.run(["git", "-C", str(canonical), "update-ref", "HEAD", merge], check=True)
    subprocess.run(["git", "-C", str(canonical), "reset", "--hard", "--quiet", merge], check=True)
    errors = validator.validate_phase0_interface_freeze(canonical, record)
    assert any("single-parent direct child" in error for error in errors)

    extra = _binding_clone(tmp_path / "extra")
    binding = str(_git(extra, "log", "-1", "--format=%H", "--", "governance/phase0-interface-freeze.yaml")).strip()
    (extra / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(extra), "add", "unexpected.txt"], check=True)
    amended_tree = str(_git(extra, "write-tree")).strip()
    replacement = str(
        subprocess.check_output(
            ["git", "-C", str(extra), "-c", "user.name=policy-test", "-c", "user.email=policy@test", "commit-tree", amended_tree, "-p", APRIME, "-m", "extra binding path"],
            text=True,
        )
    ).strip()
    subprocess.run(["git", "-C", str(extra), "update-ref", "HEAD", replacement], check=True)
    subprocess.run(["git", "-C", str(extra), "reset", "--hard", "--quiet", replacement], check=True)
    errors = validator.validate_phase0_interface_freeze(extra)
    assert any("changed path inventory" in error for error in errors)

    omitted_path = "tests/policy/test_repository_governance.py"
    missing = _binding_clone(tmp_path / "missing", omit_path=omitted_path)
    errors = validator.validate_phase0_interface_freeze(missing)
    assert any(
        "changed path inventory" in error and omitted_path not in error.split("found ", 1)[-1]
        for error in errors
    ), errors


def test_replacement_graft_shallow_and_override_guards(validator, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    clone = _binding_clone(tmp_path / "guards")
    _assert_valid(validator, clone)

    subprocess.run(["git", "-C", str(clone), "replace", APRIME, "HEAD"], check=True)
    assert any("replacement ref" in error for error in validator.validate_phase0_interface_freeze(clone))
    subprocess.run(["git", "-C", str(clone), "replace", "-d", APRIME], check=True)

    grafts = Path(str(_git(clone, "rev-parse", "--git-path", "info/grafts")).strip())
    if not grafts.is_absolute():
        grafts = clone / grafts
    grafts.parent.mkdir(parents=True, exist_ok=True)
    grafts.write_text("forged graft\n", encoding="utf-8")
    assert any("graft" in error for error in validator.validate_phase0_interface_freeze(clone))
    grafts.unlink()

    monkeypatch.setenv("GIT_SHALLOW_FILE", str(tmp_path / "forged-shallow"))
    assert any("override environment" in error for error in validator.validate_phase0_interface_freeze(clone))

    shallow = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "--quiet", "--depth", "1", f"file://{clone}", str(shallow)],
        check=True,
        capture_output=True,
    )
    monkeypatch.delenv("GIT_SHALLOW_FILE")
    assert any("shallow" in error for error in validator.validate_phase0_interface_freeze(shallow))


def test_plan_and_guide_disagreement_checked_boxes_and_stale_wording_fail(validator, tmp_path: Path) -> None:
    mutations = (
        ("CONSOLIDATED_PLAN.md", "lane_authorization: false", "lane_authorization: true"),
        ("PARALLEL_WORK_GUIDE.md", "status: approved_pending_merge", "status: merged_verified"),
        ("CONSOLIDATED_PLAN.md", "- [ ] **WP-0.1", "- [x] **WP-0.1"),
        ("PARALLEL_WORK_GUIDE.md", "approved_pending_merge", "freeze itself is still pending"),
    )
    for index, (relative, old, new) in enumerate(mutations):
        clone = _binding_clone(tmp_path / str(index))
        _assert_valid(validator, clone)
        path = clone / relative
        text = path.read_text(encoding="utf-8")
        assert old in text
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        errors = validator.validate_phase0_interface_freeze(clone)
        assert any("plan/guide" in error or "WP-0" in error for error in errors), errors


def test_cli_is_cwd_independent_strict_and_traceback_free(tmp_path: Path) -> None:
    clone = _binding_clone(tmp_path / "clone")
    validator_path = clone / "scripts/policy/validate_phase0_interface_freeze.py"
    result = subprocess.run(
        [sys.executable, str(validator_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == "Phase 0 interface freeze policy: PASS\n"
    assert result.stderr == ""

    strict = subprocess.run(
        [sys.executable, str(validator_path), "unexpected"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert strict.returncode == 2
    assert "Traceback" not in strict.stdout + strict.stderr

    (clone / "governance/phase0-interface-freeze.yaml").write_bytes(b"schema_version: [\n")
    failed = subprocess.run(
        [sys.executable, str(validator_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert failed.returncode == 1
    lines = [line.removeprefix("ERROR: ") for line in failed.stdout.splitlines()]
    assert lines == sorted(set(lines))
    assert "Traceback" not in failed.stdout + failed.stderr
