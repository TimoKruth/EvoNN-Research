"""Prepare, qualify, run and analyze the explicitly requested Prism-only study."""

import argparse
from itertools import combinations
import json
from pathlib import Path
import subprocess
import sys
import uuid

from evonn_shared.artifact_io import publish_artifact
from evonn_shared.export_reader import read_export
from evonn_shared.prism_policy import PrismResearchPolicy
from . import campaign as c
from .baseline_study import validate_replay
from .prism_frontier import VARIANTS
from .prism_confidence_stats import PRIMARY_TASKS, inference, power_sensitivity


ARMS = ("legacy", "archive", "training", "broad", *VARIANTS)
SEEDS = tuple(range(21601, 21631))
QUALIFICATION_SEED = 21600
PANELS = {
    "core128": ("tier_b_core_v2", 128),
    "core256": ("tier_b_core_v2", 256),
    "breadth128": ("language_breadth_v1", 128),
}
QUALIFICATION = {"qcore": ("tier_b_core_v2", 32), "qbreadth": ("language_breadth_v1", 32)}
AUTHORIZATION = "User requested only Prism versions on 2026-09-21, then explicitly selected all eleven variants."


def policy():
    return {
        "schema_version": "evonn.prism-version-confidence/v1", "authorization": AUTHORIZATION,
        "systems": ["prism"], "arms": list(ARMS), "seeds": list(SEEDS),
        "qualification_seed": QUALIFICATION_SEED, "qualification_budget": 32,
        "panels": {key: {"pack": pack, "budget": budget} for key, (pack, budget) in PANELS.items()},
        "primary_tasks": {k: list(v) for k, v in PRIMARY_TASKS.items()},
        "primary_contrasts": [{"panel": panel, "before": a, "after": b}
                              for panel in PRIMARY_TASKS for a, b in combinations(ARMS, 2)],
        "inference": "Exact two-sided paired signed-rank sign enumeration; differences rounded to 12 decimals; zeros discarded, ties use average ranks. One Holm family over all 110 contrasts, alpha .05. Seeds are independent units; benchmarks and budget prefixes are not extra replicates. Requires symmetric paired effects under the null.",
        "confidence_intervals": "20000 paired-seed percentile resamples, RNG seed 21600; 95% descriptive intervals, not simultaneous intervals.",
        "decision": "Supported direction requires Holm p <= .05, absolute mean symmetric gain >= .01, and its descriptive interval excluding zero. A panel leader must beat every other variant by this rule; otherwise no unique leader. No equivalence claim from nonsignificance. No automatic promotion.",
        "aggregation": "Equal task weights per seed, symmetric direction-aware effect 2*(better-worse)/(abs(a)+abs(b)). Banknote is a fixed core sentinel; delayed copy is a fixed breadth sentinel, not included in real-text mean. No outcome-dependent exclusions.",
        "secondary": "Core128, per-task metrics, banknote and delayed-copy sentinels, budget scaling, quality/work curves, training time, model size and runtime are descriptive. Report every task and negative trade-off; no pooled task rows as independent samples.",
        "failure_policy": "Stop on any failed, invalid, missing or unreplayable run. Retain its artifacts; do not drop arms, replace seeds, or silently restart. Main analysis is blocked until every qualification and main slot validates. Source fixes require a separately frozen replacement study.",
        "execution": "Serial bounded runs; rotating arm/panel order; pause between runs; fit/engine time caps unchanged; main run gated by all-arm, both-pack qualification and replay.",
        "qualification_runs": 22, "main_runs": 990, "total_fit_attempts": 169664,
        "protected_test_access": False, "automatic_promotion": False,
        "scope": "Within-Prism validation-selected version comparison. No contender, other-engine, protected-test or broad generalization claim.",
    }


def campaigns():
    rows = []
    for stage, panels, seeds, epochs in (("qualification", QUALIFICATION, [QUALIFICATION_SEED], 2),
                                         ("main", PANELS, list(SEEDS), 12)):
        for panel, (pack, budget) in panels.items():
            base = c.CampaignSpec(pack=pack, budgets=[budget], seeds=seeds, systems=["prism"],
                backend="mlx_native", epochs=epochs, timeout=1500., fit_timeout=120.,
                min_free_bytes=20 * 1024**3, prism_version_study="user-requested-20260921",
                prism_research=PrismResearchPolicy())
            for arm in ARMS:
                # Only substitute an independently validated Prism policy. Full
                # campaign/data validation still occurs on every stored manifest.
                spec = base.model_copy(update={"prism_research": PrismResearchPolicy(variant=arm)})
                rows.append({"stage": stage, "panel": panel, "arm": arm,
                             "campaign": f"campaigns/{stage}-{panel}-{arm}", "spec": spec.model_dump(mode="json")})
    return rows


