# Faster canonical JSON checkpoint replay

Checkpoint recovery uses an in-memory encoding tree scoped to a single load.
Unchanged private objects reuse exactly the bytes produced by the standard
JSON encoder. Changed containers are rebuilt; scalar arrays remain in the C
encoder. Parent buffers above 256 KiB are assembled on demand to limit duplicate
storage. Evicted objects are released immediately, without relying on cyclic GC.

Every record is still read and verified, every logical-state digest is still
computed, and the final returned JSON remains byte compatible. Signed zero,
integer/float/bool distinctions, Unicode escaping and nonfinite rejection retain
the standard encoder's behavior. The checkpoint format, publication/commit
boundaries and training algorithms are unchanged. No cache persists between
loads, so historical checkpoint bytes remain authoritative.

The implementation relies on a narrow ownership contract: replay decodes its own
states and delta application replaces containers without mutating predecessors.
The encoder must not be reused with caller-owned mutable objects.

## Measurement protocol

The existing Topograph core@256 seed-1001 checkpoint contains 256 completed
attempts. Six fresh processes read the same unchanged chain in order
before/after, after/before, before/after. Each process hashes all input files
before and after loading; initial hashing warms filesystem caches in both
versions and is outside the timed interval. No model fits or test evaluation
occur in the benchmark. The complete sequence of logical-state digests and
final payload hash must agree, not just the final task scores.

Timings use perf_counter without cProfile; both versions record per-state digests.
These are repeated timings of one artifact on one host, not independent training
replicates or a claim about end-to-end training speed. Peak RSS covers the whole
fresh process and includes verification outside the timed interval.

## Results

| Measurement | Original reader | Optimized reader |
| --- | ---: | ---: |
| Median replay time (three reads each) | 57.788 s | 23.774 s |
| Replay time range | 57.709–57.831 s | 23.736–24.059 s |
| Peak process RSS range (decimal GB) | 1.219–1.327 | 1.255–1.268 |
| JSON iterencode self time (separate cProfile reads) | 46.197 s | 6.376 s |

The median replay is **2.43× faster**, saving **34.0 seconds (58.9%)**.
All 258 logical-state digest calls match in each of the six
reads. The final 7,818,889-byte payload has SHA-256
`6e7324aacbac45d2afe207c8f0d11b0303cd686dfe411301afa42beb0552da73`.
Peak RSS ranges overlap; these measurements do not establish a memory improvement.
The cProfile totals were 61.404 s before and 41.456 s after.
Instrumentation affects the Python-heavy cached reader more; use the unprofiled
repeats for the speedup and the profiles only to locate costs.

## Verification and reproduction

The focused tests exercise exact canonical bytes through cache eviction, keyed
reordering, deletion, appends and periodic snapshots; numeric types, signed zero,
Unicode/surrogate escaping, nonfinite rejection and byte limits; deep legacy
snapshots; immediate release of evicted payloads; and intermediate logical
corruption even after recomputing every outer artifact hash. Existing publication
crash-boundary tests remain unchanged.

The benchmark script is
`EvoNN-Shared/tests/benchmark_runtime_journal.py`. Run it with each producer's
Python from that producer's working directory, using a new output file for each
read. The frozen protocol records the source revisions and benchmark script hash;
raw observations retain source hashes, timing scope and every state digest.

The larger research study and original 28/30 qualification remain unchanged.
A speedup of replay does not qualify baseline adequacy, measured-training budgets
or the entire timing/recovery protocol. Required hosted checks and integration
still gate use in a new scientific producer.
