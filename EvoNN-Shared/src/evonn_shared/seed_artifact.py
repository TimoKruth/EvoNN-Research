"""Portable seed envelope; compatibility is a declaration, not transfer proof."""
from typing import Literal
import json
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .canonical import canonical_sha256
from .telemetry import RuntimeMetadata


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class Source(Strict):
    engine: Literal['primordia', 'stratograph', 'topograph', 'prism']
    version: str = Field(min_length=1)
    commit: str = Field(pattern=r'^[0-9a-f]{40}$')
    code_dirty: bool
    run_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    benchmark: str = Field(min_length=1)
    pack: str = Field(min_length=1)
    seed: int = Field(ge=0, lt=2**32)
    budget_spent: int = Field(gt=0)
    runtime: dict


class Quality(Strict):
    metric: str = Field(min_length=1)
    direction: Literal['min', 'max']
    value: float


class Contamination(Strict):
    policy: Literal['train-fit_validation-selection_no-target-test']
    raw_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    split_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    target_overlap: Literal['unknown_requires_target_check']


class Ingestion(Strict):
    target: Literal['prism', 'topograph', 'stratograph']
    protocol: Literal['evonn.motif-translation/v1']
    status: Literal['translation_required_not_native_ingestion']
    instructions: str = Field(min_length=1)


class SeedArtifact(Strict):
    schema_version: Literal['evonn.seed/v1'] = 'evonn.seed/v1'
    source: Source
    encoding: dict
    descriptors: dict[str, float]
    quality: Quality
    diversity: dict[str, float]
    contamination: Contamination
    compatible_targets: list[Literal['prism', 'topograph', 'stratograph']] = Field(min_length=1)
    ingestion: list[Ingestion] = Field(min_length=1)
    transfer_status: Literal['unproven'] = 'unproven'
    checksum: str = Field(pattern=r'^[0-9a-f]{64}$')

    @model_validator(mode='after')
    def validate_envelope(self):
        # Runtime schema is shared with exports; opaque dictionaries may not bypass it.
        RuntimeMetadata.model_validate_json(json.dumps(self.source.runtime, allow_nan=False))
        targets = self.compatible_targets
        if len(set(targets)) != len(targets) or sorted(targets) != sorted(item.target for item in self.ingestion):
            raise ValueError('target compatibility and ingestion instructions disagree')
        allowed = {'primordia': {'prism', 'topograph', 'stratograph'},
                   'stratograph': {'prism', 'topograph'}, 'topograph': {'prism'}, 'prism': set()}
        if not set(targets) <= allowed[self.source.engine] or not self.encoding or not self.descriptors or not self.diversity:
            raise ValueError('unsupported target edge or empty motif description')
        expected = canonical_sha256(self.model_dump(mode='json', exclude={'checksum'}),
                                    schema_version='evonn.seed/v1', digest_field=None)
        if expected != self.checksum:
            raise ValueError('seed checksum mismatch')
        return self


def seal_seed(payload):
    data = {'schema_version': 'evonn.seed/v1', 'transfer_status': 'unproven', **payload}
    data['checksum'] = canonical_sha256(data, schema_version='evonn.seed/v1', digest_field=None)
    return SeedArtifact.model_validate(data).model_dump(mode='json')
