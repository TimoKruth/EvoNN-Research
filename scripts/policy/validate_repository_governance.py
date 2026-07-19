#!/usr/bin/env python3
"""Fail-closed validation for the repository's plan and authority controls."""

from __future__ import annotations

import hashlib
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Set, Tuple
from urllib.parse import urlparse

import yaml


ALLOWED_ROOT_PLAN_FILENAMES: Set[str] = {"CONSOLIDATED_PLAN.md"}
REQUIRED_B0_ITEM_IDS: Tuple[str, ...] = ("B0.1", "B0.2", "B0.3", "B0.4", "B0.5", "B0.6")
EXCLUDED_PROSE_SCAN_TREES: Set[str] = {"archive", "claude-spec", "claudex-spec"}
IGNORED_INTERNAL_TREES: Set[str] = {".git", ".claude", ".superpowers", ".pytest_cache"}
RESEARCH_LOG_DIRECTORIES: Set[str] = {"research", "research-log", "research-logs", "research_log", "research_logs"}
RESEARCH_LOG_NAME = re.compile(r"(?:^|[_-])(?:OBSERVATIONS?|RESEARCH[_-]LOG|EXPERIMENT[_-]LOG)$", re.I)
PINNED_SOURCE_COMMIT = "2c622528ac31f9e86d3fd9e03fab3279b3819d72"
REQUIRED_ENTRY_FIELDS: Set[str] = {
    "id",
    "scope",
    "path",
    "normative_role",
    "origin_state",
    "upstream_url",
    "source_commit",
    "declared_version",
    "imported_at",
    "git_object_type",
    "git_object_id",
    "content_digest",
    "consumer_acceptance_authority",
    "supersedes",
}
EXPECTED_SOURCES: Mapping[str, Mapping[str, Any]] = {
    "claude-spec": {
        "scope": "directory",
        "path": "claude-spec/",
        "source_commit": PINNED_SOURCE_COMMIT,
        "declared_version": "0.1.0-draft.1",
        "git_object_type": "tree",
        "git_object_id": "0f43ade62e57d743b94410ebadbb193ac5284618",
        "digest": "89298a056b9f37d94a3cfa4e404c9f04f33b558929a9fbb60070f14eb51478a9",
        "consumer_acceptance_authority": False,
    },
    "program-charter": {
        "scope": "file",
        "path": "PROGRAM_CHARTER.md",
        "source_commit": PINNED_SOURCE_COMMIT,
        "declared_version": "rev.2",
        "git_object_type": "blob",
        "git_object_id": "c0b000d449352308ef7387a25519dc9258b85659",
        "digest": "cdbc578234d31076649f5b2c013f82fb5887b03be653c99b729dd57fa8598330",
        "consumer_acceptance_authority": False,
    },
    "product-research-interop": {
        "scope": "file",
        "path": "claudex-spec/19-research-interop.md",
        "source_commit": PINNED_SOURCE_COMMIT,
        "declared_version": "1.0.0-draft",
        "git_object_type": "blob",
        "git_object_id": "a53716b253cb870efb4916883c3348c4dd5dbe07",
        "digest": "55979195c29aec4bb0bd34ab893f4b1797d99e2227e1f6ee07907622b6af8833",
        "consumer_acceptance_authority": True,
    },
}
ACTIVE_PLAN_PATTERNS: Sequence[re.Pattern[str]] = (
    re.compile(r"^\s*(?:\*\*)?status(?:\*\*)?\s*:\s*(?:\*\*)?active execution plan\b", re.I | re.M),
    re.compile(r"^\s*\*\*status:\*\*\s*active execution plan\b", re.I | re.M),
    re.compile(r"^\s*this (?:document|file) is (?:the|an) active execution plan\b", re.I | re.M),
)
PLAN_LIKE_NAME = re.compile(r"(?:^|[_-])(?:PLAN|CHECKLIST)(?:[_-]|\.md$)", re.I)
PLAN_HEADING = re.compile(r"^#{1,6}\s+.*\bexecution plan\s*$", re.I | re.M)
ACTIVE_STATUS = re.compile(r"^\s*(?:\*\*)?status(?::\*\*|(?:\*\*)?\s*:)[ \t]*(?:\*\*)?active\b", re.I | re.M)
ARCHIVE_PLAN_SUFFIX = re.compile(
    r"^(?:v?\d+|rev\d+|done|final|archive|archived|old|complete|completed|draft|backup)$",
    re.I,
)
UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
EXPECTED_B0_REPOSITORY_MODEL: Mapping[str, Any] = {
    "python_package_skeleton_count": 7,
    "data_only_skeleton": "shared-benchmarks/",
    "benchmark_helpers_module": "evonn_shared.benchmarks",
    "data_only_check_script": "scripts/ci/benchmarks-checks.sh",
    "python_import_validation": "required",
    "data_skeleton_validation": "layout_and_loader",
}
B0_REPORT_LEGACY_SCHEMA_VERSION = "1.0.0"
B0_REPORT_SCHEMA_VERSION = "2.0.0"
# This is the exact pre-closure evidence revision. Schema 1 is a historical
# transition record, not a reusable report format.
B0_REPORT_LEGACY_REVISION = "cc067143fd3143eaba490c4dcc9f3765db1d70f2"
B0_REPORT_KIND = "gate_b0_integration"
B0_REPORT_BLOCKERS: Mapping[str, str] = {
    "B0.2": "authoritative_remote_url_absent",
    "B0.5": "hosted_ci_not_executed",
}
B0_REPORT_NEXT_TRANSITION = (
    "After B0.2 and B0.5 both close, rerun joint Gate B0 integration, then jointly freeze the Phase 0 "
    "interfaces before Lane A and Lane B branches begin."
)
B0_REPORT_CLOSED_NEXT_TRANSITION = (
    "The team must jointly freeze the Phase 0 interfaces before creating "
    "Lane A and Lane B implementation branches."
)
B0_REPORT_LOCAL_PROBES: Mapping[str, Mapping[str, str]] = {
    "numpy": {
        "artifact_path": ".artifacts/b0/local/numpy/b0-runtime-probe.json",
        "system": "stratograph",
        "manifest_path": "EvoNN-Stratograph/backend-capabilities.json",
    },
    "mlx": {
        "artifact_path": ".artifacts/b0/local/mlx/b0-runtime-probe.json",
        "system": "prism",
        "manifest_path": "EvoNN-Prism/backend-capabilities.json",
    },
}
# This is a B0-closure-specific hosted-evidence pin. It is not a general
# runtime, workflow, branch, or future-gate policy.
B0_CLOSURE_HOSTED_COMMIT = "f68856f0c2fdf0ebc73671264b5a3ab0cff3b224"
B0_CLOSURE_AUTHORITY_URL = "https://github.com/TimoKruth/EvoNN-Research.git"
B0_CLOSURE_PENDING_B02 = {
    "status": "open",
    "open_reason": "authoritative_remote_url_absent",
    "evidence": (
        "governance/authority-provenance.yaml remains local-only/provisional with null upstream URLs; "
        "governance/b0-report.json records the blocker"
    ),
}

B0_REPORT_HOSTED_PROBE_FIELDS = frozenset(
    {
        "backend",
        "backend_version",
        "system",
        "manifest_path",
        "artifact_name",
        "artifact_path",
        "sha256",
        "repository_commit",
        "workflow_name",
        "run_id",
        "run_attempt",
        "run_url",
        "event",
        "branch",
        "host_os",
        "host_architecture",
        "execution_scope",
        "evidence_scope",
        "qualification",
        "conclusion",
    }
)

