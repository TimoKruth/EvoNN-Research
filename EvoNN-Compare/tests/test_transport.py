"""Move checked evidence without rewriting producer paths or relaxing integrity."""

import hashlib
import io
import json
import shutil
import tarfile

import pytest

from evonn_compare.registry import promote, validate_registry
from evonn_compare.transport import file_digest, hydrate_registry, pack_registry


def test_portable_registry_needs_no_original_paths(tmp_path, export_factory):
    source = export_factory(tmp_path / "producer" / "source")
    registry = tmp_path / "registry"
    promote(source.root, registry=registry, label="before", copy_artifacts=True)
    index = (registry / "index.jsonl").read_bytes()
    archive = tmp_path / "transport.tar.gz"
    descriptor = pack_registry(registry, archive=archive)
    relocated = tmp_path / "consumer" / "registry"
    shutil.copytree(registry, relocated)
    source.root.rename(source.root.with_name("unavailable"))
    assert validate_registry(relocated, require_artifacts=True)["status"] == "blocked"
    assert hydrate_registry(relocated, archive=archive, descriptor=descriptor)["status"] == "passed"
    assert (relocated / "index.jsonl").read_bytes() == index
    mapping = json.loads((relocated / "artifact_roots.json").read_text())
    path = relocated / mapping["roots"][str(source.root)] / "report.md"
    path.write_text("tampered")
    assert validate_registry(relocated, require_artifacts=True)["status"] == "blocked"


def test_transport_rejects_hash_mismatch_and_fully_rehashed_link(tmp_path, export_factory):
    source = export_factory(tmp_path / "source")
    registry = tmp_path / "registry"
    promote(source.root, registry=registry, label="before")
    archive = tmp_path / "transport.tar.gz"
    descriptor = pack_registry(registry, archive=archive)
    with pytest.raises(ValueError, match="checksum"):
        hydrate_registry(registry, archive=archive, descriptor={**descriptor, "archive_sha256": "0" * 64})
    malicious = tmp_path / "malicious.tar.gz"
    with tarfile.open(archive) as original, tarfile.open(malicious, "w:gz") as target:
        for member in original:
            target.addfile(member, original.extractfile(member))
        link = tarfile.TarInfo("dependencies/link")
        link.type = tarfile.SYMTYPE
        link.linkname = "/tmp/outside"
        target.addfile(link)
    sha, size = file_digest(malicious)
    with pytest.raises(ValueError, match="link or special"):
        hydrate_registry(
            registry, archive=malicious, descriptor={**descriptor, "archive_sha256": sha, "archive_size_bytes": size}
        )


