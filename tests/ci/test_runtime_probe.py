from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

from evonn_shared.backend_contract import PACKAGE_BY_SYSTEM

REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_PATH = REPO_ROOT / "scripts/ci/runtime_probe.py"
sys.path.insert(0, str(REPO_ROOT))
MANIFEST = Path(PACKAGE_BY_SYSTEM["prism"].manifest_path)
TIMESTAMPS = ("2026-07-18T12:00:00Z", "2026-07-18T12:00:01Z")
RUNTIME = {
    "os_name": "Darwin",
    "os_version": "25.5.0",
    "kernel": "Darwin 25.5.0",
    "architecture": "arm64",
    "logical_cpu_count": 10,
    "python_implementation": "CPython",
    "python_version": "3.13.5",
}


def _probe_module():
    assert PROBE_PATH.is_file(), "runtime probe implementation is missing"
    from scripts.ci import runtime_probe

    return runtime_probe


def _write_probe(tmp_path: Path, **overrides: object) -> Path:
    output = tmp_path / "b0-runtime-probe.json"
    moments = iter(TIMESTAMPS)
    arguments: dict[str, object] = {
        "output_path": output,
        "repo_root": REPO_ROOT,
        "backend": "numpy",
        "system": "prism",
        "manifest_path": MANIFEST,
        "execution_mode": "local",
        "environment": {},
        "clock": lambda: next(moments),
        "runtime": RUNTIME,
        "uv_version": "0.5.13",
        "repository_commit": "a" * 40,
        "hostname": "secret-hostname",
        "operation_executor": lambda backend: {
            "operation": "sum_of_squares",
            "input": [1.0, 2.0, 3.0],
            "expected": 14.0,
            "actual": 14.0,
            "validated": True,
        },
        "backend_version": "2.3.1",
    }
    arguments.update(overrides)
    _probe_module().write_runtime_probe(**arguments)
    return output


def _validate(path: Path, **overrides: object) -> list[str]:
    arguments: dict[str, object] = {
        "probe_path": path,
        "repo_root": REPO_ROOT,
        "execution_mode": "local",
        "expected_backend": "numpy",
        "runtime": RUNTIME,
        "uv_version": "0.5.13",
        "backend_version": "2.3.1",
        "hostname": "secret-hostname",
        "environment": {},
        "repository_commit": "a" * 40,
    }
    arguments.update(overrides)
    return _probe_module().validate_runtime_probe(**arguments)


def test_uv_version_parser_accepts_pinned_uv_build_metadata() -> None:
    assert _probe_module().parse_uv_version("uv 0.5.13 (c456bae5e 2024-12-27)") == "0.5.13"
    with pytest.raises(ValueError, match="unexpected uv version output"):
        _probe_module().parse_uv_version("not-uv 0.5.13")


def test_all_declared_workspace_packages_are_imported_and_version_validated() -> None:
    validated = _probe_module().validate_installed_packages()

    assert len(validated) == 7
    assert all(entry["version"] == "0.0.0" for entry in validated)
    assert {entry["system"] for entry in validated} == {
        "shared",
        "compare",
        "contenders",
        "prism",
        "topograph",
        "stratograph",
        "primordia",
    }