B0_REPORT_HOSTED_PROBES: Tuple[Mapping[str, str], ...] = (
    {
        "backend": "numpy",
        "backend_version": "2.5.1",
        "system": "stratograph",
        "manifest_path": "EvoNN-Stratograph/backend-capabilities.json",
        "artifact_name": "b0-linux-runtime-probe",
        "artifact_path": "governance/evidence/b0/hosted/linux-runtime-probe.json",
        "sha256": "f17ca8a8f35538d72c6a7585ef013a7e1f5d50484fcc08d85ac672745d371c00",
        "repository_commit": B0_CLOSURE_HOSTED_COMMIT,
        "workflow_name": "B0 Linux trust lane",
        "run_id": "29658842317",
        "run_attempt": "1",
        "run_url": (
            "https://github.com/TimoKruth/EvoNN-Research/actions/runs/"
            "29658842317"
        ),
        "event": "push",
        "branch": "main",
        "host_os": "Linux",
        "host_architecture": "x86_64",
        "execution_scope": "hosted",
        "evidence_scope": "hosted_bootstrap",
        "qualification": "bootstrap_probe_only",
        "conclusion": "success",
    },
    {
        "backend": "mlx",
        "backend_version": "0.32.0",
        "system": "prism",
        "manifest_path": "EvoNN-Prism/backend-capabilities.json",
        "artifact_name": "b0-macos-runtime-probe",
        "artifact_path": "governance/evidence/b0/hosted/macos-runtime-probe.json",
        "sha256": "147e5c54a75bb9090eb3e94e06fe9c9f656ca751df12fdb5fc8950bf4398e157",
        "repository_commit": B0_CLOSURE_HOSTED_COMMIT,
        "workflow_name": "B0 macOS engine lane",
        "run_id": "29658842318",
        "run_attempt": "1",
        "run_url": (
            "https://github.com/TimoKruth/EvoNN-Research/actions/runs/"
            "29658842318"
        ),
        "event": "push",
        "branch": "main",
        "host_os": "Darwin",
        "host_architecture": "arm64",
        "execution_scope": "hosted",
        "evidence_scope": "hosted_bootstrap",
        "qualification": "bootstrap_probe_only",
        "conclusion": "success",
    },
)
B0_HOSTED_PROBE_SEMANTIC_SHA256: Mapping[str, str] = {
    "numpy": "124f120ca1f5e0f7ff41b286df32b86525d066a9d42882edb96e82a22bd7a5aa",
    "mlx": "ba6161c85502e9a68f72531d224af221dd99e2c4a3999a70c2ee588d05f309b1",
}
B0_HOSTED_PROBE_PACKAGES: Tuple[Mapping[str, str], ...] = (
    {"distribution": "evonn-shared", "module": "evonn_shared", "system": "shared", "version": "0.0.0"},
    {"distribution": "evonn-compare", "module": "evonn_compare", "system": "compare", "version": "0.0.0"},
    {
        "distribution": "evonn-contenders",
        "module": "evonn_contenders",
        "system": "contenders",
        "version": "0.0.0",
    },
    {"distribution": "evonn-prism", "module": "prism", "system": "prism", "version": "0.0.0"},
    {"distribution": "evonn-topograph", "module": "topograph", "system": "topograph", "version": "0.0.0"},
    {
        "distribution": "evonn-stratograph",
        "module": "stratograph",
        "system": "stratograph",
        "version": "0.0.0",
    },
    {
        "distribution": "evonn-primordia",
        "module": "evonn_primordia",
        "system": "primordia",
        "version": "0.0.0",
    },
)
B0_HOSTED_PROBE_CLOSURE_CLAIMS: Mapping[str, Mapping[str, Any]] = {
    "numpy": {
        "backend_class": "numpy_fallback",
        "device_class": "cpu",
        "package_under_test": "evonn-stratograph",
        "precision_mode": "float64",
        "host": {
            "architecture": "x86_64",
            "kernel": "6.17.0-1020-azure",
            "logical_cpu_count": 4,
            "os_name": "Linux",
            "os_version": "Linux-6.17.0-1020-azure-x86_64-with-glibc2.39",
        },
    },
    "mlx": {
        "backend_class": "mlx_native",
        "device_class": "apple_silicon_mlx_default",
        "package_under_test": "evonn-prism",
        "precision_mode": "float32",
        "host": {
            "architecture": "arm64",
            "kernel": "24.6.0",
            "logical_cpu_count": 3,
            "os_name": "Darwin",
            "os_version": "15.7.7",
        },
    },
}
B0_HOSTED_PROBE_EVIDENCE = {
    "class": "contract",
    "statement": "Bootstrap portability/runtime contract evidence only; not scientific or backend qualification.",
}
B0_HOSTED_PROBE_WORKERS = {"count": 1, "topology": "single_process"}
B0_HOSTED_PROBE_OPERATION = {
    "operation": "sum_of_squares",
    "input": [1.0, 2.0, 3.0],
    "expected": 14.0,
    "actual": 14.0,
    "validated": True,
}
B0_REPORT_WORKFLOWS: Tuple[Mapping[str, Any], ...] = (
    {
        "path": ".github/workflows/linux-trust.yml",
        "name": "B0 Linux trust lane",
        "runner": "ubuntu-latest",
        "python_version": "3.13",
        "uv_version": "0.5.13",
        "actions": [
            "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd",
            "astral-sh/setup-uv@11f9893b081a58869d3b5fccaea48c9e9e46f990",
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
        ],
    },
    {
        "path": ".github/workflows/macos-engines.yml",
        "name": "B0 macOS engine lane",
        "runner": "macos-15",
        "python_version": "3.13",
        "uv_version": "0.5.13",
        "actions": [
            "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd",
            "astral-sh/setup-uv@11f9893b081a58869d3b5fccaea48c9e9e46f990",
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
        ],
    },
)
B0_REPORT_VERIFICATION_COMMANDS: Tuple[str, ...] = (
    "uv lock --check",
    "uv sync --all-packages --group dev --locked",
    "uv run --locked --group dev pytest -q",
    "uv run --locked --group dev ruff check .",
    "uv run --locked --group dev python scripts/policy/validate_import_boundaries.py",
    "python3 scripts/policy/validate_repository_governance.py",
    "uv run --locked --group dev python scripts/policy/validate_backend_capabilities.py",
    "scripts/ci/b0-policy-checks.sh",
    "scripts/ci/shared-checks.sh (from /tmp)",
    "scripts/ci/benchmarks-checks.sh (from /tmp)",
    "scripts/ci/compare-checks.sh (from /tmp)",
    "scripts/ci/contenders-checks.sh (from /tmp)",
    "scripts/ci/prism-checks.sh (from /tmp)",
    "scripts/ci/topograph-checks.sh (from /tmp)",
    "scripts/ci/stratograph-checks.sh (from /tmp)",
    "scripts/ci/primordia-checks.sh (from /tmp)",
    (
        "uv run --locked --all-packages --group dev python scripts/ci/runtime_probe.py generate --backend numpy "
        "--system stratograph --manifest EvoNN-Stratograph/backend-capabilities.json "
        "--output .artifacts/b0/local/numpy/b0-runtime-probe.json --execution-mode local"
    ),
    (
        "uv run --locked --all-packages --group dev python scripts/ci/runtime_probe.py validate "
        "--input .artifacts/b0/local/numpy/b0-runtime-probe.json --execution-mode local --expected-backend numpy"
    ),
    (
        "uv run --locked --all-packages --group dev python scripts/ci/runtime_probe.py generate --backend mlx "
        "--system prism --manifest EvoNN-Prism/backend-capabilities.json "
        "--output .artifacts/b0/local/mlx/b0-runtime-probe.json --execution-mode local"
    ),
    (
        "uv run --locked --all-packages --group dev python scripts/ci/runtime_probe.py validate "
        "--input .artifacts/b0/local/mlx/b0-runtime-probe.json --execution-mode local --expected-backend mlx"
    ),
    "uv run --locked --group dev pytest -q tests/policy/test_b0_ci_bootstrap.py",
    "git diff --check",
)
FORBIDDEN_HOSTED_REPORT_KEYS: Set[str] = {
    "run_id",
    "run_url",
    "run_attempt",
    "attempt",
    "hosted_run_id",
    "hosted_run_url",
    "hosted_run_attempt",
    "hosted_artifact",
    "hosted_artifacts",
    "artifact_url",
}
B0_REPORT_LEGACY_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "report_kind",
        "evaluated_at",
        "repository",
        "overall_state",
        "items",
        "blockers",
        "local_runtime_probes",
        "workflows",
        "checked_in_evidence",
        "verification",
        "parallel_handoff_ready",
        "parallel_handoff_blockers",
        "next_transition",
    }
)
B0_REPORT_TOP_LEVEL_FIELDS = frozenset(
    {*B0_REPORT_LEGACY_TOP_LEVEL_FIELDS, "hosted_runtime_probes"}
)
B0_REPORT_SCHEMA_2_REQUIRED_ITEM_EVIDENCE: Mapping[str, frozenset[str]] = {
    "B0.2": frozenset(
        {
            "governance/authority-provenance.yaml",
            "governance/SPEC_UPGRADE_PROCESS.md",
            "governance/SPEC_TRACEABILITY.md",
            "governance/b0-report.json",
        }
    ),
    "B0.5": frozenset(
        {
            ".github/workflows/linux-trust.yml",
            ".github/workflows/macos-engines.yml",
            "scripts/ci/runtime_probe.py",
            "governance/b0-report.json",
            *(probe["artifact_path"] for probe in B0_REPORT_HOSTED_PROBES),
        }
    ),
    "B0.6": frozenset(
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
    ),
}
B0_REPORT_REPOSITORY_FIELDS = frozenset({"branch", "evaluated_commit", "evaluated_tree", "relationship"})
B0_REPORT_ITEM_FIELDS = frozenset({"state", "reason", "evidence_paths"})
B0_REPORT_PROBE_FIELDS = frozenset(
    {
        "backend",
        "backend_version",
        "system",
        "manifest_path",
        "artifact_path",
        "sha256",
        "host_os",
        "host_architecture",
        "execution_scope",
        "evidence_scope",
        "qualification",
        "optional_local_evidence",
    }
)
B0_REPORT_WORKFLOW_FIELDS = frozenset(
    {"path", "name", "runner", "python_version", "uv_version", "actions"}
)
B0_REPORT_VERIFICATION_FIELDS = frozenset({"overall", "summary", "commands"})
B0_REPORT_VERIFICATION_SUMMARY_FIELDS = frozenset({"passed", "failed"})
B0_REPORT_VERIFICATION_COMMAND_FIELDS = frozenset({"command", "result"})
B0_EVIDENCE_ONLY_PATHS = frozenset(
    {"governance/b0-report.json", "governance/b0-status.yaml", ".superpowers/sdd/task-6-report.md"}
)


def read_frontmatter(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    marker = text.find("\n---\n", 4)
    if marker < 0:
        return {}
    parsed = yaml.safe_load(text[4:marker])
    return parsed if isinstance(parsed, dict) else {}


def _markdown_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.md"):
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] in IGNORED_INTERNAL_TREES:
            continue
        yield path


def _is_untyped_research_log(relative: Path, metadata: Mapping[str, Any]) -> bool:
    if metadata.get("document_kind") == "execution_plan":
        return False
    in_research_directory = any(part.lower() in RESEARCH_LOG_DIRECTORIES for part in relative.parts[:-1])
    research_log_name = bool(RESEARCH_LOG_NAME.search(relative.stem))
    return in_research_directory or research_log_name


def _is_plan_candidate(path: Path, text: str, metadata: Mapping[str, Any]) -> bool:
    return (
        bool(PLAN_LIKE_NAME.search(path.name))
        or metadata.get("document_kind") == "execution_plan"
        or bool(PLAN_HEADING.search(text))
        or any(pattern.search(text) for pattern in ACTIVE_PLAN_PATTERNS)
    )


def find_active_execution_plans(root: Path) -> List[Path]:
    active: List[Path] = []
    for path in _markdown_files(root):
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] in EXCLUDED_PROSE_SCAN_TREES:
            continue
        metadata = read_frontmatter(path)
        explicitly_active = metadata.get("document_kind") == "execution_plan" and metadata.get("status") == "active"
        if _is_untyped_research_log(relative, metadata):
            continue
        text = path.read_text(encoding="utf-8")
        prose_active = any(pattern.search(text) for pattern in ACTIVE_PLAN_PATTERNS)
        unclassified_active = PLAN_HEADING.search(text) and ACTIVE_STATUS.search(text)
        if explicitly_active or prose_active or unclassified_active:
            active.append(relative)
    return sorted(active, key=lambda item: item.as_posix().encode("utf-8"))


