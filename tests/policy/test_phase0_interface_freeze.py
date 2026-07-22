from __future__ import annotations

import copy
import hashlib
import importlib.util
import os
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
CANONICAL_ORIGIN = "git@github.com:TimoKruth/EvoNN-Research.git"
A_DOUBLE_PRIME = "25352a4bd7c33b73077d9f9be231b2bb1b48109f"
A_DOUBLE_PRIME_TREE = "78a72f1a2229d9e94cd78512be0585f08b2a5895"
V2_DIGESTS = {
    "canonical_digest_rng": "1806b230d6d218154898f5db8eae4089ffda07bfdf8c395d3523946a2f9fb7bc",
    "export_models": "f4199dccbab802edd8f6c671286dca8005434ef54b50a0f678e62399784a5c72",
    "catalog_loaders": "3b804f54e14749e3f0ae1bcb06b0b8415f5954a312c3eaf9057001ea4832f2cc",
}
V2_REVIEW_IDENTITIES = (
    {
        "lane": "lane_a",
        "role": "lane_a_contract_owner",
        "reviewer": "phase0-lane-a-producer-a2-reviewer-20260723",
        "subject": "phase0-frozen-surface-a-double-prime-lane-a-producer-review",
        "evidence_path": "reviews/2026-07-23-phase0-lane-a-producer-a2-review.md",
        "evidence_sha256": "e546bb678bddbec18a705e6484f54de11fcfcece3b099b9f18b095c540cb741d",
    },
    {
        "lane": "lane_b",
        "role": "lane_b_contract_owner",
        "reviewer": "phase0-lane-b-consumer-a2-reviewer-20260723",
        "subject": "phase0-frozen-surface-a-double-prime-lane-b-consumer-review",
        "evidence_path": "reviews/2026-07-23-phase0-lane-b-consumer-a2-review.md",
        "evidence_sha256": "171ff311c5a6f61e1f71bbd2d913f6c221bf4657ec169400117113a1c16039af",
    },
)
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
BINDING_MODES = {
    relative: "100755" if relative == "scripts/ci/b0-policy-checks.sh" else "100644"
    for relative in ALLOWED_BINDING_PATHS
}
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


def _historical_binding(repository: Path = REPO_ROOT) -> str:
    revisions = [
        revision
        for revision in str(
            _git(
                repository,
                "log",
                "--diff-filter=A",
                "--format=%H",
                "HEAD",
                "--",
                "governance/phase0-interface-freeze.yaml",
            )
        ).splitlines()
        if revision
    ]
    assert len(revisions) == 1, revisions
    binding = revisions[0]
    assert str(_git(repository, "rev-parse", f"{binding}^")).strip() == APRIME
    changed = {
        relative
        for relative in str(
            _git(
                repository,
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                binding,
            )
        ).splitlines()
        if relative
    }
    assert changed == set(ALLOWED_BINDING_PATHS)
    return binding


def _binding_clone(tmp_path: Path, *, omit_path: str | None = None) -> Path:
    binding_source = _historical_binding()
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
        entry = str(_git(REPO_ROOT, "ls-tree", binding_source, "--", relative)).strip().split()
        assert entry[:2] == [BINDING_MODES[relative], "blob"], (relative, entry)
        destination = clone / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(_git(REPO_ROOT, "show", f"{binding_source}:{relative}", text=False))
        destination.chmod(0o755 if BINDING_MODES[relative] == "100755" else 0o644)
    binding = _commit(clone, "synthetic Phase 0 binding")
    assert str(_git(clone, "rev-parse", f"{binding}^")).strip() == APRIME
    subprocess.run(
        ["git", "-C", str(clone), "remote", "set-url", "origin", CANONICAL_ORIGIN],
        check=True,
        capture_output=True,
    )
    return clone


def _current_clone(tmp_path: Path) -> Path:
    clone = tmp_path / "current-clone"
    subprocess.run(
        ["git", "clone", "--quiet", "--no-local", str(REPO_ROOT), str(clone)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(clone), "checkout", "--quiet", "--detach", "HEAD"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(clone), "remote", "set-url", "origin", CANONICAL_ORIGIN],
        check=True,
        capture_output=True,
    )
    return clone


def _record(repository: Path) -> dict:
    loaded = yaml.safe_load((repository / "governance/phase0-interface-freeze.yaml").read_bytes())
    assert isinstance(loaded, dict)
    return loaded


def _v2_record(repository: Path) -> dict:
    record = copy.deepcopy(_record(repository))
    record["freeze_id"] = "phase0-interface-freeze-v2"
    record["supersedes"] = "phase0-interface-freeze-v1"
    record["approved_commit"] = A_DOUBLE_PRIME
    record["approved_tree"] = A_DOUBLE_PRIME_TREE
    for surface in record["frozen_surfaces"]:
        surface["sha256"] = V2_DIGESTS[surface["surface_id"]]
    reviews = []
    for identity in V2_REVIEW_IDENTITIES:
        reviews.append(
            {
                **identity,
                "reviewed_commit": A_DOUBLE_PRIME,
                "reviewed_tree": A_DOUBLE_PRIME_TREE,
                "reviewed_digests": copy.deepcopy(V2_DIGESTS),
                "independent_review": True,
                "decision": "approved",
                "findings": {
                    "critical": 0,
                    "important": 0,
                    "specification": 0,
                    "frozen_correctness": 0,
                    "minor": 0,
                },
            }
        )
    record["reviews"] = reviews
    record["amendment_rule"]["next_record_must_supersede"] = (
        "phase0-interface-freeze-v1"
    )
    return record


def _assert_valid(validator, repository: Path) -> dict:
    record = _record(repository)
    assert validator.validate_phase0_interface_freeze(repository, record) == []
    return record


def _write_record(repository: Path, record: dict) -> None:
    (repository / "governance/phase0-interface-freeze.yaml").write_text(
        yaml.safe_dump(record, sort_keys=False),
        encoding="utf-8",
    )


def _v2_pending_marker() -> str:
    return f"""```yaml
freeze_id: phase0-interface-freeze-v2
governance_record: governance/phase0-interface-freeze.yaml
approved_commit: {A_DOUBLE_PRIME}
approved_tree: {A_DOUBLE_PRIME_TREE}
digests:
  canonical_digest_rng: {V2_DIGESTS["canonical_digest_rng"]}
  export_models: {V2_DIGESTS["export_models"]}
  catalog_loaders: {V2_DIGESTS["catalog_loaders"]}
reviews:
  - {V2_REVIEW_IDENTITIES[0]["evidence_path"]}
  - {V2_REVIEW_IDENTITIES[1]["evidence_path"]}
status: approved_pending_merge
lane_authorization: false
lane_branches: none
next_sequence: protected PR merge → verify canonical merge → attestation → only then create lane/integration branches
joint_boundary: WP-0.10 and the Phase 0 exit remain joint
```"""


def _v2_verified_marker(merge_commit: str, verified_at: str) -> str:
    return f"""```yaml
freeze_id: phase0-interface-freeze-v2
governance_record: governance/phase0-interface-freeze.yaml
approved_commit: {A_DOUBLE_PRIME}
approved_tree: {A_DOUBLE_PRIME_TREE}
digests:
  canonical_digest_rng: {V2_DIGESTS["canonical_digest_rng"]}
  export_models: {V2_DIGESTS["export_models"]}
  catalog_loaders: {V2_DIGESTS["catalog_loaders"]}
reviews:
  - {V2_REVIEW_IDENTITIES[0]["evidence_path"]}
  - {V2_REVIEW_IDENTITIES[1]["evidence_path"]}
status: merged_verified
lane_authorization: true
canonical_merge_commit: {merge_commit}
verified_at: {verified_at}
lane_branch_creation: authorized
authorization_effective_after: separate authorization attestation is merged
joint_boundary: WP-0.10 and the Phase 0 exit remain joint
```"""


