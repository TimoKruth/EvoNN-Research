"""Engine advancement needs exact registry evidence, independent of PR prose."""
from pathlib import Path
from evonn_compare import pr_policy

import pytest

ROOT=Path(__file__).resolve().parents[2]
POLICY={'check':pr_policy.check}


def test_policy_rejects_malformed_advancement_and_unbound_registry_citations(tmp_path):
    for body,paths in [('looks good',['EvoNN-Stratograph/src/stratograph/search.py']),
                       ('see evidence/evidence_report.json',['README.md'])]:
        with pytest.raises(ValueError):
            POLICY['check'](root=tmp_path,body=body,paths=paths)
    assert POLICY['check'](root=tmp_path,body='documentation correction',paths=['README.md'])['status']=='not_applicable'


def test_both_required_lanes_enforce_evidence_and_template_names_contract():
    for name in ('linux-trust.yml','macos-engines.yml'):
        assert 'evonn-compare evidence pr-policy --event "$GITHUB_EVENT_PATH"' in (ROOT/'.github/workflows'/name).read_text()
    template=(ROOT/'.github/pull_request_template.md').read_text()
    assert 'exactly one `evonn-evidence` JSON block' in template
    assert 'EvidenceBlock' in template