def validate_plan_metadata(root: Path) -> List[str]:
    errors: List[str] = []
    for path in _markdown_files(root):
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] in EXCLUDED_PROSE_SCAN_TREES:
            continue
        text = path.read_text(encoding="utf-8")
        metadata = read_frontmatter(path)
        if _is_untyped_research_log(relative, metadata):
            continue
        if not _is_plan_candidate(path, text, metadata):
            continue
        if metadata.get("document_kind") != "execution_plan":
            errors.append(f"plan-like project document requires execution_plan frontmatter: {relative}")
            continue
        if metadata.get("status") not in {"active", "archived", "non-authoritative"}:
            errors.append(f"execution plan has invalid status metadata: {relative}")
        if not isinstance(metadata.get("authoritative"), bool):
            errors.append(f"execution plan must declare boolean authoritative metadata: {relative}")
        if metadata.get("status") == "active" and metadata.get("authoritative") is not True:
            errors.append(f"active execution plan must be authoritative: {relative}")
        if metadata.get("status") in {"archived", "non-authoritative"} and metadata.get("authoritative") is not False:
            errors.append(f"inactive execution plan must be non-authoritative: {relative}")
    return errors


def validate_root_plan_filenames(root: Path) -> List[str]:
    errors: List[str] = []
    for path in root.glob("*.md"):
        metadata = read_frontmatter(path)
        if _is_untyped_research_log(path.relative_to(root), metadata):
            continue
        looks_like_plan = bool(PLAN_LIKE_NAME.search(path.name)) or metadata.get("document_kind") == "execution_plan"
        if looks_like_plan and path.name not in ALLOWED_ROOT_PLAN_FILENAMES:
            errors.append(f"root plan filename is not allowlisted: {path.name}")
    return errors


def _archive_name_is_plan_candidate(name: str) -> bool:
    tokens = [token for token in re.split(r"[_-]+", Path(name).stem) if token]
    for index, token in enumerate(tokens):
        if token.upper() not in {"PLAN", "CHECKLIST"}:
            continue
        suffix = tokens[index + 1 :]
        if not suffix or all(ARCHIVE_PLAN_SUFFIX.fullmatch(part) for part in suffix):
            return True
    return False


def validate_archived_plans(root: Path) -> List[str]:
    errors: List[str] = []
    archive = root / "archive"
    if not archive.exists():
        return errors
    for path in archive.rglob("*.md"):
        metadata = read_frontmatter(path)
        is_plan = metadata.get("document_kind") == "execution_plan" or _archive_name_is_plan_candidate(path.name)
        if not is_plan:
            continue
        if metadata.get("authoritative") is not False:
            errors.append(f"archived plan must set authoritative: false: {path.relative_to(root)}")
        if metadata.get("status") not in {"archived", "non-authoritative"}:
            errors.append(f"archived plan must have archived/non-authoritative status: {path.relative_to(root)}")
    return errors


def _git(repo_root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo_root), *args], stderr=subprocess.STDOUT)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def canonical_tree_digest(entries: Iterable[Tuple[str, bytes]]) -> str:
    ordered = sorted(entries, key=lambda item: item[0].encode("utf-8"))
    manifest = b"".join(f"{_sha256(content)}  {relative}\n".encode("utf-8") for relative, content in ordered)
    return _sha256(manifest)


def canonical_tree_digest_from_git(repo_root: Path, commit: str, directory: str) -> str:
    directory = directory.rstrip("/")
    raw_paths = _git(repo_root, "ls-tree", "-r", "-z", "--name-only", commit, "--", directory)
    paths = [item.decode("utf-8") for item in raw_paths.split(b"\0") if item]
    prefix = directory + "/"
    entries = ((path[len(prefix) :], _git(repo_root, "show", f"{commit}:{path}")) for path in paths)
    return canonical_tree_digest(entries)


def canonical_tree_digest_from_worktree(directory: Path) -> str:
    files = (path for path in directory.rglob("*") if path.is_file())
    entries = ((path.relative_to(directory).as_posix(), path.read_bytes()) for path in files)
    return canonical_tree_digest(entries)


def _entry_digest(entry: Mapping[str, Any]) -> Any:
    digest = entry.get("content_digest")
    return digest.get("value") if isinstance(digest, dict) else None


def validate_working_tree_digests(manifest: Mapping[str, Any], repo_root: Path) -> List[str]:
    errors: List[str] = []
    for index, entry in enumerate(manifest.get("sources", [])):
        if not isinstance(entry, Mapping):
            errors.append(f"provenance source entry {index} must be a mapping")
            continue
        path_value = entry.get("path")
        if not isinstance(path_value, str):
            errors.append(f"{entry.get('id', '<unknown>')}: missing path")
            continue
        path = repo_root / path_value.rstrip("/")
        if not path.exists():
            errors.append(f"{entry.get('id', '<unknown>')}: checked-out source is missing")
            continue
        actual = canonical_tree_digest_from_worktree(path) if entry.get("scope") == "directory" else _sha256(path.read_bytes())
        if actual != _entry_digest(entry):
            errors.append(f"{entry.get('id', '<unknown>')}: working-tree content digest does not match provenance")
    return errors


def validate_provenance(manifest: Mapping[str, Any], repo_root: Path) -> List[str]:
    errors: List[str] = []
    duplicate_status_fields = {"b0_2_status", "b0_2_open_reason"} & set(manifest)
    if duplicate_status_fields:
        errors.append("gate status belongs only in governance/b0-status.yaml")
    if manifest.get("digest_method") != "canonical-sha256-tree-v1":
        errors.append("provenance digest_method must be canonical-sha256-tree-v1")
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        errors.append("provenance sources must be a list")
        return errors
    if manifest.get("authority_state") == "remote-pinned":
        if manifest.get("status") != "active":
            errors.append("remote-pinned provenance status must be active")
        for index, entry in enumerate(sources):
            if isinstance(entry, Mapping) and entry.get("upstream_url") != B0_CLOSURE_AUTHORITY_URL:
                source_id = entry.get("id", f"source entry {index}")
                errors.append(
                    f"{source_id}: remote-pinned B0 authority URL must be {B0_CLOSURE_AUTHORITY_URL}"
                )
    entries: Dict[str, Mapping[str, Any]] = {}
    for index, entry in enumerate(sources):
        if not isinstance(entry, Mapping):
            errors.append(f"provenance source entry {index} must be a mapping")
            continue
        source_id = entry.get("id")
        missing = REQUIRED_ENTRY_FIELDS - set(entry)
        if missing:
            errors.append(f"{source_id or f'source entry {index}'}: missing fields {sorted(missing)}")
        if not isinstance(source_id, str) or not source_id:
            errors.append(f"provenance source entry {index} must have a non-empty string id")
            continue
        if source_id in entries:
            errors.append(f"duplicate provenance source id: {source_id}")
            continue
        entries[source_id] = entry
    if set(entries) != set(EXPECTED_SOURCES):
        errors.append(f"provenance source IDs must be exactly {sorted(EXPECTED_SOURCES)}")
    for source_id, expected in EXPECTED_SOURCES.items():
        entry = entries[source_id] if source_id in entries else None
        if not entry:
            continue
        missing = REQUIRED_ENTRY_FIELDS - set(entry)
        if missing:
            errors.append(f"{source_id}: missing fields {sorted(missing)}")
            continue
        if not entry.get("normative_role"):
            errors.append(f"{source_id}: normative_role must be non-empty")
        for field in ("scope", "path", "source_commit", "declared_version", "git_object_type", "git_object_id", "consumer_acceptance_authority"):
            if entry[field] != expected[field]:
                errors.append(f"{source_id}: {field} does not match the required pin")
        if entry.get("supersedes") is not None:
            errors.append(f"{source_id}: initial pin must set supersedes to null")
        imported_at = entry.get("imported_at")
        if not isinstance(imported_at, str) or not UTC_TIMESTAMP.match(imported_at):
            errors.append(f"{source_id}: imported_at must be a deterministic UTC ISO-8601 timestamp")
        digest = entry.get("content_digest")
        if not isinstance(digest, dict) or digest.get("algorithm") != "sha256" or digest.get("value") != expected["digest"]:
            errors.append(f"{source_id}: checked-in SHA-256 digest does not match the required pin")
        try:
            git_path = str(entry["path"]).rstrip("/")
            actual_object_id = _git(repo_root, "rev-parse", f"{entry['source_commit']}:{git_path}").decode().strip()
            actual_object_type = _git(repo_root, "cat-file", "-t", actual_object_id).decode().strip()
            if actual_object_id != entry["git_object_id"]:
                errors.append(f"{source_id}: git object ID does not match pinned source")
            if actual_object_type != entry["git_object_type"]:
                errors.append(f"{source_id}: git object type does not match pinned source")
            if entry["scope"] == "directory":
                pinned_digest = canonical_tree_digest_from_git(repo_root, entry["source_commit"], git_path)
            else:
                pinned_digest = _sha256(_git(repo_root, "show", f"{entry['source_commit']}:{git_path}"))
            if pinned_digest != digest.get("value"):
                errors.append(f"{source_id}: content digest does not match pinned commit bytes")
        except (KeyError, subprocess.CalledProcessError) as exc:
            errors.append(f"{source_id}: cannot verify pinned Git bytes: {exc}")
    authoritative = [
        entry.get("id")
        for entry in sources
        if isinstance(entry, Mapping) and entry.get("consumer_acceptance_authority") is True
    ]
    if authoritative != ["product-research-interop"]:
        errors.append("only product-research-interop may have consumer acceptance authority")
    errors.extend(validate_working_tree_digests(manifest, repo_root))
    return errors


def _is_authoritative_remote_host(host: str) -> bool:
    normalized = host.strip("[]").rstrip(".").lower()
    if not normalized or normalized in {"file", "localhost"} or normalized.endswith(".localhost"):
        return False
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        labels = normalized.split(".")
        return all(
            label
            and len(label) <= 63
            and not label.startswith("-")
            and not label.endswith("-")
            and re.fullmatch(r"[a-z0-9-]+", label)
            for label in labels
        )
    return not (address.is_loopback or address.is_unspecified or address.is_link_local)


def _normalize_remote_identity(url: Any) -> Any:
    if not isinstance(url, str) or not url.strip():
        return None
    value = url.strip().rstrip("/")
    if re.match(r"^[A-Za-z]:[\\/]", value):
        return None
    scp_match = re.fullmatch(
        r"(?:(?:[A-Za-z0-9._-]+)@)?(?P<host>\[[0-9A-Fa-f:]+\]|[A-Za-z0-9][A-Za-z0-9.-]*):(?P<path>.+)",
        value,
    )
    if scp_match and "://" not in value:
        host, path = scp_match.group("host"), scp_match.group("path")
    else:
        parsed = urlparse(value)
        if parsed.scheme not in {"https", "ssh"} or not parsed.hostname:
            return None
        host, path = parsed.hostname, parsed.path
    if not _is_authoritative_remote_host(host):
        return None
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return f"{host.strip('[]').lower()}/{path}" if path else None


