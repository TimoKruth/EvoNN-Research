"""Durable invocation clocks prevent time-budget renewal after process death.

A clean pause excludes downtime. An unclosed invocation conservatively charges
wall time through recovery, including downtime; a backward clock fails closed.
This ledger is storage infrastructure, independent of engine search state.
"""
import json
import math
import re
import time

from .artifact_io import create_artifact_directory, publish_artifact
from .export_reader import read_document
from .runtime_journal import digest, encode


def number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def read(directory, name):
    value = json.loads(read_document(directory, name))
    if type(value) is not dict or "sha256" not in value:
        raise ValueError("invalid invocation clock record")
    if digest({k: v for k, v in value.items() if k != "sha256"}) != value["sha256"]:
        raise ValueError("invocation clock checksum mismatch")
    return value


def write(path, value):
    publish_artifact(path, encode({**value, "sha256": digest(value)}))


class InvocationClock:
    def __init__(self, root, accounted, *, setup_seconds=0.0):
        if not number(accounted) or not number(setup_seconds):
            raise ValueError("invalid accounted invocation time")
        self.directory = create_artifact_directory(root / "invocation_clock")
        names = {p.name for p in self.directory.iterdir() if not re.fullmatch(r"\.publish-[0-9a-f]{32}", p.name)}
        starts = sorted(name for name in names if name.endswith("_start.json"))
        expected = {f"{i:06d}_start.json" for i in range(1, len(starts) + 1)}
        if set(starts) != expected or not names <= expected | {name.replace("_start", "_end") for name in expected}:
            raise ValueError("invocation clock sequence mismatch")
        previous, elapsed, last_wall = None, 0.0, 0.0
        recovered = False
        for name in starts:
            start = read(self.directory, name)
            if (set(start) != {"base", "wall", "previous", "sha256"} or start["previous"] != previous
                    or not number(start["base"]) or not number(start["wall"]) or start["base"] < elapsed
                    or start["wall"] < last_wall):
                raise ValueError("invalid invocation clock start")
            end_name = name.replace("_start", "_end")
            if end_name in names:
                end = read(self.directory, end_name)
                if (set(end) != {"start", "elapsed", "wall", "sha256"} or end["start"] != start["sha256"]
                        or not number(end["elapsed"]) or end["elapsed"] < start["base"]
                        or not number(end["wall"]) or end["wall"] < start["wall"]):
                    raise ValueError("invalid invocation clock completion")
                previous, elapsed, last_wall = end["sha256"], end["elapsed"], end["wall"]
            else:
                # Only the last invocation may remain unclosed. Recovery seals it
                # before any subsequent invocation can dispatch training.
                if name != starts[-1]:
                    raise ValueError("unclosed historical invocation")
                now = time.time()
                if now < start["wall"]:
                    raise ValueError("wall clock moved backwards during interrupted invocation")
                elapsed = start["base"] + now - start["wall"]
                recovered = True
                recovery = {"start": start["sha256"], "elapsed": elapsed, "wall": now}
                write(self.directory / end_name, recovery)
                previous, last_wall = digest(recovery), now
        self.base = max(float(accounted), elapsed) + (0.0 if recovered else setup_seconds)
        self.started = time.monotonic()
        wall = time.time()
        if wall < last_wall:
            raise ValueError("wall clock moved backwards between invocations")
        self.wall = wall
        self.sequence = len(starts) + 1
        start = {"base": self.base, "wall": wall, "previous": previous}
        self.start_hash = digest(start)
        write(self.directory / f"{self.sequence:06d}_start.json", start)

    def elapsed(self):
        return self.base + time.monotonic() - self.started

    def finish(self):
        wall = time.time()
        if wall < self.wall:
            raise ValueError("wall clock moved backwards during invocation")
        write(self.directory / f"{self.sequence:06d}_end.json",
              {"start": self.start_hash, "elapsed": self.elapsed(), "wall": wall})
