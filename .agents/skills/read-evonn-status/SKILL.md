---
name: read-evonn-status
description: Read the current EvoNN engine comparison's progress, active engine, pauses, failures and guardian health in one quick query. Use for “Status?”, “Update?”, “Is training still running?” and EvoNN training notifications in this project. Not for SLM runs, PR status or full scientific evaluation.
---

# EvoNN training status

From the EvoNN project root, run once:

```sh
.venv/bin/python .agents/skills/read-evonn-status/scripts/status.py --project .
```

Any available Python 3.10+ works; this script uses only the standard library.
When the guardian directory is known from the conversation, add
`--guardian /absolute/path/to/guardian-state`. No fixed historical campaign is
assumed current. Discovery reads only `.artifacts/*/config.json`; if several
unfinished guardians exist, use the returned candidates and conversation to
select one. Do not silently choose the newest active campaign.

The query follows `control.json.target` after repairs and reads the bounded
campaign journals, current process table, launchd services and recent guardian
history. It does not import engines, inspect checkpoints, run preflight, load
exports, fit models, scan the entire artifact tree or install dependencies.

## Interpret the snapshot

- Report local time, completed/planned runs, active engine/budget/seed and any
  current problem. Budget and engine counts include all four engines and
  Contenders declared by the protocol. Missing systems are visible, not excluded.
- Counts are **journaled completions**, not a new validation of all exported
  results. A matching guardian completion receipt records its final verification.
  Training completion does not mean the statistical comparison has been evaluated.
- Prefer the current guardian target and journals over the original supervisor's
  stale status. An absent engine process can mean between-run waiting or an active
  validation probe. A launchd agent normally shows `not running` between ticks.
  Match live command paths; old recorded PIDs alone do not prove liveness.
- `control.last_error` is also used as a crash sentinel during healthy managed
  training. The script does not report it as a current failure without supporting
  state. Historical repair events and the hourly check's old alerts have their own
  timestamps; do not present them as new interruptions.
- Host identity is checked directly against the frozen identity, even between
  guardian polls: new `machine-v1` campaigns use the shared machine-ID helper;
  historical campaigns retain their hostname check. A matching host alone does not validate code, libraries or
  data. Preserve unknown/error output and investigate only the specific file or
  short log tail needed; never call an incomplete query “healthy”.
- Do not infer ETA from mixed budgets or wall time containing manual pauses.
  Do not infer scores, winners or statistical significance from progress counts.

Keep the response short and emphasize changes since the previous update.
This skill is read-only: no pause/resume, repairs, hostname changes, notification
sending, scheduler changes or edits to frozen evidence. An explicit action request
is handled separately from the status query.
