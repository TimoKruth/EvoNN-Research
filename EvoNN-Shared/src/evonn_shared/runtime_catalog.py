"""Pinned runtime manifests selected per dataset; Phase-1 bytes remain intact."""
import json
from .artifact_io import read_verified_artifact
from .benchmarks import resolve_data_root
from .telemetry import ArtifactReference

CORE_RUNTIME_SHA256 = "c649dbc90ee017a34fb91722e7e238baa56a8de30a068e81bd7998dcd1a924a4"
PHASE4_RUNTIME_SHA256 = "8810cfaf34fd9d07241e724c30559d0823456f75506a5c2d0d5fba3bad38df45"


def runtime_manifest(benchmark_id, *, root=None):
    extended=benchmark_id in {"banknote_classification", "shakespeare_byte_lm"}
    path="runtime/phase4_v1.json" if extended else "runtime/tier1_core_v1.json"
    sha=PHASE4_RUNTIME_SHA256 if extended else CORE_RUNTIME_SHA256
    payload=read_verified_artifact(root if root is not None else resolve_data_root(),ArtifactReference(path=path,sha256=sha),max_bytes=256*1024)
    manifest=json.loads(payload)
    if benchmark_id not in manifest["benchmarks"]:
        raise ValueError("dataset lacks a pinned runtime binding")
    return payload,manifest
