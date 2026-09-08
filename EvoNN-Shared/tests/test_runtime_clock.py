"""Interrupted execution never renews the run's elapsed-time budget."""
import pytest

from evonn_shared import runtime_clock as clock


def test_clean_pause_excludes_downtime_but_preserves_work(tmp_path, monkeypatch):
    wall, monotonic = [100.0], [10.0]
    monkeypatch.setattr(clock.time, "time", lambda: wall[0])
    monkeypatch.setattr(clock.time, "monotonic", lambda: monotonic[0])
    first = clock.InvocationClock(tmp_path, 3.0)
    wall[0], monotonic[0] = 110.0, 20.0
    first.finish()
    wall[0], monotonic[0] = 1000.0, 910.0
    second = clock.InvocationClock(tmp_path, 8.0)
    assert second.base == 13.0
    second.finish()


def test_unclean_invocation_charges_through_recovery_once(tmp_path, monkeypatch):
    wall, monotonic = [100.0], [10.0]
    monkeypatch.setattr(clock.time, "time", lambda: wall[0])
    monkeypatch.setattr(clock.time, "monotonic", lambda: monotonic[0])
    clock.InvocationClock(tmp_path, 3.0)
    wall[0], monotonic[0] = 120.0, 30.0
    second = clock.InvocationClock(tmp_path, 8.0)
    assert second.base == 23.0
    second.finish()
    wall[0], monotonic[0] = 150.0, 60.0
    third = clock.InvocationClock(tmp_path, 8.0)
    assert third.base == 23.0


def test_clock_rollback_and_missing_record_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(clock.time, "time", lambda: 100.0)
    clock.InvocationClock(tmp_path, 0.0)
    monkeypatch.setattr(clock.time, "time", lambda: 99.0)
    with pytest.raises(ValueError, match="backwards"):
        clock.InvocationClock(tmp_path, 0.0)

    (tmp_path / "invocation_clock" / "000003_start.json").write_text("{}")
    with pytest.raises(ValueError, match="sequence"):
        clock.InvocationClock(tmp_path, 0.0)


def test_setup_time_and_single_wall_sample_finish(tmp_path, monkeypatch):
    wall = [100.0]
    monkeypatch.setattr(clock.time, "time", lambda: wall[0])
    first = clock.InvocationClock(tmp_path, 1700.0, setup_seconds=120.0)
    assert first.base == 1820.0
    samples = iter([110.0])
    monkeypatch.setattr(clock.time, "time", lambda: next(samples))
    first.finish()


def test_staging_orphan_is_never_authoritative_and_overflow_rejected(tmp_path):
    first = clock.InvocationClock(tmp_path, 0.0)
    first.finish()
    (tmp_path / "invocation_clock" / (".publish-" + "a" * 32)).write_bytes(b"partial")
    clock.InvocationClock(tmp_path, 0.0).finish()
    with pytest.raises(ValueError, match="accounted"):
        clock.InvocationClock(tmp_path, 10**400)
