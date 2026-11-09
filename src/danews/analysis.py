"""Shared statistics: bootstrap intervals and Bradley–Terry ratings (§6.4.2, §6.6)."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Callable, Sequence

import numpy as np

from .schemas import TonePairRecord

BT_MEAN, BT_SD = 50.0, 15.0


def bootstrap_ci(
    groups: Sequence[Sequence[float]],
    stat: Callable[[list[float]], float] = lambda xs: float(np.mean(xs)),
    n_boot: int = 1000,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Resample *groups* (one per source) with replacement; return (point, lo, hi).

    Each group holds the values for one aggregation unit (a source text). Resampling units
    rather than individual values is what §6.6 asks for.
    """
    groups = [list(g) for g in groups if len(g)]
    if not groups:
        return (math.nan, math.nan, math.nan)
    flat = [v for g in groups for v in g]
    point = stat(flat)
    if len(groups) == 1:
        return (point, point, point)
    rng = np.random.default_rng(seed)
    idx = np.arange(len(groups))
    vals = []
    for _ in range(n_boot):
        sample = rng.choice(idx, size=len(groups), replace=True)
        vals.append(stat([v for i in sample for v in groups[i]]))
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return (point, float(lo), float(hi))


def bt_ratings(
    pairs: Sequence[TonePairRecord], models: Sequence[str], alpha: float = 0.01
) -> dict[str, float]:
    """Bradley–Terry via choix.ilsr_pairwise. Ties count 0.5/0.5 (decisive outcomes are
    entered twice, ties once in each direction). Scaled to mean 50, sd 15, clipped 0–100."""
    import choix

    models = sorted(models)
    ix = {m: i for i, m in enumerate(models)}
    data: list[tuple[int, int]] = []
    for p in pairs:
        if p.winner is None or p.left_model not in ix or p.right_model not in ix:
            continue
        left, right = ix[p.left_model], ix[p.right_model]
        if p.winner == "left":
            data += [(left, right)] * 2
        elif p.winner == "right":
            data += [(right, left)] * 2
        else:
            data += [(left, right), (right, left)]
    if len(models) < 2 or not data:
        return dict.fromkeys(models, BT_MEAN)
    theta = np.asarray(choix.ilsr_pairwise(len(models), data, alpha=alpha))
    sd = theta.std()
    z = (theta - theta.mean()) / sd if sd > 0 else np.zeros_like(theta)
    rating = np.clip(BT_MEAN + BT_SD * z, 0, 100)
    return {m: float(rating[ix[m]]) for m in models}


def bt_bootstrap(
    pairs: Sequence[TonePairRecord],
    models: Sequence[str],
    slot_source: Callable[[str], str],
    n_boot: int = 1000,
    seed: int = 42,
) -> dict[str, tuple[float, float, float]]:
    """BT point rating plus CI from resampling sources (slots grouped by source)."""
    point = bt_ratings(pairs, models)
    by_source: dict[str, list[TonePairRecord]] = defaultdict(list)
    for p in pairs:
        by_source[slot_source(p.slot_ref)].append(p)
    sources = sorted(by_source)
    if len(sources) < 2:
        return {m: (r, r, r) for m, r in point.items()}
    rng = random.Random(seed)
    samples: dict[str, list[float]] = defaultdict(list)
    for _ in range(n_boot):
        picked = [rng.choice(sources) for _ in sources]
        r = bt_ratings([p for s in picked for p in by_source[s]], models)
        for m, v in r.items():
            samples[m].append(v)
    return {
        m: (point[m], float(np.percentile(samples[m], 2.5)), float(np.percentile(samples[m], 97.5)))
        for m in point
    }
