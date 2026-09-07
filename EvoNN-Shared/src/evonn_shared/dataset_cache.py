"""Verify the simple numeric NumPy cache wire format without importing a runtime."""
import ast
import math
from pathlib import Path
import struct

from .artifact_io import read_verified_artifact
from .canonical import canonical_sha256
from .telemetry import ArtifactReference


def verify_split_cache(provenance: dict, *, feature_count: int, regression: bool) -> str:
    """Recompute the consumed-array digest, including dtype and shape, from checked bytes."""
    arrays = {}
    expected = {"x_train.npy": "<f4", "x_validation.npy": "<f4",
                "y_train.npy": "<f4" if regression else "<i8",
                "y_validation.npy": "<f4" if regression else "<i8"}
    if len(provenance["cache_artifacts"]) != 4:
        raise ValueError("exactly four cache artifacts required")
    for item in provenance["cache_artifacts"]:
        name = item["path"]
        if name not in expected or name.removesuffix(".npy") in arrays:
            raise ValueError("duplicate or foreign split-cache artifact")
        payload = read_verified_artifact(Path(provenance["cache_directory"]),
            ArtifactReference(path=name, sha256=item["sha256"]), size_bytes=item["size_bytes"])
        if payload[:8] != b"\x93NUMPY\x01\x00" or len(payload) < 10:
            raise ValueError("unsupported numeric cache format")
        length = struct.unpack("<H", payload[8:10])[0]
        if length > 4096 or 10 + length > len(payload):
            raise ValueError("invalid numeric cache header length")
        try:
            header = ast.literal_eval(payload[10:10 + length].decode("ascii"))
        except (UnicodeError, SyntaxError, ValueError, RecursionError) as error:
            raise ValueError("invalid numeric cache header syntax") from error
        if not isinstance(header, dict) or set(header) != {"descr", "fortran_order", "shape"}:
            raise ValueError("invalid numeric cache header")
        shape = header["shape"]
        if header["descr"] != expected[name] or header["fortran_order"] is not False:
            raise ValueError("cache dtype or storage order differs from split contract")
        if type(shape) is not tuple or not shape or any(type(size) is not int or size < 1 for size in shape):
            raise ValueError("invalid numeric cache shape")
        data = payload[10 + length:]
        if len(data) != math.prod(shape) * (4 if header["descr"] == "<f4" else 8):
            raise ValueError("numeric cache shape and bytes differ")
        if header["descr"] == "<f4" and any(not math.isfinite(value) for (value,) in struct.iter_unpack("<f", data)):
            raise ValueError("numeric cache contains non-finite values")
        arrays[name.removesuffix(".npy")] = {"dtype": header["descr"], "shape": shape, "bytes": data}
    for suffix in ("train", "validation"):
        x, y = arrays["x_" + suffix], arrays["y_" + suffix]
        if len(x["shape"]) != 2 or x["shape"][1] != feature_count or y["shape"] != (x["shape"][0],):
            raise ValueError("numeric cache task dimensions differ")
    digest = canonical_sha256(arrays, schema_version="evonn-dataset-arrays-v1", digest_field=None)
    if digest != provenance["split_sha256"]:
        raise ValueError("cache array digest differs from dataset provenance")
    return digest