def test_probe_write_is_deterministic_complete_atomic_and_hostname_safe(tmp_path: Path) -> None:
    path = _write_probe(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))

    assert list(data) == sorted(data)
    assert data["schema_version"] == "1.0.0"
    assert data["probe_kind"] == "b0_runtime_backend_bootstrap"
    assert data["repository_commit"] == "a" * 40
    assert data["workflow"] == {"name": "local", "run_id": "local", "attempt": "local"}
    assert data["timestamps"] == {"started_at_utc": TIMESTAMPS[0], "ended_at_utc": TIMESTAMPS[1]}
    assert data["status"] == "passed"
    assert data["host"]["architecture"] == "arm64"
    assert data["host"]["logical_cpu_count"] == 10
    assert data["python"] == {"implementation": "CPython", "version": "3.13.5"}
    assert data["uv_version"] == "0.5.13"
    assert data["package_under_test"] == "evonn-prism"
    assert data["system_under_test"] == "prism"
    assert data["backend"] == {"class": "numpy_fallback", "distribution": "numpy", "version": "2.3.1"}
    assert data["device_class"] == "cpu"
    assert data["precision_mode"] == "float64"
    assert data["workers"] == {"topology": "single_process", "count": 1}
    assert {entry["distribution"] for entry in data["packages_validated"]} == {
        "evonn-shared",
        "evonn-compare",
        "evonn-contenders",
        "evonn-prism",
        "evonn-topograph",
        "evonn-stratograph",
        "evonn-primordia",
    }
    assert data["host_fingerprint"]["algorithm"] == "sha256"
    assert data["host_fingerprint"]["digest"] == hashlib.sha256(
        b"secret-hostname\x00Darwin\x00arm64"
    ).hexdigest()
    assert "secret-hostname" not in path.read_text(encoding="utf-8")
    assert data["manifest"]["path"] == MANIFEST.as_posix()
    assert data["qualification"] == "bootstrap_probe_only"
    assert data["evidence"]["class"] == "contract"
    assert "not scientific or backend qualification" in data["evidence"]["statement"].lower()
    assert data["operation"]["validated"] is True
    assert _validate(path) == []
    assert not list(tmp_path.glob(".*.tmp"))


def test_timestamps_bracket_backend_execution_in_clock_order(tmp_path: Path) -> None:
    events: list[str] = []
    moments = iter(TIMESTAMPS)

    def clock() -> str:
        value = next(moments)
        events.append(f"clock:{value}")
        return value

    def operation(backend: str) -> dict[str, object]:
        events.append(f"operation:{backend}")
        return {
            "operation": "sum_of_squares",
            "input": [1.0, 2.0, 3.0],
            "expected": 14.0,
            "actual": 14.0,
            "validated": True,
        }

    _write_probe(tmp_path, clock=clock, operation_executor=operation)

    assert events == [f"clock:{TIMESTAMPS[0]}", "operation:numpy", f"clock:{TIMESTAMPS[1]}"]


