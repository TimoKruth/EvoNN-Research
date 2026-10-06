"""Topograph command boundary."""

import json
import sys
from evonn_shared.engine_cli import main as engine_main
from .search import Search
from .config import RunConfig
from .run import run_engine, evaluation_worker, replay_export
from .genome import Genome
from .research import VARIANTS
from .presets import expand_preset


def main(argv=None):
    argv = expand_preset(list(sys.argv[1:] if argv is None else argv))
    # The shared CLI uses this fallback for old saved configs with no variant.
    # New runs resolve an omitted policy to mixer; resumes keep historical meaning.
    resuming = any(arg.split("=", 1)[0] == "--resume" for arg in argv)
    engine_main(Search, Genome, run_engine, evaluation_worker, RunConfig, replay_export, argv=argv,
                run_options={"variant": {"choices": VARIANTS, "default": "legacy" if resuming else None,
                                         "help": "default: mixer preset; use --preset legacy for historical search"},
                             "research_options": {"type": json.loads, "default": None,
                                                  "help": "JSON switches for the experimental next variant"}})


if __name__ == "__main__":
    main()
