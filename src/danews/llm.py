"""Single gateway for all model calls: LiteLLM, retries, disk cache, cost log (§4).

No other module may import a vendor SDK. The `fake/echo` provider returns deterministic
text derived from the prompt so the whole pipeline can run offline in tests and `make smoke`.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from .config import Paths
from .schemas import CostRecord, ModelCfg

Message = dict[str, str]

FAKE_PREFIX = "fake/"


@dataclass
class LLMResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    cost_usd: float
    provider_request_id: str | None
    cached: bool = False

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def cache_key(model_id: str, messages: list[Message], params: dict[str, Any]) -> str:
    blob = json.dumps(
        {"model_id": model_id, "messages": messages, "params": params},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(blob.encode()).hexdigest()


def prompt_sha256(messages: list[Message]) -> str:
    return hashlib.sha256(
        json.dumps(messages, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def cost_for(cfg: ModelCfg, prompt_tokens: int, completion_tokens: int) -> float:
    return (
        prompt_tokens * cfg.price_in_per_m + completion_tokens * cfg.price_out_per_m
    ) / 1_000_000


def log_cost(paths: Paths, stage: str, cfg: ModelCfg, res: LLMResult) -> None:
    rec = CostRecord(
        ts=datetime.now(UTC),
        stage=stage,
        model_id=cfg.id,
        prompt_tokens=res.prompt_tokens,
        completion_tokens=res.completion_tokens,
        cost_usd=res.cost_usd,
        cached=res.cached,
    )
    with paths.costs.open("a") as f:
        f.write(rec.model_dump_json() + "\n")


def _is_retryable(exc: BaseException) -> bool:
    name = type(exc).__name__
    if any(
        k in name
        for k in ("RateLimit", "Timeout", "ServiceUnavailable", "InternalServer", "APIConnection")
    ):
        return True
    status = getattr(exc, "status_code", None)
    return status is not None and (status == 429 or 500 <= int(status) < 600)


class LLMClient:
    def __init__(self, paths: Paths, use_cache: bool = True, stage: str = "unknown"):
        self.paths = paths
        self.use_cache = use_cache
        self.stage = stage
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    # Public API --------------------------------------------------------------

    def complete(
        self,
        model_cfg: ModelCfg,
        messages: list[Message],
        temperature: float = 0.0,
        max_tokens: int = 1024,
        seed: int | None = 42,
    ) -> LLMResult:
        return asyncio.run(self.acomplete(model_cfg, messages, temperature, max_tokens, seed))

    async def acomplete(
        self,
        model_cfg: ModelCfg,
        messages: list[Message],
        temperature: float = 0.0,
        max_tokens: int = 1024,
        seed: int | None = 42,
    ) -> LLMResult:
        params = self.effective_params(model_cfg, temperature, max_tokens, seed)
        key = cache_key(model_cfg.id, messages, params)
        cache_file = self.paths.cache / f"{key}.json"
        if self.use_cache and cache_file.exists():
            res = LLMResult(**json.loads(cache_file.read_text()))
            res.cached = True
            log_cost(self.paths, self.stage, model_cfg, res)
            return res
        sem = self._semaphore(model_cfg)
        async with sem:
            res = await self._call_with_retry(model_cfg, messages, params)
        res.cost_usd = cost_for(model_cfg, res.prompt_tokens, res.completion_tokens)
        self.paths.cache.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(res.to_json(), ensure_ascii=False))
        log_cost(self.paths, self.stage, model_cfg, res)
        return res

    @staticmethod
    def effective_params(
        cfg: ModelCfg, temperature: float, max_tokens: int, seed: int | None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"max_tokens": max_tokens}
        if cfg.supports_temperature:
            params["temperature"] = temperature
        if cfg.supports_seed and seed is not None:
            params["seed"] = seed
        return params

    # Internals ---------------------------------------------------------------

    def _semaphore(self, cfg: ModelCfg) -> asyncio.Semaphore:
        provider = cfg.api_base or cfg.litellm_model.split("/")[0]
        if provider not in self._semaphores:
            self._semaphores[provider] = asyncio.Semaphore(cfg.max_concurrency)
        return self._semaphores[provider]

    async def _call_with_retry(
        self, cfg: ModelCfg, messages: list[Message], params: dict[str, Any]
    ) -> LLMResult:
        @retry(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, min=1, max=30),
            retry=retry_if_exception(_is_retryable),
            reraise=True,
        )
        async def _inner() -> LLMResult:
            return await self._call(cfg, messages, params)

        return await _inner()

    async def _call(
        self, cfg: ModelCfg, messages: list[Message], params: dict[str, Any]
    ) -> LLMResult:
        if cfg.litellm_model.startswith(FAKE_PREFIX):
            return fake_complete(cfg, messages, params)
        import litellm  # the only place a model SDK is touched

        litellm.suppress_debug_info = True
        kwargs: dict[str, Any] = dict(model=cfg.litellm_model, messages=messages, **params)
        if cfg.api_base:
            kwargs["api_base"] = cfg.api_base
        if cfg.api_key_env:
            key = os.environ.get(cfg.api_key_env)
            if not key:
                raise RuntimeError(f"{cfg.api_key_env} not set (needed for {cfg.id})")
            kwargs["api_key"] = key
        t0 = time.perf_counter()
        resp = await litellm.acompletion(**kwargs)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        choice = resp.choices[0]
        text = (choice.message.content or "").strip()
        usage = resp.usage
        return LLMResult(
            text=text,
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            latency_ms=latency_ms,
            cost_usd=0.0,
            provider_request_id=getattr(resp, "id", None),
        )


# Fake provider ---------------------------------------------------------------

_DANISH_FILLER = (
    "Det oplyser kilden. Beslutningen gælder fra i år. Flere parter er berørt af sagen. "
    "Tallene stammer fra den seneste opgørelse. Ministeren har ikke kommenteret sagen yderligere. "
).split()


def _det_rng(seed_text: str) -> int:
    return int(hashlib.sha256(seed_text.encode()).hexdigest()[:8], 16)


def _source_body(user_prompt: str) -> str:
    m = re.search(r"KILDE:.*?\n(.*)\Z", user_prompt, re.S)
    return m.group(1).strip() if m else user_prompt


def _n_words(text: str, n: int) -> str:
    ws = text.split()
    if len(ws) >= n:
        return " ".join(ws[:n])
    out = list(ws)
    i = 0
    while len(out) < n:
        out.append(_DANISH_FILLER[i % len(_DANISH_FILLER)])
        i += 1
    return " ".join(out)


def fake_complete(cfg: ModelCfg, messages: list[Message], params: dict[str, Any]) -> LLMResult:
    """Deterministic stand-in: shapes its answer to the prompt so format checks can pass."""
    user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    seed = _det_rng(cfg.id + user)
    variant = cfg.litellm_model.removeprefix(FAKE_PREFIX)
    if '"claims"' in user:
        text = json.dumps(
            {
                "claims": [
                    {
                        "text": "Påstand A",
                        "label": "supported",
                        "source_span": "A",
                        "rationale": "ok",
                    },
                    {
                        "text": "Påstand B",
                        "label": "unsupported" if seed % 3 == 0 else "supported",
                        "source_span": None,
                        "rationale": "r",
                    },
                    {
                        "text": "Påstand C",
                        "label": "contradicted" if seed % 7 == 0 else "supported",
                        "source_span": "C",
                        "rationale": "r",
                    },
                ]
            },
            ensure_ascii=False,
        )
    elif '"winner"' in user:
        text = json.dumps(
            {
                "winner": ["left", "right", "tie"][seed % 3],
                "confidence": 1 + seed % 3,
                "rationale": "fake",
            }
        )
    elif '"score"' in user:
        text = json.dumps(
            {
                "score": 1 + seed % 5,
                "issues": ["særskrivning"] if seed % 2 else [],
                "rationale": "fake",
            }
        )
    elif "RUBRIK:" in user:
        body = _source_body(user)
        text = f"RUBRIK: {_n_words(body, 5)}\nUNDERRUBRIK: {_n_words(body, 14)}"
    elif "præcis 5 punkter" in user:
        body = _source_body(user)
        ws = body.split()
        text = "\n".join(f"- {' '.join(ws[i * 12 : (i + 1) * 12]) or 'Punkt.'}" for i in range(5))
    else:
        body = _source_body(user)
        m = re.search(r"(\d+)[–-](\d+) ord", user)
        lo, hi = (int(m.group(1)), int(m.group(2))) if m else (90, 120)
        n = lo + (seed % (hi - lo + 1))
        if variant == "bad":  # a second fake model that breaks limits, for tests
            n = hi + 40
        text = _n_words(body, n)
        if "oplæsning" in user:
            text = re.sub(r"\d+", "tolv", text)
    prompt_tokens = sum(len(m["content"].split()) for m in messages)
    return LLMResult(
        text=text,
        prompt_tokens=prompt_tokens,
        completion_tokens=len(text.split()),
        latency_ms=1 + seed % 50,
        cost_usd=0.0,
        provider_request_id=f"fake-{seed}",
    )


def read_costs(paths: Paths) -> list[CostRecord]:
    if not paths.costs.exists():
        return []
    return [
        CostRecord.model_validate_json(line)
        for line in paths.costs.read_text().splitlines()
        if line.strip()
    ]


def ensure_parent(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
