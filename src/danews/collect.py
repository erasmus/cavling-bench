"""Stage `collect`: fetch sources, extract text, lint sources and facts (§6.1)."""

from __future__ import annotations

import asyncio
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
import yaml
from pydantic import BaseModel, ConfigDict
from rich.console import Console

from . import danish
from .config import Config, parse_source_markdown, render_source_markdown
from .schemas import DOMAIN_COUNTS, FactsFile, Source, SourceMeta

console = Console(stderr=True)
USER_AGENT = "cavling-bench/1.0 (+github.com/erasmus/cavling-bench)"
TIMEOUT = 20.0


class SourceEntry(BaseModel):
    """One row of data/sources.yaml (registry, before the text exists)."""

    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    publisher: str
    domain: str
    url: str
    published: date
    licence: str
    licence_url: str | None = None
    notes: str = ""
    planted_ambiguity: bool = False
    skip: bool = False


def load_registry(cfg: Config) -> list[SourceEntry]:
    raw = yaml.safe_load(cfg.paths.sources_yaml.read_text())
    return [SourceEntry.model_validate(r) for r in raw["sources"]]


# Fetching --------------------------------------------------------------------


@dataclass
class Fetcher:
    client: httpx.AsyncClient
    last_hit: dict[str, float] = field(default_factory=dict)
    robots: dict[str, RobotFileParser | None] = field(default_factory=dict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def allowed(self, url: str) -> bool:
        host = urlparse(url).netloc
        if host not in self.robots:
            rp = RobotFileParser()
            try:
                r = await self.client.get(f"https://{host}/robots.txt")
                if r.status_code == 200:
                    rp.parse(r.text.splitlines())
                    self.robots[host] = rp
                else:
                    self.robots[host] = None
            except httpx.HTTPError:
                self.robots[host] = None
        rp = self.robots[host]
        return True if rp is None else rp.can_fetch(USER_AGENT, url)

    async def get(self, url: str) -> httpx.Response:
        host = urlparse(url).netloc
        async with self.lock:
            wait = self.last_hit.get(host, 0) + 1.0 - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self.last_hit[host] = time.monotonic()
        return await self.client.get(url)


def extract_text(html: str, url: str) -> str | None:
    import trafilatura

    text = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
        output_format="txt",
    )
    return text.strip() if text else None


def extract_pdf(content: bytes) -> tuple[str | None, bool]:
    """Return (text, good_quality). Quality = share of alphabetic chars ≥ 60 %."""
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    text = "\n\n".join((p.extract_text() or "") for p in reader.pages).strip()
    if not text:
        return None, False
    alpha = sum(c.isalpha() for c in text) / max(1, sum(not c.isspace() for c in text))
    return text, alpha >= 0.6


def clean_text(text: str) -> str:
    text = text.replace("­", "")  # soft hyphens
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_source(entry: SourceEntry, body: str, needs_manual: bool = False) -> Source:
    body = clean_text(body)
    wc = danish.word_count(body)
    needs_manual = needs_manual or not 300 <= wc <= 1500
    meta = SourceMeta(
        id=entry.id,
        title=entry.title,
        publisher=entry.publisher,
        domain=entry.domain,  # type: ignore[arg-type]
        url=entry.url,
        published=entry.published,
        retrieved=datetime.now(UTC).date(),
        licence=entry.licence,
        word_count=max(300, min(1500, danish.word_count(body)))
        if needs_manual
        else danish.word_count(body),
        planted_ambiguity=entry.planted_ambiguity,
        notes=entry.notes,
        needs_manual=needs_manual,
    )
    return Source(meta=meta, body=body)


async def _collect_one(fetcher: Fetcher, cfg: Config, entry: SourceEntry) -> str:
    path = cfg.paths.sources_dir / f"{entry.id}.md"
    if path.exists():
        return "exists"
    if not await fetcher.allowed(entry.url):
        return "robots-disallowed"
    try:
        resp = await fetcher.get(entry.url)
    except httpx.HTTPError as e:
        return f"error:{type(e).__name__}"
    if resp.status_code != 200:
        return f"http-{resp.status_code}"
    ctype = resp.headers.get("content-type", "")
    if "pdf" in ctype or entry.url.lower().endswith(".pdf"):
        text, good = extract_pdf(resp.content)
        if not text:
            return "pdf-empty"
        src = build_source(entry, text, needs_manual=not good)
    else:
        text = extract_text(resp.text, entry.url)
        if not text:
            return "extract-empty"
        src = build_source(entry, text)
    cfg.paths.sources_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(render_source_markdown(src))
    return "written"


