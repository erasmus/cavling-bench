"""Stage `judge`: grounding, pairwise tone, fluency via two cross-family judges (§6.4)."""

from __future__ import annotations

import asyncio
import json
import math
import random
import re
from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import Any

from jinja2 import Environment, StrictUndefined
from pydantic import BaseModel, ValidationError
from rich.console import Console

from .check import load_outputs
from .config import Config
from .llm import LLMClient, model_is_reachable
from .pairs import schedule
from .schemas import (
    FluencyRecord,
    GroundingRecord,
    JudgeFluencyResponse,
    JudgeGroundingResponse,
    JudgeToneResponse,
    ModelCfg,
    Output,
    TonePairRecord,
)

console = Console(stderr=True)
_env = Environment(undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)

REPAIR_INSTRUCTION = (
    "Your previous reply was not valid JSON matching the required schema. "
    "Reply again with ONLY the JSON object, no prose, no code fences."
)
TONE_TASKS = ("t2_rubrik", "t4_versionering", "t6_lydmanus")
JUDGE_MAX_TOKENS = {"grounding": 6000, "tone": 300, "fluency": 400}


# JSON handling -------------------------------------------------------------------


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found")
    return json.loads(text[start : end + 1])


async def ask_json[T: BaseModel](
    client: LLMClient, judge: ModelCfg, prompt: str, model: type[T], max_tokens: int
) -> tuple[T | None, str | None]:
    """Call once; on parse failure retry once with a repair instruction; then (None, error)."""
    messages = [{"role": "user", "content": prompt}]
    last_err = ""
    for attempt in range(2):
        try:
            res = await client.acomplete(judge, messages, 0.0, max_tokens, 42)
        except Exception as e:  # noqa: BLE001
            return None, f"{type(e).__name__}: {e}"[:300]
        try:
            return model.model_validate(extract_json(res.text)), None
        except (ValueError, ValidationError) as e:
            last_err = f"parse: {e}"[:300]
            if attempt == 0:
                messages = messages + [
                    {"role": "assistant", "content": res.text},
                    {"role": "user", "content": REPAIR_INSTRUCTION},
                ]
    return None, last_err


# Sampling ----------------------------------------------------------------------------


def stratified_sample[T: BaseModel](
    items: Iterable[T], key: Callable[[T], str], fraction: float, seed: int = 42
) -> list[T]:
    """Take ceil(fraction × n) items from every stratum, deterministically."""
    strata: dict[str, list[T]] = defaultdict(list)
    for it in items:
        strata[key(it)].append(it)
    out: list[T] = []
    for k in sorted(strata):
        group = strata[k]
        rng = random.Random(f"{seed}:{k}")
        n = math.ceil(fraction * len(group))
        out.extend(rng.sample(group, n))
    return out


# JSONL persistence -------------------------------------------------------------------


def _read_jsonl[T: BaseModel](path, model: type[T]) -> list[T]:
    if not path.exists():
        return []
    return [model.model_validate_json(ln) for ln in path.read_text().splitlines() if ln.strip()]


