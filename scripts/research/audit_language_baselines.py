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


def main(base, output):
    torch.set_num_threads(1)
    rows = []
    for receipt_path in sorted((base / "receipts").glob("*.json")):
        receipt = json.loads(receipt_path.read_text())
        if receipt["system"] != "contenders":
            continue
        root = Path(receipt["export"])
        assert sha(root / "manifest.json") == receipt["documents"]["manifest.json"]
        manifest = json.loads((root / "manifest.json").read_text())
        artifacts = {a["path"]: a["sha256"] for a in manifest["artifacts"]}
        assert sha(root / "attempts.json") == artifacts["attempts.json"]
        attempts = json.loads((root / "attempts.json").read_text())["attempts"]
        for name in sorted({a["benchmark_id"] for a in attempts if a["family"] == "transformer_lm_tiny"}):
            for family in ["transformer_lm_tiny", "unigram_lm", "bigram_lm", "trigram_lm"]:
                candidates = [
                    a for a in attempts if a["benchmark_id"] == name and a["family"] == family and a["status"] == "ok"
                ]
                attempt = min(candidates, key=lambda a: a["score"])
                directory = root.parent / "attempts" / (name + "_" + attempt["outcome_id"])
                model_path = directory / "model.pkl"
                assert sha(model_path) == attempt["worker_model_sha256"]
                # These are local models produced by this user's frozen runs;
                # the trusted export binds the serialized model's exact bytes.
                with model_path.open("rb") as stream:
                    model = pickle.load(stream)
                provenance_path = root / "dataset_provenance.json"
                assert sha(provenance_path) == artifacts["dataset_provenance.json"]
                data = next(d for d in json.loads(provenance_path.read_text()) if d["benchmark_id"] == name)
                arrays = {}
                for entry in data["cache_artifacts"]:
                    p = Path(data["cache_directory"]) / entry["path"]
                    assert sha(p) == entry["sha256"]
                    arrays[Path(entry["path"]).stem] = np.load(io.BytesIO(p.read_bytes()), allow_pickle=False)
                for key in ["x_train", "x_validation"]:
                    arrays[key] = arrays[key].astype(np.int64)
                validation = model.perplexity(arrays["x_validation"], arrays["y_validation"])
                assert np.isclose(validation, attempt["score"], rtol=1e-6, atol=1e-7)
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
                    model=str(model_path),
                    model_sha256=sha(model_path),
                    receipt=str(receipt_path),
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
