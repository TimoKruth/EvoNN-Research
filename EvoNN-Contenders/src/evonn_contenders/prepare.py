"""Isolated dataset preparation and optional dependency probing."""
import json
from pathlib import Path
import sys

from evonn_shared.artifact_io import create_artifact_directory, publish_artifact
from .datasets import load_dataset
from .models import OptionalContenderUnavailable, build_model


def prepare(request):
    import openml
    openml.config.set_root_cache_directory(str(create_artifact_directory(Path(request["cache_root"]) / "openml")))
    dataset = load_dataset(request["benchmark"], seed=request["seed"], cache_root=Path(request["cache_root"]), root=Path(request["shared_root"]))
    available, outcomes = [], {}
    for name, config in request["optional"].items():
        result = {"status": "skipped", "reason": "optional pressure not requested", "charged": 0, "invalid": 0}
        if request["enhanced"]:
            try:
                build_model(config["model"], task=dataset.definition.task_kind.value, seed=request["seed"],
                            input_shape=dataset.definition.input_shape, train_rows=len(dataset.x_train),
                            output_dim=dataset.definition.output_dim, parameters=config["parameters"])
                available.append(name)
                result["reason"] = "optional contender not reached within budget"
            except OptionalContenderUnavailable as error:
                result["reason"] = str(error)
            except (ValueError, TypeError, OverflowError) as error:
                result = {"status": "failed", "reason": f"invalid optional configuration: {error}", "charged": 0, "invalid": 1}
        outcomes[name] = result
    return {"status": "ok", "provenance": dataset.provenance, "train_rows": len(dataset.x_train),
            "available_optional": available, "optional_results": outcomes}


def main():
    request_path, output_path = map(Path, sys.argv[1:])
    try:
        result = prepare(json.loads(request_path.read_text()))
    except Exception as error:
        result = {"status": "failed", "reason": f"{type(error).__name__}: {error}"}
    publish_artifact(output_path, (json.dumps(result, sort_keys=True, allow_nan=False) + "\n").encode())


if __name__ == "__main__":
    main()
