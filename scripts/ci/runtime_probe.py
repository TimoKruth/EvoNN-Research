#!/usr/bin/env python3
"""Generate and validate B0 backend bootstrap runtime evidence."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
from typing import Any

from evonn_shared.backend_contract import (
    ENGINE_CONTRACTS,
    MLX_CAPABILITY,
    NUMPY_CAPABILITY,
    PACKAGE_BY_SYSTEM,
    PACKAGE_CONTRACTS,
)

SCHEMA_VERSION = "1.0.0"
PROBE_KIND = "b0_runtime_backend_bootstrap"
QUALIFICATION = "bootstrap_probe_only"
EVIDENCE_STATEMENT = "Bootstrap portability/runtime contract evidence only; not scientific or backend qualification."
SYSTEM_PACKAGES = {engine.system: engine.distribution for engine in ENGINE_CONTRACTS}
BACKENDS = {
    "numpy": {
        "class": NUMPY_CAPABILITY["id"],
        "distribution": NUMPY_CAPABILITY["dependency"],
        "device_class": "cpu",
        "precision_mode": "float64",
        "platforms": tuple(NUMPY_CAPABILITY["platforms"]),
    },
    "mlx": {
        "class": MLX_CAPABILITY["id"],
        "distribution": MLX_CAPABILITY["dependency"],
        "device_class": "apple_silicon_mlx_default",
        "precision_mode": "float32",
        "platforms": tuple(MLX_CAPABILITY["platforms"]),
    },
}
UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
HEX_COMMIT = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_OPERATION = {
    "operation": "sum_of_squares",
    "input": [1.0, 2.0, 3.0],
    "expected": 14.0,
    "actual": 14.0,
    "validated": True,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _runtime_snapshot() -> dict[str, Any]:
    mac_version = platform.mac_ver()[0]
    os_version = mac_version if mac_version else platform.platform()
    return {
        "os_name": platform.system(),
        "os_version": os_version,
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "logical_cpu_count": os.cpu_count() or 1,
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
    }


def parse_uv_version(output: str) -> str:
    """Extract the semantic version from uv's optional build-metadata output."""
    fields = output.strip().split()
    if len(fields) < 2 or fields[0] != "uv":
        raise ValueError(f"unexpected uv version output: {output!r}")
    return fields[1]


def _uv_version() -> str:
    output = subprocess.check_output(["uv", "--version"], text=True)
    return parse_uv_version(output)


def _repository_commit(repo_root: Path, environment: Mapping[str, str], execution_mode: str) -> str:
    if execution_mode == "hosted":
        if "GITHUB_SHA" not in environment:
            raise ValueError("hosted execution requires GITHUB_SHA")
        return environment["GITHUB_SHA"].lower()
    return subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        text=True,
    ).strip().lower()