def _verified_marker(merge_commit: str, verified_at: str) -> str:
    return f"""```yaml
freeze_id: phase0-interface-freeze-v1
governance_record: governance/phase0-interface-freeze.yaml
approved_commit: b720ea6461c970e3875f8ef735e3e63cf680b660
approved_tree: f1c5742c2581d270af05714b5ef8514c3f49d996
digests:
  canonical_digest_rng: 1806b230d6d218154898f5db8eae4089ffda07bfdf8c395d3523946a2f9fb7bc
  export_models: b18bcdcc8fd8e4cbb6d9dfb1f82c0d998a1f3fedce927991d79388139c2275fc
  catalog_loaders: 81cf090ba61b1bfb1bdbf4a5e74c9fe46bfe34f36dcc5c44f72cd4f5cb33edc5
reviews:
  - reviews/2026-07-21-phase0-lane-a-producer-review.md
  - reviews/2026-07-21-phase0-lane-b-consumer-review.md
status: merged_verified
lane_authorization: true
canonical_merge_commit: {merge_commit}
verified_at: {verified_at}
lane_branch_creation: authorized
authorization_effective_after: separate authorization attestation is merged
joint_boundary: WP-0.10 and the Phase 0 exit remain joint
```"""


PENDING_PLAN_B0_EXIT = """**Exit (contract evidence):** Gate B0 is closed by the anchored schema-2
report and closed status evidence. Binding C has recorded the approved Phase 0
interface freeze in `approved_pending_merge` state. Lane and integration work
remain unauthorized until the protected freeze PR merge is verified on
canonical `origin/main` and a separate authorization attestation is merged."""
VERIFIED_PLAN_B0_EXIT = """**Exit (contract evidence):** Gate B0 is closed by the anchored schema-2
report and closed status evidence. Binding C's Phase 0 interface freeze is
`merged_verified`. Lane and integration branch creation is authorized because
the protected freeze PR merge is verified on canonical `origin/main` and the
separate authorization attestation is merged. No lane branch is asserted to
exist by this record."""
PENDING_PLAN_PHASE0_FREEZE = """*Interface freeze:* canonical-encoding/digest API (A→B for checkpoint
checksums), export model shapes (A→B for RunWorkspace fixtures), catalog
loader signatures (B→A for validators). The co-signed freeze is approved and
recorded, but lane creation remains merge-gated."""
VERIFIED_PLAN_PHASE0_FREEZE = """*Interface freeze:* canonical-encoding/digest API (A→B for checkpoint
checksums), export model shapes (A→B for RunWorkspace fixtures), catalog
loader signatures (B→A for validators). The co-signed freeze is approved,
recorded, merged, verified, and separately attested; lane creation is authorized
from the attested canonical history."""
PENDING_PLAN_NEXT_ACTIONS = """The durable governance record is `governance/phase0-interface-freeze.yaml` with
`status: approved_pending_merge` and `lane_authorization: false`. No Phase 0
lane or integration branch exists. The required sequence is
protected PR merge → verify canonical merge → attestation → only then create the Phase 0 lane and integration branches. WP-0.10 and the Phase 0 exit remain joint. No Phase 0
implementation work is authorized before that sequence completes."""
VERIFIED_PLAN_NEXT_ACTIONS = """The durable governance record is `governance/phase0-interface-freeze.yaml` with
`status: merged_verified` and `lane_authorization: true`. No Phase 0 lane or
integration branch is recorded as existing. The protected freeze PR merge and
separate authorization attestation are merged on canonical `origin/main`, so
Phase 0 lane and integration branches may now be created from the attested
canonical history. WP-0.10 and the Phase 0 exit remain joint."""
PENDING_GUIDE_AUTHORIZATION = """The Phase 0 interfaces are now co-signed and durably recorded, but this does
not authorize immediate parallel implementation. The freeze remains merge-gated:
no Phase 0 lane branch exists, and no lane or integration branch may be created
until the protected freeze PR is merged, the actual canonical merge is verified,
and a later attestation records that verification."""
VERIFIED_GUIDE_AUTHORIZATION = """The Phase 0 interfaces are co-signed, the protected freeze PR merge is verified,
and the separate authorization attestation is merged on canonical `origin/main`.
Phase 0 lane and integration branches may now be created from the attested
canonical history, but the authorization record does not claim that any lane
branch already exists. WP-0.10 and the Phase 0 exit remain joint."""


def _replace_marker(repository: Path, marker: str) -> None:
    for relative in ("CONSOLIDATED_PLAN.md", "PARALLEL_WORK_GUIDE.md"):
        _replace_document_marker(repository, relative, marker)


def _replace_authorization_prose(repository: Path) -> None:
    replacements = {
        "CONSOLIDATED_PLAN.md": (
            (PENDING_PLAN_B0_EXIT, VERIFIED_PLAN_B0_EXIT),
            (PENDING_PLAN_PHASE0_FREEZE, VERIFIED_PLAN_PHASE0_FREEZE),
            (PENDING_PLAN_NEXT_ACTIONS, VERIFIED_PLAN_NEXT_ACTIONS),
        ),
        "PARALLEL_WORK_GUIDE.md": (
            (PENDING_GUIDE_AUTHORIZATION, VERIFIED_GUIDE_AUTHORIZATION),
        ),
    }
    for relative, document_replacements in replacements.items():
        path = repository / relative
        text = path.read_text(encoding="utf-8")
        for pending, verified in document_replacements:
            assert text.count(pending) == 1, (relative, pending)
            text = text.replace(pending, verified, 1)
        path.write_text(text, encoding="utf-8")


def _replace_document_marker(repository: Path, relative: str, marker: str) -> None:
    path = repository / relative
    text = path.read_text(encoding="utf-8")
    before, remainder = text.split("<!-- phase0-interface-freeze:begin -->", 1)
    _, after = remainder.split("<!-- phase0-interface-freeze:end -->", 1)
    path.write_text(
        before
        + "<!-- phase0-interface-freeze:begin -->\n"
        + marker
        + "\n<!-- phase0-interface-freeze:end -->"
        + after,
        encoding="utf-8",
    )


def _document_marker(repository: Path, relative: str = "CONSOLIDATED_PLAN.md") -> str:
    text = (repository / relative).read_text(encoding="utf-8")
    return (
        text.split("<!-- phase0-interface-freeze:begin -->", 1)[1]
        .split("<!-- phase0-interface-freeze:end -->", 1)[0]
        .strip()
    )


def _tree_with_extra_path(repository: Path, relative: str) -> str:
    path = repository / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("SYNTHESIZED = True\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", relative], check=True)
    tree = str(_git(repository, "write-tree")).strip()
    subprocess.run(
        ["git", "-C", str(repository), "reset", "--hard", "--quiet", "HEAD"],
        check=True,
    )
    return tree


