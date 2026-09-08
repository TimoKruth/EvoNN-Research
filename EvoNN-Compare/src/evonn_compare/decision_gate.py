"""Machine-checked PR evidence blocks; no category supplied on trust."""
import json
from pathlib import Path
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from evonn_shared.export_reader import read_document
from .registry import read_registry, registry_report, validate_registry
from .statistics import AnalysisRequest, DecisionCategory

DASHBOARD_SLICES=(
    'Overall Leaderboard: Projects Only','Aggregate Evidence: Projects Only',
    'Per-Seed Aggregate Snapshots: Projects Only','Engine Rank By Benchmark Family: Projects Only',
    'Benchmark Trend View',
)


class EvidenceBlock(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    schema_version: Literal[1]=1
    workspace_paths: list[str]=Field(min_length=1)
    trend_report_paths: list[str]=Field(min_length=1)
    dashboard_paths: list[str]=Field(min_length=1)
    comparison_labels: list[str]=Field(min_length=2,max_length=2)
    case_ids: list[str]=Field(min_length=1)
    run_ids: list[str]=Field(min_length=1)
    dashboard_slices: list[str]=Field(min_length=1)
    packs: list[str]=Field(min_length=1)
    budgets: list[int]=Field(min_length=1)
    seeds: list[int]=Field(min_length=1)
    operating_states: list[str]=Field(min_length=1)
    accounting_states: list[str]=Field(min_length=1)
    repeatability_states: list[str]=Field(min_length=1)
    decision_category: str
    request_path: str


def parse_block(body):
    matches=re.findall(r'^```evonn-evidence\s*\n(.*?)^```\s*$',body,flags=re.MULTILINE|re.DOTALL)
    if len(matches)!=1:
        raise ValueError('exactly one evonn-evidence JSON block required')
    block=EvidenceBlock.model_validate_json(matches[0])
    DecisionCategory(block.decision_category)
    if not set(DASHBOARD_SLICES)<=set(block.dashboard_slices):
        raise ValueError('all five required named dashboard slices must be reviewed')
    allowed=set(DASHBOARD_SLICES)|{name.replace('Projects Only','All Systems') for name in DASHBOARD_SLICES}
    if not set(block.dashboard_slices)<=allowed:
        raise ValueError('unknown named dashboard slice')
    for field in ('comparison_labels','case_ids','run_ids','packs','budgets','seeds'):
        values=block.model_dump()[field]
        if len(values)!=len(set(values)):
            raise ValueError(f'duplicate {field} in evidence block')
    return block


def validate_decision_block(body, *, registry):
    block=parse_block(body)
    root=Path(registry)
    validation=validate_registry(root,require_artifacts=True)
    if validation['status']!='passed':
        raise ValueError('registry validation blocked: '+'; '.join(validation['blockers']))
    request=AnalysisRequest.model_validate_json(read_document(root,block.request_path))
    if set(block.comparison_labels)!={request.before,request.after}:
        raise ValueError('comparison labels differ from stored analysis request')
    records=[r for r in read_registry(root) if r['label'] in block.comparison_labels and r['decision_status'] not in ('superseded','rejected')]
    expected=dict(case_ids=sorted({r['case_id'] for r in records}),run_ids=sorted({r['run_id'] for r in records}),
        packs=sorted({r['pack'] for r in records}),budgets=sorted({r['budget'] for r in records}),seeds=sorted({r['seed'] for r in records}),
        operating_states=sorted({r['lane_trust_state'] for r in records}),accounting_states=sorted({r['budget_accounting_state'] for r in records}),
        repeatability_states=sorted({r['repeatability_state'] for r in records}))
    for name,values in expected.items():
        if sorted(block.model_dump()[name])!=values:
            raise ValueError(f'evidence block {name} differ from exact registry cohort')
    if not set(block.workspace_paths)<={p for r in records for p in r['source_paths']}:
        raise ValueError('workspace path not bound by registry')
    for name in block.trend_report_paths+block.dashboard_paths:
        read_document(root,name,limit=128*1024*1024)
    if set(block.trend_report_paths)!={'evidence_report.md','evidence_report.json'} or set(block.dashboard_paths)!={'fair_matrix_dashboard.html','fair_matrix_dashboard.json'}:
        raise ValueError('cite canonical registry report and dashboard artifacts')
    report=registry_report(root,request=request,require_artifacts=True)
    if report['analysis']['decision_category']!=block.decision_category:
        raise ValueError('claimed decision category differs from recomputed evidence')
    return dict(status='passed',decision_category=block.decision_category,run_ids=block.run_ids,case_ids=block.case_ids,
        target_engines=sorted({panel.engine for panel in request.panels}),before_revision=request.before_revision,after_revision=request.after_revision)


def validate_event(event_path, *, registry, advancement):
    event=json.loads(Path(event_path).read_text())
    if not advancement:
        return {'status':'not_applicable','reason':'no engine runtime advancement in this diff'}
    body=event['pull_request']['body'] or ''
    return validate_decision_block(body,registry=registry)
