"""Audit retained, checksum-bound baseline models without fitting or test access."""

import datetime
import hashlib
import io
import json
from pathlib import Path
import pickle
import sys

import numpy as np
import torch


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def object_fields(value, keys, label):
    require(isinstance(value, dict) and set(keys) <= set(value), f"missing or malformed {label}")
    return value


def main(base, output):
    base = base.resolve()
    torch.set_num_threads(1)
    rows = []
    for receipt_path in sorted((base / "receipts").glob("*.json")):
        receipt = object_fields(json.loads(receipt_path.read_text()),
                                ["system", "export", "documents", "stage", "budget", "seed"], "receipt")
        if receipt["system"] != "contenders":
            continue
        object_fields(receipt["documents"], ["manifest.json"], "receipt document hashes")
        root = Path(receipt["export"])
        require(sha(root / "manifest.json") == receipt["documents"]["manifest.json"], "audit input hash or replay mismatch")
        manifest = object_fields(json.loads((root / "manifest.json").read_text()), ["artifacts"], "manifest")
        require(isinstance(manifest["artifacts"], list), "malformed artifact list")
        for artifact in manifest["artifacts"]:
            object_fields(artifact, ["path", "sha256"], "artifact reference")
        artifacts = {a["path"]: a["sha256"] for a in manifest["artifacts"]}
        require({"attempts.json", "dataset_provenance.json"} <= set(artifacts), "missing audit artifacts")
        require(sha(root / "attempts.json") == artifacts["attempts.json"], "audit input hash or replay mismatch")
        ledger = object_fields(json.loads((root / "attempts.json").read_text()), ["attempts"], "attempt ledger")
        attempts = ledger["attempts"]
        require(isinstance(attempts, list) and bool(attempts), "missing attempt records")
        for attempt in attempts:
            object_fields(attempt, ["benchmark_id", "status"], "attempt")
            if attempt["status"] == "ok":
                object_fields(attempt, ["family", "score", "outcome_id", "worker_model_sha256", "parameters",
                                       "training_iterations_or_trees", "training_rows", "train_seconds"], "successful attempt")
        for name in sorted({a["benchmark_id"] for a in attempts if a.get("family") == "transformer_lm_tiny"}):
            for family in ["transformer_lm_tiny", "unigram_lm", "bigram_lm", "trigram_lm"]:
                candidates = [
                    a for a in attempts if a["benchmark_id"] == name and a.get("family") == family and a["status"] == "ok"
                ]
                require(bool(candidates), f"missing successful {family} attempt for {name}")
                attempt = min(candidates, key=lambda a: a["score"])
                directory = root.parent / "attempts" / (name + "_" + attempt["outcome_id"])
                model_path = directory / "model.pkl"
                require(sha(model_path) == attempt["worker_model_sha256"], "audit input hash or replay mismatch")
                # These are local models produced by this user's frozen runs;
                # the trusted export binds the serialized model's exact bytes.
                with model_path.open("rb") as stream:
                    model = pickle.load(stream)
                provenance_path = root / "dataset_provenance.json"
                require(sha(provenance_path) == artifacts["dataset_provenance.json"], "audit input hash or replay mismatch")
                provenance = json.loads(provenance_path.read_text())
                require(isinstance(provenance, list), "malformed dataset provenance")
                for item in provenance:
                    object_fields(item, ["benchmark_id", "cache_directory", "cache_artifacts"], "dataset provenance entry")
                matches = [item for item in provenance if item["benchmark_id"] == name]
                require(len(matches) == 1, f"missing or duplicate provenance for {name}")
                data = matches[0]
                require(isinstance(data["cache_artifacts"], list), "malformed cache artifact list")
                arrays = {}
                for entry in data["cache_artifacts"]:
                    object_fields(entry, ["path", "sha256"], "cache artifact")
                    p = Path(data["cache_directory"]) / entry["path"]
                    require(sha(p) == entry["sha256"], "audit input hash or replay mismatch")
                    arrays[Path(entry["path"]).stem] = np.load(io.BytesIO(p.read_bytes()), allow_pickle=False)
                require(set(arrays) == {"x_train", "y_train", "x_validation", "y_validation"}, "missing or unexpected split arrays")
                for key in ["x_train", "x_validation"]:
                    arrays[key] = arrays[key].astype(np.int64)
                validation = model.perplexity(arrays["x_validation"], arrays["y_validation"])
                require(np.isclose(validation, attempt["score"], rtol=1e-6, atol=1e-7), "audit input hash or replay mismatch")
                train = model.perplexity(arrays["x_train"], arrays["y_train"])
                row = dict(
                    stage=receipt["stage"],
                    budget=receipt["budget"],
                    seed=receipt["seed"],
                    benchmark=name,
                    family=family,
                    validation_perplexity=validation,
                    training_perplexity=train,
                    validation_to_training_ratio=validation / train,
                    parameters=attempt["parameters"],
                    iterations=attempt["training_iterations_or_trees"],
                    training_rows=attempt["training_rows"],
                    training_seconds=attempt["train_seconds"],
                    model=str(model_path.resolve().relative_to(base)),
                    model_sha256=sha(model_path),
                    receipt=str(receipt_path.resolve().relative_to(base)),
                    receipt_sha256=sha(receipt_path),
                )
                if family == "transformer_lm_tiny":
                    row.update(
                        epochs=model.epochs,
                        batch_size=model.batch_size,
                        learning_rate=model.learning_rate,
                        updates=model.epochs * ((len(arrays["x_train"]) + model.batch_size - 1) // model.batch_size),
                        parameter_count=sum(p.numel() for p in model.model.parameters()),
                    )
                else:
                    contexts = model._contexts(arrays["x_validation"])
                    row.update(
                        alpha=model.alpha,
                        seen_training_contexts=len(model.counts),
                        validation_unseen_context_fraction=sum(c not in model.counts for c in contexts) / len(contexts),
                    )
                rows.append(row)
        print(receipt["stage"], receipt["budget"], receipt["seed"], "audited", flush=True)
    result = dict(
        at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        artifact_root="qualification",
        model_fits_started=0,
        protected_test_access=False,
        selection="Existing best validation attempt per family; descriptive audit, not a new independent comparison",
        rows=rows,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main(*map(Path, sys.argv[1:3]))
