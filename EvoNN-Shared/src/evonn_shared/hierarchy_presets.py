"""Portable, explicit Stratograph experiment configurations; no engine runtime."""
from .hierarchy_policy import HierarchyResearchPolicy


def standard_hierarchy_policy():
    """Quality-first default: the exact evolving arm confirmed on 16 paired seeds."""
    return hierarchy_presets()['evolving']


def hierarchy_presets():
    reference = HierarchyResearchPolicy(evaluator='trainable', normalization='rms', evolve_representation=False)
    control = dict(reference.model_dump(), version=3, temporal='prefix', embedding_width=0,
                   position='none', cell_normalization='none', residual_mode='legacy', merge='mean',
                   readout_skip=False, select_initial=False, weight_decay_scope='all', niche_policy='structure')
    full = dict(version=3, evaluator='trainable', normalization='rms', evolve_representation=False)
    policies = {
        'v2_reference': reference,
        'v3_control': HierarchyResearchPolicy(**control),
        'attention_only': HierarchyResearchPolicy(**{**control, 'temporal': 'attention', 'position': 'relative'}),
        'dilated_only': HierarchyResearchPolicy(**{**control, 'temporal': 'dilated'}),
        'stabilized_prefix': HierarchyResearchPolicy(**full, temporal='prefix'),
        'attention': HierarchyResearchPolicy(**full, temporal='attention'),
        'dilated': HierarchyResearchPolicy(**full, temporal='dilated'),
        'hybrid': HierarchyResearchPolicy(**full, temporal='hybrid'),
        'hybrid_fresh': HierarchyResearchPolicy(**full, temporal='hybrid', inheritance='fresh'),
        'hybrid_dropout': HierarchyResearchPolicy(**full, temporal='hybrid', dropout=.1),
        'evolving': HierarchyResearchPolicy(**{**full, 'evolve_representation': True}, temporal='hybrid', evolve_temporal=True),
    }
    return policies