def _append_jsonl(path, records: list[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        for r in records:
            f.write(r.model_dump_json() + "\n")


def _load_done[T: BaseModel](path, model: type[T], force: bool) -> list[T]:
    """Existing successful records. Error records are dropped from the file so they are retried."""
    if force:
        if path.exists():
            path.unlink()
        return []
    recs = _read_jsonl(path, model)
    good = [r for r in recs if not getattr(r, "error", None)]
    if len(good) != len(recs):
        path.write_text("".join(r.model_dump_json() + "\n" for r in good))
    return good


def _active_judges(cfg: Config, stats: dict[str, Any]) -> list[tuple[int, ModelCfg]]:
    """Judges that can be called now; unreachable ones are reported in stats and skipped."""
    active = []
    for ix, judge in enumerate(_judges(cfg)):
        reason = model_is_reachable(judge)
        if reason:
            stats[f"{judge.id}_skipped"] = reason
            console.print(f"[yellow]{judge.id}: skipped ({reason})[/yellow]")
        else:
            active.append((ix, judge))
    return active


def _judges(cfg: Config) -> list[ModelCfg]:
    js = [cfg.model(cfg.models_file.judges.A)]
    if cfg.models_file.judges.B:
        js.append(cfg.model(cfg.models_file.judges.B))
    return js


def _usable(outputs: list[Output]) -> list[Output]:
    return [o for o in outputs if not o.error and o.text.strip()]


def _plan_outputs(cfg: Config, outputs: list[Output], judge_ix: int) -> list[Output]:
    """Judge A: all usable outputs; Judge B: stratified sample by task × model."""
    if judge_ix == 0:
        return outputs
    return stratified_sample(
        outputs, lambda o: f"{o.task_id}|{o.model_id}", cfg.models_file.judge_b_sample_fraction
    )


# Grounding -----------------------------------------------------------------------------


async def _grounding(cfg: Config, only: str | None, use_cache: bool, force: bool) -> dict:
    path = cfg.paths.scores / "grounding.jsonl"
    done = {(r.output_ref, r.judge_id) for r in _load_done(path, GroundingRecord, force)}
    template = _env.from_string(cfg.prompt_template("judge_grounding"))
    client = LLMClient(cfg.paths, use_cache=use_cache, stage="judge_grounding")
    outputs = _usable(load_outputs(cfg))
    if only:
        outputs = [o for o in outputs if only in o.ref]
    stats: dict[str, Any] = defaultdict(int)

    async def one(judge: ModelCfg, out: Output) -> GroundingRecord | None:
        if (out.ref, judge.id) in done:
            return None
        prompt = template.render(
            source_body=cfg.source(out.source_id).body.strip(), output_text=out.text.strip()
        )
        resp, err = await ask_json(
            client, judge, prompt, JudgeGroundingResponse, JUDGE_MAX_TOKENS["grounding"]
        )
        claims = resp.claims if resp else []
        n = len(claims)
        return GroundingRecord(
            output_ref=out.ref,
            judge_id=judge.id,
            claims=claims,
            n_claims=n,
            pct_supported=(100.0 * sum(c.label == "supported" for c in claims) / n) if n else 0.0,
            n_contradicted=sum(c.label == "contradicted" for c in claims),
            error=err,
        )

    for ix, judge in _active_judges(cfg, stats):
        plan = _plan_outputs(cfg, outputs, ix)
        recs = [r for r in await asyncio.gather(*[one(judge, o) for o in plan]) if r]
        _append_jsonl(path, recs)
        stats[judge.id] += len(recs)
        stats[f"{judge.id}_errors"] += sum(1 for r in recs if r.error)
    return dict(stats)


def run_grounding(
    cfg: Config, only: str | None = None, use_cache: bool = True, force: bool = False
) -> dict:
    return asyncio.run(_grounding(cfg, only, use_cache, force))


# Fluency --------------------------------------------------------------------------------


async def _fluency(cfg: Config, only: str | None, use_cache: bool, force: bool) -> dict:
    path = cfg.paths.scores / "fluency.jsonl"
    done = {(r.output_ref, r.judge_id) for r in _load_done(path, FluencyRecord, force)}
    template = _env.from_string(cfg.prompt_template("judge_fluency"))
    client = LLMClient(cfg.paths, use_cache=use_cache, stage="judge_fluency")
    outputs = _usable(load_outputs(cfg))
    if only:
        outputs = [o for o in outputs if only in o.ref]
    stats: dict[str, Any] = defaultdict(int)

    async def one(judge: ModelCfg, out: Output) -> FluencyRecord | None:
        if (out.ref, judge.id) in done:
            return None
        resp, err = await ask_json(
            client,
            judge,
            template.render(output_text=out.text.strip()),
            JudgeFluencyResponse,
            JUDGE_MAX_TOKENS["fluency"],
        )
        return FluencyRecord(
            output_ref=out.ref,
            judge_id=judge.id,
            score=resp.score if resp else None,
            issues=resp.issues if resp else [],
            rationale=resp.rationale if resp else "",
            error=err,
        )

    for ix, judge in _active_judges(cfg, stats):
        plan = _plan_outputs(cfg, outputs, ix)
        recs = [r for r in await asyncio.gather(*[one(judge, o) for o in plan]) if r]
        _append_jsonl(path, recs)
        stats[judge.id] += len(recs)
        stats[f"{judge.id}_errors"] += sum(1 for r in recs if r.error)
    return dict(stats)


def run_fluency(
    cfg: Config, only: str | None = None, use_cache: bool = True, force: bool = False
) -> dict:
    return asyncio.run(_fluency(cfg, only, use_cache, force))


# Tone (pairwise) ----------------------------------------------------------------------------


def tone_pairs(cfg: Config, outputs: list[Output]) -> list[tuple[str, Output, Output, int]]:
    """(slot_ref, left_output, right_output, order_seed) for every tone slot."""
    by_slot: dict[str, dict[str, Output]] = defaultdict(dict)
    for o in outputs:
        if o.task_id in TONE_TASKS:
            by_slot[o.slot_ref][o.model_id] = o
    pairs = []
    for slot_ref in sorted(by_slot):
        models = by_slot[slot_ref]
        for p in schedule(list(models), slot_ref):
            pairs.append((slot_ref, models[p.left], models[p.right], p.order_seed))
    return pairs


def single_judge_cells(cfg: Config) -> list[tuple[str, str]]:
    """(model_id, 'tone') cells that only one judge can grade under the cross-family rule."""
    judges = _judges(cfg)
    cells = []
    for m in cfg.models:
        graders = [j for j in judges if j.family != m.family]
        if len(graders) < len(judges):
            cells.append((m.id, "tone"))
    return cells


async def _tone(cfg: Config, only: str | None, use_cache: bool, force: bool) -> dict:
    path = cfg.paths.scores / "tone_pairs.jsonl"
    existing = _load_done(path, TonePairRecord, force)
    done = {(r.slot_ref, r.left_model, r.right_model, r.judge_id) for r in existing}
    template = _env.from_string(cfg.prompt_template("judge_tone_pairwise"))
    client = LLMClient(cfg.paths, use_cache=use_cache, stage="judge_tone")
    outputs = _usable(load_outputs(cfg))
    pairs = tone_pairs(cfg, outputs)
    if only:
        pairs = [p for p in pairs if only in p[0]]
    stats: dict[str, Any] = defaultdict(int)

    async def one(judge: ModelCfg, slot_ref: str, left: Output, right: Output, seed: int):
        if (slot_ref, left.model_id, right.model_id, judge.id) in done:
            return None
        if judge.family in (cfg.model(left.model_id).family, cfg.model(right.model_id).family):
            stats[f"{judge.id}_skipped_cross_family"] += 1
            return None
        src = cfg.source(left.source_id)
        arch = left.archetype or ""
        prompt = template.render(
            styleguide=cfg.styleguides[arch],
            source_title=src.meta.title,
            source_excerpt=" ".join(src.body.split()[:100]),
            left_text=left.text.strip(),
            right_text=right.text.strip(),
        )
        resp, err = await ask_json(
            client, judge, prompt, JudgeToneResponse, JUDGE_MAX_TOKENS["tone"]
        )
        return TonePairRecord(
            slot_ref=slot_ref,
            judge_id=judge.id,
            left_model=left.model_id,
            right_model=right.model_id,
            order_seed=seed,
            winner=resp.winner if resp else None,
            confidence=resp.confidence if resp else None,
            rationale=resp.rationale if resp else "",
            error=err,
        )

    for ix, judge in _active_judges(cfg, stats):
        plan = pairs
        if ix > 0:
            plan = stratified_sample(
                pairs,
                lambda p: p[0].rsplit("/", 1)[0] + "|" + (p[1].archetype or ""),
                cfg.models_file.judge_b_sample_fraction,
            )
        recs = [r for r in await asyncio.gather(*[one(judge, *p) for p in plan]) if r]
        _append_jsonl(path, recs)
        stats[judge.id] += len(recs)
        stats[f"{judge.id}_errors"] += sum(1 for r in recs if r.error)
    return dict(stats)


def run_tone(
    cfg: Config, only: str | None = None, use_cache: bool = True, force: bool = False
) -> dict:
    return asyncio.run(_tone(cfg, only, use_cache, force))
