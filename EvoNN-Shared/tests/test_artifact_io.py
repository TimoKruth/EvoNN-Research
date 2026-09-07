import hashlib
from pathlib import Path

import pytest

from evonn_shared.artifact_io import (
    create_artifact_directory, publish_artifact, publish_artifact_directory, read_verified_artifact,
)
from evonn_shared.telemetry import ArtifactReference


def test_verified_bytes_and_non_overwriting_publication(tmp_path: Path):
    reference = publish_artifact(tmp_path / "data.bin", b"1234")
    assert read_verified_artifact(tmp_path, reference, size_bytes=4) == b"1234"
    with pytest.raises(FileExistsError):
        publish_artifact(tmp_path / "data.bin", b"replacement")
    (tmp_path / "data.bin").write_bytes(b"4321")
    with pytest.raises(ValueError, match="content mismatch"):
        read_verified_artifact(tmp_path, reference)


def test_verification_rejects_wrong_size_limit_and_symlink(tmp_path: Path):
    reference = publish_artifact(tmp_path / "data.bin", b"1234")
    for options in ({"size_bytes": 3}, {"max_bytes": 3}):
        with pytest.raises(ValueError, match="size"):
            read_verified_artifact(tmp_path, reference, **options)
    (tmp_path / "link").symlink_to(tmp_path / "data.bin")
    reference = ArtifactReference(path="link", sha256=hashlib.sha256(b"1234").hexdigest())
    with pytest.raises(OSError):
        read_verified_artifact(tmp_path, reference)


def test_directory_creation_never_follows_a_symlink(tmp_path: Path):
    target = create_artifact_directory(tmp_path / "real")
    (tmp_path / "alias").symlink_to(target, target_is_directory=True)
    with pytest.raises(OSError):
        create_artifact_directory(tmp_path / "alias" / "new")
    assert not (target / "new").exists()


def test_complete_directory_publication_refuses_existing_evidence(tmp_path: Path):
    staging = create_artifact_directory(tmp_path / "staging")
    reference = publish_artifact(staging / "complete.json", b"{}")
    destination = tmp_path / "final"
    publish_artifact_directory(staging, destination)
    assert not staging.exists()
    assert read_verified_artifact(destination, reference) == b"{}"
    create_artifact_directory(staging)
    publish_artifact(staging / "different.json", b"different")
    with pytest.raises(FileExistsError):
        publish_artifact_directory(staging, destination)
    assert (destination / "complete.json").read_bytes() == b"{}"
    assert (staging / "different.json").read_bytes() == b"different"


def test_append_artifact_preserves_prior_bytes_and_rejects_stale_source(tmp_path):
    import hashlib
    from evonn_shared.artifact_io import append_artifact
    path = tmp_path / "trend.jsonl"
    path.write_bytes(b'{}\n')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    append_artifact(path, b'{"run":2}\n', expected_sha256=digest)
    assert path.read_bytes() == b'{}\n{"run":2}\n'
    with pytest.raises(ValueError, match="source changed"):
        append_artifact(path, b'{}\n', expected_sha256=digest)
    actual = tmp_path / "actual"
    path.rename(actual)
    path.symlink_to(actual)
    with pytest.raises(OSError):
        append_artifact(path, b'{}\n', expected_sha256=digest)