def _prospective_freeze_merge(
    repository: Path,
    *,
    approved_commit: str = APRIME,
) -> tuple[str, str]:
    feature_parent = str(_git(repository, "rev-parse", "HEAD")).strip()
    approved_tree = str(
        _git(repository, "rev-parse", f"{approved_commit}^{{tree}}")
    ).strip()
    feature_tree = str(
        _git(repository, "rev-parse", f"{feature_parent}^{{tree}}")
    ).strip()
    git = [
        "git",
        "-C",
        str(repository),
        "-c",
        "user.name=policy-test",
        "-c",
        "user.email=policy@test",
    ]
    first_parent = subprocess.check_output(
        [
            *git,
            "commit-tree",
            approved_tree,
            "-p",
            approved_commit,
            "-m",
            "canonical main",
        ],
        text=True,
    ).strip()
    merge = subprocess.check_output(
        [
            *git,
            "commit-tree",
            feature_tree,
            "-p",
            first_parent,
            "-p",
            feature_parent,
            "-m",
            "prospective freeze merge",
        ],
        text=True,
    ).strip()
    subprocess.run(
        ["git", "-C", str(repository), "reset", "--hard", "--quiet", merge],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "update-ref",
            "refs/remotes/origin/main",
            first_parent,
        ],
        check=True,
        capture_output=True,
    )
    return first_parent, feature_parent


def _verified_transition(
    repository: Path,
    *,
    approved_commit: str = APRIME,
    include_binding_in_first_parent: bool = False,
    include_binding_in_feature_parent: bool = True,
    merge_on_first_parent: bool = True,
    freeze_merge_extra_path: str | None = None,
    attestation_merge_extra_path: str | None = None,
    attestation_first_parent_extra_path: str | None = None,
    publish_attestation: bool = True,
) -> tuple[str, str]:
    binding = _historical_binding(repository)
    feature_tip = str(_git(repository, "rev-parse", "HEAD")).strip()
    git = [
        "git",
        "-C",
        str(repository),
        "-c",
        "user.name=policy-test",
        "-c",
        "user.email=policy@test",
    ]
    first_parent_base = binding if include_binding_in_first_parent else approved_commit
    first_parent_tree = str(_git(repository, "rev-parse", f"{first_parent_base}^{{tree}}")).strip()
    first_parent = subprocess.check_output(
        [*git, "commit-tree", first_parent_tree, "-p", first_parent_base, "-m", "canonical main parent"],
        text=True,
    ).strip()
    if include_binding_in_feature_parent:
        feature_parent = feature_tip
    else:
        feature_parent = subprocess.check_output(
            [
                *git,
                "commit-tree",
                first_parent_tree,
                "-p",
                approved_commit,
                "-m",
                "unrelated feature parent",
            ],
            text=True,
        ).strip()
    merge_tree = str(_git(repository, "rev-parse", f"{feature_tip}^{{tree}}")).strip()
    if freeze_merge_extra_path is not None:
        merge_tree = _tree_with_extra_path(repository, freeze_merge_extra_path)
    merge_commit = subprocess.check_output(
        [
            *git,
            "commit-tree",
            merge_tree,
            "-p",
            first_parent,
            "-p",
            feature_parent,
            "-m",
            "canonical protected freeze merge",
        ],
        text=True,
    ).strip()
    base_for_attestation = merge_commit if merge_on_first_parent else feature_tip
    subprocess.run(
        ["git", "-C", str(repository), "reset", "--hard", "--quiet", base_for_attestation],
        check=True,
        capture_output=True,
    )
    verified_at = "2026-07-21T12:34:56Z"
    record = _record(repository)
    record["status"] = "merged_verified"
    record["merge_verification"] = {
        "target_branch": "main",
        "status": "verified",
        "canonical_merge_commit": merge_commit,
        "verified_at": verified_at,
    }
    record["lane_authorization"] = {
        "authorized": True,
        "reason": "freeze_pull_request_merged_and_canonical_merge_verified",
    }
    _write_record(repository, record)
    marker = (
        _v2_verified_marker(merge_commit, verified_at)
        if record.get("freeze_id") == "phase0-interface-freeze-v2"
        else _verified_marker(merge_commit, verified_at)
    )
    _replace_marker(repository, marker)
    _replace_authorization_prose(repository)
    transition = _commit(repository, "attest canonical freeze merge")
    transition_tree = str(_git(repository, "rev-parse", f"{transition}^{{tree}}")).strip()
    if attestation_merge_extra_path is not None:
        transition_tree = _tree_with_extra_path(repository, attestation_merge_extra_path)
    carrier_first_parent = merge_commit
    if attestation_first_parent_extra_path is not None:
        transition_tree = _tree_with_extra_path(
            repository,
            attestation_first_parent_extra_path,
        )
        subprocess.run(
            ["git", "-C", str(repository), "reset", "--hard", "--quiet", merge_commit],
            check=True,
            capture_output=True,
        )
        first_parent_tree = _tree_with_extra_path(
            repository,
            attestation_first_parent_extra_path,
        )
        carrier_first_parent = subprocess.check_output(
            [
                *git,
                "commit-tree",
                first_parent_tree,
                "-p",
                merge_commit,
                "-m",
                "unauthorized pre-attestation mainline implementation",
            ],
            text=True,
        ).strip()
    attestation_merge = subprocess.check_output(
        [
            *git,
            "commit-tree",
            transition_tree,
            "-p",
            carrier_first_parent,
            "-p",
            transition,
            "-m",
            "merge authorization attestation",
        ],
        text=True,
    ).strip()
    subprocess.run(
        ["git", "-C", str(repository), "reset", "--hard", "--quiet", attestation_merge],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "update-ref",
            "refs/remotes/origin/main",
            attestation_merge if publish_attestation else merge_commit,
        ],
        check=True,
        capture_output=True,
    )
    return binding, merge_commit


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
    _write_record(clone, record)
    _commit(clone, "commit record mutation")
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
    _write_record(clone, record)
    _commit(clone, "commit record mutation")
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
    _write_record(clone, record)
    _commit(clone, "commit malicious record mutation")
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
    _write_record(clone, record)
    _commit(clone, "commit record mutation")
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
    _write_record(clone, record)
    _commit(clone, "commit record mutation")
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
        assert any("frozen path" in error and "worktree" in error for error in errors), (
            mutation,
            errors,
        )


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


@pytest.mark.parametrize(
    "relative",
    [
        ".superpowers/sdd/task-6-report.md",
        "governance/authority-provenance.yaml",
        "governance/b0-report.json",
        "governance/b0-status.yaml",
        "governance/evidence/b0/hosted/linux-runtime-probe.json",
        "governance/evidence/b0/hosted/macos-runtime-probe.json",
        "reviews/2026-07-19-b0-closure-review.md",
    ],
)
@pytest.mark.parametrize("mutation", ["bytes", "mode"])
def test_historical_b0_evidence_byte_and_mode_drift_fail(
    validator,
    tmp_path: Path,
    relative: str,
    mutation: str,
) -> None:
    clone = _binding_clone(tmp_path)
    _assert_valid(validator, clone)
    path = clone / relative
    if mutation == "bytes":
        path.write_bytes(path.read_bytes() + b"# forged\n")
    else:
        path.chmod(0o755)
    _commit(clone, f"mutate historical evidence {mutation}")
    errors = validator.validate_phase0_interface_freeze(clone)
    assert any(
        "historical B0 evidence" in error and relative in error
        for error in errors
    ), errors


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


