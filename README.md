# EvoNN Research Lab

Research workspace for four independent evolutionary neural-search engines,
portable contender baselines and a file-based comparison/evidence layer.
This repository is the foundation rebuild; its predecessor is
`TimoKruth/EvoNN` (locally `../Evo Neural Nets`).

## Read these three documents

| Document | Purpose |
| --- | --- |
| **[README.md](README.md)** | What works, package boundaries, installation, verification and operating constraints. |
| **[CONSOLIDATED_PLAN.md](CONSOLIDATED_PLAN.md)** | The sole execution plan: priorities, dependencies, work packages and acceptance criteria. |
| **[PROJECT_HISTORY.md](PROJECT_HISTORY.md)** | Completed work, durable decisions, review outcomes and exact evidence references. |

Update these files in place. Historical specifications and proof records are
reference material; their role and locations are indexed in project history.
Package READMEs are short navigation links, not separate status reports or plans.

## Current capabilities

**Verified baseline: 2026-09-08.** Gate B0 and Phase 0 contract acceptance are
closed. The [acceptance receipt](governance/phase0-acceptance.json) binds the
canonical catalog authorization and successful Linux/macOS CI evidence.
Exact integrations and review decisions are recorded in project history.

| Component | Implemented | Remaining |
| --- | --- | --- |
| Shared | Canonical identities/RNG, strict budgets/telemetry/three-file exports, catalog/pack loaders, checkpoints, LM-cache validation, transactional DuckDB/workspace and verified read-only access | Producer interoperability and future contract extensions |
| Shared benchmarks | Eight frozen definitions plus two additive runtime definitions, four packs, verified tabular/image/real-text caches | Repeated Tier-B scientific qualification and optional enhanced pressure |
| Reference fixtures | Real kill/resume, failed/invalid accounting, seed/label binding, read-only diagnostics and hosted integrity reports | Broader scientific qualification and future producer interoperability |
| Contenders + Compare | Fixed CPU pools, bounded isolated fits, complete verified exports, case/budget audit, append-only trends, L0–L3 quality, append-only evidence registry, paired-seed L4 analysis and evidence dashboard | Scientific acceptance, targeted confirmation and native transfer |
| Prism + Topograph | Package-local MLX/NumPy models including real next-token LM, bounded search, inheritance, atomic resume, portable exports and Compare ingestion | Targeted confirmation, stronger baselines and native transfer evidence |
| Stratograph | Hierarchical cell search, trained-head proxy, five ablations, winner motifs, resume/replay | End-to-end hierarchy learning and scientific comparison claims |
| Primordia | Trained primitive circuits, bounded archive/cost policy, verified motif/seed bank | Native cross-engine ingestion and proven transfer gains |

The [Phase 4 receipt](governance/phase4-runtime-evidence.json) records **13 short
qualification runs / 304 real fits**: both new engines on Tier A/core@64, five
Stratograph variants and all five systems on Tier-B@16. All exports are L3;
80 trained winners replay. Tier-B contract audit passes with zero blockers.
That short qualification remains single-seed evidence. The completed comparison
below supplies repeated low/mid-budget observations; neither receipt establishes
a broad superiority or transfer claim.
Stratograph explicitly uses deterministic hierarchy features with a trained head.
[Phase 1](governance/phase1-runtime-evidence.json),
[Phase 2](governance/phase2-runtime-evidence.json) and
[Phase 3](governance/phase3-runtime-evidence.json) retain their scoped evidence.

All four engine runtimes accept at most **256 proposals** and **30 minutes** per run.
Each committed checkpoint appends one attempt and a state delta; every 16 steps
it includes a compact search-state snapshot. Weight-cache changes are keyed, so
LRU reordering does not rewrite all weights. The **128 MiB** publication guard
and **32 MiB** cache remain. Search traces and integrity hashing can still grow
with history. The [performance receipt](governance/performance-runtime-evidence.json)
qualifies native Tier-B budgets 64/128 on seed 42: 13 short runs, 848 fits,
48 replayed neural winners and zero failed fits. The 128-fit runs take 49–158
seconds on the recorded host. Limits are unchanged.

