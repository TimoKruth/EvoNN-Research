"""Canonical cases and envelope parity, independent of engine implementations."""
from dataclasses import dataclass
from pathlib import Path
import json

from .evidence import comparison_fingerprint
from evonn_shared.canonical import canonical_sha256
from evonn_shared.active_catalog import load_parity_pack
from evonn_shared.engine_evidence import validate_engine_bundle
from evonn_shared.export_reader import ExportBundle, read_document


@dataclass(frozen=True)
class Case:
    pack: str
    budget: int
    seed: int

    def __post_init__(self):
        pack = load_parity_pack(self.pack)
        if type(self.budget) is not int or self.budget <= 0 or self.budget % len(pack.benchmarks):
            raise ValueError("case budget must be positive and divisible across the pack")
        if type(self.seed) is not int or not 0 <= self.seed < 2**32:
            raise ValueError("case seed must be an integer in [0, 2**32)")

    @property
    def id(self):
        return f"{self.pack}_b{self.budget}_s{self.seed}"

    def as_dict(self):
        return {"pack": self.pack, "budget": self.budget, "seed": self.seed}


def envelope(bundle: ExportBundle) -> dict:
    """Envelope parity retains all seven budgets; scoring units remain disclosed."""
    budget = bundle.manifest.budget.model_dump(mode="json")
    return budget


def evaluate_case(case: Case, bundles: list[ExportBundle], *, failures: list[dict] | None = None,
                  cohort: str = "current", no_contenders: bool = False) -> dict:
    blockers = [item["reason"] for item in (failures or [])]
    systems = [bundle.manifest.system.value for bundle in bundles]
    if len(systems) != len(set(systems)):
        blockers.append("duplicate system within a comparison case")
    if not bundles:
        blockers.append("no valid exported runs")
    budgets, seed_regimes, protocols = [], [], []
    for bundle in bundles:
        manifest = bundle.manifest
        if (manifest.pack_id, manifest.accounting.evaluation_count, manifest.seed) != (case.pack, case.budget, case.seed):
            blockers.append(f"case identity mismatch: {manifest.run_id}")
        if manifest.status.value != "completed" or manifest.accounting.partial_run:
            blockers.append(f"incomplete run: {manifest.run_id}")
        try:
            validate_engine_bundle(bundle, verify_cache=True)
            if manifest.system.value in {"prism", "topograph", "stratograph", "primordia"}:
                protocols.append(comparison_fingerprint(bundle))
        except (ValueError, OSError, KeyError, TypeError) as error:
            blockers.append(f"{manifest.run_id}: invalid engine evidence: {error}")
        if manifest.accounting.actual_evaluations + manifest.accounting.cached_evaluations != case.budget:
            blockers.append(f"evaluation accounting drift: {manifest.run_id}")
        if bundle.results.coverage.failed or bundle.results.coverage.unsupported:
            blockers.append(f"failed or unsupported outcomes: {manifest.run_id}")
        blockers.extend(f"{manifest.run_id}: exporter blocker {flag.code}: {flag.message}"
                        for flag in bundle.summary.fairness_flags if flag.severity.value == "blocker")
        budgets.append(envelope(bundle))
        seed_regimes.append(manifest.seeding.model_dump(mode="json"))
    if budgets and any(value != budgets[0] for value in budgets[1:]):
        blockers.append("declared budget envelopes differ; inspect all seven dimensions")
    if seed_regimes and any(value != seed_regimes[0] for value in seed_regimes[1:]):
        blockers.append("seeding regimes or prior provenance differ; compare as explicit separate cohorts")
    engine_backends = {b.manifest.runtime.backend.value for b in bundles if b.manifest.system.value != "contenders"}
    if len(engine_backends) > 1:
        blockers.append("mixed engine backends require separate native and portability cases")
    if len(set(protocols)) > 1:
        blockers.append("engine runtime versions, hosts or shared training policies differ")
    engine_only = no_contenders or "contenders" not in systems
    if no_contenders and "contenders" in systems:
        blockers.append("no-contenders case contains contenders")
    if cohort not in ("current", "exploratory", "reference"):
        raise ValueError("unknown comparison cohort")
    state = "reference" if cohort == "reference" else ("exploratory" if blockers or cohort == "exploratory" else "contract-fair")
    # trusted-core/extended require a separate green audit and repeat evidence;
    # absence of those is not inferred from an exporter self-declaration.
    return {"schema_version": "1.0.0", "case": case.as_dict(), "operating_state": state,
            "accounting_state": "complete" if not blockers else "blocked",
            "repeatability_state": "single_seed", "engine_only": engine_only,
            "external_floor_claim": False, "cohort": cohort, "blockers": sorted(set(blockers)),
            "run_ids": [bundle.manifest.run_id for bundle in bundles],
            "contender_run_ids": [bundle.manifest.run_id for bundle in bundles if bundle.manifest.system.value == "contenders"],
            "budget_fingerprints": [canonical_sha256(value, schema_version="evonn-compare-envelope-v1", digest_field=None)
                                    for value in budgets]}


def resolve_export_path(workspace: Path, relative: str) -> Path:
    """Only workspace-contained relative references are accepted on rebuild."""
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("run reference must stay inside the workspace")
    resolved = workspace / path
    if resolved.resolve().is_relative_to(workspace.resolve()) is False:
        raise ValueError("run reference escapes workspace")
    return resolved


def resolve_preset(name: str) -> tuple[str, int]:
    """Only admit aliases backed by checked-in runtime evidence, never future labels."""
    repository = Path(__file__).resolve().parents[3]
    filename = "phase4-runtime-evidence.json" if name == "tier_b_tiny" else "phase1-runtime-evidence.json"
    receipt = json.loads(read_document(repository / "governance", filename))
    presets = receipt["runtime_presets"]
    if name not in presets:
        raise ValueError(f"preset {name!r} has no verified runtime evidence")
    preset = presets[name]
    all_ids = [run["run_id"] for run in receipt["runs"]]
    requested = preset["run_ids"]
    if len(all_ids) != len(set(all_ids)) or len(requested) != len(set(requested)):
        raise ValueError("preset evidence requires unique run IDs")
    supported = [run for run in receipt["runs"] if run["run_id"] in requested]
    if (not supported or {run["run_id"] for run in supported} != set(requested)
            or any(run["pack"] != preset["pack"] or run["budget"] != preset["budget"] or run["status"] != "completed" for run in supported)):
        raise ValueError("preset evidence binding is incomplete")
    return preset["pack"], preset["budget"]