def test_v2_pending_supersession_preserves_historical_binding_c(
    validator,
    tmp_path: Path,
) -> None:
    clone = _current_clone(tmp_path)
    binding_c = _historical_binding(clone)
    binding_c_record = str(
        _git(
            clone,
            "rev-parse",
            f"{binding_c}:governance/phase0-interface-freeze.yaml",
        )
    ).strip()
    record = _v2_record(clone)
    _write_record(clone, record)
    _replace_marker(clone, _v2_pending_marker())
    binding_d = _commit(clone, "bind pending Phase 0 freeze v2")

    assert str(
        _git(
            clone,
            "rev-parse",
            f"{binding_c}:governance/phase0-interface-freeze.yaml",
        )
    ).strip() == binding_c_record
    assert str(_git(clone, "rev-parse", f"{binding_d}^")).strip() != binding_c
    assert validator.validate_phase0_interface_freeze(clone) == []


def test_v2_rejects_historical_review_rewrite_before_supersession_binding(
    validator,
    tmp_path: Path,
) -> None:
    clone = _current_clone(tmp_path)
    relative = next(iter(REVIEW_DIGESTS))
    path = clone / relative
    path.write_bytes(path.read_bytes() + b"\nforged historical review evidence\n")
    _commit(clone, "rewrite historical reciprocal review evidence")

    record = _v2_record(clone)
    _write_record(clone, record)
    _replace_marker(clone, _v2_pending_marker())
    _commit(clone, "bind pending Phase 0 freeze v2")

    errors = validator.validate_phase0_interface_freeze(clone)

    assert any(
        "historical reciprocal review evidence" in error and relative in error
        for error in errors
    ), errors


def test_v2_exact_prospective_freeze_merge_uses_supersession_binding(
    validator,
    tmp_path: Path,
) -> None:
    clone = _current_clone(tmp_path)
    record = _v2_record(clone)
    _write_record(clone, record)
    _replace_marker(clone, _v2_pending_marker())
    _commit(clone, "bind pending Phase 0 freeze v2")
    _prospective_freeze_merge(clone, approved_commit=A_DOUBLE_PRIME)

    assert validator.validate_phase0_interface_freeze(clone) == []


def test_v2_verified_transition_uses_supersession_binding(
    validator,
    tmp_path: Path,
) -> None:
    clone = _current_clone(tmp_path)
    record = _v2_record(clone)
    _write_record(clone, record)
    _replace_marker(clone, _v2_pending_marker())
    _commit(clone, "bind pending Phase 0 freeze v2")
    _verified_transition(clone, approved_commit=A_DOUBLE_PRIME)

    assert validator.validate_phase0_interface_freeze(clone) == []


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


def test_verified_transition_requires_canonical_pending_binding_record(
    validator,
    tmp_path: Path,
) -> None:
    clone = _binding_clone(tmp_path)
    repaired_plan = (clone / "CONSOLIDATED_PLAN.md").read_bytes()
    binding = _historical_binding(clone)
    subprocess.run(
        ["git", "-C", str(clone), "reset", "--hard", "--quiet", binding],
        check=True,
    )
    record = _record(clone)
    record["lane_authorization"] = {
        "authorized": True,
        "reason": "noncanonical-binding-state",
    }
    _write_record(clone, record)
    git = [
        "git",
        "-C",
        str(clone),
        "-c",
        "user.name=policy-test",
        "-c",
        "user.email=policy@test",
    ]
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "--quiet", "--amend", "--no-edit"], check=True)
    (clone / "CONSOLIDATED_PLAN.md").write_bytes(repaired_plan)
    _commit(clone, "restore current active plan repair")
    _verified_transition(clone)

    errors = validator.validate_phase0_interface_freeze(clone)

    assert any("canonical pending record blob" in error for error in errors), errors


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
    repairable = clone / "tests/policy/test_repository_governance.py"
    repairable.write_bytes(repairable.read_bytes() + b"# ordinary repair\n")
    _commit(clone, "repair policy test descendant")
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


def test_exact_prospective_freeze_merge_is_valid(
    validator,
    tmp_path: Path,
) -> None:
    clone = _binding_clone(tmp_path)
    first_parent, feature_parent = _prospective_freeze_merge(clone)

    head_parents = str(_git(clone, "rev-list", "--parents", "-n", "1", "HEAD")).split()
    assert head_parents[1:] == [first_parent, feature_parent]
    assert str(_git(clone, "rev-parse", "refs/remotes/origin/main")).strip() == first_parent
    assert validator.validate_phase0_interface_freeze(clone) == []


def test_exact_prospective_attestation_merge_is_valid(
    validator,
    tmp_path: Path,
) -> None:
    clone = _binding_clone(tmp_path)
    _, merge_commit = _verified_transition(clone, publish_attestation=False)

    carrier = str(_git(clone, "rev-parse", "HEAD")).strip()
    carrier_parents = str(
        _git(clone, "rev-list", "--parents", "-n", "1", carrier)
    ).split()
    assert carrier_parents[1] == merge_commit
    assert carrier_parents[2] == str(_git(clone, "rev-parse", "HEAD^2")).strip()
    assert str(_git(clone, "rev-parse", "refs/remotes/origin/main")).strip() == merge_commit
    assert validator.validate_phase0_interface_freeze(clone) == []


def test_complete_verified_transition_is_valid(validator, tmp_path: Path) -> None:
    clone = _binding_clone(tmp_path)
    _, merge_commit = _verified_transition(clone)

    assert str(_git(clone, "rev-parse", "refs/remotes/origin/main")).strip() == str(
        _git(clone, "rev-parse", "HEAD")
    ).strip()
    assert merge_commit in str(_git(clone, "rev-list", "--first-parent", "refs/remotes/origin/main")).splitlines()
    assert validator.validate_phase0_interface_freeze(clone) == []


def test_verified_transition_allows_origin_main_to_advance_beyond_head(
    validator,
    tmp_path: Path,
) -> None:
    clone = _binding_clone(tmp_path)
    _verified_transition(clone)
    carrier = str(_git(clone, "rev-parse", "HEAD")).strip()
    carrier_tree = str(_git(clone, "rev-parse", f"{carrier}^{{tree}}")).strip()
    git = [
        "git",
        "-C",
        str(clone),
        "-c",
        "user.name=policy-test",
        "-c",
        "user.email=policy@test",
    ]
    advanced_origin = subprocess.check_output(
        [*git, "commit-tree", carrier_tree, "-p", carrier, "-m", "advance canonical main"],
        text=True,
    ).strip()
    subprocess.run(
        ["git", "-C", str(clone), "update-ref", "refs/remotes/origin/main", advanced_origin],
        check=True,
        capture_output=True,
    )

    assert str(_git(clone, "rev-parse", "HEAD")).strip() == carrier
    assert validator.validate_phase0_interface_freeze(clone) == []


def test_verified_transition_rejects_head_before_attestation_carrier(
    validator,
    tmp_path: Path,
) -> None:
    clone = _binding_clone(tmp_path)
    _verified_transition(clone)
    carrier = str(_git(clone, "rev-parse", "HEAD")).strip()
    transition = str(_git(clone, "rev-parse", f"{carrier}^2")).strip()
    subprocess.run(
        ["git", "-C", str(clone), "reset", "--hard", "--quiet", transition],
        check=True,
        capture_output=True,
    )

    errors = validator.validate_phase0_interface_freeze(clone)

    assert any(
        "authorization attestation carrier must be present on current HEAD first-parent history"
        in error
        for error in errors
    ), errors


