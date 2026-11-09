# DECISIONS

Running log of decisions, cuts, freezes, pins and budget check-ins.
Format: `## YYYY-MM-DD HH:MM — <title>` then 1–5 lines.

## 2026-11-09 20:00 — Project start, scaffold per REQUIREMENTS.md §3
Repo scaffolded from REQUIREMENTS.md v1.0. `specs/` is git-ignored (owner's working drafts);
the canonical copy is `REQUIREMENTS.md` at the repo root.
Python pinned to 3.12 via `.python-version`; `lingua-language-detector` chosen over `langdetect`
(spec allows either) because it gives per-language confidence values needed for the > 0.9 rule.
