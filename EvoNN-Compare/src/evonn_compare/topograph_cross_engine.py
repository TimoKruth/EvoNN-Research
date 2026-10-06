"""Frozen all-engine follow-up to the confirmed Topograph mixer configuration."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from random import Random
import subprocess
import sys

import numpy as np

from evonn_shared.active_catalog import load_parity_pack
from evonn_shared.export_reader import read_export
from evonn_shared.prism_policy import PrismResearchPolicy
from evonn_shared.primordia_policy import PrimordiaResearchPolicy
from evonn_shared.topograph_policy import TopographResearchPolicy
from evonn_shared.runtime_journal import load_runtime_checkpoint
from . import campaign as c
from . import topograph_study as s
from .statistics import paired_inference

SYSTEMS = ("prism", "topograph", "stratograph", "primordia", "contenders")
CONTROLS = tuple(x for x in SYSTEMS if x != "topograph")
PACKS = ("tier_b_core_v2", "language_breadth_v1")
SEEDS = {"qualification": [52901], "comparison": list(range(53001, 53017))}
BUDGETS = {"qualification": 16, "comparison": 128}
POLICY = {
    "schema": "evonn.topograph-cross-engine/v1",
    "systems": list(SYSTEMS), "packs": list(PACKS), "seeds": SEEDS, "budgets": BUDGETS,
    "epochs": 12, "backend": "mlx_native", "device": "cpu", "population_size": 4,
    "topograph": "Exact confirmed mixer settings; no task-specific routing or additional tuning",
    "controls": "Prism open; Stratograph shared legacy; Primordia breadth_v2/v2; Contenders required fixed pool. These are maintained defaults, not winners of unfinished variant studies.",
    "timeout": 1740.0, "fit_timeout": 120.0, "segment_fits": 32,
    "primary_endpoints": [list(x) for x in s.ENDPOINTS],
    "memory_endpoint": [PACKS[1], "delayed_copy_lm", -1],
    "inference": "16 fresh paired seeds. Four mixer-vs-control aggregate tests and four delayed-copy tests in one Holm family (8); 32768 seed bootstrap resamples, RNG 0, 99.375% simultaneous percentile intervals. Material gain/regression requires adjusted p <= .05 and interval beyond +/-1% symmetric relative effect. No optional stopping.",
    "contender_selection": "Best successful outcome of the required fixed pool for each task; no optional enhanced families. Required-family coverage must pass admission.",
    "completeness": "All five systems on every declared pack/budget/seed. Qualification plus native winner replays must pass before comparison. Failures stop dispatch and block inference; never drop engines, tasks or seeds.",
    "scope": "Validation-selected outcomes at 128 fits. No protected test, causal mechanism, strongest-variant, compute-matched or universal superiority claim. Report memory separately even when aggregate improves. Historical evidence remains unchanged.",
}


def matrix():
    rows = []
    for stage, seeds in SEEDS.items():
        for seed in seeds:
            packs = list(PACKS)
            Random(seed).shuffle(packs)
            for pack in packs:
                order = list(SYSTEMS)
                Random(f"topograph-cross-v1:{stage}:{seed}:{pack}").shuffle(order)
                spec = c.CampaignSpec(pack=pack, budgets=[BUDGETS[stage]], seeds=[seed], systems=order,
                    backend="mlx_native", epochs=12, timeout=1740.0, fit_timeout=120.0,
                    topograph_variant="next", topograph_research=TopographResearchPolicy(adapters="mixer"),
                    prism_research=PrismResearchPolicy(), primordia_research=PrimordiaResearchPolicy(),
                    min_free_bytes=20 * 1024**3)
                rows.append(dict(stage=stage, seed=seed, pack=pack,
                                 campaign=f"{stage}/s{seed}-{pack}", spec=spec.model_dump(mode="json")))
    return rows


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def status(root, state, **fields):
    value = dict(status=state, updated_at=datetime.now(timezone.utc).isoformat(), **fields)
    write(root / "status.json", value)
    return value


def seed_audit():
    requested = {x for seeds in SEEDS.values() for x in seeds}
    checked = {}
    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"seed", "seeds"}:
                    values = item if isinstance(item, list) else [item]
                    if any(type(x) is int and x in requested for x in values):
                        raise ValueError("fresh seeds overlap retained evidence")
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    for folder in ("governance", "reports"):
        for path in sorted((c.ROOT / folder).rglob("*.json")):
            visit(json.loads(path.read_text()))
            checked[str(path.relative_to(c.ROOT))] = digest(path)
    return dict(requested=sorted(requested), checked=checked,
                scope="Repository governance/report JSON seed declarations; unseen external runs are unknown")


def prepare(root, cache):
    if root.exists():
        raise ValueError("fresh study directory required")
    identity, audit = c.identity(), seed_audit()
    rows = matrix()
    root.mkdir(parents=True)
    with c.lease(root):
        for row in rows:
            c.prepare_plan(root / row["campaign"], c.CampaignSpec.model_validate(row["spec"]), cache)
        if c.identity() != identity:
            raise ValueError("producer changed during preparation")
        hashes = {r["campaign"]: c.read_manifest(root / r["campaign"])["sha256"] for r in rows}
        s.publish_json(root / "study.json", s.signed(dict(policy=POLICY, rows=rows, identity=identity,
                         cache=str(cache), seed_audit=audit, campaign_sha256=hashes)))
    preflight(root, datasets=True)
    return status(root, "prepared", completed=0, declared=170, training_started=False)


def preflight(root, *, datasets=False):
    plan = s.read_signed(root, "study.json")
    if plan["policy"] != POLICY or plan["rows"] != matrix() or plan["identity"] != c.identity():
        raise ValueError("study policy, matrix or producer drift")
    for row in plan["rows"]:
        path = root / row["campaign"]
        manifest = c.read_manifest(path)
        if (manifest["sha256"] != plan["campaign_sha256"][row["campaign"]]
                or manifest["spec"] != row["spec"] or manifest["identity"] != plan["identity"]
                or manifest["cache"] != plan["cache"]):
            raise ValueError("campaign differs from frozen study")
        if datasets:
            c.preflight(path)
    return plan


def receipt_path(campaign, system):
    return campaign / f"verified-{system}.json"


def saved_receipt(campaign, system):
    path = receipt_path(campaign, system)
    if not path.exists():
        return None
    value = s.read_signed(campaign, path.name)
    manifest = c.read_manifest(campaign)
    if value["campaign_sha256"] != manifest["sha256"] or value["result"]["status"] != "passed":
        raise ValueError("verification receipt drift")
    reference = value["reference"]
    if reference["system"] != system:
        raise ValueError("verification system mismatch")
    completions = [e["details"] for e in c.events(campaign, manifest)
                   if e["kind"] == "complete" and e["details"]["system"] == system]
    if completions != [reference]:
        raise ValueError("completion journal differs from receipt")
    for document in reference["documents"]:
        if digest(campaign / reference["export"] / document["path"]) != document["sha256"]:
            raise ValueError("completed export changed")
    return reference


def checkpoint_progress(run):
    _, payload = load_runtime_checkpoint(run / "checkpoints")
    state = json.loads(payload)
    if any(a["status"] != "ok" for a in state["attempts"]):
        raise ValueError("failed attempt retained; no automatic retry")
    return state["completed"]


def command_for(spec, case, system, output, cache):
    command = [sys.executable, "-m", c.MODULES[system], "run", "--pack", case.pack,
               "--budget", str(case.budget), "--seed", str(case.seed), "--output", str(output),
               "--cache", cache, "--timeout", str(spec.timeout), "--fit-timeout", str(spec.fit_timeout)]
    if system != "contenders":
        command += ["--backend", spec.backend, "--epochs", str(spec.epochs)]
    if system == "topograph":
        command += ["--variant", spec.topograph_variant, "--research-options",
                    json.dumps(spec.topograph_research.model_dump(mode="json"), sort_keys=True)]
    if system in {"prism", "primordia"}:
        policy = spec.prism_research if system == "prism" else spec.primordia_research
        for key, value in policy.model_dump(mode="json").items():
            if value is not None:
                command += ["--" + key.replace("_", "-"),
                            json.dumps(value, sort_keys=True) if isinstance(value, dict) else str(value)]
    return command


def dispatch(root, campaign, case, system, study_fd):
    with c.lease(campaign) as campaign_fd:
        c.preflight(campaign)
        manifest = c.read_manifest(campaign)
        spec = c.CampaignSpec.model_validate(manifest["spec"])
        history = c.events(campaign, manifest)
        slot = c.slot_id(case, system)
        c.active_dispatch(campaign, history, slot)
        run, reference = c.adopted(campaign, manifest, case, system)
        if reference is not None:
            if not any(e["kind"] == "complete" and e["slot"] == slot for e in history):
                c.append_event(campaign, manifest, history, slot, "complete", reference)
            return run, reference, case.budget
        if run is not None and system == "contenders":
            raise ValueError("incomplete Contenders retained; no automatic restart")
        before = checkpoint_progress(run) if run is not None else 0
        target = min(case.budget, before + POLICY["segment_fits"])
        command = command_for(spec, case, system, campaign / "runs" / slot, manifest["cache"])
        if system != "contenders":
            command += ["--stop-after", str(target)]
        if run is not None:
            config = json.loads(c.read_document(run, "config.yaml"))
            c.match_config(config, manifest, case, system)
            command += ["--resume", str(run)]
        if (root / "PAUSE").exists():
            return run, None, before
        event = c.append_event(campaign, manifest, history, slot, "dispatch", {"command": command})
        directory = campaign / "dispatch"
        directory.mkdir(exist_ok=True)
        description = directory / f"{event['sequence']:06d}.json"
        s.publish_json(description, event)
        c._bounded_process([sys.executable, "-m", "evonn_compare.campaign_worker", "dispatch",
                            str(description), str(campaign_fd)], spec.timeout + 20,
                           directory / f"{event['sequence']:06d}.log", pass_fds=(study_fd, campaign_fd))
        run, reference = c.adopted(campaign, manifest, case, system)
        if reference is not None:
            c.append_event(campaign, manifest, history, slot, "complete", reference)
            return run, reference, case.budget
        if run is None or system == "contenders" or checkpoint_progress(run) != target or target == case.budget:
            raise ValueError("dispatch did not reach committed target; failed work retained")
        return run, None, target


def verify_slot(campaign, case, system):
    manifest = c.read_manifest(campaign)
    run, reference = c.adopted(campaign, manifest, case, system)
    if reference is None:
        raise ValueError("missing complete export")
    if system == "contenders":
        result = dict(status="passed", method="full export and required-floor admission; no native replay contract")
    else:
        replay = subprocess.run([sys.executable, "-m", c.MODULES[system], "replay", str(run)],
                                capture_output=True, text=True, timeout=1800)
        if replay.returncode:
            raise ValueError("native winner replay failed: " + replay.stderr[-2000:])
        result = json.loads(replay.stdout)
        if result["status"] != "passed":
            raise ValueError("native winner replay did not pass")
    s.publish_json(receipt_path(campaign, system), s.signed(dict(
        campaign_sha256=manifest["sha256"], reference=reference, result=result)))


def collect(root, rows):
    results = []
    for row in rows:
        campaign = root / row["campaign"]
        manifest = c.read_manifest(campaign)
        bundles = []
        spec = c.CampaignSpec.model_validate(row["spec"])
        for case, system in c.slots(spec):
            receipt = saved_receipt(campaign, system)
            run, reference = c.adopted(campaign, manifest, case, system)
            if receipt is None or receipt != reference:
                raise ValueError("incomplete coverage or changed evidence; inference blocked")
            bundle = read_export(run / "symbiosis")
            bundles.append(bundle)
            attempts = c.artifact_json(bundle, "attempts.json")["attempts"]
            results.append(dict(arm=system, pack=case.pack, seed=case.seed, budget=case.budget,
                metrics={b.benchmark_id: b.value for b in bundle.summary.best_per_benchmark},
                timing=bundle.summary.timing.model_dump(mode="json"),
                failed_attempts=sum(a["status"] == "failed" for a in attempts),
                reference=reference, campaign=row["campaign"]))
        acceptance = c.evaluate_case(case, bundles, no_contenders=False)
        if acceptance["blockers"]:
            raise ValueError("all-system case admission failed: " + "; ".join(acceptance["blockers"]))
    return results


def inference(results):
    expected = {(a, seed, p) for a in SYSTEMS for seed in SEEDS["comparison"] for p in PACKS}
    actual = [(r["arm"], r["seed"], r["pack"]) for r in results]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("inference requires complete unique all-engine coverage")
    lookup = {(r["arm"], r["seed"], r["pack"]): r["metrics"] for r in results}
    for row in results:
        if set(row["metrics"]) != set(load_parity_pack(row["pack"]).benchmarks):
            raise ValueError("missing mandatory task, including sentinels")
        if row["budget"] != BUDGETS["comparison"] or row["failed_attempts"]:
            raise ValueError("incomplete budget or failed attempts")
        if not all(math.isfinite(x) for x in row["metrics"].values()):
            raise ValueError("nonfinite metric")
    contrasts = []
    for control in CONTROLS:
        aggregate, _ = s.effects(results, "topograph", control, SEEDS["comparison"])
        memory = []
        for seed in SEEDS["comparison"]:
            a, b = [lookup[(arm, seed, PACKS[1])]["delayed_copy_lm"] for arm in ("topograph", control)]
            memory.append(-2 * (a - b) / (abs(a) + abs(b)) if a or b else 0.0)
        for endpoint, values in (("aggregate", aggregate), ("delayed_copy", memory)):
            stats = paired_inference(values)
            means = np.random.default_rng(0).choice(values, size=(32768, len(values))).mean(axis=1)
            stats["bootstrap_ci95"] = np.quantile(means, [.025, .975]).tolist()
            stats["simultaneous_ci"] = np.quantile(means, [.05 / 16, 1 - .05 / 16]).tolist()
            stats["bootstrap_method"] = "32768 percentile paired-seed resamples; RNG 0; family size 8"
            test = stats["wilcoxon"]
            contrasts.append(dict(candidate="topograph", control=control, endpoint=endpoint,
                seed_effects=values, inference=stats,
                pvalue=test["pvalue"] if test["status"] == "available" else 1.0))
    previous = 0.0
    for index, row in enumerate(sorted(contrasts, key=lambda r: r["pvalue"])):
        row["holm_pvalue"] = max(previous, min(1.0, row["pvalue"] * (8 - index)))
        previous = row["holm_pvalue"]
        low, high = row["inference"]["simultaneous_ci"]
        row["decision"] = ("confirmed_gain" if row["holm_pvalue"] <= .05 and low > .01 else
                           "confirmed_regression" if row["holm_pvalue"] <= .05 and high < -.01 else
                           "no_material_change" if low >= -.01 and high <= .01 else "inconclusive")
    return contrasts


def report(root):
    plan = preflight(root, datasets=True)
    qualification = collect(root, [r for r in plan["rows"] if r["stage"] == "qualification"])
    results = collect(root, [r for r in plan["rows"] if r["stage"] == "comparison"])
    value = dict(status="complete", policy=POLICY, study_sha256=plan["sha256"],
                 qualification=qualification, results=results, contrasts=inference(results))
    write(root / "report.json", value)
    lines = ["# Topograph mixer versus maintained engine defaults", "",
             "Complete: 10 qualification and 160 comparison runs; 16 paired fresh seeds, 128 fits per comparison run.",
             "", "Effects are symmetric relative effects, not accuracy points. All eight contrasts share Holm correction "
             "and 99.375% simultaneous bootstrap intervals. Delayed copy is a separate required endpoint.", "",
             "| Control | Endpoint | Mean effect | Simultaneous interval | Holm p | Decision |",
             "|---|---|---:|---:|---:|---|"]
    for contrast in value["contrasts"]:
        stats = contrast["inference"]
        low, high = stats["simultaneous_ci"]
        lines.append(f"| {contrast['control']} | {contrast['endpoint']} | {stats['effect_mean']:+.2%} | "
                     f"{low:+.2%} to {high:+.2%} | {contrast['holm_pvalue']:.5g} | {contrast['decision']} |")
    lines += ["", "Descriptive means across all 16 seeds:", "",
              "| Pack / task | " + " | ".join(SYSTEMS) + " |",
              "|---|" + "---:|" * len(SYSTEMS)]
    for pack in PACKS:
        for task in load_parity_pack(pack).benchmarks:
            means = [float(np.mean([r["metrics"][task] for r in results if r["pack"] == pack and r["arm"] == a]))
                     for a in SYSTEMS]
            lines.append(f"| {pack} / {task} | " + " | ".join(f"{x:.6g}" for x in means) + " |")
    lines += ["", "Recorded elapsed seconds summed across comparison runs (includes clock conventions and host contention; "
              "not an isolated speed benchmark):", ""]
    for arm in SYSTEMS:
        elapsed = sum(r["timing"]["elapsed_seconds"] for r in results if r["arm"] == arm)
        lines.append(f"- {arm}: {elapsed:.1f}")
    lines += ["", POLICY["controls"], "", POLICY["scope"], ""]
    (root / "report.md").write_text("\n".join(lines))
    return value


def run(root):
    with c.lease(root) as study_fd:
        completed = 0
        try:
            plan = preflight(root)
            completed = sum(saved_receipt(root / r["campaign"], engine) is not None
                            for r in plan["rows"] for engine in SYSTEMS)
            for stage in SEEDS:
                rows = [r for r in plan["rows"] if r["stage"] == stage]
                for row in rows:
                    campaign = root / row["campaign"]
                    for case, system in c.slots(c.CampaignSpec.model_validate(row["spec"])):
                        if saved_receipt(campaign, system) is not None:
                            continue
                        while True:
                            if (root / "PAUSE").exists():
                                return status(root, "paused", completed=completed, declared=170)
                            status(root, "running", completed=completed, declared=170, stage=stage,
                                   active=row["campaign"], engine=system, budget=case.budget)
                            _, reference, progress = dispatch(root, campaign, case, system, study_fd)
                            status(root, "running", completed=completed, declared=170, stage=stage,
                                   active=row["campaign"], engine=system, active_fits=progress)
                            if reference is not None:
                                break
                        verify_slot(campaign, case, system)
                        completed += 1
                # Revalidate the complete qualification gate before any main dispatch.
                if stage == "qualification":
                    status(root, "validating_qualification", completed=completed, declared=170)
                    collect(root, rows)
            status(root, "validating_report", completed=completed, declared=170)
            report(root)
            return status(root, "complete", completed=completed, declared=170, report=str(root / "report.json"))
        except Exception as error:
            status(root, "failed", completed=completed, declared=170, error=str(error))
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "preflight", "run", "resume", "pause", "report"))
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--cache", type=Path)
    args = parser.parse_args()
    root = args.workspace.absolute()
    if args.action == "prepare":
        if args.cache is None:
            parser.error("--cache required")
        result = prepare(root, args.cache.absolute())
    elif args.action == "preflight":
        plan = preflight(root, datasets=True)
        result = dict(status="ready", study_sha256=plan["sha256"])
    elif args.action == "report":
        result = report(root)
    elif args.action == "pause":
        (root / "PAUSE").touch()
        result = dict(status="pause_requested")
    else:
        if args.action == "resume":
            preflight(root)
            (root / "PAUSE").unlink(missing_ok=True)
        result = run(root)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
