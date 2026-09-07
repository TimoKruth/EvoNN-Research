"""Machine-readable synthetic persistence evidence, never engine qualification."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import signal
import subprocess
import sys

_SPEC = importlib.util.spec_from_file_location("synthetic_probe_runner", Path(__file__).with_name("reference_runner.py"))
if _SPEC is None or _SPEC.loader is None:
    raise ImportError("reference runner helper is unavailable")
runner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(runner)

BOUNDARIES = ("row", "stage", "payload", "manifest")
STEPS = (2, 3)  # Known failure and pre-evaluation invalidity respectively.
BUDGET = 6


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(runner.encode(value)).hexdigest()


def source_digest(root):
    return digest({
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*")) if path.is_file()
    })


def invoke(root, *arguments):
    return subprocess.run(
        [sys.executable, str(Path(runner.__file__)), str(root), *map(str, arguments)],
        capture_output=True, text=True, timeout=30, check=False,
    )


def checked_diagnostic(root, destination):
    before = source_digest(root)
    runner.export_diagnostic(root, destination)
    after = source_digest(root)
    require(before == after, "diagnostic export changed its source")
    return json.loads(destination.read_bytes()), before, after


def validate_report(report):
    """Validate internal consistency of this synthetic report, not authenticity."""
    try:
        require(report["schema_version"] == "1", "unsupported probe schema")
        require(report["evidence_class"] == "synthetic_contract_preparation", "wrong evidence class")
        require(type(report["budget"]) is int and report["budget"] == BUDGET, "wrong budget")
        baseline = report["baseline"]
        require(baseline["source_before"] == baseline["source_after"], "baseline source changed")
        cases = report["cases"]
        expected = {(boundary, step) for boundary in BOUNDARIES for step in STEPS}
        require(len(cases) == len(expected), "missing or duplicate cases")
        require({(case["boundary"], case["step"]) for case in cases} == expected, "wrong case matrix")
        for case in cases:
            require(type(case["step"]) is int and type(case["returncode"]) is int, "invalid case scalar types")
            require(case["returncode"] == -signal.SIGKILL, "child was not killed by SIGKILL")
            require(case["rows_sha256"] == baseline["rows_sha256"], "row-chain mismatch")
            require(case["checkpoint_sha256"] == baseline["checkpoint_sha256"], "checkpoint mismatch")
            require(case["source_before"] == case["source_after"], "resumed source changed")
            accounting = runner.BudgetAccounting.model_validate(case["accounting"])
            require(accounting.actual_evaluations == BUDGET - case["step"], "fresh work was recharged")
            require(accounting.cached_evaluations == accounting.resumed_evaluations == case["step"], "bad inherited work")
            require(accounting.evaluation_count == BUDGET and not accounting.partial_run, "incomplete run")
            require(accounting.failed_evaluations == 1, "wrong fresh failure accounting")
            require(accounting.invalid_evaluations == (2 if case["step"] == 2 else 1), "wrong fresh invalid accounting")
            require(case["resumed_trace"] == [f"evaluate:{index}" for index in range(case["step"], BUDGET)],
                    "resumed selector reevaluated committed work")
        for item in (baseline, *cases):
            for key in ("rows_sha256", "checkpoint_sha256", "source_before", "source_after"):
                value = item[key]
                require(type(value) is str and len(value) == 64 and set(value) <= set("0123456789abcdef"),
                        "invalid digest encoding")
    except (KeyError, TypeError) as error:
        raise ValueError("malformed integrity report") from error


def generate(work_root, output):
    require(not output.resolve().is_relative_to(work_root.resolve()), "output must be outside probe work root")
    require(not output.exists(), "output already exists")
    work_root.parent.mkdir(parents=True, exist_ok=True)
    work_root.mkdir()  # Never reuse or delete another run's evidence.
    outcomes = ("success", "failed", "invalid", "success", "failed", "invalid")
    baseline_root = runner.initialize(work_root / "baseline", budget=BUDGET, outcomes=outcomes)
    complete = invoke(baseline_root)
    require(complete.returncode == 0, f"baseline failed: {complete.stderr}")
    require(complete.stdout.splitlines() == [f"evaluate:{i}" for i in range(BUDGET)], "bad baseline trace")
    baseline, before, after = checked_diagnostic(baseline_root, work_root / "baseline.json")
    report = {
        "schema_version": "1", "evidence_class": "synthetic_contract_preparation", "budget": BUDGET,
        "host": {"platform": sys.platform, "machine": platform.machine(), "python": platform.python_version()},
        "baseline": {
            "rows_sha256": digest(baseline["evaluations"]), "checkpoint_sha256": baseline["checkpoint_sha256"],
            "source_before": before, "source_after": after,
        },
        "cases": [],
    }
    for boundary in BOUNDARIES:
        for step in STEPS:
            name = f"{boundary}_{step}"
            root = runner.initialize(work_root / name, budget=BUDGET, outcomes=outcomes)
            killed = invoke(root, "--crash-at", boundary, "--crash-step", step)
            require(killed.returncode == -signal.SIGKILL, f"expected real SIGKILL at {name}")
            require(killed.stdout.splitlines() == [
                *[f"evaluate:{i}" for i in range(step)], f"crash:{boundary}:{step}"
            ], f"unexpected interrupted trace at {name}")
            resumed = invoke(root)
            require(resumed.returncode == 0, f"resume failed at {name}: {resumed.stderr}")
            diagnostic, before, after = checked_diagnostic(root, work_root / f"{name}.json")
            report["cases"].append({
                "boundary": boundary, "step": step, "returncode": killed.returncode,
                "rows_sha256": digest(diagnostic["evaluations"]),
                "checkpoint_sha256": diagnostic["checkpoint_sha256"],
                "accounting": diagnostic["accounting"], "resumed_trace": resumed.stdout.splitlines(),
                "source_before": before, "source_after": after,
            })
    validate_report(report)
    with output.open("xb") as stream:
        stream.write(runner.encode(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate", type=Path)
    options = parser.parse_args()
    try:
        if options.validate is not None:
            if options.work_root is not None or options.output is not None:
                parser.error("--validate cannot be combined with generation options")
            validate_report(json.loads(options.validate.read_bytes()))
        elif options.work_root is not None and options.output is not None:
            generate(options.work_root, options.output)
        else:
            parser.error("supply --work-root and --output, or --validate")
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f"integrity probe failed: {error}\n")
    print("Synthetic integrity probe: PASS (not Phase-0 acceptance)")


if __name__ == "__main__":
    main()
