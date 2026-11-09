"""`danews smoke`: whole pipeline on the fixtures with the fake provider, in a temp root."""

from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path

from rich.console import Console

from .config import Config, Paths

console = Console()
REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures"


def build_root(dst: Path) -> Paths:
    shutil.copytree(FIXTURES / "data", dst / "data")
    shutil.copytree(REPO / "data" / "wordlists", dst / "data" / "wordlists")
    for d in ("tasks", "styleguides", "prompts", "site"):
        shutil.copytree(
            REPO / d, dst / d, ignore=shutil.ignore_patterns("site_data.json", "figures")
        )
    shutil.copy(FIXTURES / "models.yaml", dst / "models.yaml")
    return Paths(dst)


def run_smoke(root: Path | None = None) -> None:
    from .agreement import run_agreement
    from .check import run_check
    from .collect import lint_facts, lint_sources
    from .generate import run_generate, status
    from .judge import run_fluency, run_grounding, run_tone
    from .report import run_report
    from .site import run_site
    from .spotcheck import run_sample

    t0 = time.perf_counter()
    tmp = Path(tempfile.mkdtemp(prefix="danews-smoke-")) if root is None else root
    cfg = Config(build_root(tmp / "root"))
    steps = [
        ("sources-lint", lambda: lint_sources(cfg) or "ok"),
        ("facts-lint", lambda: lint_facts(cfg) or "ok"),
        ("generate", lambda: run_generate(cfg, models=["fake-echo", "fake-bad"])),
        ("status", lambda: status(cfg)),
        ("check", lambda: run_check(cfg)),
        ("judge grounding", lambda: run_grounding(cfg)),
        ("judge tone", lambda: run_tone(cfg)),
        ("judge fluency", lambda: run_fluency(cfg)),
        ("spotcheck sample", lambda: run_sample(cfg, n=20)),
        ("agreement", lambda: run_agreement(cfg)),
        ("report", lambda: run_report(cfg, n_boot=100)),
        ("site", lambda: run_site(cfg)),
    ]
    for name, fn in steps:
        out = fn()
        console.print(f"[green]✓[/] {name}: {out}")
    md = (cfg.paths.results / "leaderboard.md").read_text()
    assert "## Begrænsninger" in md and "composite" not in md.lower()
    dt = time.perf_counter() - t0
    console.print(f"[bold green]smoke ok[/] in {dt:.1f}s → {cfg.paths.root}")
    if dt > 60:
        raise SystemExit("smoke exceeded 60 s")
