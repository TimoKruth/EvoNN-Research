from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import textwrap
import time

import duckdb
import pytest
from pydantic import ValidationError

from evonn_shared.run_store import (
    LOCK_FILENAME,
    RUN_STORE_SCHEMA_VERSION,
    STORE_FILENAME,
    ArtifactRow,
    EvaluationChainError,
    EvaluationRow,
    LockOwner,
    RunIdentityError,
    RunStoreError,
    RunStoreExistsError,
    RunStoreLockedError,
    RunStoreNotFoundError,
    open_run_store,
    read_lock_owner,
)

RUN_ID = "run_0001"
DIGEST = "a" * 64


def _run_directory(tmp_path: Path) -> Path:
    directory = tmp_path / RUN_ID
    directory.mkdir()
    return directory


def _seeded(tmp_path: Path) -> Path:
    directory = _run_directory(tmp_path)
    with open_run_store(directory, RUN_ID, create=True) as store:
        store.append_evaluation("iris", "mlp_baseline", "accuracy", 0.91)
        store.append_evaluation("iris", "evonn_prism", "accuracy", 0.94)
        store.append_evaluation("wine", "mlp_baseline", "accuracy", 0.88)
    return directory


def _raw(directory: Path, statement: str) -> None:
    connection = duckdb.connect(str(directory / STORE_FILENAME))
    try:
        connection.execute(statement)
    finally:
        connection.close()


# --- schema and identity --------------------------------------------------


def test_creating_a_store_records_exactly_one_run(tmp_path: Path) -> None:
    directory = _run_directory(tmp_path)

    with open_run_store(directory, RUN_ID, create=True) as store:
        record = store.run()

    assert record.run_id == RUN_ID
    assert record.schema_version == RUN_STORE_SCHEMA_VERSION
    assert (directory / STORE_FILENAME).is_file()


def test_creating_over_an_existing_store_is_refused(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)

    with pytest.raises(RunStoreExistsError):
        with open_run_store(directory, RUN_ID, create=True):
            pass


def test_opening_a_missing_store_is_refused(tmp_path: Path) -> None:
    directory = _run_directory(tmp_path)

    with pytest.raises(RunStoreNotFoundError):
        with open_run_store(directory, RUN_ID):
            pass


def test_opening_in_a_missing_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(RunStoreNotFoundError):
        with open_run_store(tmp_path / "absent", RUN_ID, create=True):
            pass


def test_opening_a_store_under_the_wrong_run_id_is_refused(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)

    with pytest.raises(RunIdentityError):
        with open_run_store(directory, "run_0002"):
            pass


def test_a_run_directory_must_be_a_concrete_path(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)

    with pytest.raises(RunStoreError):
        with open_run_store(str(directory), RUN_ID):  # type: ignore[arg-type]
            pass


# --- append-only evaluations ----------------------------------------------


def test_appended_evaluations_chain_to_their_predecessor(tmp_path: Path) -> None:
    directory = _run_directory(tmp_path)

    with open_run_store(directory, RUN_ID, create=True) as store:
        first = store.append_evaluation("iris", "mlp_baseline", "accuracy", 0.91)
        second = store.append_evaluation("iris", "evonn_prism", "accuracy", 0.94)

        assert [first.sequence, second.sequence] == [0, 1]
        assert first.previous_sha256 == "0" * 64
        assert second.previous_sha256 == first.row_sha256
        assert store.verify_evaluation_chain() == 2


def test_evaluations_survive_a_reopen_in_order(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)

    with open_run_store(directory, RUN_ID) as store:
        rows = store.evaluations()

    assert [row.sequence for row in rows] == [0, 1, 2]
    assert [row.benchmark_id for row in rows] == ["iris", "iris", "wine"]


def test_appending_continues_the_chain_across_sessions(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)

    with open_run_store(directory, RUN_ID) as store:
        previous_tip = store.evaluations()[-1].row_sha256
        row = store.append_evaluation("wine", "evonn_prism", "accuracy", 0.9)

        assert row.sequence == 3
        assert row.previous_sha256 == previous_tip
        assert store.verify_evaluation_chain() == 4


def test_an_edited_evaluation_row_is_detected(tmp_path: Path) -> None:
    """Editing evidence in place must not survive verification."""

    directory = _seeded(tmp_path)
    _raw(directory, "UPDATE evaluations SET metric_value = 0.99 WHERE sequence = 1")

    with open_run_store(directory, RUN_ID) as store:
        with pytest.raises(EvaluationChainError):
            store.verify_evaluation_chain()


def test_a_deleted_evaluation_row_is_detected(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)
    _raw(directory, "DELETE FROM evaluations WHERE sequence = 1")

    with open_run_store(directory, RUN_ID) as store:
        with pytest.raises(EvaluationChainError):
            store.verify_evaluation_chain()


