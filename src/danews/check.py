"""Mechanical checks, no LLM (REQUIREMENTS.md §6.3)."""

from __future__ import annotations

import json
import re
import statistics
from dataclasses import dataclass
from functools import lru_cache

from rapidfuzz import fuzz

from . import danish
from .config import Config
from .schemas import CheckRecord, Fact, FactsFile, Medianism, Output, Task

HEADLINE_RE = re.compile(r"^RUBRIK:\s*(.+?)\s*$", re.M)
SUBHEADLINE_RE = re.compile(r"^UNDERRUBRIK:\s*(.+?)\s*$", re.M)
BULLET_RE = re.compile(r"^\s*[-•*]\s+\S", re.M)
YEAR_ALLOWED_RE = re.compile(r"\b(1[89]|20)\d{2}\b")
DIGIT_RE = re.compile(r"\d+")

ENGLISH_ALLOWLIST = {
    "brexit", "ceo", "cfo", "it", "ai", "eu", "nato", "fbi", "usa", "uk", "ok", "online",
    "podcast", "smartphone", "software", "hardware", "app", "apps", "website", "streaming",
}  # fmt: skip

DANISH_STOPWORDS = {
    "og", "i", "at", "det", "en", "et", "den", "til", "er", "som", "på", "de", "med", "han",
    "af", "for", "ikke", "der", "var", "mig", "sig", "men", "ét", "har", "om", "vi", "min",
    "havde", "ham", "hun", "nu", "over", "da", "fra", "du", "ud", "sin", "dem", "os", "op",
    "man", "hans", "hvor", "eller", "hvad", "skal", "selv", "her", "alle", "vil", "blev",
    "kunne", "ind", "når", "være", "dog", "noget", "ville", "jo", "deres", "efter", "ned",
    "skulle", "denne", "end", "dette", "mit", "også", "under", "have", "dig", "anden", "hende",
    "mine", "alt", "meget", "sit", "sine", "vor", "mod", "disse", "hvis", "din", "nogle", "hos",
    "blive", "mange", "ad", "bliver", "hendes", "været", "thi", "jer", "så", "kan",
}  # fmt: skip

FINITE_VERB_HINT_RE = re.compile(r"\b[a-zæøå]{2,}(?:er|ede|te|r)\b")
BLIVE_PASSIVE_RE = re.compile(r"\b(?:bliver|blev|blive|blevet)\s+\w+(?:et|t|ede|te|ne|ede)\b")


# Format ----------------------------------------------------------------------


def check_format(task: Task, text: str, abbreviations: set[str]) -> list[str]:
    """Return a list of failure reasons; empty list means pass."""
    reasons: list[str] = []
    if not text.strip():
        return ["empty_output"]
    lim = task.limits
    if task.output_kind == "headline_pair":
        heads = HEADLINE_RE.findall(text)
        subs = SUBHEADLINE_RE.findall(text)
        if len(heads) != 1:
            reasons.append(f"headline_count={len(heads)}")
        elif lim.max_headline_chars and len(heads[0]) > lim.max_headline_chars:
            reasons.append(f"headline_chars={len(heads[0])}>{lim.max_headline_chars}")
        if len(subs) != 1:
            reasons.append(f"subheadline_count={len(subs)}")
        elif lim.max_subheadline_chars and len(subs[0]) > lim.max_subheadline_chars:
            reasons.append(f"subheadline_chars={len(subs[0])}>{lim.max_subheadline_chars}")
        extra = [
            ln
            for ln in text.strip().splitlines()
            if ln.strip() and not re.match(r"^(RUBRIK|UNDERRUBRIK):", ln)
        ]
        if extra:
            reasons.append("extra_lines")
        return reasons
    if task.output_kind == "bullets":
        bullets = BULLET_RE.findall(text)
        if lim.bullets is not None and len(bullets) != lim.bullets:
            reasons.append(f"bullet_count={len(bullets)}!={lim.bullets}")
        if lim.max_words_per_bullet:
            for i, line in enumerate(ln for ln in text.splitlines() if BULLET_RE.match(ln)):
                n = danish.word_count(line)
                if n > lim.max_words_per_bullet:
                    reasons.append(f"bullet_{i + 1}_words={n}>{lim.max_words_per_bullet}")
        return reasons
    n = danish.word_count(text)
    if lim.min_words is not None and n < lim.min_words:
        reasons.append(f"words={n}<{lim.min_words}")
    if lim.max_words is not None and n > lim.max_words:
        reasons.append(f"words={n}>{lim.max_words}")
    if task.output_kind == "script":
        stray = [
            m.group(0) for m in DIGIT_RE.finditer(text) if not YEAR_ALLOWED_RE.fullmatch(m.group(0))
        ]
        if stray:
            reasons.append(f"digits={','.join(stray[:5])}")
        low = text.lower()
        found = sorted(
            a for a in abbreviations if re.search(rf"(?<![\w.]){re.escape(a)}(?!\w)", low)
        )
        if found:
            reasons.append(f"abbreviations={','.join(found)}")
    return reasons


