"""Auditing cannot silently omit a declared task with a missing baseline family."""
import importlib.util
from pathlib import Path

import pytest

pytest.importorskip('torch')
spec=importlib.util.spec_from_file_location('audit_language',Path(__file__).resolve().parents[1]/'scripts/research/audit_language_baselines.py')
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_missing_transformer_task_is_rejected_from_declared_pack():
    declared,language,bindings=audit.expected_language_tasks('language_breadth_v1')
    assert len(language)==4 and set(language)==set(declared) and len(bindings)==5
    attempts=[dict(benchmark_id=task,family=family,status='ok') for task in language
              for family in ['transformer_lm_tiny','unigram_lm','bigram_lm','trigram_lm']]
    audit.require_baseline_coverage(attempts,'language_breadth_v1')
    attempts=[a for a in attempts if not (a['benchmark_id']=='aesop_context64_lm' and a['family']=='transformer_lm_tiny')]
    with pytest.raises(ValueError,match='missing successful transformer_lm_tiny attempt for aesop'):
        audit.require_baseline_coverage(attempts,'language_breadth_v1')


def test_core_audit_requires_its_one_declared_language_task():
    declared,language,_=audit.expected_language_tasks('tier_b_core_v2')
    assert len(declared)==4 and language==['shakespeare_byte_lm']
