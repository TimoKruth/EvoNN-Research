"""Write matched all-system campaign specifications; never prepare data or fit."""

import argparse
from pathlib import Path

from evonn_compare.campaign import CampaignSpec
from evonn_shared.prism_policy import PrismResearchPolicy, V3_VARIANTS


VARIANTS = ("open", "search_v2", "representation_v2", "regularized_v2", "averaged_v2", "calibrated_v2", "frontier_v2")
SUPPORTED_VARIANTS = (*VARIANTS, "broad", *V3_VARIANTS)
SYSTEMS = {"prism", "topograph", "stratograph", "primordia", "contenders"}


def prepare(base, output, variants=VARIANTS):
    if set(base.systems) != SYSTEMS:
        raise ValueError("every arm requires Prism, Topograph, Stratograph, Primordia and Contenders")
    if not variants or len(set(variants)) != len(variants) or not set(variants) <= set(SUPPORTED_VARIANTS):
        raise ValueError("select unique supported frontier variants")
    policies = (base.prism_research or PrismResearchPolicy()).model_dump(mode="json")
    if policies["fixed_genomes"] and set(variants) & {"search_v2", "representation_v2", "frontier_v2", *V3_VARIANTS}:
        raise ValueError("fixed genomes suppress search/representation experiments; choose training-only variants")
    specs = {}
    for variant in variants:
        values = base.model_dump(mode="json")
        values["prism_research"] = {**policies, "variant": variant}
        specs[variant] = CampaignSpec.model_validate(values)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    for variant, spec in specs.items():
        (output / (variant + ".json")).write_text(spec.model_dump_json(indent=2) + "\n")
    return list(specs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-spec", type=Path, required=True,
                        help="existing JSON CampaignSpec specifying pack, budgets, seeds and full system roster")
    parser.add_argument("--output", type=Path, required=True, help="new directory; existing directories are rejected")
    parser.add_argument("--variants", nargs="+", choices=SUPPORTED_VARIANTS, default=VARIANTS)
    args = parser.parse_args()
    base = CampaignSpec.model_validate_json(args.base_spec.read_text())
    for name in prepare(base, args.output, args.variants):
        print(args.output / (name + ".json"))


if __name__ == "__main__":
    main()