def test_verified_transition_allows_implementation_descendants_after_carrier(
    validator,
    tmp_path: Path,
) -> None:
    clone = _binding_clone(tmp_path)
    _verified_transition(clone)
    implementation = clone / "EvoNN-Shared/src/evonn_shared/post_attestation.py"
    implementation.write_text("AUTHORIZED = True\n", encoding="utf-8")
    _commit(clone, "implement after authorization attestation")

    assert validator.validate_phase0_interface_freeze(clone) == []


def test_verified_transition_rejects_pre_attestation_first_parent_bypass(
    validator,
    tmp_path: Path,
) -> None:
    clone = _binding_clone(tmp_path)
    relative = "EvoNN-Shared/src/evonn_shared/pre_attestation.py"
    _verified_transition(
        clone,
        attestation_first_parent_extra_path=relative,
    )

    errors = validator.validate_phase0_interface_freeze(clone)

    assert any(
        "authorization attestation merge first parent must be the canonical freeze merge" in error
        and relative not in error
        for error in errors
    ), errors


def test_verified_transition_rejects_carrier_only_on_head_second_parent(
    validator,
    tmp_path: Path,
) -> None:
    clone = _binding_clone(tmp_path)
    _, merge_commit = _verified_transition(clone)
    carrier = str(_git(clone, "rev-parse", "HEAD")).strip()
    relative = "EvoNN-Shared/src/evonn_shared/pre_carrier_mainline.py"
    subprocess.run(
        ["git", "-C", str(clone), "reset", "--hard", "--quiet", merge_commit],
        check=True,
        capture_output=True,
    )
    implementation = clone / relative
    implementation.parent.mkdir(parents=True, exist_ok=True)
    implementation.write_text("UNAUTHORIZED = True\n", encoding="utf-8")
    first_parent = _commit(clone, "implement before authorization carrier")
    subprocess.run(
        ["git", "-C", str(clone), "reset", "--hard", "--quiet", carrier],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(clone), "checkout", first_parent, "--", relative],
        check=True,
        capture_output=True,
    )
    combined_tree = str(_git(clone, "write-tree")).strip()
    git = [
        "git",
        "-C",
        str(clone),
        "-c",
        "user.name=policy-test",
        "-c",
        "user.email=policy@test",
    ]
    head = subprocess.check_output(
        [
            *git,
            "commit-tree",
            combined_tree,
            "-p",
            first_parent,
            "-p",
            carrier,
            "-m",
            "merge carrier behind unauthorized mainline implementation",
        ],
        text=True,
    ).strip()
    subprocess.run(
        ["git", "-C", str(clone), "reset", "--hard", "--quiet", head],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(clone), "update-ref", "refs/remotes/origin/main", carrier],
        check=True,
        capture_output=True,
    )

    errors = validator.validate_phase0_interface_freeze(clone)

    assert any(
        "authorization attestation carrier must be present on current HEAD first-parent history"
        in error
        for error in errors
    ), errors


def test_verified_transition_requires_canonical_origin_and_remote_attestation(
    validator,
    tmp_path: Path,
) -> None:
    local_only = _binding_clone(tmp_path / "local-only")
    _, merge_commit = _verified_transition(local_only)
    transition = str(_git(local_only, "rev-parse", "HEAD^2")).strip()
    subprocess.run(
        ["git", "-C", str(local_only), "reset", "--hard", "--quiet", transition],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(local_only), "update-ref", "refs/remotes/origin/main", merge_commit],
        check=True,
    )
    errors = validator.validate_phase0_interface_freeze(local_only)
    assert any("origin/main" in error or "attestation" in error for error in errors), errors

    fast_forward = _binding_clone(tmp_path / "fast-forward")
    _verified_transition(fast_forward)
    transition = str(_git(fast_forward, "rev-parse", "HEAD^2")).strip()
    subprocess.run(
        ["git", "-C", str(fast_forward), "reset", "--hard", "--quiet", transition],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(fast_forward), "update-ref", "refs/remotes/origin/main", transition],
        check=True,
    )
    errors = validator.validate_phase0_interface_freeze(fast_forward)
    assert any("attestation merge" in error for error in errors), errors

    noncanonical = _binding_clone(tmp_path / "noncanonical")
    _verified_transition(noncanonical)
    subprocess.run(
        ["git", "-C", str(noncanonical), "remote", "set-url", "origin", "https://example.com/forged/repo.git"],
        check=True,
    )
    errors = validator.validate_phase0_interface_freeze(noncanonical)
    assert any("canonical origin" in error for error in errors), errors


def test_verified_merge_requires_exact_feature_parent_roles(validator, tmp_path: Path) -> None:
    first_parent_contains_binding = _binding_clone(tmp_path / "first-parent")
    _verified_transition(
        first_parent_contains_binding,
        include_binding_in_first_parent=True,
        include_binding_in_feature_parent=False,
    )
    errors = validator.validate_phase0_interface_freeze(first_parent_contains_binding)
    assert any("first parent" in error for error in errors), errors
    assert any("feature parent" in error for error in errors), errors

    absent = _binding_clone(tmp_path / "absent")
    _verified_transition(absent, include_binding_in_feature_parent=False)
    errors = validator.validate_phase0_interface_freeze(absent)
    assert any("feature parent" in error for error in errors), errors


@pytest.mark.parametrize(
    ("keyword", "relative"),
    [
        ("freeze", "EvoNN-Shared/src/evonn_shared/preauthorization.py"),
        ("attestation", "EvoNN-Shared/src/evonn_shared/authorization_merge_extra.py"),
    ],
)
def test_verified_merges_cannot_synthesize_paths_absent_from_feature_parents(
    validator,
    tmp_path: Path,
    keyword: str,
    relative: str,
) -> None:
    clone = _binding_clone(tmp_path)
    arguments = (
        {"freeze_merge_extra_path": relative}
        if keyword == "freeze"
        else {"attestation_merge_extra_path": relative}
    )
    _verified_transition(clone, **arguments)

    errors = validator.validate_phase0_interface_freeze(clone)

    assert any(keyword in error and "merge tree" in error and relative in error for error in errors), errors


def test_verified_transition_requires_declared_merge_as_direct_first_parent(
    validator,
    tmp_path: Path,
) -> None:
    clone = _binding_clone(tmp_path)
    _verified_transition(clone, merge_on_first_parent=False)

    errors = validator.validate_phase0_interface_freeze(clone)

    assert any("direct first parent" in error or "first-parent history" in error for error in errors), errors


def test_verified_transition_rejects_octopus_merge(validator, tmp_path: Path) -> None:
    clone = _binding_clone(tmp_path)
    binding = _historical_binding(clone)
    git = [
        "git",
        "-C",
        str(clone),
        "-c",
        "user.name=policy-test",
        "-c",
        "user.email=policy@test",
    ]
    aprime_tree = str(_git(clone, "rev-parse", f"{APRIME}^{{tree}}")).strip()
    first_parent = subprocess.check_output(
        [*git, "commit-tree", aprime_tree, "-p", APRIME, "-m", "main parent"], text=True
    ).strip()
    third_parent = subprocess.check_output(
        [*git, "commit-tree", aprime_tree, "-p", APRIME, "-m", "third parent"], text=True
    ).strip()
    merge_tree = str(_git(clone, "rev-parse", f"{binding}^{{tree}}")).strip()
    octopus = subprocess.check_output(
        [
            *git,
            "commit-tree",
            merge_tree,
            "-p",
            first_parent,
            "-p",
            binding,
            "-p",
            third_parent,
            "-m",
            "octopus",
        ],
        text=True,
    ).strip()
    subprocess.run(["git", "-C", str(clone), "reset", "--hard", "--quiet", octopus], check=True)
    record = _record(clone)
    record["status"] = "merged_verified"
    record["merge_verification"] = {
        "target_branch": "main",
        "status": "verified",
        "canonical_merge_commit": octopus,
        "verified_at": "2026-07-21T12:34:56Z",
    }
    record["lane_authorization"] = {
        "authorized": True,
        "reason": "freeze_pull_request_merged_and_canonical_merge_verified",
    }
    _write_record(clone, record)
    _replace_marker(clone, _verified_marker(octopus, "2026-07-21T12:34:56Z"))
    transition = _commit(clone, "attest octopus")
    subprocess.run(
        ["git", "-C", str(clone), "update-ref", "refs/remotes/origin/main", transition],
        check=True,
    )

    errors = validator.validate_phase0_interface_freeze(clone)

    assert any("exactly two parents" in error for error in errors), errors


