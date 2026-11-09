.PHONY: collect generate check judge spotcheck report site smoke test lint

collect:
	uv run danews collect

generate:
	uv run danews generate

check:
	uv run danews check

judge:
	uv run danews judge grounding
	uv run danews judge tone
	uv run danews judge fluency

spotcheck:
	uv run danews spotcheck sample --n 150

report:
	uv run danews report

site:
	uv run danews site

smoke:
	uv run danews smoke

test:
	uv run pytest

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests
