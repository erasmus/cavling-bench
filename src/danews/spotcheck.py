"""Stage `spotcheck sample`: stratified human-rating sample with hidden model names (§6.5)."""

from __future__ import annotations

import csv
import hashlib
import math
import random
from collections import defaultdict

from .check import load_outputs
from .config import Config

SAMPLE_COLUMNS = [
    "sample_id",
    "task",
    "archetype",
    "source_title",
    "source_text",
    "output_text",
    "styleguide_name",
    "h_grounding_pct",
    "h_contradicted",
    "h_tone_1to5",
    "h_fluency_1to5",
    "h_notes",
]
HUMAN_COLUMNS = ["rater_id", *SAMPLE_COLUMNS]


def sample_id_for(output_ref: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{output_ref}".encode()).hexdigest()[:10]


def run_sample(cfg: Config, n: int = 150, seed: int = 42) -> dict[str, int]:
    outputs = [o for o in load_outputs(cfg) if not o.error and o.text.strip()]
    cells: dict[tuple[str, str], list] = defaultdict(list)
    for o in outputs:
        cells[(o.task_id, o.model_id)].append(o)
    per_cell = max(1, math.ceil(n / max(1, len(cells))))
    chosen = []
    for key in sorted(cells):
        rng = random.Random(f"{seed}:{key}")
        group = sorted(cells[key], key=lambda o: o.ref)
        chosen.extend(rng.sample(group, min(per_cell, len(group))))
    rng = random.Random(seed)
    rng.shuffle(chosen)
    chosen = chosen[:n]
    cfg.paths.scores.mkdir(parents=True, exist_ok=True)
    with (cfg.paths.scores / "spotcheck_sample.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SAMPLE_COLUMNS)
        w.writeheader()
        for o in chosen:
            src = cfg.source(o.source_id)
            w.writerow(
                {
                    "sample_id": sample_id_for(o.ref, seed),
                    "task": o.task_id,
                    "archetype": o.archetype or "",
                    "source_title": src.meta.title,
                    "source_text": src.body.strip(),
                    "output_text": o.text.strip(),
                    "styleguide_name": o.archetype or "",
                    "h_grounding_pct": "",
                    "h_contradicted": "",
                    "h_tone_1to5": "",
                    "h_fluency_1to5": "",
                    "h_notes": "",
                }
            )
    with (cfg.paths.scores / "spotcheck_key.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sample_id", "output_ref"])
        for o in sorted(chosen, key=lambda o: o.ref):
            w.writerow([sample_id_for(o.ref, seed), o.ref])
    human = cfg.paths.scores / "spotcheck_human.csv"
    if not human.exists():
        with human.open("w", newline="") as f:
            csv.DictWriter(f, fieldnames=HUMAN_COLUMNS).writeheader()
    return {"rows": len(chosen), "cells": len(cells), "per_cell": per_cell}
