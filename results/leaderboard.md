# Cavling-bench – resultater

*Målt 2026-11-10. Ingen samlet score: hver tabel rangerer pr. opgave og pr. dimension. Alle tal har 95 % bootstrap-intervaller over kildetekster.*

Cavling-bench målte 4 sprogmodeller på 6 redaktionelle opgaver over 40 danske offentlige kildetekster (774 output, kørt 2026-11-10). På versioneringsopgaven lå andelen af understøttede påstande mellem 92 % (Qwen3-235B-A22B (Nebius)) og 100 % (Claude Sonnet 5.5); intervallerne overlapper for de fleste modeller. Prisen for 1.000 telegrammer spændte fra USD 0.40 (gpt-oss-120b (Nebius)) til USD 7.04 (Claude Sonnet 5.5).

## Afhængighed

| Model | Niveau | USD pr. 1.000 T1 | Latens median/p95 ms | Åbne vægte | Licens | EU-residens | Params (mia.) | Version | Dato |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Fable 5.1 | Frontier (proprietær) | – | – | nej | proprietary | no | – | `claude-fable-5-1` | 2026-11-10 |
| Claude Sonnet 5.5 | Mellemklasse (proprietær) | 7.04 | 2948/3054 | nej | proprietary | no | – | `claude-sonnet-5-5` | 2026-11-10 |
| GPT-6 Astra | Frontier (proprietær) | – | – | nej | proprietary | cloud region | – | `gpt-6-astra` | 2026-11-10 |
| GPT-6 Luna | Mellemklasse (proprietær) | – | – | nej | proprietary | cloud region | – | `gpt-6-luna` | 2026-11-10 |
| Gemini 4 Argon | Frontier (proprietær) | – | – | nej | proprietary | no | – | `gemini-4-argon` | 2026-11-10 |
| Gemini 3.8 Flash | Mellemklasse (proprietær) | – | – | nej | proprietary | no | – | `gemini-3.8-flash` | 2026-11-10 |
| Mistral Large 4 | Europæisk | – | – | ja | Mistral Ecosystem Open Weight License | yes | 1050.0 | `mistral-large-4-0` | 2026-11-10 |
| Mistral Small 4 | Europæisk | – | – | ja | Apache-2.0 | yes | 119.0 | `mistral-small-2603` | 2026-11-10 |
| gpt-oss-120b (Nebius) | Åbne vægte (global) | 0.40 | 1168/1923 | ja | Apache-2.0 | cloud region | 120.0 | `openai/gpt-oss-120b` | 2026-11-10 |
| Qwen3-235B-A22B (Nebius) | Åbne vægte (global) | 0.50 | 5966/18914 | ja | Apache-2.0 | cloud region | 235.0 | `Qwen/Qwen3-235B-A22B-Instruct-2507` | 2026-11-10 |
| DFM Mimir v1.5 (1.8B) | Dansk/nordisk åben | selvhostet* | – | ja | Apache-2.0 | self-hosted | 1.8 | `danish-foundation-models/DFM-Mimir-v1.5` | 2026-11-10 |
| DFM Munin 7B alpha | Dansk/nordisk åben | selvhostet* | – | ja | Apache-2.0 | self-hosted | 7.0 | `danish-foundation-models/munin-7b-alpha` | 2026-11-10 |
| DanskGPT v4 12B | Dansk/nordisk åben | selvhostet* | – | ja | CC-BY-4.0 (Gemma terms apply) | self-hosted | 12.0 | `syvai/danskgpt-v4-12b` | 2026-11-10 |

\* Selvhostede modeller: GPU-time ÷ gennemløb, se `docs/serving.md`.

## Resultater pr. opgave

### Nyhedstelegram (t1_telegram)

