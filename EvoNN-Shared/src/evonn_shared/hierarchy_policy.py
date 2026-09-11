"""Portable Stratograph v2 policy contract; contains no engine execution code."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class HierarchyResearchPolicy(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True, allow_inf_nan=False)
    version: Literal[2] = 2
    evaluator: Literal['proxy', 'trainable'] = 'proxy'
    normalization: Literal['none', 'train_standard', 'rms'] = 'train_standard'
    evolve_representation: bool = True
    readout: Literal['final', 'all', 'input_final'] = 'final'
    residual: bool = False
    inheritance: Literal['compatible', 'fresh', 'head_diagnostic'] = 'compatible'
    selection: Literal['diverse', 'quality'] = 'diverse'
    screen_epochs: int = Field(default=0, ge=0, le=1000, strict=True)
    archive_size: int = Field(default=32, ge=8, le=128, strict=True)
    max_macro_nodes: int = Field(default=8, ge=1, le=8, strict=True)
    max_cell_nodes: int = Field(default=6, ge=1, le=6, strict=True)
    max_width: int = Field(default=64, ge=4, le=64, strict=True)
    head_width: int = Field(default=16, ge=4, le=64, strict=True)

    @property
    def fidelity(self):
        return 'hierarchy_features_trained_head_v2' if self.evaluator == 'proxy' else 'end_to_end_hierarchy_v2'
