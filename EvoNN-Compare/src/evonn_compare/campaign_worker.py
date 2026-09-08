"""CLI-only preparation and dispatch handshake, with inherited campaign lease."""
import json
import os
from pathlib import Path
import sys

from evonn_shared.artifact_io import publish_artifact
from evonn_shared.datasets import load_dataset
from evonn_shared.export_reader import read_document
from .workspace import encoded


def main():
    if sys.argv[1] == "prepare":
        name, seed, cache, output = sys.argv[2:]
        data = load_dataset(name, seed=int(seed), cache_root=Path(cache))
        publish_artifact(Path(output), encoded(data.provenance))
    elif sys.argv[1] == "dispatch":
        path, descriptor = Path(sys.argv[2]), int(sys.argv[3])
        event = json.loads(read_document(path.parent, path.name))
        os.fstat(descriptor)
        os.set_inheritable(descriptor, True)
        if os.getpgrp() != os.getpid():
            raise ValueError("dispatch requires its own process group")
        publish_artifact(path.with_name(path.stem + ".started.json"), encoded({"dispatch": event["sha256"], "pid": os.getpid()}))
        command = event["details"]["command"]
        os.execv(command[0], command)
    else:
        raise ValueError("unknown campaign worker operation")


if __name__ == "__main__":
    main()
