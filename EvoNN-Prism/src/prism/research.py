"""Versioned experimental policies; resource bounds remain run-level contracts."""

import math
from typing import Literal
from evonn_shared.canonical import canonical_sha256

Variant = Literal["legacy", "archive", "training", "broad", "open"]
VARIANTS = ("legacy", "archive", "training", "broad", "open")


def policy(variant):
    if variant not in VARIANTS:
        raise ValueError("unknown Prism research variant")
    return {
        "archive": variant in {"archive", "open"},
        "training": variant in {"training", "open"},
        "broad": variant in {"broad", "open"},
    }


def allocate_training(epochs, generation, inheritance, parameters, *, protected=False, variant="open"):
    """Coverage is a discount ceiling, never proof that transferred weights help."""
    if not policy(variant)["training"]:
        full = max(1, math.ceil(epochs * (0.5 if generation == 0 else 1)))
        ratio = {"exact": .3, "partial": .6, "none": 1.0}[inheritance["mode"]]
        return full, max(1, math.ceil(full * ratio)), "legacy_inheritance_discount"
    if protected or inheritance["mode"] == "none":
        return epochs, epochs, "protected_full" if protected else "fresh_full"
    if inheritance.get("source_needs_more_training", False):
        return epochs, epochs, "learning_progress_full"
    coverage = min(1.0, max(0.0, inheritance["copied_parameters"] / max(1, parameters)))
    # Partial transfers never receive a stronger discount than the old policy;
    # low-coverage transfers receive nearly the full budget.
    ratio = .3 if inheritance["mode"] == "exact" else 1 - .4 * coverage
    return epochs, max(1, math.ceil(epochs * ratio)), "coverage_discount"


def summarize_attempts(attempts):
    """Expose discovery and continuation separately without treating hashes as diversity."""
    panels = {}
    for attempt in attempts:
        panel = panels.setdefault(attempt["benchmark_id"], {
            "fits": 0, "new_genomes": 0, "revisited_genomes": 0, "family_fits": {},
            "protected_fits": 0, "fresh_initializations": 0, "optimizer_updates": 0,
            "train_seconds": 0.0, "seen": set(),
            "architectures": set(),
        })
        identity = attempt["genome_id"]
        panel["fits"] += 1
        panel["revisited_genomes" if identity in panel["seen"] else "new_genomes"] += 1
        panel["seen"].add(identity)
        if attempt.get("architecture_id"):
            panel["architectures"].add(attempt["architecture_id"])
        family = attempt["genome"]["family"]
        panel["family_fits"][family] = panel["family_fits"].get(family, 0) + 1
        panel["protected_fits"] += bool(attempt.get("proposal", {}).get("protected", False))
        panel["fresh_initializations"] += attempt["inheritance"]["mode"] == "none"
        panel["optimizer_updates"] += attempt.get("updates", 0)
        panel["train_seconds"] += attempt.get("train_seconds", 0.0)
    return {key: {**{k: v for k, v in panel.items() if k not in {"seen", "architectures"}},
                  "distinct_executed_architectures": len(panel["architectures"])} for key, panel in panels.items()}


def architecture_identity(genome):
    """Ignore optimizer genes and fields not executed by this architecture."""
    family = genome.family
    kinds = {b.kind for b in genome.blocks}
    fields = {"family", "activation", "norm_type", "dropout"}
    fields.add("blocks" if family == "composite" else "hidden_layers")
    if family not in {"mlp", "sparse_mlp", "moe_mlp", "conv1d", "lite_conv1d", "conv2d", "lite_conv2d"}:
        fields.add("embedding_dim")
    if "conv" in family or kinds & {"conv1d", "conv2d"}:
        fields.add("kernel_size")
    if "attention" in family or family == "causal_transformer" or "attention" in kinds:
        fields.update({"position_encoding", "num_heads", "ffn_ratio"})
    if family == "causal_transformer" or "attention" in kinds:
        fields.add("kv_heads")
    if "sparse" in family or "sparse" in kinds:
        fields.add("activation_sparsity")
    if family == "moe_mlp":
        fields.update({"num_experts", "moe_top_k"})
    if family in {"mlp", "sparse_mlp"}:
        fields.add("residual")
    return canonical_sha256(genome.model_dump(mode="json", include=fields),
                            schema_version="prism.executed-architecture/v1", digest_field=None)


def finalist_seeding(prior):
    """Prior architecture discovery is reported separately from new training work."""
    if prior is None:
        return None
    import json
    from evonn_shared.telemetry import SeedingMetadata
    source_digest = prior.get("source_manifest_sha256", "")
    if not isinstance(source_digest, str) or len(source_digest) != 64 or any(c not in "0123456789abcdef" for c in source_digest):
        raise ValueError("finalist provenance requires a source manifest digest")
    value = {"seeding_enabled": True, "seeding_ladder": "direct", "seed_source_system": "prism",
             "seed_source_run_id": prior.get("source_run_id"), "seed_artifact_path": "config.yaml",
             "seed_target_family": "fixed architectures per benchmark", "seed_selected_family": "fixed architectures per benchmark",
             "seed_rank": 1, "seed_overlap_policy": "benchmark-overlapping",
             "seed_cost_accounting": "reported_prior", "seed_source_evaluations": prior.get("source_fits")}
    return SeedingMetadata.model_validate_json(json.dumps(value)).model_dump(mode="json")
