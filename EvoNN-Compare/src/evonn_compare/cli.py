"""Compare Phase 1 CLI: orchestration, reports, audit and quality."""
import argparse
import json
from pathlib import Path
import webbrowser

from evonn_shared.export_reader import read_export
from .audit import benchmark_audit
from .cases import Case, evaluate_case, resolve_preset
from .evidence import trend_rows, winners
from .quality import classify
from .workspace import fair_matrix, load_cases, workspace_report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    matrix = commands.add_parser("fair-matrix")
    matrix.add_argument("--workspace", type=Path, required=True)
    selection = matrix.add_mutually_exclusive_group()
    selection.add_argument("--pack")
    selection.add_argument("--preset")
    matrix.add_argument("--reset-workspace", action="store_true")
    matrix.add_argument("--budgets", nargs="+", type=int)
    matrix.add_argument("--seeds", nargs="+", type=int, default=[42])
    matrix.add_argument("--systems", nargs="+", default=["contenders"])
    matrix.add_argument("--no-contenders", action="store_true")
    matrix.add_argument("--cohort", choices=["current", "exploratory", "reference"], default="current")
    matrix.add_argument("--timeout", type=float, default=1200)
    matrix.add_argument("--fit-timeout", type=float, default=180)
    matrix.add_argument("--cache", type=Path)
    matrix.add_argument("--enhanced", action="store_true")
    view = matrix.add_mutually_exclusive_group()
    view.add_argument("--open", action="store_true")
    view.add_argument("--no-open", action="store_true")
    for name in ("workspace-report", "trend-report", "dashboard", "output-quality"):
        command = commands.add_parser(name)
        command.add_argument("workspace", type=Path)
        if name == "trend-report":
            command.add_argument("--benchmark")
            command.add_argument("--budget", type=int)
            command.add_argument("--system")
    audit = commands.add_parser("benchmark-audit")
    audit.add_argument("--pack", required=True)
    audit.add_argument("--workspace", type=Path, required=True)
    audit.add_argument("--decision-grade", action="store_true")
    compare = commands.add_parser("compare")
    compare.add_argument("exports", nargs="+", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "fair-matrix":
            pack = args.pack or "tier1_core"
            if args.preset:
                pack, budget = resolve_preset(args.preset)
                if args.budgets is not None and args.budgets != [budget]:
                    raise ValueError("preset budget cannot be overridden")
                args.budgets = [budget]
            data = fair_matrix(workspace=args.workspace, pack=pack, budgets=args.budgets, seeds=args.seeds,
                systems=args.systems, no_contenders=args.no_contenders, timeout=args.timeout, fit_timeout=args.fit_timeout,
                cache=args.cache, enhanced=args.enhanced, cohort=args.cohort, reset_workspace=args.reset_workspace)
            if args.open:
                webbrowser.open((args.workspace / "fair_matrix_dashboard.html").absolute().as_uri())
            print(json.dumps({"workspace": str(args.workspace.absolute()), "cases": len(data["cases"]),
                              "states": [case["acceptance"]["operating_state"] for case in data["cases"]]}, indent=2))
            return int(any(case["acceptance"]["blockers"] for case in data["cases"]))
        if args.command == "compare":
            bundles = [read_export(root) for root in args.exports]
            manifest = bundles[0].manifest
            case = Case(manifest.pack_id, manifest.accounting.evaluation_count, manifest.seed)
            acceptance = evaluate_case(case, bundles)
            rows = [row for bundle in bundles for row in trend_rows(bundle, case.id, acceptance)]
            result = {"acceptance": acceptance, "all_systems": winners(rows), "projects_only": winners(rows, projects_only=True)}
        elif args.command == "benchmark-audit":
            data = workspace_report(args.workspace)
            loaded = load_cases(args.workspace)
            bundles = [bundle for _, _, values, _ in loaded for bundle in values]
            result = benchmark_audit(args.pack, bundles, decision_grade=args.decision_grade,
                dashboard_present=(args.workspace / "fair_matrix_dashboard.html").is_file(),
                output_levels={item["run_id"]: item["level"] for item in data["output_quality"]})
            source_blockers = [reason for _, document, _, acceptance in loaded if document["case"]["pack"] == args.pack for reason in acceptance["blockers"]]
            result["blockers"] = sorted(set(result["blockers"] + source_blockers))
            result["blocker_count"] = len(result["blockers"])
            result["status"] = "blocked" if result["blockers"] else result["status"]
            print(json.dumps(result, indent=2, allow_nan=False))
            return int(result["blocker_count"] > 0)
        elif args.command == "output-quality" and (args.workspace / "manifest.json").is_file():
            result = classify(args.workspace)
        else:
            data = workspace_report(args.workspace)
            result = data
            if args.command == "output-quality":
                result = data["output_quality"]
            elif args.command == "trend-report":
                result = [row for row in data["rows"] if (args.benchmark is None or row["benchmark"] == args.benchmark)
                          and (args.budget is None or row["budget"] == args.budget)
                          and (args.system is None or row["engine"] == args.system)]
            else:
                result = {"workspace": str(args.workspace.absolute()), "cases": len(data["cases"]),
                          "dashboard": str(args.workspace / "fair_matrix_dashboard.html")}
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"Compare: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
