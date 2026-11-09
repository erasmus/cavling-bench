# Cavling-bench – resultater

*Målt 2026-11-09. Ingen samlet score: hver tabel rangerer pr. opgave og pr. dimension. Alle tal har 95 % bootstrap-intervaller over kildetekster.*

Cavling-bench målte 2 sprogmodeller på 6 redaktionelle opgaver over 40 danske offentlige kildetekster (90 output, kørt 2026-11-09). På versioneringsopgaven lå andelen af understøttede påstande mellem 89 % (Qwen3-235B-A22B (Nebius)) og 93 % (gpt-oss-120b (Nebius)); intervallerne overlapper for de fleste modeller. Prisen for 1.000 telegrammer spændte fra USD 0.36 (gpt-oss-120b (Nebius)) til USD 0.47 (Qwen3-235B-A22B (Nebius)).

## Afhængighed

| Model | Niveau | USD pr. 1.000 T1 | Latens median/p95 ms | Åbne vægte | Licens | EU-residens | Params (mia.) | Version | Dato |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Fable 5.1 | Frontier (proprietær) | – | – | nej | proprietary | no | – | `claude-fable-5-1` | 2026-11-09 |
| Claude Sonnet 5.5 | Mellemklasse (proprietær) | – | – | nej | proprietary | no | – | `claude-sonnet-5-5` | 2026-11-09 |
| GPT-6 Astra | Frontier (proprietær) | – | – | nej | proprietary | cloud region | – | `gpt-6-astra` | 2026-11-09 |
| GPT-6 Luna | Mellemklasse (proprietær) | – | – | nej | proprietary | cloud region | – | `gpt-6-luna` | 2026-11-09 |
| Gemini 4 Argon | Frontier (proprietær) | – | – | nej | proprietary | no | – | `gemini-4-argon` | 2026-11-09 |
| Gemini 3.8 Flash | Mellemklasse (proprietær) | – | – | nej | proprietary | no | – | `gemini-3.8-flash` | 2026-11-09 |
| Mistral Large 4 | Europæisk | – | – | ja | Mistral Ecosystem Open Weight License | yes | 1050.0 | `mistral-large-4-0` | 2026-11-09 |
| Mistral Small 4 | Europæisk | – | – | ja | Apache-2.0 | yes | 119.0 | `mistral-small-2603` | 2026-11-09 |
| gpt-oss-120b (Nebius) | Åbne vægte (global) | 0.36 | 1456/1877 | ja | Apache-2.0 | cloud region | 120.0 | `openai/gpt-oss-120b` | 2026-11-09 |
| Qwen3-235B-A22B (Nebius) | Åbne vægte (global) | 0.47 | 13973/17698 | ja | Apache-2.0 | cloud region | 235.0 | `Qwen/Qwen3-235B-A22B-Instruct-2507` | 2026-11-09 |
| DFM Mimir v1.5 (1.8B) | Dansk/nordisk åben | selvhostet* | – | ja | Apache-2.0 | self-hosted | 1.8 | `danish-foundation-models/DFM-Mimir-v1.5` | 2026-11-09 |
| DFM Munin 7B alpha | Dansk/nordisk åben | selvhostet* | – | ja | Apache-2.0 | self-hosted | 7.0 | `danish-foundation-models/munin-7b-alpha` | 2026-11-09 |
| DanskGPT v4 12B | Dansk/nordisk åben | selvhostet* | – | ja | CC-BY-4.0 (Gemma terms apply) | self-hosted | 12.0 | `syvai/danskgpt-v4-12b` | 2026-11-09 |

\* Selvhostede modeller: GPU-time ÷ gennemløb, se `docs/serving.md`.

## Resultater pr. opgave

### Nyhedstelegram (t1_telegram)

| Model | Niveau | n | Understøttede påstande % [CI] | Modsigelser (sum) | Fakta bevaret % | Sprogkvalitet 1–5 [CI] * | Format OK % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-oss-120b (Nebius) | Åbne vægte (global) | 5 | 98.2 [94.5; 100.0] | 0 | 91 | 4.80 [4.40; 5.00] | 80 |
| Qwen3-235B-A22B (Nebius) | Åbne vægte (global) | 5 | 90.9 [87.4; 95.8] | 1 | 96 | 4.40 [4.00; 4.80] | 80 |

