import json

from danews.analysis import bootstrap_ci, bt_ratings
from danews.check import run_check
from danews.generate import run_generate
from danews.judge import run_fluency, run_grounding, run_tone
from danews.report import run_report
from danews.schemas import TonePairRecord


def test_bootstrap_ci_is_an_interval():
    groups = [[10.0, 12.0], [50.0], [90.0, 95.0, 100.0]]
    point, lo, hi = bootstrap_ci(groups, n_boot=200)
    assert lo <= point <= hi and lo < hi


def test_bt_ratings_mean_50_and_order():
    pairs = [
        TonePairRecord(
            slot_ref=f"t4/s{i}__a",
            judge_id="j",
            left_model="a",
            right_model="b",
            order_seed=0,
            winner="left",
            confidence=2,
            rationale="",
        )
        for i in range(6)
    ]
    pairs += [
        TonePairRecord(
            slot_ref="t4/s9__a",
            judge_id="j",
            left_model="a",
            right_model="b",
            order_seed=0,
            winner="tie",
            confidence=1,
            rationale="",
        )
    ]
    r = bt_ratings(pairs, ["a", "b"])
    assert r["a"] > r["b"] and abs((r["a"] + r["b"]) / 2 - 50) < 1e-6


def test_report_from_committed_scores_without_api(fixture_cfg, monkeypatch):
    run_generate(fixture_cfg, models=["fake-echo", "fake-bad"])
    run_check(fixture_cfg)
    run_grounding(fixture_cfg)
    run_fluency(fixture_cfg)
    run_tone(fixture_cfg)
    # report must not touch the LLM layer at all
    import danews.llm as llm

    monkeypatch.setattr(
        llm.LLMClient,
        "acomplete",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("API call in report")),
    )
    info = run_report(fixture_cfg, n_boot=50)
    res = fixture_cfg.paths.results
    md = (res / "leaderboard.md").read_text()
    assert info["figures"] == 4
    for section in (
        "## Afhængighed",
        "## Resultater pr. opgave",
        "## Begrænsninger",
        "## v2",
        "## Reproducér",
        "Vejledende",
    ):
        assert section in md
    assert "[" in md and ";" in md  # intervals rendered
    lower = md.lower()
    assert "samlet score" in lower and "composite" not in lower
    data = json.loads((res / "site_data.json").read_text())
    assert {t["id"] for t in data["tasks"]} == {t.id for t in fixture_cfg.tasks}
    for t in data["tasks"]:
        for row in t["rows"]:
            assert set(row) & {"pct_supported", "fluency", "tone_bt", "format_pass_pct"}
            assert not any(k.startswith(("composite", "overall", "total_score")) for k in row)
    assert (res / "task_t4_versionering.csv").exists() and (res / "dependency.csv").exists()
    # format failures from the 'bad' fake model are visible
    t1 = next(t for t in data["tasks"] if t["id"] == "t1_telegram")
    bad = next(r for r in t1["rows"] if r["model_id"] == "fake-bad")
    assert bad["format_pass_pct"] == 0.0
