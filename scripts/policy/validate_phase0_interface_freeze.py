#!/usr/bin/env python3
"""Fail-closed validation for the co-signed Phase 0 interface freeze."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any

import yaml
from yaml.events import AliasEvent
from yaml.nodes import MappingNode, SequenceNode
from yaml.tokens import AliasToken, AnchorToken, DocumentStartToken, TagToken


SCHEMA_VERSION = "1.0.0"
FREEZE_ID = "phase0-interface-freeze-v1"
STATUS_PENDING = "approved_pending_merge"
STATUS_VERIFIED = "merged_verified"
CANONICAL_BASE = "b22316d3dea7e0f01ee8aa359f4786897b0680ba"
APPROVED_COMMIT = "b720ea6461c970e3875f8ef735e3e63cf680b660"
APPROVED_TREE = "f1c5742c2581d270af05714b5ef8514c3f49d996"
DIGEST_METHOD = "canonical-sha256-file-set-v1"
MAX_YAML_BYTES = 1024 * 1024
MAX_YAML_COLLECTION_DEPTH = 64
MAX_YAML_NODES = 10_000
GIT_OVERRIDE_VARIABLES = ("GIT_REPLACE_REF_BASE", "GIT_GRAFT_FILE", "GIT_SHALLOW_FILE")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

TOP_LEVEL_FIELDS = (
    "schema_version",
    "document_kind",
    "phase",
    "freeze_id",
    "status",
    "supersedes",
    "canonical_base_commit",
    "approved_commit",
    "approved_tree",
    "digest_method",
    "frozen_surfaces",
    "reviews",
    "amendment_rule",
    "merge_verification",
    "lane_authorization",
)
SURFACE_FIELDS = (
    "surface_id",
    "version_id",
    "direction",
    "source_documents",
    "public_modules",
    "frozen_paths",
    "sha256",
)
MODULE_FIELDS = ("module", "schema_version", "public_symbols", "callable_signatures")
REVIEW_FIELDS = (
    "lane",
    "role",
    "reviewer",
    "subject",
    "reviewed_commit",
    "reviewed_tree",
    "reviewed_digests",
    "evidence_path",
    "evidence_sha256",
    "independent_review",
    "decision",
    "findings",
)
FINDING_FIELDS = ("critical", "important", "specification", "frozen_correctness", "minor")
AMENDMENT_FIELDS = (
    "frozen_byte_or_mode_change_invalidates_current_freeze",
    "requires_new_freeze_version",
    "next_record_must_supersede",
    "requires_fresh_lane_a_review",
    "requires_fresh_lane_b_review",
    "requires_joint_mini_review",
    "replacement_freeze_must_be_merged_before_lane_creation",
)
MERGE_FIELDS = ("target_branch", "status", "canonical_merge_commit", "verified_at")
AUTHORIZATION_FIELDS = ("authorized", "reason")
DIGESTS = {
    "canonical_digest_rng": "1806b230d6d218154898f5db8eae4089ffda07bfdf8c395d3523946a2f9fb7bc",
    "export_models": "b18bcdcc8fd8e4cbb6d9dfb1f82c0d998a1f3fedce927991d79388139c2275fc",
    "catalog_loaders": "81cf090ba61b1bfb1bdbf4a5e74c9fe46bfe34f36dcc5c44f72cd4f5cb33edc5",
}
FROZEN_PATHS = {
    "canonical_digest_rng": (
        "EvoNN-Shared/src/evonn_shared/canonical.py",
        "EvoNN-Shared/src/evonn_shared/rng.py",
        "EvoNN-Shared/tests/golden/canonical-v1.json",
        "EvoNN-Shared/tests/test_canonical.py",
        "EvoNN-Shared/tests/test_rng.py",
        "tests/contracts/test_phase0_shared_interfaces.py",
    ),
    "export_models": (
        "EvoNN-Shared/src/evonn_shared/budgets.py",
        "EvoNN-Shared/src/evonn_shared/exports.py",
        "EvoNN-Shared/src/evonn_shared/telemetry.py",
        "EvoNN-Shared/tests/fixtures/invalid/b0-capability.json",
        "EvoNN-Shared/tests/fixtures/invalid/product-evaluation.json",
        "EvoNN-Shared/tests/fixtures/invalid/wrong-schema.json",
        "EvoNN-Shared/tests/fixtures/valid/manifest.json",
        "EvoNN-Shared/tests/fixtures/valid/results.json",
        "EvoNN-Shared/tests/fixtures/valid/summary.json",
        "EvoNN-Shared/tests/golden/exports/manifest.json",
        "EvoNN-Shared/tests/golden/exports/results.json",
        "EvoNN-Shared/tests/golden/exports/summary.json",
        "EvoNN-Shared/tests/test_budgets.py",
        "EvoNN-Shared/tests/test_exports.py",
        "EvoNN-Shared/tests/test_telemetry.py",
        "tests/contracts/test_phase0_shared_interfaces.py",
    ),
    "catalog_loaders": (
        "EvoNN-Shared/src/evonn_shared/benchmarks.py",
        "EvoNN-Shared/src/evonn_shared/catalog.py",
        "EvoNN-Shared/tests/fixtures/catalog/canonical/catalog/canonical_ids.yaml",
        "EvoNN-Shared/tests/fixtures/catalog/canonical/catalog/contract_alpha_classification.yaml",
        "EvoNN-Shared/tests/fixtures/catalog/canonical/catalog/contract_beta_regression.yaml",
        "EvoNN-Shared/tests/fixtures/catalog/canonical/suites/parity/contract_parity_pack.yaml",
        "EvoNN-Shared/tests/fixtures/catalog/fallback-a/contract_fallback_sequence.yaml",
        "EvoNN-Shared/tests/fixtures/catalog/fallback-packs/contract_fallback_pack.yaml",
        "EvoNN-Shared/tests/fixtures/catalog/invalid/duplicate_nested.yaml",
        "EvoNN-Shared/tests/fixtures/catalog/invalid/duplicate_top.yaml",
        "EvoNN-Shared/tests/fixtures/catalog/invalid/registry-mismatch/catalog/canonical_ids.yaml",
        "EvoNN-Shared/tests/fixtures/catalog/invalid/registry-mismatch/catalog/contract_registry_mismatch.yaml",
        "EvoNN-Shared/tests/fixtures/catalog/invalid/unknown_field.yaml",
        "EvoNN-Shared/tests/test_catalog.py",
        "shared-benchmarks/catalog/canonical_ids.yaml",
        "tests/contracts/test_phase0_shared_interfaces.py",
    ),
}
SOURCE_DOCUMENTS = {
    "canonical_digest_rng": (
        "claude-spec/04-telemetry-and-artifacts.md",
        "CONSOLIDATED_PLAN.md",
        "tests/contracts/test_phase0_shared_interfaces.py",
    ),
    "export_models": (
        "claude-spec/03-budget-and-fairness.md",
        "claude-spec/04-telemetry-and-artifacts.md",
        "CONSOLIDATED_PLAN.md",
        "tests/contracts/test_phase0_shared_interfaces.py",
    ),
    "catalog_loaders": (
        "claude-spec/02-shared-benchmarks.md",
        "CONSOLIDATED_PLAN.md",
        "tests/contracts/test_phase0_shared_interfaces.py",
    ),
}
PUBLIC_MODULES = {
    "canonical_digest_rng": (
        {
            "module": "evonn_shared.canonical",
            "schema_version": None,
            "public_symbols": (
                "AbsolutePathError", "CANONICAL_ENCODING", "CanonicalIdentityError",
                "CanonicalScalar", "CanonicalValue", "IntegerOutOfRangeError",
                "InvalidBytePayloadError", "InvalidDigestFieldError", "InvalidMappingKeyError",
                "InvalidSchemaVersionError", "InvalidUnicodeError", "NonFiniteFloatError",
                "NormalizedKeyCollisionError", "UnsupportedCanonicalTypeError", "VolatileFieldError",
                "canonical_bytes", "canonical_sha256", "sha256_bytes",
            ),
            "callable_signatures": (
                "canonical_bytes(value: CanonicalValue, *, schema_version: str) -> bytes",
                'canonical_sha256(value: CanonicalValue, *, schema_version: str, digest_field: str | None = "digest") -> str',
                "sha256_bytes(payload: bytes | bytearray | memoryview) -> str",
            ),
        },
        {
            "module": "evonn_shared.rng",
            "schema_version": None,
            "public_symbols": ("InvalidRootSeedError", "InvalidStreamNameError", "StreamName", "derive_stream"),
            "callable_signatures": ("derive_stream(root_seed: int, name: StreamName) -> int",),
        },
    ),
    "export_models": (
        {
            "module": "evonn_shared.budgets",
            "schema_version": None,
            "public_symbols": (
                "BenchmarkSurfaceBudget", "BudgetAccounting", "BudgetDeclaration", "ContractModel",
                "EvaluationBudget", "EvaluationStage", "FidelityBudget", "FidelityStage",
                "HardwareEnvelope", "LadderTier", "ModelArtifactBudget", "TrainingBudget", "WallClockBudget",
            ),
            "callable_signatures": (),
        },
        {
            "module": "evonn_shared.telemetry",
            "schema_version": None,
            "public_symbols": (
                "AggregateMetric", "ArtifactReference", "BackendClass", "BenchmarkResult", "BestResult",
                "Coverage", "FairnessFlag", "FairnessSeverity", "FloatMeasurement", "IntegerMeasurement",
                "MeasurementProvenance", "MetricDirection", "MetricValue", "ResultStatus", "RuntimeMetadata",
                "SeedCostAccounting", "SeedingLadder", "SeedingMetadata", "SeedOverlapPolicy", "SystemId",
                "TaskKind", "RunTiming", "WorkerTopology",
            ),
            "callable_signatures": (),
        },
        {
            "module": "evonn_shared.exports",
            "schema_version": "1.0.0",
            "public_symbols": (
                "EXPORT_SCHEMA_VERSION", "MANIFEST_FILENAME", "RESULTS_FILENAME", "SUMMARY_FILENAME",
                "ExportDigests", "Manifest", "Results", "RunClass", "RunStatus", "RunSummary", "write_export",
            ),
            "callable_signatures": (
                "write_export(directory: Path, manifest: Manifest, results: Results, summary: RunSummary) -> ExportDigests",
            ),
        },
    ),
    "catalog_loaders": (
        {
            "module": "evonn_shared.catalog",
            "schema_version": "1.0.0",
            "public_symbols": (
                "CATALOG_SCHEMA_VERSION", "BenchmarkStatus", "InputModality", "CeilingTiePolicy",
                "PrimaryMetric", "MetricCeiling", "BenchmarkSpec", "CanonicalIdEntry", "CanonicalIdRegistry",
                "PackBudgetPolicy", "BenchmarkPack", "LadderTier", "TaskKind", "MetricDirection", "SystemId",
                "CatalogError", "InvalidCatalogIdentifierError", "UnsafeCatalogPathError",
                "DuplicateCatalogDefinitionError", "InvalidCatalogYamlError", "InvalidCatalogModelError",
                "CatalogRegistryMismatchError", "BenchmarkNotFoundError", "PackNotFoundError",
                "UnknownPackBenchmarkError", "get_benchmark", "list_benchmarks", "resolve_pack_path",
                "load_parity_pack",
            ),
            "callable_signatures": (
                "get_benchmark(benchmark_id: str, *, shared_root: Path | None = None, fallback_catalog_dirs: Sequence[Path] = ()) -> BenchmarkSpec",
                "list_benchmarks(*, shared_root: Path | None = None, fallback_catalog_dirs: Sequence[Path] = ()) -> tuple[BenchmarkSpec, ...]",
                "resolve_pack_path(pack_name: str, *, shared_root: Path | None = None, fallback_pack_dirs: Sequence[Path] = ()) -> Path",
                "load_parity_pack(pack_name: str, *, shared_root: Path | None = None, fallback_pack_dirs: Sequence[Path] = (), fallback_catalog_dirs: Sequence[Path] = ()) -> BenchmarkPack",
            ),
        },
    ),
}
SURFACE_DIRECTIONS = {
    "canonical_digest_rng": "lane_a_to_lane_b",
    "export_models": "lane_a_to_lane_b",
    "catalog_loaders": "lane_b_to_lane_a",
}
REVIEWS = (
    {
        "lane": "lane_a",
        "role": "lane_a_contract_owner",
        "reviewer": "phase0-lane-a-producer-aprime-reviewer-20260721",
        "subject": "phase0-frozen-surface-a-prime-lane-a-producer-review",
        "evidence_path": "reviews/2026-07-21-phase0-lane-a-producer-review.md",
        "evidence_sha256": "9299b5a0e3aef5ac5d2dabe053ca205783f15920605dde57d6b5964f69a66833",
    },
    {
        "lane": "lane_b",
        "role": "lane_b_contract_owner",
        "reviewer": "phase0-lane-b-consumer-aprime-reviewer-20260721",
        "subject": "phase0-frozen-surface-aprime-lane-b-consumer-review",
        "evidence_path": "reviews/2026-07-21-phase0-lane-b-consumer-review.md",
        "evidence_sha256": "f82e42b230fb60f8d1e58d9f072f3aba43f2375fe9578a4854987fbc0291072c",
    },
)
AMENDMENT_RULE = {
    "frozen_byte_or_mode_change_invalidates_current_freeze": True,
    "requires_new_freeze_version": True,
    "next_record_must_supersede": FREEZE_ID,
    "requires_fresh_lane_a_review": True,
    "requires_fresh_lane_b_review": True,
    "requires_joint_mini_review": True,
    "replacement_freeze_must_be_merged_before_lane_creation": True,
}
PENDING_MERGE = {
    "target_branch": "main",
    "status": "pending",
    "canonical_merge_commit": None,
    "verified_at": None,
}
PENDING_AUTHORIZATION = {
    "authorized": False,
    "reason": "freeze_pull_request_not_merged_and_canonical_merge_not_verified",
}
VERIFIED_AUTHORIZATION = {
    "authorized": True,
    "reason": "freeze_pull_request_merged_and_canonical_merge_verified",
}
BINDING_PATHS = frozenset(
    {
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
    }
)
HISTORICAL_B0_PATHS = (
    ".superpowers/sdd/task-6-report.md",
    "governance/b0-report.json",
    "governance/b0-status.yaml",
    "reviews/2026-07-19-b0-closure-review.md",
)
PROHIBITED_REF = re.compile(
    r"(?:^|/)(?:agent/p0-lane-a-[^/]+|agent/p0-lane-b-[^/]+|agent/p0-integrate)$"
)
MARKER_BEGIN = "<!-- phase0-interface-freeze:begin -->"
MARKER_END = "<!-- phase0-interface-freeze:end -->"
MARKER_BODY = """```yaml
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
status: approved_pending_merge
lane_authorization: false
lane_branches: none
next_sequence: protected PR merge → verify canonical merge → attestation → only then create lane/integration branches
joint_boundary: WP-0.10 and the Phase 0 exit remain joint
```"""


class _StrictLoader(yaml.SafeLoader):
    def __init__(self, stream: Any) -> None:
        super().__init__(stream)
        self.collection_depth = 0
        self.composed_nodes = 0

    def compose_node(self, parent: Any, index: Any) -> Any:
        event = self.peek_event()
        if isinstance(event, AliasEvent):
            raise yaml.composer.ComposerError(None, None, "aliases and anchors are forbidden", event.start_mark)
        if self.composed_nodes >= MAX_YAML_NODES:
            raise yaml.composer.ComposerError(None, None, "YAML node limit exceeded", event.start_mark)
        self.composed_nodes += 1
        return super().compose_node(parent, index)

    def compose_mapping_node(self, anchor: Any) -> MappingNode:
        event = self.peek_event()
        self.collection_depth += 1
        try:
            if self.collection_depth > MAX_YAML_COLLECTION_DEPTH:
                raise yaml.composer.ComposerError(None, None, "YAML collection depth limit exceeded", event.start_mark)
            return super().compose_mapping_node(anchor)
        finally:
            self.collection_depth -= 1

    def compose_sequence_node(self, anchor: Any) -> SequenceNode:
        event = self.peek_event()
        self.collection_depth += 1
        try:
            if self.collection_depth > MAX_YAML_COLLECTION_DEPTH:
                raise yaml.composer.ComposerError(None, None, "YAML collection depth limit exceeded", event.start_mark)
            return super().compose_sequence_node(anchor)
        finally:
            self.collection_depth -= 1

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[Any, Any]:
        self.flatten_mapping(node)
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in mapping
            except TypeError as exc:
                raise yaml.constructor.ConstructorError(None, None, "unhashable YAML key", key_node.start_mark) from exc
            if duplicate:
                raise yaml.constructor.ConstructorError(None, None, f"duplicate YAML key: {key!r}", key_node.start_mark)
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


_StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _StrictLoader.construct_mapping)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _error_text(exc: BaseException) -> str:
    return str(exc).replace("\n", " ").strip()


def load_phase0_interface_freeze(path: Path) -> Mapping[str, Any]:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read Phase 0 interface freeze record: {_error_text(exc)}") from None
    if len(content) > MAX_YAML_BYTES:
        raise ValueError("Phase 0 interface freeze YAML exceeds size limit")
    if b"\0" in content:
        raise ValueError("Phase 0 interface freeze YAML contains NUL")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("Phase 0 interface freeze YAML must be valid UTF-8") from None
    try:
        tokens = list(yaml.scan(text, Loader=_StrictLoader))
    except yaml.YAMLError as exc:
        raise ValueError(f"Phase 0 interface freeze YAML is invalid: {_error_text(exc)}") from None
    if any(isinstance(token, (AnchorToken, AliasToken)) for token in tokens):
        raise ValueError("Phase 0 interface freeze YAML aliases and anchors are forbidden")
    if any(isinstance(token, TagToken) for token in tokens):
        raise ValueError("Phase 0 interface freeze custom YAML tags are forbidden")
    if sum(isinstance(token, DocumentStartToken) for token in tokens) > 1:
        raise ValueError("Phase 0 interface freeze must contain exactly one YAML document")
    try:
        documents = list(yaml.load_all(text, Loader=_StrictLoader))
    except (yaml.YAMLError, RecursionError, ValueError) as exc:
        message = _error_text(exc)
        if "duplicate YAML key" in message:
            raise ValueError(message) from None
        if "depth limit" in message:
            raise ValueError("Phase 0 interface freeze YAML collection depth limit exceeded") from None
        if "node limit" in message:
            raise ValueError("Phase 0 interface freeze YAML node limit exceeded") from None
        raise ValueError(f"Phase 0 interface freeze YAML is invalid: {message}") from None
    if len(documents) != 1:
        raise ValueError("Phase 0 interface freeze must contain exactly one YAML document")
    value = documents[0]
    if not isinstance(value, Mapping):
        raise ValueError("Phase 0 interface freeze root must be a mapping")
    return value


def _git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    if "GIT_REPLACE_REF_BASE" in environment:
        del environment["GIT_REPLACE_REF_BASE"]
    if "GIT_GRAFT_FILE" in environment:
        del environment["GIT_GRAFT_FILE"]
    if "GIT_SHALLOW_FILE" in environment:
        del environment["GIT_SHALLOW_FILE"]
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    return environment


def _git(repo_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        env=_git_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def _git_text(repo_root: Path, *args: str) -> str:
    return _git(repo_root, *args).stdout.decode("utf-8")


def _safe_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or value.strip() != value or "\0" in value:
        return False
    try:
        value.encode("utf-8")
    except UnicodeError:
        return False
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts and path.as_posix() == value


def _mapping(value: Any, fields: Sequence[str], label: str, errors: list[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        errors.append(f"{label} must be a mapping")
        return {}
    actual = set(value)
    expected = set(fields)
    unknown = sorted(str(key) for key in actual - expected)
    missing = sorted(expected - actual)
    if unknown:
        errors.append(f"{label} has unknown fields: {unknown}")
    if missing:
        errors.append(f"{label} has missing fields: {missing}")
    if any(not isinstance(key, str) for key in actual):
        errors.append(f"{label} field names must be strings")
    return value


def _exact_list(value: Any, expected: Sequence[Any], label: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list):
        errors.append(f"{label} must be a list")
        return []
    if value != list(expected):
        errors.append(f"{label} must match the exact canonical ordered inventory")
    return value


def _validate_record_schema(record: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    record = _mapping(record, TOP_LEVEL_FIELDS, "Phase 0 record", errors)
    exact_scalars = {
        "schema_version": SCHEMA_VERSION,
        "document_kind": "phase_interface_freeze",
        "freeze_id": FREEZE_ID,
        "canonical_base_commit": CANONICAL_BASE,
        "approved_commit": APPROVED_COMMIT,
        "approved_tree": APPROVED_TREE,
        "digest_method": DIGEST_METHOD,
    }
    for field, expected in exact_scalars.items():
        actual = record[field] if field in record else None
        if actual != expected or type(actual) is not type(expected):
            errors.append(f"Phase 0 record {field} must be {expected}")
    if type(record.get("phase")) is not int or record.get("phase") != 0:
        errors.append("Phase 0 record phase must be exact integer 0")
    if record.get("supersedes") is not None:
        errors.append("Phase 0 record supersedes must be null")
    if record.get("status") not in {STATUS_PENDING, STATUS_VERIFIED}:
        errors.append("Phase 0 record status must be approved_pending_merge or merged_verified")

    surfaces = record.get("frozen_surfaces")
    if not isinstance(surfaces, list) or len(surfaces) != 3:
        errors.append("Phase 0 record must contain exactly three surfaces")
        surfaces = surfaces if isinstance(surfaces, list) else []
    actual_ids = [surface.get("surface_id") if isinstance(surface, Mapping) else None for surface in surfaces]
    if actual_ids != list(DIGESTS):
        errors.append("Phase 0 surface order must be canonical_digest_rng, export_models, catalog_loaders")
    for index, surface_id in enumerate(DIGESTS):
        surface = _mapping(
            surfaces[index] if index < len(surfaces) else None,
            SURFACE_FIELDS,
            f"Phase 0 surface {surface_id}",
            errors,
        )
        if surface.get("surface_id") != surface_id:
            errors.append(f"Phase 0 surface {index} surface_id must be {surface_id}")
        if surface.get("version_id") != "1.0.0":
            errors.append(f"Phase 0 surface {surface_id} version_id must be 1.0.0")
        if surface.get("direction") != SURFACE_DIRECTIONS[surface_id]:
            errors.append(f"Phase 0 surface {surface_id} direction must be {SURFACE_DIRECTIONS[surface_id]}")
        _exact_list(surface.get("source_documents"), SOURCE_DOCUMENTS[surface_id], f"Phase 0 surface {surface_id} source_documents", errors)
        frozen_paths = _exact_list(
            surface.get("frozen_paths"),
            FROZEN_PATHS[surface_id],
            f"Phase 0 surface {surface_id} frozen_paths",
            errors,
        )
        if frozen_paths != list(FROZEN_PATHS[surface_id]):
            errors.append(f"Phase 0 surface {surface_id} canonical frozen_paths are invalid")
        if surface.get("sha256") != DIGESTS[surface_id]:
            errors.append(f"Phase 0 surface {surface_id} sha256 must be {DIGESTS[surface_id]}")
        modules = surface.get("public_modules")
        expected_modules = PUBLIC_MODULES[surface_id]
        if not isinstance(modules, list) or len(modules) != len(expected_modules):
            errors.append(f"Phase 0 surface {surface_id} public_modules must match exact module order")
            modules = modules if isinstance(modules, list) else []
        for module_index, expected_module in enumerate(expected_modules):
            module = _mapping(
                modules[module_index] if module_index < len(modules) else None,
                MODULE_FIELDS,
                f"Phase 0 surface {surface_id} public_modules[{module_index}]",
                errors,
            )
            if module.get("module") != expected_module["module"]:
                errors.append(f"Phase 0 surface {surface_id} public_modules order/module is invalid")
            if module.get("schema_version") != expected_module["schema_version"]:
                errors.append(f"Phase 0 module {expected_module['module']} schema_version is invalid")
            _exact_list(
                module.get("public_symbols"),
                expected_module["public_symbols"],
                f"Phase 0 module {expected_module['module']} public_symbols",
                errors,
            )
            _exact_list(
                module.get("callable_signatures"),
                expected_module["callable_signatures"],
                f"Phase 0 module {expected_module['module']} callable_signatures",
                errors,
            )

    reviews = record.get("reviews")
    if not isinstance(reviews, list) or len(reviews) != 2:
        errors.append("Phase 0 record must contain exactly two review records")
        reviews = reviews if isinstance(reviews, list) else []
    lanes = [review.get("lane") if isinstance(review, Mapping) else None for review in reviews]
    if lanes != ["lane_a", "lane_b"]:
        errors.append("Phase 0 review order must be lane_a then lane_b")
    reviewers: list[Any] = []
    evidence_paths: list[Any] = []
    for index, expected in enumerate(REVIEWS):
        review = _mapping(
            reviews[index] if index < len(reviews) else None,
            REVIEW_FIELDS,
            f"Phase 0 review {index}",
            errors,
        )
        for field in ("lane", "role", "reviewer", "subject", "evidence_path", "evidence_sha256"):
            actual = review[field] if field in review else None
            if actual != expected[field]:
                errors.append(f"Phase 0 review {index} {field} must be {expected[field]}")
        reviewers.append(review.get("reviewer"))
        evidence_paths.append(review.get("evidence_path"))
        if review.get("reviewed_commit") != APPROVED_COMMIT:
            errors.append(f"Phase 0 review {index} reviewed_commit must be A-prime")
        if review.get("reviewed_tree") != APPROVED_TREE:
            errors.append(f"Phase 0 review {index} reviewed_tree must be A-prime tree")
        reviewed_digests = _mapping(
            review.get("reviewed_digests"),
            tuple(DIGESTS),
            f"Phase 0 review {index} reviewed_digests",
            errors,
        )
        if dict(reviewed_digests) != DIGESTS:
            errors.append(f"Phase 0 review {index} reviewed_digests must match the approved triple")
        if review.get("independent_review") is not True:
            errors.append(f"Phase 0 review {index} independent_review must be true")
        if review.get("decision") != "approved":
            errors.append(f"Phase 0 review {index} decision must be approved")
        findings = _mapping(review.get("findings"), FINDING_FIELDS, f"Phase 0 review {index} findings", errors)
        if set(findings) == set(FINDING_FIELDS) and any(type(findings[field]) is not int or findings[field] != 0 for field in FINDING_FIELDS):
            errors.append(f"Phase 0 review {index} findings must be exact integer zeros")
    if len(reviewers) == 2 and reviewers[0] == reviewers[1]:
        errors.append("Phase 0 review reviewer identities must be distinct")
    if len(evidence_paths) == 2 and evidence_paths[0] == evidence_paths[1]:
        errors.append("Phase 0 review evidence_path values must be distinct")

    amendment = _mapping(record.get("amendment_rule"), AMENDMENT_FIELDS, "Phase 0 amendment_rule", errors)
    if dict(amendment) != AMENDMENT_RULE:
        errors.append("Phase 0 amendment_rule must match the exact invalidation rule")
    merge = _mapping(record.get("merge_verification"), MERGE_FIELDS, "Phase 0 merge_verification", errors)
    authorization = _mapping(record.get("lane_authorization"), AUTHORIZATION_FIELDS, "Phase 0 lane_authorization", errors)
    if record.get("status") == STATUS_PENDING:
        if dict(merge) != PENDING_MERGE:
            errors.append("Phase 0 pending merge fields must remain null and pending")
        if dict(authorization) != PENDING_AUTHORIZATION:
            errors.append("Phase 0 pending lane_authorization must remain false with the exact reason")
    else:
        if merge.get("target_branch") != "main" or merge.get("status") != "verified":
            errors.append("Phase 0 verified merge_verification must target main with verified status")
        if not isinstance(merge.get("canonical_merge_commit"), str) or HEX40.fullmatch(merge.get("canonical_merge_commit", "")) is None:
            errors.append("Phase 0 verified canonical_merge_commit must be a full lowercase commit ID")
        if not isinstance(merge.get("verified_at"), str) or UTC_TIMESTAMP.fullmatch(merge.get("verified_at", "")) is None:
            errors.append("Phase 0 verified_at must be strict UTC")
        if dict(authorization) != VERIFIED_AUTHORIZATION:
            errors.append("Phase 0 verified lane_authorization must be true with the exact reason")
    return errors


def _validate_repository_git_state(repo_root: Path) -> list[str]:
    errors: list[str] = []
    supplied = [key for key in GIT_OVERRIDE_VARIABLES if key in os.environ]
    if supplied:
        return [f"Git override environment is forbidden: {', '.join(supplied)}"]
    try:
        graft_raw = _git_text(repo_root, "rev-parse", "--git-path", "info/grafts").strip()
        graft_path = Path(graft_raw)
        if not graft_path.is_absolute():
            graft_path = repo_root / graft_path
        if graft_path.exists() and graft_path.read_bytes():
            errors.append("active Git graft metadata is forbidden")
        shallow = _git_text(repo_root, "rev-parse", "--is-shallow-repository").strip()
        if shallow != "false":
            errors.append("Phase 0 interface freeze validation requires a non-shallow repository")
        shallow_raw = _git_text(repo_root, "rev-parse", "--git-path", "shallow").strip()
        shallow_path = Path(shallow_raw)
        if not shallow_path.is_absolute():
            shallow_path = repo_root / shallow_path
        if shallow_path.exists():
            errors.append("resolved Git shallow file must be absent")
        replacements = [line for line in _git_text(repo_root, "for-each-ref", "--format=%(refname)", "refs/replace").splitlines() if line]
        if replacements:
            errors.append(f"Git replacement refs are forbidden: {sorted(replacements)}")
    except (OSError, subprocess.CalledProcessError, UnicodeError, ValueError) as exc:
        errors.append(f"cannot verify hardened Git state: {_error_text(exc)}")
    return errors


def _object(repo_root: Path, object_id: str, expected_type: str, label: str, errors: list[str]) -> None:
    if HEX40.fullmatch(object_id) is None:
        errors.append(f"{label} must be a full lowercase 40-hex object ID")
        return
    try:
        matches = [line for line in _git_text(repo_root, "rev-parse", f"--disambiguate={object_id}").splitlines() if line]
        if matches != [object_id]:
            errors.append(f"{label} must disambiguate to exactly one object")
            return
        object_type = _git_text(repo_root, "cat-file", "-t", object_id).strip()
        if object_type != expected_type:
            errors.append(f"{label} must identify a {expected_type}")
    except (OSError, subprocess.CalledProcessError, UnicodeError) as exc:
        errors.append(f"{label} cannot be resolved: {_error_text(exc)}")


def _tree(repo_root: Path, commit: str, label: str, errors: list[str]) -> dict[str, tuple[str, str, str]]:
    entries: dict[str, tuple[str, str, str]] = {}
    try:
        raw = _git(repo_root, "ls-tree", "-rz", "--full-tree", commit).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        errors.append(f"cannot read {label} tree: {_error_text(exc)}")
        return entries
    for raw_record in raw.split(b"\0"):
        if not raw_record:
            continue
        metadata, separator, raw_path = raw_record.partition(b"\t")
        try:
            mode, object_type, object_id = metadata.decode("ascii").split()
            path = raw_path.decode("utf-8")
        except (UnicodeError, ValueError):
            errors.append(f"{label} tree contains a malformed or invalid-UTF-8 record")
            continue
        if not separator or not _safe_path(path) or HEX40.fullmatch(object_id) is None:
            errors.append(f"{label} tree contains a malformed record: {path!r}")
            continue
        if path in entries:
            errors.append(f"{label} tree contains a duplicate/ambiguous path: {path}")
            continue
        entries[path] = (mode, object_type, object_id)
    return entries


def _blob(repo_root: Path, object_id: str) -> bytes:
    return _git(repo_root, "cat-file", "blob", object_id).stdout


def _validate_frozen_paths(repo_root: Path, aprime_tree: Mapping[str, tuple[str, str, str]], head_tree: Mapping[str, tuple[str, str, str]]) -> list[str]:
    errors: list[str] = []
    for surface_id, paths in FROZEN_PATHS.items():
        manifest = bytearray()
        for relative in paths:
            aprime_entry = aprime_tree[relative] if relative in aprime_tree else None
            if aprime_entry is None:
                errors.append(f"{surface_id}: A-prime frozen path is missing: {relative}")
                continue
            if aprime_entry[:2] != ("100644", "blob"):
                errors.append(f"{surface_id}: A-prime frozen path must be 100644 blob: {relative}")
                continue
            head_entry = head_tree[relative] if relative in head_tree else None
            if head_entry != aprime_entry:
                errors.append(f"{surface_id}: HEAD frozen path mode/object differs from A-prime: {relative}")
            content = _blob(repo_root, aprime_entry[2])
            manifest.extend(f"{_sha256(content)}  {relative}\n".encode("utf-8"))
            path = repo_root / relative
            try:
                status = path.lstat()
                regular = stat.S_ISREG(status.st_mode) and not stat.S_ISLNK(status.st_mode)
                executable = bool(status.st_mode & 0o111)
                worktree_content = path.read_bytes() if regular else None
            except OSError:
                regular = False
                executable = False
                worktree_content = None
            if not regular or executable or worktree_content != content:
                errors.append(f"{surface_id}: working-tree frozen path must be regular, non-executable, and byte-equal to A-prime: {relative}")
        actual_digest = _sha256(bytes(manifest))
        if actual_digest != DIGESTS[surface_id]:
            errors.append(f"{surface_id}: recomputed A-prime digest does not match approved sha256")
    return errors


def _frontmatter(content: bytes, label: str, errors: list[str]) -> Mapping[str, Any]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        errors.append(f"{label} must be valid UTF-8")
        return {}
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        errors.append(f"{label} must contain strict frontmatter")
        return {}
    _, body = text.split("---\n", 1)
    raw_frontmatter, _ = body.split("\n---\n", 1)
    try:
        value = yaml.load(raw_frontmatter, Loader=_StrictLoader)
    except (yaml.YAMLError, ValueError) as exc:
        errors.append(f"{label} frontmatter is invalid: {_error_text(exc)}")
        return {}
    if not isinstance(value, Mapping):
        errors.append(f"{label} frontmatter must be a mapping")
        return {}
    return value


def _validate_reviews(repo_root: Path, binding_tree: Mapping[str, tuple[str, str, str]], head_tree: Mapping[str, tuple[str, str, str]]) -> list[str]:
    errors: list[str] = []
    for expected in REVIEWS:
        relative = expected["evidence_path"]
        binding_entry = binding_tree[relative] if relative in binding_tree else None
        head_entry = head_tree[relative] if relative in head_tree else None
        if binding_entry is None or binding_entry[:2] != ("100644", "blob"):
            errors.append(f"review {relative} must be a checked-in 100644 regular file")
            continue
        if head_entry != binding_entry:
            errors.append(f"review {relative} binding bytes/mode must be preserved at HEAD")
        content = _blob(repo_root, binding_entry[2])
        if _sha256(content) != expected["evidence_sha256"]:
            errors.append(f"review {relative} raw SHA-256 does not match the approved draft")
        path = repo_root / relative
        try:
            status = path.lstat()
            if not stat.S_ISREG(status.st_mode) or stat.S_ISLNK(status.st_mode) or status.st_mode & 0o111 or path.read_bytes() != content:
                errors.append(f"review {relative} working tree must be regular, non-executable, and committed-byte exact")
        except OSError:
            errors.append(f"review {relative} working tree is missing or unreadable")
        try:
            index_line = _git_text(repo_root, "ls-files", "-s", "--", relative).strip()
            expected_index = f"{binding_entry[0]} {binding_entry[2]} 0\t{relative}"
            if index_line != expected_index:
                errors.append(f"review {relative} index entry must match the binding commit exactly")
        except (OSError, subprocess.CalledProcessError, UnicodeError) as exc:
            errors.append(f"review {relative} index entry cannot be verified: {_error_text(exc)}")
        metadata = _frontmatter(content, f"review {relative}", errors)
        expected_frontmatter = {
            "document_kind": "review",
            "status": "delivered",
            "authoritative": False,
            "subject": expected["subject"],
            "reviewed_ref": APPROVED_COMMIT,
            "reviewer": expected["reviewer"],
            "verdict": "approved",
        }
        if dict(metadata) != expected_frontmatter:
            errors.append(f"review {relative} frontmatter must match the exact approved identity and verdict")
        text = content.decode("utf-8", errors="replace").lower()
        if not all(needle in text for needle in ("critical", "important", "minor", "specification", "frozen-correctness")):
            errors.append(f"review {relative} must record zero-finding approved semantics")
    return errors


def _binding_commit(repo_root: Path, errors: list[str]) -> str | None:
    try:
        revisions = [
            line
            for line in _git_text(
                repo_root,
                "log",
                "--diff-filter=A",
                "--format=%H",
                "HEAD",
                "--",
                "governance/phase0-interface-freeze.yaml",
            ).splitlines()
            if line
        ]
    except (OSError, subprocess.CalledProcessError, UnicodeError) as exc:
        errors.append(f"cannot locate Phase 0 binding commit: {_error_text(exc)}")
        return None
    if len(revisions) != 1:
        if not revisions:
            tracked = _git(
                repo_root,
                "ls-files",
                "--error-unmatch",
                "--",
                "governance/phase0-interface-freeze.yaml",
                check=False,
            )
            if tracked.returncode != 0:
                return None
        errors.append(f"Phase 0 record must have one unique introducing binding commit; found {revisions}")
        errors.append("Phase 0 binding commit must be a single-parent direct child of A-prime")
        return None
    binding = revisions[0]
    try:
        parent_line = _git_text(repo_root, "rev-list", "--parents", "-n", "1", binding).split()
        if len(parent_line) != 2 or parent_line[1] != APPROVED_COMMIT:
            errors.append("Phase 0 binding commit must be a single-parent direct child of A-prime")
        changed = {
            item.decode("utf-8")
            for item in _git(repo_root, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", binding).stdout.split(b"\0")
            if item
        }
        if changed != BINDING_PATHS:
            errors.append(f"Phase 0 binding changed path inventory must be exactly {sorted(BINDING_PATHS)}; found {sorted(changed)}")
        frozen = {path for paths in FROZEN_PATHS.values() for path in paths}
        protected = frozen | set(HISTORICAL_B0_PATHS)
        overlap = sorted(changed & protected)
        if overlap:
            errors.append(f"Phase 0 binding commit must not modify frozen or historical evidence paths: {overlap}")
    except (OSError, subprocess.CalledProcessError, UnicodeError) as exc:
        errors.append(f"cannot verify Phase 0 binding topology/inventory: {_error_text(exc)}")
    return binding


def _validate_binding_bytes(repo_root: Path, binding: str, binding_tree: Mapping[str, tuple[str, str, str]], head_tree: Mapping[str, tuple[str, str, str]], status: Any) -> list[str]:
    errors: list[str] = []
    for relative in BINDING_PATHS:
        binding_entry = binding_tree[relative] if relative in binding_tree else None
        if binding_entry is None or binding_entry[1] != "blob":
            errors.append(f"Phase 0 binding path must be committed as a blob: {relative}")

    record_path = "governance/phase0-interface-freeze.yaml"
    if status == STATUS_PENDING:
        binding_entry = binding_tree[record_path] if record_path in binding_tree else None
        head_entry = head_tree[record_path] if record_path in head_tree else None
        if binding_entry is not None and head_entry != binding_entry:
            errors.append(
                "Phase 0 record binding bytes/mode must be preserved at HEAD while "
                "status is approved_pending_merge"
            )

    try:
        ancestry = _git(repo_root, "merge-base", "--is-ancestor", binding, "HEAD", check=False)
        if ancestry.returncode != 0:
            errors.append("Phase 0 binding commit must be an ancestor of HEAD")
    except OSError as exc:
        errors.append(f"cannot verify Phase 0 binding ancestry: {_error_text(exc)}")
    return errors


def _validate_historical_b0(head_tree: Mapping[str, tuple[str, str, str]], base_tree: Mapping[str, tuple[str, str, str]]) -> list[str]:
    errors: list[str] = []
    for relative in HISTORICAL_B0_PATHS:
        head_entry = head_tree[relative] if relative in head_tree else None
        base_entry = base_tree[relative] if relative in base_tree else None
        if head_entry != base_entry:
            errors.append(f"historical B0 evidence must remain mode/object-identical to canonical base: {relative}")
    return errors


def _validate_documents(repo_root: Path) -> list[str]:
    errors: list[str] = []
    blocks: dict[str, str] = {}
    for relative in ("CONSOLIDATED_PLAN.md", "PARALLEL_WORK_GUIDE.md"):
        try:
            text = (repo_root / relative).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"plan/guide document cannot be read: {relative}: {_error_text(exc)}")
            continue
        if text.count(MARKER_BEGIN) != 1 or text.count(MARKER_END) != 1:
            errors.append(f"plan/guide document must contain one Phase 0 marker block: {relative}")
            continue
        block = text.split(MARKER_BEGIN, 1)[1].split(MARKER_END, 1)[0].strip()
        blocks[relative] = block
        if block != MARKER_BODY:
            errors.append(f"plan/guide Phase 0 marker block is not exact: {relative}")
        if "freeze itself is still pending" in text or "deferred implementation claim" in text:
            errors.append(f"plan/guide contains stale pending-freeze or deferred implementation wording: {relative}")
    if len(blocks) == 2 and len(set(blocks.values())) != 1:
        errors.append("plan/guide Phase 0 authorization blocks must agree exactly")
    try:
        plan = (repo_root / "CONSOLIDATED_PLAN.md").read_text(encoding="utf-8")
        phase0 = plan.split("## Phase 0", 1)[1].split("## Phase 1", 1)[0]
        for item in range(1, 11):
            pattern = re.compile(rf"^- \[ \] \*\*WP-0\.{item}(?!\d)", re.MULTILINE)
            if pattern.search(phase0) is None:
                errors.append(f"WP-0.{item} must remain unchecked in CONSOLIDATED_PLAN.md")
    except (OSError, UnicodeError, IndexError):
        pass
    return errors


def _validate_refs(repo_root: Path, authorized: bool) -> list[str]:
    if authorized:
        return []
    try:
        refs = _git_text(repo_root, "for-each-ref", "--format=%(refname)").splitlines()
    except (OSError, subprocess.CalledProcessError, UnicodeError) as exc:
        return [f"cannot inspect Phase 0 refs: {_error_text(exc)}"]
    prohibited = sorted(ref for ref in refs if PROHIBITED_REF.search(ref))
    return [f"prohibited Phase 0 ref exists while lane authorization is false: {ref}" for ref in prohibited]


def _validate_verified_topology(repo_root: Path, record: Mapping[str, Any], binding: str) -> list[str]:
    if record.get("status") != STATUS_VERIFIED:
        return []
    errors: list[str] = []
    merge = record.get("merge_verification")
    if not isinstance(merge, Mapping):
        return errors
    merge_commit = merge.get("canonical_merge_commit")
    if not isinstance(merge_commit, str) or HEX40.fullmatch(merge_commit) is None:
        return errors
    try:
        _object(repo_root, merge_commit, "commit", "canonical merge commit", errors)
        parents = _git_text(repo_root, "rev-list", "--parents", "-n", "1", merge_commit).split()
        if len(parents) < 3:
            errors.append("verified canonical merge commit must have at least two parents")
        elif not any(_git(repo_root, "merge-base", "--is-ancestor", binding, parent, check=False).returncode == 0 for parent in parents[2:]):
            errors.append("Binding C must be reachable through a merged feature parent")
        first_parent_history = _git_text(repo_root, "rev-list", "--first-parent", "HEAD").splitlines()
        if merge_commit not in first_parent_history:
            errors.append("canonical merge commit must be present on current canonical first-parent history")
    except (OSError, subprocess.CalledProcessError, UnicodeError) as exc:
        errors.append(f"cannot verify canonical merge topology: {_error_text(exc)}")
    return errors


def validate_phase0_interface_freeze(
    repo_root: Path,
    record: Mapping[str, Any] | None = None,
) -> list[str]:
    errors = _validate_repository_git_state(repo_root)
    if errors:
        return sorted(set(errors))
    record_path = repo_root / "governance/phase0-interface-freeze.yaml"
    if record is None:
        try:
            record = load_phase0_interface_freeze(record_path)
        except ValueError as exc:
            return [str(exc)]
    errors.extend(_validate_record_schema(record))
    try:
        committed_record = load_phase0_interface_freeze(record_path)
    except ValueError as exc:
        errors.append(str(exc))
        committed_record = record
    errors.extend(
        error.replace("Phase 0 record", "committed Phase 0 record", 1)
        for error in _validate_record_schema(committed_record)
    )

    _object(repo_root, CANONICAL_BASE, "commit", "canonical base", errors)
    _object(repo_root, APPROVED_COMMIT, "commit", "A-prime", errors)
    _object(repo_root, APPROVED_TREE, "tree", "approved tree", errors)
    try:
        actual_tree = _git_text(repo_root, "rev-parse", f"{APPROVED_COMMIT}^{{tree}}").strip()
        if actual_tree != APPROVED_TREE:
            errors.append("A-prime tree does not equal approved_tree")
        if _git(repo_root, "merge-base", "--is-ancestor", CANONICAL_BASE, APPROVED_COMMIT, check=False).returncode != 0:
            errors.append("canonical base must be an ancestor of A-prime")
        if _git(repo_root, "merge-base", "--is-ancestor", APPROVED_COMMIT, "HEAD", check=False).returncode != 0:
            errors.append("A-prime must be an ancestor of HEAD; squash/cherry-pick transplantation is forbidden")
    except (OSError, subprocess.CalledProcessError, UnicodeError) as exc:
        errors.append(f"cannot verify A-prime topology: {_error_text(exc)}")

    aprime_tree = _tree(repo_root, APPROVED_COMMIT, "A-prime", errors)
    head_tree = _tree(repo_root, "HEAD", "HEAD", errors)
    base_tree = _tree(repo_root, CANONICAL_BASE, "canonical base", errors)
    errors.extend(_validate_frozen_paths(repo_root, aprime_tree, head_tree))
    errors.extend(_validate_historical_b0(head_tree, base_tree))

    binding = _binding_commit(repo_root, errors)
    if binding is not None:
        binding_tree = _tree(repo_root, binding, "Binding C", errors)
        errors.extend(_validate_binding_bytes(repo_root, binding, binding_tree, head_tree, record.get("status")))
        errors.extend(_validate_reviews(repo_root, binding_tree, head_tree))
        errors.extend(_validate_verified_topology(repo_root, record, binding))
        entry = head_tree.get("governance/phase0-interface-freeze.yaml")
        if entry is None or entry[:2] != ("100644", "blob"):
            errors.append("Phase 0 record must be a committed 100644 regular file")
        else:
            committed_content = _blob(repo_root, entry[2])
            try:
                path_status = record_path.lstat()
                if not stat.S_ISREG(path_status.st_mode) or stat.S_ISLNK(path_status.st_mode) or path_status.st_mode & 0o111 or record_path.read_bytes() != committed_content:
                    errors.append("Phase 0 record working tree must be regular, non-executable, and committed-byte exact")
            except OSError:
                errors.append("Phase 0 record working tree is missing or unreadable")

    errors.extend(_validate_documents(repo_root))
    authorization = record.get("lane_authorization")
    authorized = isinstance(authorization, Mapping) and authorization.get("authorized") is True
    errors.extend(_validate_refs(repo_root, authorized))
    return sorted(set(errors))


def main() -> int:
    if len(sys.argv) != 1:
        print("ERROR: usage: validate_phase0_interface_freeze.py", file=sys.stderr)
        return 2
    repo_root = Path(__file__).resolve().parents[2]
    try:
        errors = validate_phase0_interface_freeze(repo_root)
    except (OSError, subprocess.CalledProcessError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        errors = [f"Phase 0 interface freeze validation failed safely: {_error_text(exc)}"]
    if errors:
        for error in sorted(set(errors)):
            print(f"ERROR: {error}")
        return 1
    print("Phase 0 interface freeze policy: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
