"""Portable declarations for Primordia campaign search and size controls."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


RESEARCH_DEFAULTS = dict(architecture_policy="v2", optimization_policy="v2",
                         proposal_policy="v2", inheritance_policy="enabled")
TEMPORAL_POLICIES = {"temporal_v3", "attention_v3", "convolution_v3", "multiscale_v3"}
SPATIAL_POLICIES = {"spatial_v3", "conv_flat_v3", "conv_pool_v3"}


def portfolio_families(task, modality):
    """Modality-only priors, without benchmark IDs or validation-score routing."""
    if task == "language_modeling":
        return ("convolution", "attention", "multiscale")
    if modality == "image":
        return ("conv_pool", "conv_flat")
    return ()


def uses_v3(policy, task, modality):
    return (policy == "expressive_v3"
            or policy in TEMPORAL_POLICIES and task == "language_modeling"
            or policy in SPATIAL_POLICIES and modality == "image"
            or policy == "portfolio_v4" and bool(portfolio_families(task, modality)))


class PrimordiaResearchPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    search_policy: Literal["legacy_v1", "breadth_v2"] = "breadth_v2"
    max_width: int = Field(default=48, ge=2, le=256, strict=True)
    max_depth: int = Field(default=8, ge=1, le=32, strict=True)
    architecture_policy: Literal["v2", "temporal_v3", "attention_v3", "convolution_v3", "multiscale_v3",
                                 "spatial_v3", "conv_flat_v3", "conv_pool_v3", "expressive_v3", "portfolio_v4"] = "v2"
    optimization_policy: Literal["v2", "stable_v3", "steady_v3"] = "v2"
    proposal_policy: Literal["v2", "progress_v3"] = "v2"
    inheritance_policy: Literal["enabled", "disabled"] = "enabled"

    @model_validator(mode="after")
    def legacy_control(self):
        if self.search_policy == "legacy_v1" and any(
                self.model_dump()[key] != value for key, value in RESEARCH_DEFAULTS.items()):
            raise ValueError("legacy_v1 requires unchanged research controls")
        return self

    @property
    def training_policy(self):
        if self.optimization_policy != "v2":
            return self.optimization_policy + "/initial_checkpoint_selection"
        return "learning_progress_with_patient_slots/v2" if self.search_policy == "breadth_v2" else "legacy/v1"
