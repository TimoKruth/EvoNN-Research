"""Materialize editable ablation inputs without planning or launching training."""
import argparse
import json
from pathlib import Path

from evonn_shared.topograph_policy import TopographResearchPolicy


# Each intervention is relative to next; open is a separate historical-policy control.
INTERVENTIONS = {
    "next": {},
    "query": {"adapters": "query"},
    "mixer": {"adapters": "mixer"},
    "legacy_adapters": {"adapters": "legacy"},
    "full_training": {"allocation": "full"},
    "coverage_training": {"allocation": "coverage"},
    "quality_selection": {"selection": "quality"},
    "broad_mutation": {"mutation_scale": "broad"},
    "cold": {"inheritance": "disabled"},
    "no_smoothing": {"label_smoothing": 0.0},
    "all_decay": {"decay": "all"},
    "wide_cap": {"parameter_cap": 2_000_000},
    "more_crossover": {"crossover_probability": 0.25},
}


def configurations():
    """All-engine templates, not a registered protocol or an execution decision."""
    for name in ("open", *INTERVENTIONS):
        options = None if name == "open" else TopographResearchPolicy(**INTERVENTIONS[name]).model_dump(mode="json")
        variant = "open" if name == "open" else "next"
        yield name, {
            "variant": variant, "research_options": options,
            "pack": "tier1_core_smoke", "budget": 32, "epochs": 2, "seed": 42,
            "population_size": 2, "backend": "numpy_fallback", "timeout": 220, "fit_timeout": 20,
        }, {
            "pack": "tier_b_core_v2", "budgets": [128, 256], "seeds": [1501, 1502, 1503],
            "systems": ["prism", "topograph", "stratograph", "primordia", "contenders"],
            "backend": "mlx_native", "epochs": 12, "timeout": 1740.0, "fit_timeout": 120.0,
            "topograph_variant": variant, "topograph_research": options,
            "analysis": "descriptive_repeated_seed_no_superiority_claim",
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    for name, run, campaign in configurations():
        for suffix, config in (("run", run), ("campaign", campaign)):
            (args.output / f"{name}.{suffix}.json").write_text(json.dumps(config, indent=2) + "\n")
    (args.output / "README.md").write_text(
        "# Topograph experimental controls\n\n"
        "Generated inputs only: no campaign has been registered or run. Review packs, seeds, "
        "budgets and host limits before freezing an execution protocol. Each campaign repeats "
        "Prism, Topograph, Stratograph, Primordia and Contenders on every declared combination.\n\n"
        "Each named switch is relative to next; open retains its earlier search policy. "
        "Search trajectories can diverge after any intervention, including cold inheritance. "
        "These are search-policy comparisons, not matched-finalist causal tests. "
        "Budgets count fits, not equal compute. The breadth comparison remains historically incomplete; "
        "these templates do not replace that evidence or unlock the larger study.\n"
    )
    print(args.output)


if __name__ == "__main__":
    main()
