import json

import pytest

from evonn_compare.decision_gate import DASHBOARD_SLICES, parse_block, validate_decision_block


def block(**updates):
    data=dict(schema_version=1,workspace_paths=['workspace'],trend_report_paths=['evidence_report.md','evidence_report.json'],
        dashboard_paths=['fair_matrix_dashboard.html','fair_matrix_dashboard.json'],comparison_labels=['before','after'],
        case_ids=['case'],run_ids=['run'],dashboard_slices=list(DASHBOARD_SLICES),packs=['tier1_core'],budgets=[64],seeds=[0,1,2],
        operating_states=['trusted-core'],accounting_states=['complete'],repeatability_states=['multi_seed'],decision_category='inconclusive',request_path='request.json')
    return '```evonn-evidence\n'+json.dumps({**data,**updates})+'\n```\n'


def test_malformed_blocks_fail():
    for body in ('',block()+block(),block(decision_category='clear_gain'),block(decision_category=['promote','regress']),block(dashboard_slices=['dashboard']),block(run_ids=['run','run'])):
        with pytest.raises(ValueError):
            parse_block(body)
    assert parse_block(block()).decision_category=='inconclusive'


def test_registry_citations_must_exist(tmp_path):
    with pytest.raises(ValueError,match='registry validation'):
        validate_decision_block(block(),registry=tmp_path)
