"""Versioned, all-system language baseline diagnostic; preparation never fits."""

import argparse
import json
import math
from pathlib import Path
import statistics
import sys

from evonn_shared.artifact_io import publish_artifact
from evonn_shared.export_reader import read_export
from evonn_shared.hierarchy_policy import HierarchyResearchPolicy
from evonn_shared.prism_policy import PrismResearchPolicy
from evonn_shared.primordia_policy import PrimordiaResearchPolicy
from . import campaign as c
from .audit import artifact_json

SYSTEMS = ["prism", "topograph", "stratograph", "primordia", "contenders"]
ARMS = ["reference", "epochs2", "epochs5", "epochs10", "alpha01", "alpha001"]
SEEDS = [1421, 1422]
QUALIFICATION_SEED = 1431
POLICY = {
    "schema_version": "evonn.language-baseline-screen/v1",
    "pack": "language_breadth_v1",
    "budget": 64,
    "seeds": SEEDS,
    "arms": ARMS,
    "systems": SYSTEMS,
    "runs": 60,
    "fits": 3840,
    "protected_test_access": False,
    "coverage": "Every arm/seed/system and all four tasks; four successful fits per baseline family/task/run.",
    "selection": "Descriptive nomination only after full coverage. For each family use the best validation attempt within each task/seed. Transformer candidates are reference/epochs2/epochs5/epochs10; n-gram candidates reference/alpha01/alpha001, using the best of unigram/bigram/trigram. Minimize the geometric mean perplexity ratio to reference over the three real-text tasks and two seeds. Require at least 2% aggregate improvement and at most 10% geometric-mean delayed-copy regression; otherwise retain reference. Exact ties use declared arm order. Nominate the two families separately; no combined-policy result is inferred.",
    "limits": "Two discovery seeds, no significance, test/generalization or architecture claim. Unchanged native controls across arms are repeated controls, not additional independent seeds. Baseline adequacy remains open pending independent confirmation.",
    "failures": "Stop on failed or incomplete slots; retain all artifacts. Never drop a system or automatically replace a failed Contenders run.",
    "pause": "Graceful pause between complete slots; native interrupted slots retain the campaign checkpoint recovery contract.",
}


def spec(arm, seed, index, *, qualification=False):
    offset = index % len(SYSTEMS)
    return c.CampaignSpec(
        pack=POLICY["pack"],
        budgets=[16 if qualification else POLICY["budget"]],
        seeds=[seed],
        systems=SYSTEMS[offset:] + SYSTEMS[:offset],
        backend="mlx_native",
        epochs=2 if qualification else 12,
        enhanced=True,
        contender_pool="lm_screen_v1_" + arm,
        prism_research=PrismResearchPolicy(),
        topograph_variant="open",
        stratograph_research=HierarchyResearchPolicy(evaluator="trainable", normalization="rms"),
        primordia_research=PrimordiaResearchPolicy(),
        timeout=1500.0,
        fit_timeout=90.0,
        min_free_bytes=20 * 1024**3,
    )


def matrix(*, qualification=False):
    rows = []
    for seed_index, seed in enumerate([QUALIFICATION_SEED] if qualification else SEEDS):
        order = ARMS[seed_index:] + ARMS[:seed_index]
        for arm_index, arm in enumerate(order):
            rows.append(
                {
                    "arm": arm,
                    "seed": seed,
                    "campaign": f"campaigns/s{seed}-{arm}",
                    "spec": spec(arm, seed, seed_index + arm_index, qualification=qualification).model_dump(
                        mode="json"
                    ),
                }
            )
    return rows


def read_plan(root):
    value = json.loads(c.read_document(root, "study.json"))
    if set(value) != {"schema_version", "policy", "qualification", "identity", "matrix", "sha256"}:
        raise ValueError("unexpected study fields")
    if value["schema_version"] != "evonn.baseline-study/v1" or type(value["qualification"]) is not bool:
        raise ValueError("unsupported study schema")
    if value["policy"] != POLICY or value["matrix"] != matrix(qualification=value["qualification"]):
        raise ValueError("study differs from preregistered matrix or interpretation")
    if value["sha256"] != c.sha({k: v for k, v in value.items() if k != "sha256"}):
        raise ValueError("study checksum mismatch")
    for row in value["matrix"]:
        manifest = c.read_manifest(root / row["campaign"])
        if manifest["spec"] != row["spec"] or manifest["identity"] != value["identity"]:
            raise ValueError("campaign differs from frozen study")
    return value


def prepare(root, cache, *, qualification=False):
    root = root.absolute()
    if root.exists():
        raise ValueError("use a fresh study directory; existing evidence is never replaced")
    root.mkdir(parents=True)
    pinned = c.identity()
    rows = matrix(qualification=qualification)
    for row in rows:
        c.prepare_plan(root / row["campaign"], c.CampaignSpec.model_validate(row["spec"]), cache)
    if c.identity() != pinned:
        raise ValueError("producer changed while preparing study")
    value = {
        "schema_version": "evonn.baseline-study/v1",
        "policy": POLICY,
        "qualification": qualification,
        "identity": pinned,
        "matrix": rows,
    }
    publish_artifact(root / "study.json", c.encoded({**value, "sha256": c.sha(value)}))
    return preflight(root)


def preflight(root):
    plan = read_plan(root)
    for row in plan["matrix"]:
        c.preflight(root / row["campaign"])
    return {
        "status": "ready",
        "qualification": plan["qualification"],
        "runs": len(plan["matrix"]) * 5,
        "fit_attempts": sum(row["spec"]["budgets"][0] * 5 for row in plan["matrix"]),
        "study_sha256": plan["sha256"],
        "training_started": False,
    }


