"""Explicit experimental policies, independent of the frozen legacy search."""

import math
from typing import Literal

Variant = Literal["legacy", "mechanics", "training", "archive", "broad", "open", "next"]
VARIANTS = ("legacy", "mechanics", "training", "archive", "broad", "open", "next")


def lookup(mapping, key, default=None):
    return mapping[key] if key in mapping else default


def take(mapping, key, default=None):
    value = lookup(mapping, key, default)
    if key in mapping:
        del mapping[key]
    return value


def policy(variant):
    if variant not in VARIANTS:
        raise ValueError("unknown Topograph research variant")
    return {name: variant in (name, "open", "next") for name in ("training", "archive", "broad")}


def allocate_training(epochs, generation, inheritance, parameters, *, protected=False, variant="open"):
    if not policy(variant)["training"]:
        full = max(1, math.ceil(epochs * (0.5 if generation == 0 else 1)))
        ratio = {"exact": 0.3, "partial": 0.6, "none": 1.0}[inheritance["mode"]]
        return full, max(1, math.ceil(full * ratio)), "legacy_discount"
    copied = min(1, max(0, inheritance["copied_parameters"] / max(1, parameters)))
    ratio = 1 if protected else 1 - 0.5 * copied
    return epochs, max(1, math.ceil(epochs * ratio)), "protected_full" if protected else "coverage_discount"


def runtime_profile(attempts):
    """Nested durations are named, never added as though they were disjoint."""
    keys = (
        "compile_inherit_seconds",
        "request_seconds",
        "worker_roundtrip_seconds",
        "search_seconds",
        "snapshot_seconds",
    )
    return {
        "coordinator": {k: sum(lookup(a.get("profile", {}), k, 0) for a in attempts) for k in keys},
        "worker": {
            k: sum(lookup(a.get("worker_profile", {}), k, 0) for a in attempts)
            for k in ("setup_seconds", "fit_seconds", "model_publication_seconds")
        },
        "scope": "Worker phases are nested in roundtrip. Checkpoint timing is optional after a crash; "
        "preparation and final export are outside these stage sums. Timing is diagnostic, not a compute-equivalence claim.",
    }


# The file-only consumer independently reconstructs these rules in Shared;
# search/training policy execution stays owned by Topograph.
def progressing(curve, selected_epoch):
    """Recent selected improvement, with a relative noise floor; not a forecast."""
    return (len(curve) >= 2 and selected_epoch >= len(curve) - 1
            and min(curve[-2:]) < curve[0] - max(1e-8, abs(curve[0]) * 0.01))


def next_allocation(epochs, copied, parameters, protected, settings, source_progress=False):
    if protected or settings.allocation == "full" or (settings.allocation == "progress" and source_progress):
        return epochs, "protected_full" if protected else "full" if settings.allocation == "full" else "progress_full"
    return max(1, math.ceil(epochs * (1 - 0.5 * copied / max(1, parameters)))), "coverage_discount"
