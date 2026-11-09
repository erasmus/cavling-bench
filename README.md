# DaNews-Edit

**Dansk resumé.** DaNews-Edit er et åbent benchmark, der måler, hvilke sprogmodeller der kan betros danske redaktionelle opgaver – på hvilket grundlag og til hvilken afhængighedspris. Seks faste opgaver (telegram, rubrik, faktaboks, versionering, forkortelse, lydmanus) køres over 40 danske offentlige kildetekster på ~8 modeller. Output scores på kildetroskab, tonefit, dansk sprogkvalitet og formatoverholdelse med mekaniske tjek, to dommermodeller fra forskellige modelfamilier og en menneskelig stikprøve med rapporteret enighed. Ingen samlet score; alle tal har konfidensintervaller.

DaNews-Edit is an open benchmark that answers one question for Danish news publishers: which language models can be trusted with Danish editorial tasks, on what evidence, and at what cost of dependency?

See `REQUIREMENTS.md` for the full specification and `DECISIONS.md` for the running log of decisions, pins and cuts.

## Quick start

```bash
uv sync
uv run pytest
make smoke          # whole pipeline on fixtures with the fake provider
```

## Licence

Code: MIT (`LICENSE`). Data, outputs, scores and results: CC BY 4.0 (`LICENSE-DATA`).