\* **Vejledende**: enigheden med menneskelige bedømmere lå under tærsklen (se Enighed).

### Rubrik og underrubrik (t2_rubrik)

| Model | Niveau | n | Understøttede påstande % [CI] | Modsigelser (sum) | Sprogkvalitet 1–5 [CI] * | Tone BT lynposten [CI] * | Tone BT landsavisen [CI] * | Tone BT erhvervsnyt [CI] * | Format OK % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-oss-120b (Nebius) | Åbne vægte (global) | 15 | 95.0 [91.1; 98.9] | 2 | 4.93 [4.80; 5.00] | – † | – † | – † | 53 |
| Qwen3-235B-A22B (Nebius) | Åbne vægte (global) | 15 | 86.0 [74.6; 95.9] | 0 | 4.40 [3.67; 4.93] | – | – | – | 67 |

\* **Vejledende**: enigheden med menneskelige bedømmere lå under tærsklen (se Enighed).
† Tone bedømt af én dommer (krydsfamilie-reglen).

### Faktaboks (t3_faktaboks)

| Model | Niveau | n | Understøttede påstande % [CI] | Modsigelser (sum) | Fakta bevaret % | Sprogkvalitet 1–5 [CI] * | Format OK % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-oss-120b (Nebius) | Åbne vægte (global) | 5 | 96.0 [88.0; 100.0] | 0 | 70 | 4.40 [3.60; 5.00] | 100 |
| Qwen3-235B-A22B (Nebius) | Åbne vægte (global) | 5 | 96.0 [88.0; 100.0] | 0 | 78 | 4.40 [3.60; 5.00] | 80 |

\* **Vejledende**: enigheden med menneskelige bedømmere lå under tærsklen (se Enighed).

### Versionering (t4_versionering)

| Model | Niveau | n | Understøttede påstande % [CI] | Modsigelser (sum) | Sprogkvalitet 1–5 [CI] * | Tone BT lynposten [CI] * | Tone BT landsavisen [CI] * | Format OK % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-oss-120b (Nebius) | Åbne vægte (global) | 10 | 92.9 [88.5; 97.3] | 2 | 4.00 [4.00; 4.00] | – † | – † | 40 |
| Qwen3-235B-A22B (Nebius) | Åbne vægte (global) | 10 | 89.0 [83.1; 93.5] | 0 | 4.30 [4.10; 4.50] | – | – | 60 |

\* **Vejledende**: enigheden med menneskelige bedømmere lå under tærsklen (se Enighed).
† Tone bedømt af én dommer (krydsfamilie-reglen).

### Forkortelse (t5_forkortelse)

| Model | Niveau | n | Understøttede påstande % [CI] | Modsigelser (sum) | Fakta bevaret % | Sprogkvalitet 1–5 [CI] * | Format OK % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-oss-120b (Nebius) | Åbne vægte (global) | 5 | 98.3 [95.0; 100.0] | 0 | 88 | 4.00 [4.00; 4.00] | 40 |
| Qwen3-235B-A22B (Nebius) | Åbne vægte (global) | 5 | 97.3 [92.0; 100.0] | 1 | 92 | 3.40 [2.40; 4.40] | 60 |

\* **Vejledende**: enigheden med menneskelige bedømmere lå under tærsklen (se Enighed).

### Lydmanus (t6_lydmanus)

| Model | Niveau | n | Understøttede påstande % [CI] | Modsigelser (sum) | Sprogkvalitet 1–5 [CI] * | Tone BT lynposten [CI] * | Format OK % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gpt-oss-120b (Nebius) | Åbne vægte (global) | 5 | 92.3 [80.9; 100.0] | 2 | 2.60 [2.00; 3.40] | – † | 60 |
| Qwen3-235B-A22B (Nebius) | Åbne vægte (global) | 5 | 87.1 [81.5; 92.5] | 4 | 3.60 [2.20; 4.60] | – | 20 |

