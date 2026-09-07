"""Editable baseline pools and official pack-based lane configurations."""
from pathlib import Path
import hashlib
import re

import yaml

from evonn_shared.catalog import BenchmarkSpec


DEFAULT_POOLS = Path(__file__).with_name("pools.yaml")
OFFICIAL_LANES = Path(__file__).with_name("official_lanes.yaml")


def load_pools(path: Path | None = None) -> tuple[dict, str]:
    payload = (path if path is not None else DEFAULT_POOLS).read_bytes()
    if len(payload) > 256 * 1024:
        raise ValueError("pool configuration exceeds limit")
    try:
        config = yaml.safe_load(payload)
    except yaml.YAMLError as error:
        raise ValueError(f"invalid pool YAML: {error}") from error
    if not isinstance(config, dict) or set(config) != {"schema_version", "models", "pools", "optional"} or config["schema_version"] != "1.0.0":
        raise ValueError("invalid pool configuration schema")
    if not all(isinstance(config[key], dict) for key in ("models", "pools", "optional")):
        raise ValueError("pool configuration requires mappings")
    for name, model in config["models"].items():
        if not isinstance(name, str) or re.fullmatch(r"[a-z][a-z0-9_]*", name) is None:
            raise ValueError("invalid contender ID")
        if not isinstance(model, dict) or not {"model", "parameters"} <= set(model) <= {"model", "parameters", "extra"}:
            raise ValueError("invalid model configuration")
        if not isinstance(model["model"], str) or not isinstance(model["parameters"], dict):
            raise ValueError("model name and parameters required")
        if "extra" in model and model["extra"] not in ("boosted", "torch"):
            raise ValueError("unknown optional dependency group")
    for collection in (config["pools"], config["optional"]):
        for names in collection.values():
            if not isinstance(names, list) or not names or any(not isinstance(name, str) for name in names):
                raise ValueError("each pool must contain contender IDs")
            if len(names) != len(set(names)) or not set(names) <= set(config["models"]):
                raise ValueError("duplicate or unknown contender in pool")
    return config, hashlib.sha256(payload).hexdigest()


def benchmark_group(definition: BenchmarkSpec) -> str:
    if definition.task_kind.value == "language_modeling":
        return "text"
    if definition.input_modality.value == "image":
        return "image"
    return "synthetic" if "generated" in definition.tags else "tabular"


def resolve_pool(config: dict, definition: BenchmarkSpec) -> tuple[list[str], list[str]]:
    group = benchmark_group(definition)
    name = group + "_" + definition.task_kind.value
    if name not in config["pools"]:
        raise ValueError(f"No configured required pool for {name}")
    required = list(config["pools"][name])
    optional = list(config["optional"][group]) if group in config["optional"] else []
    if set(required) & set(optional) or any("extra" in config["models"][item] for item in required):
        raise ValueError("optional extras cannot be required floors")
    if not set(definition.required_contenders) <= set(required):
        raise ValueError("pool omits canonical required contenders")
    return required, optional


def load_official_lane(name: str) -> dict:
    lanes = yaml.safe_load(OFFICIAL_LANES.read_text())["lanes"]
    if name not in lanes:
        raise ValueError(f"Unknown official lane {name}")
    return lanes[name]