def _configured_remote_identities(repo_root: Path) -> Set[str]:
    try:
        output = _git(repo_root, "config", "--get-regexp", r"^remote\..*\.url$").decode("utf-8")
    except subprocess.CalledProcessError:
        return set()
    identities: Set[str] = set()
    for line in output.splitlines():
        _, _, url = line.partition(" ")
        identity = _normalize_remote_identity(url)
        if identity:
            identities.add(identity)
    return identities


def validate_b0_status(
    status: Mapping[str, Any],
    manifest: Mapping[str, Any],
    repo_root: Path,
    *,
    closure_pending: bool = False,
) -> List[str]:
    errors: List[str] = []
    if status.get("document_kind") != "gate_status":
        errors.append("B0 status document_kind must be gate_status")
    if status.get("gate") != "B0":
        errors.append("B0 status gate must be B0")
    if status.get("status") not in {"open", "closed"}:
        errors.append("B0 top-level status must be open or closed")

    raw_items = status.get("items")
    if not isinstance(raw_items, Mapping):
        errors.append("B0 status items must be a mapping")
        items: Mapping[str, Any] = {}
    else:
        items = raw_items
        if set(items) != set(REQUIRED_B0_ITEM_IDS):
            errors.append(f"B0 status item IDs must be exactly {list(REQUIRED_B0_ITEM_IDS)}")
    item_mappings: Dict[str, Mapping[str, Any]] = {}
    for item_id in REQUIRED_B0_ITEM_IDS:
        item = items[item_id] if item_id in items else None
        if not isinstance(item, Mapping):
            errors.append(f"{item_id} status item must be a mapping")
            continue
        item_mappings[item_id] = item
        item_status = item.get("status")
        if not isinstance(item_status, str) or not item_status:
            errors.append(f"{item_id} status item must contain a non-empty status")
        if item_status == "open" and not item.get("open_reason"):
            errors.append(f"{item_id} open status must contain open_reason")
        if item_status == "closed" and "open_reason" not in item:
            errors.append(f"{item_id} closed status must contain open_reason: null")
        elif item_status == "closed" and item.get("open_reason") is not None:
            errors.append(f"{item_id} closed status must clear open_reason")
    for item_id in ("B0.1", "B0.6"):
        item = item_mappings[item_id] if item_id in item_mappings else {}
        if item.get("status") not in {"locally_satisfied", "closed"}:
            errors.append(f"{item_id} must be locally_satisfied or closed")
    for item_id in ("B0.3", "B0.4", "B0.5"):
        item = item_mappings[item_id] if item_id in item_mappings else {}
        if item.get("status") not in {"open", "closed"}:
            errors.append(f"{item_id} must be open or closed")
    b02 = item_mappings.get("B0.2", {})
    if "open_reason" not in b02:
        errors.append("B0.2 status item must contain open_reason")
    all_items_closed = len(item_mappings) == len(REQUIRED_B0_ITEM_IDS) and all(
        item.get("status") == "closed" for item in item_mappings.values()
    )
    derived_gate_status = "closed" if all_items_closed else "open"
    if status.get("status") != derived_gate_status:
        errors.append(f"B0 top-level status must be {derived_gate_status} for the declared item states")

    authority_state = manifest.get("authority_state")
    raw_sources = manifest.get("sources", [])
    if not isinstance(raw_sources, list) or any(not isinstance(entry, Mapping) for entry in raw_sources):
        errors.append("provenance sources must be mappings before B0 status can be evaluated")
        sources: List[Mapping[str, Any]] = []
    else:
        sources = raw_sources
    if authority_state not in {"local-only/provisional", "remote-pinned"}:
        errors.append(f"unknown authority_state fails closed: {authority_state!r}")
    elif authority_state == "local-only/provisional":
        if any(entry.get("origin_state") != "local-only/provisional" for entry in sources):
            errors.append("local-only authority requires local-only/provisional source entries")
        if any(entry.get("upstream_url") is not None for entry in sources):
            errors.append("local-only authority requires upstream_url: null")
        if b02.get("status") != "open" or b02.get("open_reason") != "authoritative_remote_url_absent":
            errors.append("local-only authority must keep B0.2 open solely for the absent authoritative remote URL")
    else:
        if any(entry.get("origin_state") != "authoritative-remote" for entry in sources):
            errors.append("remote-pinned authority requires authoritative-remote source entries")
        configured_remotes = _configured_remote_identities(repo_root)
        upstream_urls = [entry.get("upstream_url") for entry in sources]
        upstream_identities = [_normalize_remote_identity(url) for url in upstream_urls]
        if not upstream_identities or any(identity is None for identity in upstream_identities):
            errors.append("closing B0.2 requires an authoritative HTTPS or SSH URL for every authority entry")
        elif any(url != B0_CLOSURE_AUTHORITY_URL for url in upstream_urls):
            errors.append(f"every B0 authority URL must be exactly {B0_CLOSURE_AUTHORITY_URL}")
        canonical_identity = _normalize_remote_identity(B0_CLOSURE_AUTHORITY_URL)
        if canonical_identity not in configured_remotes:
            errors.append("the canonical B0 authority URL must match a configured Git remote before B0.2 can close")
        b02_closed = b02.get("status") == "closed" and b02.get("open_reason") is None
        historical_open_state = closure_pending and dict(b02) == B0_CLOSURE_PENDING_B02
        if not b02_closed and not historical_open_state:
            errors.append("remote-pinned authority must close B0.2 and clear its open reason")
    return errors


