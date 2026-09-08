"""Bounded matched ablations and verified winner-motif inspection."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import uuid

from evonn_shared.active_catalog import load_parity_pack
from evonn_shared.artifact_io import create_artifact_directory
from evonn_shared.engine_evidence import artifact_json, validate_engine_bundle
from evonn_shared.export_reader import read_export
from evonn_shared.runtime_io import derived, encode
from .config import RunConfig
from .run import run_engine
from .search import Search

VARIANTS = ("shared", "flat", "unshared", "no-clone", "no-motif-bias")


def analyze_motifs(run_directory):
    bundle = read_export(Path(run_directory) / "symbiosis")
    if bundle.manifest.system.value != "stratograph":
        raise ValueError("Stratograph export required")
    validate_engine_bundle(bundle, verify_cache=True)
    return artifact_json(bundle, "motif_analysis.json")


def ablation(*, configs, output, cache, timeout):
    """Every variant gets the same case settings; timeout caps the entire batch."""
    if not configs or not 0 < timeout <= 1800 or any(config.timeout > timeout for config in configs):
        raise ValueError("nonempty ablation and total timeout in (0,1800] required")
    started = time.monotonic()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:10]
    root = create_artifact_directory(Path(output) / ("ablation_" + stamp))
    summary = dict(
        schema_version=1,
        status="running",
        decision_grade=False,
        cases=[],
        planned_runs=len(configs) * len(VARIANTS),
        timeout_seconds=timeout,
    )
    derived(root / "ablation.json", encode(summary))
    try:
        for config in configs:
            for variant in VARIANTS:
                remaining = timeout - (time.monotonic() - started)
                if remaining < config.timeout:
                    raise TimeoutError("ablation batch time limit reached")
                exported = run_engine(
                    Search,
                    pack_name=config.pack,
                    budget=config.budget,
                    seed=config.seed,
                    output_parent=root / "runs",
                    cache_root=cache,
                    backend=config.backend,
                    device=config.target_device,
                    timeout=config.timeout,
                    fit_timeout=config.fit_timeout,
                    epochs=config.epochs,
                    population_size=config.population_size,
                    variant=variant,
                )
                bundle = read_export(exported)
                validate_engine_bundle(bundle, verify_cache=True)
                if (
                    bundle.manifest.status.value != "completed"
                    or bundle.results.coverage.failed
                    or bundle.results.coverage.unsupported
                ):
                    raise ValueError("ablation requires completed fits for every variant")
                summary["cases"].append(
                    dict(
                        pack=config.pack,
                        budget=config.budget,
                        seed=config.seed,
                        variant=variant,
                        run_id=bundle.manifest.run_id,
                        export=str(exported),
                        source_commit=bundle.manifest.git_commit,
                        winners=artifact_json(bundle, "motif_analysis.json")["local_winners"],
                    )
                )
                derived(root / "ablation.json", encode(summary))
        summary["status"] = "completed"
    except (ValueError, OSError, TimeoutError) as error:
        summary["status"], summary["reason"] = "incomplete", str(error)
        raise
    finally:
        summary["elapsed_seconds"] = time.monotonic() - started
        derived(root / "ablation.json", encode(summary))
    return root / "ablation.json"


def main(argv):
    parser = argparse.ArgumentParser(prog="evonn-stratograph", allow_abbrev=False)
    commands = parser.add_subparsers(dest="command", required=True)
    motifs = commands.add_parser("motifs").add_subparsers(dest="action", required=True)
    analyze = motifs.add_parser("analyze")
    analyze.add_argument("run_directory", type=Path)
    batch = commands.add_parser("ablate", aliases=["ablate-matrix"], allow_abbrev=False)
    batch.add_argument("--pack", default="tier_a_contract")
    budget = batch.add_mutually_exclusive_group()
    budget.add_argument("--budget", type=int)
    budget.add_argument("--budgets", type=int, nargs="+")
    batch.add_argument("--seeds", type=int, nargs="+", default=[42])
    batch.add_argument("--output", type=Path, default=Path(".artifacts/stratograph-ablations"))
    batch.add_argument("--cache", type=Path, default=Path(".artifacts/dataset-cache"))
    batch.add_argument("--backend", choices=["numpy_fallback", "mlx_native"], default="numpy_fallback")
    batch.add_argument("--epochs", type=int, default=12)
    batch.add_argument("--population-size", type=int, default=4)
    batch.add_argument("--timeout", type=float, default=1800, help="whole-batch wall-clock limit, at most 1800 seconds")
    batch.add_argument("--run-timeout", type=float, default=300, help="identical per-run cap for every variant")
    batch.add_argument("--fit-timeout", type=float, default=90)
    options = parser.parse_args(argv)
    try:
        if options.command == "motifs":
            print(json.dumps(analyze_motifs(options.run_directory), sort_keys=True))
            return
        budgets = options.budgets or [options.budget if options.budget is not None else 16]
        if len(set(budgets)) != len(budgets) or len(set(options.seeds)) != len(options.seeds):
            raise ValueError("ablation cases must be unique")
        pack = load_parity_pack(options.pack)
        configs = [
            RunConfig(
                pack=options.pack,
                budget=budget,
                seed=seed,
                backend=options.backend,
                epochs=options.epochs,
                population_size=options.population_size,
                timeout=options.run_timeout,
                fit_timeout=options.fit_timeout,
            )
            for budget in budgets
            for seed in options.seeds
        ]
        if any(config.budget % len(pack.benchmarks) for config in configs):
            raise ValueError("ablation budget must be divisible across the pack")
        print(ablation(configs=configs, output=options.output, cache=options.cache, timeout=options.timeout))
    except (ValueError, OSError, TimeoutError) as error:
        parser.exit(1, f"stratograph: {error}\n")