def test_record_history_rejects_reverted_and_multiple_transitions(validator, tmp_path: Path) -> None:
    reverted = _binding_clone(tmp_path / "reverted")
    binding = _historical_binding(reverted)
    _verified_transition(reverted)
    subprocess.run(
        [
            "git",
            "-C",
            str(reverted),
            "checkout",
            binding,
            "--",
            "governance/phase0-interface-freeze.yaml",
            "CONSOLIDATED_PLAN.md",
            "PARALLEL_WORK_GUIDE.md",
        ],
        check=True,
    )
    _commit(reverted, "revert attestation to pending bytes")
    errors = validator.validate_phase0_interface_freeze(reverted)
    assert any("record transition" in error or "record rewrite" in error for error in errors), errors

    rewritten = _binding_clone(tmp_path / "rewritten")
    _verified_transition(rewritten)
    record = _record(rewritten)
    record["merge_verification"]["verified_at"] = "2026-07-21T12:34:57Z"
    _write_record(rewritten, record)
    _replace_marker(
        rewritten,
        _verified_marker(record["merge_verification"]["canonical_merge_commit"], "2026-07-21T12:34:57Z"),
    )
    rewritten_head = _commit(rewritten, "rewrite verified attestation")
    subprocess.run(
        ["git", "-C", str(rewritten), "update-ref", "refs/remotes/origin/main", rewritten_head],
        check=True,
    )
    errors = validator.validate_phase0_interface_freeze(rewritten)
    assert any("record transition" in error or "record rewrite" in error for error in errors), errors


def test_verified_history_rejects_pending_merge_selection_then_reverification(
    validator,
    tmp_path: Path,
) -> None:
    clone = _binding_clone(tmp_path)
    binding = _historical_binding(clone)
    _verified_transition(clone)
    verified_carrier = str(_git(clone, "rev-parse", "HEAD")).strip()
    verified_tree = str(
        _git(clone, "rev-parse", f"{verified_carrier}^{{tree}}")
    ).strip()
    pending_tree = str(_git(clone, "rev-parse", f"{binding}^{{tree}}")).strip()
    git = [
        "git",
        "-C",
        str(clone),
        "-c",
        "user.name=policy-test",
        "-c",
        "user.email=policy@test",
    ]
    pending_selection = subprocess.check_output(
        [
            *git,
            "commit-tree",
            pending_tree,
            "-p",
            verified_carrier,
            "-p",
            binding,
            "-m",
            "select pending record after verification",
        ],
        text=True,
    ).strip()
    reverification = subprocess.check_output(
        [
            *git,
            "commit-tree",
            verified_tree,
            "-p",
            pending_selection,
            "-p",
            verified_carrier,
            "-m",
            "select verified record again",
        ],
        text=True,
    ).strip()
    subprocess.run(
        ["git", "-C", str(clone), "reset", "--hard", "--quiet", reverification],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(clone),
            "update-ref",
            "refs/remotes/origin/main",
            reverification,
        ],
        check=True,
        capture_output=True,
    )

    errors = validator.validate_phase0_interface_freeze(clone)

    assert any(
        "verified record bytes" in error or "pending record" in error
        for error in errors
    ), errors


def test_public_record_argument_must_equal_committed_authority(validator, tmp_path: Path) -> None:
    clone = _binding_clone(tmp_path)
    committed = _record(clone)
    divergent = copy.deepcopy(committed)
    divergent["lane_authorization"]["authorized"] = True

    errors = validator.validate_phase0_interface_freeze(clone, divergent)

    assert "caller-supplied Phase 0 record must exactly match the committed record" in errors


@pytest.mark.parametrize(
    ("field_path", "integer_alias"),
    [
        (("lane_authorization", "authorized"), 0),
        (("amendment_rule", "requires_joint_mini_review"), 1),
        (("reviews", 0, "independent_review"), 1),
    ],
)
def test_strict_boolean_fields_reject_integer_aliases(
    validator,
    tmp_path: Path,
    field_path: tuple,
    integer_alias: int,
) -> None:
    clone = _binding_clone(tmp_path)
    record = _record(clone)
    target = record
    for part in field_path[:-1]:
        target = target[part]
    target[field_path[-1]] = integer_alias
    _write_record(clone, record)
    _commit(clone, "write integer boolean alias")

    errors = validator.validate_phase0_interface_freeze(clone)

    assert any("boolean" in error or "lane_authorization" in error or "independent_review" in error for error in errors), errors


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-13-01T00:00:00Z",
        "2026-02-30T00:00:00Z",
        "2026-01-01T24:00:00Z",
        "2026-01-01T00:60:00Z",
        "2026-01-01T00:00:60Z",
        "2026-1-01T00:00:00Z",
    ],
)
def test_verified_timestamp_must_be_a_real_canonical_utc_instant(
    validator,
    tmp_path: Path,
    timestamp: str,
) -> None:
    clone = _binding_clone(tmp_path)
    _verified_transition(clone)
    record = _record(clone)
    record["merge_verification"]["verified_at"] = timestamp
    _write_record(clone, record)
    _replace_marker(
        clone,
        _verified_marker(record["merge_verification"]["canonical_merge_commit"], timestamp),
    )
    head = _commit(clone, "write invalid verified timestamp")
    subprocess.run(
        ["git", "-C", str(clone), "update-ref", "refs/remotes/origin/main", head],
        check=True,
    )

    errors = validator.validate_phase0_interface_freeze(clone)

    assert any("verified_at must be strict UTC" in error for error in errors), errors


def test_verified_marker_authorizes_creation_without_claiming_branch_absence(
    validator,
) -> None:
    record = {
        "status": "merged_verified",
        "merge_verification": {
            "canonical_merge_commit": "0" * 40,
            "verified_at": "2026-07-23T12:00:00Z",
        },
    }

    marker = validator._expected_marker_body(record, validator.V2_CONTRACT)

    assert "lane_branch_creation: authorized" in marker
    assert "lane_branches: none" not in marker


def test_verified_and_pending_markers_are_record_sensitive(validator, tmp_path: Path) -> None:
    verified = _binding_clone(tmp_path / "verified")
    _verified_transition(verified)
    for relative in ("CONSOLIDATED_PLAN.md", "PARALLEL_WORK_GUIDE.md"):
        path = verified / relative
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("status: merged_verified", "status: approved_pending_merge", 1), encoding="utf-8")
    _commit(verified, "restore stale pending markers")
    errors = validator.validate_phase0_interface_freeze(verified)
    assert any("marker block is not exact" in error for error in errors), errors

    pending = _binding_clone(tmp_path / "pending")
    merge = "1" * 40
    _replace_marker(pending, _verified_marker(merge, "2026-07-21T12:34:56Z"))
    _commit(pending, "install premature verified markers")
    errors = validator.validate_phase0_interface_freeze(pending)
    assert any("marker block is not exact" in error for error in errors), errors