| Model | Niveau | n | Understøttede påstande % [CI] | Modsigelser (sum) | Fakta bevaret % | Sprogkvalitet 1–5 [CI] * | Format OK % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Sonnet 5.5 | Mellemklasse (proprietær) | 5 | 100.0 [100.0; 100.0] | 0 | 96 | 3.80 [3.20; 4.40] | 80 |
| Gemini 3.8 Flash | Mellemklasse (proprietær) | 1 | – | 0 | 0 | – | 0 |
| gpt-oss-120b (Nebius) | Åbne vægte (global) | 40 | 94.5 [88.5; 98.4] | 1 | 85 | 4.36 [4.15; 4.56] | 60 |
| Qwen3-235B-A22B (Nebius) | Åbne vægte (global) | 40 | 89.0 [84.1; 92.9] | 7 | 92 | 4.15 [3.88; 4.40] | 65 |

\* **Vejledende**: enigheden med menneskelige bedømmere lå under tærsklen (se Enighed).

### Rubrik og underrubrik (t2_rubrik)

| Model | Niveau | n | Understøttede påstande % [CI] | Modsigelser (sum) | Sprogkvalitet 1–5 [CI] * | Tone BT lynposten [CI] * | Tone BT landsavisen [CI] * | Tone BT erhvervsnyt [CI] * | Format OK % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Sonnet 5.5 | Mellemklasse (proprietær) | 15 | 92.0 [85.7; 98.3] | 1 | 4.73 [4.33; 5.00] | 50 [35; 65] † | 50 [35; 65] † | 35 [35; 35] † | 60 |
| Gemini 3.8 Flash | Mellemklasse (proprietær) | 3 | – | 0 | – | – | – | – | 0 |
| gpt-oss-120b (Nebius) | Åbne vægte (global) | 120 | 94.4 [90.9; 97.2] | 7 | 4.73 [4.60; 4.85] | – † | – † | – † | 52 |
| Qwen3-235B-A22B (Nebius) | Åbne vægte (global) | 120 | 91.4 [88.1; 94.5] | 0 | 4.60 [4.44; 4.74] | 50 [35; 65] | 50 [35; 65] | 65 [65; 65] | 64 |

\* **Vejledende**: enigheden med menneskelige bedømmere lå under tærsklen (se Enighed).
† Tone bedømt af én dommer (krydsfamilie-reglen).

### Faktaboks (t3_faktaboks)

| Model | Niveau | n | Understøttede påstande % [CI] | Modsigelser (sum) | Fakta bevaret % | Sprogkvalitet 1–5 [CI] * | Format OK % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Sonnet 5.5 | Mellemklasse (proprietær) | 5 | 100.0 [100.0; 100.0] | 0 | 78 | 4.00 [3.00; 4.80] | 80 |
| Gemini 3.8 Flash | Mellemklasse (proprietær) | 1 | – | 0 | 0 | – | 0 |
| gpt-oss-120b (Nebius) | Åbne vægte (global) | 40 | 98.0 [95.5; 100.0] | 2 | 72 | 4.50 [4.30; 4.70] | 98 |
| Qwen3-235B-A22B (Nebius) | Åbne vægte (global) | 40 | 96.5 [93.5; 99.0] | 2 | 80 | 4.00 [3.75; 4.28] | 92 |

\* **Vejledende**: enigheden med menneskelige bedømmere lå under tærsklen (se Enighed).

### Versionering (t4_versionering)

| Model | Niveau | n | Understøttede påstande % [CI] | Modsigelser (sum) | Sprogkvalitet 1–5 [CI] * | Tone BT lynposten [CI] * | Tone BT landsavisen [CI] * | Format OK % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Sonnet 5.5 | Mellemklasse (proprietær) | 10 | 100.0 [100.0; 100.0] | 0 | 3.80 [3.30; 4.20] | 65 [35; 65] † | 65 [35; 65] † | 70 |
| Gemini 3.8 Flash | Mellemklasse (proprietær) | 2 | – | 0 | – | – | – | 0 |
| gpt-oss-120b (Nebius) | Åbne vægte (global) | 80 | 93.1 [90.1; 95.3] | 9 | 3.98 [3.76; 4.16] | – † | – † | 59 |
| Qwen3-235B-A22B (Nebius) | Åbne vægte (global) | 80 | 92.4 [90.7; 94.3] | 10 | 3.81 [3.61; 4.01] | 35 [35; 65] | 35 [35; 65] | 55 |

