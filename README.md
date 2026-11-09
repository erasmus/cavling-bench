# Cavling-bench

**Dansk resumé.** Cavling-bench er et åbent benchmark, der måler, hvilke sprogmodeller der kan betros danske redaktionelle opgaver – på hvilket grundlag og til hvilken afhængighedspris. Seks faste opgaver (telegram, rubrik, faktaboks, versionering, forkortelse, lydmanus) køres over 40 danske offentlige kildetekster på ~13 modeller fra amerikanske frontier-modeller til danske åbne modeller. Output scores på kildetroskab, tonefit, dansk sprogkvalitet og formatoverholdelse med mekaniske tjek, to dommermodeller fra forskellige modelfamilier og en menneskelig stikprøve med rapporteret enighed. Ingen samlet score; alle tal har konfidensintervaller.

Cavling-bench is an open benchmark that answers one question for Danish news publishers: which language models can be trusted with Danish editorial tasks, on what evidence, and at what cost of dependency?

The full specification (`REQUIREMENTS.md`) is kept outside version control; `DECISIONS.md` is the running log of pins, cuts and freezes and records every deviation from it.

## Quick start

```bash
uv sync
uv run pytest            # unit tests on fixtures
make smoke               # whole pipeline on fixtures with the fake provider (< 60 s, no keys)
uv run danews report     # rebuild results/ from committed scores/ — no API keys needed
```

Re-running generation needs keys in `.env` (see `.env.example`):

```bash
uv run danews generate --models anthropic-frontier,nebius-gpt-oss-120b --sources <id1>,<id2>
uv run danews check && uv run danews judge grounding && uv run danews judge tone && uv run danews judge fluency
uv run danews costs      # paid vs credit spend; stop above USD 45
```

## Pipeline

| Stage | Command | Reads | Writes |
| --- | --- | --- | --- |
| collect | `danews collect`, `sources-lint`, `facts-lint` | `data/sources.yaml` | `data/sources/*.md` |
| generate | `danews generate` | tasks, styleguides, sources, `models.yaml` | `outputs/<model>/<task>/<slot>.json` |
| check | `danews check` | outputs, facts, wordlists | `scores/checks.jsonl` |
| judge | `danews judge grounding\|tone\|fluency` | outputs, prompts | `scores/{grounding,tone_pairs,fluency}.jsonl` |
| spotcheck | `danews spotcheck sample` | outputs | `scores/spotcheck_sample.csv` (+ key) |
| agreement | `danews agreement` | scores, `spotcheck_human.csv` | `results/agreement.md` |
| report | `danews report` | scores | `results/*.md`, `results/figures/`, `site_data.json` |
| site | `danews site` | results | `site/` (GitHub Pages) |

Every stage is idempotent and skips work whose output exists (`--force` to redo). All model calls go through `src/danews/llm.py` (LiteLLM, disk cache, cost log).

## Layout

```
data/        sources.yaml, sources/*.md, facts/*.yaml, wordlists/
styleguides/ three invented archetypes (Lynposten, Landsavisen, Erhvervsnyt)
tasks/       t1–t6 prompt YAMLs        prompts/   judge prompts
models.yaml  pinned ids, prices, dependency metadata
src/danews/  pipeline                  tests/     pytest + fixtures (3 sources, fake provider)
outputs/ scores/ results/ site/        committed artefacts
docs/        serving.md (local models), FACTS_GUIDE.md
```

## Licence

Code: MIT (`LICENSE`). Data, outputs, scores and results: CC BY 4.0 (`LICENSE-DATA`). Source texts remain under their publishers' reuse terms, recorded per source.
