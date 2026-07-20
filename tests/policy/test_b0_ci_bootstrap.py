from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

from evonn_shared.backend_contract import ENGINE_CONTRACTS, ENGINE_DEPENDENCIES

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKOUT_SHA = "de0fac2e4500dabe0009e67214ff5f5447ce83dd"
SETUP_UV_SHA = "11f9893b081a58869d3b5fccaea48c9e9e46f990"
UPLOAD_SHA = "ea165f8d65b6e75b540449e92b4886f43607fa02"
UV_VERSION = "0.5.13"
ENGINE_DIRECTORIES = tuple(engine.directory for engine in ENGINE_CONTRACTS)


def _workflow(name: str) -> tuple[dict, str]:
    path = REPO_ROOT / ".github/workflows" / name
    text = path.read_text(encoding="utf-8")
    loaded = yaml.safe_load(text)
    assert isinstance(loaded, dict)
    return loaded, text


def _job(workflow: dict, job_name: str) -> dict:
    jobs = workflow["jobs"]
    assert list(jobs) == [job_name]
    return jobs[job_name]


def _steps(job: dict) -> list[dict]:
    steps = job["steps"]
    assert isinstance(steps, list) and steps
    return steps


def _run_text(steps: list[dict]) -> str:
    return "\n".join(str(step["run"]) for step in steps if "run" in step)


def _uses(steps: list[dict]) -> list[str]:
    return [str(step["uses"]) for step in steps if "uses" in step]


@pytest.mark.parametrize(
    ("workflow_name", "job_name"),
    (("linux-trust.yml", "linux-trust"), ("macos-engines.yml", "macos-engines")),
)
def test_hosted_workflows_fetch_full_git_history(workflow_name: str, job_name: str) -> None:
    workflow, _ = _workflow(workflow_name)
    checkout = next(
        step
        for step in _steps(_job(workflow, job_name))
        if str(step.get("uses", "")).startswith("actions/checkout@")
    )

    assert checkout["with"]["fetch-depth"] == 0


def test_linux_workflow_has_exact_trust_lane_contract() -> None:
    workflow, text = _workflow("linux-trust.yml")
    job = _job(workflow, "linux-trust")
    steps = _steps(job)
    commands = _run_text(steps)

    assert workflow["name"] == "B0 Linux trust lane"
    assert job["runs-on"] == "ubuntu-latest"
    assert _uses(steps) == [
        f"actions/checkout@{CHECKOUT_SHA}",
        f"astral-sh/setup-uv@{SETUP_UV_SHA}",
        f"actions/upload-artifact@{UPLOAD_SHA}",
    ]
    setup_uv = next(step for step in steps if str(step.get("uses", "")).startswith("astral-sh/setup-uv@"))
    assert setup_uv["with"]["version"] == UV_VERSION
    assert "uv python install 3.13" in commands
    assert "uv sync --all-packages --group dev --locked" in commands
    assert "scripts/ci/b0-policy-checks.sh" in commands
    for script in (
        "shared-checks.sh",
        "benchmarks-checks.sh",
        "compare-checks.sh",
        "contenders-checks.sh",
        "stratograph-checks.sh",
        "primordia-checks.sh",
    ):
        assert f"scripts/ci/{script}" in commands
    assert "prism-checks.sh" not in commands
    assert "topograph-checks.sh" not in commands
    assert "uv pip show mlx" in commands
    assert "--backend numpy" in commands
    assert "--execution-mode hosted" in commands
    assert "validate" in commands and "--expected-backend numpy" in commands
    assert "b0-linux-runtime-probe" in text
    assert "b0-runtime-probe.json" in text
    assert "run: true" not in text and "run: echo" not in text and "run: print" not in text


