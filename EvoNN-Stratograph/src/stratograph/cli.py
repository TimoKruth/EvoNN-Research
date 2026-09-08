"""Stratograph command and worker boundary."""

import sys
from .commands import main as research_main
from evonn_shared.engine_cli import main as engine_main
from .search import Search
from .config import RunConfig
from .run import run_engine, evaluation_worker, replay_export
from .genome import HierarchicalGenome


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in {"ablate", "ablate-matrix", "motifs"}:
        return research_main(argv)
    if argv and argv[0] in {"--help", "-h"}:
        print("Research commands: ablate / ablate-matrix; motifs analyze <run-directory>\n")
    engine_main(Search, HierarchicalGenome, run_engine, evaluation_worker, RunConfig, replay_export, argv)


if __name__ == "__main__":
    main()
