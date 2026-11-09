# DECISIONS

Running log of decisions, cuts, freezes, pins and budget check-ins.
Format: `## YYYY-MM-DD HH:MM — <title>` then 1–5 lines.

## 2026-11-09 20:00 — Project start, scaffold per REQUIREMENTS.md §3
Repo scaffolded from REQUIREMENTS.md v1.0. `specs/` is git-ignored (owner's working drafts);
the canonical copy is `REQUIREMENTS.md` at the repo root.
Python pinned to 3.12 via `.python-version`; `lingua-language-detector` chosen over `langdetect`
(spec allows either) because it gives per-language confidence values needed for the > 0.9 rule.

## 2026-11-09 21:30 — models.yaml pinned (ids and list prices as of today)
Frontier: claude-fable-5-1 (10/50), gpt-6-astra (10/50), gemini-4-argon (2/10, doubles 2026-12-01).
Mid: claude-sonnet-5-5 (2/10, Judge B), gpt-6-luna (0.10/0.50), gemini-3.8-flash (0.75/3.75).
EU: `mistral-medium` row replaced by `mistral-large` (Mistral Large 4, 0.70/2.10) because Mistral
Medium 3.5 was deprecated 2026-10-31; mistral-small-2603 (0.15/0.60, Apache-2.0).
Nebius: gpt-oss-120b (0.15/0.60, Judge A) and Qwen3-235B-A22B-Instruct-2507 (0.20/0.60); Nebius
removed Llama 3.3 70B on 2026-08-31, so "Llama or Qwen" resolves to Qwen. Nordic: DFM-Mimir-v1.5,
munin-7b-alpha, syvai/danskgpt-v4-12b via a local OpenAI-compatible endpoint.
Anthropic API (2026-10-21) no longer accepts temperature; those rows run with vendor defaults and
`supports_temperature: false` is recorded in each output's params. Anthropic documents no EU
inference geo, so eu_residency = "no". Estimated paid spend at these prices: ~USD 39 (within G4).

## 2026-11-09 22:30 — 50 candidates collected, 40 selected, boilerplate stripped by script
Collected 49/50 (ft.dk returns 403 to non-browser clients; domstol.dk likewise, so courts are
police/prosecution releases). Boilerplate (press-contact blocks, phone numbers, "Øvrige nyheder"/
"Pressemeddelelse" headers, newsletter and related-link lists) removed by `scripts/clean_sources.py`,
not by hand, so the step is reproducible. 10 spares marked `skip: true` in `data/sources.yaml`
with the reason inline. Reuse terms: explicit for dst.dk and nationalbanken.dk; all other
authorities carry the ophavsretslov § 9 public-document reading — to confirm with press offices
before the repo goes public.

## 2026-11-09 23:30 — Facts written for 40 sources; 8 texts flagged planted_ambiguity
Facts (6–10 per source, ≥ 3 critical) drafted from the texts with verbatim spans and validated by
`facts-lint`; the owner should spot-read them before freezing. No source text was altered to plant
a trap; `planted_ambiguity: true` marks the 8 texts whose *natural* confusable figures or revised
numbers serve that purpose (described in each file's `notes`). Linter limits noted by curators:
bare-year dates and compound durations ("et år og seks måneder") are not parsed, so such facts
were recorded as `quote` or omitted.