async def _collect(cfg: Config, only: str | None) -> dict[str, str]:
    entries = [e for e in load_registry(cfg) if not e.skip and (not only or only in e.id)]
    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT, "Accept-Language": "da,en;q=0.5"},
        timeout=TIMEOUT,
        follow_redirects=True,
    ) as client:
        fetcher = Fetcher(client)
        results = await asyncio.gather(*[_collect_one(fetcher, cfg, e) for e in entries])
    out = dict(zip([e.id for e in entries], results, strict=True))
    for sid, status in out.items():
        console.print(f"{status:>18}  {sid}")
    return out


def run_collect(cfg: Config, only: str | None = None) -> dict[str, str]:
    return asyncio.run(_collect(cfg, only))


# Lint ------------------------------------------------------------------------------


def lint_sources(cfg: Config, fix_word_count: bool = False) -> list[str]:
    """Return a list of problems (empty = pass). Enforces §5.1 constraints and domain counts."""
    problems: list[str] = []
    domains: Counter[str] = Counter()
    ids: set[str] = set()
    for p in sorted(cfg.paths.sources_dir.glob("*.md")):
        try:
            src = parse_source_markdown(p.read_text())
        except Exception as e:  # noqa: BLE001
            problems.append(f"{p.name}: {e}")
            continue
        if src.meta.needs_manual:
            problems.append(f"{src.id}: needs_manual")
            continue
        if src.id != p.stem:
            problems.append(f"{p.name}: id {src.id!r} != filename")
        if src.id in ids:
            problems.append(f"{src.id}: duplicate id")
        ids.add(src.id)
        actual = danish.word_count(src.body)
        if actual != src.meta.word_count:
            if fix_word_count:
                src.meta.word_count = actual
                p.write_text(render_source_markdown(src))
            else:
                problems.append(f"{src.id}: word_count {src.meta.word_count} != actual {actual}")
        if not 300 <= actual <= 1500:
            problems.append(f"{src.id}: {actual} words outside 300–1500")
        domains[src.meta.domain] += 1
    for dom, want in DOMAIN_COUNTS.items():
        if domains.get(dom, 0) != want:
            problems.append(f"domain {dom}: {domains.get(dom, 0)} sources, want {want}")
    return problems


def lint_facts(cfg: Config) -> list[str]:
    """Each source has a facts file; each span occurs in the body; canonical parses (§5.2)."""
    problems: list[str] = []
    sources = {s.id: s for s in cfg.sources}
    for p in sorted(cfg.paths.facts_dir.glob("*.yaml")):
        try:
            ff = FactsFile.model_validate(yaml.safe_load(p.read_text()))
        except Exception as e:  # noqa: BLE001
            problems.append(f"{p.name}: {e}")
            continue
        src = sources.get(ff.source_id)
        if src is None:
            problems.append(f"{p.name}: unknown source {ff.source_id}")
            continue
        body_norm = re.sub(r"\s+", " ", src.body)
        for f in ff.facts:
            if re.sub(r"\s+", " ", f.span) not in body_norm:
                problems.append(f"{ff.source_id}/{f.id}: span not found in body")
            if f.value not in f.span and f.value not in body_norm:
                problems.append(f"{ff.source_id}/{f.id}: value {f.value!r} not in body")
            if f.type == "number":
                n = danish.normalise_number_string(f.value)
                if n is None:
                    words_val = danish.NUMBER_WORDS.get(f.value.split()[0].lower())
                    if words_val is None:
                        problems.append(f"{ff.source_id}/{f.id}: cannot parse number {f.value!r}")
                    elif not danish.numbers_match(words_val, float(f.canonical)):
                        problems.append(f"{ff.source_id}/{f.id}: {f.value!r} != canonical")
                elif not danish.numbers_match(n.value, float(f.canonical)):
                    problems.append(
                        f"{ff.source_id}/{f.id}: parsed {n.value} != canonical {f.canonical}"
                    )
            elif f.type == "date":
                iso = danish.parse_danish_date(f.value)
                if iso != f.canonical:
                    problems.append(
                        f"{ff.source_id}/{f.id}: parsed {iso} != canonical {f.canonical}"
                    )
    for sid in sources:
        if sid not in cfg.facts:
            problems.append(f"{sid}: no facts file")
    return problems
