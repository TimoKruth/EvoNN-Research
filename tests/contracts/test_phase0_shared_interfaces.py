from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

from evonn_shared.backend_contract import PACKAGE_CONTRACTS

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_PACKAGE_CONTEXTS = (
    ("EvoNN-Shared", "evonn-shared", "evonn_shared", "shared"),
    ("EvoNN-Compare", "evonn-compare", "evonn_compare", "compare"),
    ("EvoNN-Contenders", "evonn-contenders", "evonn_contenders", "contenders"),
    ("EvoNN-Prism", "evonn-prism", "prism", "prism"),
    ("EvoNN-Topograph", "evonn-topograph", "topograph", "topograph"),
    ("EvoNN-Stratograph", "evonn-stratograph", "stratograph", "stratograph"),
    ("EvoNN-Primordia", "evonn-primordia", "evonn_primordia", "primordia"),
)
FROZEN_PUBLIC_APIS = {
    "evonn_shared.canonical": (
        "AbsolutePathError",
        "CANONICAL_ENCODING",
        "CanonicalIdentityError",
        "CanonicalScalar",
        "CanonicalValue",
        "IntegerOutOfRangeError",
        "InvalidBytePayloadError",
        "InvalidDigestFieldError",
        "InvalidMappingKeyError",
        "InvalidSchemaVersionError",
        "InvalidUnicodeError",
        "NonFiniteFloatError",
        "NormalizedKeyCollisionError",
        "UnsupportedCanonicalTypeError",
        "VolatileFieldError",
        "canonical_bytes",
        "canonical_sha256",
        "sha256_bytes",
    ),
    "evonn_shared.rng": (
        "InvalidRootSeedError",
        "InvalidStreamNameError",
        "StreamName",
        "derive_stream",
    ),
    "evonn_shared.budgets": (
        "BenchmarkSurfaceBudget",
        "BudgetAccounting",
        "BudgetDeclaration",
        "ContractModel",
        "EvaluationBudget",
        "EvaluationStage",
        "FidelityBudget",
        "FidelityStage",
        "HardwareEnvelope",
        "LadderTier",
        "ModelArtifactBudget",
        "TrainingBudget",
        "WallClockBudget",
    ),
    "evonn_shared.telemetry": (
        "AggregateMetric",
        "ArtifactReference",
        "BackendClass",
        "BenchmarkResult",
        "BestResult",
        "Coverage",
        "FairnessFlag",
        "FairnessSeverity",
        "FloatMeasurement",
        "IntegerMeasurement",
        "MeasurementProvenance",
        "MetricDirection",
        "MetricValue",
        "ResultStatus",
        "RuntimeMetadata",
        "SeedCostAccounting",
        "SeedingLadder",
        "SeedingMetadata",
        "SeedOverlapPolicy",
        "SystemId",
        "TaskKind",
        "RunTiming",
        "WorkerTopology",
    ),
    "evonn_shared.exports": (
        "EXPORT_SCHEMA_VERSION",
        "MANIFEST_FILENAME",
        "RESULTS_FILENAME",
        "SUMMARY_FILENAME",
        "ExportDigests",
        "Manifest",
        "Results",
        "RunClass",
        "RunStatus",
        "RunSummary",
        "write_export",
    ),
    "evonn_shared.catalog": (
        "CATALOG_SCHEMA_VERSION",
        "BenchmarkStatus",
        "InputModality",
        "CeilingTiePolicy",
        "PrimaryMetric",
        "MetricCeiling",
        "BenchmarkSpec",
        "CanonicalIdEntry",
        "CanonicalIdRegistry",
        "PackBudgetPolicy",
        "BenchmarkPack",
        "LadderTier",
        "TaskKind",
        "MetricDirection",
        "SystemId",
        "CatalogError",
        "InvalidCatalogIdentifierError",
        "UnsafeCatalogPathError",
        "DuplicateCatalogDefinitionError",
        "InvalidCatalogYamlError",
        "InvalidCatalogModelError",
        "CatalogRegistryMismatchError",
        "BenchmarkNotFoundError",
        "PackNotFoundError",
        "UnknownPackBenchmarkError",
        "get_benchmark",
        "list_benchmarks",
        "resolve_pack_path",
        "load_parity_pack",
    ),
}

