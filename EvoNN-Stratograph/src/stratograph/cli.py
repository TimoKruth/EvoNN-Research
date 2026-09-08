"""Stratograph command and worker boundary."""
from evonn_shared.engine_cli import main as engine_main
from .search import Search
from .config import RunConfig
from .run import run_engine, evaluation_worker, replay_export
from .genome import HierarchicalGenome

def main():
    engine_main(Search, HierarchicalGenome, run_engine, evaluation_worker, RunConfig, replay_export)

if __name__ == "__main__":
    main()
