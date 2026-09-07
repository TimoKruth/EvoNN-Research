"""CLI/file-only orchestration and rebuildable comparison workspaces."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import uuid

from evonn_shared._run_io import open_directory, open_regular_at
from evonn_shared.artifact_io import append_artifact, create_artifact_directory, publish_artifact, publish_artifact_directory, read_verified_artifact
from evonn_shared.catalog import load_parity_pack
from evonn_shared.export_reader import read_document, read_export
from evonn_shared.telemetry import ArtifactReference

from .audit import artifact_json
from .cases import Case, evaluate_case, resolve_export_path
from .evidence import aggregates, trend_rows, winners
from .quality import classify

SYSTEMS = ("contenders", "prism", "topograph", "stratograph", "primordia")


def encoded(value) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


@contextmanager
def ownership(root: Path):
    root = create_artifact_directory(root)
    try:
        publish_artifact(root / ".workspace.lock", b"")
    except FileExistsError:
        pass
    with open_directory(root) as directory, open_regular_at(directory, ".workspace.lock", exclusive=True) as fd:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield root
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)


def derived(path: Path, payload: bytes):
    """Replace only rebuildable views, atomically, under workspace ownership."""
    create_artifact_directory(path.parent)
    temporary = path.parent / (".derived_" + uuid.uuid4().hex)
    publish_artifact(temporary, payload)
    with open_directory(path.parent) as directory:
        os.replace(temporary.name, path.name, src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)


def load_cases(root: Path):
    cases = []
    reports = root / "reports"
    if not reports.exists():
        return cases
    for path in sorted(reports.iterdir()):
        if not path.is_dir():
            continue
        document = json.loads(read_document(path, "case.json"))
        case = Case(**document["case"])
        bundles, failures = [], list(document["failures"])
        for run in document["runs"]:
            try:
                exported = resolve_export_path(root, run["export"])
                for reference in run["documents"]:
                    read_verified_artifact(exported, ArtifactReference(**reference), max_bytes=16 * 1024 * 1024)
                bundle = read_export(exported)
                if bundle.manifest.system.value != run["system"] or bundle.manifest.run_id != run["run_id"]:
                    raise ValueError("run identity differs from recorded case")
                bundles.append(bundle)
            except (OSError, ValueError) as error:
                failures.append({"system": run["system"], "run_id": run["run_id"], "reason": f"invalid source export: {error}"})
        acceptance = evaluate_case(case, bundles, failures=failures, cohort=document["cohort"], no_contenders=document["no_contenders"])
        cases.append((path.name, {**document, "failures": failures}, bundles, acceptance))
    return cases


def _append_rows(root: Path, rows: list[dict]):
    path = root / "trends" / "fair_matrix_trend_rows.jsonl"
    try:
        payload = read_document(path.parent, path.name, limit=128 * 1024 * 1024)
    except FileNotFoundError:
        payload = b""
    if payload and not payload.endswith(b"\n"):
        raise ValueError("append-only trend has an incomplete final record")
    prior = {}
    for line in payload.splitlines():
        row = json.loads(line)
        key = (row["case_id"], row["run_id"], row["benchmark"], row["outcome_id"])
        if key in prior:
            raise ValueError("duplicate append-only trend row")
        prior[key] = row
    additions = []
    for row in rows:
        key = (row["case_id"], row["run_id"], row["benchmark"], row["outcome_id"])
        if key in prior:
            if prior[key] != row:
                raise ValueError("existing trend evidence differs from rebuilt source")
        else:
            additions.append((json.dumps(row, sort_keys=True, allow_nan=False) + "\n").encode())
    if additions:
        try:
            publish_artifact(path, b"".join(additions))
        except FileExistsError:
            append_artifact(path, b"".join(additions), expected_sha256=hashlib.sha256(payload).hexdigest())


def _rebuild(root: Path):
    from .dashboard import render_dashboard
    all_rows, case_views, qualities = [], [], []
    loaded = load_cases(root)
    seed_groups = {}
    for _, document, bundles, acceptance in loaded:
        if not acceptance["blockers"] and acceptance["cohort"] == "current":
            signature = (document["case"]["pack"], document["case"]["budget"], tuple(sorted(document["systems"])), tuple(acceptance["budget_fingerprints"]),
                         tuple(json.dumps(bundle.manifest.seeding.model_dump(mode="json"), sort_keys=True) for bundle in bundles))
            if signature not in seed_groups:
                seed_groups[signature] = set()
            seed_groups[signature].add(document["case"]["seed"])
    for comparison_id, document, bundles, acceptance in loaded:
        rows = [row for bundle in bundles for row in trend_rows(bundle, comparison_id, acceptance)]
        signature = (document["case"]["pack"], document["case"]["budget"], tuple(sorted(document["systems"])), tuple(acceptance["budget_fingerprints"]),
                     tuple(json.dumps(bundle.manifest.seeding.model_dump(mode="json"), sort_keys=True) for bundle in bundles))
        observed_seeds = sorted(seed_groups[signature]) if signature in seed_groups else []
        acceptance = {**acceptance, "observed_seeds": observed_seeds,
                      "repeatability_state": "multi_seed_descriptive" if len(observed_seeds) >= 2 else "single_seed"}
        case_view = {"comparison_id": comparison_id, "case": document["case"], "acceptance": acceptance,
                     "runs": document["runs"], "failures": document["failures"],
                     "all_systems_winners": winners(rows), "projects_only_winners": winners(rows, projects_only=True)}
        path = root / "reports" / comparison_id
        derived(path / "lane_acceptance.json", encoded(acceptance))
        derived(path / "fair_matrix_summary.json", encoded(case_view))
        text = f"# {comparison_id}\n\nOperating: {acceptance['operating_state']} · Accounting: {acceptance['accounting_state']} · Repeatability: {acceptance['repeatability_state']}\n\n"
        text += "\n".join("- " + item for item in acceptance["blockers"]) + "\n"
        derived(path / "fair_matrix_summary.md", text.encode())
        derived(path / "trend_rows.json", encoded(rows))
        derived(path / "trend_report.md", text.encode())
        # Case-local JSONL is a rebuildable projection, workspace JSONL is append-only.
        derived(path / "fair_matrix_trends.jsonl", b"".join((json.dumps(row, sort_keys=True) + "\n").encode() for row in rows))
        if not acceptance["blockers"]:
            _append_rows(root, rows)
        all_rows.extend(rows)
        case_views.append(case_view)
        qualities.extend({**classify(bundle.root, propagated=True), "case_id": comparison_id} for bundle in bundles)
        qualities.extend({"path": str(root / "runs" / comparison_id), "run_id": item["run_id"] if "run_id" in item else None, "case_id": comparison_id, "system": item["system"],
                          "level": "L0", "gaps": [item["reason"]], "next_level": "complete verified export required"}
                         for item in document["failures"])
    data = {"schema_version": "1.0.0", "cases": case_views, "rows": all_rows,
            "all_systems_winners": winners(all_rows), "projects_only_winners": winners(all_rows, projects_only=True),
            "statistics": aggregates(all_rows), "output_quality": qualities,
            "discovered_systems": sorted({row["engine"] for row in all_rows}),
            "absent_systems": sorted(set(SYSTEMS) - {row["engine"] for row in all_rows})}
    derived(root / "trends" / "fair_matrix_trends.json", encoded(data))
    table = "# Comparison evidence\n\n| Case | Operating | Accounting | Repeatability | Engine only |\n|---|---|---|---|---|\n"
    for case in case_views:
        state = case["acceptance"]
        table += f"| {case['comparison_id']} | {state['operating_state']} | {state['accounting_state']} | {state['repeatability_state']} | {state['engine_only']} |\n"
        table += "\n".join(f"\nBlocker: {item}\n" for item in state["blockers"])
    derived(root / "trends" / "fair_matrix_trends.md", table.encode())
    derived(root / "fair_matrix_dashboard.json", encoded(data))
    derived(root / "fair_matrix_dashboard.html", render_dashboard(data).encode())
    derived(root / "output_quality.json", encoded(qualities))
    return data


def workspace_report(root: Path):
    with ownership(root) as owned:
        for name in ("packs", "runs", "logs", "reports", "trends"):
            create_artifact_directory(owned / name)
        return _rebuild(owned)


def fair_matrix(*, workspace: Path, pack: str = "tier1_core", budgets: list[int] | None = None,
                seeds: list[int] | None = None, systems: list[str] | None = None,
                no_contenders: bool = False, timeout: float = 1200, fit_timeout: float = 180,
                cache: Path | None = None, enhanced: bool = False, cohort: str = "current", reset_workspace: bool = False):
    if not math.isfinite(timeout) or timeout <= 0 or timeout > 1740:
        raise ValueError("each system run must have a time limit in (0, 1740] seconds")
    selected = list(SYSTEMS[:1] if systems is None else systems)
    if no_contenders:
        selected = [system for system in selected if system != "contenders"]
    if not selected or len(set(selected)) != len(selected) or not set(selected) <= set(SYSTEMS):
        raise ValueError("select distinct known systems; no-contenders requires at least one engine")
    source_pack = load_parity_pack(pack)
    cases = [Case(pack, budget, seed) for budget in (budgets or [source_pack.budget_policy.evaluation_count]) for seed in (seeds or [42])]
    if reset_workspace and workspace.exists():
        archive = workspace.absolute().with_name(workspace.name + ".previous_" + uuid.uuid4().hex)
        with ownership(workspace) as previous:
            for provenance in previous.rglob("dataset_provenance.json"):
                export_root = provenance.parent if (provenance.parent / "manifest.json").exists() else provenance.parent / "symbiosis"
                bundle = read_export(export_root)
                references = {item.path: item for item in bundle.summary.artifact_digests}
                if "dataset_provenance.json" not in references:
                    raise ValueError("cannot archive unbound dataset provenance")
                read_verified_artifact(provenance.parent, references["dataset_provenance.json"], max_bytes=16 * 1024 * 1024)
                datasets = artifact_json(bundle, "dataset_provenance.json")
                if not isinstance(datasets, list):
                    raise ValueError("cannot archive unreadable dataset provenance")
                for dataset in datasets:
                    if not isinstance(dataset, dict) or "cache_directory" not in dataset or not isinstance(dataset["cache_directory"], str):
                        raise ValueError("cannot archive unreadable cache provenance")
                    cache_path = Path(dataset["cache_directory"])
                    if not cache_path.is_absolute() or cache_path.resolve().is_relative_to(previous.resolve()):
                        raise ValueError("cannot reset workspace with internal cache references; retain this workspace and use a new workspace with an external cache")
            publish_artifact_directory(previous, archive)
    with ownership(workspace) as root:
        for name in ("packs", "runs", "logs", "reports", "trends"):
            create_artifact_directory(root / name)
        cache = create_artifact_directory(cache if cache is not None else root.with_name(root.name + ".cache"))
        for case in cases:
            comparison_id = case.id + "_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]
            output = create_artifact_directory(root / "runs" / comparison_id)
            report = create_artifact_directory(root / "reports" / comparison_id)
            stamped = source_pack.model_dump(mode="json")
            stamped["budget_policy"]["evaluation_count"] = case.budget
            publish_artifact(root / "packs" / (comparison_id + ".json"), encoded(stamped))
            runs, failures = [], []
            for system in selected:
                command = [f"evonn-{system}", "run", "--pack", case.pack, "--budget", str(case.budget),
                           "--seed", str(case.seed), "--output", str(output), "--cache", str(cache),
                           "--timeout", str(timeout), "--fit-timeout", str(fit_timeout)]
                if system == "contenders" and enhanced:
                    command.append("--enhanced")
                try:
                    process = subprocess.run(command, capture_output=True, text=True, timeout=timeout + 20, check=False)
                    publish_artifact(root / "logs" / f"{comparison_id}_{system}.log", (process.stdout + process.stderr).encode())
                    if process.returncode:
                        raise ValueError(f"CLI exited {process.returncode}; see {comparison_id}_{system}.log")
                    exported = Path(process.stdout.strip().splitlines()[-1])
                    if not exported.resolve().is_relative_to(output.resolve()):
                        raise ValueError("CLI returned an export outside its case output directory")
                    bundle = read_export(exported)
                    if bundle.manifest.system.value != system:
                        raise ValueError("CLI system and export system differ")
                    references = [ArtifactReference(path=name, sha256=hashlib.sha256(read_document(exported, name)).hexdigest()).model_dump(mode="json")
                                  for name in ("manifest.json", "results.json", "summary.json")]
                    runs.append({"system": system, "run_id": bundle.manifest.run_id,
                                 "export": str(exported.relative_to(root)), "documents": references})
                except (OSError, ValueError, IndexError, subprocess.TimeoutExpired) as error:
                    failures.append({"system": system, "reason": f"{type(error).__name__}: {error}"})
            document = {"schema_version": "1.0.0", "case": case.as_dict(), "systems": selected,
                        "cohort": cohort, "no_contenders": no_contenders, "runs": runs, "failures": failures}
            publish_artifact(report / "case.json", encoded(document))
        return _rebuild(root)
