import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from evonn_compare import workspace
from evonn_compare.dashboard import render_dashboard


def test_cli_orchestration_rebuild_is_read_only_and_accumulation_is_append_only(tmp_path, monkeypatch, export_factory):
    def run(command, **kwargs):
        output = Path(command[command.index("--output") + 1])
        system = command[0].removeprefix("evonn-")
        bundle = export_factory(output / system, system=system, run_id=output.name + "_" + system)
        return SimpleNamespace(returncode=0, stdout=str(bundle.root) + "\n", stderr="")
    monkeypatch.setattr(workspace.subprocess, "run", run)
    root = tmp_path / "workspace"
    first = workspace.fair_matrix(workspace=root, systems=["contenders", "prism"])
    assert first["cases"][0]["acceptance"]["operating_state"] == "contract-fair"
    trend = root / "trends/fair_matrix_trend_rows.jsonl"
    original = trend.read_bytes()
    source_hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (root / "runs").rglob("*") if p.is_file()}
    monkeypatch.setattr(workspace.subprocess, "run", lambda *a, **k: pytest.fail("rebuild must not run a system"))
    workspace.workspace_report(root)
    assert trend.read_bytes() == original
    assert source_hashes == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in (root / "runs").rglob("*") if p.is_file()}
    monkeypatch.setattr(workspace.subprocess, "run", run)
    second = workspace.fair_matrix(workspace=root, systems=["contenders", "prism"])
    assert len(second["cases"]) == 2 and trend.read_bytes().startswith(original)
    assert len(trend.read_bytes()) > len(original)
    artifact = next((root / "runs").rglob("report.md"))
    artifact.write_text("tampered")
    rebuilt = workspace.workspace_report(root)
    assert any(case["acceptance"]["blockers"] for case in rebuilt["cases"])
    assert any(item["level"] == "L0" and item["run_id"] is not None for item in rebuilt["output_quality"])
    assert any(case["failures"] for case in rebuilt["cases"])


def test_interrupted_jsonl_final_record_is_rejected_without_repair(tmp_path):
    (tmp_path / "trends").mkdir()
    path = tmp_path / "trends/fair_matrix_trend_rows.jsonl"
    original = b'{"case_id":"a","run_id":"r","benchmark":"b","outcome_id":"o"}'
    path.write_bytes(original)
    with pytest.raises(ValueError, match="incomplete final record"):
        workspace._append_rows(tmp_path, [{"case_id": "next", "run_id": "r", "benchmark": "b", "outcome_id": "o"}])
    assert path.read_bytes() == original


def test_dashboard_payload_cannot_escape_script_element():
    html = render_dashboard({"rows": [], "untrusted": '</script><script>alert("x")</script>'})
    assert '</script><script>alert(' not in html
    payload = html.split('id="data">', 1)[1].split('</script>', 1)[0]
    assert json.loads(payload)["untrusted"].startswith('</script>')


def test_reset_archives_evidence_and_starts_fresh(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    root.mkdir()
    original = root / "evidence.txt"
    original.write_text("preserve these bytes")
    monkeypatch.setattr(workspace.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("unimplemented fixture engine")))
    result = workspace.fair_matrix(workspace=root, systems=["prism"], no_contenders=True, reset_workspace=True)
    archives = list(tmp_path.glob("workspace.previous_*"))
    assert len(archives) == 1
    assert (archives[0] / "evidence.txt").read_text() == "preserve these bytes"
    assert not original.exists() and len(result["cases"]) == 1
    assert result["cases"][0]["acceptance"]["operating_state"] == "exploratory"


@pytest.mark.parametrize("internal", [True, False])
def test_reset_preserves_cache_provenance_or_rejects_before_archive(tmp_path, monkeypatch, export_factory, internal):
    root = tmp_path / "workspace"
    cache = (root / "arbitrary-data-location" if internal else tmp_path / "workspace.cache")
    cache.mkdir(parents=True)
    cached = cache / "checked.npy"
    cached.write_bytes(b"checked fixture bytes")
    bundle = export_factory(root / "runs" / "fixture" / "symbiosis")
    payload = json.dumps([{"cache_directory": str(cache)}]).encode()
    (bundle.root / "dataset_provenance.json").write_bytes(payload)
    (bundle.root.parent / "dataset_provenance.json").write_bytes(payload)
    reference = {"path": "dataset_provenance.json", "sha256": hashlib.sha256(payload).hexdigest()}
    for name, key in (("manifest", "artifacts"), ("summary", "artifact_digests")):
        path = bundle.root / (name + ".json")
        document = json.loads(path.read_text())
        document[key].append(reference)
        document[key].sort(key=lambda item: item["path"])
        path.write_text(json.dumps(document))
    original = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    monkeypatch.setattr(workspace.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("fixture")))
    if internal:
        with pytest.raises(ValueError, match="internal cache"):
            workspace.fair_matrix(workspace=root, reset_workspace=True)
        assert not list(tmp_path.glob("workspace.previous_*"))
        assert all((root / path).read_bytes() == payload for path, payload in original.items())
    else:
        workspace.fair_matrix(workspace=root, reset_workspace=True)
        archive, = tmp_path.glob("workspace.previous_*")
        assert all((archive / path).read_bytes() == payload for path, payload in original.items())
    assert cached.read_bytes() == b"checked fixture bytes"


def test_audit_cli_uses_one_locked_case_snapshot(tmp_path, monkeypatch, export_factory, capsys):
    from evonn_compare.cli import main
    def run(command, **kwargs):
        output = Path(command[command.index("--output") + 1])
        bundle = export_factory(output / "contenders", run_id=output.name + "_contenders")
        return SimpleNamespace(returncode=0, stdout=str(bundle.root) + "\n", stderr="")
    monkeypatch.setattr(workspace.subprocess, "run", run)
    root = tmp_path / "workspace"
    workspace.fair_matrix(workspace=root)
    original_load, original_audit = workspace.load_cases, workspace.benchmark_audit
    calls = []
    def load(owned):
        calls.append(owned)
        assert len(calls) == 1, "audit must not reload a second case snapshot"
        return original_load(owned)
    def audit(*args, **kwargs):
        with pytest.raises(BlockingIOError):
            with workspace.ownership(root):
                pytest.fail("audit released its workspace lock")
        assert len(kwargs["output_levels"]) == len(args[1]) == 1
        assert kwargs["dashboard_present"]
        return original_audit(*args, **kwargs)
    monkeypatch.setattr(workspace, "load_cases", load)
    monkeypatch.setattr(workspace, "benchmark_audit", audit)
    assert main(["benchmark-audit", "--pack", "tier1_core", "--workspace", str(root)]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "blocked"  # Synthetic fixture is never runtime proof.
    assert len(calls) == 1