def _closed_report_mapping(
    value: Any,
    required_fields: frozenset[str],
    label: str,
    errors: List[str],
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        errors.append(f"{label} must be a mapping")
        return {}
    actual_fields = set(value)
    unknown = actual_fields - required_fields
    missing = required_fields - actual_fields
    if unknown:
        errors.append(f"{label} has unknown fields: {sorted(str(field) for field in unknown)}")
    if missing:
        errors.append(f"{label} is missing required fields: {sorted(missing)}")
    if any(not isinstance(field, str) for field in actual_fields):
        errors.append(f"{label} field names must be strings")
    return value


def _find_forbidden_hosted_report_keys(value: Any, prefix: str = "report") -> List[str]:
    findings: List[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            child_prefix = f"{prefix}.{key_text}"
            if key_text in FORBIDDEN_HOSTED_REPORT_KEYS:
                findings.append(child_prefix)
            findings.extend(_find_forbidden_hosted_report_keys(child, child_prefix))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_find_forbidden_hosted_report_keys(child, f"{prefix}[{index}]"))
    return findings


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


class _StrictJsonError(ValueError):
    """A deliberate rejection of JSON outside the hosted evidence contract."""


def _strict_json_object(pairs: List[tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _StrictJsonError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> Any:
    raise _StrictJsonError(f"non-standard JSON constant: {value}")


def _strict_json_loads(content: bytes) -> Any:
    return json.loads(
        content,
        object_pairs_hook=_strict_json_object,
        parse_constant=_reject_json_constant,
    )


def _canonical_json_sha256(value: Any) -> str:
    content = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256(content)


def _exact_json_value(actual: Any, expected: Any) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            _exact_json_value(actual[key], expected_value)
            for key, expected_value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _exact_json_value(actual_value, expected_value)
            for actual_value, expected_value in zip(actual, expected)
        )
    return actual == expected


def _safe_checked_in_relative_path(relative: Any) -> bool:
    if not isinstance(relative, str) or not relative or "\0" in relative:
        return False
    try:
        relative.encode("utf-8")
    except UnicodeEncodeError:
        return False
    if Path(relative).is_absolute():
        return False
    relative_path = Path(relative)
    return ".." not in relative_path.parts and relative_path.as_posix() == relative


def _committed_regular_file(
    repo_root: Path,
    commit: str,
    relative: Any,
    label: str,
) -> tuple[bytes | None, str | None]:
    if not _safe_checked_in_relative_path(relative):
        return None, f"{label} must be a normalized repository-relative path"

    parts = Path(relative).parts
    for index in range(len(parts)):
        prefix = Path(*parts[: index + 1]).as_posix()
        try:
            raw = _git(
                repo_root,
                "--no-replace-objects",
                "ls-tree",
                "-z",
                commit,
                "--",
                prefix,
            )
        except (subprocess.CalledProcessError, OSError, TypeError, ValueError, UnicodeError) as exc:
            return None, f"{label} cannot be resolved at {commit}: {exc}"

        records = [record for record in raw.split(b"\0") if record]
        if len(records) != 1:
            return None, f"{label} is missing or ambiguous at {commit}: {prefix}"

        metadata, separator, raw_path = records[0].partition(b"\t")
        try:
            decoded_path = raw_path.decode("utf-8")
            mode, object_type, _ = metadata.decode("ascii").split()
        except (UnicodeError, ValueError):
            return None, f"{label} has an invalid Git tree entry: {prefix}"
        if not separator or decoded_path != prefix:
            return None, f"{label} has an invalid Git tree entry: {prefix}"

        final = index == len(parts) - 1
        if not final and (mode != "040000" or object_type != "tree"):
            return None, f"{label} contains a symbolic-link or non-directory component: {prefix}"
        if final and (mode not in {"100644", "100755"} or object_type != "blob"):
            return None, f"{label} must identify a committed regular file"

    try:
        return (
            _git(
                repo_root,
                "--no-replace-objects",
                "cat-file",
                "blob",
                f"{commit}:{relative}",
            ),
            None,
        )
    except (subprocess.CalledProcessError, OSError, TypeError, ValueError, UnicodeError) as exc:
        return None, f"{label} cannot be read at {commit}: {exc}"


def _optional_local_artifact_path(repo_root: Path, relative: str) -> tuple[Path | None, str | None]:
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts or relative_path.as_posix() != relative:
        return None, "local probe artifact path must be a normalized repository-relative path"
    if repo_root.is_symlink() or not repo_root.is_dir():
        return None, "local probe repository root must be a regular non-symlink directory"
    root_resolved = repo_root.resolve()
    current = repo_root
    for part in relative_path.parts:
        current = current / part
        if current.is_symlink():
            return None, f"local probe artifact path component is a symbolic link: {current.relative_to(repo_root)}"
        if not current.exists():
            return None, None
        try:
            current.resolve().relative_to(root_resolved)
        except ValueError:
            return None, "local probe artifact path escapes repository root"
    if not current.is_file():
        return None, "local probe artifact path must identify a regular file when present"
    return current, None


def validate_local_probe_evidence(
    entries: Any,
    repo_root: Path,
    evaluated_commit: Any,
) -> List[str]:
    errors: List[str] = []
    if not isinstance(entries, list):
        return ["B0 report local_runtime_probes must be a list"]
    if [entry.get("backend") if isinstance(entry, Mapping) else None for entry in entries] != ["numpy", "mlx"]:
        errors.append("B0 report local_runtime_probes must contain numpy then mlx")
    for index, entry in enumerate(entries):
        entry = _closed_report_mapping(
            entry,
            B0_REPORT_PROBE_FIELDS,
            f"B0 report local_runtime_probes[{index}]",
            errors,
        )
        if not entry:
            continue
        backend = entry.get("backend")
        expected = B0_REPORT_LOCAL_PROBES[backend] if backend in B0_REPORT_LOCAL_PROBES else None
        if expected is None:
            errors.append(f"B0 report local runtime probe {index} has unknown backend {backend!r}")
            continue
        for field, expected_value in expected.items():
            actual_value = entry[field] if field in entry else None
            if actual_value != expected_value:
                errors.append(f"B0 report {backend} local probe {field} must be {expected_value}")
        if entry.get("execution_scope") != "local":
            errors.append(f"B0 report {backend} local probe must set execution_scope to local")
        if entry.get("evidence_scope") != "local_bootstrap_only":
            errors.append(f"B0 report {backend} local probe must be labeled local_bootstrap_only")
        if entry.get("qualification") != "bootstrap_probe_only":
            errors.append(f"B0 report {backend} local probe must set bootstrap_probe_only qualification")
        if entry.get("optional_local_evidence") is not True:
            errors.append(f"B0 report {backend} local probe must be optional local evidence")
        if not _valid_sha256(entry.get("sha256")):
            errors.append(f"B0 report {backend} local probe must record a SHA-256 digest")
        for field in ("backend_version", "host_os", "host_architecture"):
            value = entry[field] if field in entry else None
            if not isinstance(value, str) or not value:
                errors.append(f"B0 report {backend} local probe must record {field}")

        artifact_path, path_error = _optional_local_artifact_path(repo_root, str(expected["artifact_path"]))
        if path_error:
            errors.append(f"B0 report {backend} {path_error}")
            continue
        if artifact_path is None:
            continue
        content = artifact_path.read_bytes()
        if _sha256(content) != entry.get("sha256"):
            errors.append(f"B0 report {backend} local probe SHA-256 does not match the present artifact")
        try:
            artifact = json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"B0 report {backend} local probe artifact is not valid JSON: {exc}")
            continue
        if not isinstance(artifact, Mapping):
            errors.append(f"B0 report {backend} local probe artifact must contain a JSON object")
            continue
        if artifact.get("repository_commit") != evaluated_commit:
            errors.append(f"B0 report {backend} local probe commit does not match the evaluated implementation commit")
        if artifact.get("schema_version") != "1.0.0" or artifact.get("probe_kind") != "b0_runtime_backend_bootstrap":
            errors.append(f"B0 report {backend} local probe schema/kind is invalid")
        if artifact.get("status") != "passed" or artifact.get("qualification") != "bootstrap_probe_only":
            errors.append(f"B0 report {backend} local probe is not passed bootstrap-only evidence")
        if artifact.get("system_under_test") != expected["system"]:
            errors.append(f"B0 report {backend} local probe system does not match its canonical system")
        artifact_backend = artifact.get("backend")
        if not isinstance(artifact_backend, Mapping):
            errors.append(f"B0 report {backend} local probe backend block must be a mapping")
        else:
            if artifact_backend.get("distribution") != backend:
                errors.append(f"B0 report {backend} local probe backend distribution is inconsistent")
            if artifact_backend.get("version") != entry.get("backend_version"):
                errors.append(f"B0 report {backend} local probe backend version is inconsistent")
        artifact_host = artifact.get("host")
        if not isinstance(artifact_host, Mapping):
            errors.append(f"B0 report {backend} local probe host block must be a mapping")
        else:
            if artifact_host.get("os_name") != entry.get("host_os"):
                errors.append(f"B0 report {backend} local probe host OS is inconsistent")
            if artifact_host.get("architecture") != entry.get("host_architecture"):
                errors.append(f"B0 report {backend} local probe host architecture is inconsistent")
        artifact_manifest = artifact.get("manifest")
        if not isinstance(artifact_manifest, Mapping) or artifact_manifest.get("path") != expected["manifest_path"]:
            errors.append(f"B0 report {backend} local probe manifest path is not canonical")
        workflow = artifact.get("workflow")
        local_workflow = isinstance(workflow, Mapping) and all(
            (workflow[field] if field in workflow else None) == "local" for field in ("name", "run_id", "attempt")
        )
        if not local_workflow:
            errors.append(f"B0 report {backend} local probe does not contain local workflow placeholders")
    return errors


def _validate_hosted_probe_report_schema(entries: Any) -> List[str]:
    errors: List[str] = []
    if entries is None:
        return ["B0 report hosted_runtime_probes must contain exactly two entries"]
    if not isinstance(entries, list):
        return ["B0 report hosted_runtime_probes must be a list"]
    if len(entries) != len(B0_REPORT_HOSTED_PROBES):
        errors.append("B0 report hosted_runtime_probes must contain exactly two entries")
    actual_order = [
        entry.get("backend") if isinstance(entry, Mapping) else None
        for entry in entries
    ]
    expected_order = [probe["backend"] for probe in B0_REPORT_HOSTED_PROBES]
    if actual_order != expected_order:
        errors.append("B0 report hosted_runtime_probes must contain Linux numpy then macOS mlx")
    for index, expected in enumerate(B0_REPORT_HOSTED_PROBES):
        entry = _closed_report_mapping(
            entries[index] if index < len(entries) else None,
            B0_REPORT_HOSTED_PROBE_FIELDS,
            f"B0 report hosted_runtime_probes[{index}]",
            errors,
        )
        if not entry:
            continue
        for field, expected_value in expected.items():
            actual_value = entry[field] if field in entry else None
            if actual_value != expected_value:
                errors.append(
                    f"B0 report {expected['backend']} hosted probe {field} must be {expected_value}"
                )
    return errors


def validate_hosted_probe_evidence(
    entries: Any,
    repo_root: Path,
    evidence_commit: str | None,
) -> List[str]:
    errors: List[str] = []
    if entries is None:
        return ["B0 report hosted_runtime_probes must contain exactly two entries"]
    if not isinstance(entries, list):
        return ["B0 report hosted_runtime_probes must be a list"]
    if len(entries) != len(B0_REPORT_HOSTED_PROBES):
        errors.append("B0 report hosted_runtime_probes must contain exactly two entries")
    actual_order = [
        entry.get("backend") if isinstance(entry, Mapping) else None
        for entry in entries
    ]
    expected_order = [probe["backend"] for probe in B0_REPORT_HOSTED_PROBES]
    if actual_order != expected_order:
        errors.append("B0 report hosted_runtime_probes must contain Linux numpy then macOS mlx")

    if evidence_commit is not None:
        if not isinstance(evidence_commit, str) or re.fullmatch(r"[0-9a-f]{40}", evidence_commit) is None:
            errors.append("B0 report hosted probe evidence commit must be a full Git commit ID")
        else:
            try:
                _git(
                    repo_root,
                    "--no-replace-objects",
                    "merge-base",
                    "--is-ancestor",
                    B0_CLOSURE_HOSTED_COMMIT,
                    evidence_commit,
                )
            except subprocess.CalledProcessError as exc:
                if exc.returncode == 1:
                    errors.append(
                        "B0 closure hosted commit must be an ancestor of the evidence revision"
                    )
                else:
                    errors.append(
                        f"B0 report cannot verify hosted commit ancestry: {exc}"
                    )
            except (OSError, TypeError, ValueError, UnicodeError) as exc:
                errors.append(f"B0 report cannot verify hosted commit ancestry: {exc}")

    target_commits: List[Any] = []
    for index, expected in enumerate(B0_REPORT_HOSTED_PROBES):
        raw_entry = entries[index] if index < len(entries) else None
        entry = _closed_report_mapping(
            raw_entry,
            B0_REPORT_HOSTED_PROBE_FIELDS,
            f"B0 report hosted_runtime_probes[{index}]",
            errors,
        )
        backend = expected["backend"]
        if not entry:
            continue
        target_commits.append(entry.get("repository_commit"))
        for field, expected_value in expected.items():
            actual_value = entry[field] if field in entry else None
            if actual_value != expected_value:
                errors.append(
                    f"B0 report {backend} hosted probe {field} must be {expected_value}"
                )

        if evidence_commit is None:
            errors.append(
                f"B0 report {backend} hosted probe cannot be verified without an evidence commit"
            )
            continue
        label = f"B0 report {backend} hosted probe artifact_path"
        content, read_error = _committed_regular_file(
            repo_root,
            evidence_commit,
            entry.get("artifact_path"),
            label,
        )
        if read_error:
            errors.append(read_error)
            continue
        assert content is not None
        if _sha256(content) != entry.get("sha256"):
            errors.append(f"B0 report {backend} hosted probe SHA-256 does not match committed artifact bytes")
        try:
            artifact = _strict_json_loads(content)
        except _StrictJsonError as exc:
            errors.append(f"B0 report {backend} hosted probe artifact is not strict JSON: {exc}")
            continue
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            errors.append(f"B0 report {backend} hosted probe artifact is not valid JSON: {exc}")
            continue
        except ValueError as exc:
            errors.append(f"B0 report {backend} hosted probe artifact is not valid JSON: {exc}")
            continue
        if not isinstance(artifact, Mapping):
            errors.append(f"B0 report {backend} hosted probe artifact must contain a JSON object")
            continue

        try:
            semantic_sha256 = _canonical_json_sha256(artifact)
        except (RecursionError, TypeError, ValueError, UnicodeError) as exc:
            errors.append(
                f"B0 report {backend} hosted probe artifact has invalid JSON semantics: {exc}"
            )
            continue
        if semantic_sha256 != B0_HOSTED_PROBE_SEMANTIC_SHA256[backend]:
            errors.append(
                f"B0 report {backend} hosted probe semantic SHA-256 does not match the canonical artifact"
            )
        closure_claims = B0_HOSTED_PROBE_CLOSURE_CLAIMS[backend]
        if artifact.get("schema_version") != "1.0.0":
            errors.append(f"B0 report {backend} hosted probe schema_version is invalid")
        if artifact.get("probe_kind") != "b0_runtime_backend_bootstrap":
            errors.append(f"B0 report {backend} hosted probe probe_kind is invalid")
        if artifact.get("status") != "passed":
            errors.append(f"B0 report {backend} hosted probe status must be passed")
        if artifact.get("qualification") != "bootstrap_probe_only":
            errors.append(
                f"B0 report {backend} hosted probe qualification must be bootstrap_probe_only"
            )
        if artifact.get("system_under_test") != entry.get("system"):
            errors.append(f"B0 report {backend} hosted probe system identity is inconsistent")
        if artifact.get("repository_commit") != entry.get("repository_commit"):
            errors.append(
                f"B0 report {backend} hosted probe repository_commit is inconsistent"
            )

        artifact_backend = artifact.get("backend")
        expected_backend = {
            "class": closure_claims["backend_class"],
            "distribution": entry.get("backend"),
            "version": entry.get("backend_version"),
        }
        if not _exact_json_value(artifact_backend, expected_backend):
            errors.append(f"B0 report {backend} hosted probe backend.class/distribution/version is inconsistent")
        if artifact.get("device_class") != closure_claims["device_class"]:
            errors.append(f"B0 report {backend} hosted probe device_class is inconsistent")
        if not _exact_json_value(artifact.get("evidence"), B0_HOSTED_PROBE_EVIDENCE):
            errors.append(
                f"B0 report {backend} hosted probe evidence.class/evidence.statement is inconsistent"
            )
        if artifact.get("package_under_test") != closure_claims["package_under_test"]:
            errors.append(f"B0 report {backend} hosted probe package_under_test is inconsistent")
        if not _exact_json_value(
            artifact.get("packages_validated"),
            list(B0_HOSTED_PROBE_PACKAGES),
        ):
            errors.append(f"B0 report {backend} hosted probe packages_validated is inconsistent")
        if artifact.get("precision_mode") != closure_claims["precision_mode"]:
            errors.append(f"B0 report {backend} hosted probe precision_mode is inconsistent")
        if not _exact_json_value(artifact.get("workers"), B0_HOSTED_PROBE_WORKERS):
            errors.append(f"B0 report {backend} hosted probe workers is inconsistent")
        if not _exact_json_value(artifact.get("host"), closure_claims["host"]):
            errors.append(f"B0 report {backend} hosted probe host is inconsistent")

        expected_workflow = {
            "name": entry.get("workflow_name"),
            "run_id": entry.get("run_id"),
            "attempt": entry.get("run_attempt"),
        }
        if not _exact_json_value(artifact.get("workflow"), expected_workflow):
            errors.append(f"B0 report {backend} hosted probe workflow is inconsistent")

        operation = artifact.get("operation")
        if not isinstance(operation, Mapping):
            errors.append(
                f"B0 report {backend} hosted probe operation must be the exact closed typed mapping"
            )
        else:
            operation_fields = set(operation)
            expected_operation_fields = set(B0_HOSTED_PROBE_OPERATION)
            if operation_fields != expected_operation_fields:
                errors.append(
                    f"B0 report {backend} hosted probe operation fields must be exactly "
                    f"{sorted(expected_operation_fields)}"
                )
            for field, expected_value in B0_HOSTED_PROBE_OPERATION.items():
                if field not in operation or not _exact_json_value(
                    operation[field], expected_value
                ):
                    errors.append(
                        f"B0 report {backend} hosted probe operation.{field} must be the exact JSON value "
                        f"{expected_value!r}"
                    )

        artifact_manifest = artifact.get("manifest")
        if not isinstance(artifact_manifest, Mapping):
            errors.append(f"B0 report {backend} hosted probe manifest must be a mapping")
            continue
        if set(artifact_manifest) != {"path", "sha256"}:
            errors.append(f"B0 report {backend} hosted probe manifest has schema drift")
        if artifact_manifest.get("path") != entry.get("manifest_path"):
            errors.append(f"B0 report {backend} hosted probe manifest.path is inconsistent")
        tested_commit = entry.get("repository_commit")
        if not isinstance(tested_commit, str) or re.fullmatch(r"[0-9a-f]{40}", tested_commit) is None:
            errors.append(
                f"B0 report {backend} hosted probe repository_commit must be a full Git commit ID"
            )
            continue
        manifest_content, manifest_error = _committed_regular_file(
            repo_root,
            tested_commit,
            entry.get("manifest_path"),
            f"B0 report {backend} hosted probe manifest_path",
        )
        if manifest_error:
            errors.append(manifest_error)
        elif manifest_content is not None and _sha256(manifest_content) != artifact_manifest.get("sha256"):
            errors.append(
                f"B0 report {backend} hosted probe manifest.sha256 does not match the historical manifest"
            )

    if len(target_commits) != len(B0_REPORT_HOSTED_PROBES) or any(
        commit != B0_CLOSURE_HOSTED_COMMIT for commit in target_commits
    ):
        errors.append(
            f"B0 report hosted probes must target one shared B0 closure commit {B0_CLOSURE_HOSTED_COMMIT}"
        )
    return errors


def validate_b0_closure_state(
    report: Mapping[str, Any],
    status: Mapping[str, Any],
) -> List[str]:
    errors: List[str] = []
    if report.get("overall_state") != "closed":
        errors.append("B0 report overall_state must be closed for schema 2.0.0")
    if status.get("status") != "closed":
        errors.append("governance/b0-status.yaml top-level status must be closed for schema 2.0.0")
    blockers = report.get("blockers")
    if not isinstance(blockers, Mapping) or blockers:
        errors.append("B0 report blockers must be an empty mapping for schema 2.0.0")
    if report.get("parallel_handoff_ready") is not True:
        errors.append("B0 report parallel_handoff_ready must be true for schema 2.0.0")
    if report.get("parallel_handoff_blockers") != []:
        errors.append("B0 report parallel_handoff_blockers must be empty for schema 2.0.0")
    if report.get("next_transition") != B0_REPORT_CLOSED_NEXT_TRANSITION:
        errors.append("B0 report next_transition must be the Phase 0 interface-freeze transition")

    report_items = report.get("items")
    status_items = status.get("items")
    if not isinstance(report_items, Mapping) or set(report_items) != set(REQUIRED_B0_ITEM_IDS):
        errors.append(f"B0 report item IDs must be exactly {list(REQUIRED_B0_ITEM_IDS)}")
        report_items = {}
    if not isinstance(status_items, Mapping) or set(status_items) != set(REQUIRED_B0_ITEM_IDS):
        errors.append(f"B0 status item IDs must be exactly {list(REQUIRED_B0_ITEM_IDS)}")
        status_items = {}

    for item_id in REQUIRED_B0_ITEM_IDS:
        report_item = report_items[item_id] if item_id in report_items else None
        status_item = status_items[item_id] if item_id in status_items else None
        if not isinstance(report_item, Mapping) or not isinstance(status_item, Mapping):
            errors.append(f"B0 report/status item {item_id} must be a mapping")
            continue
        report_state = report_item.get("state")
        status_state = status_item.get("status")
        if report_state != "closed":
            errors.append(f"B0 report {item_id} state must be closed for schema 2.0.0")
        if report_item.get("reason") is not None:
            errors.append(f"B0 report {item_id} closed reason must be null")
        if status_state != "closed":
            errors.append(f"governance/b0-status.yaml {item_id} status must be closed for schema 2.0.0")
        if "open_reason" not in status_item:
            errors.append(
                f"governance/b0-status.yaml {item_id} closed status must contain open_reason: null"
            )
        elif status_item.get("open_reason") is not None:
            errors.append(f"governance/b0-status.yaml {item_id} closed open_reason must be null")
        if report_state != status_state:
            errors.append(f"B0 report {item_id} state does not match governance/b0-status.yaml")
    return errors


def validate_b0_schema_2_state(
    report: Mapping[str, Any],
    status: Mapping[str, Any],
) -> List[str]:
    errors: List[str] = []
    report = _closed_report_mapping(
        report,
        B0_REPORT_TOP_LEVEL_FIELDS,
        "B0 report",
        errors,
    )
    if report.get("schema_version") != B0_REPORT_SCHEMA_VERSION:
        errors.append(f"B0 report schema_version must be {B0_REPORT_SCHEMA_VERSION}")
    if not isinstance(status, Mapping):
        errors.append("governance/b0-status.yaml must be a mapping")
        status = {}
    else:
        if status.get("document_kind") != "gate_status":
            errors.append("governance/b0-status.yaml document_kind must be gate_status")
        if status.get("gate") != "B0":
            errors.append("governance/b0-status.yaml gate must be B0")
    errors.extend(validate_b0_closure_state(report, status))

    repository = _closed_report_mapping(
        report.get("repository"),
        B0_REPORT_REPOSITORY_FIELDS,
        "B0 report repository",
        errors,
    )
    if repository.get("branch") != "b0/close-gate":
        errors.append("B0 report repository.branch must be b0/close-gate for schema 2.0.0")

    report_items = report.get("items")
    if isinstance(report_items, Mapping):
        for item_id in REQUIRED_B0_ITEM_IDS:
            item = _closed_report_mapping(
                report_items[item_id] if item_id in report_items else None,
                B0_REPORT_ITEM_FIELDS,
                f"B0 report items.{item_id}",
                errors,
            )
            evidence_paths = item.get("evidence_paths")
            if not isinstance(evidence_paths, list) or not evidence_paths or any(
                not isinstance(path, str) for path in evidence_paths
            ):
                errors.append(
                    f"B0 report {item_id} evidence_paths must be a non-empty string list"
                )
                continue
            evidence_path_set = set(evidence_paths)
            if (
                "governance/b0-report.json" in evidence_path_set
                and item_id not in {"B0.2", "B0.5", "B0.6"}
            ):
                errors.append(
                    f"B0 report {item_id} must not use governance/b0-report.json as self-reference evidence"
                )
            required_paths = B0_REPORT_SCHEMA_2_REQUIRED_ITEM_EVIDENCE.get(item_id)
            if required_paths:
                missing_paths = required_paths - evidence_path_set
                if missing_paths:
                    errors.append(
                        f"B0 report {item_id} required evidence paths are missing: {sorted(missing_paths)}"
                    )

    errors.extend(
        _validate_hosted_probe_report_schema(report.get("hosted_runtime_probes"))
    )
    return errors


def _validate_b0_legacy_state(
    report: Mapping[str, Any],
    status: Mapping[str, Any],
) -> List[str]:
    errors: List[str] = []
    if report.get("overall_state") != "open" or status.get("status") != "open":
        errors.append("B0 report overall_state and governance/b0-status.yaml must both remain open")
    blockers = _closed_report_mapping(
        report.get("blockers"),
        frozenset(B0_REPORT_BLOCKERS),
        "B0 report blockers",
        errors,
    )
    if blockers != dict(B0_REPORT_BLOCKERS):
        errors.append("B0 report blockers must be the exact B0.2 and B0.5 blocker codes")
    if report.get("parallel_handoff_ready") is not False:
        errors.append("B0 report parallel_handoff_ready must remain false")
    if report.get("parallel_handoff_blockers") != ["B0.2", "B0.5"]:
        errors.append("B0 report parallel_handoff_blockers must be exactly [B0.2, B0.5]")
    if report.get("next_transition") != B0_REPORT_NEXT_TRANSITION:
        errors.append("B0 report next_transition does not match the required joint Phase 0 handoff")
    return errors


def _validate_b0_legacy_revision(
    report: Mapping[str, Any],
    repo_root: Path,
) -> List[str]:
    errors: List[str] = []
    try:
        revision = (
            _git(
                repo_root,
                "--no-replace-objects",
                "log",
                "-1",
                "--format=%H",
                "HEAD",
                "--",
                "governance/b0-report.json",
            )
            .decode("ascii")
            .strip()
        )
    except (subprocess.CalledProcessError, OSError, TypeError, ValueError, UnicodeError) as exc:
        return [f"B0 legacy report cannot resolve its frozen evidence revision: {exc}"]
    if revision != B0_REPORT_LEGACY_REVISION:
        errors.append(
            "B0 report schema 1.0.0 is permitted only at frozen transition revision "
            f"{B0_REPORT_LEGACY_REVISION}; found {revision or '<none>'}"
        )

    content, read_error = _committed_regular_file(
        repo_root,
        B0_REPORT_LEGACY_REVISION,
        "governance/b0-report.json",
        "frozen B0 legacy report",
    )
    if read_error or content is None:
        errors.append(read_error or "frozen B0 legacy report is unavailable")
        return errors
    try:
        frozen_report = _strict_json_loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        errors.append(f"frozen B0 legacy report is not strict JSON: {exc}")
        return errors
    if not _exact_json_value(report, frozen_report):
        errors.append("B0 report schema 1.0.0 must be the exact frozen transition record")
    return errors


def _validate_b0_schema_history(
    repo_root: Path,
    current_schema_version: str,
) -> List[str]:
    try:
        shallow = (
            _git(
                repo_root,
                "--no-replace-objects",
                "rev-parse",
                "--is-shallow-repository",
            )
            .decode("ascii")
            .strip()
        )
        if shallow != "false":
            return [
                "B0 report schema validation requires full Git history; "
                "a shallow repository cannot prove the permanent schema 2.0.0 anti-downgrade invariant"
            ]
        revisions = (
            _git(
                repo_root,
                "--no-replace-objects",
                "log",
                "--full-history",
                "--format=%H",
                "HEAD",
                "--",
                "governance/b0-report.json",
            )
            .decode("ascii")
            .splitlines()
        )
    except (subprocess.CalledProcessError, OSError, TypeError, ValueError, UnicodeError) as exc:
        return [f"B0 report cannot inspect complete committed schema history: {exc}"]

    declarations: List[tuple[str, str]] = []
    for revision in revisions:
        content, read_error = _committed_regular_file(
            repo_root,
            revision,
            "governance/b0-report.json",
            "historical B0 report",
        )
        if read_error or content is None:
            continue
        try:
            historical = _strict_json_loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError):
            continue
        if not isinstance(historical, Mapping):
            continue
        historical_schema = historical.get("schema_version")
        if historical_schema in {
            B0_REPORT_LEGACY_SCHEMA_VERSION,
            "2.0.0",
        }:
            declarations.append((revision, historical_schema))

    closure_revisions = [
        revision for revision, schema in declarations if schema == "2.0.0"
    ]
    if current_schema_version == B0_REPORT_LEGACY_SCHEMA_VERSION and closure_revisions:
        return [
            "B0 report schema downgrade from a reachable schema 2.0.0 revision is forbidden"
        ]

    legacy_revisions = [
        revision
        for revision, schema in declarations
        if schema == B0_REPORT_LEGACY_SCHEMA_VERSION
        and revision != B0_REPORT_LEGACY_REVISION
    ]
    for legacy_revision in legacy_revisions:
        for closure_revision in closure_revisions:
            try:
                _git(
                    repo_root,
                    "--no-replace-objects",
                    "merge-base",
                    "--is-ancestor",
                    closure_revision,
                    legacy_revision,
                )
            except subprocess.CalledProcessError as exc:
                if exc.returncode == 1:
                    continue
                return [
                    f"B0 report cannot verify permanent schema history ordering: {exc}"
                ]
            except (OSError, TypeError, ValueError, UnicodeError) as exc:
                return [
                    f"B0 report cannot verify permanent schema history ordering: {exc}"
                ]
            return [
                "B0 report schema downgrade from a reachable schema 2.0.0 revision is forbidden"
            ]
    return []


