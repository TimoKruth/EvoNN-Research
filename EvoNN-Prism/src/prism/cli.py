"""Prism command boundary."""

import argparse
import json
from pathlib import Path
import sys

from evonn_shared.engine_cli import main as engine_main
from .search import Search
from .config import RunConfig
from .run import run_engine, evaluation_worker, replay_export
from .genome import ModelGenome
from .research import VARIANTS, summarize_attempts


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in {"research-report", "finalist-config"}:
        from evonn_shared.export_reader import read_export, read_document
        from evonn_shared.engine_evidence import artifact_json, validate_engine_bundle
        parser = argparse.ArgumentParser(prog="evonn-prism " + argv[0])
        parser.add_argument("export", type=Path)
        options = parser.parse_args(argv[1:])
        root = options.export / "symbiosis" if (options.export / "symbiosis").is_dir() else options.export
        bundle = read_export(root)
        if bundle.manifest.system.value != "prism":
            raise ValueError("research report requires a Prism export")
        validate_engine_bundle(bundle)
        attempts = artifact_json(bundle, "attempts.json")["attempts"]
        if argv[0] == "finalist-config":
            import hashlib
            from evonn_shared.canonical import canonical_sha256
            if bundle.manifest.status.value != "completed" or bundle.manifest.accounting.partial_run:
                raise ValueError("finalist configuration requires a complete successful export")
            genomes = {winner.benchmark_id: ModelGenome.model_validate(
                max((a for a in attempts if a["benchmark_id"] == winner.benchmark_id and a["status"] == "ok"),
                    key=lambda a: a["score"])["genome"]).model_dump(mode="json") for winner in bundle.summary.best_per_benchmark}
            config = artifact_json(bundle, bundle.manifest.config_snapshot.path)
            proposal = RunConfig(pack=bundle.manifest.pack_id, seed=bundle.manifest.seed,
                                 budget=config["total"], epochs=config["epochs"], variant="training",
                                 backend=config["backend"], target_device=config["device"],
                                 timeout=config["timeout"], fit_timeout=config["fit_timeout"],
                                 fixed_genomes=genomes, prior_discovery={"accounting": "reported_prior",
                                     "source_run_id": bundle.manifest.run_id,
                                     "source_manifest_sha256": hashlib.sha256(read_document(root, "manifest.json")).hexdigest(),
                                     "source_fits": bundle.manifest.accounting.evaluation_count,
                                     "fixed_genomes_sha256": canonical_sha256(genomes, schema_version="prism.fixed-genomes/v1", digest_field=None)})
            print(proposal.model_dump_json(indent=2))
            return
        print(json.dumps({"scope": "descriptive; no superiority or generalization claim",
                          "run_id": bundle.manifest.run_id, "benchmarks": summarize_attempts(attempts)}, indent=2))
        return
    engine_main(Search, ModelGenome, run_engine, evaluation_worker, RunConfig, replay_export, argv,
                run_options={"variant": {"choices": VARIANTS, "default": "open"},
                             "inheritance_policy": {"choices": ["enabled", "disabled"], "default": "enabled"},
                             "optimizer_policy": {"choices": ["restart", "continue"], "default": "restart"},
                             "optimizer_backend": {"choices": ["numpy", "native"], "default": "numpy"},
                             "fixed_genomes": {"type": json.loads, "default": None},
                             "prior_discovery": {"type": json.loads, "default": None}})


if __name__ == "__main__":
    main()