@pytest.mark.parametrize(
    "stale_documents",
    [
        ("CONSOLIDATED_PLAN.md", "PARALLEL_WORK_GUIDE.md"),
        ("CONSOLIDATED_PLAN.md",),
        ("PARALLEL_WORK_GUIDE.md",),
    ],
)
def test_verified_markers_reject_both_plan_only_and_guide_only_stale_pending_blocks(
    validator,
    tmp_path: Path,
    stale_documents: tuple[str, ...],
) -> None:
    clone = _binding_clone(tmp_path)
    pending_marker = _document_marker(clone)
    _verified_transition(clone)
    for relative in stale_documents:
        _replace_document_marker(clone, relative, pending_marker)
    head = _commit(clone, "restore selected stale pending markers")
    subprocess.run(
        ["git", "-C", str(clone), "update-ref", "refs/remotes/origin/main", head],
        check=True,
    )

    errors = validator.validate_phase0_interface_freeze(clone)

    for relative in stale_documents:
        assert any(relative in error and "marker block is not exact" in error for error in errors), errors


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("status: approved_pending_merge", "status: merged_verified"),
        ("lane_authorization: false", "lane_authorization: true"),
    ],
)
def test_pending_markers_reject_status_or_authorization_mismatch(
    validator,
    tmp_path: Path,
    old: str,
    new: str,
) -> None:
    clone = _binding_clone(tmp_path)
    relative = "CONSOLIDATED_PLAN.md"
    marker = _document_marker(clone, relative).replace(old, new, 1)
    _replace_document_marker(clone, relative, marker)
    _commit(clone, "commit pending marker status authorization mismatch")

    errors = validator.validate_phase0_interface_freeze(clone)

    assert any(relative in error and "marker block is not exact" in error for error in errors), errors


def test_exact_marker_block_is_the_only_document_authorization_authority(
    validator,
    tmp_path: Path,
) -> None:
    clone = _binding_clone(tmp_path)
    path = clone / "PARALLEL_WORK_GUIDE.md"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "\n\nPhase 0 lane work may begin now. The team has the green light.\n",
        encoding="utf-8",
    )
    _commit(clone, "append non-authoritative authorization prose")

    assert validator.validate_phase0_interface_freeze(clone) == []


def test_verified_marker_remains_authoritative_over_stale_prose(
    validator,
    tmp_path: Path,
) -> None:
    clone = _binding_clone(tmp_path)
    _verified_transition(clone)
    path = clone / "PARALLEL_WORK_GUIDE.md"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "\n\nPhase 0 lane work remains unauthorized until a later attestation.\n",
        encoding="utf-8",
    )
    head = _commit(clone, "append non-authoritative stale prose")
    subprocess.run(
        ["git", "-C", str(clone), "update-ref", "refs/remotes/origin/main", head],
        check=True,
    )

    assert validator.validate_phase0_interface_freeze(clone) == []














def test_active_plan_omits_obsolete_b0_exit_wording() -> None:
    plan = (REPO_ROOT / "CONSOLIDATED_PLAN.md").read_text(encoding="utf-8")

    assert "legacy open record until Commit B" not in plan
    assert "next permitted action is to jointly freeze" not in plan


@pytest.mark.parametrize(
    ("mutation", "needle"),
    [
        (lambda text: text.replace("## Phase 0 —", "## Stage Zero —", 1), "exactly one ## Phase 0"),
        (lambda text: text.replace("## Phase 1 —", "## Stage One —", 1), "exactly one ## Phase 1"),
        (lambda text: text.replace("## Phase 1 —", "## Phase 0 — Duplicate\n\n## Phase 1 —", 1), "exactly one ## Phase 0"),
        (lambda text: text.replace("## Phase 0 —", "## Phase 1 — Reversed\n\n## Phase 0 —", 1), "exactly one ## Phase 1"),
        (
            lambda text: text.replace("## Phase 0 —", "## Stage Zero —", 1).replace("- [ ] **WP-0.1", "WP-0.1 removed ", 1),
            "exactly one ## Phase 0",
        ),
    ],
)
def test_plan_heading_structure_fails_closed(
    validator,
    tmp_path: Path,
    mutation,
    needle: str,
) -> None:
    clone = _binding_clone(tmp_path)
    path = clone / "CONSOLIDATED_PLAN.md"
    path.write_text(mutation(path.read_text(encoding="utf-8")), encoding="utf-8")
    _commit(clone, "malform Phase 0 headings")

    errors = validator.validate_phase0_interface_freeze(clone)

    assert any(needle in error or "after ## Phase 0" in error for error in errors), errors


@pytest.mark.parametrize("mutation", ["delete", "executable"])
def test_repairable_binding_paths_must_remain_100644_blobs(
    validator,
    tmp_path: Path,
    mutation: str,
) -> None:
    clone = _binding_clone(tmp_path)
    relative = "tests/policy/test_repository_governance.py"
    path = clone / relative
    if mutation == "delete":
        path.unlink()
    else:
        path.chmod(0o755)
    _commit(clone, f"make repairable binding path {mutation}")

    errors = validator.validate_phase0_interface_freeze(clone)

    assert any("HEAD binding path must remain a 100644 blob" in error and relative in error for error in errors), errors


def test_repairable_binding_fixture_survives_restoring_aprime_bytes(
    validator,
    tmp_path: Path,
) -> None:
    clone = _binding_clone(tmp_path)
    relative = "tests/policy/test_repository_governance.py"
    (clone / relative).write_bytes(_git(clone, "show", f"{APRIME}:{relative}", text=False))
    _commit(clone, "restore repairable path to A-prime bytes")

    assert validator.validate_phase0_interface_freeze(clone) == []


def test_pending_record_allows_unrelated_ordinary_descendants(
    validator,
    tmp_path: Path,
) -> None:
    clone = _binding_clone(tmp_path)
    unrelated = clone / "notes/unrelated.txt"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text("ordinary descendant\n", encoding="utf-8")
    _commit(clone, "add unrelated ordinary descendant")

    assert validator.validate_phase0_interface_freeze(clone) == []


def test_pending_record_allows_unrelated_merge_tips(
    validator,
    tmp_path: Path,
) -> None:
    clone = _binding_clone(tmp_path)
    base = str(_git(clone, "rev-parse", "HEAD")).strip()
    side_path = clone / "notes/side.txt"
    side_path.parent.mkdir(parents=True)
    side_path.write_text("side\n", encoding="utf-8")
    side = _commit(clone, "add unrelated side descendant")
    subprocess.run(
        ["git", "-C", str(clone), "reset", "--hard", "--quiet", base],
        check=True,
    )
    main_path = clone / "notes/main.txt"
    main_path.parent.mkdir(parents=True)
    main_path.write_text("main\n", encoding="utf-8")
    _commit(clone, "add unrelated main descendant")
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
            "--no-ff",
            "--quiet",
            "-m",
            "merge unrelated descendants",
            side,
        ],
        check=True,
        capture_output=True,
    )

    assert validator.validate_phase0_interface_freeze(clone) == []


