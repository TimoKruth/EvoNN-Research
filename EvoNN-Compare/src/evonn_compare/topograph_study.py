"""Topograph-only staged comparison, explicitly requested by the user; prepare never fits."""
import argparse
from copy import deepcopy
from functools import lru_cache
import json
import math
from pathlib import Path
from random import Random
import subprocess
import sys
import time

import numpy as np
from evonn_shared.artifact_io import publish_artifact
from evonn_shared.export_reader import read_export
from evonn_shared.topograph_policy import TopographResearchPolicy
from . import campaign as c
from .audit import artifact_json
from .statistics import paired_inference

OLD = ("legacy", "mechanics", "training", "archive", "broad", "open")
INTERVENTIONS = {
    "next": {}, "query": {"adapters": "query"}, "mixer": {"adapters": "mixer"},
    "legacy_adapters": {"adapters": "legacy"}, "full_training": {"allocation": "full"},
    "coverage_training": {"allocation": "coverage"}, "quality_selection": {"selection": "quality"},
    "broad_mutation": {"mutation_scale": "broad"}, "cold": {"inheritance": "disabled"},
    "no_smoothing": {"label_smoothing": 0.0}, "all_decay": {"decay": "all"},
    "wide_cap": {"parameter_cap": 2_000_000}, "more_crossover": {"crossover_probability": 0.25},
}
ARMS = (*OLD, *INTERVENTIONS)
PACKS = ("tier_b_core_v2", "language_breadth_v1")
SEEDS = {"qualification": [32701], "screening": list(range(32711, 32715)),
         "confirmation": list(range(32801, 32817))}
BUDGETS = {"qualification": 16, "screening": 128, "confirmation": 256}
CONTROLS = ("legacy", "open", "next")
# Repeated Shakespeare-byte results in the breadth pack remain descriptive only.
ENDPOINTS = ((PACKS[0], "digits_image", 1, 1 / 3),
             (PACKS[0], "diabetes_regression", -1, 1 / 3),
             (PACKS[0], "shakespeare_byte_lm", -1, 1 / 9),
             (PACKS[1], "shakespeare_context64_lm", -1, 1 / 9),
             (PACKS[1], "aesop_context64_lm", -1, 1 / 9))
POLICY = {
    "schema": "evonn.topograph-study/v1", "arms": list(ARMS), "packs": list(PACKS),
    "seeds": SEEDS, "budgets": BUDGETS, "systems": ["topograph"],
    "authorization": "User explicitly requested only Topograph current versions; all 19, staged screening and confirmation.",
    "scope_exception": "topograph_variants_v1; general all-engine rule and historical protocols remain unchanged",
    "backend": "mlx_native", "device": "cpu", "population_size": 4,
    "epochs": {"qualification": 2, "screening": 12, "confirmation": 12},
    "primary_endpoints": [list(e) for e in ENDPOINTS],
    "effect": "direction * 2 * (candidate - control) / (abs(candidate) + abs(control)); zero/zero = 0",
    "aggregation": "Equal weight to image, regression, real text; equal weight to three real-text tasks. Paired seeds are inference units, not tasks or fits.",
    "nomination": "After complete qualification and screening, nominate the arm with highest mean primary gain vs open; exact ties use declared arm order. Retain open unless the best mean gain is positive. Freeze before confirmation fits.",
    "confirmation": "16 disjoint fresh paired seeds. Run legacy, open, next and nominee (deduplicated). Three predeclared nominee-vs-control contrasts; self/unavailable contrasts retain p=1 in Holm family.",
    "confidence": "95% paired-seed bootstrap intervals plus 98.333333% Bonferroni intervals across three aggregate contrasts; 32768 resamples, RNG 0. Two-sided signed-rank permutation p-values and Holm correction, alpha .05. No optional stopping or adding seeds after looking.",
    "gain_rule": "Holm p <= .05 and simultaneous aggregate interval lower bound > .01. Symmetric-effect materiality is 1%, not accuracy points. A gain is against the named control only.",
    "sentinels": "Banknote and delayed-copy remain mandatory and reported separately. Per-task intervals and measured runtime are descriptive; no taskwise dominance or compute-matched claim.",
    "completeness": "Any failed/missing run, replay failure or provenance mismatch blocks nomination/confirmation. Retain failures; never omit an arm or automatically replace a failed seed.",
    "limits": "Validation-selected winners; no protected-test access, external baseline adequacy, cross-engine ranking, causal mechanism proof or guaranteed statistical power. A complete study may be inconclusive.",
}


