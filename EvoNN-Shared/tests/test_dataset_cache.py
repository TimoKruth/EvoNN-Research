import hashlib
import io

import numpy as np
import pytest

from evonn_shared.canonical import canonical_sha256
from evonn_shared.dataset_cache import verify_split_cache


def test_numeric_cache_wire_verification_matches_reference_array_digest(tmp_path):
    arrays = {"x_train": np.ones((3, 2), dtype=np.float32), "y_train": np.zeros(3, dtype=np.int64),
              "x_validation": np.ones((2, 2), dtype=np.float32), "y_validation": np.ones(2, dtype=np.int64)}
    refs = []
    for name, array in arrays.items():
        buffer = io.BytesIO()
        np.save(buffer, array, allow_pickle=False)
        payload = buffer.getvalue()
        (tmp_path / (name + ".npy")).write_bytes(payload)
        refs.append({"path": name + ".npy", "sha256": hashlib.sha256(payload).hexdigest(), "size_bytes": len(payload)})
    digest = canonical_sha256({name: {"dtype": array.dtype.str, "shape": tuple(array.shape), "bytes": array.tobytes()}
                              for name, array in arrays.items()}, schema_version="evonn-dataset-arrays-v1", digest_field=None)
    provenance = {"cache_directory": str(tmp_path), "cache_artifacts": refs, "split_sha256": digest}
    assert verify_split_cache(provenance, feature_count=2, regression=False) == digest
    with pytest.raises(ValueError, match="dimensions"):
        verify_split_cache(provenance, feature_count=3, regression=False)
    with pytest.raises(ValueError, match="digest"):
        verify_split_cache({**provenance, "split_sha256": "0" * 64}, feature_count=2, regression=False)
    bad = b"not an NPY array"
    (tmp_path / refs[0]["path"]).write_bytes(bad)
    refs[0].update(sha256=hashlib.sha256(bad).hexdigest(), size_bytes=len(bad))
    with pytest.raises(ValueError, match="format"):
        verify_split_cache(provenance, feature_count=2, regression=False)