def schedule(rows):
    result = []
    for stage, seeds, panels in (("qualification", [QUALIFICATION_SEED], list(QUALIFICATION)),
                                 ("main", SEEDS, list(PANELS))):
        for index, seed in enumerate(seeds):
            ordered_panels = panels[index % len(panels):] + panels[:index % len(panels)]
            for panel in ordered_panels:
                offset = (index + panels.index(panel)) % len(ARMS)
                for arm in ARMS[offset:] + ARMS[:offset]:
                    row = next(r for r in rows if (r["stage"], r["panel"], r["arm"]) == (stage, panel, arm))
                    result.append({"campaign": row["campaign"], "stage": stage, "panel": panel,
                                   "arm": arm, "seed": seed})
    return result


def seed_audit(evidence_root):
    requested = {QUALIFICATION_SEED, *SEEDS}
    files = sorted({*evidence_root.glob("governance/**/*.json"), *evidence_root.glob("reports/**/*.json")})
    # Include local campaign manifests, including frozen execution checkouts.
    for directory in evidence_root.parent.glob("EvoNN*/.artifacts"):
        result = subprocess.run(["rg", "--files", "--hidden", "--no-ignore", "-g", "campaign.json",
                                 "-g", "!.venv/**", str(directory)], capture_output=True, text=True, check=False)
        if result.returncode not in (0, 1):
            raise ValueError("cannot inventory historical campaigns: " + result.stderr)
        files.extend(Path(p) for p in result.stdout.splitlines())
    checked = []
    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"seed", "seeds", "qualification_seed"}:
                    values = item if isinstance(item, list) else [item]
                    if any(type(v) is int and v in requested for v in values):
                        raise ValueError("study seeds overlap recorded evidence in " + str(path))
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    for path in sorted(set(files)):
        payload = path.read_bytes()
        visit(json.loads(payload))
        checked.append({"path": str(path), "sha256": c.hashlib.sha256(payload).hexdigest()})
    return {"requested": sorted(requested), "checked": checked,
            "scope": "available governance/report JSON and campaign manifests in sibling EvoNN artifact directories; unrecorded external runs unknown"}


def prepare(root, cache, evidence_root):
    root, cache = root.absolute(), cache.absolute()
    if root.exists():
        raise ValueError("use a new study directory; existing evidence is never overwritten")
    pinned = c.identity()
    audit = seed_audit(evidence_root.absolute())
    rows = campaigns()
    root.mkdir(parents=True)
    dataset_manifests = {}
    for row in rows:
        spec = c.CampaignSpec.model_validate(row["spec"])
        workspace = root / row["campaign"]
        key = spec.pack, tuple(spec.seeds)
        if key not in dataset_manifests:
            c.prepare_plan(workspace, spec, cache)
            dataset_manifests[key] = c.read_manifest(workspace)
        else:
            template = dataset_manifests[key]
            with c.lease(workspace):
                value = {"schema_version": "evonn.campaign/v1", "spec": row["spec"], "identity": pinned,
                         "cache": str(cache), "datasets": template["datasets"], "workspace": str(workspace)}
                publish_artifact(workspace / "campaign.json", c.encoded({**value, "sha256": c.sha(value)}))
            c.preflight(workspace)
        print(json.dumps({"prepared": row["campaign"], "training_started": False}), flush=True)
    if c.identity() != pinned:
        raise ValueError("producer changed during preparation")
    value = {"schema_version": "evonn.prism-confidence-study/v1", "policy": policy(), "identity": pinned,
             "campaigns": rows, "schedule": schedule(rows), "seed_audit": audit,
             "power_sensitivity": power_sensitivity(ARMS, len(SEEDS)),
             "campaign_hashes": {row["campaign"]: c.read_manifest(root / row["campaign"])["sha256"] for row in rows}}
    publish_artifact(root / "study.json", c.encoded({**value, "sha256": c.sha(value)}))
    return preflight(root)


