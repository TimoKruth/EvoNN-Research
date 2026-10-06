from copy import deepcopy
import json
import pytest

from evonn_compare import stratograph_continuation as c


def test_amendment_changes_only_unfinished_caps():
    p = {'slots': c.study.slots(c.study.StudySpec())}
    before = deepcopy(p)
    inherited = {s['id']: {} for s in p['slots'][:35]}
    actual = c.amended_slots(p, inherited)
    assert p == before
    assert actual[:35] == p['slots'][:35]
    for old, new in zip(p['slots'][35:], actual[35:]):
        expected = deepcopy(old)
        expected['config']['timeout'] = 1800.
        assert new == expected


def fixture_parent(tmp_path, monkeypatch, epochs=12, reason='isolated worker wall-clock cap exceeded'):
    parent = tmp_path/'parent'
    parent.mkdir()
    failed = parent/'runs'/'bad'/'run1'
    failed.mkdir(parents=True)
    attempts = [{'status': 'ok', 'charged': 1, 'train_seconds': 2}, {'status':'failed','charged':1,'reason':reason}]
    (failed/'attempts.json').write_text(json.dumps({'attempts':attempts}))
    for name in ('summary.json','config.yaml'):
        (failed/name).write_text('{}')
    receipt = {'export':'good/symbiosis','documents':{'manifest.json':'abc'}}
    old = {'status':'incomplete','completed':{'good':receipt},'failures':[{'slot':'bad','reason':'no complete export'}]}
    (parent/'status.json').write_text(json.dumps(old))
    plan = {'sha256':'parent', 'slots':[{'id':'good','config':{'timeout':1500.}}, {'id':'bad','config':{'timeout':1500.}}]}
    monkeypatch.setattr(c.study, 'preflight', lambda root: None)
    monkeypatch.setattr(c.study, 'read_plan', lambda root: plan)
    monkeypatch.setattr(c.study, 'adopt', lambda *a: (None, receipt))
    monkeypatch.setattr(c, 'verify_receipt', lambda *a: None)
    monkeypatch.setattr(c, 'read_export', lambda *a: None)
    monkeypatch.setattr(c, 'artifact_json', lambda *a: {'attempts':[{'epochs':epochs,'allocated_epochs':12}]})
    return parent


def test_prepare_retains_failure_cost_and_parent_bytes(tmp_path, monkeypatch):
    parent = fixture_parent(tmp_path, monkeypatch)
    old = (parent/'status.json').read_bytes()
    root = tmp_path/'next'
    result = c.prepare(parent, root)
    assert result == {'status':'prepared','inherited_runs':1,'remaining_runs':1,'retained_failed_attempts':2}
    manifest, _, state = c.preflight(root)
    assert manifest['retained_failures'][0]['failed_attempts'] == 1
    assert manifest['retained_failures'][0]['successful_attempts'] == 1
    assert (parent/'status.json').read_bytes() == old
    state['completed'].clear()
    (root/'status.json').write_text(json.dumps(state))
    with pytest.raises(ValueError, match='inherited completion'):
        c.preflight(root)


def test_reject_partial_epochs(tmp_path, monkeypatch):
    parent = fixture_parent(tmp_path, monkeypatch, epochs=11)
    with pytest.raises(ValueError, match='time-limited training'):
        c.prepare(parent, tmp_path/'next')


def test_reject_undiagnosed_failure(tmp_path, monkeypatch):
    parent = fixture_parent(tmp_path, monkeypatch, reason='invalid tensor')
    with pytest.raises(ValueError, match='only addresses'):
        c.prepare(parent, tmp_path/'next')


def test_failed_continuation_never_automatically_retries(tmp_path, monkeypatch):
    parent = fixture_parent(tmp_path, monkeypatch)
    root = tmp_path/'next'
    c.prepare(parent, root)
    state = json.loads((root/'status.json').read_text())
    state['failures'] = [{'slot':'bad','reason':'timeout again'}]
    (root/'status.json').write_text(json.dumps(state))
    monkeypatch.setattr(c, '_bounded_process', lambda *a, **k: pytest.fail('unexpected dispatch'))
    with pytest.raises(ValueError, match='automatic retries are disabled'):
        c.run(root)
