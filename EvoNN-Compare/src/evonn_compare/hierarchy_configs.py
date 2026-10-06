"""Emit unexecuted all-engine campaign specifications for Stratograph alternatives.

This does not freeze a scientific protocol, prepare datasets or launch training.
Use Compare's existing plan/preflight/run boundary on the resulting specs later.
"""
import argparse
import json
from pathlib import Path

from evonn_compare.campaign import CampaignSpec
from evonn_shared.hierarchy_presets import hierarchy_presets


def configurations(*, packs, budgets, seeds, arms, backend='mlx_native', epochs=12):
    presets = hierarchy_presets()
    specs = {}
    for pack in packs:
        for arm in arms:
            spec = CampaignSpec(pack=pack, budgets=budgets, seeds=seeds,
                                systems=['prism', 'topograph', 'stratograph', 'primordia', 'contenders'],
                                backend=backend, epochs=epochs, timeout=1200., fit_timeout=120.,
                                stratograph_research=presets[arm])
            specs[f'{pack}--{arm}'] = spec.model_dump(mode='json')
    return specs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new directory; never overwrite existing results')
    parser.add_argument('--packs', nargs='+', required=True)
    parser.add_argument('--budgets', nargs='+', type=int, required=True)
    parser.add_argument('--seeds', nargs='+', type=int, required=True)
    parser.add_argument('--arms', nargs='+', choices=tuple(hierarchy_presets()),
                        default=['v2_reference', 'attention', 'dilated', 'hybrid', 'evolving'])
    parser.add_argument('--backend', choices=['mlx_native', 'numpy_fallback'], default='mlx_native')
    parser.add_argument('--epochs', type=int, default=12)
    args = parser.parse_args(argv)
    specs = configurations(packs=args.packs, budgets=args.budgets, seeds=args.seeds,
                           arms=args.arms, backend=args.backend, epochs=args.epochs)
    args.output.mkdir(parents=True, exist_ok=False)
    for name, spec in specs.items():
        (args.output / f'{name}.json').write_text(json.dumps(spec, indent=2) + '\n')
    manifest = dict(status='unexecuted_configuration_templates', specs=list(specs),
                    total_runs=len(specs) * len(args.budgets) * len(args.seeds) * 5,
                    evidence='No fits, no superiority claim. Qualification and frozen scientific protocol remain pending.',
                    completion='Every arm requires every declared system/benchmark/budget/seed; failures remain incomplete.')
    (args.output / 'index.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(args.output)


if __name__ == '__main__':
    main()
