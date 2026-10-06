"""Bounded, explicit engine run configuration."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .research import ResearchPolicy
from evonn_shared.runtime_budget import MAX_ENGINE_EVALUATIONS
from evonn_shared.hierarchy_presets import standard_hierarchy_policy
from .presets import DEFAULT_BUDGET, DEFAULT_BACKEND, DEFAULT_TIMEOUT, DEFAULT_FIT_TIMEOUT


class RunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    research: ResearchPolicy | None = Field(default_factory=standard_hierarchy_policy)
    variant: Literal["shared", "flat", "unshared", "no-clone", "no-motif-bias"] = "shared"
    schema_version: Literal[1] = 1
    pack: str = "tier1_core"
    budget: int = Field(default=DEFAULT_BUDGET, gt=0, le=MAX_ENGINE_EVALUATIONS, strict=True)
    seed: int = Field(default=42, ge=0, lt=2**32, strict=True)
    epochs: int = Field(default=12, ge=1, le=1000, strict=True)
    population_size: int = Field(default=4, ge=2, le=16, strict=True)
    backend: Literal["numpy_fallback", "mlx_native"] = DEFAULT_BACKEND
    target_device: Literal["cpu", "gpu"] = "cpu"
    timeout: float = Field(default=DEFAULT_TIMEOUT, gt=0, le=86400)
    fit_timeout: float = Field(default=DEFAULT_FIT_TIMEOUT, gt=0, le=1800)