# Fact preservation -------------------------------------------------------------


@dataclass
class FactMatch:
    fact_id: str
    preserved: bool
    fuzzy: bool = False


def _norm_name(s: str) -> str:
    return re.sub(r"[^\wæøå\- ]", "", s.lower()).strip()


def _name_in_text(canonical: str, text: str) -> tuple[bool, bool]:
    """Exact token match allowing genitive -s and hyphen-compounding; fuzzy ≥ 92 fallback."""
    cand = _norm_name(canonical)
    low = _norm_name(text)
    pattern = re.escape(cand) + r"(?:s|'s|’s)?(?:-\w+)?(?![\wæøå])"
    if re.search(r"(?<![\wæøå])" + pattern, low):
        return True, False
    # fuzzy: slide a window of the same token length over the text
    toks = low.split()
    k = len(cand.split())
    best = 0.0
    for i in range(0, max(1, len(toks) - k + 1)):
        window = " ".join(toks[i : i + k])
        best = max(best, fuzz.ratio(cand, window))
        if best >= 92:
            return True, True
    return False, False


def fact_preserved(fact: Fact, text: str) -> FactMatch:
    if fact.type == "number":
        target = float(fact.canonical)
        unit = fact.unit
        if unit:
            unit = danish._norm_unit(unit) or unit
        for num in danish.extract_numbers(text):
            if danish.numbers_match(num.value, target) and (
                unit is None or num.unit is None or num.unit == unit
            ):
                return FactMatch(fact.id, True)
        # spelled-out numbers (T6 writes digits as words)
        for w in danish.tokens(text):
            if w in danish.NUMBER_WORDS and danish.numbers_match(danish.NUMBER_WORDS[w], target):
                return FactMatch(fact.id, True)
        return FactMatch(fact.id, False)
    if fact.type == "date":
        for iso in danish.extract_dates(text):
            if danish.dates_match(str(fact.canonical), iso):
                return FactMatch(fact.id, True)
        return FactMatch(fact.id, False)
    ok, fuzzy = _name_in_text(str(fact.canonical), text)
    return FactMatch(fact.id, ok, fuzzy)


def check_facts(task: Task, facts: FactsFile | None, text: str) -> list[FactMatch]:
    """T1/T3: critical facts only; T5: all facts; other tasks: none."""
    if facts is None:
        return []
    if task.id.startswith("t5"):
        pool = facts.facts
    elif task.id.startswith(("t1", "t3")):
        pool = [f for f in facts.facts if f.critical]
    else:
        return []
    return [fact_preserved(f, text) for f in pool]


# Language leakage -----------------------------------------------------------------


@lru_cache(maxsize=1)
def _detector():
    from lingua import Language, LanguageDetectorBuilder

    return LanguageDetectorBuilder.from_languages(
        Language.DANISH, Language.ENGLISH, Language.GERMAN, Language.SWEDISH, Language.BOKMAL
    ).build()


def language_leak_tokens(text: str, allowlist: set[str] = ENGLISH_ALLOWLIST) -> int:
    """Count words in sentences detected as non-Danish with confidence > 0.9."""
    from lingua import Language

    det = _detector()
    leaked = 0
    for sent in danish.sentences(text):
        toks = [t for t in danish.tokens(sent) if t not in allowlist]
        if len(toks) < 3:
            continue
        probe = " ".join(toks)
        values = det.compute_language_confidence_values(probe)
        if not values:
            continue
        top = values[0]
        if top.language != Language.DANISH and top.value > 0.9:
            leaked += len(toks)
    return leaked


# Særskrivning -----------------------------------------------------------------------


