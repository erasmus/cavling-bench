from danews.danish import (
    extract_dates,
    extract_numbers,
    normalise_number_string,
    numbers_match,
    parse_danish_date,
    parse_danish_number,
    sentences,
    word_count,
)


def test_parse_thousand_sep_and_decimal_comma():
    assert parse_danish_number("1.234,5") == 1234.5
    assert parse_danish_number("1.234") == 1234.0
    assert parse_danish_number("12,5") == 12.5
    assert parse_danish_number("2026") == 2026.0
    assert parse_danish_number("abc") is None


def test_scale_words_and_currency():
    n = normalise_number_string("1,2 mia. kr.")
    assert n is not None
    assert n.value == 1.2e9
    assert n.unit == "DKK"
    n2 = normalise_number_string("350 mio. kroner")
    assert n2.value == 350e6 and n2.unit == "DKK"


def test_percent_variants():
    for s in ("12 pct.", "12 %", "12%", "12 procent"):
        n = normalise_number_string(s)
        assert n.value == 12 and n.unit == "%", s
    pp = normalise_number_string("2,5 procentpoint")
    assert pp.value == 2.5 and pp.unit == "pp"


def test_extract_numbers_from_sentence():
    nums = extract_numbers("Ledigheden faldt med 1.200 personer til 2,8 pct. i oktober 2026.")
    values = [(n.value, n.unit) for n in nums]
    assert (1200.0, None) in values
    assert (2.8, "%") in values
    assert (2026.0, None) in values


def test_numbers_match_tolerance():
    assert numbers_match(1000, 1004)
    assert not numbers_match(1000, 1010)
    assert numbers_match(0, 0)


def test_dates():
    assert parse_danish_date("12. november 2026") == "2026-11-12"
    assert parse_danish_date("12/11 2026") == "2026-11-12"
    assert parse_danish_date("12.11.2026") == "2026-11-12"
    assert parse_danish_date("november 2026") == "2026-11"
    assert parse_danish_date("nov. 2026") == "2026-11"
    assert parse_danish_date("1. januar 2025") == "2025-01-01"
    assert parse_danish_date("2026-09-14") == "2026-09-14"


def test_extract_dates_year_fallback_and_no_double_count():
    ds = extract_dates("Loven træder i kraft den 1. juli 2026, og evalueres i 2028.")
    assert ds == ["2026-07-01", "2028"]


def test_word_count_strips_markdown():
    assert word_count("**Fed** tekst - med *kursiv*") == 4
    assert word_count("- punkt et\n- punkt to") == 4


def test_sentences_split_danish():
    s = sentences("Det er sket. Ministeren siger nej! Hvad nu? Ca. 12 pct. er med.")
    assert s[0] == "Det er sket."
    assert s[1] == "Ministeren siger nej!"
    assert s[2] == "Hvad nu?"
    assert len(s) == 4
