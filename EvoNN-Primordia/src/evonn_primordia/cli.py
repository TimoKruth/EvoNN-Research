"""Primordia command and worker boundary."""
from evonn_shared.engine_cli import main as engine_main
from .search import Search
from .config import RunConfig
from .run import run_engine, evaluation_worker, replay_export
from .genome import PrimitiveGenome
from .datasets import load_dataset
from .artifacts import rebuild_bank

def main():
    engine_main(Search, PrimitiveGenome, run_engine, evaluation_worker, RunConfig, replay_export, dataset_loader=load_dataset, inspect_extra=rebuild_bank)

if __name__ == "__main__":
    main()
