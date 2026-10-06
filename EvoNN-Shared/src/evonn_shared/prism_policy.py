"""Portable Prism experiment declarations, with no search/compiler implementation."""

from typing import Literal, get_args
from pydantic import BaseModel, ConfigDict


PrismVariant = Literal["legacy", "archive", "training", "broad", "open", "search_v2",
                       "representation_v2", "regularized_v2", "averaged_v2", "calibrated_v2", "frontier_v2",
                       "routed_v3", "lean_v3", "aligned_v3"]
PRISM_VARIANTS = get_args(PrismVariant)
V3_VARIANTS = ("routed_v3", "lean_v3", "aligned_v3")


def prism_policy_flags(variant, *, task=None):
    """Portable deterministic declaration; v3 routes by task kind, never dataset ID.

    New combinations are post-study hypotheses, not promoted study winners.
    Historical policy dictionaries and their execution semantics stay unchanged.
    """
    if variant not in PRISM_VARIANTS:
        raise ValueError("unknown Prism research variant")
    if variant in V3_VARIANTS:
        if task not in {"classification", "regression", "language_modeling"}:
            raise ValueError("task kind is required for a routed Prism policy")
        flags = prism_policy_flags("broad" if task == "language_modeling" else "frontier_v2")
        if variant in {"lean_v3", "aligned_v3"}:
            flags.update(regularized=False, averaged=False)
        return {**flags, "aligned": variant == "aligned_v3" and task == "classification"}
    v2 = variant.endswith("_v2")
    return {
        "archive": variant in {"archive", "open"} or v2,
        "training": variant in {"training", "open"} or v2,
        "broad": variant in {"broad", "open"} or v2,
        **{name: variant in {name + "_v2", "frontier_v2"}
           for name in ("search", "representation", "regularized", "averaged", "calibrated")},
    }


class PrismResearchPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    variant: PrismVariant = "open"
    inheritance_policy: Literal["enabled", "disabled"] = "enabled"
    optimizer_policy: Literal["restart", "continue"] = "restart"
    optimizer_backend: Literal["numpy", "native"] = "numpy"
    fixed_genomes: dict[str, dict] | None = None
    prior_discovery: dict | None = None