def validate_b0_report(report: Mapping[str, Any], status: Mapping[str, Any], repo_root: Path) -> List[str]:
    errors: List[str] = []
    schema_version = report.get("schema_version") if isinstance(report, Mapping) else None
    if not isinstance(schema_version, str) or schema_version not in (
        B0_REPORT_LEGACY_SCHEMA_VERSION,
        B0_REPORT_SCHEMA_VERSION,
    ):
        _closed_report_mapping(report, B0_REPORT_TOP_LEVEL_FIELDS, "B0 report", errors)
        errors.append(
            "B0 report schema_version must be a string equal to one of "
            f"{B0_REPORT_LEGACY_SCHEMA_VERSION} or {B0_REPORT_SCHEMA_VERSION}"
        )
        return errors
    if schema_version == B0_REPORT_LEGACY_SCHEMA_VERSION:
        report = _closed_report_mapping(
            report,
            B0_REPORT_LEGACY_TOP_LEVEL_FIELDS,
            "B0 report",
            errors,
        )
    else:
        errors.extend(validate_b0_schema_2_state(report, status))
    if not isinstance(status, Mapping):
        if schema_version == B0_REPORT_LEGACY_SCHEMA_VERSION:
            errors.append("governance/b0-status.yaml must be a mapping")
        status = {}
    if report.get("report_kind") != B0_REPORT_KIND:
        errors.append(f"B0 report report_kind must be {B0_REPORT_KIND}")
    evaluated_at = report.get("evaluated_at")
    if not isinstance(evaluated_at, str) or not UTC_TIMESTAMP.match(evaluated_at):
        errors.append("B0 report evaluated_at must be a UTC ISO-8601 timestamp")
    if schema_version == B0_REPORT_LEGACY_SCHEMA_VERSION:
        for path in _find_forbidden_hosted_report_keys(report):
            errors.append(f"B0 report contains forbidden hosted evidence field: {path}")
        errors.extend(_validate_b0_legacy_revision(report, repo_root))
    errors.extend(_validate_b0_schema_history(repo_root, schema_version))

    repository = _closed_report_mapping(
        report.get("repository"),
        B0_REPORT_REPOSITORY_FIELDS,
        "B0 report repository",
        errors,
    )
    if repository and any(
        field not in repository or not isinstance(repository[field], str) for field in B0_REPORT_REPOSITORY_FIELDS
    ):
        errors.append("B0 report repository fields must all be strings")
    evaluated_commit = repository.get("evaluated_commit")
    evaluated_tree = repository.get("evaluated_tree")
    if not isinstance(evaluated_commit, str) or re.fullmatch(r"[0-9a-f]{40}", evaluated_commit) is None:
        errors.append("B0 report evaluated_commit must be a full Git commit ID")
    if not isinstance(evaluated_tree, str) or re.fullmatch(r"[0-9a-f]{40}", evaluated_tree) is None:
        errors.append("B0 report evaluated_tree must be a full Git tree ID")
    if repository.get("relationship") != "implementation commit immediately before the evidence-only report commit":
        errors.append("B0 report must document the implementation/evidence-only commit relationship")
    evidence_commit: str | None = None
    if isinstance(evaluated_commit, str) and re.fullmatch(r"[0-9a-f]{40}", evaluated_commit):
        try:
            actual_tree = _git(
                repo_root,
                "--no-replace-objects",
                "rev-parse",
                f"{evaluated_commit}^{{tree}}",
            ).decode().strip()
            if actual_tree != evaluated_tree:
                errors.append("B0 report evaluated_tree does not match evaluated_commit")
            # Anchor all historical claims to the committed evidence-only
            # revision, not to the moving HEAD/working tree: the report must
            # stay verifiable on merge commits and on every later commit.
            recorded = (
                _git(
                    repo_root,
                    "--no-replace-objects",
                    "log",
                    "-1",
                    "--format=%H",
                    "HEAD",
                    "--",
                    "governance/b0-report.json",
                )
                .decode()
                .strip()
            )
            if not recorded:
                errors.append("B0 report has no committed evidence-only revision reachable from HEAD")
            elif recorded == evaluated_commit:
                errors.append(
                    "B0 report evaluated_commit must be the direct parent of the evidence-only commit and must not equal it"
                )
            else:
                committed_report = _git(
                    repo_root,
                    "--no-replace-objects",
                    "show",
                    f"{recorded}:governance/b0-report.json",
                )
                if committed_report != (repo_root / "governance/b0-report.json").read_bytes():
                    errors.append("B0 report working-tree content must match its committed evidence-only revision")
                try:
                    frozen_report = _strict_json_loads(committed_report)
                except (
                    UnicodeDecodeError,
                    json.JSONDecodeError,
                    RecursionError,
                    ValueError,
                ) as exc:
                    errors.append(f"B0 report committed evidence is not strict JSON: {exc}")
                else:
                    if (
                        schema_version == B0_REPORT_SCHEMA_VERSION
                        and not _exact_json_value(report, frozen_report)
                    ):
                        errors.append(
                            "B0 report mapping must match the frozen evidence report"
                        )
                parent_line = (
                    _git(
                        repo_root,
                        "--no-replace-objects",
                        "rev-list",
                        "--parents",
                        "-n",
                        "1",
                        recorded,
                    )
                    .decode("ascii")
                    .split()
                )
                if len(parent_line) != 2:
                    errors.append(
                        "B0 report evidence-only commit must be a single-parent direct child"
                    )
                elif parent_line[1] != evaluated_commit:
                    errors.append("B0 report evaluated_commit must be the direct parent of the evidence-only commit")
                else:
                    evidence_commit = recorded
                    changed = frozenset(
                        line
                        for line in _git(
                            repo_root,
                            "--no-replace-objects",
                            "diff",
                            "--name-only",
                            f"{evaluated_commit}..{recorded}",
                        )
                        .decode("utf-8")
                        .splitlines()
                        if line
                    )
                    if changed != B0_EVIDENCE_ONLY_PATHS:
                        errors.append(
                            "B0 report evidence-only commit diff must contain exactly "
                            f"{sorted(B0_EVIDENCE_ONLY_PATHS)}; found {sorted(changed)}"
                        )
        except subprocess.CalledProcessError as exc:
            errors.append(f"B0 report cannot verify evaluated Git identity: {exc}")

    if schema_version == B0_REPORT_LEGACY_SCHEMA_VERSION:
        errors.extend(_validate_b0_legacy_state(report, status))

    status_items = status.get("items")
    report_items = report.get("items")
    if not isinstance(status_items, Mapping) or not isinstance(report_items, Mapping):
        errors.append("B0 report and governance/b0-status.yaml items must be mappings")
        status_items = {}
        report_items = {}
    elif set(report_items) != set(REQUIRED_B0_ITEM_IDS):
        errors.append(f"B0 report item IDs must be exactly {list(REQUIRED_B0_ITEM_IDS)}")
    referenced_paths: Set[str] = set()
    local_artifact_paths = {entry["artifact_path"] for entry in B0_REPORT_LOCAL_PROBES.values()}
    non_digest_evidence_paths = set(local_artifact_paths)
    if schema_version == B0_REPORT_SCHEMA_VERSION:
        non_digest_evidence_paths.add("governance/b0-report.json")
    for item_id in REQUIRED_B0_ITEM_IDS:
        report_item = _closed_report_mapping(
            report_items[item_id] if item_id in report_items else None,
            B0_REPORT_ITEM_FIELDS,
            f"B0 report items.{item_id}",
            errors,
        )
        status_item = status_items[item_id] if item_id in status_items else None
        if not report_item:
            continue
        if schema_version == B0_REPORT_LEGACY_SCHEMA_VERSION:
            if not isinstance(status_item, Mapping):
                errors.append(f"B0 report/status item {item_id} must be a mapping")
                continue
            if report_item.get("state") != status_item.get("status"):
                errors.append(f"B0 report {item_id} state does not match governance/b0-status.yaml")
            expected_reason = status_item.get("open_reason") if status_item.get("status") == "open" else None
            if report_item.get("reason") != expected_reason:
                errors.append(f"B0 report {item_id} reason does not match governance/b0-status.yaml")
        evidence_paths = report_item.get("evidence_paths")
        if not isinstance(evidence_paths, list) or not evidence_paths or any(not isinstance(path, str) for path in evidence_paths):
            errors.append(f"B0 report {item_id} evidence_paths must be a non-empty string list")
            continue
        evidence_path_set = set(evidence_paths)
        if (
            schema_version == B0_REPORT_LEGACY_SCHEMA_VERSION
            and "governance/b0-report.json" in evidence_path_set
        ):
            errors.append(
                "B0 report schema 1.0.0 evidence must not self-reference governance/b0-report.json"
            )
        referenced_paths.update(
            path for path in evidence_paths if path not in non_digest_evidence_paths
        )

    workflows = report.get("workflows")
    if not isinstance(workflows, list):
        errors.append("B0 report workflows must be a list")
    else:
        for index, workflow in enumerate(workflows):
            workflow = _closed_report_mapping(
                workflow,
                B0_REPORT_WORKFLOW_FIELDS,
                f"B0 report workflows[{index}]",
                errors,
            )
            actions = workflow.get("actions")
            if not isinstance(actions, list) or any(not isinstance(action, str) for action in actions):
                errors.append(f"B0 report workflows[{index}].actions must be a string list")
    if workflows != list(B0_REPORT_WORKFLOWS):
        errors.append("B0 report workflows do not match the immutable workflow/action/runner contracts")
    else:
        referenced_paths.update(workflow["path"] for workflow in B0_REPORT_WORKFLOWS)

    probes = report.get("local_runtime_probes")
    errors.extend(validate_local_probe_evidence(probes, repo_root, evaluated_commit))
    if schema_version == B0_REPORT_SCHEMA_VERSION:
        errors.extend(
            validate_hosted_probe_evidence(
                report.get("hosted_runtime_probes"),
                repo_root,
                evidence_commit,
            )
        )

    checked_in = report.get("checked_in_evidence")
    if not isinstance(checked_in, Mapping):
        errors.append("B0 report checked_in_evidence must be a path-to-SHA-256 mapping")
        checked_in = {}
    if "governance/b0-report.json" in checked_in:
        errors.append("B0 report must not contain a self-referential digest")
    referenced_paths.update({"CONSOLIDATED_PLAN.md", "PARALLEL_WORK_GUIDE.md", "governance/b0-status.yaml"})
    if set(checked_in) != referenced_paths:
        errors.append("B0 report checked_in_evidence paths must exactly cover every referenced checked-in evidence path")
    for relative, expected_digest in checked_in.items():
        if not _valid_sha256(expected_digest):
            errors.append(f"B0 report checked-in evidence {relative} must record a SHA-256 digest")
            continue
        if not _safe_checked_in_relative_path(relative):
            errors.append(f"B0 report checked-in evidence path is missing, unsafe, or not a regular file: {relative}")
            continue
        if evidence_commit is None:
            errors.append(f"B0 report checked-in evidence cannot be verified without a valid evidence-only commit: {relative}")
            continue
        # Digests describe regular evidence files as frozen at the evidence-only
        # commit; later development may legitimately change the working tree.
        content, read_error = _committed_regular_file(
            repo_root,
            evidence_commit,
            relative,
            f"B0 report checked-in evidence path {relative}",
        )
        if read_error:
            errors.append(read_error)
            continue
        assert content is not None
        if _sha256(content) != expected_digest:
            errors.append(f"B0 report checked-in evidence SHA-256 does not match: {relative}")

    verification = _closed_report_mapping(
        report.get("verification"),
        B0_REPORT_VERIFICATION_FIELDS,
        "B0 report verification",
        errors,
    )
    expected_commands = [{"command": command, "result": "pass"} for command in B0_REPORT_VERIFICATION_COMMANDS]
    if verification:
        summary = _closed_report_mapping(
            verification.get("summary"),
            B0_REPORT_VERIFICATION_SUMMARY_FIELDS,
            "B0 report verification.summary",
            errors,
        )
        commands = verification.get("commands")
        if not isinstance(commands, list):
            errors.append("B0 report verification.commands must be a list")
        else:
            for index, command in enumerate(commands):
                _closed_report_mapping(
                    command,
                    B0_REPORT_VERIFICATION_COMMAND_FIELDS,
                    f"B0 report verification.commands[{index}]",
                    errors,
                )
        if verification.get("overall") != "pass":
            errors.append("B0 report verification overall result must be pass")
        if commands != expected_commands:
            errors.append("B0 report verification commands/results do not match the full required local command set")
        expected_summary = {"passed": len(B0_REPORT_VERIFICATION_COMMANDS), "failed": 0}
        if summary != expected_summary or any(type(summary[field]) is not int for field in summary):
            errors.append("B0 report verification summary must count every required command as passed")
    return errors


