"""Portable Stratograph v2 policy contract; contains no engine execution code."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator


V3_FIELDS = ('temporal', 'embedding_width', 'position', 'cell_normalization',
             'residual_mode', 'merge', 'readout_skip', 'select_initial',
             'weight_decay_scope', 'evolve_temporal', 'dropout', 'niche_policy')
V3_REPRESENTATION_CHOICES = {
    'cell_normalization': ['none', 'rms'],
    'residual_mode': ['legacy', 'gated'],
    'merge': ['mean', 'learned'],
    'readout_skip': [False, True],
}


class HierarchyResearchPolicy(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True, allow_inf_nan=False)
    version: Literal[2, 3] = 2
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

    temporal: Literal['prefix', 'attention', 'dilated', 'hybrid'] = 'attention'
    embedding_width: int = Field(default=32, ge=0, le=64, strict=True)
    position: Literal['none', 'sinusoidal', 'relative'] = 'relative'
    cell_normalization: Literal['none', 'rms'] = 'rms'
    residual_mode: Literal['legacy', 'gated'] = 'gated'
    merge: Literal['mean', 'learned'] = 'learned'
    readout_skip: bool = True
    select_initial: bool = True
    weight_decay_scope: Literal['all', 'matrices'] = 'matrices'
    evolve_temporal: bool = False
    dropout: float = Field(default=0., ge=0., le=.5)
    niche_policy: Literal['structure', 'representation'] = 'representation'

    @model_validator(mode='after')
    def versioned_options(self):
        if self.version == 2 and self.model_fields_set.intersection(V3_FIELDS):
            raise ValueError('temporal research options require policy version 3')
        if self.version == 3 and self.evaluator != 'trainable':
            raise ValueError('policy version 3 requires the trainable evaluator')
        return self

    @model_serializer(mode='wrap')
    def serialized(self, handler):
        value = handler(self)
        if self.version == 2:
            value = {key: item for key, item in value.items() if key not in V3_FIELDS}
        return value

    @property
    def fidelity(self):
        if self.version == 3:
            return 'end_to_end_hierarchy_v3'
        return 'hierarchy_features_trained_head_v2' if self.evaluator == 'proxy' else 'end_to_end_hierarchy_v2'
