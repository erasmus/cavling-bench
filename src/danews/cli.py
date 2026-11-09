"""Typer CLI: one sub-command per pipeline stage (§6). Every stage is idempotent."""

from __future__ import annotations

from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from .config import Config, Paths

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Cavling-bench pipeline")
judge_app = typer.Typer(no_args_is_help=True, help="LLM judging")
spotcheck_app = typer.Typer(no_args_is_help=True, help="Human spot-check")
app.add_typer(judge_app, name="judge")
app.add_typer(spotcheck_app, name="spotcheck")
console = Console()

ROOT_OPT = typer.Option(None, "--root", help="Repo root (default: $DANEWS_ROOT or .)")


def _cfg(root: Path | None) -> Config:
    load_dotenv()
    return Config(Paths(root.resolve()) if root else Paths.from_env())


def _fail_if(problems: list[str], label: str) -> None:
    if problems:
        for p in problems:
            console.print(f"[red]✗[/] {p}")
        console.print(f"[red]{label}: {len(problems)} problem(s)[/]")
        raise typer.Exit(1)
    console.print(f"[green]{label}: ok[/]")


@app.command()
def collect(only: str | None = None, root: Path | None = ROOT_OPT) -> None:
    """Fetch registered sources into data/sources/*.md."""
    from .collect import run_collect

    run_collect(_cfg(root), only)


@app.command("sources-lint")
def sources_lint(
    fix_word_count: bool = typer.Option(False, help="Rewrite word_count from the body"),
    root: Path | None = ROOT_OPT,
) -> None:
    """Enforce §5.1 constraints and domain counts."""
    from .collect import lint_sources

    _fail_if(lint_sources(_cfg(root), fix_word_count), "sources-lint")


@app.command("facts-lint")
def facts_lint(root: Path | None = ROOT_OPT) -> None:
    """Enforce §5.2: spans occur in body, canonicals parse, ≥5 facts, ≥3 critical."""
    from .collect import lint_facts

    _fail_if(lint_facts(_cfg(root)), "facts-lint")


@app.command()
def generate(
    only: str | None = typer.Option(None, help="Substring filter on task/slot"),
    models: str | None = typer.Option(None, help="Comma-separated model ids"),
    tasks: str | None = typer.Option(None, help="Comma-separated task ids"),
    sources: str | None = typer.Option(None, help="Comma-separated source ids"),
    no_cache: bool = False,
    force: bool = False,
    dry_run: bool = False,
    root: Path | None = ROOT_OPT,
) -> None:
    """Generate outputs for every model × task × source × archetype."""
    from .generate import run_generate

    run_generate(
        _cfg(root),
        only=only,
        models=models.split(",") if models else None,
        tasks=tasks.split(",") if tasks else None,
        sources=sources.split(",") if sources else None,
        use_cache=not no_cache,
        force=force,
        dry_run=dry_run,
    )


@app.command()
def status(root: Path | None = ROOT_OPT) -> None:
    """Outputs present / errors per model."""
    from .generate import status as _status

    t = Table("model", "expected", "present", "errors", "ok %")
    for mid, row in _status(_cfg(root)).items():
        ok = row["present"] - row["errors"]
        pct = 100 * ok / row["expected"] if row["expected"] else 0
        t.add_row(mid, str(row["expected"]), str(row["present"]), str(row["errors"]), f"{pct:.1f}")
    console.print(t)


@app.command()
def check(only: str | None = None, force: bool = False, root: Path | None = ROOT_OPT) -> None:
    """Mechanical checks → scores/checks.jsonl."""
    from .check import run_check

    n = run_check(_cfg(root), only, force)
    console.print(f"checks.jsonl: {n} records")


@judge_app.command("grounding")
def judge_grounding(
    only: str | None = None,
    no_cache: bool = False,
    force: bool = False,
    root: Path | None = ROOT_OPT,
) -> None:
    from .judge import run_grounding

    console.print(run_grounding(_cfg(root), only, not no_cache, force))


@judge_app.command("tone")
def judge_tone(
    only: str | None = None,
    no_cache: bool = False,
    force: bool = False,
    root: Path | None = ROOT_OPT,
) -> None:
    from .judge import run_tone

    console.print(run_tone(_cfg(root), only, not no_cache, force))


@judge_app.command("fluency")
def judge_fluency(
    only: str | None = None,
    no_cache: bool = False,
    force: bool = False,
    root: Path | None = ROOT_OPT,
) -> None:
    from .judge import run_fluency

    console.print(run_fluency(_cfg(root), only, not no_cache, force))


@spotcheck_app.command("sample")
def spotcheck_sample(n: int = 150, seed: int = 42, root: Path | None = ROOT_OPT) -> None:
    """Stratified sample for human rating → scores/spotcheck_sample.csv (+ key file)."""
    from .spotcheck import run_sample

    console.print(run_sample(_cfg(root), n, seed))


@app.command()
def agreement(root: Path | None = ROOT_OPT) -> None:
    """Human vs judge and judge vs judge agreement → results/agreement.md."""
    from .agreement import run_agreement

    console.print(run_agreement(_cfg(root)))


@app.command()
def report(root: Path | None = ROOT_OPT) -> None:
    """Aggregate scores → results/*.md, figures, site_data.json. No API calls."""
    from .report import run_report

    console.print(run_report(_cfg(root)))


@app.command()
def site(root: Path | None = ROOT_OPT) -> None:
    """Copy site_data.json and figures into site/."""
    from .site import run_site

    console.print(run_site(_cfg(root)))


@app.command()
def costs(root: Path | None = ROOT_OPT) -> None:
    """Cumulative spend by model and stage, split paid vs credit."""
    from collections import defaultdict

    from .llm import read_costs

    cfg = _cfg(root)
    by_model: dict[str, float] = defaultdict(float)
    by_stage: dict[str, float] = defaultdict(float)
    by_billing: dict[str, float] = defaultdict(float)
    for rec in read_costs(cfg.paths):
        if rec.cached:
            continue
        by_model[rec.model_id] += rec.cost_usd
        by_stage[rec.stage] += rec.cost_usd
        try:
            billing = cfg.model(rec.model_id).billing
        except KeyError:
            billing = "unknown"
        by_billing[billing] += rec.cost_usd
    for title, d in (("model", by_model), ("stage", by_stage), ("billing", by_billing)):
        t = Table(title, "USD")
        for k, v in sorted(d.items(), key=lambda kv: -kv[1]):
            t.add_row(k, f"{v:.4f}")
        console.print(t)
    paid = by_billing.get("paid", 0.0)
    colour = "red" if paid > 45 else "green"
    console.print(f"[{colour}]paid total: USD {paid:.2f}[/] (stop and ask above USD 45)")


@app.command()
def smoke(root: Path | None = ROOT_OPT) -> None:
    """Run the whole pipeline on fixtures with the fake provider (< 60 s)."""
    from .smoke import run_smoke

    run_smoke(root)


if __name__ == "__main__":
    app()
