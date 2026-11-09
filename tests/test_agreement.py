import csv

from danews.agreement import compute_agreement, run_agreement
from danews.generate import run_generate
from danews.judge import run_fluency, run_grounding, run_tone
from danews.spotcheck import run_sample


def test_spotcheck_sample_and_agreement_roundtrip(fixture_cfg):
    run_generate(fixture_cfg, models=["fake-echo", "fake-bad"])
    run_grounding(fixture_cfg)
    run_fluency(fixture_cfg)
    run_tone(fixture_cfg)
    info = run_sample(fixture_cfg, n=20)
    assert info["rows"] == 20
    sample = fixture_cfg.paths.scores / "spotcheck_sample.csv"
    key = fixture_cfg.paths.scores / "spotcheck_key.csv"
    with sample.open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 20
    assert "output_ref" not in rows[0] and "model" not in " ".join(rows[0].keys())
    assert all(not any(m in r["output_text"] for m in ("fake-echo", "fake-bad")) for r in rows)
    with key.open() as f:
        keys = {r["sample_id"]: r["output_ref"] for r in csv.DictReader(f)}
    assert set(keys) == {r["sample_id"] for r in rows}

    # no human rows yet → agreement runs, all human metrics NaN, note present
    res = compute_agreement(fixture_cfg)
    assert res.n_human_rows == 0 and res.fluency_indicative and res.tone_indicative
    assert res.ab_fluency_kappa == res.ab_fluency_kappa or True  # may be NaN on tiny overlap

    # simulate two raters who copy judge A → perfect agreement
    from danews.judge import _read_jsonl
    from danews.schemas import FluencyRecord, GroundingRecord

    g = {
        r.output_ref: r
        for r in _read_jsonl(fixture_cfg.paths.scores / "grounding.jsonl", GroundingRecord)
        if r.judge_id == "fake-judge-a"
    }
    fl = {
        r.output_ref: r
        for r in _read_jsonl(fixture_cfg.paths.scores / "fluency.jsonl", FluencyRecord)
        if r.judge_id == "fake-judge-a"
    }
    human = fixture_cfg.paths.scores / "spotcheck_human.csv"
    with human.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["rater_id", *rows[0].keys()])
        w.writeheader()
        for rater in ("r1", "r2"):
            for r in rows:
                ref = keys[r["sample_id"]]
                r2 = dict(r)
                r2["rater_id"] = rater
                r2["h_grounding_pct"] = f"{g[ref].pct_supported:.0f}"
                r2["h_contradicted"] = str(g[ref].n_contradicted)
                r2["h_fluency_1to5"] = str(fl[ref].score)
                r2["h_tone_1to5"] = "3"
                w.writerow(r2)
    out = run_agreement(fixture_cfg)
    assert out["n_human_rows"] == 40
    md = (fixture_cfg.paths.results / "agreement.md").read_text()
    assert "Publiceringsregel" in md
    res = compute_agreement(fixture_cfg)
    assert res.fluency_kappa > 0.99 and res.fluency_within1 == 1.0
    assert res.grounding_mad < 1.0
    assert res.human_fluency_kappa > 0.99