def arm_policy(arm):
    if arm in OLD:
        return arm, None
    if arm not in INTERVENTIONS:
        raise ValueError("unknown Topograph arm")
    return "next", TopographResearchPolicy(**INTERVENTIONS[arm])


@lru_cache(maxsize=8)
def _matrix(stage, nominee=None):
    arms = list(ARMS) if stage != "confirmation" else list(dict.fromkeys((*CONTROLS, nominee)))
    if stage == "confirmation" and nominee not in ARMS:
        raise ValueError("confirmation requires a frozen known nominee")
    rows = []
    for seed in SEEDS[stage]:
        blocks = list(PACKS)
        Random(seed).shuffle(blocks)
        for pack in blocks:
            order = arms.copy()
            Random(f"topograph-v1:{stage}:{seed}:{pack}").shuffle(order)
            for arm in order:
                variant, options = arm_policy(arm)
                spec = c.CampaignSpec(pack=pack, budgets=[BUDGETS[stage]], seeds=[seed], systems=["topograph"],
                    comparison_scope="topograph_variants_v1", topograph_variant=variant, topograph_research=options,
                    backend="mlx_native", epochs=POLICY["epochs"][stage], timeout=300.0 if stage == "qualification" else 1500.0,
                    fit_timeout=120.0, min_free_bytes=20 * 1024**3)
                rows.append(dict(arm=arm, pack=pack, seed=seed,
                    campaign=f"{stage}/s{seed}-{pack}-{arm}", spec=spec.model_dump(mode="json")))
    return rows


def matrix(stage, nominee=None):
    # Declarations are deterministic for this producer; callers cannot mutate the cache.
    return deepcopy(_matrix(stage, nominee))


def publish_json(path, value):
    publish_artifact(path, c.encoded(value))


def signed(value):
    return {**value, "sha256": c.sha(value)}


def read_signed(root, name):
    value = json.loads(c.read_document(root, name))
    if value.get("sha256") != c.sha({k: v for k, v in value.items() if k != "sha256"}):
        raise ValueError("study document checksum mismatch")
    return value


def read_plan(root):
    plan = read_signed(root, "study.json")
    expected = matrix("qualification") + matrix("screening")
    if plan["policy"] != POLICY or plan["matrix"] != expected:
        raise ValueError("study differs from frozen Topograph protocol")
    for row in expected:
        manifest = c.read_manifest(root / row["campaign"])
        if (manifest["sha256"] != plan["campaign_sha256"][row["campaign"]]
                or manifest["spec"] != row["spec"] or manifest["identity"] != plan["identity"]
                or manifest["cache"] != plan["cache"]):
            raise ValueError("campaign differs from frozen Topograph study")
    return plan


def seed_audit():
    requested = {s for seeds in SEEDS.values() for s in seeds}
    if sum(map(len, SEEDS.values())) != len(requested):
        raise ValueError("study seeds overlap")
    checked = {}

    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"seed", "seeds"}:
                    values = item if isinstance(item, list) else [item]
                    if any(type(v) is int and v in requested for v in values):
                        raise ValueError("Topograph seeds overlap retained evidence")
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    for folder in ("governance", "reports"):
        for path in sorted((c.ROOT / folder).rglob("*.json")):
            value = json.loads(path.read_text())
            visit(value)
            checked[str(path.relative_to(c.ROOT))] = c.sha(value)
    return {"requested": sorted(requested), "checked": checked,
            "scope": "All JSON receipts in governance/reports; unseen external runs cannot be audited."}


def prepare_rows(root, rows, cache):
    """Reuse checksum-verified dataset preparation across arms, never model outcomes."""
    prepared = {}
    for row in rows:
        target = root / row["campaign"]
        spec = c.CampaignSpec.model_validate(row["spec"])
        key = (row["pack"], row["seed"])
        if key not in prepared:
            c.prepare_plan(target, spec, cache)
            prepared[key] = c.read_manifest(target)
        else:
            original = prepared[key]
            value = {k: v for k, v in original.items() if k != "sha256"}
            value.update(spec=row["spec"], workspace=str(target.absolute()))
            with c.lease(target):
                publish_json(target / "campaign.json", signed(value))
            c.read_manifest(target)


