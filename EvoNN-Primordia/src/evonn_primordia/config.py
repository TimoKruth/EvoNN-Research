"""Bounded, explicit engine run configuration."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from evonn_shared.runtime_budget import MAX_ENGINE_EVALUATIONS


class RunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    schema_version: Literal[1] = 1
    pack: str = "tier1_core"
    budget: int = Field(default=64, gt=0, le=MAX_ENGINE_EVALUATIONS, strict=True)
    seed: int = Field(default=42, ge=0, lt=2**32, strict=True)
    epochs: int = Field(default=12, ge=1, le=1000, strict=True)
    population_size: int = Field(default=4, ge=2, le=16, strict=True)
    backend: Literal["numpy_fallback", "mlx_native"] = "numpy_fallback"
    target_device: Literal["cpu", "gpu"] = "cpu"
    timeout: float = Field(default=1200, gt=0, le=1800)
    fit_timeout: float = Field(default=120, gt=0, le=1800)
    search_policy: Literal["legacy_v1", "breadth_v2"] = "breadth_v2"
    max_width: int = Field(default=48, ge=2, le=256, strict=True)
    max_depth: int = Field(default=8, ge=1, le=32, strict=True)
