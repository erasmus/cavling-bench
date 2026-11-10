import json

from danews.generate import run_generate
from danews.judge import (
    _judges,
    extract_json,
    run_fluency,
    run_grounding,
    run_tone,
    single_judge_cells,
    stratified_sample,
    tone_pairs,
)
from danews.schemas import FluencyRecord, GroundingRecord, TonePairRecord


def test_extract_json_handles_fences_and_prose():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Here you go: {"a": [1, 2]} thanks') == {"a": [1, 2]}


def test_stratified_sample_takes_ceil_fraction_per_stratum():
    items = [("t1", i) for i in range(10)] + [("t2", i) for i in range(3)]
    s = stratified_sample(items, lambda x: x[0], 0.25)
    assert sum(1 for x in s if x[0] == "t1") == 3
    assert sum(1 for x in s if x[0] == "t2") == 1
    assert s == stratified_sample(items, lambda x: x[0], 0.25)


def _lines(path, model):
    return [model.model_validate_json(ln) for ln in path.read_text().splitlines() if ln.strip()]


def test_judges_end_to_end_on_fixtures(fixture_cfg):
    run_generate(fixture_cfg, models=["fake-echo", "fake-bad"])
    g = run_grounding(fixture_cfg)
    assert g["fake-judge-a"] == 54  # 27 slots × 2 models, judge A on all
    assert g["fake-judge-b"] > 0  # 50 % sample in the fixture models.yaml
    recs = _lines(fixture_cfg.paths.scores / "grounding.jsonl", GroundingRecord)
    assert all(r.error is None for r in recs)
    assert all(0 <= r.pct_supported <= 100 for r in recs)
    # idempotent: a second run adds nothing
    assert run_grounding(fixture_cfg) == {
        "fake-judge-a": 0,
        "fake-judge-a_errors": 0,
        "fake-judge-b": 0,
        "fake-judge-b_errors": 0,
    }

    f = run_fluency(fixture_cfg)
    assert f["fake-judge-a"] == 54
    frecs = _lines(fixture_cfg.paths.scores / "fluency.jsonl", FluencyRecord)
    assert all(r.score in {1, 2, 3, 4, 5} for r in frecs)

    pairs = tone_pairs(fixture_cfg, [])
    assert pairs == []
    t = run_tone(fixture_cfg)
    trecs = _lines(fixture_cfg.paths.scores / "tone_pairs.jsonl", TonePairRecord)
    # T2 (3 sources × 3 archetypes) + T4 (3 × 2) + T6 (3 × 1) = 18 slots, 2 models → 1 pair each
    assert t["fake-judge-a"] == 18
    assert all(r.winner in {"left", "right", "tie"} for r in trecs)
    assert {(r.left_model, r.right_model) for r in trecs} <= {
        ("fake-echo", "fake-bad"),
        ("fake-bad", "fake-echo"),
    }
    # cross-family rule: judge B shares family "fake" with fake-echo, so it grades no tone pairs
    assert "fake-judge-b_skipped_cross_family" in t
    assert t.get("fake-judge-b", 0) == 0
    assert single_judge_cells(fixture_cfg) == [
        ("fake-echo", "tone"),
        ("fake-judge-a", "tone"),
    ]
    # model names never reach the judge prompt
    cache_files = list(fixture_cfg.paths.cache.glob("*.json"))
    assert cache_files
    for cf in cache_files:
        rec = json.loads(cf.read_text())
        assert "fake-echo" not in rec["text"] or "RUBRIK" in rec["text"]


def test_unreachable_judge_is_skipped_and_error_records_are_retried(fixture_cfg, monkeypatch):
    from danews.judge import _append_jsonl

    run_generate(fixture_cfg, models=["fake-echo"])
    # A judge whose key is missing is skipped with a notice, not recorded as 27 errors.
    monkeypatch.setattr(
        "danews.judge.model_is_reachable",
        lambda m: "DANEWS_TEST_MISSING_KEY not set" if m.id == "fake-judge-b" else None,
    )
    g = run_grounding(fixture_cfg)
    assert g["fake-judge-a"] == 27
    assert "fake-judge-b" not in g
    assert g["fake-judge-b_skipped"] == "DANEWS_TEST_MISSING_KEY not set"
    # An existing error record does not count as done.
    path = fixture_cfg.paths.scores / "grounding.jsonl"
    recs = _lines(path, GroundingRecord)
    bad = recs[0].model_copy(update={"error": "RuntimeError: boom", "claims": []})
    path.write_text("".join(r.model_dump_json() + "\n" for r in recs[1:]))
    _append_jsonl(path, [bad])
    g2 = run_grounding(fixture_cfg)
    assert g2["fake-judge-a"] == 1
    a_recs = [r for r in _lines(path, GroundingRecord) if r.judge_id == "fake-judge-a"]
    assert all(r.error is None for r in a_recs)


def test_disabled_row_is_judge_only(fixture_cfg):
    """`enabled: false` keeps a row out of the generator set but it can still be a judge."""
    assert "fake-judge-b" not in {m.id for m in fixture_cfg.models}
    assert [j.id for j in _judges(fixture_cfg)] == ["fake-judge-a", "fake-judge-b"]
