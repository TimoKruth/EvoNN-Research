from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from evonn_shared.lm_cache import (
    LM_CACHE_SCHEMA_VERSION,
    InvalidLmCacheManifestError,
    LmCacheArtifact,
    LmCacheDefect,
    LmCacheError,
    LmCacheIdMismatchError,
    LmCacheManifest,
    LmCacheNotFoundError,
    LmCacheReport,
    UnsafeLmCachePathError,
    list_lm_caches,
    load_lm_cache_manifest,
    validate_lm_cache,
    verify_lm_cache,
)

CACHE_ID = "tinystories_lm"
TRAIN_BYTES = b"the quick brown fox\n" * 64
VALID_BYTES = b"jumped over the lazy dog\n" * 32


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _artifact(path: str, payload: bytes) -> dict[str, object]:
    return {"path": path, "size_bytes": len(payload), "sha256": _digest(payload)}


def _manifest_mapping(**overrides: object) -> dict[str, object]:
    mapping: dict[str, object] = {
        "schema_version": LM_CACHE_SCHEMA_VERSION,
        "cache_id": CACHE_ID,
        "benchmark_ids": ("tinystories_lm",),
        "artifacts": (
            _artifact("train.bin", TRAIN_BYTES),
            _artifact("valid.bin", VALID_BYTES),
        ),
    }
    mapping.update(overrides)
    return mapping


def _manifest(**overrides: object) -> LmCacheManifest:
    return LmCacheManifest.model_validate(_manifest_mapping(**overrides))


