"""Current runtime declarations; historical B0 evidence remains immutable."""

from copy import deepcopy

from .backend_contract import EXPECTED_MANIFESTS as B0_MANIFESTS

CURRENT_CAPABILITIES_VERSION = "3.0.0"
EXPECTED_MANIFESTS = deepcopy(B0_MANIFESTS)
EXPECTED_MANIFESTS["EvoNN-Contenders/backend-capabilities.json"] = {
    "schema_version": "1.0.0",
    "system": "contenders",
    "runtime_role": "fixed_pool_contender",
    "capabilities": [
        {
            "id": "sklearn_contender",
            "platforms": ["darwin", "linux"],
            "implemented": True,
            "dependency": "scikit-learn",
            "dependency_condition": "Pinned required CPU runtime; optional boosted and torch pressure is reported separately. No scientific qualification.",
        }
    ],
    "evidence": {"scientific": False, "portability": False, "producer_conformance": False},
}

EXPECTED_MANIFESTS["EvoNN-Prism/backend-capabilities.json"] = {
    "schema_version": "1.0.0",
    "system": "prism",
    "runtime_role": "evolutionary_engine",
    "capabilities": [
        {
            "id": "mlx_native",
            "platforms": ["darwin-arm64"],
            "implemented": True,
            "dependency": "mlx",
            "dependency_condition": "Package-local differentiated models and bounded search; native Apple Silicon execution.",
        },
        {
            "id": "numpy_fallback",
            "platforms": ["darwin", "linux"],
            "implemented": True,
            "dependency": "numpy",
            "dependency_condition": "Package-local differentiated models and bounded search; portability-only evidence, separate from native cohorts.",
        },
    ],
    "evidence": {"scientific": False, "portability": False, "producer_conformance": False},
}

EXPECTED_MANIFESTS["EvoNN-Topograph/backend-capabilities.json"] = {
    "schema_version": "1.0.0",
    "system": "topograph",
    "runtime_role": "evolutionary_engine",
    "capabilities": [
        {
            "id": "mlx_native",
            "platforms": ["darwin-arm64"],
            "implemented": True,
            "dependency": "mlx",
            "dependency_condition": "Package-local differentiated models and bounded search; native Apple Silicon execution.",
        },
        {
            "id": "numpy_fallback",
            "platforms": ["darwin", "linux"],
            "implemented": True,
            "dependency": "numpy",
            "dependency_condition": "Package-local differentiated models and bounded search; portability-only evidence, separate from native cohorts.",
        },
    ],
    "evidence": {"scientific": False, "portability": False, "producer_conformance": False},
}
