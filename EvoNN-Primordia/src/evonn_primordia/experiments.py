"""Generate reviewable all-engine campaign specifications without starting fits."""
import argparse
import json
from pathlib import Path

from evonn_shared.active_catalog import load_parity_pack
from evonn_shared.primordia_policy import PrimordiaResearchPolicy


from evonn_shared.primordia_presets import ARMS, PRESETS

SYSTEMS = ['prism', 'topograph', 'stratograph', 'primordia', 'contenders']


def specifications(*, pack, budgets, seeds, epochs=12, backend='mlx_native', arms=None, max_width=48, max_depth=8):
    """Each arm repeats every system and case; no baseline reuse or promotion."""
    selected = list(ARMS) if arms is None else list(arms)
    if not selected or len(set(selected)) != len(selected) or any(arm not in PRESETS for arm in selected):
        raise ValueError('unique known research arms required')
    if not budgets or len(set(budgets)) != len(budgets) or any(type(v) is not int or not 1 <= v <= 256 for v in budgets):
        raise ValueError('unique budgets in [1,256] required')
    if not seeds or len(set(seeds)) != len(seeds) or any(type(v) is not int or not 0 <= v < 2**32 for v in seeds):
        raise ValueError('unique unsigned 32-bit seeds required')
    if type(epochs) is not int or not 1 <= epochs <= 100 or backend not in {'mlx_native', 'numpy_fallback'}:
        raise ValueError('invalid bounded epochs/backend')
    pack_definition = load_parity_pack(pack)
    if any(v % len(pack_definition.benchmarks) for v in budgets):
        raise ValueError('budgets must be divisible across the pack')
    if len(budgets) > 16 or len(seeds) > 64 or len(budgets) * len(seeds) * len(SYSTEMS) > 512:
        raise ValueError('arm exceeds campaign size limits')
    from evonn_shared.active_catalog import get_benchmark
    if any(budget // len(pack_definition.benchmarks) < len(get_benchmark(name).required_contenders)
           for budget in budgets for name in pack_definition.benchmarks):
        raise ValueError('budget cannot cover the required contender floor')
    return {arm: dict(pack=pack, budgets=budgets, seeds=seeds, systems=list(SYSTEMS), backend=backend,
                      epochs=epochs, enhanced=True, timeout=1740., fit_timeout=120.,
                      primordia_research=PrimordiaResearchPolicy(max_width=max_width, max_depth=max_depth,
                                                               **PRESETS[arm]).model_dump(),
                      analysis='descriptive_repeated_seed_no_superiority_claim')
            for arm in selected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--pack', default='tier_b_core_v2')
    parser.add_argument('--budgets', type=int, nargs='+', default=[128, 256])
    parser.add_argument('--seeds', type=int, nargs='+', required=True)
    parser.add_argument('--epochs', type=int, default=12)
    parser.add_argument('--backend', choices=['mlx_native', 'numpy_fallback'], default='mlx_native')
    parser.add_argument('--arms', choices=list(PRESETS), nargs='+')
    parser.add_argument('--max-width', type=int, default=48)
    parser.add_argument('--max-depth', type=int, default=8)
    args = parser.parse_args()
    output = args.output
    specs = specifications(**{key: value for key, value in args._get_kwargs() if key != 'output'})
    output.mkdir(parents=True, exist_ok=False)
    for arm, spec in specs.items():
        (output / (arm + '.json')).write_text(json.dumps(spec, indent=2) + '\n')
    (output / 'README.md').write_text(
        '# Primordia research specifications\n\n'
        'Generated specifications only; no campaign has been prepared or executed.\n'
        'Every arm includes all four engines and Contenders on every declared case.\n'
        'Prepare each JSON with `evonn-compare campaign plan --workspace BASE --spec FILE --cache CACHE` '
        'from one clean, locked producer, then qualify and run the resulting campaigns.\n'
        'Retain failures; incomplete arms remain incomplete. Compare validation quality, '
        'actual updates and training seconds as well as fit counts.\n'
        'These are mechanistic screening arms, not a superiority protocol. Select a bounded subset '
        'before execution; fresh-seed confirmation and multiplicity-aware analysis remain required.\n'
        '`full_cold` disables inheritance during search; diverging proposals make it an end-to-end '
        'search ablation, not a matched-finalist warm/cold test.\n')
    print(output)


if __name__ == '__main__':
    main()
