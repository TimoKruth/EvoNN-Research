"""Common CLI surface with explicit engine-supplied search/compiler types."""

import argparse
import json
from pathlib import Path
import sys
import yaml
from .active_catalog import load_parity_pack
from .runtime_io import prepare_worker, boundary_ownership
from .export_reader import read_document, read_export


def main(search_type, genome_type, run_engine, evaluation_worker, config_type, replay_export, argv=None, *, dataset_loader=None, inspect_extra=None, run_options=None):
    run_options = run_options or {}
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in {"_prepare", "_worker"}:
        request = json.loads(read_document(Path(argv[1]).parent, Path(argv[1]).name, limit=128 * 1024**2))
        if argv[0] == "_prepare":
            prepare_worker(request, Path(argv[2]), dataset_loader=dataset_loader)
        else:
            with boundary_ownership(Path(argv[2]).parent, ".worker.lock", timeout=1800):
                if Path(argv[2]).exists():
                    return
                if (Path(argv[2]).parent / "started").exists():
                    raise ValueError("interrupted started worker cannot be silently retrained")
                evaluation_worker(request, Path(argv[2]), search_type, genome_type)
        return
    parser = argparse.ArgumentParser(prog="evonn-" + search_type.system)
    sub = parser.add_subparsers(dest="verb", required=True)
    run = sub.add_parser("evolve", aliases=["run"], allow_abbrev=False)
    run.add_argument("--config", type=Path)
    run.add_argument("--pack", default="tier1_core")
    run.add_argument("--budget", type=int, default=64)
    run.add_argument("--seed", type=int, default=42)
    run.add_argument("--output", type=Path, default=Path(".artifacts/engine-runs"))
    run.add_argument("--cache", type=Path, default=Path(".artifacts/dataset-cache"))
    run.add_argument("--backend", choices=["numpy_fallback", "mlx_native"], default="numpy_fallback")
    run.add_argument("--target-device", choices=["cpu", "gpu"], default="cpu")
    run.add_argument("--timeout", type=float, default=1200.0)
    run.add_argument("--fit-timeout", type=float, default=120.0)
    run.add_argument("--epochs", type=int, default=12)
    run.add_argument("--population-size", type=int, default=4)
    if search_type.system == "primordia":
        run.add_argument("--search-policy", choices=["legacy_v1", "breadth_v2"], default="breadth_v2")
        run.add_argument("--max-width", type=int, default=48)
        run.add_argument("--max-depth", type=int, default=8)
    for name, settings in run_options.items():
        run.add_argument("--" + name.replace("_", "-"), **settings)
    if search_type.system == "topograph":
        run.add_argument("--benchmark-pooling", action="store_true")
        run.add_argument("--novelty-weight", type=float, default=0)
    if search_type.system == "stratograph":
        run.add_argument("--research", type=json.loads, help="explicit versioned Stratograph research policy as JSON")
        run.add_argument("--variant", choices=["shared", "flat", "unshared", "no-clone", "no-motif-bias"], default="shared")
    run.add_argument("--resume", type=Path)
    run.add_argument("--stop-after", type=int)
    # Explicit fault injection is limited to testing local persistence boundaries.
    run.add_argument(
        "--crash-at", choices=["worker", "transaction", "row", "stage", "payload", "manifest"], help=argparse.SUPPRESS
    )
    run.add_argument("--crash-step", type=int, default=1, help=argparse.SUPPRESS)
    for verb in ("inspect", "report", "symbiosis-export", "replay"):
        command = sub.add_parser(verb)
        command.add_argument("run_directory", type=Path)
    benchmarks = sub.add_parser("benchmarks")
    benchmarks.add_argument("--pack", default="tier1_core")
    cache = sub.add_parser("warm-cache")
    cache.add_argument("--pack", default="tier1_core")
    cache.add_argument("--seed", type=int, default=42)
    cache.add_argument("--cache", type=Path, required=True)
    options = parser.parse_args(argv)
    try:
        if options.verb in {"evolve", "run"}:
            user_config = {}
            if options.config:
                try:
                    user_config = yaml.safe_load(read_document(options.config.parent, options.config.name))
                except yaml.YAMLError as error:
                    raise ValueError(f"invalid config YAML: {error}") from error
                if not isinstance(user_config, dict):
                    raise ValueError("config must be a mapping")
            supplied_config_fields = set(user_config)
            fields = (
                "pack",
                "budget",
                "seed",
                "epochs",
                "population_size",
                "backend",
                "target_device",
                "timeout",
                "fit_timeout",
            )
            values = {
                "pack": options.pack,
                "budget": options.budget,
                "seed": options.seed,
                "epochs": options.epochs,
                "population_size": options.population_size,
                "backend": options.backend,
                "target_device": options.target_device,
                "timeout": options.timeout,
                "fit_timeout": options.fit_timeout,
            }
            if search_type.system == "topograph":
                fields = (*fields, "benchmark_pooling", "novelty_weight")
                values.update(benchmark_pooling=options.benchmark_pooling, novelty_weight=options.novelty_weight)
            if search_type.system == "stratograph":
                fields = (*fields, "variant", "research")
                values["variant"] = options.variant
                values["research"] = options.research
            if search_type.system == "primordia":
                fields = (*fields, "search_policy", "max_width", "max_depth")
                values.update(search_policy=options.search_policy, max_width=options.max_width, max_depth=options.max_depth)
            fields = (*fields, *run_options)
            values.update({name: getattr(options, name) for name in run_options})
            for field in fields:
                flag = "--" + field.replace("_", "-")
                explicit = any(arg == flag or arg.startswith(flag + "=") for arg in argv)
                if explicit or field not in user_config:
                    user_config[field] = values[field]
            validated = config_type.model_validate(user_config)
            options.pack, options.budget, options.seed = validated.pack, validated.budget, validated.seed
            options.epochs, options.population_size, options.backend = (
                validated.epochs,
                validated.population_size,
                validated.backend,
            )
            options.target_device, options.timeout, options.fit_timeout = (
                validated.target_device,
                validated.timeout,
                validated.fit_timeout,
            )
            config = {
                "pack_name": options.pack,
                "budget": options.budget,
                "seed": options.seed,
                "output_parent": options.output,
                "cache_root": options.cache,
                "backend": options.backend,
                "device": options.target_device,
                "timeout": options.timeout,
                "fit_timeout": options.fit_timeout,
                "epochs": options.epochs,
                "population_size": options.population_size,
            }
            if search_type.system == "topograph":
                config.update(benchmark_pooling=validated.benchmark_pooling, novelty_weight=validated.novelty_weight)
            if search_type.system == "stratograph":
                config["variant"] = validated.variant
                config["research"] = validated.research.model_dump(mode="json") if validated.research else None
            if search_type.system == "primordia":
                config.update(search_policy=validated.search_policy, max_width=validated.max_width, max_depth=validated.max_depth)
            if run_options:
                serialized_config = validated.model_dump(mode="json")
                config.update({name: serialized_config[name] for name in run_options})
            if options.resume:
                stored = json.loads(read_document(options.resume, "config.yaml"))
                mappings = {
                    "pack_name": "pack",
                    "budget": "total",
                    "seed": "seed",
                    "cache_root": "cache",
                    "backend": "backend",
                    "device": "device",
                    "timeout": "timeout",
                    "fit_timeout": "fit_timeout",
                    "epochs": "epochs",
                    "population_size": "population_size",
                }
                flags = {
                    "pack_name": "--pack",
                    "budget": "--budget",
                    "seed": "--seed",
                    "cache_root": "--cache",
                    "backend": "--backend",
                    "device": "--target-device",
                    "timeout": "--timeout",
                    "fit_timeout": "--fit-timeout",
                    "epochs": "--epochs",
                    "population_size": "--population-size",
                }
                if search_type.system == "topograph":
                    mappings.update(benchmark_pooling="benchmark_pooling", novelty_weight="novelty_weight")
                    flags.update(benchmark_pooling="--benchmark-pooling", novelty_weight="--novelty-weight")
                if search_type.system == "stratograph":
                    mappings["variant"] = "variant"
                    flags["variant"] = "--variant"
                    mappings["research"] = "research"
                    flags["research"] = "--research"
                if search_type.system == "primordia":
                    for field, default in (("search_policy", "legacy_v1"), ("max_width", 48), ("max_depth", 8)):
                        mappings[field] = field
                        flags[field] = "--" + field.replace("_", "-")
                        if field not in stored:
                            stored[field] = default
                mappings.update({name: name for name in run_options})
                flags.update({name: "--" + name.replace("_", "-") for name in run_options})
                for name, settings in run_options.items():
                    if "default" in settings:
                        stored.setdefault(name, settings["default"])
                for target, source in mappings.items():
                    explicit = flags[target][2:].replace("-", "_") in supplied_config_fields or any(
                        argument == flags[target] or argument.startswith(flags[target] + "=") for argument in argv
                    )
                    current = str(Path(config[target]).absolute()) if target == "cache_root" else config[target]
                    saved_value = stored.get("research") if source == "research" else stored[source]
                    if explicit and current != saved_value:
                        raise ValueError(f"explicit resume option {flags[target]} differs from saved run")
                    config[target] = saved_value
            print(
                run_engine(
                    search_type,
                    **config,
                    resume=options.resume,
                    stop_after=options.stop_after,
                    crash_at=options.crash_at,
                    crash_step=options.crash_step,
                )
            )
        elif options.verb == "benchmarks":
            print("\n".join(load_parity_pack(options.pack).benchmarks))
        elif options.verb == "warm-cache":
            if dataset_loader is None:
                from .datasets import load_dataset
                dataset_loader = load_dataset
            for benchmark in load_parity_pack(options.pack).benchmarks:
                print(
                    dataset_loader(benchmark, seed=options.seed, cache_root=options.cache).provenance["cache_directory"]
                )
        else:
            from .run_store import open_run_store, open_run_reader
            from .run_workspace import open_run_workspace, write_report

            workspace = open_run_workspace(options.run_directory)
            if inspect_extra is not None and options.verb in {"inspect", "report"}:
                with boundary_ownership(workspace.root):
                    inspect_extra(workspace.root)
            if options.verb == "replay":
                print(json.dumps(replay_export(workspace.root / "symbiosis", search_type, genome_type), sort_keys=True))
            elif options.verb == "report":
                with boundary_ownership(workspace.root), open_run_store(workspace.root, workspace.run_id) as store:
                    write_report(workspace, store)
                print(workspace.report_path)
            elif options.verb == "symbiosis-export":
                exported = workspace.root / "symbiosis"
                read_export(exported)
                print(exported)
            else:
                with open_run_reader(workspace.root, workspace.run_id) as reader:
                    print(
                        json.dumps(
                            {
                                "run_id": workspace.run_id,
                                "rows": reader.verify_evaluation_chain(),
                                "metadata": dict(reader.metadata()),
                            },
                            sort_keys=True,
                        )
                    )
    except (ValueError, OSError) as error:
        parser.exit(1, f"{search_type.system}: {error}\n")
