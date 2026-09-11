"""File-only consumer validation of Topograph's additive research evidence."""

import math
from .canonical import canonical_sha256

VARIANTS = {"mechanics", "training", "archive", "broad", "open"}


def lookup(mapping, key, default=None):
    return mapping[key] if key in mapping else default


def expected_epochs(config, attempt, state, telemetry):
    variant = config.get("variant", "legacy")
    if variant == "legacy":
        if attempt["genome"].get("schema_version", 1) != 1:
            raise ValueError("Topograph v2 genome requires a versioned research policy")
        return None
    if (
        variant not in VARIANTS
        or config.get("search_policy_version") != 2
        or config.get("genome_schema") != "topograph.genome/v2"
        or state["search"].get("variant") != variant
        or state["search"].get("research_schema") != 2
        or telemetry.get("research", {}).get("variant") != variant
        or config["benchmark_pooling"]
        or config["novelty_weight"]
    ):
        raise ValueError("Topograph research policy/configuration disagreement")
    genome = attempt["genome"]
    if genome.get("schema_version") != 2:
        raise ValueError("Topograph research genome version missing")
    canonical = dict(genome)
    for name in ("layers", "connections", "experts"):
        canonical[name] = sorted(genome[name], key=lambda g: g["innovation"])
    canonical["convolutions"] = sorted(genome["convolutions"], key=lambda g: g["layer"])
    if canonical_sha256(canonical, schema_version="topograph.genome/v2", digest_field=None) != attempt["genome_id"]:
        raise ValueError("Topograph genome identity mismatch")
    proposal = attempt.get("proposal", {})
    if (
        proposal.get("source")
        not in {"initial", "champion", "species", "diversity", "uncertain", "reservoir", "immigrant", "fresh_control"}
        or type(proposal.get("protected")) is not bool
        or type(proposal.get("fresh")) is not bool
        or not isinstance(proposal.get("parents"), list)
        or proposal.get("actual") != proposal.get("requested")
    ):
        raise ValueError("invalid Topograph proposal or operator attribution")
    history = state["search"]["benchmarks"][attempt["benchmark_id"]]
    event = next((e for e in history["events"] if e.get("outcome_id") == attempt["outcome_id"]), None)
    if (
        event is None
        or any(lookup(event, k) != v for k, v in proposal.items())
        or event["identity"] != attempt["genome_id"]
    ):
        raise ValueError("Topograph proposal differs from durable search event")
    copied = attempt["inheritance"]["copied_parameters"]
    parameters = attempt.get("compiled_parameters")
    if type(parameters) is not int or parameters < 0 or type(copied) is not int or not 0 <= copied <= parameters:
        raise ValueError("invalid Topograph copied parameter accounting")
    if attempt["status"] == "ok" and parameters != attempt["parameter_count"]:
        raise ValueError("Topograph compiled/measured parameter count mismatch")
    if proposal["fresh"] and attempt["inheritance"]["mode"] != "none":
        raise ValueError("Topograph fresh control inherited weights")
    if variant in {"training", "open"}:
        if attempt["full_epochs"] != config["epochs"]:
            raise ValueError("Topograph research training cap mismatch")
        ratio = 1 if proposal["protected"] else 1 - 0.5 * copied / max(1, parameters)
        allocated = max(1, math.ceil(config["epochs"] * ratio))
        if attempt["status"] == "ok" and proposal["protected"] and attempt["epochs"] != allocated:
            raise ValueError("Topograph protected candidate did not receive its allocation")
    else:
        full = max(1, math.ceil(config["epochs"] * (0.5 if attempt["generation"] == 0 else 1)))
        if attempt["full_epochs"] != full:
            raise ValueError("Topograph legacy training cap mismatch")
        allocated = max(1, math.ceil(full * {"none": 1, "partial": 0.6, "exact": 0.3}[attempt["inheritance"]["mode"]]))
    if attempt["status"] == "ok":
        curve, behavior = attempt.get("validation_curve"), attempt.get("behavior_descriptor")
        if (
            not isinstance(curve, list)
            or len(curve) != attempt["epochs"]
            or not isinstance(behavior, list)
            or len(behavior) != 16
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in curve + behavior)
            or attempt.get("behavior_source") != "training_probe/v1"
        ):
            raise ValueError("invalid Topograph learning curve or training-only behavior descriptor")
    history = {a["outcome_id"]: a for a in state["attempts"]}
    ancestry = sorted(set(attempt["inheritance"].get("ancestor_attempts", []) + [attempt["outcome_id"]]))
    if any(
        a not in history or a > attempt["outcome_id"] or history[a]["benchmark_id"] != attempt["benchmark_id"]
        for a in ancestry
    ):
        raise ValueError("Topograph ancestry crosses a task or references future/absent work")
    expected = {k: sum(lookup(history[a], k, 0) for a in ancestry) for k in ("epochs", "updates", "train_seconds")}
    expected["attempts"] = ancestry
    if attempt.get("ancestral_training") != expected:
        raise ValueError("Topograph ancestral training accounting mismatch")
    return allocated


def validate_profile(profile, attempts):
    coordinator = (
        "compile_inherit_seconds",
        "request_seconds",
        "worker_roundtrip_seconds",
        "search_seconds",
        "snapshot_seconds",
    )
    worker = ("setup_seconds", "fit_seconds", "model_publication_seconds")
    for output, source, keys in (("coordinator", "profile", coordinator), ("worker", "worker_profile", worker)):
        expected = {k: sum(lookup(lookup(a, source, {}), k, 0) for a in attempts) for k in keys}
        if lookup(profile, output) != expected or any(not math.isfinite(v) or v < 0 for v in expected.values()):
            raise ValueError("Topograph runtime profile differs from measured attempt stages")
    timings = profile.get("checkpoint_publications", [])
    ids = [t["attempt"] for t in timings]
    if len(ids) != len(set(ids)) or any(type(i) is not int or not 1 <= i <= len(attempts) for i in ids):
        raise ValueError("invalid Topograph checkpoint timing identifiers")
    if any(not math.isfinite(t["checkpoint_seconds"]) or t["checkpoint_seconds"] < 0 for t in timings):
        raise ValueError("invalid Topograph checkpoint timing")
    if profile.get("missing_checkpoint_timings") != sorted(set(range(1, len(attempts) + 1)) - set(ids)):
        raise ValueError("Topograph missing checkpoint timing accounting mismatch")