def test_index_and_worktree_drift_cannot_mask_protected_committed_bytes(
    validator,
    tmp_path: Path,
) -> None:
    staged_frozen = _binding_clone(tmp_path / "frozen")
    frozen = staged_frozen / "EvoNN-Shared/src/evonn_shared/canonical.py"
    frozen.write_bytes(frozen.read_bytes() + b"# staged drift\n")
    subprocess.run(["git", "-C", str(staged_frozen), "add", str(frozen.relative_to(staged_frozen))], check=True)
    errors = validator.validate_phase0_interface_freeze(staged_frozen)
    assert any("index" in error and "canonical.py" in error for error in errors), errors

    for mutation in ("unstaged", "staged"):
        historical = _binding_clone(tmp_path / mutation)
        relative = "governance/b0-status.yaml"
        path = historical / relative
        path.write_bytes(path.read_bytes() + b"# historical drift\n")
        if mutation == "staged":
            subprocess.run(["git", "-C", str(historical), "add", relative], check=True)
        errors = validator.validate_phase0_interface_freeze(historical)
        assert any("historical B0" in error and relative in error for error in errors), errors

    marker = _binding_clone(tmp_path / "marker")
    relative = "PARALLEL_WORK_GUIDE.md"
    marker_path = marker / relative
    good_bytes = marker_path.read_bytes()
    marker_path.write_text(marker_path.read_text(encoding="utf-8").replace("lane_authorization: false", "lane_authorization: true", 1), encoding="utf-8")
    _commit(marker, "commit a bad marker")
    marker_path.write_bytes(good_bytes)
    errors = validator.validate_phase0_interface_freeze(marker)
    assert any(relative in error and ("marker" in error or "worktree" in error or "index" in error) for error in errors), errors


@pytest.mark.parametrize(
    "variable",
    [
        "GIT_DIR",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_INDEX_FILE",
        "GIT_NAMESPACE",
        "GIT_CONFIG_COUNT",
    ],
)
def test_git_redirection_environment_is_rejected_by_api_and_cli(
    validator,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    variable: str,
) -> None:
    clone = _binding_clone(tmp_path)
    shutil.copy2(VALIDATOR_PATH, clone / "scripts/policy/validate_phase0_interface_freeze.py")
    _commit(clone, "install current validator")
    value = str(tmp_path / "forged")
    monkeypatch.setenv(variable, value)
    errors = validator.validate_phase0_interface_freeze(clone)
    assert any("Git override environment is forbidden" in error and variable in error for error in errors), errors

    environment = os.environ.copy()
    result = subprocess.run(
        [sys.executable, str(clone / "scripts/policy/validate_phase0_interface_freeze.py")],
        cwd=clone,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert variable in result.stdout
    assert "Traceback" not in result.stdout + result.stderr


@pytest.mark.parametrize(
    "location",
    [
        "pack-directory",
        "pack-artifact",
        "loose-directory",
        "loose-object",
        "info-directory",
    ],
)
def test_git_object_store_symlinks_are_rejected_by_api_and_cli(
    validator,
    tmp_path: Path,
    location: str,
) -> None:
    clone = _binding_clone(tmp_path / "clone")
    shutil.copy2(VALIDATOR_PATH, clone / "scripts/policy/validate_phase0_interface_freeze.py")
    _commit(clone, "install test candidate validator")
    objects = clone / ".git/objects"
    external = tmp_path / f"external-{location}"
    if location == "pack-directory":
        target = objects / "pack"
        target.rename(external)
        target.symlink_to(external, target_is_directory=True)
        expected_relative = "pack"
    elif location == "pack-artifact":
        artifacts = sorted((objects / "pack").glob("*.pack"))
        assert artifacts
        target = artifacts[0]
        target.rename(external)
        target.symlink_to(external)
        expected_relative = f"pack/{target.name}"
    elif location == "loose-directory":
        external.mkdir()
        target = next(
            objects / f"{value:02x}"
            for value in range(256)
            if not (objects / f"{value:02x}").exists()
        )
        target.symlink_to(external, target_is_directory=True)
        expected_relative = target.name
    elif location == "loose-object":
        target = objects / "bb" / ("0" * 38)
        target.parent.mkdir(exist_ok=True)
        external.write_bytes(b"not a Git object\n")
        target.symlink_to(external)
        expected_relative = f"bb/{target.name}"
    else:
        target = objects / "info"
        target.rename(external)
        target.symlink_to(external, target_is_directory=True)
        expected_relative = "info"

    errors = validator.validate_phase0_interface_freeze(clone)

    diagnostic = (
        "symbolic links are forbidden below .git/objects: "
        f"{expected_relative}"
    )
    assert any(diagnostic in error for error in errors), errors

    result = subprocess.run(
        [sys.executable, str(clone / "scripts/policy/validate_phase0_interface_freeze.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert diagnostic in result.stdout
    assert "Traceback" not in result.stdout + result.stderr


def test_git_object_store_traversal_fails_closed_on_unreadable_subtree(
    validator,
    tmp_path: Path,
) -> None:
    clone = _binding_clone(tmp_path / "clone")
    shutil.copy2(VALIDATOR_PATH, clone / "scripts/policy/validate_phase0_interface_freeze.py")
    _commit(clone, "install test candidate validator")
    fanout = clone / ".git/objects/aa"
    fanout.mkdir(exist_ok=True)
    external = tmp_path / "external-object"
    external.write_bytes(b"not a Git object\n")
    (fanout / "hidden-object").symlink_to(external)
    fanout.chmod(0)
    try:
        try:
            with os.scandir(fanout) as entries:
                next(entries, None)
        except PermissionError:
            pass
        else:
            pytest.skip("filesystem permissions do not make the object subtree unreadable")

        errors = validator.validate_phase0_interface_freeze(clone)

        assert any("cannot verify hardened Git state" in error for error in errors), errors
    finally:
        fanout.chmod(0o700)


def test_repository_git_directory_must_not_be_a_symlink(validator, tmp_path: Path) -> None:
    clone = _binding_clone(tmp_path / "clone")
    external_git = tmp_path / "external-git-dir"
    (clone / ".git").rename(external_git)
    (clone / ".git").symlink_to(external_git, target_is_directory=True)

    errors = validator.validate_phase0_interface_freeze(clone)

    assert any("repository-root .git" in error and "symlink" in error for error in errors), errors


def test_shared_clone_alternate_object_store_is_rejected(validator, tmp_path: Path) -> None:
    shared = tmp_path / "shared"
    subprocess.run(
        ["git", "clone", "--quiet", "--shared", str(REPO_ROOT), str(shared)],
        check=True,
        capture_output=True,
    )

    errors = validator.validate_phase0_interface_freeze(shared)

    assert any("alternate object" in error for error in errors), errors


def test_cli_reexecutes_in_isolated_mode_before_sibling_imports(tmp_path: Path) -> None:
    clone = _binding_clone(tmp_path / "clone")
    validator_path = clone / "scripts/policy/validate_phase0_interface_freeze.py"
    shutil.copy2(VALIDATOR_PATH, validator_path)
    (clone / "scripts/policy/yaml.py").write_text(
        "raise SystemExit(0)\n",
        encoding="utf-8",
    )
    (clone / "governance/phase0-interface-freeze.yaml").write_text(
        "schema_version: [\n",
        encoding="utf-8",
    )
    _commit(clone, "install hostile sibling yaml module")

    result = subprocess.run(
        [sys.executable, str(validator_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "invalid" in result.stdout.lower() or "yaml" in result.stdout.lower()
    assert "Traceback" not in result.stdout + result.stderr


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
