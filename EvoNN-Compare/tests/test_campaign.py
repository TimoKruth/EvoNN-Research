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


@pytest.fixture
def binding():
    """Build declared settings independently of match_config's implementation."""
    spec = c.CampaignSpec(seeds=[42], timeout=600.0)
    identity = {"commit": "a" * 40, "source_sha256": "b" * 64, "versions": c.versions(), "data_files": {}}
    pool_path = "EvoNN-Contenders/src/evonn_contenders/pools.yaml"
    pools = (c.ROOT / pool_path).read_bytes()
    identity["data_files"][pool_path] = c.hashlib.sha256(pools).hexdigest()
    manifest = {"spec": spec.model_dump(mode="json"), "identity": identity, "cache": "/pinned/cache"}
    common = {"git_commit": identity["commit"], "code_dirty": False,
              "dataset_versions": {name: identity["versions"][name] for name in ("numpy", "scipy", "scikit-learn", "pandas", "openml")}}
    native = {**common, "system": "stratograph", "pack": "tier_b_core_v2", "total": 16, "seed": 42,
              "backend": "mlx_native", "epochs": 12, "timeout": 600.0, "fit_timeout": 90.0,
              "population_size": 4, "device": "cpu", "source_sha256": identity["source_sha256"],
              "cache": "/pinned/cache", "shared_root": str(c.ROOT / "shared-benchmarks"), "variant": "shared"}
    contender = {**common, "fit_timeout_seconds": 90.0, "enhanced": False,
                 "pool_sha256": identity["data_files"][pool_path], "pools": c.yaml.safe_load(pools)}
    return manifest, c.Case("tier_b_core_v2", 16, 42), native, contender


@pytest.mark.parametrize("change", [{"timeout": 300.0}, {"variant": "no_hierarchy"}, {"epochs": 6},
    {"fit_timeout": 45.0}, {"backend": "numpy_fallback"}, {"code_dirty": True}])
def test_native_adoption_and_resume_reject_changed_training_settings(binding, change):
    manifest, case, native, _ = binding
    c.match_config(native, manifest, case, "stratograph")
    with pytest.raises(ValueError):
        c.match_config({**native, **change}, manifest, case, "stratograph")


@pytest.mark.parametrize("change", [{"pool_sha256": "0" * 64}, {"pools": {}}, {"enhanced": True}])
def test_contender_adoption_rejects_changed_pool(binding, change):
    manifest, case, _, contender = binding
    c.match_config(contender, manifest, case, "contenders")
    with pytest.raises(ValueError):
        c.match_config({**contender, **change}, manifest, case, "contenders")


def test_adoption_checks_full_export_budget_envelope(binding, tmp_path, monkeypatch):
    from types import SimpleNamespace
    manifest, case, native, _ = binding
    manifest["identity"]["host"] = ["test-host", "Darwin", "arm64", "arm"]
    wrong = c.execution_budget(c.load_parity_pack(case.pack), case.budget, 300.0, "darwin_arm64_cpu")
    exported = SimpleNamespace(system=SimpleNamespace(value="stratograph"),
                               budget=SimpleNamespace(model_dump=lambda **kwargs: wrong))
    directory = tmp_path / "runs" / c.slot_id(case, "stratograph") / "run" / "symbiosis"
    directory.mkdir(parents=True)
    monkeypatch.setattr(c, "read_export", lambda path: SimpleNamespace(manifest=exported))
    monkeypatch.setattr(c, "artifact_json", lambda *args: native)
    with pytest.raises(ValueError, match="budget envelope"):
        c.adopted(tmp_path, manifest, case, "stratograph")


def test_slow_second_preflight_cannot_overrun_session(planned, monkeypatch):
    clock, calls = [0.0], []
    original = c.preflight
    def slow(root):
        result = original(root)
        calls.append(root)
        if len(calls) == 2:
            clock[0] = 60.0
        return result
    monkeypatch.setattr(c, "preflight", slow)
    monkeypatch.setattr(c.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(c, "_bounded_process", lambda *a, **k: pytest.fail("must not dispatch"))
    monkeypatch.setattr(c, "workspace_report", lambda root: {})
    result = c.run_campaign(planned, session_timeout=100)
    assert result["status"] == "paused" and result["new_runs"] == 0
    assert len(calls) == 2
    assert not (planned / "events").exists()


def test_enhanced_policy_is_explicit_and_cannot_adopt_plain_floor(binding):
    manifest,case,_,contender=binding
    manifest['spec']['enhanced']=True
    with pytest.raises(ValueError):c.match_config(contender,manifest,case,'contenders')
    c.match_config({**contender,'enhanced':True},manifest,case,'contenders')
    legacy={**manifest['spec']};legacy.pop('enhanced')
    assert c.CampaignSpec.model_validate(legacy).enhanced is False


def test_enhanced_dispatch_reaches_contender_cli(planned,monkeypatch):
    manifest=c.read_manifest(planned)
    manifest['spec'].update(systems=['contenders'],budgets=[64],enhanced=True)
    manifest['sha256']=c.sha({k:v for k,v in manifest.items() if k!='sha256'})
    (planned/'campaign.json').write_bytes(c.encoded(manifest))
    monkeypatch.setattr(c,'preflight',lambda root:None)
    finished={}
    monkeypatch.setattr(c,'adopted',lambda root,manifest,case,system:(None,finished.get(c.slot_id(case,system))))
    def dispatch(command,*args,**kwargs):
        event=json.loads(Path(command[-2]).read_bytes())
        assert event['details']['command'][-1]=='--enhanced'
        finished[event['slot']]={'system':'contenders','run_id':event['slot'],'export':'fixture','documents':[]}
    monkeypatch.setattr(c,'_bounded_process',dispatch)
    monkeypatch.setattr(c,'workspace_report',lambda root:{})
    assert c.run_campaign(planned,max_runs=1)['new_runs']==1
