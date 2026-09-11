"""Portable declarations for Primordia campaign search and size controls."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class PrimordiaResearchPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    search_policy: Literal["legacy_v1", "breadth_v2"] = "breadth_v2"
    max_width: int = Field(default=48, ge=2, le=256, strict=True)
    max_depth: int = Field(default=8, ge=1, le=32, strict=True)

    @property
    def training_policy(self):
        return "learning_progress_with_patient_slots/v2" if self.search_policy == "breadth_v2" else "legacy/v1"
