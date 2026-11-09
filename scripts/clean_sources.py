"""Strip publisher boilerplate from fetched sources (run once after `danews collect`).

Rules are deliberately conservative and per-pattern; everything removed is navigation,
press-contact or link-list material, never story text. Recorded in DECISIONS.md.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from danews.config import parse_source_markdown, render_source_markdown
from danews.danish import word_count

LEADING_JUNK = {"nyhed", "pressemeddelelse", "øvrige nyheder", ""}
DATE_ONLY = re.compile(r"^\d{1,2}\.? ?(\w+ \d{4}|\d{2}\.\d{4})$")
# A line matching CUT_FROM ends the story; everything after it is contact/link material.
CUT_FROM = re.compile(
    r"^(Pressekontakt:?|Pressemeddelelser fra Konkurrence.*|Fakta om byggeriet|"
    r"Statistikdokumentation|Kilder og metode|Kontakt)$",
    re.I,
)
# A line matching DROP_LINE is removed on its own.
DROP_LINE = re.compile(
    r"(tlf\.? ?\d|telefon:? ?\d|mobil:? ?\d|pressetelefon|^https?://\S+$|^Kilde: |"
    r"^Næste udgivelse:|^\d{1,2}\. \w+ \d{4} - Nr\. \d+$|^E-mail:|📞|"
    r"^Yderligere oplysninger:?$|^Læs hele udtalelsen\.$|^Du kan læse |^Læs mere |"
    r"^Læs den samlede|^For journalister:|^Henvendelse kan rettes|^Pressen kan henvende|"
    r"^Kontakt vagtchefen)",
    re.I,
)


def clean(body: str) -> str:
    lines = [ln.rstrip() for ln in body.splitlines()]
    while lines and (lines[0].strip().lower() in LEADING_JUNK or DATE_ONLY.match(lines[0].strip())):
        lines.pop(0)
    out: list[str] = []
    for ln in lines:
        if CUT_FROM.match(ln.strip()):
            break
        if DROP_LINE.search(ln):
            continue
        out.append(ln)
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def main(paths: list[str]) -> None:
    for p in paths:
        path = Path(p)
        src = parse_source_markdown(path.read_text())
        before = word_count(src.body)
        src.body = clean(src.body)
        after = word_count(src.body)
        src.meta.word_count = max(300, min(1500, after))
        src.meta.needs_manual = not 300 <= after <= 1500
        path.write_text(render_source_markdown(src))
        flag = " MANUAL" if src.meta.needs_manual else ""
        print(f"{before:5} -> {after:5}{flag}  {src.id}")


if __name__ == "__main__":
    main(sys.argv[1:] or [str(p) for p in sorted(Path("data/sources").glob("*.md"))])
