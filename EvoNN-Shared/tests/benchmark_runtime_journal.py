"""Read-only replay measurement; run with each producer's Python in its checkout.

Example: python /path/to/this/file.py CHECKPOINT_DIRECTORY NEW_OUTPUT_JSON
Each invocation is a fresh process. Hashing inputs is outside the measured load.
Per-state digest capture is identical in scope for old and optimized readers.
"""

import hashlib
import json
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time

from evonn_shared import runtime_journal as journal


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(directory, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(output)
    inputs = {p.name: sha(p) for p in directory.iterdir() if p.is_file()}
    trace = []
    optimized = hasattr(journal, "ReplayEncoder")
    if optimized:
        original = journal.ReplayEncoder.digest

        def traced(self, state):
            result = original(self, state)
            trace.append(result)
            return result

        journal.ReplayEncoder.digest = traced
    else:
        original = journal.digest

        def traced(state):
            result = original(state)
            trace.append(result)
            return result

        journal.digest = traced
    start = time.perf_counter()
    cpu = time.process_time()
    record, payload = journal.load_runtime_checkpoint(directory)
    cpu = time.process_time() - cpu
    wall = time.perf_counter() - start
    after = {p.name: sha(p) for p in directory.iterdir() if p.is_file()}
    if inputs != after:
        raise ValueError("checkpoint inputs changed during measurement")
    sources = [Path(journal.__file__)]
    if optimized:
        sources.append(sources[0].with_name("_journal_encoding.py"))
    result = dict(
        optimized=optimized,
        wall_seconds=wall,
        cpu_seconds=cpu,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024),
        checkpoint_directory_id=hashlib.sha256(str(directory).encode()).hexdigest(),
        checkpoint_id=record.checkpoint_id,
        logical_sha256=hashlib.sha256(payload).hexdigest(),
        logical_bytes=len(payload),
        state_digests=trace,
        input_files_sha256=hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest(),
        inputs_unchanged=inputs == after,
        fits_started=0,
        python=platform.python_version(),
        platform=platform.platform(),
        source_revision=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        source_dirty=bool(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], text=True)),
        source_files={str(p.relative_to(Path(__file__).resolve().parents[2])): sha(p) for p in sources},
        benchmark_script_sha256=sha(Path(__file__)),
        timing_scope="Unprofiled checkpoint load with per-state digest capture; input hashing excluded",
    )
    with output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps({k: result[k] for k in ["optimized", "wall_seconds", "peak_rss_bytes", "logical_sha256"]}),
        flush=True,
    )


if __name__ == "__main__":
    main(*map(Path, sys.argv[1:3]))