PACKAGE_PROBE = """
import importlib
import json
import sys
from importlib.metadata import version

contract = json.loads(sys.argv[1])
package = importlib.import_module(contract["module"])
assert version(contract["distribution"]) == "0.0.0"
assert package.__version__ == "0.0.0"
assert package.SYSTEM == contract["system"]
for module_name, expected_names in contract["public_apis"].items():
    module = importlib.import_module(module_name)
    assert tuple(module.__all__) == tuple(expected_names)
    for name in expected_names:
        getattr(module, name)
record = {
    "directory": contract["directory"],
    "distribution": contract["distribution"],
    "module": contract["module"],
    "status": "ok",
    "system": contract["system"],
    "version": "0.0.0",
}
print(json.dumps(record, sort_keys=True, separators=(",", ":")))
""".strip()


def _contract_payload(package: object) -> dict[str, object]:
    return {
        "directory": package.directory,
        "distribution": package.distribution,
        "module": package.module,
        "system": package.system,
        "public_apis": FROZEN_PUBLIC_APIS,
    }


def _success_record(package: object) -> dict[str, str]:
    return {
        "directory": package.directory,
        "distribution": package.distribution,
        "module": package.module,
        "status": "ok",
        "system": package.system,
        "version": "0.0.0",
    }


def _probe_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    environment["PYTHONHASHSEED"] = "0"
    return environment


def _run_package_contract(package: object) -> None:
    payload = json.dumps(_contract_payload(package), sort_keys=True, separators=(",", ":"))
    result = subprocess.run(
        [sys.executable, "-I", "-c", PACKAGE_PROBE, payload],
        cwd=REPO_ROOT / package.directory,
        env=_probe_environment(),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    expected_record = _success_record(package)
    assert result.returncode == 0, (
        f"{package.directory} failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert result.stderr == ""
    assert result.stdout == json.dumps(expected_record, sort_keys=True, separators=(",", ":")) + "\n"
    assert json.loads(result.stdout) == expected_record


def test_package_contracts_have_exact_canonical_order() -> None:
    actual = tuple(
        (package.directory, package.distribution, package.module, package.system)
        for package in PACKAGE_CONTRACTS
    )
    assert actual == EXPECTED_PACKAGE_CONTEXTS


def test_parent_process_resolves_exact_frozen_public_apis() -> None:
    assert tuple(FROZEN_PUBLIC_APIS) == (
        "evonn_shared.canonical",
        "evonn_shared.rng",
        "evonn_shared.budgets",
        "evonn_shared.telemetry",
        "evonn_shared.exports",
        "evonn_shared.catalog",
    )
    for module_name, expected_names in FROZEN_PUBLIC_APIS.items():
        module = importlib.import_module(module_name)
        assert tuple(module.__all__) == expected_names
        for name in expected_names:
            assert getattr(module, name) is not None


def test_package_probe_invocation_is_isolated_and_sanitized(monkeypatch: object) -> None:
    package = PACKAGE_CONTRACTS[0]
    captured: dict[str, object] = {}
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT / "EvoNN-Shared/src"))
    monkeypatch.setenv("PYTHONHOME", str(REPO_ROOT / ".venv"))

    def record_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["argv"] = argv
        captured.update(kwargs)
        stdout = json.dumps(_success_record(package), sort_keys=True, separators=(",", ":")) + "\n"
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(subprocess, "run", record_run)
    _run_package_contract(package)

    argv = captured["argv"]
    environment = captured["env"]
    assert argv[:2] == [sys.executable, "-I"]
    assert argv[2:4] == ["-c", PACKAGE_PROBE]
    assert len(argv) == 5
    assert captured["cwd"] == REPO_ROOT / package.directory
    assert "PYTHONPATH" not in environment
    assert "PYTHONHOME" not in environment
    assert environment["PYTHONHASHSEED"] == "0"


def test_all_seven_installed_package_contexts_resolve_frozen_shared_contracts() -> None:
    for package in PACKAGE_CONTRACTS:
        _run_package_contract(package)