def read_plan(root):
    value = json.loads(c.read_document(root, "study.json"))
    if (value["schema_version"] != "evonn.prism-confidence-study/v1" or value["policy"] != policy()
            or value["campaigns"] != campaigns() or value["schedule"] != schedule(campaigns())
            or value["sha256"] != c.sha({k: v for k, v in value.items() if k != "sha256"})):
        raise ValueError("study differs from frozen policy or schedule")
    for row in value["campaigns"]:
        manifest = c.read_manifest(root / row["campaign"])
        if (manifest["spec"] != row["spec"] or manifest["identity"] != value["identity"]
                or manifest["sha256"] != value["campaign_hashes"][row["campaign"]]):
            raise ValueError("campaign differs from study binding")
    return value


def preflight(root):
    plan = read_plan(root)
    for row in plan["campaigns"]:
        c.preflight(root / row["campaign"])
    return {"status": "ready_for_qualification", "runs": len(plan["schedule"]),
            "fit_attempts": policy()["total_fit_attempts"], "study_sha256": plan["sha256"],
            "training_started": bool(list((root / "campaigns").glob("*/events/*.json")))}


def slot(row, entry):
    case = c.Case(row["spec"]["pack"], row["spec"]["budgets"][0], entry["seed"])
    return case, c.slot_id(case, "prism")


def replay(root, row, entry):
    workspace = root / row["campaign"]
    manifest = c.read_manifest(workspace)
    case, identifier = slot(row, entry)
    run, reference = c.adopted(workspace, manifest, case, "prism")
    if reference is None:
        raise ValueError("slot lacks a verified complete export")
    bundle = read_export(workspace / reference["export"])
    attempts = c.artifact_json(bundle, "attempts.json")["attempts"]
    if len(attempts) != case.budget or any(a["status"] != "ok" or a["charged"] != 1 for a in attempts):
        raise ValueError("study requires every fit to succeed; failed/invalid slot retained without replacement")
    directory = c.create_artifact_directory(workspace / "replays")
    path = directory / (identifier + ".json")
    if not path.exists():
        token = uuid.uuid4().hex
        temporary = directory / (identifier + "-" + token + ".output.json")
        c._bounded_process([sys.executable, "-m", "prism.cli", "replay", str(run)], 300,
                           directory / (identifier + "-" + token + ".log"), stdout_path=temporary)
        result = json.loads(temporary.read_bytes())
        validate_replay(result, reference["run_id"], case.pack)
        publish_artifact(path, c.encoded(result))
    validate_replay(json.loads(c.read_document(directory, path.name)), reference["run_id"], case.pack)


def completed_receipts(root, plan):
    completed = {}
    for row in plan["campaigns"]:
        workspace = root / row["campaign"]
        manifest = c.read_manifest(workspace)
        completed[row["campaign"]] = {e["slot"]: e["details"] for e in c.events(workspace, manifest)
                                       if e["kind"] == "complete"}
    return completed


def adopt_scheduled(workspace, case):
    """Recover only this slot if its export survived a lost journal receipt.

    Generic campaign adoption can continue into a later seed without consuming
    max_runs. Keep that recovery from advancing the balanced study schedule.
    """
    with c.lease(workspace):
        manifest = c.read_manifest(workspace)
        history = c.events(workspace, manifest)
        identifier = c.slot_id(case, "prism")
        c.active_dispatch(workspace, history, identifier)
        _, reference = c.adopted(workspace, manifest, case, "prism")
        if reference is None:
            return False
        if not any(e["slot"] == identifier and e["kind"] == "complete" for e in history):
            c.append_event(workspace, manifest, history, identifier, "complete", reference)
        return True


def run(root, *, max_runs=None, qualification_only=False):
    if max_runs is not None and max_runs < 1:
        raise ValueError("max-runs must be positive")
    with c.lease(root / "controller"):
        preflight(root)
        plan = read_plan(root)
        by_path = {r["campaign"]: r for r in plan["campaigns"]}
        receipts = completed_receipts(root, plan)
        launched, qualification_validated = 0, False
        for entry in plan["schedule"]:
            if entry["stage"] == "main" and not qualification_validated:
                if qualification_only:
                    return {"status": "qualification_complete", "new_runs": launched}
                for qualified in (e for e in plan["schedule"] if e["stage"] == "qualification"):
                    replay(root, by_path[qualified["campaign"]], qualified)
                qualification_validated = True
            row = by_path[entry["campaign"]]
            case, identifier = slot(row, entry)
            workspace = root / row["campaign"]
            if identifier in receipts[row["campaign"]]:
                replay(root, row, entry)
                continue
            if (root / "PAUSE").exists() or (max_runs is not None and launched >= max_runs):
                return {"status": "paused", "new_runs": launched, "next": entry}
            result = {"new_runs": 0} if adopt_scheduled(workspace, case) else c.run_campaign(workspace, max_runs=1)
            manifest = c.read_manifest(workspace)
            current = {e["slot"]: e["details"] for e in c.events(workspace, manifest) if e["kind"] == "complete"}
            if identifier not in current:
                raise ValueError("scheduled slot did not complete; study stopped with evidence retained")
            receipts[row["campaign"]] = current
            launched += result["new_runs"]
            replay(root, row, entry)
            print(json.dumps({"completed": entry, "new_runs": launched}), flush=True)
        return analyze(root)


