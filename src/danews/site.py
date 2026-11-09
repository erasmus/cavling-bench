"""Stage `site`: copy site_data.json and figures next to the static page (§6.7)."""

from __future__ import annotations

import shutil

from .config import Config


def run_site(cfg: Config) -> dict[str, str]:
    cfg.paths.site.mkdir(parents=True, exist_ok=True)
    src = cfg.paths.results / "site_data.json"
    if not src.exists():
        raise FileNotFoundError("results/site_data.json missing; run `danews report` first")
    shutil.copy(src, cfg.paths.site / "site_data.json")
    figs = cfg.paths.site / "figures"
    figs.mkdir(exist_ok=True)
    n = 0
    for p in (cfg.paths.results / "figures").glob("*.png"):
        shutil.copy(p, figs / p.name)
        n += 1
    return {"site_data": str(cfg.paths.site / "site_data.json"), "figures": str(n)}
