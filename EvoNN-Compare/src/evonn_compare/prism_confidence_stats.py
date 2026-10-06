"""Predeclared Prism version inference, with seeds as the sampling unit."""

from itertools import combinations
import math

import numpy as np
from scipy.stats import rankdata


PRIMARY_TASKS = {
    "core256": ("digits_image", "diabetes_regression", "shakespeare_byte_lm"),
    "breadth128": ("shakespeare_byte_lm", "shakespeare_context64_lm", "aesop_context64_lm"),
}


def signed_rank(values):
    """Exact two-sided signed-rank sign enumeration via integer subset counts.

    Doubled average ranks support ties; rounded zero differences are discarded.
    Independent paired seed effects must be symmetric under the null.
    """
    values = np.round(np.asarray(values, dtype=float), 12)
    if not np.isfinite(values).all() or values.ndim != 1 or len(values) > 30:
        raise ValueError("finite vector of at most 30 paired seed effects required")
    values = values[values != 0]
    if not len(values):
        return {"pvalue": 1., "nonzero_pairs": 0}
    ranks = np.rint(2 * rankdata(np.abs(values))).astype(int)
    counts = np.zeros(int(ranks.sum()) + 1, dtype=np.int64)
    counts[0] = 1
    for rank in ranks:
        counts[rank:] += counts[:-rank].copy()
    observed = int(ranks[values > 0].sum())
    tail = min(observed, int(ranks.sum()) - observed)
    return {"pvalue": min(1., 2 * int(counts[:tail + 1].sum()) / 2 ** len(values)),
            "nonzero_pairs": len(values)}


def holm(pvalues):
    if any(not math.isfinite(p) or not 0 <= p <= 1 for p in pvalues):
        raise ValueError("invalid p-value")
    corrected, previous = [None] * len(pvalues), 0.
    for position, index in enumerate(sorted(range(len(pvalues)), key=lambda i: pvalues[i])):
        previous = max(previous, min(1., pvalues[index] * (len(pvalues) - position)))
        corrected[index] = previous
    return corrected


def symmetric_effect(before, after, direction):
    if direction not in {"min", "max"} or not all(math.isfinite(x) for x in (before, after)):
        raise ValueError("finite metrics with explicit direction required")
    denominator = abs(before) + abs(after)
    return (0. if denominator == 0 else 2 * (after - before) / denominator) * (1 if direction == "max" else -1)


def inference(rows, arms, seeds):
    """Only callable on a complete fixed matrix; all pairs form one Holm family."""
    indexed = {}
    for row in rows:
        key = row["panel"], row["arm"], row["seed"], row["benchmark"]
        if key in indexed:
            raise ValueError("duplicate observation")
        indexed[key] = row
    samples = np.random.default_rng(21600).integers(0, len(seeds), size=(20000, len(seeds)))
    contrasts = []
    for panel, tasks in PRIMARY_TASKS.items():
        for before, after in combinations(arms, 2):
            effects = []
            task_effects = {task: [] for task in tasks}
            for seed in seeds:
                for task in tasks:
                    a, b = indexed[(panel, before, seed, task)], indexed[(panel, after, seed, task)]
                    if a["direction"] != b["direction"]:
                        raise ValueError("paired metric directions disagree")
                    task_effects[task].append(symmetric_effect(a["value"], b["value"], a["direction"]))
                effects.append(float(np.mean([task_effects[task][-1] for task in tasks])))
            array = np.asarray(effects)
            interval = np.quantile(array[samples].mean(axis=1), [.025, .975]).tolist()
            test = signed_rank(effects)
            contrasts.append({"panel": panel, "before": before, "after": after, "n": len(seeds),
                              "effect_mean": float(array.mean()), "paired_effects": effects,
                              "bootstrap_ci95_descriptive": interval, **test,
                              "task_effect_means": {k: float(np.mean(v)) for k, v in task_effects.items()}})
    adjusted = holm([c["pvalue"] for c in contrasts])
    for contrast, pvalue in zip(contrasts, adjusted, strict=True):
        contrast["holm_pvalue"] = pvalue
        mean = contrast["effect_mean"]
        low, high = contrast["bootstrap_ci95_descriptive"]
        winner = None
        if pvalue <= .05:
            if mean >= .01 and low > 0:
                winner = contrast["after"]
            elif mean <= -.01 and high < 0:
                winner = contrast["before"]
        contrast["supported_winner"] = winner
        contrast["decision"] = "supported_difference" if winner else "inconclusive"
    leaders = {}
    for panel in PRIMARY_TASKS:
        leaders[panel] = [arm for arm in arms if all(
            c["supported_winner"] == arm for c in contrasts
            if c["panel"] == panel and arm in (c["before"], c["after"]))]
    return {"scope": "validation-selected performance on fixed workloads; no protected-test or external superiority claim",
            "alpha_familywise": .05, "holm_family_size": len(contrasts), "contrasts": contrasts,
            "panel_leaders_beating_every_other_arm": leaders,
            "bootstrap_intervals": "95% descriptive paired-seed percentile intervals; not simultaneous intervals",
            "inconclusive_semantics": "lack of significance does not establish equivalence",
            "promotion": "none; task-level sentinels and fresh confirmation must be reviewed"}


def power_sensitivity(arms, n=16):
    """Planning sensitivity only: Gaussian paired effects, no fitted pilot effect."""
    rng = np.random.default_rng(21600)
    pairs = 2 * math.comb(len(arms), 2)
    ranks = np.arange(1, n + 1)
    counts = np.zeros(n * (n + 1) // 2 + 1, dtype=np.int64)
    counts[0] = 1
    for rank in ranks:
        counts[rank:] += counts[:-rank].copy()
    probabilities = np.minimum(1., 2 * np.cumsum(counts) / 2 ** n)
    values = []
    for standardized in (.5, .75, 1., 1.25, 1.5):
        draws = rng.normal(standardized, 1., size=(20000, n))
        ranked = rankdata(np.abs(draws), axis=1)
        positive = (ranked * (draws > 0)).sum(axis=1).astype(int)
        tail = np.minimum(positive, n * (n + 1) // 2 - positive)
        probability = float(np.mean(probabilities[tail] <= .05 / pairs))
        values.append({"paired_mean_over_sd": standardized, "power_at_conservative_first_holm_threshold": probability})
    return {"n": n, "hypotheses": pairs, "two_sided_minimum_p": 2 / 2 ** n,
            "first_holm_threshold": .05 / pairs, "simulations_per_effect": 20000,
            "assumption": "independent Gaussian paired effects; sensitivity, not promised power; ignores materiality filter",
            "sensitivity": values}
