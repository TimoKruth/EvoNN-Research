"""Prepare fresh-seed, all-engine tests of post-study Prism hypotheses; no fits."""
import argparse
from pathlib import Path

from .campaign import CampaignSpec
from .prism_frontier import prepare as prepare_frontier
from evonn_shared.prism_policy import V3_VARIANTS

VARIANTS = ("open", "broad", "frontier_v2", *V3_VARIANTS)


def prepare(base, output, variants=VARIANTS):
    if base.comparison_scope != "all_engines" or base.prism_version_study is not None:
        raise ValueError("new Prism hypotheses require the ordinary all-engine scope")
    if set(base.seeds) & set(range(21600, 21631)):
        raise ValueError("confirmation requires fresh seeds outside the completed Prism study")
    if not set(variants) <= set(VARIANTS):
        raise ValueError("select a supported follow-up variant")
    return prepare_frontier(base, output, variants)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=VARIANTS)
    args = parser.parse_args()
    for variant in prepare(CampaignSpec.model_validate_json(args.base_spec.read_text()), args.output, args.variants):
        print(args.output / (variant + ".json"))


if __name__ == "__main__":
    main()
