# Topograph confirmation resource-admission amendment

The user requested repair and resumption on September 23. The original study
completed all 38 qualification and 152 screening runs and froze `mixer` as its
nominee. Confirmation completed one `next` cell, then stopped at legacy seed
32801 on the language pack. Of 256 attempted candidates, 253 fitted successfully;
three raw-context graphs exceeded the existing two-million-parameter cap before
fitting. The strict completion/accounting validator correctly rejected the export.

Legacy breeding now checks the exact parameter estimate before accepting a
mutated child. If it exceeds the existing cap, the valid parent is retained and
the rejection count is recorded in search state and telemetry. No additional
random draws are introduced. Admitted mutations retain their original behavior.
Model compilation, training, evaluation, accounting and validation stay unchanged.

Because this repairs search behavior, **all 128 confirmation cells restart** in a
separate workspace under one clean producer, `5c0bc17`. The original confirmation
remains incomplete and is excluded from amended inference. Both historical runs,
including 509 charged fits and three rejected proposals, are retained with hashes
and separately reported cost. No historical output, seed or arm is removed.

The screening nomination, all 16 paired confirmation seeds, randomized run order,
four arms, two packs, 256-fit budgets, epoch limits, runtime caps, primary endpoint,
three contrasts and confidence tests remain fixed. This amendment changes the
legacy control's handling of inadmissible mutations; conclusions must name that
amended control. It does not establish superiority over the original failing
legacy implementation. Screening results remain historical, descriptive evidence.

The external controller binds the original signed nomination to the complete
screening report and originating export/replay receipts. It verifies each new
campaign before fitting, admits only complete exports, requires winner replay,
and stops on any failure. Every confirmation export receives full validation again
before final inference. Completed receipts avoid repeated full artifact scans
between cells; mutation of referenced export documents still blocks progress.

Verification: 104 Topograph tests, 46 focused tests in the frozen producer,
seven controller tests in each environment, Ruff and all-data preflight passed.
The original producer remains clean and unchanged.

Current workspace: `.artifacts/topograph-confirmation-repair-20260923/study`.
Read `status.json` there and `../run.log` for progress. Use the adjacent `studyctl`
with `pause`, `resume`, `preflight` or `report`. `run`/`resume` execute all remaining
cells serially; each campaign has its own 30-minute scheduling allowance with
verification overhead. No automatic restart after failure or reboot is installed.
The original artifact directory's `CURRENT.json` points to this continuation.

The [launch receipt](topograph-confirmation-repair-20260923.json) records exact
source/controller/plan identities and the retained historical computation cost.
