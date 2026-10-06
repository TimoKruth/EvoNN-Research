"""Regression checks for accumulated verification starving pending study slots."""
from contextlib import nullcontext
import json
from types import SimpleNamespace

import pytest
from evonn_compare import topograph_study as s


@pytest.fixture
def scheduling(tmp_path, monkeypatch):
    clock = [0.0]
    rows = s.matrix('screening')[:3]
    paths = [tmp_path / row['campaign'] for row in rows]
    for path in paths:
        path.mkdir(parents=True)
    complete = {paths[0]}
    reference = {'run_id': 'fixture'}
    s.publish_json(paths[0] / 'winner-replay.json', s.signed(dict(
        reference=reference, result={'status': 'passed'})))
    calls = []
    def slow_preflight(root):
        clock[0] += 4000  # Longer than even the entire dispatch window.
    def adopted(path, *args):
        if path == paths[0]:
            clock[0] += 2000  # Revalidating completed history also grows.
        return (path / 'run', reference) if path in complete else (None, None)
    def dispatch(path, **kwargs):
        calls.append((path, kwargs))
        complete.add(path)
        clock[0] += 200  # Leaves too little allowance for another 1500s slot.
    monkeypatch.setattr(s.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(s.c, 'lease', lambda root: nullcontext())
    monkeypatch.setattr(s, 'preflight', slow_preflight)
    monkeypatch.setattr(s, 'read_plan', lambda root: {})
    monkeypatch.setattr(s, 'stage_rows', lambda *args: rows)
    monkeypatch.setattr(s.c, 'read_manifest', lambda path: {})
    monkeypatch.setattr(s.c, 'adopted', adopted)
    monkeypatch.setattr(s.c, 'run_campaign', dispatch)
    monkeypatch.setattr(s, 'collect', lambda *args: {'status': 'complete', 'results': []})
    monkeypatch.setattr(s.subprocess, 'run', lambda *args, **kwargs:
                        SimpleNamespace(returncode=0, stdout=json.dumps({'status': 'passed'})))
    return tmp_path, calls, complete, paths


def test_slow_verification_does_not_starve_first_pending_slot(scheduling):
    root, calls, complete, paths = scheduling
    s.run(root, 'screening')
    assert [path for path, _ in calls] == [paths[1]]
    assert calls[0][1] == {'session_timeout': 1660, 'max_runs': 1}
    assert len(complete) == 2  # Existing result preserved; later slot still bounded.
    assert (paths[1] / 'winner-replay.json').exists()


def test_pause_blocks_dispatch_after_verification(scheduling):
    root, calls, _, _ = scheduling
    (root / 'PAUSE').touch()
    s.run(root, 'screening')
    assert not calls


def test_incomplete_prior_stage_still_blocks_dispatch(scheduling, monkeypatch):
    root, calls, _, _ = scheduling
    monkeypatch.setattr(s, 'collect', lambda *args: {'status': 'incomplete'})
    with pytest.raises(ValueError, match='prior stage incomplete'):
        s.run(root, 'screening')
    assert not calls


def test_changed_replay_still_blocks_dispatch(scheduling):
    root, calls, _, paths = scheduling
    (paths[0] / 'winner-replay.json').write_text('{}')
    with pytest.raises(ValueError):
        s.run(root, 'screening')
    assert not calls


def test_failed_replay_retains_run_and_stops(scheduling, monkeypatch):
    root, calls, complete, paths = scheduling
    monkeypatch.setattr(s.subprocess, 'run', lambda *args, **kwargs:
                        SimpleNamespace(returncode=1, stderr='replay failure'))
    with pytest.raises(ValueError, match='winner replay failed'):
        s.run(root, 'screening')
    assert paths[1] in complete and len(calls) == 1
    assert not (paths[1] / 'winner-replay.json').exists()
