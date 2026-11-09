from datetime import date

import pytest
from pydantic import ValidationError

from danews.schemas import (
    Fact,
    FactsFile,
    ModelsFile,
    Output,
    SourceMeta,
    Task,
    output_ref,
    parse_output_ref,
    slot_ref,
)

GOOD_SOURCE = dict(
    id="folketing-2026-l45",
    title="L 45 Forslag til lov om ændring af ...",
    publisher="Folketinget",
    domain="politics",
    url="https://www.ft.dk/x",
    published="2026-09-14",
    retrieved="2026-11-10",
    licence="Folketinget – fri genanvendelse med kildeangivelse",
    word_count=812,
    language="da",
    planted_ambiguity=False,
    notes="",
)


def test_source_meta_valid():
    m = SourceMeta(**GOOD_SOURCE)
    assert m.published == date(2026, 9, 14)


@pytest.mark.parametrize(
    "patch",
    [
        {"id": "Bad_ID"},
        {"word_count": 299},
        {"word_count": 1501},
        {"published": "2024-12-31"},
        {"domain": "sports"},
        {"licence": ""},
    ],
)
def test_source_meta_invalid(patch):
    with pytest.raises(ValidationError):
        SourceMeta(**{**GOOD_SOURCE, **patch})


def _fact(i, critical=True, **kw):
    base = dict(
        id=f"f{i}",
        type="number",
        value="1,2 mia. kr.",
        canonical=1.2e9,
        unit="DKK",
        span="en samlet ramme på 1,2 mia. kr.",
        critical=critical,
    )
    base.update(kw)
    return base


def test_facts_file_valid():
    ff = FactsFile(source_id="x", facts=[_fact(i, critical=i < 3) for i in range(5)])
    assert len(ff.facts) == 5


def test_facts_file_too_few_or_not_critical():
    with pytest.raises(ValidationError):
        FactsFile(source_id="x", facts=[_fact(i) for i in range(4)])
    with pytest.raises(ValidationError):
        FactsFile(source_id="x", facts=[_fact(i, critical=i < 2) for i in range(5)])


def test_fact_type_canonical_consistency():
    with pytest.raises(ValidationError):
        Fact(**_fact(1, canonical="not a number"))
    Fact(**_fact(2, type="date", value="12. november 2026", canonical="2026-11-12"))
    with pytest.raises(ValidationError):
        Fact(**_fact(3, type="date", canonical="12/11/2026"))


def test_task_max_tokens_and_slots():
    t = Task(
        id="t4_versionering",
        name="Versionering",
        uses_archetypes=["lynposten", "landsavisen"],
        output_kind="text",
        limits={"max_words": 275, "min_words": 225},
        dimensions=["grounding", "tone", "fluency", "format"],
        system_prompt="s",
        user_prompt="u",
    )
    assert t.max_tokens == 275 * 3 + 200
    assert t.archetype_slots == ["lynposten", "landsavisen"]
    t1 = t.model_copy(update={"uses_archetypes": []})
    assert t1.archetype_slots == [None]


def test_models_file_judges_must_exist():
    model = dict(
        id="anthropic-frontier",
        display="Claude",
        family="anthropic",
        tier="frontier_proprietary",
        litellm_model="anthropic/x",
        pinned_version="x",
        billing="paid",
        open_weights=False,
        licence="proprietary",
        eu_residency="cloud region",
    )
    ModelsFile(judges={"A": "anthropic-frontier"}, models=[model])
    with pytest.raises(ValidationError):
        ModelsFile(judges={"A": "missing"}, models=[model])


def test_output_example_and_refs():
    o = Output(
        model_id="anthropic-frontier",
        pinned_version="v",
        task_id="t4_versionering",
        source_id="folketing-2026-l45",
        archetype="lynposten",
        prompt_sha256="abc",
        params={"temperature": 0, "seed": 42, "max_tokens": 1200},
        text="...",
        prompt_tokens=1830,
        completion_tokens=410,
        latency_ms=5120,
        cost_usd=0.0123,
        created="2026-11-11T14:02:11Z",
        error=None,
    )
    assert o.ref == "anthropic-frontier/t4_versionering/folketing-2026-l45__lynposten"
    assert o.slot_ref == "t4_versionering/folketing-2026-l45__lynposten"
    assert parse_output_ref(o.ref) == (
        "anthropic-frontier",
        "t4_versionering",
        "folketing-2026-l45",
        "lynposten",
    )
    assert output_ref("m", "t1_telegram", "s", None) == "m/t1_telegram/s"
    assert slot_ref("t1_telegram", "s", None) == "t1_telegram/s"
