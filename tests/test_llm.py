import json

import pytest

from danews.config import Paths
from danews.llm import LLMClient, cache_key, cost_for, fake_complete, read_costs
from danews.schemas import ModelCfg


def _cfg(**kw):
    base = dict(
        id="fake-echo",
        display="Fake",
        family="fake",
        tier="open_nordic",
        litellm_model="fake/echo",
        pinned_version="fake-1",
        billing="local",
        open_weights=True,
        licence="MIT",
        eu_residency="self-hosted",
        price_in_per_m=1.0,
        price_out_per_m=2.0,
    )
    base.update(kw)
    return ModelCfg(**base)


def test_fake_is_deterministic_and_respects_word_range():
    msgs = [
        {
            "role": "user",
            "content": "Skriv et nyhedstelegram på 90–120 ord.\n\nKILDE: T\n" + "ord " * 300,
        }
    ]
    a = fake_complete(_cfg(), msgs, {})
    b = fake_complete(_cfg(), msgs, {})
    assert a.text == b.text
    assert 90 <= len(a.text.split()) <= 120


def test_fake_headline_format():
    msgs = [
        {
            "role": "user",
            "content": "Svar præcis i dette format:\nRUBRIK: <tekst>\nUNDERRUBRIK: <tekst>\n\n"
            + "KILDE: T\n"
            + "ord " * 50,
        }
    ]
    r = fake_complete(_cfg(), msgs, {})
    assert r.text.startswith("RUBRIK: ") and "\nUNDERRUBRIK: " in r.text


def test_fake_judge_json():
    r = fake_complete(
        _cfg(), [{"role": "user", "content": 'Return JSON only: {"claims":[...]}'}], {}
    )
    assert "claims" in json.loads(r.text)


def test_cache_and_cost_log(tmp_path):
    paths = Paths(tmp_path)
    client = LLMClient(paths, stage="test")
    cfg = _cfg()
    msgs = [{"role": "user", "content": "Skriv 90–120 ord\n\nKILDE: X\n" + "a " * 200}]
    r1 = client.complete(cfg, msgs, max_tokens=100)
    r2 = client.complete(cfg, msgs, max_tokens=100)
    assert not r1.cached and r2.cached
    assert r1.text == r2.text
    assert r1.cost_usd == cost_for(cfg, r1.prompt_tokens, r1.completion_tokens) > 0
    costs = read_costs(paths)
    assert [c.cached for c in costs] == [False, True]
    assert costs[0].stage == "test"
    r3 = LLMClient(paths, use_cache=False).complete(cfg, msgs, max_tokens=100)
    assert not r3.cached


def test_cache_key_depends_on_params():
    msgs = [{"role": "user", "content": "x"}]
    assert cache_key("m", msgs, {"max_tokens": 1}) != cache_key("m", msgs, {"max_tokens": 2})


def test_effective_params_drop_unsupported():
    p = LLMClient.effective_params(
        _cfg(supports_seed=False, supports_temperature=False), 0.0, 10, 42
    )
    assert p == {"max_tokens": 10}
    p = LLMClient.effective_params(_cfg(supports_seed=True), 0.0, 10, 42)
    assert p == {"max_tokens": 10, "temperature": 0.0, "seed": 42}


def test_effective_params_reasoning_budget_and_effort():
    cfg = _cfg(reasoning_effort="low", reasoning_budget_tokens=1500)
    p = LLMClient.effective_params(cfg, 0.0, 400, None)
    assert p == {"max_tokens": 1900, "temperature": 0.0, "reasoning_effort": "low"}


def test_empty_truncated_completion_is_an_error():
    from danews.llm import EmptyCompletion, finalise_text

    assert finalise_text("  svar  ", "stop") == "svar"
    with pytest.raises(EmptyCompletion):
        finalise_text("", "length")


def test_empty_completion_still_logs_cost_and_is_not_cached(tmp_path):
    from danews.llm import EmptyCompletion

    paths = Paths(root=tmp_path)
    client = LLMClient(paths, use_cache=True, stage="generate")
    cfg = _cfg(id="fake-empty", litellm_model="fake/empty")
    msgs = [{"role": "user", "content": "Skriv noget."}]
    with pytest.raises(EmptyCompletion) as ei:
        client.complete(cfg, msgs, max_tokens=50)
    # usage travels with the exception so callers can record it on the Output
    assert ei.value.result is not None
    assert ei.value.result.completion_tokens > 0
    assert ei.value.result.cost_usd > 0
    costs = read_costs(paths)
    assert len(costs) == 1
    assert costs[0].model_id == "fake-empty" and costs[0].cost_usd > 0
    assert not list(paths.cache.glob("*.json"))
