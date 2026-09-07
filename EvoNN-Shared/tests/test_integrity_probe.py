"""End-to-end probe generation and fail-closed report checks."""

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

_SPEC = importlib.util.spec_from_file_location("integrity_probe_test_helper", Path(__file__).with_name("integrity_probe.py"))
assert _SPEC and _SPEC.loader
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


@pytest.fixture(scope="module")
def evidence(tmp_path_factory):
    root = tmp_path_factory.mktemp("integrity_probe")
    output = root / "report.json"
    result = subprocess.run(
        [sys.executable, str(Path(probe.__file__)), "--work-root", str(root / "runs"), "--output", str(output)],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "not Phase-0 acceptance" in result.stdout
    return json.loads(output.read_bytes())


def test_probe_covers_real_failure_and_invalid_crashes_on_all_boundaries(evidence):
    probe.validate_report(evidence)
    assert len(evidence["cases"]) == 8
    assert evidence["evidence_class"] == "synthetic_contract_preparation"
    assert evidence["host"]["platform"] == sys.platform


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "rows", "checkpoint", "recharge", "source", "trace", "class"])
def test_report_validation_rejects_missing_or_contradictory_evidence(evidence, mutation):
    report = copy.deepcopy(evidence)
    if mutation == "missing":
        report["cases"].pop()
    elif mutation == "duplicate":
        report["cases"][0] = report["cases"][1]
    elif mutation == "class":
        report["evidence_class"] = "decision_grade_scientific"
    else:
        case = report["cases"][0]
        if mutation == "rows":
            case["rows_sha256"] = "0" * 64
        elif mutation == "checkpoint":
            case["checkpoint_sha256"] = "0" * 64
        elif mutation == "recharge":
            case["accounting"]["actual_evaluations"] += 1
        elif mutation == "source":
            case["source_after"] = "0" * 64
        else:
            case["resumed_trace"].append("evaluate:0")
    with pytest.raises(ValueError):
        probe.validate_report(report)


def test_probe_never_reuses_existing_work_root_or_output(tmp_path):
    work_root = tmp_path / "existing"
    work_root.mkdir()
    marker = work_root / "keep"
    marker.write_text("existing evidence")
    with pytest.raises(FileExistsError):
        probe.generate(work_root, tmp_path / "output.json")
    assert marker.read_text() == "existing evidence"
    assert not (tmp_path / "output.json").exists()
    with pytest.raises(ValueError, match="outside"):
        probe.generate(tmp_path / "fresh", tmp_path / "fresh" / "report.json")
    assert not (tmp_path / "fresh").exists()


def test_failed_child_produces_no_final_report(tmp_path, monkeypatch):
    monkeypatch.setattr(probe, "invoke", lambda *args: subprocess.CompletedProcess([], 1, "", "injected failure"))
    with pytest.raises(ValueError, match="baseline failed"):
        probe.generate(tmp_path / "runs", tmp_path / "report.json")
    assert not (tmp_path / "report.json").exists()


def test_validate_cli_is_read_only_and_rejects_invalid_reports(tmp_path, evidence):
    report = tmp_path / "report.json"
    report.write_text(json.dumps(evidence))
    before = report.read_bytes()
    result = subprocess.run([sys.executable, str(Path(probe.__file__)), "--validate", str(report)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert report.read_bytes() == before
    report.write_text('{}')
    result = subprocess.run([sys.executable, str(Path(probe.__file__)), "--validate", str(report)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 1
