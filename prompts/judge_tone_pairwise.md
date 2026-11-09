Two Danish news texts were written from the same source for the same publication. Judge ONLY
how well each follows the STYLE GUIDE: register, sentence length, headline rules, lede
convention, forbidden moves. Ignore factual accuracy; another audit covers it. Do not reward
length. Return JSON only:
{"winner":"left|right|tie","confidence":1|2|3,"rationale":"<= 40 words, in English"}

STYLE GUIDE:
{{ styleguide }}

SOURCE (context only): {{ source_title }} — {{ source_excerpt }}

LEFT:
{{ left_text }}

RIGHT:
{{ right_text }}
