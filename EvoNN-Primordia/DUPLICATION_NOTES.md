# Package independence

The numerical autodiff boundary (`tensors.py`), optimizer (`training.py`) and
run transaction coordinator (`run.py`) start from Prism at `32cd43f`. They
remain local under the Standalone Rule; unused quantization/normalization
helpers were removed. Subsequent engine policy and artifact behavior belong
to this package. No runtime import of Prism or another engine is permitted.
Shared retains only explicit contract, data and publication infrastructure.

`datasets.py` duplicates the verified historical loader from Shared at the same revision. Primordia owns raw loading, splitting and cache publication; Shared supplies only catalog and provenance contracts. Loader compatibility is checked against the canonical dataset cache.