def _workflow_metadata(environment: Mapping[str, str], execution_mode: str) -> dict[str, str]:
    if execution_mode == "local":
        return {"name": "local", "run_id": "local", "attempt": "local"}
    required = ("GITHUB_WORKFLOW", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")
    missing = [name for name in required if name not in environment or not environment[name]]
    if missing:
        raise ValueError(f"hosted execution is missing workflow metadata: {missing}")
    return {
        "name": environment["GITHUB_WORKFLOW"],
        "run_id": environment["GITHUB_RUN_ID"],
        "attempt": environment["GITHUB_RUN_ATTEMPT"],
    }


def _safe_manifest(repo_root: Path, manifest_path: Path) -> tuple[Path, str]:
    if manifest_path.is_absolute():
        raise ValueError("manifest path must be repository-relative")
    root = repo_root.resolve()
    current = root
    for part in manifest_path.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("manifest path must not contain a symbolic link")
    resolved = (root / manifest_path).resolve(strict=True)
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("manifest path must remain within the repository root") from exc
    if not resolved.is_file():
        raise ValueError("manifest path must identify a regular file")
    return resolved, relative.as_posix()


def _system_manifest(repo_root: Path, system: str, manifest_path: Path) -> tuple[Path, str]:
    expected_path = PACKAGE_BY_SYSTEM[system].manifest_path
    manifest_file, manifest_relative = _safe_manifest(repo_root, manifest_path)
    if manifest_path.as_posix() != expected_path or manifest_relative != expected_path:
        raise ValueError(f"{system} requires exact canonical manifest {expected_path}")
    return manifest_file, manifest_relative


def _manifest_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _host_fingerprint(hostname: str, runtime: Mapping[str, Any]) -> str:
    material = "\x00".join((hostname, runtime["os_name"], runtime["architecture"]))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def validate_installed_packages() -> list[dict[str, str]]:
    """Import every declared package and verify distribution/module identity."""
    import evonn_compare
    import evonn_contenders
    import evonn_primordia
    import evonn_shared
    import prism
    import stratograph
    import topograph

    modules = {
        "evonn-shared": evonn_shared,
        "evonn-compare": evonn_compare,
        "evonn-contenders": evonn_contenders,
        "evonn-prism": prism,
        "evonn-topograph": topograph,
        "evonn-stratograph": stratograph,
        "evonn-primordia": evonn_primordia,
    }
    validated: list[dict[str, str]] = []
    for package in PACKAGE_CONTRACTS:
        module = modules[package.distribution]
        installed_version = version(package.distribution)
        if module.__version__ != installed_version:
            raise RuntimeError(
                f"{package.distribution} module version {module.__version__!r} does not match installed {installed_version!r}"
            )
        if module.SYSTEM != package.system:
            raise RuntimeError(
                f"{package.distribution} module system {module.SYSTEM!r} does not match {package.system!r}"
            )
        validated.append(
            {
                "distribution": package.distribution,
                "module": package.module,
                "system": package.system,
                "version": installed_version,
            }
        )
    return validated


def _run_numpy_operation() -> dict[str, Any]:
    import numpy as np

    values = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    actual = float(np.dot(values, values))
    expected = 14.0
    if actual != expected:
        raise RuntimeError(f"NumPy sum-of-squares mismatch: expected {expected}, found {actual}")
    return {
        "operation": "sum_of_squares",
        "input": [1.0, 2.0, 3.0],
        "expected": expected,
        "actual": actual,
        "validated": True,
    }


def _run_mlx_operation() -> dict[str, Any]:
    import mlx.core as mx

    values = mx.array([1.0, 2.0, 3.0], dtype=mx.float32)
    result = mx.sum(values * values)
    mx.eval(result)
    actual = float(result.item())
    expected = 14.0
    if actual != expected:
        raise RuntimeError(f"MLX sum-of-squares mismatch: expected {expected}, found {actual}")
    return {
        "operation": "sum_of_squares",
        "input": [1.0, 2.0, 3.0],
        "expected": expected,
        "actual": actual,
        "validated": True,
    }


def _execute_operation(backend: str) -> dict[str, Any]:
    if backend == "numpy":
        return _run_numpy_operation()
    if backend == "mlx":
        return _run_mlx_operation()
    raise ValueError(f"unsupported backend: {backend}")


def _backend_capability(manifest: Mapping[str, Any], backend_class: str) -> Mapping[str, Any]:
    try:
        capabilities = manifest["capabilities"]
    except KeyError as exc:
        raise ValueError("manifest is missing capabilities") from exc
    if not isinstance(capabilities, list):
        raise ValueError("manifest capabilities must be a list")
    for capability in capabilities:
        if isinstance(capability, Mapping) and "id" in capability and capability["id"] == backend_class:
            return capability
    raise ValueError(f"manifest does not declare backend capability {backend_class}")


def _atomic_write_json(output_path: Path, document: Mapping[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_name = stream.name
            json.dump(document, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, output_path)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def write_runtime_probe(
    output_path: Path,
    repo_root: Path,
    backend: str,
    system: str,
    manifest_path: Path,
    execution_mode: str,
    *,
    environment: Mapping[str, str] | None = None,
    clock: Callable[[], str] | None = None,
    runtime: Mapping[str, Any] | None = None,
    uv_version: str | None = None,
    repository_commit: str | None = None,
    hostname: str | None = None,
    operation_executor: Callable[[str], dict[str, Any]] | None = None,
    backend_version: str | None = None,
) -> dict[str, Any]:
    """Execute a backend operation and atomically write passed bootstrap evidence."""
    output_path.unlink(missing_ok=True)
    if backend not in BACKENDS:
        raise ValueError(f"unsupported backend: {backend}")
    if system not in SYSTEM_PACKAGES:
        raise ValueError(f"unsupported engine system: {system}")
    if execution_mode not in {"local", "hosted"}:
        raise ValueError("execution mode must be local or hosted")

    manifest_file, manifest_relative = _system_manifest(repo_root, system, manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if not isinstance(manifest, Mapping):
        raise ValueError("backend capability manifest must be an object")
    if "system" not in manifest or manifest["system"] != system:
        raise ValueError(f"manifest system must be {system}")
    backend_contract = BACKENDS[backend]
    capability = _backend_capability(manifest, str(backend_contract["class"]))
    if "implemented" not in capability or capability["implemented"] is not False:
        raise ValueError("B0 backend capability must remain unimplemented")

    selected_environment = os.environ if environment is None else environment
    selected_runtime = _runtime_snapshot() if runtime is None else dict(runtime)
    selected_clock = _utc_now if clock is None else clock
    selected_uv_version = _uv_version() if uv_version is None else uv_version
    selected_commit = (
        _repository_commit(repo_root.resolve(), selected_environment, execution_mode)
        if repository_commit is None
        else repository_commit.lower()
    )
    selected_hostname = platform.node() if hostname is None else hostname
    executor = _execute_operation if operation_executor is None else operation_executor
    distribution = str(backend_contract["distribution"])
    selected_backend_version = version(distribution) if backend_version is None else backend_version
    packages_validated = validate_installed_packages()
    started_at = selected_clock()
    operation = executor(backend)
    if operation != EXPECTED_OPERATION:
        raise RuntimeError("backend operation did not prove the required numerical execution")
    ended_at = selected_clock()
    document: dict[str, Any] = {
        "backend": {
            "class": backend_contract["class"],
            "distribution": distribution,
            "version": selected_backend_version,
        },
        "device_class": backend_contract["device_class"],
        "evidence": {"class": "contract", "statement": EVIDENCE_STATEMENT},
        "host": {
            "architecture": selected_runtime["architecture"],
            "kernel": selected_runtime["kernel"],
            "logical_cpu_count": selected_runtime["logical_cpu_count"],
            "os_name": selected_runtime["os_name"],
            "os_version": selected_runtime["os_version"],
        },
        "host_fingerprint": {
            "algorithm": "sha256",
            "digest": _host_fingerprint(selected_hostname, selected_runtime),
        },
        "manifest": {"path": manifest_relative, "sha256": _manifest_digest(manifest_file)},
        "operation": operation,
        "package_under_test": SYSTEM_PACKAGES[system],
        "packages_validated": packages_validated,
        "precision_mode": backend_contract["precision_mode"],
        "probe_kind": PROBE_KIND,
        "python": {
            "implementation": selected_runtime["python_implementation"],
            "version": selected_runtime["python_version"],
        },
        "qualification": QUALIFICATION,
        "repository_commit": selected_commit,
        "schema_version": SCHEMA_VERSION,
        "status": "passed",
        "system_under_test": system,
        "timestamps": {
            "ended_at_utc": ended_at,
            "started_at_utc": started_at,
        },
        "uv_version": selected_uv_version,
        "workers": {"count": 1, "topology": "single_process"},
        "workflow": _workflow_metadata(selected_environment, execution_mode),
    }
    _atomic_write_json(output_path, document)
    return document


def _load_probe(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, [f"cannot load runtime probe: {exc}"]
    if not isinstance(document, dict):
        return None, ["runtime probe must be a JSON object"]
    return document, []


def validate_runtime_probe(
    probe_path: Path,
    repo_root: Path,
    execution_mode: str,
    expected_backend: str | None = None,
    *,
    runtime: Mapping[str, Any] | None = None,
    uv_version: str | None = None,
    backend_version: str | None = None,
    hostname: str | None = None,
    environment: Mapping[str, str] | None = None,
    repository_commit: str | None = None,
) -> list[str]:
    """Validate a probe against the current host, runtime, manifest, and execution mode."""
    document, diagnostics = _load_probe(probe_path)
    if document is None:
        return diagnostics
    required = {
        "backend",
        "device_class",
        "evidence",
        "host",
        "host_fingerprint",
        "manifest",
        "operation",
        "package_under_test",
        "packages_validated",
        "precision_mode",
        "probe_kind",
        "python",
        "qualification",
        "repository_commit",
        "schema_version",
        "status",
        "system_under_test",
        "timestamps",
        "uv_version",
        "workers",
        "workflow",
    }
    missing = sorted(required - set(document), key=lambda item: item.encode("utf-8"))
    if missing:
        diagnostics.append(f"runtime probe is missing required fields: {missing}")
        return diagnostics

    selected_runtime = _runtime_snapshot() if runtime is None else dict(runtime)
    selected_uv_version = _uv_version() if uv_version is None else uv_version
    selected_hostname = platform.node() if hostname is None else hostname
    selected_environment = os.environ if environment is None else environment
    expected_commit = (
        _repository_commit(repo_root.resolve(), selected_environment, execution_mode)
        if repository_commit is None
        else repository_commit.lower()
    )
    accepted_commits = {expected_commit}
    if repository_commit is None and execution_mode == "local":
        # The two-commit evidence discipline generates local probes at the
        # implementation commit and validates them from its evidence-only
        # child, so local validation also accepts HEAD's first parent.
        try:
            parent = (
                subprocess.check_output(
                    ["git", "-C", str(repo_root.resolve()), "rev-parse", "HEAD^"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                )
                .strip()
                .lower()
            )
        except subprocess.CalledProcessError:
            parent = ""
        if HEX_COMMIT.fullmatch(parent):
            accepted_commits.add(parent)
    if document["schema_version"] != SCHEMA_VERSION:
        diagnostics.append("schema version is incorrect")
    if document["probe_kind"] != PROBE_KIND:
        diagnostics.append("probe kind is incorrect")
    if document["qualification"] != QUALIFICATION:
        diagnostics.append("qualification must be bootstrap_probe_only")
    if document["status"] != "passed":
        diagnostics.append("runtime probe status must be passed")
    commit = document["repository_commit"]
    if not isinstance(commit, str) or not HEX_COMMIT.fullmatch(commit):
        diagnostics.append("repository commit must be a full lowercase Git object ID")
    elif commit not in accepted_commits:
        diagnostics.append(f"repository commit does not match the executing checkout: expected {expected_commit}")

    host = document["host"]
    expected_host = {
        "architecture": selected_runtime["architecture"],
        "kernel": selected_runtime["kernel"],
        "logical_cpu_count": selected_runtime["logical_cpu_count"],
        "os_name": selected_runtime["os_name"],
        "os_version": selected_runtime["os_version"],
    }
    if host != expected_host:
        diagnostics.append(f"host fields do not match the executing host: expected {expected_host!r}")
    expected_python = {
        "implementation": selected_runtime["python_implementation"],
        "version": selected_runtime["python_version"],
    }
    if document["python"] != expected_python:
        diagnostics.append(f"Python runtime fields do not match: expected {expected_python!r}")
    if document["uv_version"] != selected_uv_version:
        diagnostics.append(f"uv version does not match the executing environment: expected {selected_uv_version}")

    workflow = document["workflow"]
    try:
        expected_workflow = _workflow_metadata(selected_environment, execution_mode)
    except ValueError as exc:
        diagnostics.append(f"cannot establish expected workflow metadata: {exc}")
    else:
        if workflow != expected_workflow:
            diagnostics.append(f"workflow metadata does not match the executing context: expected {expected_workflow!r}")

    timestamps = document["timestamps"]
    if not isinstance(timestamps, dict) or set(timestamps) != {"started_at_utc", "ended_at_utc"}:
        diagnostics.append("timestamps must contain exact UTC start and end fields")
    else:
        started = timestamps["started_at_utc"]
        ended = timestamps["ended_at_utc"]
        if not isinstance(started, str) or not UTC_TIMESTAMP.fullmatch(started):
            diagnostics.append("start timestamp must be UTC ISO-8601 seconds")
        if not isinstance(ended, str) or not UTC_TIMESTAMP.fullmatch(ended):
            diagnostics.append("end timestamp must be UTC ISO-8601 seconds")
        if isinstance(started, str) and isinstance(ended, str) and ended < started:
            diagnostics.append("end timestamp must not precede start timestamp")

    workers = document["workers"]
    if not isinstance(workers, dict) or "topology" not in workers or workers["topology"] != "single_process":
        diagnostics.append("worker topology must be single_process")
    if not isinstance(workers, dict) or "count" not in workers or type(workers["count"]) is not int or workers["count"] != 1:
        diagnostics.append("worker count must be the exact integer 1 for single_process execution")

    fingerprint = document["host_fingerprint"]
    expected_fingerprint = {
        "algorithm": "sha256",
        "digest": _host_fingerprint(selected_hostname, selected_runtime),
    }
    if fingerprint != expected_fingerprint:
        diagnostics.append("host fingerprint does not match the executing host")

    backend = document["backend"]
    backend_name: str | None = None
    if isinstance(backend, dict) and "class" in backend:
        backend_class = backend["class"]
        backend_name = next(
            (name for name, contract in BACKENDS.items() if contract["class"] == backend_class),
            None,
        )
    if backend_name is None:
        diagnostics.append("backend class is unknown")
    else:
        contract = BACKENDS[backend_name]
        if expected_backend is not None and backend_name != expected_backend:
            diagnostics.append(f"backend does not match expected backend {expected_backend}")
        expected_distribution = contract["distribution"]
        selected_backend_version = version(str(expected_distribution)) if backend_version is None else backend_version
        expected_backend_fields = {
            "class": contract["class"],
            "distribution": expected_distribution,
            "version": selected_backend_version,
        }
        if backend != expected_backend_fields:
            diagnostics.append(f"backend runtime fields do not match: expected {expected_backend_fields!r}")
        os_key = str(selected_runtime["os_name"]).lower()
        platform_key = f"{os_key}-{selected_runtime['architecture']}"
        supported = contract["platforms"]
        if backend_name == "mlx" and platform_key not in supported:
            diagnostics.append("MLX backend requires Darwin arm64")
        if backend_name == "numpy" and os_key not in supported:
            diagnostics.append("NumPy backend requires a declared Darwin or Linux platform")
        if document["device_class"] != contract["device_class"]:
            diagnostics.append("device class does not match the backend")
        if document["precision_mode"] != contract["precision_mode"]:
            diagnostics.append("precision mode does not match the backend")

    system = document["system_under_test"]
    if not isinstance(system, str) or system not in SYSTEM_PACKAGES:
        diagnostics.append("system under test is not an engine")
    elif document["package_under_test"] != SYSTEM_PACKAGES[system]:
        diagnostics.append("package under test does not match the engine system")
    expected_packages = validate_installed_packages()
    if document["packages_validated"] != expected_packages:
        diagnostics.append("validated package identities do not match the installed workspace")

    manifest_entry = document["manifest"]
    if not isinstance(manifest_entry, dict) or set(manifest_entry) != {"path", "sha256"}:
        diagnostics.append("manifest evidence must contain exact path and sha256 fields")
    else:
        raw_manifest_path = manifest_entry["path"]
        if not isinstance(raw_manifest_path, str):
            diagnostics.append("manifest path must be repository-relative")
        else:
            try:
                if not isinstance(system, str) or system not in PACKAGE_BY_SYSTEM:
                    raise ValueError("cannot establish canonical manifest for invalid system")
                manifest_file, manifest_relative = _system_manifest(repo_root, system, Path(raw_manifest_path))
                if manifest_relative != raw_manifest_path:
                    diagnostics.append("manifest path is not canonical and repository-relative")
                actual_digest = _manifest_digest(manifest_file)
                digest = manifest_entry["sha256"]
                if not isinstance(digest, str) or not HEX_SHA256.fullmatch(digest) or digest != actual_digest:
                    diagnostics.append("manifest digest does not match repository bytes")
                manifest_document = json.loads(manifest_file.read_text(encoding="utf-8"))
                if not isinstance(manifest_document, Mapping) or "system" not in manifest_document or manifest_document["system"] != system:
                    diagnostics.append("manifest system does not match the system under test")
                if backend_name is not None and isinstance(manifest_document, Mapping):
                    capability = _backend_capability(manifest_document, str(BACKENDS[backend_name]["class"]))
                    if "implemented" not in capability or capability["implemented"] is not False:
                        diagnostics.append("manifest capability must remain unimplemented during B0 bootstrap")
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                diagnostics.append(f"manifest path or content is invalid: {exc}")

    evidence = document["evidence"]
    if evidence != {"class": "contract", "statement": EVIDENCE_STATEMENT}:
        diagnostics.append("evidence must explicitly remain non-scientific contract evidence")
    operation = document["operation"]
    if operation != EXPECTED_OPERATION:
        diagnostics.append("operation result does not prove the required numerical execution")

    return sorted(set(diagnostics), key=lambda item: item.encode("utf-8"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="execute a backend and write a probe")
    generate.add_argument("--backend", choices=sorted(BACKENDS), required=True)
    generate.add_argument("--system", choices=sorted(SYSTEM_PACKAGES), required=True)
    generate.add_argument("--manifest", type=Path, required=True)
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--execution-mode", choices=("local", "hosted"), required=True)
    validate = commands.add_parser("validate", help="validate a written probe")
    validate.add_argument("--input", type=Path, required=True)
    validate.add_argument("--execution-mode", choices=("local", "hosted"), required=True)
    validate.add_argument("--expected-backend", choices=sorted(BACKENDS), required=True)
    return parser


def main(arguments: list[str] | None = None) -> int:
    parsed = _parser().parse_args(arguments)
    repo_root = Path(__file__).resolve().parents[2]
    if parsed.command == "generate":
        document = write_runtime_probe(
            output_path=parsed.output,
            repo_root=repo_root,
            backend=parsed.backend,
            system=parsed.system,
            manifest_path=parsed.manifest,
            execution_mode=parsed.execution_mode,
        )
        print(
            f"Runtime probe: PASS ({document['backend']['class']} {document['backend']['version']}, "
            f"{parsed.output})"
        )
        return 0
    diagnostics = validate_runtime_probe(
        probe_path=parsed.input,
        repo_root=repo_root,
        execution_mode=parsed.execution_mode,
        expected_backend=parsed.expected_backend,
    )
    if diagnostics:
        print(f"Runtime probe validation: FAIL ({len(diagnostics)} violations)")
        for diagnostic in diagnostics:
            print(f"ERROR: {diagnostic}")
        return 1
    print(f"Runtime probe validation: PASS ({parsed.expected_backend})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
