"""Fixed-architecture initialization controls, through the real bounded CLI."""
import json
import os
from pathlib import Path
import subprocess
import sys

from evonn_shared.export_reader import read_export
from evonn_shared.engine_evidence import artifact_json, validate_engine_bundle

ROOT = Path(__file__).resolve().parents[2]


def invoke(*args):
    return subprocess.run([sys.executable, "-m", "prism.cli", *map(str, args)], cwd=ROOT,
                          text=True, capture_output=True, timeout=240)


def test_finalist_controls_freeze_genomes_training_and_prior_accounting(tmp_path):
    source = invoke("run", "--pack", "tier1_core_smoke", "--budget", 8, "--epochs", 2,
                    "--variant", "legacy", "--timeout", 220, "--fit-timeout", 20,
                    "--backend", os.environ.get("EVONN_TEST_BACKEND", "numpy_fallback"),
                    "--output", tmp_path / "source", "--cache", tmp_path / "cache")
    assert source.returncode == 0, source.stderr
    plan = invoke("finalist-config", source.stdout.strip())
    assert plan.returncode == 0, plan.stderr
    config = json.loads(plan.stdout)
    config_path = tmp_path / "finalists.json"
    config_path.write_text(json.dumps(config))
    ledgers = []
    for policy in ("enabled", "disabled"):
        result = invoke("run", "--config", config_path, "--budget", 16, "--inheritance-policy", policy,
                        "--optimizer-policy", "continue", "--optimizer-backend", "native",
                        "--output", tmp_path / policy, "--cache", tmp_path / "cache")
        assert result.returncode == 0, result.stderr
        bundle = read_export(Path(result.stdout.strip()))
        validate_engine_bundle(bundle, verify_cache=True)
        assert bundle.manifest.seeding.seeding_enabled
        assert bundle.manifest.seeding.seed_cost_accounting.value == "reported_prior"
        assert bundle.manifest.seeding.seed_source_evaluations == 8
        rows = artifact_json(bundle, "attempts.json")["attempts"]
        assert len(rows) == 16
        assert all(a["allocated_epochs"] == a["epochs"] == a["full_epochs"] == 2 for a in rows)
        assert all(a["genome"] == config["fixed_genomes"][a["benchmark_id"]] for a in rows)
        assert all(a["proposal"]["origin"] == "fixed_architecture" for a in rows)
        ledgers.append(rows)
        report = invoke("research-report", bundle.root)
        assert report.returncode == 0, report.stderr
    assert any(a["inheritance"]["mode"] == "exact" for a in ledgers[0])
    assert any(a["optimizer_resumed_step"] > 0 for a in ledgers[0])
    assert all(a["inheritance"]["mode"] == "none" for a in ledgers[1])
    assert [(a["genome_id"], a["model_seed"]) for a in ledgers[0]] == [(a["genome_id"], a["model_seed"]) for a in ledgers[1]]
    first = next(iter(config["fixed_genomes"]))
    config["fixed_genomes"][first]["learning_rate"] = .07
    config_path.write_text(json.dumps(config))
    rejected = invoke("run", "--config", config_path, "--output", tmp_path / "tampered")
    assert rejected.returncode != 0 and "discovery provenance" in rejected.stderr
    assert not (tmp_path / "tampered").exists()