def test_archive_traversal_rejected_before_publication(tmp_path, export_factory):
    source = export_factory(tmp_path / "source")
    registry = tmp_path / "registry"
    promote(source.root, registry=registry, label="before")
    archive = tmp_path / "transport.tar.gz"
    descriptor = pack_registry(registry, archive=archive)
    bad = tmp_path / "bad.tar.gz"
    with tarfile.open(bad, "w:gz") as tar:
        for name in ("transport_manifest.json", "../escape"):
            member = tarfile.TarInfo(name)
            member.size = 2
            tar.addfile(member, io.BytesIO(b"{}"))
    sha = hashlib.sha256(bad.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        hydrate_registry(
            registry,
            archive=bad,
            descriptor={**descriptor, "archive_sha256": sha, "archive_size_bytes": bad.stat().st_size},
        )
    assert not (tmp_path / "escape").exists()


def test_download_descriptor_is_validated_before_io_and_partial_is_retryable(tmp_path, monkeypatch):
    from evonn_compare.transport import hydrate_declared

    root = tmp_path / "project"
    registry = root / "evidence"
    registry.mkdir(parents=True)
    descriptor = dict(
        schema_version=1,
        archive_sha256="../../escaped",
        archive_size_bytes=10,
        index_sha256="0" * 64,
        transport_manifest_sha256="0" * 64,
        run_ids=["run"],
    )
    declaration = dict(
        url="https://github.com/TimoKruth/EvoNN-Research/releases/download/test/evidence.tar.gz", descriptor=descriptor
    )
    (registry / "source_bundle.json").write_text(json.dumps(declaration))
    requests = []

    def unavailable(*args, **kwargs):
        requests.append(args)
        raise OSError("network unavailable")

    monkeypatch.setattr("urllib.request.urlopen", unavailable)
    with pytest.raises(ValueError):
        hydrate_declared(root)
    assert not requests and not (root / ".artifacts").exists()
    declaration["descriptor"]["archive_sha256"] = "0" * 64
    (registry / "source_bundle.json").write_text(json.dumps(declaration))
    for _ in range(2):
        with pytest.raises(OSError, match="network unavailable"):
            hydrate_declared(root)
    assert len(requests) == 2
    assert not list((root / ".artifacts/evidence-transport").glob(".download_*"))


def test_receipt_only_checkout_rehydrates_snapshot_and_dependencies(tmp_path, export_factory, monkeypatch):
    from evonn_compare.transport import hydrate_declared

    source = export_factory(tmp_path / "producer" / "source")
    registry = tmp_path / "registry"
    promote(source.root, registry=registry, label="before", copy_artifacts=True)
    dependencies = tmp_path / "dependencies.tar.gz"
    descriptor = pack_registry(registry, archive=dependencies)
    (registry / "analysis-request.json").write_text(json.dumps({"materiality": 0.01}))
    snapshot = tmp_path / "registry.tar.gz"
    with tarfile.open(snapshot, "w:gz") as packed:
        for path in sorted(registry.rglob("*")):
            if path.is_file() and not path.name.startswith("."):
                packed.add(path, arcname=str(path.relative_to(registry)), recursive=False)
    prefix = "https://github.com/TimoKruth/EvoNN-Research/releases/download/test/"
    sha, size = file_digest(snapshot)
    declaration = dict(
        url=prefix + "dependencies.tar.gz",
        descriptor=descriptor,
        registry_snapshot=dict(
            url=prefix + "registry.tar.gz",
            archive_sha256=sha,
            archive_size_bytes=size,
            index_sha256=descriptor["index_sha256"],
        ),
    )
    checkout = tmp_path / "checkout"
    (checkout / "evidence").mkdir(parents=True)
    encoded = json.dumps(declaration)
    (checkout / "evidence/source_bundle.json").write_text(encoded)
    payloads = {
        prefix + "registry.tar.gz": snapshot.read_bytes(),
        prefix + "dependencies.tar.gz": dependencies.read_bytes(),
    }
    monkeypatch.setattr("urllib.request.urlopen", lambda url, **kwargs: io.BytesIO(payloads[url]))
    source.root.rename(source.root.with_name("unavailable"))
    assert hydrate_declared(checkout)["status"] == "passed"
    assert (checkout / "evidence/index.jsonl").read_bytes() == (registry / "index.jsonl").read_bytes()
    assert (checkout / "evidence/source_bundle.json").read_text() == encoded
    assert hydrate_declared(checkout)["status"] == "passed"
    (checkout / "evidence/analysis-request.json").write_text(json.dumps({"materiality": 1000}))
    with pytest.raises(ValueError, match="conflicts with declared bytes"):
        hydrate_declared(checkout)


def test_snapshot_cannot_publish_escape_or_replace_source_declaration(tmp_path):
    from evonn_compare.transport import hydrate_snapshot

    for index, name in enumerate(("../outside", "source_bundle.json", "nested/.hidden")):
        archive = tmp_path / f"bad{index}.tar.gz"
        with tarfile.open(archive, "w:gz") as packed:
            member = tarfile.TarInfo(name)
            member.size = 2
            packed.addfile(member, io.BytesIO(b"{}"))
        sha, size = file_digest(archive)
        root = tmp_path / f"registry{index}"
        root.mkdir()
        (root / "source_bundle.json").write_text("preserve")
        with pytest.raises(ValueError):
            hydrate_snapshot(
                root,
                archive,
                dict(
                    url="https://github.com/TimoKruth/EvoNN-Research/releases/download/test/snapshot.tar.gz",
                    archive_sha256=sha,
                    archive_size_bytes=size,
                    index_sha256="0" * 64,
                ),
            )
        assert (root / "source_bundle.json").read_text() == "preserve"
        assert not (root / "index.jsonl").exists()
    assert not (tmp_path / "outside").exists()


def test_snapshot_existing_symlink_cannot_create_outside_directories(tmp_path, export_factory):
    from evonn_compare.transport import hydrate_snapshot

    source = export_factory(tmp_path / "source")
    registry = tmp_path / "registry"
    promote(source.root, registry=registry, label="before", copy_artifacts=True)
    snapshot = tmp_path / "snapshot.tar.gz"
    with tarfile.open(snapshot, "w:gz") as packed:
        for path in sorted(registry.rglob("*")):
            if path.is_file() and not path.name.startswith("."):
                packed.add(path, arcname=str(path.relative_to(registry)), recursive=False)
        member = tarfile.TarInfo("extra/deeper/file.txt")
        member.size = 2
        packed.addfile(member, io.BytesIO(b"{}"))
    sha, size = file_digest(snapshot)
    destination = tmp_path / "destination"
    destination.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (destination / "extra").symlink_to(outside, target_is_directory=True)
    with pytest.raises((ValueError, OSError)):
        hydrate_snapshot(
            destination,
            snapshot,
            dict(
                url="https://github.com/TimoKruth/EvoNN-Research/releases/download/test/snapshot.tar.gz",
                archive_sha256=sha,
                archive_size_bytes=size,
                index_sha256=hashlib.sha256((registry / "index.jsonl").read_bytes()).hexdigest(),
            ),
        )
    assert not list(outside.iterdir())
    assert not (destination / "index.jsonl").exists()
