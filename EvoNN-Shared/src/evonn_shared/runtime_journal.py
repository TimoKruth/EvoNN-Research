"""Incremental runtime persistence over the existing atomic checkpoint contract.

One immutable record per attempt; compact state snapshots every 16 attempts.
Attempt history is reconstructed once on recovery, never copied into each record.
The generic checkpoint manifest remains the sole commit point.
"""
from copy import deepcopy
import hashlib
import json
import math

from .artifact_io import publish_artifact, read_verified_artifact
from .checkpoints import CheckpointPublication, CheckpointRecord, read_checkpoint_manifest
from .export_reader import read_document
from .telemetry import ArtifactReference

FORMAT = "evonn.runtime-journal/v1"
INTERVAL = 16
LIMIT = 128 * 1024**2
MAX_RECORDS = 100_000


def encode(value):
    payload = (json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")) + "\n").encode()
    if len(payload) > LIMIT:
        raise ValueError("journal record exceeds 128 MiB limit")
    return payload


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def same(left, right):
    """Equality of canonical JSON, preserving bool/int/float and signed zero."""
    if type(left) in (list, tuple) and type(right) in (list, tuple):
        return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(same(value, right[key]) for key, value in left.items())
    if type(left) is float and left == right == 0:
        return math.copysign(1, left) == math.copysign(1, right)
    return left == right


def delta(before, after):
    """JSON changes, including append-only sequences, with explicit operations."""
    if type(before) is dict and type(after) is dict:
        return {"dict": {key: delta(before[key], value) if key in before else {"replace": value}
                         for key, value in after.items() if key not in before or not same(value, before[key])},
                "remove": sorted(set(before) - set(after))}
    if type(before) in (list, tuple) and type(after) in (list, tuple) and same(after[:len(before)], before):
        return {"append": after[len(before):]}
    if keyed(before) and keyed(after):
        return {"keyed": delta(dict(before), dict(after)), "order": [item[0] for item in after]}
    return {"replace": after}


def keyed(value):
    return (type(value) is list and bool(value)
            and all(type(item) in (list, tuple) and len(item) == 2 and type(item[0]) is str for item in value)
            and len({item[0] for item in value}) == len(value))


def apply_delta(before, change, depth=0):
    if depth > 100 or type(change) is not dict:
        raise ValueError("invalid journal delta")
    if set(change) == {"replace"}:
        return deepcopy(change["replace"])
    if set(change) == {"append"} and type(before) in (list, tuple) and type(change["append"]) in (list, tuple):
        return list(before) + deepcopy(list(change["append"]))
    if set(change) == {"keyed", "order"} and keyed(before):
        order = change["order"]
        if type(order) is not list or any(type(key) is not str for key in order) or len(set(order)) != len(order):
            raise ValueError("invalid keyed journal order")
        values = apply_delta(dict(before), change["keyed"], depth + 1)
        if type(values) is not dict or set(order) != set(values):
            raise ValueError("keyed journal entries and order differ")
        return [[key, values[key]] for key in order]
    if (set(change) != {"dict", "remove"} or type(before) is not dict
            or type(change["dict"]) is not dict or type(change["remove"]) is not list
            or any(type(key) is not str for key in change["remove"])
            or len(set(change["remove"])) != len(change["remove"])
            or not set(change["remove"]) <= set(before)
            or set(change["remove"]) & set(change["dict"])):
        raise ValueError("invalid journal dictionary delta")
    result = dict(before)
    for key in change["remove"]:
        del result[key]
    for key, value in change["dict"].items():
        if key not in before and (type(value) is not dict or set(value) != {"replace"}):
            raise ValueError("new journal key requires a replacement")
        result[key] = apply_delta(before[key] if key in before else None, value, depth + 1)
    return result


def compact(state):
    if (type(state) is not dict or not {"completed", "attempts"} <= set(state) or type(state["completed"]) is not int
            or not 0 <= state["completed"] <= MAX_RECORDS
            or type(state["attempts"]) is not list or len(state["attempts"]) != state["completed"]):
        raise ValueError("journal attempt count differs from completed progress")
    return {key: value for key, value in state.items() if key != "attempts"}


def transition(before, after):
    old, new = compact(before), compact(after)
    if after["completed"] != before["completed"] + 1 or not same(after["attempts"][:-1], before["attempts"]):
        raise ValueError("journal transition must append exactly one attempt")
    if type(after["attempts"][-1]) is not dict:
        raise ValueError("journal attempt must be an object")
    return {"delta": delta(old, new), "attempt": after["attempts"][-1]}


def restore(before, change):
    if type(change) is not dict or set(change) != {"delta", "attempt"} or type(change["attempt"]) is not dict:
        raise ValueError("invalid journal transition")
    result = apply_delta(compact(before), change["delta"])
    if type(result) is not dict or "attempts" in result:
        raise ValueError("journal compact state must remain a dictionary without attempts")
    result["attempts"] = before["attempts"] + [change["attempt"]]
    compact(result)
    if result["completed"] != before["completed"] + 1:
        raise ValueError("nonconsecutive journal progress")
    return result


def publish_transaction(path, before, after):
    publish_artifact(path, encode({"format": FORMAT, "before_sha256": digest(before), "after_sha256": digest(after), **transition(before, after)}))


def load_transaction(path, before):
    value = json.loads(read_document(path.parent, path.name, limit=LIMIT))
    if type(value) is not dict:
        raise ValueError("invalid transaction object")
    if "format" not in value:  # Historical full-state transaction.
        if set(value) != {"before_sha256", "state"} or value["before_sha256"] != digest(before):
            raise ValueError("invalid legacy transaction")
        transition(before, value["state"])
        return value
    if set(value) != {"format", "before_sha256", "after_sha256", "delta", "attempt"} or value["format"] != FORMAT:
        raise ValueError("unsupported transaction journal")
    if value["before_sha256"] != digest(before):
        raise ValueError("pending transaction does not extend checkpoint")
    state = restore(before, {"delta": value["delta"], "attempt": value["attempt"]})
    if digest(state) != value["after_sha256"]:
        raise ValueError("transaction logical state hash mismatch")
    return {"before_sha256": value["before_sha256"], "state": state}


def load_bounded_checkpoint(directory):
    manifest = read_checkpoint_manifest(directory)
    if manifest is None:
        raise ValueError("no committed runtime checkpoint")
    record = manifest.latest
    payload = read_verified_artifact(directory, ArtifactReference(path=record.payload_path, sha256=record.sha256),
                                     size_bytes=record.size_bytes, max_bytes=LIMIT)
    return record, payload


class JournalPublication(CheckpointPublication):
    """Same stage/payload/manifest boundaries, with an incremental payload."""
    def __init__(self, directory, run_id, checkpoint_id, state, *, previous=None):
        current = compact(state)
        manifest = read_checkpoint_manifest(directory)
        if previous is None:
            if manifest is not None or state["completed"] != 0:
                raise ValueError("initial journal requires empty checkpoint directory and zero attempts")
            record = {"format": FORMAT, "previous": None, "snapshot": current, "change": None,
                      "run_id": run_id, "before": None, "after": digest(state)}
        else:
            if manifest is None or manifest.latest.checkpoint_id != f"step_{previous['completed']}":
                raise ValueError("journal predecessor is not the committed state")
            _, committed_payload = load_bounded_checkpoint(directory)
            committed = json.loads(committed_payload)
            expected = committed["after"] if "format" in committed else digest(committed)
            if digest(previous) != expected:
                raise ValueError("journal predecessor differs from committed logical state")
            change = transition(previous, state)
            snapshot = current if state["completed"] % INTERVAL == 0 else None
            # Snapshots replace compact deltas, but never include the attempt prefix.
            if snapshot is not None:
                change = {"delta": None, "attempt": change["attempt"]}
            record = {"format": FORMAT, "previous": manifest.latest.model_dump(mode="json"),
                      "snapshot": snapshot, "change": change, "run_id": run_id,
                      "before": digest(previous), "after": digest(state)}
        if checkpoint_id != f"step_{state['completed']}":
            raise ValueError("journal checkpoint ID differs from logical progress")
        super().__init__(directory, run_id, checkpoint_id, encode(record))


def publish_initial(directory, run_id, checkpoint_id, state):
    publication = JournalPublication(directory, run_id, checkpoint_id, state)
    publication.stage()
    publication.commit_payload()
    return publication.commit_manifest()


def load_runtime_checkpoint(directory):
    """Validate the entire committed chain and decode the original logical state."""
    manifest = read_checkpoint_manifest(directory)
    if manifest is not None and manifest.latest.size_bytes > LIMIT:
        raise ValueError("journal record exceeds read limit")
    latest, payload = load_bounded_checkpoint(directory)
    current = latest
    records = []
    while True:
        value = json.loads(payload)
        if type(value) is not dict:
            raise ValueError("invalid journal object")
        if "format" not in value:
            state = value  # Explicit backwards-compatible base snapshot.
            compact(state)
            break
        if (set(value) != {"format", "previous", "snapshot", "change", "run_id", "before", "after"}
                or value["format"] != FORMAT or value["run_id"] != manifest.run_id or len(records) >= MAX_RECORDS + 1):
            raise ValueError("invalid runtime journal record")
        records.append(current)
        if value["previous"] is None:
            if current.sequence != 0 or current.previous_sha256 is not None or value["change"] is not None:
                raise ValueError("invalid initial journal record")
            if type(value["snapshot"]) is not dict or "attempts" in value["snapshot"] or value["before"] is not None:
                raise ValueError("invalid initial compact state")
            state = {**value["snapshot"], "attempts": []}
            compact(state)
            if state["completed"] != 0 or current.checkpoint_id != "step_0":
                raise ValueError("invalid initial journal progress")
            if digest(state) != value["after"]:
                raise ValueError("initial journal state hash mismatch")
            records = records[:-1]
            break
        previous = CheckpointRecord.model_validate(value["previous"])
        if current.sequence != previous.sequence + 1 or current.previous_sha256 != previous.sha256:
            raise ValueError("broken journal predecessor chain")
        payload = read_verified_artifact(directory, ArtifactReference(path=previous.payload_path, sha256=previous.sha256),
                                         size_bytes=previous.size_bytes, max_bytes=LIMIT)
        if previous.payload_path != previous.checkpoint_id + ".ckpt":
            raise ValueError("journal payload name differs from checkpoint identity")
        current = previous
    for record in reversed(records):
        payload = read_verified_artifact(directory, ArtifactReference(path=record.payload_path, sha256=record.sha256),
                                         size_bytes=record.size_bytes, max_bytes=LIMIT)
        value = json.loads(payload)
        if value["before"] != digest(state):
            raise ValueError("journal prior logical state hash mismatch")
        change = value["change"]
        if value["snapshot"] is not None:
            if (type(value["snapshot"]) is not dict or "attempts" in value["snapshot"] or type(change) is not dict or set(change) != {"delta", "attempt"} or change["delta"] is not None
                    or type(change["attempt"]) is not dict):
                raise ValueError("invalid snapshot journal transition")
            next_state = {**value["snapshot"], "attempts": state["attempts"] + [change["attempt"]]}
            compact(next_state)
            if next_state["completed"] != state["completed"] + 1 or next_state["completed"] % INTERVAL:
                raise ValueError("invalid periodic journal checkpoint")
            state = next_state
        else:
            state = restore(state, change)
            if state["completed"] % INTERVAL == 0:
                raise ValueError("missing periodic compact snapshot")
        if digest(state) != value["after"]:
            raise ValueError("journal logical state hash mismatch")
        if record.checkpoint_id != f"step_{state['completed']}":
            raise ValueError("journal checkpoint and attempt progress disagree")
    return latest, encode(state)