def test_validator_rejects_manifest_digest_mismatch(tmp_path: Path) -> None:
    path = _write_probe(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["manifest"]["sha256"] = "0" * 64
    path.write_text(json.dumps(data), encoding="utf-8")

    assert any("manifest digest" in diagnostic for diagnostic in _validate(path))


def test_validator_rejects_fake_hosted_metadata_in_local_mode(tmp_path: Path) -> None:
    path = _write_probe(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["workflow"] = {"name": "B0 Linux trust lane", "run_id": "123456", "attempt": "1"}
    path.write_text(json.dumps(data), encoding="utf-8")

    assert any("workflow metadata" in diagnostic for diagnostic in _validate(path))


def test_hosted_validation_binds_commit_and_workflow_to_current_environment(tmp_path: Path) -> None:
    generated_environment = {
        "GITHUB_SHA": "b" * 40,
        "GITHUB_WORKFLOW": "B0 Linux trust lane",
        "GITHUB_RUN_ID": "12345",
        "GITHUB_RUN_ATTEMPT": "2",
    }
    path = _write_probe(
        tmp_path,
        execution_mode="hosted",
        environment=generated_environment,
        repository_commit="b" * 40,
    )
    mismatched_environment = dict(generated_environment)
    mismatched_environment["GITHUB_SHA"] = "c" * 40
    mismatched_environment["GITHUB_RUN_ID"] = "99999"

    diagnostics = _validate(
        path,
        execution_mode="hosted",
        expected_backend="numpy",
        environment=mismatched_environment,
        repository_commit=None,
    )

    assert any("repository commit" in diagnostic for diagnostic in diagnostics)
    assert any("workflow metadata" in diagnostic for diagnostic in diagnostics)


def test_validator_rejects_host_runtime_and_backend_platform_mismatch(tmp_path: Path) -> None:
    path = _write_probe(tmp_path, backend="mlx", backend_version="0.29.0")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["host"]["architecture"] = "x86_64"
    path.write_text(json.dumps(data), encoding="utf-8")
    wrong_runtime = dict(RUNTIME)
    wrong_runtime["architecture"] = "x86_64"

    diagnostics = _validate(
        path,
        expected_backend="mlx",
        runtime=wrong_runtime,
        backend_version="0.29.0",
    )

    assert any("MLX backend requires Darwin arm64" in diagnostic for diagnostic in diagnostics)


def test_validator_rejects_nonpositive_workers_and_unproved_result(tmp_path: Path) -> None:
    path = _write_probe(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["workers"]["count"] = 0
    data["operation"]["validated"] = False
    data["operation"]["actual"] = 13.0
    path.write_text(json.dumps(data), encoding="utf-8")

    diagnostics = _validate(path)

    assert any("worker count" in diagnostic for diagnostic in diagnostics)
    assert any("operation result" in diagnostic for diagnostic in diagnostics)


@pytest.mark.parametrize("invalid_count", [0, -1, True, False])
def test_validator_rejects_invalid_or_boolean_worker_counts(tmp_path: Path, invalid_count: object) -> None:
    path = _write_probe(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["workers"]["count"] = invalid_count
    path.write_text(json.dumps(data), encoding="utf-8")

    assert any("worker count" in diagnostic for diagnostic in _validate(path))


def test_validator_reports_malformed_system_without_crashing(tmp_path: Path) -> None:
    path = _write_probe(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["system_under_test"] = []
    path.write_text(json.dumps(data), encoding="utf-8")

    assert any("system under test" in diagnostic for diagnostic in _validate(path))


def test_generation_rejects_copied_noncanonical_manifest_for_system(tmp_path: Path) -> None:
    copied = REPO_ROOT / ".runtime-probe-test-copy.json"
    shutil.copy2(REPO_ROOT / MANIFEST, copied)
    try:
        with pytest.raises(ValueError, match="exact canonical manifest"):
            _write_probe(tmp_path, manifest_path=Path(copied.name))
    finally:
        copied.unlink(missing_ok=True)


def test_validation_rejects_copied_noncanonical_manifest_with_matching_digest(tmp_path: Path) -> None:
    path = _write_probe(tmp_path)
    copied = REPO_ROOT / ".runtime-probe-test-copy.json"
    shutil.copy2(REPO_ROOT / MANIFEST, copied)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["manifest"] = {
            "path": copied.name,
            "sha256": hashlib.sha256(copied.read_bytes()).hexdigest(),
        }
        path.write_text(json.dumps(data), encoding="utf-8")

        diagnostics = _validate(path)

        assert any("exact canonical manifest" in diagnostic for diagnostic in diagnostics)
    finally:
        copied.unlink(missing_ok=True)


def test_manifest_path_rejects_symlink_even_when_target_is_canonical(tmp_path: Path) -> None:
    link = REPO_ROOT / ".runtime-probe-test-link.json"
    link.symlink_to(REPO_ROOT / MANIFEST)
    try:
        with pytest.raises(ValueError, match="symbolic link"):
            _write_probe(tmp_path, manifest_path=Path(link.name))
    finally:
        link.unlink(missing_ok=True)


def test_manifest_path_cannot_escape_repository_through_symlink(tmp_path: Path) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    link = REPO_ROOT / ".runtime-probe-test-escape.json"
    link.symlink_to(outside)
    output = tmp_path / "b0-runtime-probe.json"
    try:
        with pytest.raises(ValueError, match="symbolic link"):
            _write_probe(tmp_path, manifest_path=Path(link.name), output_path=output)
        assert not output.exists()
    finally:
        link.unlink(missing_ok=True)


def test_failed_operation_removes_stale_passed_artifact(tmp_path: Path) -> None:
    output = tmp_path / "b0-runtime-probe.json"
    output.write_text('{"status":"passed"}\n', encoding="utf-8")

    def fail_operation(backend: str) -> dict[str, object]:
        raise RuntimeError(f"{backend} failed")

    with pytest.raises(RuntimeError, match="numpy failed"):
        _write_probe(tmp_path, output_path=output, operation_executor=fail_operation)

    assert not output.exists()
