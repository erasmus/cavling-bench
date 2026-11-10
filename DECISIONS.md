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

## 2026-11-10 00:15 — M1 status
Done: scaffold per §3; 53 unit tests green; `make smoke` runs the full pipeline on fixtures in ~2 s;
50 candidates in `sources.yaml`, 40 pass `sources-lint`; facts for all 40 pass `facts-lint`;
three style guides and six task YAMLs are the spec's exact text; `models.yaml` pinned with prices.
Not done: "two models end-to-end on 5 sources" — no API keys exist on this machine (`.env` absent,
no `*_API_KEY` in the environment). Command once keys are in `.env`:
`uv run danews generate --models anthropic-mid,nebius-gpt-oss-120b --sources <5 ids>` then
`check`, `judge grounding|tone|fluency`, `report`, `costs`.
Freeze: data/ and prompts are *ready to freeze* but not frozen; the owner should spot-read the
facts files (drafted from the texts, not hand-written) and confirm archetype names against the
Danish media registry (§15) before recording the freeze commit here.

## 2026-11-09 22:10 — gpt-oss-120b is a reasoning model; reasoning budget added
First Nebius run: 40 of 45 gpt-oss-120b outputs came back empty with no error, because hidden
reasoning consumed the whole task `max_tokens`. `models.yaml` rows now accept `reasoning_effort`
and `reasoning_budget_tokens`; gpt-oss-120b is pinned at `low` / 1500 extra tokens (observed
completions 114–860 tokens afterwards). An empty completion is now recorded as an error, and judge
stages skip a judge whose key is unset instead of writing error records; error records are retried
on the next run. Qwen3-235B median latency 14 s vs 1.5 s for gpt-oss (both serverless).

## 2026-11-09 22:15 — M1 end-to-end run done (Nebius only)
`generate → check → judge → report → site` ran on 5 sources × 2 models (nebius-gpt-oss-120b,
nebius-qwen3-235b): 90/90 outputs, 90 grounding + 90 fluency records from Judge A, 0 tone pairs
(both generators are judged only by Judge B under the cross-family rule, and no Anthropic key is
set yet). Credit spend USD 0.19, paid USD 0.00. Nebius catalogue checked via `/v1/models`: both
pinned ids are served; DeepSeek-V4-Pro / V4.1-Flash, Kimi-K3 and MiniMax-M3 are also available.
Decision on adding any of them is open (owner).

## 2026-11-09 22:40 — Renamed to Cavling-bench
The benchmark is now called Cavling-bench, matching the GitHub repo `erasmus/cavling-bench`.
All user-facing text, the distribution name, user agent and report were renamed. The Python
package and CLI keep the short name `danews` (code, not user-facing). `REQUIREMENTS.md` is
removed from version control and git-ignored like `specs/`; it stays on disk as the working spec.

## 2026-11-09 23:00 — review fixes: empty completions are billed; params record what was sent
Ultrareview of `feat/nebius-run-and-rename` found that `EmptyCompletion` was raised before
`log_cost`, so the ~40 empty gpt-oss calls of the first run never reached `costs.jsonl` (they are
not recoverable; the USD 45 total is under-counted by roughly those 40 × ~560 completion tokens).
Fixed: the exception now carries the billed usage, `acomplete` logs it (and never caches it), and
`generate` records tokens and cost on the error Output. `Output.params` now records the effective
request (`max_tokens` incl. `reasoning_budget_tokens`, plus `reasoning_effort`); the 45 committed
gpt-oss outputs still say `max_tokens: 560`, which was the task cap, not the 2060 sent. They are
not regenerated (outputs/ is not frozen, but a rerun costs money for no scoring change); the next
`generate --force` corrects them.

## 2026-11-10 00:40 — Anthropic key added; Sonnet 5.5 needs a reasoning budget too
`ANTHROPIC_API_KEY` is now in `.env`. First Sonnet 5.5 call: 7 of 9 outputs empty with
`finish_reason=length`, because Claude 5.5 models always think (adaptive, effort high) and the
thinking counts against `max_tokens`. Both `anthropic-*` rows pinned at `reasoning_effort: low`,
`reasoning_budget_tokens: 3000`; after that 45/45 outputs on 5 sources. Three models × 5 sources
now run end to end with both judges (Judge B 45 grounding, 45 fluency, 8 tone pairs). Spend so
far: paid USD 1.54, Nebius credit USD 0.26.

## 2026-11-10 07:30 — Nebius generators complete on all 40 sources
`nebius-gpt-oss-120b` and `nebius-qwen3-235b`: 720/720 outputs, 0 errors. Mechanical checks and
Judge A grounding + fluency run on everything (Judge A skipped for tone on all pairs between the two
Nebius generators by the cross-family rule, so tone waits for Judge B). Judge B was deliberately
held back on this pass pending the decision to move it from `anthropic-mid` (est. USD 33 paid for
the full 25 % sample) to a DeepSeek-V4 row on Nebius credit. Spend: paid USD 1.54, credit USD 1.47.
Gemini key is on the free tier (5 req/min) and unusable until billing is enabled or OpenRouter is
used; OpenAI and Mistral keys do not exist yet. Owner will use Nebius GPU hours for Munin/DanskGPT.

## 2026-11-10 — Judge B moved to DeepSeek-V4-Pro (Nebius); Anthropic rows complete
Owner approved DeepSeek-V4-Pro on Nebius credit as Judge B (replacing Sonnet 5.5, est. USD 33
paid). New row `nebius-deepseek-v4-pro` with `enabled: false`, which keeps it out of the generator
set but lets `judges.B` resolve it. Called without `reasoning_effort`: DeepSeek-V4 then answers
directly (0 reasoning tokens observed; with `reasoning_effort` it thinks first). Family `deepseek`
is shared by no generator, so every tone cell now has two judges. The 45 + 45 + 8 Sonnet Judge B
records from the 5-source pilot were removed from `scores/` (they remain in git history, commit
336a636) so the files match `models.yaml`.
`JUDGE_MAX_TOKENS["grounding"]` raised 3000 → 6000: DeepSeek lists 25–60 claims per output with
long spans, and 14 of the first 195 grounding calls were truncated mid-JSON. Two t2_rubrik
grounding calls still overflow at 6000 and remain error records (2 of 374); accepted.
Known gap: one gpt-oss-120b t1 output (`ombudsmanden-2026-lolland-avisabonnement-pression`)
degenerated into repeated "i i i"; both fluency judges echo the degeneration and return no JSON,
so it has no fluency score (it still has grounding and checks records).
Generators: `anthropic-mid` 360/360 and `anthropic-frontier` 360/360, 0 errors. Judge A: 1440
grounding, 1439 fluency, 774 tone pairs. Judge B: 372 grounding, 363 fluency, 410 tone pairs.
Spend: paid USD 21.49 (Fable 5.1 came in under the USD 22 estimate), Nebius credit USD 7.98.
Anthropic account held USD 42.89 before this run. Munin/DanskGPT: owner will create an L40S VM
in Nebius AI Cloud (eu-north1) and serve with vLLM per docs/serving.md.
