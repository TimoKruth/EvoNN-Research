#!/usr/bin/env python3
"""Fail-closed validation for the repository's plan and authority controls."""

from __future__ import annotations

import hashlib
import ipaddress
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


def validate_b0_status(status: Mapping[str, Any], manifest: Mapping[str, Any], repo_root: Path) -> List[str]:
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
        if item_status == "closed" and item.get("open_reason") is not None:
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
        upstream_identities = [_normalize_remote_identity(entry.get("upstream_url")) for entry in sources]
        if not upstream_identities or any(identity is None for identity in upstream_identities):
            errors.append("closing B0.2 requires an authoritative HTTPS or SSH URL for every authority entry")
        elif any(identity not in configured_remotes for identity in upstream_identities):
            errors.append("every authority URL must match a configured Git remote before B0.2 can close")
        if b02.get("status") != "closed" or b02.get("open_reason") is not None:
            errors.append("remote-pinned authority must close B0.2 and clear its open reason")
    return errors


def _load_yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
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
        errors.extend(validate_b0_status(status, manifest, repo_root))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        errors.append(f"cannot load B0 status: {exc}")
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
