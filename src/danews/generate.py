"""Stage `generate`: every (model × task × source × archetype) → outputs/*.json (§6.2)."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from jinja2 import Environment, StrictUndefined
from rich.console import Console

from .config import Config
from .llm import LLMClient, Message, ensure_parent, prompt_sha256
from .schemas import GenParams, ModelCfg, Output, Source, Task, slot_name

console = Console(stderr=True)
_env = Environment(undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)


@dataclass(frozen=True)
class Slot:
    task: Task
    source: Source
    archetype: str | None

    @property
    def name(self) -> str:
        return slot_name(self.source.id, self.archetype)


def iter_slots(cfg: Config, tasks: Iterable[Task] | None = None) -> list[Slot]:
    slots = []
    for task in tasks or cfg.tasks:
        for source in cfg.sources:
            for arch in task.archetype_slots:
                slots.append(Slot(task, source, arch))
    return slots


def render_messages(cfg: Config, slot: Slot) -> list[Message]:
    ctx = {
        "source_title": slot.source.meta.title,
        "source_body": slot.source.body.strip(),
        "styleguide": cfg.styleguides[slot.archetype] if slot.archetype else "",
        "limits": slot.task.limits.model_dump(exclude_none=True),
    }
    user = _env.from_string(slot.task.user_prompt).render(**ctx).strip()
    return [
        {"role": "system", "content": slot.task.system_prompt.strip()},
        {"role": "user", "content": user},
    ]


def output_path(cfg: Config, model: ModelCfg, slot: Slot):
    return cfg.paths.outputs / model.id / slot.task.id / f"{slot.name}.json"


def model_is_reachable(model: ModelCfg) -> str | None:
    """Return a reason to skip, or None if the model can be called."""
    if model.litellm_model.startswith("fake/"):
        return None
    if model.api_key_env and not os.environ.get(model.api_key_env):
        return f"{model.api_key_env} not set"
    if model.api_base and "${" in model.api_base:
        return f"api_base env var unset ({model.api_base})"
    return None


async def _generate_one(
    cfg: Config, client: LLMClient, model: ModelCfg, slot: Slot, force: bool
) -> bool:
    path = output_path(cfg, model, slot)
    if path.exists() and not force:
        return False
    messages = render_messages(cfg, slot)
    params = client.effective_params(model, 0.0, slot.task.max_tokens, 42)
    gen_params = GenParams(
        temperature=params.get("temperature", 0.0),
        seed=params.get("seed"),
        max_tokens=slot.task.max_tokens,
    )
    text, err = "", None
    pt = ct = lat = 0
    cost = 0.0
    try:
        res = await client.acomplete(model, messages, 0.0, slot.task.max_tokens, 42)
        text, pt, ct, lat, cost = (
            res.text,
            res.prompt_tokens,
            res.completion_tokens,
            res.latency_ms,
            res.cost_usd,
        )
    except Exception as e:  # noqa: BLE001 — recorded, not raised (§6.2)
        err = f"{type(e).__name__}: {e}"[:500]
    out = Output(
        model_id=model.id,
        pinned_version=model.pinned_version,
        task_id=slot.task.id,
        source_id=slot.source.id,
        archetype=slot.archetype,
        prompt_sha256=prompt_sha256(messages),
        params=gen_params,
        text=text,
        prompt_tokens=pt,
        completion_tokens=ct,
        latency_ms=lat,
        cost_usd=cost,
        created=datetime.now(UTC),
        error=err,
    )
    ensure_parent(path)
    path.write_text(out.model_dump_json(indent=2) + "\n")
    return True


async def _run(
    cfg: Config,
    models: list[ModelCfg],
    slots: list[Slot],
    use_cache: bool,
    force: bool,
    dry_run: bool,
) -> dict[str, int]:
    client = LLMClient(cfg.paths, use_cache=use_cache, stage="generate")
    counts: dict[str, int] = {}
    for model in models:
        reason = model_is_reachable(model)
        if reason:
            console.print(f"[yellow]skip {model.id}: {reason}[/]")
            continue
        if dry_run:
            pending = [s for s in slots if force or not output_path(cfg, model, s).exists()]
            counts[model.id] = len(pending)
            console.print(f"{model.id}: {len(pending)} outputs to generate")
            continue
        results = await asyncio.gather(
            *[_generate_one(cfg, client, model, s, force) for s in slots]
        )
        counts[model.id] = sum(results)
        console.print(f"{model.id}: wrote {counts[model.id]} outputs")
    return counts


def run_generate(
    cfg: Config,
    only: str | None = None,
    models: list[str] | None = None,
    tasks: list[str] | None = None,
    sources: list[str] | None = None,
    use_cache: bool = True,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, int]:
    chosen_models = [m for m in cfg.models if not models or m.id in models]
    chosen_tasks = [t for t in cfg.tasks if not tasks or t.id in tasks]
    slots = iter_slots(cfg, chosen_tasks)
    if sources:
        slots = [s for s in slots if s.source.id in sources]
    if only:
        slots = [s for s in slots if only in f"{s.task.id}/{s.name}"]
    return asyncio.run(_run(cfg, chosen_models, slots, use_cache, force, dry_run))


def status(cfg: Config) -> dict[str, dict[str, int]]:
    """Per model: expected, present, errors."""
    expected = len(iter_slots(cfg))
    table: dict[str, dict[str, int]] = {}
    for model in cfg.models:
        files = list((cfg.paths.outputs / model.id).rglob("*.json"))
        errors = sum(1 for f in files if Output.model_validate_json(f.read_text()).error)
        table[model.id] = {"expected": expected, "present": len(files), "errors": errors}
    return table
