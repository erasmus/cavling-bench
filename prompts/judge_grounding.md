You are auditing a Danish news text against its single source document. Extract every atomic
factual claim in OUTPUT and label each:
- supported: stated in SOURCE, or a number within 1% / a paraphrase that preserves meaning
- unsupported: not present in SOURCE and not derivable from it
- contradicted: SOURCE states otherwise (different number, date, actor, outcome)
Attributions like "ifølge kilden" are not claims. Headlines and stylistic framing are not claims
unless they assert a fact. Quote the exact SOURCE span for supported/contradicted claims.
Return JSON only: {"claims":[{"text":"...","label":"...","source_span":"...|null","rationale":"..."}]}

SOURCE:
{{ source_body }}

OUTPUT:
{{ output_text }}