def test_macos_workflow_has_exact_engine_lane_contract() -> None:
    workflow, text = _workflow("macos-engines.yml")
    job = _job(workflow, "macos-engines")
    steps = _steps(job)
    commands = _run_text(steps)

    assert workflow["name"] == "B0 macOS engine lane"
    assert job["runs-on"] == "macos-15"
    assert _uses(steps) == [
        f"actions/checkout@{CHECKOUT_SHA}",
        f"astral-sh/setup-uv@{SETUP_UV_SHA}",
        f"actions/upload-artifact@{UPLOAD_SHA}",
    ]
    setup_uv = next(step for step in steps if str(step.get("uses", "")).startswith("astral-sh/setup-uv@"))
    assert setup_uv["with"]["version"] == UV_VERSION
    assert "uv python install 3.13" in commands
    assert "uv sync --all-packages --group dev --locked" in commands
    assert "scripts/ci/b0-policy-checks.sh" in commands
    assert "test \"$(uname -m)\" = \"arm64\"" in commands
    assert "platform.machine() == 'arm64'" in commands
    assert "scripts/ci/prism-checks.sh" in commands
    assert "scripts/ci/topograph-checks.sh" in commands
    for script in ("shared-checks.sh", "benchmarks-checks.sh", "compare-checks.sh", "contenders-checks.sh"):
        assert f"scripts/ci/{script}" not in commands
    assert "uv pip show mlx" in commands
    assert "--backend mlx" in commands
    assert "--execution-mode hosted" in commands
    assert "validate" in commands and "--expected-backend mlx" in commands
    assert "b0-macos-runtime-probe" in text
    assert "b0-runtime-probe.json" in text
    assert "run: true" not in text and "run: echo" not in text and "run: print" not in text


def test_engine_dependency_markers_are_exact_and_linux_safe() -> None:
    for directory in ENGINE_DIRECTORIES:
        with (REPO_ROOT / directory / "pyproject.toml").open("rb") as stream:
            metadata = tomllib.load(stream)
        assert metadata["project"]["dependencies"] == list(ENGINE_DEPENDENCIES)

    contenders = (REPO_ROOT / "EvoNN-Contenders/pyproject.toml").read_text(encoding="utf-8")
    assert "scikit-learn" not in contenders.lower()
    assert "sklearn" not in contenders.lower()


def test_b0_policy_script_uses_common_root_and_complete_nonrecursive_test_discovery() -> None:
    text = (REPO_ROOT / "scripts/ci/b0-policy-checks.sh").read_text(encoding="utf-8")

    assert "source" in text and "_common.sh" in text
    assert "tests/policy" in text and "tests/ci" in text
    assert "not b0_policy_script_selftest" in text
    assert "not all_check_scripts" in text
    assert "test_repository_governance.py" not in text
    assert "test_workspace_skeletons.py" not in text


@pytest.mark.b0_policy_script_selftest
def test_b0_policy_script_runs_from_another_directory(tmp_path: Path) -> None:
    script = REPO_ROOT / "scripts/ci/b0-policy-checks.sh"
    assert os.access(script, os.X_OK)
    environment = os.environ.copy()
    environment["UV_PYTHON"] = sys.executable
    result = subprocess.run(
        [str(script)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert "Repository governance policy: PASS" in result.stdout
    assert "Import boundary policy: PASS" in result.stdout
    assert "Backend capability policy: PASS" in result.stdout


def test_workflow_policy_preserves_full_history_and_final_b0_closure() -> None:
    report = json.loads(
        (REPO_ROOT / "governance/b0-report.json").read_text(encoding="utf-8")
    )
    status = yaml.safe_load(
        (REPO_ROOT / "governance/b0-status.yaml").read_text(encoding="utf-8")
    )

    if report["schema_version"] == "1.0.0":
        assert status["status"] == "open"
    else:
        assert report["schema_version"] == "2.0.0"
        assert status["status"] == "closed"
        assert status["items"]["B0.2"]["status"] == "closed"
        assert status["items"]["B0.5"]["status"] == "closed"
