"""Compare Phase 1 CLI: orchestration, reports, audit and quality."""
import argparse
import json
from pathlib import Path
import webbrowser

from evonn_shared.export_reader import read_document, read_export
from .cases import Case, evaluate_case, resolve_preset
from .evidence import trend_rows, winners
from .quality import classify
from .workspace import fair_matrix, workspace_audit, workspace_report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    campaign = commands.add_parser("campaign", help="plan, preflight and resume bounded campaigns")
    campaign_actions = campaign.add_subparsers(dest="campaign_command", required=True)
    planning = campaign_actions.add_parser("plan", help="prepare data and freeze settings; no model fits")
    planning.add_argument("--workspace", type=Path, required=True)
    planning.add_argument("--spec", type=Path, required=True)
    planning.add_argument("--cache", type=Path, required=True)
    planning.add_argument("--preparation-timeout", type=float, default=1800)
    checking = campaign_actions.add_parser("preflight", help="read-only validation; no downloads or training")
    checking.add_argument("workspace", type=Path)
    execution = campaign_actions.add_parser("run", aliases=["resume"])
    execution.add_argument("workspace", type=Path)
    execution.add_argument("--session-timeout", type=float, default=1800)
    execution.add_argument("--max-runs", type=int)
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
    matrix.add_argument("--engine-backend", choices=["numpy_fallback", "mlx_native"], default="numpy_fallback")
    matrix.add_argument("--engine-epochs", type=int, default=12)
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
    evidence = commands.add_parser("evidence")
    actions = evidence.add_subparsers(dest="evidence_command", required=True)
    promotion = actions.add_parser("promote")
    promotion.add_argument("source", type=Path)
    promotion.add_argument("--label", required=True)
    promotion.add_argument("--copy-artifacts", action="store_true")
    validation = actions.add_parser("validate")
    reporting = actions.add_parser("report")
    reporting.add_argument("--request", type=Path)
    cohort_reporting = actions.add_parser("cohort-report", help="explicit engine, floor or budget contrasts without training")
    cohort_reporting.add_argument("--request", type=Path, required=True)
    supersession = actions.add_parser("supersede")
    supersession.add_argument("--old", required=True)
    supersession.add_argument("--new", required=True)
    supersession.add_argument("--reason", required=True)
    policy = actions.add_parser("pr-policy")
    policy.add_argument("--event", type=Path, required=True)
    policy.add_argument("--root", type=Path, default=Path.cwd())
    declared = actions.add_parser("hydrate-declared")
    declared.add_argument("--root", type=Path, default=Path.cwd())
    packing = actions.add_parser("pack")
    packing.add_argument("--archive", type=Path, required=True)
    hydration = actions.add_parser("hydrate")
    hydration.add_argument("--archive", type=Path, required=True)
    hydration.add_argument("--descriptor", type=Path, required=True)
    gate = actions.add_parser("decision-gate")
    gate.add_argument("--body", type=Path, required=True)
    for action in (promotion, validation, reporting, cohort_reporting, supersession, gate, packing, hydration):
        action.add_argument("--registry", type=Path, default=Path("evidence"))
    for action in (validation, reporting, cohort_reporting):
        action.add_argument("--require-artifacts", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "campaign":
            from .campaign import CampaignSpec, preflight, prepare_plan, run_campaign
            if args.campaign_command == "plan":
                spec = CampaignSpec.model_validate_json(read_document(args.spec.parent, args.spec.name))
                result = prepare_plan(args.workspace, spec, args.cache, timeout=args.preparation_timeout)
            elif args.campaign_command == "preflight":
                result = preflight(args.workspace.absolute())
            else:
                result = run_campaign(args.workspace, session_timeout=args.session_timeout, max_runs=args.max_runs)
            print(json.dumps(result, indent=2, allow_nan=False))
            return 0
        if args.command == "evidence":
            from .registry import promote, registry_report, supersede, validate_registry
            if args.evidence_command == "pr-policy":
                from .pr_policy import main as policy_main
                return policy_main(["--event", str(args.event), "--root", str(args.root)])
            if args.evidence_command == "hydrate-declared":
                from .transport import hydrate_declared
                result = hydrate_declared(args.root)
            elif args.evidence_command == "promote":
                result = {"record_ids": promote(args.source, registry=args.registry, label=args.label, copy_artifacts=args.copy_artifacts)}
            elif args.evidence_command == "validate":
                result = validate_registry(args.registry, require_artifacts=args.require_artifacts)
            elif args.evidence_command == "report":
                request = json.loads(args.request.read_text()) if args.request else None
                result = registry_report(args.registry, request=request, require_artifacts=args.require_artifacts)
            elif args.evidence_command == "cohort-report":
                from .cohort import cohort_report
                result = cohort_report(args.registry, json.loads(args.request.read_text()), require_artifacts=args.require_artifacts)
            elif args.evidence_command in ("pack", "hydrate"):
                from .transport import pack_registry, hydrate_registry
                result = (pack_registry(args.registry, archive=args.archive) if args.evidence_command == "pack" else
                          hydrate_registry(args.registry, archive=args.archive, descriptor=args.descriptor))
            elif args.evidence_command == "decision-gate":
                from .decision_gate import validate_decision_block
                result = validate_decision_block(args.body.read_text(), registry=args.registry)
            else:
                supersede(args.registry, old=args.old, new=args.new, reason=args.reason)
                result = {"status": "passed"}
            print(json.dumps(result, indent=2, allow_nan=False))
            return int(result.get("status") == "blocked")
        if args.command == "fair-matrix":
            pack = args.pack or "tier1_core"
            if args.preset:
                pack, budget = resolve_preset(args.preset)
                if args.budgets is not None and args.budgets != [budget]:
                    raise ValueError("preset budget cannot be overridden")
                args.budgets = [budget]
            data = fair_matrix(workspace=args.workspace, pack=pack, budgets=args.budgets, seeds=args.seeds,
                systems=args.systems, no_contenders=args.no_contenders, timeout=args.timeout, fit_timeout=args.fit_timeout,
                cache=args.cache, enhanced=args.enhanced, cohort=args.cohort, reset_workspace=args.reset_workspace, engine_backend=args.engine_backend, engine_epochs=args.engine_epochs)
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
            result = workspace_audit(args.workspace, args.pack, decision_grade=args.decision_grade)
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
