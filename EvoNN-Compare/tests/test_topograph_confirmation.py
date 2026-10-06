import json
from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from evonn_compare import topograph_confirmation as t


def test_screening_nomination_binding():
    # A changed report must be rejected before a nominee can be reused.
    evidence = dict(status='complete', failures=[], missing=[], results=[])
    nomination = dict(screening_sha256='wrong', nominee='mixer')
    with pytest.raises(ValueError, match='frozen screening'):
        t.validate_screening(evidence, nomination)


def test_bound_document_drift(tmp_path):
    p = tmp_path / 'evidence.json'
    p.write_text('original')
    documents = t.bind_documents([p])
    t.verify_documents(documents)
    p.write_text('edited')
    with pytest.raises(ValueError, match='bound evidence changed'):
        t.verify_documents(documents)


@pytest.fixture
def runner(tmp_path, monkeypatch):
    rows = t.s.matrix('confirmation', 'mixer')[:2]
    calls = []
    monkeypatch.setattr(t.c, 'lease', lambda *args: nullcontext())
    monkeypatch.setattr(t, 'preflight', lambda *args, **kwargs: {})
    monkeypatch.setattr(t.s, 'read_signed', lambda *args: dict(rows=rows))
    monkeypatch.setattr(t, 'saved_receipt', lambda *args: None)
    monkeypatch.setattr(t.c, 'run_campaign', lambda root, **kwargs: calls.append((root, kwargs)))
    monkeypatch.setattr(t.c, 'read_manifest', lambda *args: {})
    monkeypatch.setattr(t.c, 'adopted', lambda path, *args: (path / 'run', {'run_id': 'test'}))
    monkeypatch.setattr(t.subprocess, 'run', lambda *args, **kwargs:
                        SimpleNamespace(returncode=0, stdout='{"status":"passed"}'))
    monkeypatch.setattr(t.s, 'publish_json', lambda *args: None)
    monkeypatch.setattr(t, 'report', lambda *args: {})
    return tmp_path, calls


def test_each_campaign_gets_full_bounded_window(runner):
    root, calls = runner
    result = t.run(root)
    assert result['status'] == 'complete' and result['completed'] == 2
    assert len(calls) == 2
    assert all(options == dict(max_runs=1, session_timeout=1800) for _, options in calls)


def test_pause_stops_without_dispatch(runner):
    root, calls = runner
    (root / 'PAUSE').touch()
    assert t.run(root)['status'] == 'paused'
    assert not calls


def test_failed_campaign_blocks_next_cell(runner, monkeypatch):
    root, calls = runner
    def fail(*args, **kwargs):
        raise ValueError('failed fit')
    monkeypatch.setattr(t.c, 'run_campaign', fail)
    with pytest.raises(ValueError, match='failed fit'):
        t.run(root)
    assert json.loads((root / 'status.json').read_text())['status'] == 'failed'
    assert not calls


def test_replay_failure_stops_before_next_cell(runner, monkeypatch):
    root, calls = runner
    monkeypatch.setattr(t.subprocess, 'run', lambda *args, **kwargs:
                        SimpleNamespace(returncode=1, stderr='bad replay'))
    with pytest.raises(ValueError, match='winner replay failed'):
        t.run(root)
    assert len(calls) == 1


def test_incomplete_report_never_runs_inference(runner, monkeypatch):
    root, _ = runner
    # Restore the function replaced by the runner fixture using its module source.
    # The real report is saved separately before fixture monkeypatching below.
    monkeypatch.setattr(t.s, 'inference', lambda *args: pytest.fail('incomplete inference'))
    with pytest.raises(ValueError, match='incomplete confirmation'):
        REAL_REPORT(root)


REAL_REPORT = t.report
