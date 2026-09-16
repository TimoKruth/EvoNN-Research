"""Profile verified checkpoint loading without changing journals or training."""

import cProfile
import datetime
import hashlib
import json
from pathlib import Path
import pstats
import sys
import time

from evonn_shared.runtime_journal import load_runtime_checkpoint


def main(directory, output):
    inputs = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir() if p.is_file()}
    profile = cProfile.Profile()
    start = time.perf_counter()
    record, payload = profile.runcall(load_runtime_checkpoint, directory)
    wall = time.perf_counter() - start
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir() if p.is_file()}
    assert inputs == after
    state = json.loads(payload)
    stats = pstats.Stats(profile)
    rows = []
    for (filename, line, function), (primitive, calls, self_seconds, cumulative, callers) in stats.stats.items():
        rows.append(
            dict(
                file=filename,
                line=line,
                function=function,
                primitive_calls=primitive,
                calls=calls,
                self_seconds=self_seconds,
                cumulative_seconds=cumulative,
            )
        )
    result = dict(
        at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        directory=str(directory),
        completed=state["completed"],
        attempts=len(state["attempts"]),
        logical_sha256=hashlib.sha256(payload).hexdigest(),
        profile_wall_seconds=wall,
        checkpoint_files=len(inputs),
        checkpoint_bytes=sum(p.stat().st_size for p in directory.iterdir() if p.is_file()),
        inputs_sha256=hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest(),
        inputs_unchanged=True,
        fits_started=0,
        scope="One instrumented replay of full committed chain; inclusive profile times overlap. Not a production speed estimate.",
        top_self=sorted(rows, key=lambda r: r["self_seconds"], reverse=True)[:30],
        top_cumulative=sorted(rows, key=lambda r: r["cumulative_seconds"], reverse=True)[:30],
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    profile.dump_stats(str(output.with_suffix(".pstats")))
    print(
        json.dumps(
            {k: result[k] for k in ["completed", "profile_wall_seconds", "checkpoint_bytes", "inputs_unchanged"]}
        ),
        flush=True,
    )


if __name__ == "__main__":
    main(*map(Path, sys.argv[1:3]))
