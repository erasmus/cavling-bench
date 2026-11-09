"""All pydantic models for DaNews-Edit (REQUIREMENTS.md §5)."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Domain = Literal["politics", "economy", "courts", "consumer", "local", "oversight"]
FactType = Literal["number", "date", "name", "place", "org", "quote"]
OutputKind = Literal["text", "headline_pair", "bullets", "script"]
Dimension = Literal["grounding", "tone", "fluency", "format"]
Tier = Literal["frontier_proprietary", "mid_proprietary", "eu", "open_global", "open_nordic"]
Billing = Literal["paid", "credit_mistral", "credit_nebius", "local"]
ClaimLabel = Literal["supported", "unsupported", "contradicted"]
Winner = Literal["left", "right", "tie"]

DOMAIN_COUNTS: dict[str, int] = {
    "politics": 8,
    "economy": 8,
    "courts": 6,
    "consumer": 6,
    "local": 6,
    "oversight": 6,
}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MIN_PUBLISHED = date(2025, 1, 1)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# §5.1 -----------------------------------------------------------------------


class SourceMeta(Strict):
    id: str
    title: str
    publisher: str
    domain: Domain
    url: str
    published: date
    retrieved: date
    licence: str = Field(min_length=1)
    word_count: int = Field(ge=300, le=1500)
    language: Literal["da"] = "da"
    planted_ambiguity: bool = False
    notes: str = ""
    needs_manual: bool = False

    @field_validator("id")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not SLUG_RE.match(v):
            raise ValueError(f"id must match {SLUG_RE.pattern}: {v!r}")
        return v

    @field_validator("published")
    @classmethod
    def _recent(cls, v: date) -> date:
        if v < MIN_PUBLISHED:
            raise ValueError(f"published must be >= {MIN_PUBLISHED}: {v}")
        return v


class Source(BaseModel):
    """A source text: front matter plus body."""

    meta: SourceMeta
    body: str

    @property
    def id(self) -> str:
        return self.meta.id


# §5.2 -----------------------------------------------------------------------


class Fact(Strict):
    id: str
    type: FactType
    value: str
    canonical: float | str
    unit: str | None = None
    span: str
    critical: bool = False

    @field_validator("span")
    @classmethod
    def _span_len(cls, v: str) -> str:
        if len(v.split()) > 15:
            raise ValueError("span must be <= 15 words")
        return v

    @model_validator(mode="after")
    def _canonical_type(self) -> Fact:
        if self.type == "number" and not isinstance(self.canonical, int | float):
            raise ValueError("number facts need a numeric canonical")
        if self.type == "date":
            if not isinstance(self.canonical, str):
                raise ValueError("date facts need an ISO string canonical")
            if not re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", self.canonical):
                raise ValueError(f"date canonical must be ISO YYYY[-MM[-DD]]: {self.canonical!r}")
        return self


class FactsFile(Strict):
    source_id: str
    facts: list[Fact] = Field(min_length=5)

    @model_validator(mode="after")
    def _critical(self) -> FactsFile:
        n_crit = sum(f.critical for f in self.facts)
        if n_crit < 3:
            raise ValueError(f"need >= 3 critical facts, got {n_crit}")
        ids = [f.id for f in self.facts]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate fact ids")
        return self


# §5.3 -----------------------------------------------------------------------


class TaskLimits(Strict):
    min_words: int | None = None
    max_words: int | None = None
    max_headline_chars: int | None = None
    max_subheadline_chars: int | None = None
    bullets: int | None = None
    max_words_per_bullet: int | None = None


class Task(Strict):
    id: str
    name: str
    uses_archetypes: list[str]
    output_kind: OutputKind
    limits: TaskLimits
    dimensions: list[Dimension]
    system_prompt: str
    user_prompt: str

    @property
    def archetype_slots(self) -> list[str | None]:
        return list(self.uses_archetypes) if self.uses_archetypes else [None]

    @property
    def max_tokens(self) -> int:
        """§6.2: limits.max_words × 3 + 200; headline pairs get a fixed small budget."""
        if self.limits.max_words:
            return self.limits.max_words * 3 + 200
        if self.limits.bullets:
            return (self.limits.bullets * (self.limits.max_words_per_bullet or 25)) * 3 + 200
        return 400


# §5.5 -----------------------------------------------------------------------


class ModelCfg(Strict):
    id: str
    display: str
    family: str
    tier: Tier
    litellm_model: str
    pinned_version: str
    billing: Billing
    api_base: str | None = None
    api_key_env: str | None = None
    price_in_per_m: float = 0.0
    price_out_per_m: float = 0.0
    open_weights: bool
    licence: str
    eu_residency: str
    params_b: float | None = None
    max_concurrency: int = 4
    supports_seed: bool = False
    supports_temperature: bool = True
    notes: str = ""
    enabled: bool = True


class Judges(Strict):
    A: str
    B: str | None = None


class ModelsFile(Strict):
    judges: Judges
    judge_b_sample_fraction: float = 0.25
    models: list[ModelCfg]

    @model_validator(mode="after")
    def _judges_exist(self) -> ModelsFile:
        ids = {m.id for m in self.models}
        for j in (self.judges.A, self.judges.B):
            if j is not None and j not in ids:
                raise ValueError(f"judge {j!r} not in models")
        if len(ids) != len(self.models):
            raise ValueError("duplicate model ids")
        return self

    def get(self, model_id: str) -> ModelCfg:
        for m in self.models:
            if m.id == model_id:
                return m
        raise KeyError(model_id)


# §5.6 -----------------------------------------------------------------------


class GenParams(Strict):
    temperature: float = 0.0
    seed: int | None = 42
    max_tokens: int


class Output(Strict):
    model_id: str
    pinned_version: str
    task_id: str
    source_id: str
    archetype: str | None
    prompt_sha256: str
    params: GenParams
    text: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    cost_usd: float
    created: datetime
    error: str | None = None

    @property
    def ref(self) -> str:
        return output_ref(self.model_id, self.task_id, self.source_id, self.archetype)

    @property
    def slot_ref(self) -> str:
        return slot_ref(self.task_id, self.source_id, self.archetype)


def slot_name(source_id: str, archetype: str | None) -> str:
    return f"{source_id}__{archetype}" if archetype else source_id


def output_ref(model_id: str, task_id: str, source_id: str, archetype: str | None) -> str:
    return f"{model_id}/{task_id}/{slot_name(source_id, archetype)}"


def slot_ref(task_id: str, source_id: str, archetype: str | None) -> str:
    return f"{task_id}/{slot_name(source_id, archetype)}"


def parse_output_ref(ref: str) -> tuple[str, str, str, str | None]:
    model_id, task_id, slot = ref.split("/")
    source_id, _, arch = slot.partition("__")
    return model_id, task_id, source_id, arch or None


# §5.7 -----------------------------------------------------------------------


class Medianism(Strict):
    hedges: int
    fillers: int
    generic_phrases: int
    anglicisms: int
    passive_share: float
    mean_sentence_len: float
    sentence_len_sd: float


class CheckRecord(Strict):
    output_ref: str
    format_pass: bool
    format_fail_reasons: list[str]
    facts_total: int
    facts_preserved: int
    facts_missing: list[str]
    facts_fuzzy: list[str] = []
    lang_leak_tokens: int
    saerskrivning_suspects: list[str]
    medianism: Medianism


class Claim(Strict):
    text: str
    label: ClaimLabel
    source_span: str | None = None
    rationale: str = ""


class JudgeGroundingResponse(Strict):
    claims: list[Claim]


class GroundingRecord(Strict):
    output_ref: str
    judge_id: str
    claims: list[Claim]
    n_claims: int
    pct_supported: float
    n_contradicted: int
    error: str | None = None


class JudgeToneResponse(Strict):
    winner: Winner
    confidence: int = Field(ge=1, le=3)
    rationale: str


class TonePairRecord(Strict):
    slot_ref: str
    judge_id: str
    left_model: str
    right_model: str
    order_seed: int
    winner: Winner | None
    confidence: int | None
    rationale: str
    error: str | None = None


class JudgeFluencyResponse(Strict):
    score: int = Field(ge=1, le=5)
    issues: list[str] = []
    rationale: str


class FluencyRecord(Strict):
    output_ref: str
    judge_id: str
    score: int | None
    issues: list[str]
    rationale: str
    error: str | None = None


class CostRecord(Strict):
    ts: datetime
    stage: str
    model_id: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    cached: bool
