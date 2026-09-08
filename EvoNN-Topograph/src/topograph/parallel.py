"""Memory-bounded process-pool supervision with deterministic result ordering.

The fair lane deliberately uses one training worker. The evaluator also accepts
multiple independent jobs; inheritance and scheduler mutation stay in the caller.
Each pool worker supervises a hard-time-limited isolated fit process.
"""

from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import os
import math
import signal
from evonn_shared.runtime_io import _process


def capacity(*, data_bytes, snapshot_bytes, cpu_budget, memory_bytes, job_count):
    if any(type(v) is not int or v < 1 for v in (data_bytes, snapshot_bytes, cpu_budget, memory_bytes, job_count)):
        raise ValueError("positive measured sizes and resource limits required")
    per_worker = 384 * 1024**2 + 4 * data_bytes + 8 * snapshot_bytes
    workers = min(cpu_budget, job_count, int(memory_bytes * 0.5 // per_worker))
    if workers < 1:
        raise ValueError("memory budget cannot safely accommodate one training worker")
    return workers


def _deadline_expired(_signal, _frame):
    # Raising unwinds subprocess.run, which kills and waits for its owned child.
    raise TimeoutError("evaluation supervisor deadline exceeded")


def _worker_deadline(seconds):
    signal.signal(signal.SIGALRM, _deadline_expired)
    signal.alarm(max(1, math.ceil(seconds)))


def _evaluate(job):
    return _process("topograph", "_worker", job["request"], job["directory"], job["timeout"])


class Evaluator:
    def __init__(self, *, data_bytes, snapshot_bytes, cpu_budget=1, memory_bytes=None, job_count=1):
        if memory_bytes is None:
            memory_bytes = int(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"))
        self.worker_count = capacity(
            data_bytes=data_bytes,
            snapshot_bytes=snapshot_bytes,
            cpu_budget=cpu_budget,
            memory_bytes=memory_bytes,
            job_count=job_count,
        )

    def evaluate_many(self, jobs):
        if not jobs:
            return []
        if len(jobs) == 1:
            # _process still owns a fresh isolated fit with a hard deadline.
            return [_evaluate(jobs[0])]
        with ProcessPoolExecutor(
            max_workers=self.worker_count,
            mp_context=multiprocessing.get_context("spawn"),
            max_tasks_per_child=1,
            initializer=_worker_deadline,
            initargs=(max(job["timeout"] for job in jobs) + 15,),
        ) as pool:
            futures = [pool.submit(_evaluate, job) for job in jobs]
            # Submission order, never completion order, determines selection/ledger order.
            return [future.result() for future in futures]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        # Every fit has a subprocess deadline, so shutdown never waits for unbounded training.
        return False