def analyze(root):
    plan = read_plan(root)
    by_path = {r["campaign"]: r for r in plan["campaigns"]}
    receipts = completed_receipts(root, plan)
    missing = []
    for entry in plan["schedule"]:
        _, identifier = slot(by_path[entry["campaign"]], entry)
        if identifier not in receipts[entry["campaign"]]:
            missing.append(entry)
    if missing:
        return {"status": "incomplete", "missing_runs": len(missing), "required_runs": len(plan["schedule"]),
                "inference": "blocked until every declared slot succeeds and replays", "next_missing": missing[0]}
    rows, runs = [], []
    for entry in plan["schedule"]:
        row = by_path[entry["campaign"]]
        workspace = root / row["campaign"]
        manifest = c.read_manifest(workspace)
        case, identifier = slot(row, entry)
        _, reference = c.adopted(workspace, manifest, case, "prism")
        if reference != receipts[entry["campaign"]][identifier]:
            raise ValueError("completed export differs from journal receipt")
        replay_path = workspace / "replays" / (identifier + ".json")
        validate_replay(json.loads(c.read_document(replay_path.parent, replay_path.name)), reference["run_id"], case.pack)
        if entry["stage"] == "qualification":
            continue
        bundle = read_export(workspace / reference["export"])
        attempts = c.artifact_json(bundle, "attempts.json")["attempts"]
        if len(attempts) != case.budget or any(a["status"] != "ok" or a["charged"] != 1 for a in attempts):
            raise ValueError("study inference blocked by failed or invalid fits")
        for benchmark in c.load_parity_pack(case.pack).benchmarks:
            winners = [a for a in attempts if a["benchmark_id"] == benchmark and a["status"] == "ok"]
            winner = max(winners, key=lambda a: a["score"])
            direction = c.get_benchmark(benchmark).primary_metric.direction.value
            rows.append({"panel": entry["panel"], "arm": entry["arm"], "seed": entry["seed"],
                         "benchmark": benchmark, "direction": direction, "value": winner["metric_value"],
                         "parameter_count": winner["parameter_count"], "model_bytes": winner["model_bytes"],
                         "training_seconds": sum(a.get("train_seconds", 0.) for a in winners),
                         "optimizer_updates": sum(a.get("updates", 0) for a in winners)})
        runs.append({**entry, "run_id": reference["run_id"], "export": str(bundle.root),
                     "documents": reference["documents"]})
    result = {"status": "complete", "study_sha256": plan["sha256"], "rows": rows, "runs": runs,
              "statistics": inference(rows, ARMS, SEEDS)}
    path = root / "analysis.json"
    if path.exists():
        if c.read_document(root, path.name) != c.encoded(result):
            raise ValueError("analysis differs from retained evidence")
    else:
        publish_artifact(path, c.encoded(result))
    return {"status": "complete", "report": str(path), "statistics": result["statistics"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    preparing = sub.add_parser("prepare")
    preparing.add_argument("workspace", type=Path)
    preparing.add_argument("--cache", type=Path, required=True)
    preparing.add_argument("--evidence-root", type=Path, required=True)
    for verb in ("preflight", "run", "analyze"):
        command = sub.add_parser(verb)
        command.add_argument("workspace", type=Path)
        if verb == "run":
            command.add_argument("--max-runs", type=int)
            command.add_argument("--qualification-only", action="store_true")
    args = parser.parse_args()
    root = args.workspace.absolute()
    if args.command == "prepare":
        result = prepare(root, args.cache, args.evidence_root)
    elif args.command == "run":
        result = run(root, max_runs=args.max_runs, qualification_only=args.qualification_only)
    else:
        result = preflight(root) if args.command == "preflight" else analyze(root)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
