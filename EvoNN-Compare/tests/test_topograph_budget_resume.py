from copy import deepcopy
from contextlib import nullcontext
import json

import pytest
from evonn_compare import topograph_budget_resume as t


def test_only_unfinished_total_caps_change():
    rows = t.s.matrix('confirmation', 'mixer')
    before = deepcopy(rows)
    inherited = {rows[0]['campaign']: {}}
    amended = t.amended_rows(rows, inherited)
    assert rows == before and amended[0] == rows[0]
    for old, new in zip(rows[1:], amended[1:]):
        assert new['spec']['timeout'] == 39000
        new['spec']['timeout'] = old['spec']['timeout']
        assert old == new


def test_cap_requires_explicit_topograph_scope():
    spec = t.amended_rows(t.s.matrix('confirmation', 'mixer'), {})[0]['spec']
    assert t.c.CampaignSpec.model_validate(spec).timeout == 39000
    with pytest.raises(ValueError):
        t.c.CampaignSpec.model_validate(dict(spec, comparison_scope='all_engines', systems=list(t.c.SYSTEMS)))


def test_failed_checkpoint_cannot_be_silently_retried(tmp_path, monkeypatch):
    state = {'completed': 180, 'attempts': [{'status': 'failed', 'charged': 1}]}
    monkeypatch.setattr(t, 'load_runtime_checkpoint', lambda *args: (None, json.dumps(state)))
    with pytest.raises(ValueError, match='no automatic retry'):
        t.checkpoint_progress(tmp_path)


def test_inherited_results_are_not_retrained_and_pause_preserves_counts(tmp_path, monkeypatch):
    rows = t.s.matrix('confirmation', 'mixer')[:3]
    inherited = {r['campaign']: {} for r in rows[:2]}
    plan = dict(rows=rows, inherited=inherited, parent=str(tmp_path / 'parent'), segment_fits=32)
    monkeypatch.setattr(t.c, 'lease', lambda *args: nullcontext(1))
    monkeypatch.setattr(t, 'preflight', lambda *args: None)
    monkeypatch.setattr(t.s, 'read_signed', lambda *args: plan)
    monkeypatch.setattr(t, 'saved_receipt', lambda p: {} if 'parent' in p.parts else None)
    monkeypatch.setattr(t, 'dispatch_segment', lambda *args: pytest.fail('no dispatch while paused'))
    (tmp_path / 'PAUSE').touch()
    result = t.run(tmp_path)
    assert result['status'] == 'paused' and result['completed'] == 2


def test_segment_failure_stops_progress(tmp_path, monkeypatch):
    rows = t.s.matrix('confirmation', 'mixer')[:2]
    plan = dict(rows=rows, inherited={}, parent=str(tmp_path / 'parent'), segment_fits=32)
    monkeypatch.setattr(t.c, 'lease', lambda *args: nullcontext(1))
    monkeypatch.setattr(t, 'preflight', lambda *args: None)
    monkeypatch.setattr(t.s, 'read_signed', lambda *args: plan)
    monkeypatch.setattr(t, 'saved_receipt', lambda *args: None)
    calls = []
    def fail(*args):
        calls.append(args)
        raise ValueError('bad segment')
    monkeypatch.setattr(t, 'dispatch_segment', fail)
    with pytest.raises(ValueError, match='bad segment'):
        t.run(tmp_path)
    assert len(calls) == 1
    assert json.loads((tmp_path / 'status.json').read_text())['status'] == 'failed'


def test_incomplete_report_blocks_inference(tmp_path, monkeypatch):
    rows = t.s.matrix('confirmation', 'mixer')[:1]
    monkeypatch.setattr(t, 'preflight', lambda *args: None)
    monkeypatch.setattr(t.s, 'read_signed', lambda *args: dict(rows=rows, inherited={}))
    monkeypatch.setattr(t, 'saved_receipt', lambda *args: None)
    monkeypatch.setattr(t.s, 'inference', lambda *args: pytest.fail('no partial inference'))
    with pytest.raises(ValueError, match='incomplete confirmation'):
        t.report(tmp_path)


def test_inherited_report_uses_its_original_producer(tmp_path, monkeypatch):
    row = t.s.matrix('confirmation', 'mixer')[0]
    parent = tmp_path / 'original'
    plan = dict(rows=[row], inherited={row['campaign']: {}}, parent=str(parent))
    monkeypatch.setattr(t, 'preflight', lambda *args: None)
    monkeypatch.setattr(t.s, 'read_signed', lambda *args: plan)
    monkeypatch.setattr(t, 'saved_receipt', lambda *args: {})
    monkeypatch.setattr(t.c, 'read_manifest', lambda *args: {})
    monkeypatch.setattr(t.c, 'adopted', lambda *args: pytest.fail('wrong producer for inherited export'))
    def original(origin, campaign):
        assert origin == parent and campaign == parent / row['campaign']
        raise ValueError('original admission reached')
    monkeypatch.setattr(t, 'admit_origin', original)
    with pytest.raises(ValueError, match='original admission reached'):
        t.report(tmp_path)