\* **Vejledende**: enigheden med menneskelige bedømmere lå under tærsklen (se Enighed).
† Tone bedømt af én dommer (krydsfamilie-reglen).

## Median-isme-indikatorer

| Model | Hedges | Fyldord | Generiske | Anglicismer | Passiv-andel | Gns. sætningslængde | Sprog-lækage (ord) | Særskrivning |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| *Stilguidernes mål* | 0 | 0 | 0 | 0 | lav | Lynposten < 14; Landsavisen 16–22; Erhvervsnyt 15–20 | 0 | 0 |
| gpt-oss-120b (Nebius) | 0.00 | 0.11 | 0.00 | 0.00 | 0.09 | 23.5 | 0.00 | 0.00 |
| Qwen3-235B-A22B (Nebius) | 0.02 | 0.13 | 0.00 | 0.00 | 0.08 | 19.8 | 0.00 | 0.00 |

Tallene er *indikatorer* pr. output, ikke scorer.

## Enighed

Menneskelige rækker: 0 fra 0 bedømmer(e).

| Dimension | Mål | Menneske vs. dommer A | Dommer A vs. dommer B | Menneske vs. menneske |
| --- | --- | --- | --- | --- |
| Kildetroskab | Pearson r på andel understøttede påstande | – | – | – |
| Kildetroskab | Gns. absolut forskel (procentpoint) | – | – | – |
| Kildetroskab | Eksakt enighed om modsigelser | – | – | – |
| Sprogkvalitet | Kvadratisk vægtet Cohen's κ | – | – | – |
| Sprogkvalitet | Andel inden for ±1 | – | – | – |
| Tone | Spearman ρ (menneskelig 1–5 vs. BT-rating) | – | – | – (κ) |
| Tone | Enighed om vinder i par | – | – | – |

## Publiceringsregel

Tærskel: κ/ρ ≥ 0.4. Under tærsklen mærkes tabellen **Vejledende**.
- Sprogkvalitet: **Vejledende** (κ = –).
- Tone (t2_rubrik, t4_versionering, t6_lydmanus): **Vejledende** (ρ = –).

## Noter

- Ingen menneskelige vurderinger endnu; alle human-mål er tomme.

## Celler med én dommer (krydsfamilie-reglen)

- anthropic-frontier / tone
- anthropic-mid / tone
- nebius-gpt-oss-120b / tone

## Begrænsninger

1. Én fælles prompt pr. opgave; produktionsbrug ville tune prompts pr. model og brand. Resultaterne undervurderer derfor tunede opsætninger.
2. 40 kildetekster giver brede konfidensintervaller; forskelle inden for overlappende intervaller er ikke forskelle.
3. Tone-scoren er dommer-relativ; enigheden med menneskelige bedømmere var κ/ρ = endnu ikke målt.
4. Arketyperne er opfundne; de er ikke rigtige mediers stemmer. Udskift `styleguides/` og kør igen.
5. Sprogkvalitet er overvejende bedømt af modeller; mennesker rettede flest fejl netop her.
6. Modelversioner ændrer sig på uger; alle tabeller er dateret, og `make rerun` gentager målingen.
7. Dommer A er selv en åben model i testen; dens egne output er ikke tonebedømt af den (krydsfamilie-reglen), og de celler er markeret.

## v2

1. Tunede prompts pr. model og pr. arketype (den første og vigtigste udvidelse).
2. Flere kildetekster (80–100) for smallere intervaller.
3. Flere menneskelige bedømmere og parvis tonebedømmelse også for mennesker.
4. Rigtige mediers stilguider, kørt af medierne selv.
5. Journalistisk produktivitet og adoption, målt i en redaktion.

## Reproducér

```bash
uv sync
uv run danews report      # genberegner alle tabeller og figurer fra scores/ uden API-nøgler
make rerun                # (kræver nøgler) generate → check → judge → report
```

Figurer: `results/figures/`. Rådata: `outputs/`, `scores/`. Modelversioner og priser: `models.yaml`, `DECISIONS.md`.
