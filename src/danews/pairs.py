"""Deterministic pairwise comparison schedule for tone judging (§6.4.2, test_pairs.py)."""

from __future__ import annotations

import random
from dataclasses import dataclass

MIN_PAIRS_PER_MODEL = 4


@dataclass(frozen=True)
class Pair:
    left: str
    right: str
    order_seed: int


def _round_robin_rounds(models: list[str]) -> list[list[tuple[str, str]]]:
    """Circle-method tournament: each round is a perfect matching (odd n → one model rests)."""
    ms = list(models)
    if len(ms) % 2:
        ms.append("__bye__")
    n = len(ms)
    rounds = []
    for _ in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = ms[i], ms[n - 1 - i]
            if "__bye__" not in (a, b):
                pairs.append((a, b))
        rounds.append(pairs)
        ms = [ms[0]] + [ms[-1]] + ms[1:-1]
    return rounds


def schedule(models: list[str], slot_ref: str, seed: int = 42) -> list[Pair]:
    """Pairs for one slot: every model in ≥ MIN_PAIRS_PER_MODEL pairs (or all pairs if fewer
    models), left/right balanced per model, deterministic in (models, slot_ref, seed)."""
    models = sorted(models)
    if len(models) < 2:
        return []
    rng = random.Random(f"{seed}:{slot_ref}")
    rounds = _round_robin_rounds(models)
    rng.shuffle(rounds)
    appearances = dict.fromkeys(models, 0)
    chosen: list[tuple[str, str]] = []
    for rnd in rounds:
        if all(v >= MIN_PAIRS_PER_MODEL for v in appearances.values()):
            break
        for a, b in rnd:
            chosen.append((a, b))
            appearances[a] += 1
            appearances[b] += 1
    left_count = dict.fromkeys(models, 0)
    right_count = dict.fromkeys(models, 0)
    out: list[Pair] = []
    for a, b in chosen:
        bal_a = left_count[a] - right_count[a]
        bal_b = left_count[b] - right_count[b]
        if bal_a < bal_b or (bal_a == bal_b and rng.random() < 0.5):
            left, right = a, b
        else:
            left, right = b, a
        left_count[left] += 1
        right_count[right] += 1
        out.append(Pair(left, right, order_seed=rng.randrange(1 << 30)))
    return out
