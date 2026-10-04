"""Portable, versioned Primordia treatment declarations; no engine imports."""

ARMS = {
    'control': {},
    'attention': dict(architecture_policy='attention_v3'),
    'temporal_convolution': dict(architecture_policy='convolution_v3'),
    'multiscale': dict(architecture_policy='multiscale_v3'),
    'spatial_flat': dict(architecture_policy='conv_flat_v3'),
    'spatial_pool': dict(architecture_policy='conv_pool_v3'),
    'representations': dict(architecture_policy='expressive_v3'),
    'stable_training': dict(optimization_policy='stable_v3'),
    'steady_training': dict(optimization_policy='steady_v3'),
    'progress_search': dict(proposal_policy='progress_v3'),
    'full': dict(architecture_policy='expressive_v3', optimization_policy='stable_v3', proposal_policy='progress_v3'),
    'full_steady': dict(architecture_policy='expressive_v3', optimization_policy='steady_v3', proposal_policy='progress_v3'),
    'full_cold': dict(architecture_policy='expressive_v3', optimization_policy='stable_v3',
                      proposal_policy='progress_v3', inheritance_policy='disabled'),
}

# Preserve ARMS exactly: it defines the frozen 13-arm / 468-contrast study.
# New operational presets are separate from that historical experiment roster.
PRESETS = {
    **ARMS,
    'standard': dict(ARMS['full_steady']),
    'portfolio': dict(architecture_policy='portfolio_v4', optimization_policy='steady_v3', proposal_policy='progress_v3'),
    'portfolio_stable': dict(architecture_policy='portfolio_v4', optimization_policy='stable_v3', proposal_policy='progress_v3'),
}