def prepare(root, cache):
    root, cache = root.absolute(), cache.absolute()
    identity, audit = c.identity(), seed_audit()
    if root.exists():
        raise ValueError("use a fresh study directory; never overwrite a partial plan")
    rows = matrix("qualification") + matrix("screening")
    root.mkdir(parents=True)
    with c.lease(root):
        prepare_rows(root, rows, cache)
        if c.identity() != identity:
            raise ValueError("producer changed while preparing Topograph study")
        hashes = {r["campaign"]: c.read_manifest(root / r["campaign"])["sha256"] for r in rows}
        publish_json(root / "study.json", signed(dict(policy=POLICY, matrix=rows, identity=identity,
                                                      seed_audit=audit, cache=str(cache), campaign_sha256=hashes)))
    return preflight(root)


def stage_rows(root, plan, stage):
    if stage != "confirmation":
        return [r for r in plan["matrix"] if r["campaign"].startswith(stage + "/")]
    document = read_signed(root, "confirmation.json")
    nomination = read_signed(root, "nomination.json")
    if (nomination["study_sha256"] != plan["sha256"] or document["nomination_sha256"] != nomination["sha256"]
            or document["matrix"] != matrix("confirmation", nomination["nominee"])):
        raise ValueError("confirmation differs from frozen nomination")
    for row in document["matrix"]:
        if c.read_manifest(root / row["campaign"])["sha256"] != document["campaign_sha256"][row["campaign"]]:
            raise ValueError("confirmation campaign changed after freeze")
    return document["matrix"]


def preflight(root):
    plan = read_plan(root)
    if c.identity() != plan["identity"]:
        raise ValueError("Topograph study producer/environment/host drift")
    rows = plan["matrix"]
    if (root / "confirmation.json").exists():
        rows += stage_rows(root, plan, "confirmation")
    verified_data = set()
    for row in rows:
        manifest = c.read_manifest(root / row["campaign"])
        if manifest["spec"] != row["spec"] or manifest["identity"] != plan["identity"]:
            raise ValueError("campaign differs from frozen Topograph study")
        data_identity = c.sha([manifest["datasets"], manifest["cache"], row["spec"]["backend"], row["spec"]["min_free_bytes"]])
        if data_identity not in verified_data:
            c.preflight(root / row["campaign"])
            verified_data.add(data_identity)
    if c.identity() != plan["identity"]:
        raise ValueError("producer changed during study preflight")
    dispatched = sum(len(c.events(root / r["campaign"], c.read_manifest(root / r["campaign"]))) for r in rows)
    return dict(status="ready", prepared_runs=len(rows), study_sha256=plan["sha256"],
                journal_events=dispatched, training_started=bool(dispatched))


def collect(root, stage):
    plan = read_plan(root)
    rows = stage_rows(root, plan, stage)
    results, failures, missing = [], [], []
    for row in rows:
        path = root / row["campaign"]
        try:
            manifest = c.read_manifest(path)
            if manifest["spec"] != row["spec"] or manifest["identity"] != plan["identity"]:
                raise ValueError("campaign provenance differs from study")
            spec = c.CampaignSpec.model_validate(row["spec"])
            case, system = c.slots(spec)[0]
            run, reference = c.adopted(path, manifest, case, system)
            if reference is None:
                missing.append(row["campaign"])
                continue
            replay = read_signed(path, "winner-replay.json")
            if replay["reference"] != reference or replay["result"]["status"] != "passed":
                raise ValueError("winner replay receipt mismatch")
            bundle = read_export(run / "symbiosis")
            attempts = artifact_json(bundle, "attempts.json")["attempts"]
            results.append(dict(arm=row["arm"], seed=row["seed"], pack=row["pack"],
                metrics={b.benchmark_id: b.value for b in bundle.summary.best_per_benchmark},
                train_seconds=sum(a["train_seconds"] for a in attempts), updates=sum(a["updates"] for a in attempts),
                model_bytes={b.benchmark_id: next(a["model_bytes"] for a in attempts if a["outcome_id"] == b.outcome_id)
                             for b in bundle.summary.best_per_benchmark}, reference=reference))
        except (ValueError, OSError, KeyError, TypeError, StopIteration) as error:
            failures.append(dict(campaign=row["campaign"], error=str(error)))
    return dict(status="complete" if len(results) == len(rows) and not failures else "incomplete",
                stage=stage, declared=len(rows), completed=len(results), results=results, missing=missing, failures=failures)


