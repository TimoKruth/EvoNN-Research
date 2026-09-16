"""Baseline screening cannot inherit floor trust or silently lose a family."""

from copy import deepcopy

import pytest

from evonn_compare import campaign as c
from evonn_compare.audit import benchmark_audit, reviewed_ngram_parameters


@pytest.mark.parametrize(
    "field,value",
    [
        ("systems", ["contenders"]),
        ("enhanced", False),
        ("pack", "tier_b_core_v2"),
        ("budgets", [12]),
        ("budgets", [20]),
        ("contender_pool", "../../pools"),
    ],
)
def test_screen_rejects_invalid_scope(field, value):
    settings = dict(pack="language_breadth_v1", budgets=[64], enhanced=True, contender_pool="lm_screen_v1_reference")
    settings[field] = value
    with pytest.raises(ValueError):
        c.CampaignSpec(**settings)


def test_historical_campaign_uses_unchanged_pool():
    assert c.contender_pool_path(c.CampaignSpec()) == "EvoNN-Contenders/src/evonn_contenders/pools.yaml"
    assert not reviewed_ngram_parameters("bigram_lm", {"alpha": 0.1})
    with pytest.raises(ValueError, match="descriptive"):
        benchmark_audit("language_breadth_v1", [], decision_grade=True, parameter_screening=True)


@pytest.mark.parametrize(
    "suffix,epochs,alpha",
    [
        ("reference", 20, 1.0),
        ("epochs2", 2, 1.0),
        ("epochs5", 5, 1.0),
        ("epochs10", 10, 1.0),
        ("alpha01", 20, 0.1),
        ("alpha001", 20, 0.01),
    ],
)
def test_pool_changes_only_declared_baseline_parameters(suffix, epochs, alpha):
    spec = c.CampaignSpec(
        pack="language_breadth_v1", budgets=[64], enhanced=True, contender_pool="lm_screen_v1_" + suffix
    )
    original = c.yaml.safe_load((c.ROOT / c.contender_pool_path(c.CampaignSpec())).read_bytes())
    actual = c.yaml.safe_load((c.ROOT / c.contender_pool_path(spec)).read_bytes())
    expected = deepcopy(original)
    expected["models"]["transformer_lm_tiny"]["parameters"]["epochs"] = epochs
    for family in ("unigram_lm", "bigram_lm", "trigram_lm"):
        expected["models"][family]["parameters"]["alpha"] = alpha
    assert actual == expected
    identity = {
        "commit": "a" * 40,
        "source_sha256": "b" * 64,
        "versions": c.versions(),
        "data_files": {
            c.contender_pool_path(spec): c.hashlib.sha256(
                (c.ROOT / c.contender_pool_path(spec)).read_bytes()
            ).hexdigest()
        },
    }
    manifest = {"spec": spec.model_dump(mode="json"), "identity": identity, "cache": "/pinned/cache"}
    config = {
        "git_commit": identity["commit"],
        "code_dirty": False,
        "dataset_versions": {
            name: identity["versions"][name] for name in ("numpy", "scipy", "scikit-learn", "pandas", "openml")
        },
        "fit_timeout_seconds": 90.0,
        "enhanced": True,
        "pools": actual,
        "pool_sha256": identity["data_files"][c.contender_pool_path(spec)],
    }
    case = c.Case(spec.pack, 64, 42)
    c.match_config(config, manifest, case, "contenders")
    with pytest.raises(ValueError, match="pool mismatch"):
        c.match_config({**config, "pool_sha256": "0" * 64}, manifest, case, "contenders")
    altered = deepcopy(config)
    altered["pools"]["models"]["transformer_lm_tiny"]["parameters"]["epochs"] = 99
    with pytest.raises(ValueError, match="pool mismatch"):
        c.match_config(altered, manifest, case, "contenders")


def test_study_roster_coverage_and_nomination_are_preregistered():
    from evonn_compare.baseline_study import ARMS, matrix, nominate

    rows = matrix()
    assert len(rows) == 12
    assert sum(len(row["spec"]["systems"]) for row in rows) == 60
    assert sum(row["spec"]["budgets"][0] * 5 for row in rows) == 3840
    assert {row["seed"] for row in rows} == {1421, 1422}
    assert {row["seed"] for row in matrix(qualification=True)} == {1431}
    baselines = []
    for arm in ARMS:
        for seed in [1421, 1422]:
            for task in ["real1", "real2", "real3", "delayed_copy_lm"]:
                for family in ["transformer_lm_tiny", "bigram_lm"]:
                    value = 100.0
                    if arm == "epochs2" and family == "transformer_lm_tiny":
                        value = 80.0 if task != "delayed_copy_lm" else 111.0
                    if arm == "epochs5" and family == "transformer_lm_tiny":
                        value = 90.0
                    if arm == "alpha01" and family == "bigram_lm":
                        value = 97.0
                    baselines.append(dict(arm=arm, seed=seed, benchmark=task, family=family, value=value))
    result = nominate(baselines)
    assert result["transformer"]["nomination"] == "epochs5"  # best real score fails control guard
    assert result["ngram"]["nomination"] == "alpha01"
    for row in baselines:
        row["value"] = 100.0
    assert all(v["nomination"] == "reference" for v in nominate(baselines).values())


def test_production_cannot_prepare_without_completed_qualification(tmp_path, monkeypatch):
    from evonn_compare import baseline_study as study

    monkeypatch.setattr(c, "identity", lambda: {"commit": "frozen"})
    monkeypatch.setattr(study, "seed_audit", lambda qualification: {})
    with pytest.raises(ValueError, match="qualification-workspace"):
        study.prepare(tmp_path / "study", tmp_path / "cache")
    assert not (tmp_path / "study").exists()


def test_replay_validation_rejects_false_pass_and_duplicate_tasks():
    from evonn_compare.baseline_study import validate_replay

    tasks = c.load_parity_pack("language_breadth_v1").benchmarks
    value = {
        "status": "passed",
        "run_id": "run",
        "checks": [dict(benchmark=t, observed=2.0, exported=2.0) for t in tasks],
    }
    validate_replay(value, "run", "language_breadth_v1")
    value["checks"][0]["observed"] = 3.0
    with pytest.raises(ValueError, match="replay mismatch"):
        validate_replay(value, "run", "language_breadth_v1")
    value["checks"][0] = value["checks"][1]
    with pytest.raises(ValueError, match="replay mismatch"):
        validate_replay(value, "run", "language_breadth_v1")


def test_replay_payload_stays_json_when_process_warns(tmp_path):
    import sys
    import json

    log = tmp_path / "replay.log"
    payload = tmp_path / "replay.json"
    c._bounded_process(
        [sys.executable, "-c", 'import sys; print("{\\"status\\":\\"passed\\"}"); print("warning",file=sys.stderr)'],
        10,
        log,
        stdout_path=payload,
    )
    assert json.loads(payload.read_text()) == {"status": "passed"}
    assert log.read_text().strip() == "warning"


def test_missing_or_hung_transformer_is_a_diagnostic_blocker(monkeypatch):
    import subprocess
    from types import SimpleNamespace

    monkeypatch.setattr(c.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1, stderr=b"no torch"))
    with pytest.raises(ValueError, match="no torch"):
        c.probe_transformer()

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("probe", 30, stderr=b"backend hung")

    monkeypatch.setattr(c.subprocess, "run", timeout)
    with pytest.raises(ValueError, match="backend hung"):
        c.probe_transformer()
