from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from evonn_shared.checkpoints import (
    CHECKPOINT_SCHEMA_VERSION,
    MANIFEST_FILENAME,
    CheckpointError,
    CheckpointManifest,
    CheckpointNotFoundError,
    CheckpointPublication,
    CheckpointRecord,
    CheckpointSequenceError,
    CorruptCheckpointError,
    InvalidCheckpointManifestError,
    UnsafeCheckpointPathError,
    create_checkpoint_directory,
    discard_orphaned_staging,
    load_latest_checkpoint,
    publish_checkpoint,
    read_checkpoint_manifest,
)

RUN_ID = "run_0001"
FIRST = b"generation one weights\n" * 8
SECOND = b"generation two weights\n" * 8
THIRD = b"generation three weights\n" * 8


def _directory(tmp_path: Path) -> Path:
    return create_checkpoint_directory(tmp_path)


def _seeded(tmp_path: Path) -> Path:
    directory = _directory(tmp_path)
    publish_checkpoint(directory, RUN_ID, "gen_0001", FIRST)
    return directory


def _staging_names(directory: Path) -> list[str]:
    return sorted(entry.name for entry in directory.iterdir() if entry.name.startswith(".") and ".tmp-" in entry.name)


def _authoritative(directory: Path) -> str:
    record, _ = load_latest_checkpoint(directory)
    return record.checkpoint_id


# --- models ---------------------------------------------------------------


def _record_mapping(**overrides: object) -> dict[str, object]:
    mapping: dict[str, object] = {
        "checkpoint_id": "gen_0001",
        "sequence": 0,
        "payload_path": "gen_0001.ckpt",
        "size_bytes": len(FIRST),
        "sha256": hashlib.sha256(FIRST).hexdigest(),
        "previous_sha256": None,
    }
    mapping.update(overrides)
    return mapping


def test_a_valid_record_round_trips_through_json() -> None:
    record = CheckpointRecord.model_validate(_record_mapping())

    assert CheckpointRecord.model_validate_json(record.model_dump_json()) == record