def run(root):
    with c.lease(root / "controller"):
        preflight(root)
        plan = read_plan(root)
        for row in plan["matrix"]:
            workspace = root / row["campaign"]
            while True:
                if (root / "PAUSE").exists():
                    return {"status": "paused", "reason": "pause requested between slots"}
                result = c.run_campaign(workspace, max_runs=1)
                print(json.dumps({"arm": row["arm"], "seed": row["seed"], **result}), flush=True)
                if result["status"] == "complete":
                    break
                if result["new_runs"] == 0:
                    raise ValueError("campaign made no progress; retained for diagnosis")
        return report(root)


def nominate(baselines):
    """Apply the frozen descriptive rule; caller must first establish full coverage."""
    result = {}
    for family, arms in [
        ("transformer", ["reference", "epochs2", "epochs5", "epochs10"]),
        ("ngram", ["reference", "alpha01", "alpha001"]),
    ]:
        scores = {}
        for row in baselines:
            if row["arm"] not in arms:
                continue
            accepted = (
                row["family"] == "transformer_lm_tiny"
                if family == "transformer"
                else row["family"] in {"unigram_lm", "bigram_lm", "trigram_lm"}
            )
            if accepted:
                key = (row["arm"], row["seed"], row["benchmark"])
                scores[key] = min(scores.get(key, float("inf")), row["value"])
        real = [key for key in scores if key[0] == "reference" and key[2] != "delayed_copy_lm"]
        delayed = [key for key in scores if key[0] == "reference" and key[2] == "delayed_copy_lm"]
        rows = []
        for arm in arms:

            def ratio(keys):
                return math.exp(
                    statistics.mean(
                        math.log(scores[(arm, seed, task)] / scores[("reference", seed, task)])
                        for _, seed, task in keys
                    )
                )

            rows.append({"arm": arm, "real_text_ratio": ratio(real), "delayed_copy_ratio": ratio(delayed)})
        eligible = [r for r in rows if r["real_text_ratio"] <= 0.98 and r["delayed_copy_ratio"] <= 1.10]
        chosen = min(eligible, key=lambda r: r["real_text_ratio"])["arm"] if eligible else "reference"
        result[family] = {"nomination": chosen, "candidates": rows, "confirmation_required": True}
    return result


def report(root):
    plan = read_plan(root)
    complete, missing, failures, results, baselines = [], [], [], [], []
    for row in plan["matrix"]:
        workspace = root / row["campaign"]
        manifest = c.read_manifest(workspace)
        for case, system in c.slots(c.CampaignSpec.model_validate(row["spec"])):
            label = f"s{row['seed']}-{row['arm']}-{system}"
            try:
                run, reference = c.adopted(workspace, manifest, case, system)
                if reference is None:
                    missing.append(label)
                    continue
                bundle = read_export(workspace / reference["export"])
                complete.append(label)
                for task in c.load_parity_pack(case.pack).benchmarks:
                    candidates = [
                        r for r in bundle.results.records if r.benchmark_id == task and r.status.value == "ok"
                    ]
                    results.append(
                        {
                            "arm": row["arm"],
                            "seed": row["seed"],
                            "system": system,
                            "benchmark": task,
                            "value": min(r.metric.value for r in candidates),
                            "run_id": bundle.manifest.run_id,
                        }
                    )
                if system == "contenders":
                    for attempt in artifact_json(bundle, "attempts.json")["attempts"]:
                        if attempt["status"] == "ok":
                            baselines.append(
                                {
                                    "arm": row["arm"],
                                    "seed": row["seed"],
                                    "benchmark": attempt["benchmark_id"],
                                    "family": attempt["family"],
                                    "value": attempt["score"],
                                    "parameters": attempt["parameters"],
                                    "training_seconds": attempt["train_seconds"],
                                    "completed_epochs": attempt.get("completed_epochs"),
                                    "optimizer_updates": attempt.get("optimizer_updates"),
                                    "model_selection": attempt.get("model_selection"),
                                }
                            )
            except (ValueError, OSError, KeyError, TypeError) as error:
                failures.append({"slot": label, "reason": str(error)})
    done = len(complete) == len(plan["matrix"]) * 5 and not failures
    return {
        "status": "complete" if done else "incomplete",
        "qualification": plan["qualification"],
        "completed": len(complete),
        "declared": len(plan["matrix"]) * 5,
        "missing": missing,
        "failures": failures,
        "study_sha256": plan["sha256"],
        "results": results,
        "baselines": baselines,
        "nomination": nominate(baselines) if done and not plan["qualification"] else None,
        "interpretation": POLICY["limits"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "preflight", "run", "report", "pause", "resume"])
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--qualification", action="store_true")
    args = parser.parse_args(argv)
    root = args.workspace.absolute()
    try:
        if args.action == "prepare":
            if args.cache is None:
                raise ValueError("--cache required for preparation")
            result = prepare(root, args.cache, qualification=args.qualification)
        elif args.action == "pause":
            read_plan(root)
            (root / "PAUSE").touch(exist_ok=True)
            result = {"status": "pause_requested", "boundary": "between slots"}
        elif args.action == "resume":
            preflight(root)
            (root / "PAUSE").unlink(missing_ok=True)
            result = run(root)
        else:
            result = {"preflight": preflight, "run": run, "report": report}[args.action](root)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if result["status"] in {"ready", "complete", "paused", "pause_requested"} else 1
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"Baseline study: {error}\n")


if __name__ == "__main__":
    sys.exit(main())