The [completed Tier-B comparison](governance/tier-b-comparison-20260909.json)
covers **30 runs / 2,880 successful fits**, budgets 64/128 and seeds 42/43/44,
in 78 minutes. Its decision-grade benchmark-admission audit passes with zero
blockers; all exports are L3. [Results and scope](PROJECT_HISTORY.md#tier-b-comparison--2026-09-09)
show Prism leading language modeling, Primordia offering the lowest runtime,
Topograph showing a regression signal and Stratograph needing a proxy diagnostic.
The explicit follow-up now gives all 24 declared contrasts L4 evidence quality.
These remain validation-set observations from three seeds, with no automatic
engine promotion or transfer proof. The original failed producer remains preserved.

The [eight-seed confirmation](governance/tier-b-confirmation-results-20260910.json)
finished on **2026-09-10**: **48 runs / 4,608 successful fits**, no failures or
repairs. The protocol file remains an immutable pre-execution snapshot; the
result receipt records current completion. All five frozen contrasts reach L4;
128 saved native winners replay.
**Prism's bounded LM advantage is confirmed** against the tiny Transformer and
required floor (mean perplexity 16.11 versus 36.96 / 33.65; Holm p=0.0391).
**Topograph's regression advantage is not confirmed** (CatBoost comparison Holm
p=0.2344; required-floor p=1.0). **Primordia's joint tabular-quality/runtime
criterion passes narrowly**: its quality interval stays above the -3% tolerance,
and paired full-pack runtime is 28.5% lower than Prism@64 (95% interval
25.9–31.6% lower). This does not establish image/LM parity or protected-test
performance. [Next actions](CONSOLIDATED_PLAN.md#immediate-next-actions) retain
the Stratograph proxy work and scoped generalization validation.

The local training guardian is now in terminal `complete` state and starts no
new work. For an active campaign it checks the dedicated supervisor every 60
seconds; interruption triggers bounded Codex repair in an isolated clone.
Verified unchanged runs resume through the campaign journal. Producer changes
or unresumable attempts require a fresh full comparison, retaining superseded
evidence. Frozen seeds, budgets, baselines, data and admission gates remain
binding; completion requires validated exports, not just process exit.

The reusable entry point is `automation/install-training-guardian.py` with
`--producer`, `--base`, `--state-root`, first `--dry-run`, then
`--install-scheduler`. Runtime snapshots, repair decisions and logs are stored in
the supplied state directory. For this campaign it is
`.artifacts/training-guardian-20260910`: inspect `status.json`, `control.json` and
`history.jsonl`; `repairs/` contains individual Codex transcripts and fixes.
Create a `PAUSE` file there to prevent new dispatches/repairs (an active bounded
run finishes). Remove it to continue. Three failed repairs for the same error,
or twelve total attempts, open a circuit breaker and issue a local notification;
credentials/physical intervention cannot be repaired automatically. After fixing
the cause, under `guardian.lock`, change `control.json` mode to `repair`, clear
`failure_counts`, set `repairs` and `next_attempt_at` to zero, and remove `PAUSE`.
Do not edit runtime control while a repair or training invocation is active.
The LaunchAgent loads at user login and needs this Mac awake, Codex authenticated
and network available. No email, remote messages or automatic GitHub changes.

Run a verified short preset and rebuild its dashboard:

```sh
uv run evonn-compare fair-matrix --workspace .artifacts/compare --preset local \
  --systems prism topograph stratograph primordia contenders
uv run evonn-compare workspace-report .artifacts/compare
```

`--preset smoke` uses 16 fits; `local` uses 64. Runs accumulate. Each system
run stays below 30 minutes; no overnight/weekend preset is admitted.

## Campaign planning and recovery

Every new comparison must run **all four engines: Prism, Topograph, Stratograph
and Primordia**, on each declared benchmark/budget/seed combination, with
Contenders as additional baselines. This also applies to focused confirmation
and generalization comparisons. Report every engine; weaknesses or execution
failures do not justify omitting one. Failed or missing engine runs make the
comparison incomplete. Historical frozen protocols remain unchanged.

Create a JSON specification, for example `.artifacts/campaign-spec.json`:

```json
{
  "pack": "tier_b_core_v2",
  "budgets": [16],
  "seeds": [42],
  "systems": ["contenders", "prism", "topograph", "stratograph", "primordia"],
  "backend": "mlx_native",
  "epochs": 12,
  "timeout": 300,
  "fit_timeout": 90
}
```

```sh
uv run --no-sync evonn-compare campaign plan \
  --workspace .artifacts/campaign --spec .artifacts/campaign-spec.json \
  --cache .artifacts/dataset-cache
uv run --no-sync evonn-compare campaign preflight .artifacts/campaign
uv run --no-sync evonn-compare campaign run .artifacts/campaign --max-runs 2
uv run --no-sync evonn-compare campaign resume .artifacts/campaign
```

Planning may download and prepare data, but performs no model fits. It freezes
matrix, code commit, benchmark/pool definitions, environment, host, data hashes
and training settings in `campaign.json`. It requires a clean source checkout;
keep that checkout and environment unchanged until the campaign is finished.
Preflight only reads and validates those inputs, probes the requested backend
and checks free space (1 GiB by default). It neither downloads nor trains.
Use a new workspace if planning is interrupted or settings change.

For an explicitly requested macOS training job launched through `launchd`, use
`ProcessType = Standard` (the default), with `KeepAlive = false`. `Background`
and `Adaptive` without an active XPC transaction throttle worker startup and
journal work substantially. Keep the computer awake with `caffeinate -i -m`
around the bounded command. Preserve the launch configuration beside the run;
changing execution priority or source requires a newly planned campaign.

`run` and `resume` share the same recovery path. Each invocation is capped at
30 minutes and pauses before a slot whose full time allowance no longer fits;
it never reduces later slots' configured budgets. Stable case/system slots,
a durable dispatch journal and a worker-inherited lock prevent overlapping
execution. Completed exports are revalidated and adopted, even if their original
completion receipt was lost. Resuming a finished campaign starts zero new runs.
Incomplete native runs resume their committed state; incomplete Contenders runs
stop for inspection because that engine has no resumable fit contract.

The four native engines also keep a durable invocation clock: clean pauses do
not charge offline time, while an unclosed invocation conservatively charges
elapsed wall time through recovery. Clock rollback and broken journals block
resume. Campaign completion reports execution status only; repeated-seed
scientific conclusions still require the registry's separate analysis gate.

## Bounded engine operation

```sh
uv run evonn-prism evolve --config EvoNN-Prism/configs/tiny_smoke.yaml
uv run evonn-topograph evolve --config EvoNN-Topograph/configs/tiny_smoke.yaml
uv run evonn-prism evolve --resume <run-directory>
uv run evonn-prism replay <run-directory>
uv run evonn-compare fair-matrix --workspace .artifacts/phase2-native \
  --preset local --systems contenders prism topograph --seeds 42 43 44 \
  --engine-backend mlx_native --engine-epochs 12 --timeout 1200 --fit-timeout 120
```

All four engines expose `evolve`/`run`, `inspect`, `report`, `replay`, `benchmarks`,
`warm-cache` and `symbiosis-export`. Configurations and resumes reject option,
source, dependency and data drift. The tiny presets perform real fits on all
eight smoke benchmarks. NumPy executes the actual architecture and produces
`portability_only` evidence; keep its cohorts separate from native MLX runs.
The native command is a bounded acceptance cohort, not a long research campaign.
Each engine invocation and individual fit have hard limits of at most 1,800 seconds.

Exports bundle checksum-bound data, trained weights, normalization buffers,
regression calibration, attempts and engine telemetry. `replay` reconstructs
held-out metrics without the producer's cache path. Packed low-bit sizes are
estimates; serialized weights and process memory are measured separately.
Topograph's default hardware budget admits one simultaneous training worker;
its runtime worker topology describes that fit worker. One additional pool
supervisor performs no training. The configuration records training, supervisor
and total evaluation process counts explicitly. Optional benchmark pooling uses
within-benchmark quality ranks; novelty weight defaults to zero. MAP-Elites,
full deployment objectives and statistical superiority remain later-phase work.
Compare keeps immutable case evidence at `contract-fair`; a separate
`benchmark-audit --decision-grade` result governs trusted floor admission. A
green audit does not rewrite the original case labels or append-only rows.

The Phase 4 runtime adds `tier_b_core_v2`: OpenML banknote authentication,
small digit images, diabetes regression and a real Shakespeare byte next-token
benchmark. The text source is pinned to an immutable [char-rnn snapshot](https://github.com/karpathy/char-rnn/blob/370cbcd448eb7daf32f21a6be560b70e0b33c4e3/data/tinyshakespeare/input.txt).
Raw text is split before context creation; the final 15% is protected and unused.
The bounded profile samples at most 1,536 training and 384 validation contexts.
The historical catalog and runtime identities remain immutable; active runtime
consumers use the additive extension through `evonn_shared.active_catalog`.
Package READMEs document [Stratograph](EvoNN-Stratograph/README.md) and
[Primordia](EvoNN-Primordia/README.md). The completed repeated comparison remains
scoped to this bounded profile; broader and native transfer claims need further evidence.

Run the verified Tier-B tiny profile across all five systems:

```sh
uv run --locked --all-packages evonn-compare fair-matrix \
  --workspace .artifacts/tier-b-tiny --preset tier_b_tiny \
  --systems contenders prism topograph stratograph primordia --seeds 42 \
  --engine-backend mlx_native --engine-epochs 12 --timeout 300 --fit-timeout 90
```

The preset selects 16 evaluations per system. Each invocation caps five minutes;
this command starts a short qualification, not the larger repeated campaign.

## Architecture and authority

The seven uv workspace packages are Shared, Contenders, Compare, Prism,
Topograph, Stratograph and Primordia. `shared-benchmarks/` is data only;
`evonn_shared.catalog` and `evonn_shared.benchmarks` implement its resolution.
Engines remain independent. Compare invokes system CLIs and consume file
exports; Shared contains infrastructure rather than an engine core.

The pinned [Lab specification](claude-spec/README.md) is normative;
[PROGRAM_CHARTER.md](PROGRAM_CHARTER.md) defines Lab/Product boundaries.
[Product interop](claudex-spec/19-research-interop.md) is retained for the consumer
boundary. The remaining Product specifications live in an exact historical
[Git snapshot](claudex-spec/README.md), outside the Lab working documentation. Real Lab
artifacts may influence Product only after Lab I1 and Product I2 pass.
Source changes follow [SPEC_UPGRADE_PROCESS](governance/SPEC_UPGRADE_PROCESS.md);
[traceability](governance/SPEC_TRACEABILITY.md) identifies the authority roles.

## Installation and local verification

Use Python 3.13 and CI-pinned uv `0.5.13`. Supported workspace platforms are
Linux and macOS; MLX installs only on Apple Silicon macOS. From the repo root:

```sh
uv sync --all-packages --group dev --locked
scripts/ci/foundation-checks.sh
scripts/ci/benchmarks-checks.sh
```

The foundation entry point checks the complete Shared package and root
contracts once, plus lock consistency, Ruff and installed package identity.
For a focused reference check:

```sh
uv run --locked --all-packages --group dev pytest -q EvoNN-Shared/tests/test_reference_runner.py
```

For repository policy and freeze verification:

```sh
scripts/ci/b0-policy-checks.sh
```

This checks authority, freeze, import/dependency and capability rules plus
integration tests. Use a full-history clone with canonical `origin`; an archive
or shallow checkout cannot verify the historical Git evidence. The standalone
freeze validator also rejects Git worktrees: it requires a real repository-root
`.git` directory. Plan/guide validation binds committed bytes, so commit documentation candidates before
running the final governance check. The B0 integration suite takes substantially
longer than focused tests; measured timings are in project history.

Each package also has an independently callable `scripts/ci/*-checks.sh`.
Run the scripts relevant to the change; both hosted jobs run the full foundation
suite and their platform-specific checks. A full `pytest` invocation additionally
runs recursive script self-tests and the complete local script matrix.

## Synthetic integrity evidence

The test-only reference runner uses real persistence and checkpoints. Generate
and validate a fresh report of eight SIGKILL/resume cases (failed and invalid
attempts at four durable boundaries):

```sh
uv run --locked --all-packages --group dev python EvoNN-Shared/tests/integrity_probe.py \
  --work-root .artifacts/reference-integrity/runs \
  --output .artifacts/reference-integrity/report.json
uv run --locked --all-packages --group dev python EvoNN-Shared/tests/integrity_probe.py \
  --validate .artifacts/reference-integrity/report.json
```

Work/output paths must be fresh; existing evidence is never overwritten.
The report compares row/checkpoint hashes, fresh/inherited accounting, selector
traces and source digests around read-only export. It records host metadata and
`synthetic_contract_preparation`. Validation proves internal consistency, not
authenticity. Hosted provenance comes from the GitHub run and tested commit.
Each hosted lane uploads only the report as `b0-linux-synthetic-integrity` or
`b0-macos-synthetic-integrity`, with missing-file failure enabled.

This evidence contributes to the accepted Phase 0 contract gate; it does not
admit executable datasets, qualify an engine or prove scientific performance. Kills before durable row commit and general engine
failure recovery are outside this proof. The diagnostic JSON is not the regular
`manifest.json` / `results.json` / `summary.json` export contract.

## Run-directory assumptions

Use application-owned local directories with working POSIX advisory locks and
atomic rename/fsync semantics. Paths must not traverse symlinks, including
macOS aliases such as `/tmp`; resolve the actual directory. Windows and network
filesystems are not qualified.

Evaluation rows and their hash/count tip commit in one transaction. Existing
records are verified before returning a writer. File/lock/DB/WAL symlinks and
mutable-storage hardlinks are rejected; artifact reads use opened descriptors.
Reports replace atomically; new evidence publication refuses overwrites.

`open_run_reader(directory, run_id)` holds a shared lock and read-only
transaction, verifies identity/schema/row chain, exposes no writer operations,
and preserves source bytes. It rejects missing lock/DB files and existing WALs;
explicit writer recovery precedes reading an interrupted store. Readers may
coexist with readers, not a writer. Corrupt evidence is never silently repaired.

DuckDB opens pathnames, so these controls do not sandbox a process with equal
filesystem privileges replacing directories concurrently. A hash chain and tip
inside one database detect inconsistent edits, not a coordinated rewrite.
Registry receipts bind source and consumer identities; current artifact validation remains required for new claims. Failed schema
creation may leave an empty database; preserve it for diagnosis. A directory
fsync failure after publication means uncertain durability even when a complete
new file is visible; do not delete published evidence as a pretend rollback.

## Benchmark and LM-cache storage

Benchmark definitions live in `shared-benchmarks/catalog/`; packs live in
`shared-benchmarks/suites/parity/`. Eight planned definitions and three packs
are accepted under freeze v3. Additive runtime definitions live in
`shared-benchmarks/extensions/phase4/`; `evonn_shared.active_catalog` resolves
both generations without rewriting frozen identities. Scientific admission is
scoped by the runtime receipts. Canonical
IDs preserve data/split/metric meaning; changes follow WP-0.1b/0.8.

`shared-benchmarks/lm_cache/` holds versioned `<cache_id>.yaml` manifests;
payload bytes are warmed locally and are not committed. Shared validates file
existence, size and SHA-256 before use. Manifest artifact paths are relative,
UTF-8 sorted and unique. `EVONN_LM_CACHE_DIR` overrides the payload root. Example
shape only, not an admitted cache or valid content digest:

```yaml
schema_version: "1.0.0"
cache_id: tinystories_lm
benchmark_ids: [tinystories_lm]
artifacts:
  - path: train.bin
    size_bytes: 1280
    sha256: "0000000000000000000000000000000000000000000000000000000000000000"
```

## Development workflow

Work on feature branches and use reviewed PRs. GitHub currently requires **zero
approving reviews**, with last-push approval disabled. Linux/macOS checks,
up-to-date branches, resolved review conversations and admin enforcement remain
required; force pushes/deletion of main stay disabled. Substantive review and
the separate frozen-interface amendment evidence remain part of development.

For stacked PRs, merge a parent, retarget its child to main, synchronize and
validate the exact new head before merging. A successful CodeRabbit status can
represent a skipped review: inspect selected files, actionable threads and
summary warnings. Docstring coverage is distinct from code findings.
The plan owns lane assignments and phase acceptance; no second workflow plan
is needed. Stage explicit paths and preserve unrelated local work.

## License

Copyright (C) 2026 Timo Kruth and contributors.

Unless otherwise indicated, original code and documentation are licensed under
GNU GPL version 3 only (`GPL-3.0-only`); see [LICENSE](LICENSE). Each workspace
package carries its own copy for distribution. The software comes without
warranty. Dependencies, datasets and model weights retain their own licenses.
