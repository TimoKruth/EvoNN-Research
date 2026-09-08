"""Campaign matrix, immutable recovery decisions and real process ownership."""
from copy import deepcopy
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from evonn_compare import campaign as c
from evonn_shared.datasets import load_dataset


@pytest.fixture
def planned(tmp_path, monkeypatch):
    root = tmp_path / "campaign"
    root.mkdir()
    spec = c.CampaignSpec(pack="tier1_core_smoke", budgets=[8], seeds=[42, 43], systems=["prism"], backend="numpy_fallback", timeout=30.0, fit_timeout=5.0, min_free_bytes=0)
    cache = tmp_path / "cache"
    datasets = [load_dataset(name, seed=seed, cache_root=cache).provenance for seed in spec.seeds for name in c.load_parity_pack(spec.pack).benchmarks]
    identity = {"commit": "a" * 40}
    monkeypatch.setattr(c, "identity", lambda: identity)
    value = {"schema_version": "evonn.campaign/v1", "spec": spec.model_dump(mode="json"), "identity": identity,
             "cache": str(cache), "datasets": datasets, "workspace": str(root)}
    c.publish_artifact(root / "campaign.json", c.encoded({**value, "sha256": c.sha(value)}))
    return root


@pytest.mark.parametrize("change", [{"seeds": [42, 42]}, {"budgets": [8, 8]}, {"budgets": [512]},
    {"systems": ["prism", "prism"]}, {"seeds": [True]}, {"backend": "automatic"}, {"timeout": float("inf")}])
def test_invalid_matrix_rejected(change):
    with pytest.raises(ValueError):
        c.CampaignSpec(**change)


def test_preflight_is_read_only_and_rejects_data_and_source_drift(planned, monkeypatch):
    before = {str(p): p.read_bytes() for p in planned.parent.rglob("*") if p.is_file()}
    assert c.preflight(planned)["slots"] == 2
    assert before == {str(p): p.read_bytes() for p in planned.parent.rglob("*") if p.is_file()}
    monkeypatch.setattr(c, "identity", lambda: {"commit": "b" * 40})
    with pytest.raises(ValueError, match="drift"):
        c.preflight(planned)
    monkeypatch.setattr(c, "identity", lambda: {"commit": "a" * 40})
    dataset = c.read_manifest(planned)["datasets"][0]
    path = Path(dataset["cache_directory"]) / dataset["cache_artifacts"][0]["path"]
    path.write_bytes(b"corrupt")
    with pytest.raises(ValueError):
        c.preflight(planned)


def test_resume_adopts_completed_slot_without_relaunch_after_lost_receipt(planned, monkeypatch):
    finished, launched = {}, []
    def adopt(root, manifest, case, system):
        key = c.slot_id(case, system)
        return None, finished[key] if key in finished else None
    def dispatch(command, timeout, log, **kwargs):
        event = json.loads(Path(command[-2]).read_bytes())
        assert c.events(planned, c.read_manifest(planned))[-1] == event
        launched.append(event["slot"])
        finished[event["slot"]] = {"system": "prism", "run_id": event["slot"], "export": "fixture", "documents": []}
    monkeypatch.setattr(c, "adopted", adopt)
    monkeypatch.setattr(c, "_bounded_process", dispatch)
    monkeypatch.setattr(c, "workspace_report", lambda root: {})
    original = c.append_event
    def interrupted(root, manifest, history, slot, kind, details):
        if kind == "complete":
            raise RuntimeError("supervisor died before completion receipt")
        return original(root, manifest, history, slot, kind, details)
    monkeypatch.setattr(c, "append_event", interrupted)
    with pytest.raises(RuntimeError):
        c.run_campaign(planned, max_runs=1)
    assert len(launched) == 1
    monkeypatch.setattr(c, "append_event", original)
    result = c.run_campaign(planned)
    assert result["status"] == "complete" and len(launched) == 2
    assert c.run_campaign(planned)["new_runs"] == 0
    assert len(launched) == 2


def test_insufficient_remaining_time_never_shrinks_or_dispatches(planned, monkeypatch):
    monkeypatch.setattr(c, "_bounded_process", lambda *a, **k: pytest.fail("must not dispatch"))
    monkeypatch.setattr(c, "workspace_report", lambda root: {})
    result = c.run_campaign(planned, session_timeout=10)
    assert result["status"] == "paused" and result["new_runs"] == 0
    assert not (planned / "events").exists()


def test_journal_tampering_duplicates_and_orphan_staging(planned):
    manifest = c.read_manifest(planned)
    history = []
    case, system = c.slots(c.CampaignSpec.model_validate(manifest["spec"]))[0]
    slot = c.slot_id(case, system)
    c.append_event(planned, manifest, history, slot, "dispatch", {"command": ["fixture"]})
    (planned / "events" / (".publish-" + "a" * 32)).write_bytes(b"uncommitted")
    assert c.events(planned, manifest) == history
    bad = deepcopy(history[0])
    bad["details"] = {"command": ["changed"]}
    (planned / "events" / "000001.json").write_bytes(c.encoded(bad))
    with pytest.raises(ValueError, match="journal"):
        c.events(planned, manifest)


def test_inherited_lease_survives_parent_scope_and_fences_second_owner(tmp_path):
    description = tmp_path / "dispatch.json"
    event = {"sha256": "a" * 64, "details": {"command": [sys.executable, "-c", "import time; time.sleep(10)"]}}
    description.write_bytes(c.encoded(event))
    process = None
    try:
        with c.lease(tmp_path) as fd:
            process = subprocess.Popen([sys.executable, "-m", "evonn_compare.campaign_worker", "dispatch", str(description), str(fd)],
                                       pass_fds=(fd,), start_new_session=True)
            deadline = time.monotonic() + 5
            while not description.with_name("dispatch.started.json").exists() and time.monotonic() < deadline:
                time.sleep(.02)
            assert description.with_name("dispatch.started.json").exists()
        with pytest.raises(BlockingIOError):
            with c.lease(tmp_path):
                pytest.fail("live child released campaign lease")
    finally:
        if process is not None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
    with c.lease(tmp_path):
        pass
