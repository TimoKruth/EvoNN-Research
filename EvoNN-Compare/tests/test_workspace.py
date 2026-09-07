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
