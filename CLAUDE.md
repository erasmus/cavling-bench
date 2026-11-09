Read REQUIREMENTS.md before doing anything. It defines scope, schemas, pipeline stages,
prompts and acceptance criteria. Do not invent requirements that are not in it; if something
is ambiguous, ask or pick the option it marks as default and note it in DECISIONS.md.

Rules:
- Python 3.12, managed with uv. Run `uv run pytest` before every commit.
- Never edit files under data/ or outputs/ by hand after they are marked frozen in DECISIONS.md.
- Every pipeline stage is a Typer CLI under src/danews/cli.py and is idempotent.
- All model calls go through src/danews/llm.py (LiteLLM). No direct vendor SDK imports elsewhere.
- Log every model call's cost to costs.jsonl. Stop and ask if cumulative paid spend exceeds USD 45.
- Danish user-facing text (prompts, style guides, write-up). English code, comments, README.
- Commit small and often. Conventional commits (feat:, fix:, data:, docs:, test:).
