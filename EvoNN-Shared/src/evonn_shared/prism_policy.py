"""Portable Prism experiment declarations, with no search/compiler implementation."""

from typing import Literal
from pydantic import BaseModel, ConfigDict


class PrismResearchPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    variant: Literal["legacy", "archive", "training", "broad", "open"] = "open"
    inheritance_policy: Literal["enabled", "disabled"] = "enabled"
    optimizer_policy: Literal["restart", "continue"] = "restart"
    optimizer_backend: Literal["numpy", "native"] = "numpy"
    fixed_genomes: dict[str, dict] | None = None
    prior_discovery: dict | None = None