def test_a_truncated_tail_of_evaluations_is_detected(tmp_path: Path) -> None:
    """Dropping the newest rows leaves a shorter chain that is still valid.

    This is why the expected length and tip are recorded outside the chain: a
    hash chain on its own cannot tell a complete run from a truncated one.
    """

    directory = _seeded(tmp_path)
    _raw(directory, "DELETE FROM evaluations WHERE sequence = 2")

    with open_run_store(directory, RUN_ID) as store:
        with pytest.raises(EvaluationChainError):
            store.verify_evaluation_chain()


def test_an_appended_row_the_run_record_does_not_know_about_is_detected(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)
    with open_run_store(directory, RUN_ID) as store:
        tip = store.evaluations()[-1].row_sha256
    _raw(
        directory,
        "INSERT INTO evaluations VALUES (3, 'wine', 'evonn_prism', 'accuracy', 0.5, '"
        + tip
        + "', '"
        + "c" * 64
        + "')",
    )

    with open_run_store(directory, RUN_ID) as store:
        with pytest.raises(EvaluationChainError):
            store.verify_evaluation_chain()


def test_the_run_record_tracks_the_evaluation_tip(tmp_path: Path) -> None:
    directory = _run_directory(tmp_path)

    with open_run_store(directory, RUN_ID, create=True) as store:
        assert store.run().evaluation_count == 0
        assert store.run().evaluation_tip_sha256 == "0" * 64
        row = store.append_evaluation("iris", "mlp_baseline", "accuracy", 0.91)

        assert store.run().evaluation_count == 1
        assert store.run().evaluation_tip_sha256 == row.row_sha256


def test_a_relabelled_evaluation_row_is_detected(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)
    _raw(directory, "UPDATE evaluations SET contender_id = 'other_engine' WHERE sequence = 0")

    with open_run_store(directory, RUN_ID) as store:
        with pytest.raises(EvaluationChainError):
            store.verify_evaluation_chain()


def test_a_reordered_chain_is_detected(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)
    _raw(directory, "UPDATE evaluations SET previous_sha256 = '" + DIGEST + "' WHERE sequence = 2")

    with open_run_store(directory, RUN_ID) as store:
        with pytest.raises(EvaluationChainError):
            store.verify_evaluation_chain()


def test_metric_values_must_be_exact_floats(tmp_path: Path) -> None:
    directory = _run_directory(tmp_path)

    with open_run_store(directory, RUN_ID, create=True) as store:
        with pytest.raises(RunStoreError):
            store.append_evaluation("iris", "mlp_baseline", "accuracy", 1)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("benchmark_id", "contender_id", "metric_name"),
    [
        ("Iris", "mlp_baseline", "accuracy"),
        ("iris", "MLP-Baseline", "accuracy"),
        ("iris", "mlp_baseline", "Accuracy"),
    ],
)
def test_evaluation_identifiers_must_be_canonical(
    tmp_path: Path, benchmark_id: str, contender_id: str, metric_name: str
) -> None:
    directory = _run_directory(tmp_path)

    with open_run_store(directory, RUN_ID, create=True) as store:
        with pytest.raises(ValueError):
            store.append_evaluation(benchmark_id, contender_id, metric_name, 0.5)


def test_evaluation_rows_are_frozen() -> None:
    row = EvaluationRow(
        sequence=0,
        benchmark_id="iris",
        contender_id="mlp_baseline",
        metric_name="accuracy",
        metric_value=0.5,
        previous_sha256="0" * 64,
        row_sha256=DIGEST,
    )

    with pytest.raises(ValidationError):
        row.metric_value = 0.9  # type: ignore[misc]


# --- artifacts and metadata -----------------------------------------------


def test_artifacts_round_trip_in_path_order(tmp_path: Path) -> None:
    directory = _run_directory(tmp_path)

    with open_run_store(directory, RUN_ID, create=True) as store:
        store.record_artifact("summary.json", 12, DIGEST)
        store.record_artifact("config.yaml", 34, "b" * 64)

        assert [row.path for row in store.artifacts()] == ["config.yaml", "summary.json"]


def test_recording_an_artifact_twice_replaces_it(tmp_path: Path) -> None:
    directory = _run_directory(tmp_path)

    with open_run_store(directory, RUN_ID, create=True) as store:
        store.record_artifact("summary.json", 12, DIGEST)
        store.record_artifact("summary.json", 99, "b" * 64)

        assert store.artifacts() == (ArtifactRow(path="summary.json", size_bytes=99, sha256="b" * 64),)


