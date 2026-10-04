"""Primordia command and worker boundary."""
from evonn_shared.engine_cli import main as engine_main
from .search import Search
from .config import RunConfig
from .run import run_engine, evaluation_worker, replay_export
from .genome import PrimitiveGenome
from .datasets import load_dataset
from .artifacts import rebuild_bank
from evonn_shared.primordia_policy import PrimordiaResearchPolicy, RESEARCH_DEFAULTS
from typing import get_args
import sys
from .presets import cli_configuration
from evonn_shared.primordia_presets import PRESETS

def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in {"run", "evolve"} and any(a in {"--help", "-h"} for a in argv):
        print("--preset {" + ",".join(PRESETS) + "}: standard is full_steady; portfolio variants are experimental. "
              "Bare new runs use standard; explicit configs/policies and resumes retain their settings.")
    argv, defaults = cli_configuration(argv)
    options = {key: dict(choices=list(get_args(PrimordiaResearchPolicy.model_fields[key].annotation)), default=value)
               for key, value in RESEARCH_DEFAULTS.items()}
    engine_main(Search, PrimitiveGenome, run_engine, evaluation_worker, RunConfig, replay_export,
                argv=argv, dataset_loader=load_dataset, inspect_extra=rebuild_bank, run_options=options,
                run_defaults=defaults)

if __name__ == "__main__":
    main()
