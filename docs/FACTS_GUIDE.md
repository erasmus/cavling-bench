# Writing facts files (for whoever curates data/facts/<id>.yaml)

One file per source, schema `FactsFile` in `src/danews/schemas.py`. Example (from the test fixtures):

```yaml
source_id: fx-dst-2026-ledighed
facts:
  - id: f1
    type: number            # number | date | name | place | org | quote
    value: "1.200 personer" # as it appears in the source
    canonical: 1200         # number → numeric in base units (1,2 mia. kr. → 1200000000)
    unit: DKK               # optional: DKK, %, pp, EUR ...
    span: "faldt med 1.200 personer fra august til september 2026"  # VERBATIM, ≤ 15 words
    critical: true
  - id: f2
    type: date
    value: "30. oktober 2026"
    canonical: "2026-10-30" # ISO; month precision "2026-10" if the source gives only a month
    span: "offentliggjort torsdag den 30. oktober 2026"
    critical: false
  - id: f3
    type: org
    value: "Danmarks Statistik"
    canonical: "danmarks statistik"   # lowercase normalised string
    span: "nye tal fra Danmarks Statistik"
    critical: true
```

Rules the linter enforces (`uv run danews facts-lint`):
- ≥ 5 facts, ≥ 3 marked `critical: true` (the facts a 100-word telegram must not lose).
- `span` must occur verbatim in the body (whitespace-normalised). Copy-paste it.
- `value` must occur in the body (usually inside the span).
- number: `canonical` must equal what `value` parses to. "12 pct." → 12 with unit "%";
  "1,2 mia. kr." → 1200000000 unit DKK; "350 mio." → 350000000; "seks måneder" → 6.
  Percentages: unit "%" (or "pp" for procentpoint). Ages: "32-årig" → 32.
- date: `value` must parse: "12. november 2026", "12/11 2026", "november 2026", "2026".
- name/org/place: canonical = lowercase of the name as written (no genitive -s).

Guidance: 6–10 facts per source. Prefer the facts a journalist would check: the headline number,
the date of the decision, the main actor(s), the amount, the place. Mark `critical` the 3–5 the
story cannot be told without. Do not invent; do not paraphrase spans. Spans must be short (≤ 15
words) and unique enough to find. Prefer `number` facts with units over bare counts.