@pytest.mark.parametrize("path", ["/absolute.json", "../escape.json", "nested/../escape.json", ""])
def test_artifact_paths_must_stay_inside_the_run(tmp_path: Path, path: str) -> None:
    directory = _run_directory(tmp_path)

    with open_run_store(directory, RUN_ID, create=True) as store:
        with pytest.raises(ValidationError):
            store.record_artifact(path, 1, DIGEST)


def test_metadata_round_trips_in_key_order(tmp_path: Path) -> None:
    directory = _run_directory(tmp_path)

    with open_run_store(directory, RUN_ID, create=True) as store:
        store.set_metadata("engine", "prism")
        store.set_metadata("backend", "mlx")

        assert list(store.metadata()) == ["backend", "engine"]
        assert store.metadata()["engine"] == "prism"


# --- single-writer ownership ----------------------------------------------


def test_a_second_writer_is_refused_while_the_first_holds_the_lock(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)

    with open_run_store(directory, RUN_ID):
        with pytest.raises(RunStoreLockedError):
            with open_run_store(directory, RUN_ID):
                pass


def test_the_lock_is_released_when_the_context_exits(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)

    with open_run_store(directory, RUN_ID):
        pass
    with open_run_store(directory, RUN_ID) as store:
        assert store.recovered_stale_lock is False


def test_the_lock_record_is_cleared_on_a_clean_release(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)

    with open_run_store(directory, RUN_ID):
        pass

    assert read_lock_owner(directory) is None


def test_the_lock_record_names_the_holder_while_held(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)

    with open_run_store(directory, RUN_ID):
        owner = read_lock_owner(directory)

    assert owner is not None
    assert owner.pid == os.getpid()
    assert len(owner.process_token) == 32


def test_a_stale_record_alone_does_not_confer_ownership(tmp_path: Path) -> None:
    """A record naming a live PID must not block a writer that can take the lock.

    PIDs are recycled and records outlive their processes, so ownership is
    decided by the advisory lock and never by the contents of the file.
    """

    directory = _seeded(tmp_path)
    impostor = LockOwner(host="somewhere", platform=sys.platform, pid=os.getpid(), process_token="0" * 32)
    (directory / LOCK_FILENAME).write_bytes(impostor.model_dump_json().encode("utf-8"))

    with open_run_store(directory, RUN_ID) as store:
        assert store.recovered_stale_lock is True


def test_a_writer_killed_without_releasing_leaves_a_recoverable_lock(tmp_path: Path) -> None:
    """The crash case: a writer dies mid-run and the next one must take over."""

    directory = _seeded(tmp_path)
    ready = tmp_path / "ready"
    script = textwrap.dedent(
        f"""
        from pathlib import Path
        import time
        from evonn_shared.run_store import open_run_store

        with open_run_store(Path({str(directory)!r}), {RUN_ID!r}):
            Path({str(ready)!r}).write_text("held")
            time.sleep(120)
        """
    )
    process = subprocess.Popen([sys.executable, "-c", script])
    try:
        deadline = time.monotonic() + 60
        while not ready.exists():
            assert process.poll() is None, "lock holder exited early"
            assert time.monotonic() < deadline, "lock holder never acquired the lock"
            time.sleep(0.05)

        with pytest.raises(RunStoreLockedError):
            with open_run_store(directory, RUN_ID):
                pass

        process.send_signal(signal.SIGKILL)
        process.wait(timeout=60)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=60)

    with open_run_store(directory, RUN_ID) as store:
        assert store.recovered_stale_lock is True
        assert store.verify_evaluation_chain() == 3


def test_a_recovered_writer_reports_a_clean_lock_on_the_next_open(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)
    (directory / LOCK_FILENAME).write_bytes(b"{}")

    with open_run_store(directory, RUN_ID) as store:
        assert store.recovered_stale_lock is True
    with open_run_store(directory, RUN_ID) as store:
        assert store.recovered_stale_lock is False


def test_an_unreadable_lock_record_does_not_hide_the_holder(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)
    (directory / LOCK_FILENAME).write_bytes(b"not json")

    with pytest.raises(RunStoreError):
        read_lock_owner(directory)


def test_the_lock_owner_of_an_untouched_run_is_absent(tmp_path: Path) -> None:
    assert read_lock_owner(_run_directory(tmp_path)) is None


def test_lock_owner_records_reject_malformed_tokens() -> None:
    with pytest.raises(ValidationError):
        LockOwner(host="h", platform="linux", pid=1, process_token="short")


def test_the_lock_record_is_valid_json_while_held(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)

    with open_run_store(directory, RUN_ID):
        payload = json.loads((directory / LOCK_FILENAME).read_text(encoding="utf-8"))

    assert set(payload) == {"host", "platform", "pid", "process_token"}
