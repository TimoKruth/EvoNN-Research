import numpy as np
import pytest
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split

from evonn_contenders.models import NGram, OptionalContenderUnavailable, build_model
from evonn_contenders.config import load_pools, resolve_pool
from evonn_shared.catalog import list_benchmarks


def test_logistic_learns_real_training_rows_without_validation_leakage():
    x, y = load_iris(return_X_y=True)
    tx, vx, ty, vy = train_test_split(x, y, test_size=.2, random_state=42, stratify=y)
    model = build_model("logistic", task="classification", seed=42, input_shape=(4,), train_rows=len(tx), output_dim=3)
    model.fit(tx, ty)
    assert (model.predict(vx) == vy).mean() > .85
    assert np.allclose(model.steps[0][1].mean_, tx.mean(axis=0))
    assert not np.array_equal(model.steps[0][1].mean_, vx.mean(axis=0))


def test_ngram_learns_counts_and_unseen_contexts_without_mutation():
    x = np.tile(np.arange(8), 8).reshape(-1, 1)
    y = (x[:, 0] + 1) % 8
    model = NGram(order=2, vocabulary_size=8, alpha=.1).fit(x, y)
    before = {key: dict(value) for key, value in model.counts.items()}
    assert 1 <= model.perplexity(x, y) < 2
    assert np.allclose(model.predict_proba(x).sum(axis=1), 1)
    assert {key: dict(value) for key, value in model.counts.items()} == before
    with pytest.raises(ValueError):
        model.fit(x, y + 8)


def test_required_pools_cover_all_canonical_floors_and_four_groups():
    config, _ = load_pools()
    for definition in list_benchmarks():
        required, optional = resolve_pool(config, definition)
        assert set(definition.required_contenders) <= set(required)
        assert set(required).isdisjoint(optional)
    assert "text_language_modeling" in config["pools"]
    assert all("extra" not in config["models"][name] for name in config["pools"]["text_language_modeling"])


def test_missing_extra_is_distinct_from_a_failed_required_fit(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "xgboost", None)
    with pytest.raises(OptionalContenderUnavailable, match="boosted"):
        build_model("xgboost", task="classification", seed=42, input_shape=(4,), train_rows=10, output_dim=3)
    with pytest.raises(ValueError, match="Unknown contender"):
        build_model("not_a_model", task="classification", seed=42, input_shape=(4,), train_rows=10, output_dim=3)


@pytest.mark.parametrize("parameter", ["device", "device_type", "task_type", "nthread", "num_threads", "num_thread", "nthreads"])
def test_optional_device_and_thread_controls_belong_to_cpu_protocol(parameter):
    with pytest.raises(ValueError, match="controls are owned"):
        build_model("xgboost", task="classification", seed=42, input_shape=(4,), train_rows=20,
                    output_dim=2, parameters={parameter: "cuda"})


def test_ngram_extreme_finite_smoothing_preserves_probability_mass():
    model = NGram(order=2, vocabulary_size=8, alpha=np.finfo(np.float64).max)
    model.fit(np.array([[0]]), np.array([1]))
    with np.errstate(over="raise", invalid="raise"):
        probabilities = model.predict_proba(np.array([[0], [7]]))
    assert np.allclose(probabilities, 1 / 8)
    assert np.allclose(probabilities.sum(axis=1), 1)


@pytest.mark.parametrize("parameter", ["allow_writing_files", "train_dir", "save_snapshot", "snapshot_file"])
def test_catboost_cannot_enable_out_of_protocol_file_output(parameter):
    with pytest.raises(ValueError, match="file output controls"):
        build_model("catboost", task="classification", seed=42, input_shape=(4,), train_rows=20,
                    output_dim=2, parameters={parameter: True})


def test_malformed_pool_yaml_has_controlled_cli_error(tmp_path, capsys):
    from evonn_contenders.cli import main
    pools = tmp_path / "broken.yaml"
    pools.write_text("models: [unterminated")
    with pytest.raises(SystemExit) as error:
        main(["run", "--pack", "tier1_core", "--pools", str(pools),
              "--output", str(tmp_path / "runs"), "--cache", str(tmp_path / "cache")])
    assert error.value.code == 2
    assert "invalid pool YAML" in capsys.readouterr().err
    assert not (tmp_path / "runs").exists()


def test_ngram_rejects_smoothing_that_underflows_with_observed_counts():
    with pytest.raises(ValueError, match="machine epsilon"):
        NGram(order=2, vocabulary_size=2, alpha=np.nextafter(0.0, 1.0))
    model = NGram(order=2, vocabulary_size=2, alpha=np.finfo(np.float64).eps)
    model.fit(np.array([[0], [0]]), np.array([0, 0]))
    assert np.isfinite(model.perplexity(np.array([[0]]), np.array([1])))


@pytest.mark.parametrize("parameter", ["data_random_seed", "data_seed", "feature_fraction_seed",
    "bagging_seed", "bagging_fraction_seed", "extra_seed", "drop_seed", "objective_seed"])
def test_lightgbm_specific_seed_controls_belong_to_run_protocol(parameter):
    with pytest.raises(ValueError, match="controls are owned"):
        build_model("lightgbm", task="classification", seed=42, input_shape=(4,), train_rows=20,
                    output_dim=2, parameters={parameter: 999})