\* **Vejledende**: enigheden med menneskelige bedømmere lå under tærsklen (se Enighed).
† Tone bedømt af én dommer (krydsfamilie-reglen).

### Forkortelse (t5_forkortelse)

| Model | Niveau | n | Understøttede påstande % [CI] | Modsigelser (sum) | Fakta bevaret % | Sprogkvalitet 1–5 [CI] * | Format OK % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Sonnet 5.5 | Mellemklasse (proprietær) | 5 | 100.0 [100.0; 100.0] | 0 | 94 | 3.80 [2.80; 4.60] | 20 |
| Gemini 3.8 Flash | Mellemklasse (proprietær) | 1 | – | 0 | 0 | – | 0 |
| gpt-oss-120b (Nebius) | Åbne vægte (global) | 40 | 98.5 [97.1; 99.6] | 3 | 85 | 4.03 [3.85; 4.18] | 60 |
| Qwen3-235B-A22B (Nebius) | Åbne vægte (global) | 40 | 97.3 [95.4; 98.9] | 5 | 92 | 3.75 [3.45; 4.03] | 65 |

\* **Vejledende**: enigheden med menneskelige bedømmere lå under tærsklen (se Enighed).

### Lydmanus (t6_lydmanus)

| Model | Niveau | n | Understøttede påstande % [CI] | Modsigelser (sum) | Sprogkvalitet 1–5 [CI] * | Tone BT lynposten [CI] * | Format OK % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Sonnet 5.5 | Mellemklasse (proprietær) | 5 | 92.4 [83.8; 100.0] | 2 | 3.40 [2.40; 4.40] | 65 [65; 65] † | 100 |
| Gemini 3.8 Flash | Mellemklasse (proprietær) | 1 | – | 0 | – | – | 0 |
| gpt-oss-120b (Nebius) | Åbne vægte (global) | 40 | 78.4 [71.4; 84.3] | 43 | 3.02 [2.67; 3.38] | – † | 70 |
| Qwen3-235B-A22B (Nebius) | Åbne vægte (global) | 40 | 87.1 [83.5; 90.5] | 36 | 2.90 [2.60; 3.23] | 35 [35; 35] | 35 |

\* **Vejledende**: enigheden med menneskelige bedømmere lå under tærsklen (se Enighed).
† Tone bedømt af én dommer (krydsfamilie-reglen).

## Median-isme-indikatorer

| Model | Hedges | Fyldord | Generiske | Anglicismer | Passiv-andel | Gns. sætningslængde | Sprog-lækage (ord) | Særskrivning |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| *Stilguidernes mål* | 0 | 0 | 0 | 0 | lav | Lynposten < 14; Landsavisen 16–22; Erhvervsnyt 15–20 | 0 | 0 |
| Claude Sonnet 5.5 | 0.00 | 0.16 | 0.00 | 0.00 | 0.07 | 17.2 | 0.00 | 0.00 |
| Gemini 3.8 Flash | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.0 | 0.00 | 0.00 |
| gpt-oss-120b (Nebius) | 0.01 | 0.19 | 0.02 | 0.00 | 0.08 | 29.6 | 0.16 | 0.00 |
| Qwen3-235B-A22B (Nebius) | 0.01 | 0.12 | 0.03 | 0.00 | 0.08 | 19.9 | 0.12 | 0.00 |

Tallene er *indikatorer* pr. output, ikke scorer.

## Enighed

Menneskelige rækker: 0 fra 0 bedømmer(e).

| Dimension | Mål | Menneske vs. dommer A | Dommer A vs. dommer B | Menneske vs. menneske |
| --- | --- | --- | --- | --- |
| Kildetroskab | Pearson r på andel understøttede påstande | – | 0.46 | – |
| Kildetroskab | Gns. absolut forskel (procentpoint) | – | – | – |
| Kildetroskab | Eksakt enighed om modsigelser | – | 73 % | – |
| Sprogkvalitet | Kvadratisk vægtet Cohen's κ | – | 0.17 | – |
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