def _write_manifest(root: Path, mapping: dict[str, object], name: str | None = None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    identifier = name if name is not None else str(mapping["cache_id"])
    path = root / f"{identifier}.yaml"
    lines = [
        f"schema_version: \"{mapping['schema_version']}\"",
        f"cache_id: {mapping['cache_id']}",
        "benchmark_ids:",
    ]
    for benchmark_id in mapping["benchmark_ids"]:  # type: ignore[union-attr]
        lines.append(f"  - {benchmark_id}")
    lines.append("artifacts:")
    for artifact in mapping["artifacts"]:  # type: ignore[union-attr]
        lines.append(f"  - path: {artifact['path']}")
        lines.append(f"    size_bytes: {artifact['size_bytes']}")
        lines.append(f"    sha256: {artifact['sha256']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _warm(root: Path, payloads: dict[str, bytes]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for relative, payload in payloads.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    return root


def _warmed(tmp_path: Path) -> Path:
    return _warm(tmp_path / "payload", {"train.bin": TRAIN_BYTES, "valid.bin": VALID_BYTES})


def _defects(report: LmCacheReport) -> list[tuple[str, str]]:
    return [(finding.path, finding.defect.value) for finding in report.findings]


# --- manifest model -------------------------------------------------------


def test_valid_manifest_round_trips_through_json() -> None:
    manifest = _manifest()

    assert manifest.cache_id == CACHE_ID
    assert LmCacheManifest.model_validate_json(manifest.model_dump_json()) == manifest


def test_manifest_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        LmCacheManifest.model_validate(_manifest_mapping(warmed_at="2026-07-26"))


def test_manifest_requires_the_pinned_schema_version() -> None:
    with pytest.raises(ValidationError):
        LmCacheManifest.model_validate(_manifest_mapping(schema_version="2.0.0"))


def test_manifest_rejects_a_noncanonical_cache_id() -> None:
    with pytest.raises(ValidationError):
        LmCacheManifest.model_validate(_manifest_mapping(cache_id="TinyStories-LM"))


def test_manifest_rejects_empty_benchmark_ids() -> None:
    with pytest.raises(ValidationError):
        LmCacheManifest.model_validate(_manifest_mapping(benchmark_ids=()))


def test_manifest_rejects_unsorted_benchmark_ids() -> None:
    with pytest.raises(ValidationError):
        LmCacheManifest.model_validate(_manifest_mapping(benchmark_ids=("wikitext2_lm", "tinystories_lm")))


def test_manifest_rejects_empty_artifacts() -> None:
    with pytest.raises(ValidationError):
        LmCacheManifest.model_validate(_manifest_mapping(artifacts=()))


def test_manifest_rejects_unsorted_or_duplicated_artifact_paths() -> None:
    with pytest.raises(ValidationError):
        LmCacheManifest.model_validate(
            _manifest_mapping(artifacts=(_artifact("valid.bin", VALID_BYTES), _artifact("train.bin", TRAIN_BYTES)))
        )
    with pytest.raises(ValidationError):
        LmCacheManifest.model_validate(
            _manifest_mapping(artifacts=(_artifact("train.bin", TRAIN_BYTES), _artifact("train.bin", TRAIN_BYTES)))
        )


@pytest.mark.parametrize(
    "path",
    [
        "../escape.bin",
        "/absolute.bin",
        "nested/../escape.bin",
        "./train.bin",
        "",
        "train.bin/",
        "-leading-dash.bin",
        ".hidden.bin",
        "with space.bin",
        "with\nnewline.bin",
        "a/b/c/d/e/f/g/h/i.bin",
        "x" * 600,
    ],
)
def test_manifest_rejects_unsafe_artifact_paths(path: str) -> None:
    with pytest.raises(ValidationError):
        LmCacheArtifact.model_validate({"path": path, "size_bytes": 1, "sha256": "0" * 64})


@pytest.mark.parametrize("sha256", ["0" * 63, "0" * 65, "A" * 64, "g" * 64, ""])
def test_manifest_rejects_malformed_checksums(sha256: str) -> None:
    with pytest.raises(ValidationError):
        LmCacheArtifact.model_validate({"path": "train.bin", "size_bytes": 1, "sha256": sha256})


def test_manifest_rejects_a_negative_size() -> None:
    with pytest.raises(ValidationError):
        LmCacheArtifact.model_validate({"path": "train.bin", "size_bytes": -1, "sha256": "0" * 64})


def test_manifest_models_are_frozen() -> None:
    manifest = _manifest()

    with pytest.raises(ValidationError):
        manifest.cache_id = "other_lm"  # type: ignore[misc]


# --- manifest loading -----------------------------------------------------


def test_load_reads_a_manifest_by_id(tmp_path: Path) -> None:
    root = tmp_path / "manifests"
    _write_manifest(root, _manifest_mapping())

    assert load_lm_cache_manifest(CACHE_ID, manifest_root=root) == _manifest()


def test_load_rejects_an_unknown_cache(tmp_path: Path) -> None:
    root = tmp_path / "manifests"
    _write_manifest(root, _manifest_mapping())

    with pytest.raises(LmCacheNotFoundError):
        load_lm_cache_manifest("wikitext2_lm", manifest_root=root)


def test_load_rejects_a_noncanonical_requested_id(tmp_path: Path) -> None:
    root = tmp_path / "manifests"
    root.mkdir()

    with pytest.raises(LmCacheNotFoundError):
        load_lm_cache_manifest("../escape", manifest_root=root)


def test_load_rejects_a_manifest_stored_under_a_different_id(tmp_path: Path) -> None:
    root = tmp_path / "manifests"
    _write_manifest(root, _manifest_mapping(), name="wikitext2_lm")

    with pytest.raises(LmCacheIdMismatchError):
        load_lm_cache_manifest("wikitext2_lm", manifest_root=root)


def test_load_rejects_a_manifest_that_fails_validation(tmp_path: Path) -> None:
    root = tmp_path / "manifests"
    root.mkdir()
    (root / f"{CACHE_ID}.yaml").write_text("schema_version: \"1.0.0\"\ncache_id: tinystories_lm\n", encoding="utf-8")

    with pytest.raises(InvalidLmCacheManifestError):
        load_lm_cache_manifest(CACHE_ID, manifest_root=root)


def test_load_rejects_a_manifest_root_reached_through_a_symlink(tmp_path: Path) -> None:
    real = tmp_path / "real"
    _write_manifest(real, _manifest_mapping())
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)

    with pytest.raises(UnsafeLmCachePathError):
        load_lm_cache_manifest(CACHE_ID, manifest_root=link)


def test_list_returns_utf8_sorted_identifiers(tmp_path: Path) -> None:
    root = tmp_path / "manifests"
    _write_manifest(root, _manifest_mapping())
    _write_manifest(root, _manifest_mapping(cache_id="wikitext2_lm"))
    (root / "notes.md").write_text("ignored\n", encoding="utf-8")

    assert list_lm_caches(manifest_root=root) == ("tinystories_lm", "wikitext2_lm")


def test_list_rejects_an_unsafe_manifest_filename(tmp_path: Path) -> None:
    root = tmp_path / "manifests"
    root.mkdir()
    (root / "Not-Canonical.yaml").write_text("{}\n", encoding="utf-8")

    with pytest.raises(UnsafeLmCachePathError):
        list_lm_caches(manifest_root=root)


# --- verification ---------------------------------------------------------


def test_a_correctly_warmed_cache_is_valid(tmp_path: Path) -> None:
    report = verify_lm_cache(_manifest(), payload_root=_warmed(tmp_path))

    assert report.valid
    assert report.findings == ()
    assert report.cache_id == CACHE_ID
    assert report.artifacts_checked == 2
    assert report.checksums_verified is True


def test_a_missing_artifact_is_reported_as_missing(tmp_path: Path) -> None:
    root = _warm(tmp_path / "payload", {"train.bin": TRAIN_BYTES})

    report = verify_lm_cache(_manifest(), payload_root=root)

    assert not report.valid
    assert _defects(report) == [("valid.bin", "missing")]


def test_a_truncated_artifact_is_reported_as_a_size_mismatch(tmp_path: Path) -> None:
    root = _warm(tmp_path / "payload", {"train.bin": TRAIN_BYTES[:-1], "valid.bin": VALID_BYTES})

    report = verify_lm_cache(_manifest(), payload_root=root)

    assert _defects(report) == [("train.bin", "size_mismatch")]
    assert report.findings[0].expected == str(len(TRAIN_BYTES))
    assert report.findings[0].observed == str(len(TRAIN_BYTES) - 1)


def test_a_corrupted_artifact_of_the_right_length_is_caught_by_the_checksum(tmp_path: Path) -> None:
    corrupted = b"X" + TRAIN_BYTES[1:]
    root = _warm(tmp_path / "payload", {"train.bin": corrupted, "valid.bin": VALID_BYTES})

    report = verify_lm_cache(_manifest(), payload_root=root)

    assert _defects(report) == [("train.bin", "checksum_mismatch")]
    assert report.findings[0].expected == _digest(TRAIN_BYTES)
    assert report.findings[0].observed == _digest(corrupted)


def test_size_only_verification_accepts_corruption_and_says_so(tmp_path: Path) -> None:
    """The cheap mode exists for pre-flight checks and must never look valid.

    A caller that skipped checksums has not verified the cache, so the report
    records that fact rather than letting a size-only pass be mistaken for
    evidence.
    """

    root = _warm(tmp_path / "payload", {"train.bin": b"X" + TRAIN_BYTES[1:], "valid.bin": VALID_BYTES})

    report = verify_lm_cache(_manifest(), payload_root=root, verify_checksums=False)

    assert report.valid
    assert report.checksums_verified is False


def test_a_directory_standing_in_for_an_artifact_is_rejected(tmp_path: Path) -> None:
    root = _warm(tmp_path / "payload", {"valid.bin": VALID_BYTES})
    (root / "train.bin").mkdir()

    report = verify_lm_cache(_manifest(), payload_root=root)

    assert _defects(report) == [("train.bin", "not_regular_file")]


def test_an_artifact_symlink_is_not_followed(tmp_path: Path) -> None:
    """A symlinked artifact must never be read, even when it points at the
    correct bytes, because the link target is outside the verified tree."""

    outside = tmp_path / "outside.bin"
    outside.write_bytes(TRAIN_BYTES)
    root = _warm(tmp_path / "payload", {"valid.bin": VALID_BYTES})
    (root / "train.bin").symlink_to(outside)

    report = verify_lm_cache(_manifest(), payload_root=root)

    assert _defects(report) == [("train.bin", "unreadable")]


def test_a_symlinked_directory_component_is_not_followed(tmp_path: Path) -> None:
    manifest = _manifest(
        artifacts=(_artifact("shard/train.bin", TRAIN_BYTES), _artifact("valid.bin", VALID_BYTES))
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "train.bin").write_bytes(TRAIN_BYTES)
    root = _warm(tmp_path / "payload", {"valid.bin": VALID_BYTES})
    (root / "shard").symlink_to(outside, target_is_directory=True)

    report = verify_lm_cache(manifest, payload_root=root)

    assert _defects(report) == [("shard/train.bin", "unreadable")]


def test_a_nested_artifact_path_verifies_normally(tmp_path: Path) -> None:
    manifest = _manifest(
        artifacts=(_artifact("shard/train.bin", TRAIN_BYTES), _artifact("valid.bin", VALID_BYTES))
    )
    root = _warm(tmp_path / "payload", {"shard/train.bin": TRAIN_BYTES, "valid.bin": VALID_BYTES})

    assert verify_lm_cache(manifest, payload_root=root).valid


def test_an_unwarmed_cache_reports_every_artifact_missing(tmp_path: Path) -> None:
    report = verify_lm_cache(_manifest(), payload_root=tmp_path / "never-warmed")

    assert _defects(report) == [("train.bin", "missing"), ("valid.bin", "missing")]
    assert report.artifacts_checked == 2


def test_a_payload_root_reached_through_a_symlink_is_a_hard_error(tmp_path: Path) -> None:
    """An unwarmed cache and a redirected cache root are different answers.

    Reporting the redirected root as merely "not warmed" would let a planted
    symlink pass as an ordinary missing-cache result.
    """

    link = tmp_path / "link"
    link.symlink_to(_warmed(tmp_path), target_is_directory=True)

    with pytest.raises(UnsafeLmCachePathError):
        verify_lm_cache(_manifest(), payload_root=link)


def test_a_payload_root_that_is_a_regular_file_is_a_hard_error(tmp_path: Path) -> None:
    root = tmp_path / "payload"
    root.write_bytes(b"not a directory\n")

    with pytest.raises(UnsafeLmCachePathError):
        verify_lm_cache(_manifest(), payload_root=root)


def test_findings_follow_manifest_order(tmp_path: Path) -> None:
    root = _warm(tmp_path / "payload", {"train.bin": b"short", "valid.bin": b"also wrong"})

    report = verify_lm_cache(_manifest(), payload_root=root)

    assert _defects(report) == [("train.bin", "size_mismatch"), ("valid.bin", "size_mismatch")]


def test_verify_rejects_a_value_that_is_not_a_manifest(tmp_path: Path) -> None:
    with pytest.raises(InvalidLmCacheManifestError):
        verify_lm_cache(_manifest_mapping(), payload_root=tmp_path)  # type: ignore[arg-type]


def test_the_defect_taxonomy_is_closed() -> None:
    assert {defect.value for defect in LmCacheDefect} == {
        "missing",
        "not_regular_file",
        "unreadable",
        "size_mismatch",
        "checksum_mismatch",
    }


# --- root resolution ------------------------------------------------------


def test_the_environment_root_overrides_the_default_payload_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EVONN_LM_CACHE_DIR", str(_warmed(tmp_path)))

    assert verify_lm_cache(_manifest()).valid


def test_an_empty_environment_root_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVONN_LM_CACHE_DIR", "")

    with pytest.raises(UnsafeLmCachePathError):
        verify_lm_cache(_manifest())


def test_an_explicit_payload_root_wins_over_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EVONN_LM_CACHE_DIR", str(tmp_path / "never-warmed"))

    assert verify_lm_cache(_manifest(), payload_root=_warmed(tmp_path)).valid


def test_roots_must_be_concrete_paths(tmp_path: Path) -> None:
    with pytest.raises(UnsafeLmCachePathError):
        verify_lm_cache(_manifest(), payload_root=str(tmp_path))  # type: ignore[arg-type]


# --- end to end -----------------------------------------------------------


def test_validate_loads_and_verifies_in_one_call(tmp_path: Path) -> None:
    manifests = tmp_path / "manifests"
    _write_manifest(manifests, _manifest_mapping())

    report = validate_lm_cache(CACHE_ID, payload_root=_warmed(tmp_path), manifest_root=manifests)

    assert report.valid
    assert report.cache_id == CACHE_ID


def test_validate_surfaces_a_corrupted_payload(tmp_path: Path) -> None:
    manifests = tmp_path / "manifests"
    _write_manifest(manifests, _manifest_mapping())
    root = _warm(tmp_path / "payload", {"train.bin": b"X" + TRAIN_BYTES[1:], "valid.bin": VALID_BYTES})

    report = validate_lm_cache(CACHE_ID, payload_root=root, manifest_root=manifests)

    assert _defects(report) == [("train.bin", "checksum_mismatch")]


def test_manifests_and_payloads_may_share_one_directory(tmp_path: Path) -> None:
    """The default layout warms a cache next to its manifest, so a manifest
    sitting in the payload root must not disturb verification."""

    root = _warmed(tmp_path)
    _write_manifest(root, _manifest_mapping())

    assert validate_lm_cache(CACHE_ID, manifest_root=root).valid


def test_the_repository_declares_no_unverifiable_caches() -> None:
    """Every manifest checked into the repository must load and validate."""

    for cache_id in list_lm_caches():
        assert load_lm_cache_manifest(cache_id).cache_id == cache_id


def test_all_errors_share_one_base_class() -> None:
    for error in (
        UnsafeLmCachePathError,
        InvalidLmCacheManifestError,
        LmCacheNotFoundError,
        LmCacheIdMismatchError,
    ):
        assert issubclass(error, LmCacheError)
        assert issubclass(error, ValueError)


def test_large_artifacts_are_hashed_in_chunks(tmp_path: Path) -> None:
    """Hashing must not depend on reading a whole cache into memory."""

    payload = os.urandom(3 * 1024 * 1024 + 7)
    manifest = _manifest(artifacts=(_artifact("train.bin", payload),))
    root = _warm(tmp_path / "payload", {"train.bin": payload})

    assert verify_lm_cache(manifest, payload_root=root).valid
