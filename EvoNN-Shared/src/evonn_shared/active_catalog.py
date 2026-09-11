"""Current additive catalog view over the immutable Phase-0 identities."""
from pathlib import Path
import os
from . import catalog
from .benchmarks import resolve_data_root


def _directories(root):
    configured=os.environ.get("EVONN_SHARED_BENCHMARKS_DIR")
    if configured == "":
        raise ValueError("EVONN_SHARED_BENCHMARKS_DIR must not be empty")
    base = Path(root) if root is not None else Path(configured) if configured is not None else resolve_data_root()
    extensions = [base / 'extensions' / name for name in ('phase4', 'breadth_v1')]
    return base, tuple(e / 'catalog' for e in extensions if (e / 'catalog').exists()), tuple(e / 'packs' for e in extensions if (e / 'packs').exists())


def get_benchmark(benchmark_id, *, shared_root=None):
    root, definitions, _ = _directories(shared_root)
    return catalog.get_benchmark(benchmark_id, shared_root=root, fallback_catalog_dirs=definitions)


def list_benchmarks(*, shared_root=None):
    root, definitions, _ = _directories(shared_root)
    return catalog.list_benchmarks(shared_root=root, fallback_catalog_dirs=definitions)


def load_parity_pack(pack_name, *, shared_root=None):
    root, definitions, packs = _directories(shared_root)
    return catalog.load_parity_pack(pack_name, shared_root=root, fallback_catalog_dirs=definitions, fallback_pack_dirs=packs)