def _load_yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def _load_json(path: Path) -> Dict[str, Any]:
    data = _strict_json_loads(path.read_bytes())
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate_repository(repo_root: Path) -> List[str]:
    errors: List[str] = []
    active = find_active_execution_plans(repo_root)
    if active != [Path("CONSOLIDATED_PLAN.md")]:
        errors.append(f"active execution plans must be exactly CONSOLIDATED_PLAN.md; found {[str(path) for path in active]}")
    errors.extend(validate_root_plan_filenames(repo_root))
    errors.extend(validate_plan_metadata(repo_root))
    errors.extend(validate_archived_plans(repo_root))
    plan_path = repo_root / "CONSOLIDATED_PLAN.md"
    if not plan_path.is_file():
        errors.append("CONSOLIDATED_PLAN.md is missing")
    else:
        metadata = read_frontmatter(plan_path)
        expected_metadata = {"document_kind": "execution_plan", "status": "active", "revision": 2}
        for key, value in expected_metadata.items():
            if (metadata[key] if key in metadata else None) != value:
                errors.append(f"CONSOLIDATED_PLAN.md frontmatter must set {key}: {value}")
        if metadata.get("b0_repository_model") != EXPECTED_B0_REPOSITORY_MODEL:
            errors.append("CONSOLIDATED_PLAN.md must declare the normative B0 repository model")
    if (repo_root / "LAB_PLAN.md").exists():
        errors.append("legacy root LAB_PLAN.md must be absent")
    manifest_path = repo_root / "governance/authority-provenance.yaml"
    status_path = repo_root / "governance/b0-status.yaml"
    try:
        manifest = _load_yaml(manifest_path)
        errors.extend(validate_provenance(manifest, repo_root))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        errors.append(f"cannot load provenance manifest: {exc}")
        manifest = {}
    try:
        status = _load_yaml(status_path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        errors.append(f"cannot load B0 status: {exc}")
        status = {}
    report_path = repo_root / "governance/b0-report.json"
    try:
        report = _load_json(report_path)
        report_loaded = True
    except (OSError, ValueError, json.JSONDecodeError, RecursionError) as exc:
        errors.append(f"cannot load B0 integration report: {exc}")
        report = {}
        report_loaded = False
    closure_pending = (
        report.get("schema_version") == B0_REPORT_LEGACY_SCHEMA_VERSION
        and report.get("overall_state") == "open"
    )
    errors.extend(validate_b0_status(status, manifest, repo_root, closure_pending=closure_pending))
    if report_loaded:
        errors.extend(validate_b0_report(report, status, repo_root))
    for required_doc in ("SPEC_UPGRADE_PROCESS.md", "SPEC_TRACEABILITY.md"):
        if not (repo_root / "governance" / required_doc).is_file():
            errors.append(f"governance/{required_doc} is missing")
    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    errors = validate_repository(repo_root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Repository governance policy: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
