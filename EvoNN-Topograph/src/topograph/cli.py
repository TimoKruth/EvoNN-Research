"""Topograph command boundary."""

from evonn_shared.engine_cli import main as engine_main
from .search import Search
from .config import RunConfig
from .run import run_engine, evaluation_worker, replay_export
from .genome import Genome
from .research import VARIANTS


def main(argv=None):
    engine_main(Search, Genome, run_engine, evaluation_worker, RunConfig, replay_export, argv=argv,
                run_options={"variant": {"choices": VARIANTS, "default": "legacy",
                                         "help": "versioned experimental policy; legacy preserves historical search"}})


if __name__ == "__main__":
    main()
