from danews import check
from danews.schemas import Fact


def _task(cfg, tid):
    return cfg.task(tid)


ABBR = {"bl.a.", "pct.", "mio.", "mia.", "kr.", "ca.", "f.eks.", "dvs."}


def test_t1_word_limits(fixture_cfg):
    t = _task(fixture_cfg, "t1_telegram")
    assert check.check_format(t, " ".join(["ord"] * 100), ABBR) == []
    assert check.check_format(t, " ".join(["ord"] * 89), ABBR) == ["words=89<90"]
    assert check.check_format(t, " ".join(["ord"] * 121), ABBR) == ["words=121>120"]
    assert check.check_format(t, "", ABBR) == ["empty_output"]


def test_t2_headline_pair(fixture_cfg):
    t = _task(fixture_cfg, "t2_rubrik")
    ok = "RUBRIK: Ledigheden falder igen\nUNDERRUBRIK: 1.200 færre ledige i september, viser tal."
    assert check.check_format(t, ok, ABBR) == []
    too_long = "RUBRIK: " + "x" * 61 + "\nUNDERRUBRIK: kort"
    assert check.check_format(t, too_long, ABBR) == ["headline_chars=61>60"]
    missing = "RUBRIK: fin rubrik"
    assert "subheadline_count=0" in check.check_format(t, missing, ABBR)
    extra = ok + "\nHer er en forklaring."
    assert "extra_lines" in check.check_format(t, extra, ABBR)


def test_t3_bullets(fixture_cfg):
    t = _task(fixture_cfg, "t3_faktaboks")
    five = "\n".join(f"- Punkt {i} er en kort sætning." for i in range(5))
    assert check.check_format(t, five, ABBR) == []
    four = "\n".join(f"- Punkt {i}." for i in range(4))
    assert check.check_format(t, four, ABBR) == ["bullet_count=4!=5"]
    long_bullet = "\n".join(["- " + " ".join(["ord"] * 26)] + [f"- Punkt {i}." for i in range(4)])
    assert check.check_format(t, long_bullet, ABBR) == ["bullet_1_words=26>25"]


def test_t6_digits_and_abbreviations(fixture_cfg):
    t = _task(fixture_cfg, "t6_lydmanus")
    base = " ".join(["ord"] * 110)
    assert check.check_format(t, base + " i 2026.", ABBR) == []
    assert check.check_format(t, base + " med 12 procent.", ABBR) == ["digits=12"]
    assert check.check_format(t, base + " bl.a. staten.", ABBR) == ["abbreviations=bl.a."]
    # 'kr.' inside 'kroner' must not match; year 1998 allowed
    assert check.check_format(t, base + " tolv kroner i 1998.", ABBR) == []


def test_fact_numbers():
    f = Fact(id="f", type="number", value="1,2 mia. kr.", canonical=1.2e9, unit="DKK", span="x")
    assert check.fact_preserved(f, "Rammen er på 1,2 mia. kr.").preserved
    assert check.fact_preserved(f, "Rammen er på 1.200 mio. kr.").preserved
    assert check.fact_preserved(f, "Rammen er på 1.195 millioner kroner").preserved  # within 0.5 %
    assert not check.fact_preserved(f, "Rammen er på 1,3 mia. kr.").preserved
    pct = Fact(id="p", type="number", value="12 pct.", canonical=12, unit="%", span="x")
    assert check.fact_preserved(pct, "steg 12 procent").preserved
    assert check.fact_preserved(pct, "steg 12 %").preserved
    assert not check.fact_preserved(pct, "steg 12 kr.").preserved
    small = Fact(id="s", type="number", value="seks måneder", canonical=6, span="x")
    assert check.fact_preserved(small, "en frist på seks måneder").preserved
    assert check.fact_preserved(small, "en frist på 6 måneder").preserved


def test_fact_dates():
    f = Fact(id="d", type="date", value="12. november 2026", canonical="2026-11-12", span="x")
    assert check.fact_preserved(f, "fristen er 12/11 2026").preserved
    assert check.fact_preserved(f, "fristen er 12.11.2026").preserved
    assert not check.fact_preserved(f, "fristen er 13. november 2026").preserved
    month = Fact(id="m", type="date", value="november 2026", canonical="2026-11", span="x")
    assert check.fact_preserved(month, "i november 2026").preserved
    assert check.fact_preserved(month, "den 3. november 2026").preserved
    assert not check.fact_preserved(month, "i oktober 2026").preserved


def test_fact_names_genitive_and_fuzzy():
    f = Fact(
        id="n", type="org", value="Danmarks Statistik", canonical="danmarks statistik", span="x"
    )
    assert check.fact_preserved(f, "Det viser Danmarks Statistiks tal").preserved
    m = check.fact_preserved(f, "Det viser Danmark Statistik tal")
    assert m.preserved and m.fuzzy
    assert not check.fact_preserved(f, "Det viser Finansministeriets tal").preserved
    place = Fact(
        id="p", type="place", value="Region Nordjylland", canonical="region nordjylland", span="x"
    )
    assert check.fact_preserved(place, "faldet i Region Nordjylland-området").preserved


def test_check_facts_scope(fixture_cfg):
    facts = fixture_cfg.facts["fx-dst-2026-ledighed"]
    t1 = check.check_facts(fixture_cfg.task("t1_telegram"), facts, "")
    assert len(t1) == sum(f.critical for f in facts.facts)
    t5 = check.check_facts(fixture_cfg.task("t5_forkortelse"), facts, "")
    assert len(t5) == len(facts.facts)
    assert check.check_facts(fixture_cfg.task("t2_rubrik"), facts, "") == []


def test_language_leak():
    danish_text = (
        "Ledigheden faldt med tolv hundrede personer i september. "
        "Det viser nye tal fra statistikken."
    )
    assert check.language_leak_tokens(danish_text) == 0
    mixed = (
        danish_text + " The government announced the decision on Thursday morning in Copenhagen."
    )
    assert check.language_leak_tokens(mixed) >= 8


def test_saerskrivning():
    compounds = {"lovforslag", "pressemeddelelse", "finansloven"}
    assert check.saerskrivning_suspects(
        "Regeringen sendte et lov forslag og en presse meddelelse", compounds
    ) == [
        "lov forslag",
        "presse meddelelse",
    ]
    assert check.saerskrivning_suspects("Regeringen sendte et lovforslag", compounds) == []


def test_medianisms(fixture_cfg):
    wl = fixture_cfg.wordlist_yaml("medianisms")
    text = (
        "Det er vigtigt at bemærke, at en række aktører både vinder og taber. "
        "Regeringen vil adressere problemet og navigere i et nyt landskab. "
        "Loven vedtages i december, og pengene bliver udbetalt i januar."
    )
    m = check.medianism_features(text, wl)
    assert m.hedges == 1
    assert m.fillers == 2  # "en række", "både … og"
    assert m.generic_phrases == 2  # "navigere i", "landskab"
    assert m.anglicisms == 1
    assert m.passive_share > 0
    assert m.mean_sentence_len > 10 and m.sentence_len_sd >= 0