def effects(results, candidate, control, seeds):
    lookup = {(r["arm"], r["seed"], r["pack"]): r["metrics"] for r in results}
    output, tasks = [], {}
    for seed in seeds:
        total = 0.0
        for pack, task, direction, weight in ENDPOINTS:
            a, b = lookup[(candidate, seed, pack)][task], lookup[(control, seed, pack)][task]
            if not all(math.isfinite(v) for v in (a, b)):
                raise ValueError("nonfinite study metric")
            delta = direction * 2 * (a - b) / (abs(a) + abs(b)) if a or b else 0.0
            total += weight * delta
            if task not in tasks:
                tasks[task] = []
            tasks[task].append(delta)
        output.append(total)
    return output, tasks


def choose_nominee(results):
    scores = {a: float(np.mean(effects(results, a, "open", SEEDS["screening"])[0])) for a in ARMS}
    best = max(ARMS, key=lambda a: scores[a])
    return (best if scores[best] > 0 else "open"), scores


def nominate(root):
    with c.lease(root):
        preflight(root)
        if (root / "nomination.json").exists():
            raise ValueError("nomination already frozen")
        for stage in ("qualification", "screening"):
            result = collect(root, stage)
            if result["status"] != "complete":
                raise ValueError("nomination requires complete qualification and screening")
        nominee, scores = choose_nominee(result["results"])
        plan = read_plan(root)
        nomination = signed(dict(study_sha256=plan["sha256"], nominee=nominee, scores=scores,
                                 screening_sha256=c.sha(result)))
        publish_json(root / "nomination.json", nomination)
    return nomination


def prepare_confirmation(root):
    with c.lease(root):
        preflight(root)
        plan, nomination = read_plan(root), read_signed(root, "nomination.json")
        screening = collect(root, "screening")
        if (screening["status"] != "complete" or c.sha(screening) != nomination["screening_sha256"]
                or nomination["study_sha256"] != plan["sha256"]
                or choose_nominee(screening["results"])[0] != nomination["nominee"]):
            raise ValueError("nomination no longer binds complete screening evidence")
        if (root / "confirmation.json").exists():
            raise ValueError("confirmation already prepared")
        rows = matrix("confirmation", nomination["nominee"])
        prepare_rows(root, rows, Path(plan["cache"]))
        hashes = {r["campaign"]: c.read_manifest(root / r["campaign"])["sha256"] for r in rows}
        publish_json(root / "confirmation.json", signed(dict(nomination_sha256=nomination["sha256"], matrix=rows,
                                                             campaign_sha256=hashes)))
    return preflight(root)


def inference(results, nominee):
    if nominee not in ARMS:
        raise ValueError("unknown confirmation nominee")
    expected = {(a, s, p) for a in set((*CONTROLS, nominee)) for s in SEEDS["confirmation"] for p in PACKS}
    actual = [(r["arm"], r["seed"], r["pack"]) for r in results]
    if len(set(actual)) != len(actual) or set(actual) != expected:
        raise ValueError("inference requires complete unique paired confirmation rows")
    contrasts = []
    for control in CONTROLS:
        values, tasks = effects(results, nominee, control, SEEDS["confirmation"])
        stats = paired_inference(values)
        means = np.random.default_rng(0).choice(values, size=(32768, len(values)), replace=True).mean(axis=1)
        stats["bootstrap_ci95"] = np.quantile(means, [.025, .975]).tolist()
        stats["bootstrap_method"] = "32768 percentile resamples of independent paired seed aggregates; RNG seed 0"
        stats["simultaneous_ci"] = np.quantile(means, [.05 / 6, 1 - .05 / 6]).tolist()
        test = stats["wilcoxon"]
        p = test["pvalue"] if test["status"] == "available" and nominee != control else 1.0
        contrasts.append(dict(candidate=nominee, control=control, inference=stats, pvalue=p,
                              per_task_mean_effect={k: float(np.mean(v)) for k, v in tasks.items()}))
    previous = 0.0
    for index, row in enumerate(sorted(contrasts, key=lambda r: r["pvalue"])):
        row["holm_pvalue"] = max(previous, min(1, row["pvalue"] * (3 - index)))
        previous = row["holm_pvalue"]
        low, high = row["inference"]["simultaneous_ci"]
        row["decision"] = ("self_control" if row["candidate"] == row["control"] else
                           "confirmed_aggregate_gain" if row["holm_pvalue"] <= .05 and low > .01 else
                           "confirmed_aggregate_regression" if row["holm_pvalue"] <= .05 and high < -.01 else
                           "no_material_change" if low >= -.01 and high <= .01 else "inconclusive")
    return contrasts