def saerskrivning_suspects(
    text: str, compounds: set[str], stopwords: set[str] = DANISH_STOPWORDS
) -> list[str]:
    toks = danish.tokens(text)
    out: list[str] = []
    for w1, w2 in zip(toks, toks[1:], strict=False):
        if not w1.isalpha() or not w2.isalpha():
            continue
        if w1 in stopwords or w2 in stopwords:
            continue
        if w1 + w2 in compounds or w1 + "s" + w2 in compounds:
            out.append(f"{w1} {w2}")
    return out


# Median-isms ------------------------------------------------------------------------


def _count_phrases(low: str, phrases: list[str]) -> int:
    n = 0
    for p in phrases:
        p = p.lower()
        if "…" in p:
            a, b = (x.strip() for x in p.split("…", 1))
            n += len(re.findall(rf"\b{re.escape(a)}\b[^.!?]{{0,60}}?\b{re.escape(b)}\b", low))
        else:
            n += len(re.findall(rf"(?<![\wæøå]){re.escape(p)}(?![\wæøå])", low))
    return n


def medianism_features(text: str, wordlist: dict[str, list[str]]) -> Medianism:
    low = danish.strip_markdown(text).lower()
    sents = danish.sentences(text)
    lens = [danish.word_count(s) for s in sents] or [0]
    n_finite = len(FINITE_VERB_HINT_RE.findall(low)) or 1
    n_passive = _passive_count(low)
    return Medianism(
        hedges=_count_phrases(low, wordlist.get("hedges", [])),
        fillers=_count_phrases(low, wordlist.get("fillers", [])),
        generic_phrases=_count_phrases(low, wordlist.get("generic_phrases", [])),
        anglicisms=_count_phrases(low, wordlist.get("anglicisms", [])),
        passive_share=round(min(1.0, n_passive / n_finite), 4),
        mean_sentence_len=round(statistics.fmean(lens), 2),
        sentence_len_sd=round(statistics.pstdev(lens), 2) if len(lens) > 1 else 0.0,
    )


_S_PASSIVE_EXCLUDE = {"des", "les", "hes", "mes", "res", "tes", "ses"}


def _passive_count(low: str) -> int:
    """Heuristic: -es passives (`vedtages`, `findes`) plus blive/blev + participle."""
    s_pass = [w for w in re.findall(r"\b[a-zæøå]{4,}es\b", low) if w not in _S_PASSIVE_EXCLUDE]
    blive = BLIVE_PASSIVE_RE.findall(low)
    return len(s_pass) + len(blive)


# Orchestration ------------------------------------------------------------------------


def check_output(cfg: Config, out: Output) -> CheckRecord:
    task = cfg.task(out.task_id)
    abbreviations = cfg.wordlist_txt("abbreviations")
    compounds = cfg.wordlist_txt("da_compounds")
    medianisms = cfg.wordlist_yaml("medianisms")
    text = out.text or ""
    reasons = check_format(task, text, abbreviations) if not out.error else [f"error:{out.error}"]
    matches = check_facts(task, cfg.facts.get(out.source_id), text)
    return CheckRecord(
        output_ref=out.ref,
        format_pass=not reasons,
        format_fail_reasons=reasons,
        facts_total=len(matches),
        facts_preserved=sum(m.preserved for m in matches),
        facts_missing=[m.fact_id for m in matches if not m.preserved],
        facts_fuzzy=[m.fact_id for m in matches if m.fuzzy],
        lang_leak_tokens=language_leak_tokens(text) if text else 0,
        saerskrivning_suspects=saerskrivning_suspects(text, compounds),
        medianism=medianism_features(text, medianisms),
    )


def load_outputs(cfg: Config) -> list[Output]:
    outs = []
    for p in sorted(cfg.paths.outputs.rglob("*.json")):
        outs.append(Output.model_validate_json(p.read_text()))
    return outs


def run_check(cfg: Config, only: str | None = None, force: bool = False) -> int:
    """Write scores/checks.jsonl with one line per output. Returns number of records."""
    cfg.paths.scores.mkdir(parents=True, exist_ok=True)
    target = cfg.paths.scores / "checks.jsonl"
    existing: dict[str, str] = {}
    if target.exists() and not force:
        for line in target.read_text().splitlines():
            if line.strip():
                existing[json.loads(line)["output_ref"]] = line
    records: dict[str, str] = dict(existing)
    for out in load_outputs(cfg):
        if only and only not in out.ref:
            continue
        if out.ref in existing:
            continue
        records[out.ref] = check_output(cfg, out).model_dump_json()
    target.write_text("\n".join(records[k] for k in sorted(records)) + ("\n" if records else ""))
    return len(records)
