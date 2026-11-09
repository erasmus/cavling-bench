"""Danish number/date normalisation and tokenisation helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass

MONTHS = {
    "januar": 1, "jan": 1,
    "februar": 2, "feb": 2,
    "marts": 3, "mar": 3,
    "april": 4, "apr": 4,
    "maj": 5,
    "juni": 6, "jun": 6,
    "juli": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "okt": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}  # fmt: skip

SCALE_WORDS = {
    "mia": 1e9, "milliard": 1e9, "milliarder": 1e9,
    "mio": 1e6, "million": 1e6, "millioner": 1e6,
    "mrd": 1e9,
    "tusind": 1e3, "tusinde": 1e3,
}  # fmt: skip

NUMBER_WORDS = {
    "nul": 0, "en": 1, "et": 1, "én": 1, "ét": 1, "to": 2, "tre": 3, "fire": 4, "fem": 5,
    "seks": 6, "syv": 7, "otte": 8, "ni": 9, "ti": 10, "elleve": 11, "tolv": 12, "tretten": 13,
    "fjorten": 14, "femten": 15, "seksten": 16, "sytten": 17, "atten": 18, "nitten": 19,
    "tyve": 20, "tredive": 30, "fyrre": 40, "halvtreds": 50, "tres": 60, "halvfjerds": 70,
    "firs": 80, "halvfems": 90, "hundrede": 100, "hundred": 100,
}  # fmt: skip

PERCENT_UNITS = ("pct", "procent", "%")
PERCENT_POINT_UNITS = ("procentpoint", "pp")
CURRENCY_UNITS = {
    "kr": "DKK",
    "kroner": "DKK",
    "dkk": "DKK",
    "euro": "EUR",
    "eur": "EUR",
    "dollar": "USD",
    "usd": "USD",
}

_NUM_TOKEN = r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?|\d+(?:\.\d+)?"
_UNIT = r"(?:mia|mio|mrd|milliarder?|millioner?|tusinde?)"
NUMBER_RE = re.compile(
    rf"(?P<num>{_NUM_TOKEN})"
    rf"(?:\s*(?P<scale>{_UNIT})\.?)?"
    rf"(?:\s*(?P<unit>procentpoint|pct\.?|procent|%|kroner|kr\.?|euro|dollar|dkk|eur|usd))?",
    re.IGNORECASE,
)

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+(?=[\"'«»]?[A-ZÆØÅ0-9])")
MARKDOWN_RE = re.compile(r"[*_`#>]+|^\s*[-•]\s+|\[(.*?)\]\(.*?\)", re.MULTILINE)
WORD_RE = re.compile(r"[A-Za-zÆØÅæøåÉéÜüÖö0-9][A-Za-zÆØÅæøåÉéÜüÖö0-9'’\-\.,]*")
YEAR_RE = re.compile(r"\b(1[89]|20)\d{2}\b")


@dataclass(frozen=True)
class Number:
    value: float
    unit: str | None  # "%", "pp", "DKK", ... or None
    raw: str


def parse_danish_number(s: str) -> float | None:
    """`1.234,5` → 1234.5; `1,2` → 1.2; `1200` → 1200. Returns None if not a number."""
    s = s.strip()
    if not re.fullmatch(_NUM_TOKEN, s):
        return None
    if "," in s:
        return float(s.replace(".", "").replace(",", "."))
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s):
        return float(s.replace(".", ""))
    return float(s)


def _norm_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    u = unit.lower().rstrip(".")
    if u in PERCENT_POINT_UNITS:
        return "pp"
    if u in PERCENT_UNITS:
        return "%"
    return CURRENCY_UNITS.get(u)


def extract_numbers(text: str) -> list[Number]:
    """Find every number in Danish text, applying scale words and detecting units."""
    out: list[Number] = []
    for m in NUMBER_RE.finditer(text):
        base = parse_danish_number(m.group("num"))
        if base is None:
            continue
        scale = m.group("scale")
        if scale:
            base *= SCALE_WORDS[scale.lower().rstrip(".")]
        out.append(Number(value=base, unit=_norm_unit(m.group("unit")), raw=m.group(0)))
    return out


def normalise_number_string(s: str) -> Number | None:
    """Normalise a single fact value like `1,2 mia. kr.` or `12 pct.`."""
    nums = extract_numbers(s)
    return nums[0] if nums else None


def numbers_match(a: float, b: float, tol: float = 0.005) -> bool:
    return abs(a - b) / max(abs(a), abs(b), 1.0) <= tol


# Dates ----------------------------------------------------------------------

_MONTH_NAMES = "|".join(sorted(MONTHS, key=len, reverse=True))
DATE_RES = [
    # 12. november 2026 / 12 november 2026 / 12. nov. 2026
    re.compile(rf"\b(?P<d>\d{{1,2}})\.?\s+(?P<mn>{_MONTH_NAMES})\.?\s+(?P<y>\d{{4}})\b", re.I),
    # 12/11 2026, 12/11-2026, 12/11/2026
    re.compile(r"\b(?P<d>\d{1,2})/(?P<m>\d{1,2})[ /\-](?P<y>\d{4})\b"),
    # 12.11.2026
    re.compile(r"\b(?P<d>\d{1,2})\.(?P<m>\d{1,2})\.(?P<y>\d{4})\b"),
    # 2026-11-12
    re.compile(r"\b(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})\b"),
    # november 2026 / nov. 2026
    re.compile(rf"\b(?P<mn>{_MONTH_NAMES})\.?\s+(?P<y>\d{{4}})\b", re.I),
]


def _iso(y: str, m: str | int | None, d: str | None) -> str | None:
    year = int(y)
    if m is None:
        return f"{year:04d}"
    month = int(m)
    if not 1 <= month <= 12:
        return None
    if d is None:
        return f"{year:04d}-{month:02d}"
    day = int(d)
    if not 1 <= day <= 31:
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def extract_dates(text: str) -> list[str]:
    """Return ISO strings (YYYY, YYYY-MM or YYYY-MM-DD) for every date found in text."""
    found: list[tuple[int, str]] = []
    covered: list[tuple[int, int]] = []
    for rx in DATE_RES:
        for m in rx.finditer(text):
            if any(s <= m.start() < e for s, e in covered):
                continue
            gd = m.groupdict()
            month: str | int | None = gd.get("m")
            if gd.get("mn"):
                month = MONTHS[gd["mn"].lower()]
            iso = _iso(gd["y"], month, gd.get("d"))
            if iso:
                found.append((m.start(), iso))
                covered.append((m.start(), m.end()))
    for m in YEAR_RE.finditer(text):
        if not any(s <= m.start() < e for s, e in covered):
            found.append((m.start(), m.group(0)))
    return [iso for _, iso in sorted(found)]


def parse_danish_date(s: str) -> str | None:
    ds = extract_dates(s)
    return ds[0] if ds else None


def dates_match(fact_iso: str, candidate_iso: str) -> bool:
    """Match at the precision of the fact: `2026-11` matches `2026-11-12`."""
    return candidate_iso.startswith(fact_iso)


# Text helpers ----------------------------------------------------------------


def strip_markdown(text: str) -> str:
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
    text = re.sub(r"^\s*(#+|[-*•]|\d+[.)])\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_`>]+", "", text)
    return text


_ABBREV = (
    "bl.a.",
    "ca.",
    "f.eks.",
    "dvs.",
    "pct.",
    "mio.",
    "mia.",
    "kr.",
    "nr.",
    "jf.",
    "osv.",
    "mv.",
    "m.fl.",
    "evt.",
    "hhv.",
    "inkl.",
    "ekskl.",
    "ekskl.",
    "stk.",
    "tlf.",
    "sek.",
    "min.",
)
_ABBREV_RE = re.compile(
    "|".join(re.escape(a) for a in sorted(_ABBREV, key=len, reverse=True)), re.I
)
_HAS_ALNUM = re.compile(r"[A-Za-zÆØÅæøå0-9]")


def words(text: str) -> list[str]:
    """Whitespace tokens that contain at least one letter or digit (a lone dash is not a word)."""
    return [w for w in strip_markdown(text).split() if _HAS_ALNUM.search(w)]


def word_count(text: str) -> int:
    return len(words(text))


def sentences(text: str) -> list[str]:
    text = strip_markdown(text).replace("\n", " ").strip()
    if not text:
        return []
    protected = _ABBREV_RE.sub(lambda m: m.group(0).replace(".", "\u2024"), text)
    parts = SENTENCE_SPLIT_RE.split(protected)
    return [p.replace("\u2024", ".").strip() for p in parts if p.strip()]


def tokens(text: str) -> list[str]:
    """Lowercase word tokens with surrounding punctuation stripped."""
    return [
        t.strip(".,;:!?\"'«»()[]").lower()
        for t in strip_markdown(text).split()
        if t.strip(".,;:!?\"'«»()[]")
    ]