def run(root, stage, *, max_runs=None, session_timeout=1800):
    if not 0 < session_timeout <= 1800 or (max_runs is not None and max_runs < 1):
        raise ValueError("invalid bounded invocation")
    deadline = None
    with c.lease(root):
        preflight(root)
        for prerequisite in (() if stage == "qualification" else ("qualification",) if stage == "screening" else ("qualification", "screening")):
            prior = collect(root, prerequisite)
            if prior["status"] != "complete":
                raise ValueError("prior stage incomplete; study remains blocked")
        if stage == "confirmation":
            nomination = read_signed(root, "nomination.json")
            if c.sha(prior) != nomination["screening_sha256"] or choose_nominee(prior["results"])[0] != nomination["nominee"]:
                raise ValueError("confirmation nomination disagrees with screening evidence")
        plan, launched = read_plan(root), 0
        for row in stage_rows(root, plan, stage):
            if (root / "PAUSE").exists() or (max_runs is not None and launched >= max_runs):
                break
            path = root / row["campaign"]
            manifest = c.read_manifest(path)
            case, system = c.slots(c.CampaignSpec.model_validate(row["spec"]))[0]
            trained, reference = c.adopted(path, manifest, case, system)
            if reference is not None and (path / "winner-replay.json").exists():
                replay = read_signed(path, "winner-replay.json")
                if replay["reference"] != reference or replay["result"]["status"] != "passed":
                    raise ValueError("winner replay receipt mismatch")
                continue
            # Historical evidence validation grows with the study. It must not
            # consume the first pending run's bounded scheduling window.
            if deadline is None:
                deadline = time.monotonic() + session_timeout
            remaining = deadline - time.monotonic()
            reserve = row["spec"]["timeout"] + 160 if reference is None else 140
            if remaining < reserve:
                break
            if reference is None:
                c.run_campaign(path, session_timeout=min(1800, remaining - 140), max_runs=1)
                launched += 1
                trained, reference = c.adopted(path, manifest, case, system)
                if reference is None:
                    raise ValueError("campaign did not complete; evidence retained")
            replay = subprocess.run([sys.executable, "-m", "topograph.cli", "replay", str(trained)],
                                    capture_output=True, text=True, timeout=120)
            if replay.returncode:
                raise ValueError("winner replay failed: " + replay.stderr[-2000:])
            result = json.loads(replay.stdout)
            if result["status"] != "passed":
                raise ValueError("winner replay did not pass")
            publish_json(path / "winner-replay.json", signed(dict(reference=reference, result=result)))
        report = collect(root, stage)
        return {k: v for k, v in report.items() if k != "results"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "preflight", "run", "report", "nominate", "prepare-confirmation", "pause", "resume"])
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--stage", choices=list(SEEDS), default="qualification")
    parser.add_argument("--max-runs", type=int)
    args = parser.parse_args(argv)
    root = args.workspace.absolute()
    if args.action == "prepare":
        if args.cache is None:
            parser.error("--cache required")
        result = prepare(root, args.cache)
    elif args.action == "preflight":
        result = preflight(root)
    elif args.action == "nominate":
        result = nominate(root)
    elif args.action == "prepare-confirmation":
        result = prepare_confirmation(root)
    elif args.action == "pause":
        read_plan(root)
        (root / "PAUSE").touch()
        result = dict(status="pause_requested", boundary="between runs")
    elif args.action in {"run", "resume"}:
        if args.action == "resume":
            preflight(root)
            (root / "PAUSE").unlink(missing_ok=True)
        result = run(root, args.stage, max_runs=args.max_runs)
    else:
        result = collect(root, args.stage)
        if args.stage == "confirmation" and result["status"] == "complete":
            nomination = read_signed(root, "nomination.json")
            screening = collect(root, "screening")
            if (screening["status"] != "complete" or c.sha(screening) != nomination["screening_sha256"]
                    or choose_nominee(screening["results"])[0] != nomination["nominee"]):
                raise ValueError("confirmation nomination disagrees with screening evidence")
            nominee = nomination["nominee"]
            result["contrasts"] = inference(result["results"], nominee)
        result["limits"] = POLICY["limits"]
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
