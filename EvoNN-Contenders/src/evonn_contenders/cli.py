"""Run fixed contender pools through the public CLI and file contract."""
import argparse
from pathlib import Path

from .config import load_official_lane
from .runner import run_contenders


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    selection = run.add_mutually_exclusive_group(required=True)
    selection.add_argument("--pack")
    selection.add_argument("--official-lane")
    run.add_argument("--budget", type=int)
    run.add_argument("--seed", type=int, default=42)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--cache", type=Path, required=True)
    run.add_argument("--pools", type=Path)
    run.add_argument("--timeout", type=float, default=1800)
    run.add_argument("--fit-timeout", type=float, default=180)
    run.add_argument("--enhanced", action="store_true")
    args = parser.parse_args(argv)
    try:
        pack, budget = args.pack, args.budget
        if args.official_lane:
            lane = load_official_lane(args.official_lane)
            pack = lane["benchmark_pack"]["pack_name"]
            if budget is not None and budget != lane["evaluation_count"]:
                raise ValueError("official lane budget cannot be overridden")
            budget = lane["evaluation_count"]
        output = run_contenders(pack_name=pack, budget=budget, seed=args.seed, output_parent=args.output,
                                cache_root=args.cache, pools_path=args.pools, timeout=args.timeout,
                                fit_timeout=args.fit_timeout, enhanced=args.enhanced)
    except (ValueError, OSError) as error:
        parser.exit(2, f"Contenders: {error}\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