@pytest.mark.parametrize(
    "overrides",
    [
        {"checkpoint_id": "Gen-0001"},
        {"sequence": -1},
        {"payload_path": "gen_0001.bin"},
        {"payload_path": "../escape.ckpt"},
        {"sha256": "0" * 63},
        {"sha256": "A" * 64},
        {"previous_sha256": "not a digest"},
        {"size_bytes": -1},
        {"unexpected": "field"},
    ],
)
def test_records_reject_malformed_fields(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CheckpointRecord.model_validate(_record_mapping(**overrides))


def test_records_are_frozen() -> None:
    record = CheckpointRecord.model_validate(_record_mapping())

    with pytest.raises(ValidationError):
        record.sequence = 5  # type: ignore[misc]


def test_manifests_require_the_pinned_schema_version() -> None:
    with pytest.raises(ValidationError):
        CheckpointManifest.model_validate(
            {
                "schema_version": "2.0.0",
                "run_id": RUN_ID,
                "latest": _record_mapping(),
            }
        )


# --- empty directory ------------------------------------------------------


def test_an_empty_directory_has_no_committed_manifest(tmp_path: Path) -> None:
    assert read_checkpoint_manifest(_directory(tmp_path)) is None


def test_loading_from_an_empty_directory_reports_no_checkpoint(tmp_path: Path) -> None:
    with pytest.raises(CheckpointNotFoundError):
        load_latest_checkpoint(_directory(tmp_path))


# --- publication ----------------------------------------------------------


def test_publishing_makes_a_checkpoint_authoritative(tmp_path: Path) -> None:
    directory = _directory(tmp_path)

    record = publish_checkpoint(directory, RUN_ID, "gen_0001", FIRST)

    assert record.sequence == 0
    assert record.previous_sha256 is None
    assert record.sha256 == hashlib.sha256(FIRST).hexdigest()
    assert record.size_bytes == len(FIRST)
    assert load_latest_checkpoint(directory) == (record, FIRST)


def test_successive_checkpoints_chain_to_their_predecessor(tmp_path: Path) -> None:
    directory = _directory(tmp_path)

    first = publish_checkpoint(directory, RUN_ID, "gen_0001", FIRST)
    second = publish_checkpoint(directory, RUN_ID, "gen_0002", SECOND)
    third = publish_checkpoint(directory, RUN_ID, "gen_0003", THIRD)

    assert [record.sequence for record in (first, second, third)] == [0, 1, 2]
    assert second.previous_sha256 == first.sha256
    assert third.previous_sha256 == second.sha256
    assert _authoritative(directory) == "gen_0003"


def test_the_manifest_names_exactly_one_authoritative_checkpoint(tmp_path: Path) -> None:
    directory = _directory(tmp_path)
    publish_checkpoint(directory, RUN_ID, "gen_0001", FIRST)
    publish_checkpoint(directory, RUN_ID, "gen_0002", SECOND)

    manifest = read_checkpoint_manifest(directory)

    assert manifest is not None
    assert manifest.schema_version == CHECKPOINT_SCHEMA_VERSION
    assert manifest.run_id == RUN_ID
    assert manifest.latest.checkpoint_id == "gen_0002"


def test_earlier_payloads_are_retained_after_a_later_commit(tmp_path: Path) -> None:
    """Superseding a checkpoint must not delete the one it replaced."""

    directory = _directory(tmp_path)
    publish_checkpoint(directory, RUN_ID, "gen_0001", FIRST)
    publish_checkpoint(directory, RUN_ID, "gen_0002", SECOND)

    assert (directory / "gen_0001.ckpt").read_bytes() == FIRST


# --- crash boundaries -----------------------------------------------------


def test_a_crash_after_staging_leaves_the_previous_checkpoint_authoritative(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)

    publication = CheckpointPublication(directory, RUN_ID, "gen_0002", SECOND)
    publication.stage()

    assert _authoritative(directory) == "gen_0001"
    assert not (directory / "gen_0002.ckpt").exists()
    assert len(_staging_names(directory)) == 1


def test_a_crash_after_the_payload_commit_leaves_the_previous_checkpoint_authoritative(
    tmp_path: Path,
) -> None:
    """The payload is durable and named, but no manifest references it yet.

    This is the transition the whole design exists for: a checkpoint becomes
    authoritative when the manifest is replaced, not when its bytes land.
    """

    directory = _seeded(tmp_path)

    publication = CheckpointPublication(directory, RUN_ID, "gen_0002", SECOND)
    publication.stage()
    publication.commit_payload()

    assert (directory / "gen_0002.ckpt").read_bytes() == SECOND
    assert _authoritative(directory) == "gen_0001"
    assert load_latest_checkpoint(directory)[1] == FIRST
    assert _staging_names(directory) == []


def test_a_crash_after_the_manifest_commit_advances_the_checkpoint(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)

    publication = CheckpointPublication(directory, RUN_ID, "gen_0002", SECOND)
    publication.stage()
    publication.commit_payload()
    publication.commit_manifest()

    assert _authoritative(directory) == "gen_0002"
    assert load_latest_checkpoint(directory)[1] == SECOND


def test_a_crash_before_the_first_commit_leaves_no_checkpoint_at_all(tmp_path: Path) -> None:
    directory = _directory(tmp_path)

    publication = CheckpointPublication(directory, RUN_ID, "gen_0001", FIRST)
    publication.stage()
    publication.commit_payload()

    assert (directory / "gen_0001.ckpt").read_bytes() == FIRST
    with pytest.raises(CheckpointNotFoundError):
        load_latest_checkpoint(directory)


# --- recovery -------------------------------------------------------------


def test_an_interrupted_publication_can_be_completed_by_retrying_it(tmp_path: Path) -> None:
    """A crash between the payload and manifest commits must be recoverable.

    Refusing the retry would strand that checkpoint id forever, which would in
    turn make resume-equals-uninterrupted unprovable.
    """

    directory = _seeded(tmp_path)
    interrupted = CheckpointPublication(directory, RUN_ID, "gen_0002", SECOND)
    interrupted.stage()
    interrupted.commit_payload()

    record = publish_checkpoint(directory, RUN_ID, "gen_0002", SECOND)

    assert record.sequence == 1
    assert record.previous_sha256 == hashlib.sha256(FIRST).hexdigest()
    assert _authoritative(directory) == "gen_0002"


def test_a_retry_with_different_bytes_under_the_same_id_is_refused(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)
    interrupted = CheckpointPublication(directory, RUN_ID, "gen_0002", SECOND)
    interrupted.stage()
    interrupted.commit_payload()

    with pytest.raises(CheckpointSequenceError):
        publish_checkpoint(directory, RUN_ID, "gen_0002", THIRD)

    assert _authoritative(directory) == "gen_0001"


def test_republishing_the_committed_checkpoint_is_refused(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)

    with pytest.raises(CheckpointSequenceError):
        publish_checkpoint(directory, RUN_ID, "gen_0001", FIRST)


def test_orphaned_staging_files_are_discardable_without_changing_authority(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)
    CheckpointPublication(directory, RUN_ID, "gen_0002", SECOND).stage()

    removed = discard_orphaned_staging(directory)

    assert len(removed) == 1
    assert _staging_names(directory) == []
    assert _authoritative(directory) == "gen_0001"


def test_discarding_staging_on_a_clean_directory_removes_nothing(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)

    assert discard_orphaned_staging(directory) == ()
    assert _authoritative(directory) == "gen_0001"


def test_discarding_staging_never_touches_a_committed_payload(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)
    interrupted = CheckpointPublication(directory, RUN_ID, "gen_0002", SECOND)
    interrupted.stage()
    interrupted.commit_payload()

    assert discard_orphaned_staging(directory) == ()
    assert (directory / "gen_0002.ckpt").read_bytes() == SECOND


# --- integrity ------------------------------------------------------------


def test_a_truncated_committed_payload_is_rejected(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)
    (directory / "gen_0001.ckpt").write_bytes(FIRST[:-1])

    with pytest.raises(CorruptCheckpointError):
        load_latest_checkpoint(directory)


def test_a_corrupted_payload_of_the_right_length_is_rejected(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)
    (directory / "gen_0001.ckpt").write_bytes(b"X" + FIRST[1:])

    with pytest.raises(CorruptCheckpointError):
        load_latest_checkpoint(directory)


def test_a_missing_committed_payload_is_rejected(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)
    (directory / "gen_0001.ckpt").unlink()

    with pytest.raises(CorruptCheckpointError):
        load_latest_checkpoint(directory)


def test_an_unparsable_manifest_is_rejected(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)
    (directory / MANIFEST_FILENAME).write_bytes(b"{not json")

    with pytest.raises(InvalidCheckpointManifestError):
        read_checkpoint_manifest(directory)


def test_a_manifest_failing_validation_is_rejected(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)
    payload = json.loads((directory / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    payload["latest"]["sha256"] = "not a digest"
    (directory / MANIFEST_FILENAME).write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(InvalidCheckpointManifestError):
        read_checkpoint_manifest(directory)


def test_an_oversized_manifest_is_rejected(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)
    (directory / MANIFEST_FILENAME).write_bytes(b"{" + b" " * (2 * 1024 * 1024))

    with pytest.raises(InvalidCheckpointManifestError):
        read_checkpoint_manifest(directory)


# --- path safety ----------------------------------------------------------


def test_a_symlinked_checkpoint_directory_is_refused(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)
    link = tmp_path / "link"
    link.symlink_to(directory, target_is_directory=True)

    with pytest.raises(UnsafeCheckpointPathError):
        read_checkpoint_manifest(link)


def test_a_symlinked_manifest_is_refused(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_bytes((directory / MANIFEST_FILENAME).read_bytes())
    (directory / MANIFEST_FILENAME).unlink()
    (directory / MANIFEST_FILENAME).symlink_to(outside)

    with pytest.raises(UnsafeCheckpointPathError):
        read_checkpoint_manifest(directory)


def test_a_symlinked_payload_is_refused(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)
    outside = tmp_path / "outside.ckpt"
    outside.write_bytes(FIRST)
    (directory / "gen_0001.ckpt").unlink()
    (directory / "gen_0001.ckpt").symlink_to(outside)

    with pytest.raises(UnsafeCheckpointPathError):
        load_latest_checkpoint(directory)


def test_a_checkpoint_directory_must_be_a_concrete_path(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)

    with pytest.raises(UnsafeCheckpointPathError):
        read_checkpoint_manifest(str(directory))  # type: ignore[arg-type]


def test_a_missing_checkpoint_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(UnsafeCheckpointPathError):
        read_checkpoint_manifest(tmp_path / "absent")


def test_publishing_into_another_runs_directory_is_refused(tmp_path: Path) -> None:
    directory = _seeded(tmp_path)

    with pytest.raises(CheckpointSequenceError):
        publish_checkpoint(directory, "run_0002", "gen_0002", SECOND)


# --- step ordering --------------------------------------------------------


def test_committing_a_payload_before_staging_is_refused(tmp_path: Path) -> None:
    publication = CheckpointPublication(_directory(tmp_path), RUN_ID, "gen_0001", FIRST)

    with pytest.raises(CheckpointSequenceError):
        publication.commit_payload()


def test_committing_a_manifest_before_the_payload_is_refused(tmp_path: Path) -> None:
    publication = CheckpointPublication(_directory(tmp_path), RUN_ID, "gen_0001", FIRST)
    publication.stage()

    with pytest.raises(CheckpointSequenceError):
        publication.commit_manifest()


def test_staging_twice_is_refused(tmp_path: Path) -> None:
    publication = CheckpointPublication(_directory(tmp_path), RUN_ID, "gen_0001", FIRST)
    publication.stage()

    with pytest.raises(CheckpointSequenceError):
        publication.stage()


def test_committing_a_manifest_twice_is_refused(tmp_path: Path) -> None:
    publication = CheckpointPublication(_directory(tmp_path), RUN_ID, "gen_0001", FIRST)
    publication.stage()
    publication.commit_payload()
    publication.commit_manifest()

    with pytest.raises(CheckpointSequenceError):
        publication.commit_manifest()


def test_a_payload_must_be_bytes(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        CheckpointPublication(_directory(tmp_path), RUN_ID, "gen_0001", "text")  # type: ignore[arg-type]


# --- directory creation ---------------------------------------------------


def test_creating_a_checkpoint_directory_yields_an_empty_one(tmp_path: Path) -> None:
    directory = create_checkpoint_directory(tmp_path)

    assert directory.is_dir()
    assert list(directory.iterdir()) == []


def test_creating_over_an_existing_directory_is_refused(tmp_path: Path) -> None:
    create_checkpoint_directory(tmp_path)

    with pytest.raises(UnsafeCheckpointPathError):
        create_checkpoint_directory(tmp_path)


def test_all_errors_share_one_base_class() -> None:
    for error in (
        UnsafeCheckpointPathError,
        InvalidCheckpointManifestError,
        CheckpointNotFoundError,
        CorruptCheckpointError,
        CheckpointSequenceError,
    ):
        assert issubclass(error, CheckpointError)
        assert issubclass(error, ValueError)


def test_large_payloads_survive_a_publish_and_load_round_trip(tmp_path: Path) -> None:
    payload = bytes(range(256)) * 20_000

    directory = _directory(tmp_path)
    record = publish_checkpoint(directory, RUN_ID, "gen_0001", payload)

    assert record.size_bytes == len(payload)
    assert load_latest_checkpoint(directory)[1] == payload
