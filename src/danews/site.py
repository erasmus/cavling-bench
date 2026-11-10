"""Stage `site`: copy site_data.json and figures next to the results page (§6.7).

The landing page is site/index.html, the method page site/metode/, the data-driven
results page site/resultater/.
"""

from __future__ import annotations

import shutil

from .config import Config


def run_site(cfg: Config) -> dict[str, str]:
    dest = cfg.paths.site / "resultater"
    dest.mkdir(parents=True, exist_ok=True)
    src = cfg.paths.results / "site_data.json"
    if not src.exists():
        raise FileNotFoundError("results/site_data.json missing; run `danews report` first")
    shutil.copy(src, dest / "site_data.json")
    figs = dest / "figures"
    figs.mkdir(exist_ok=True)
    n = 0
    for p in (cfg.paths.results / "figures").glob("*.png"):
        shutil.copy(p, figs / p.name)
        n += 1
    return {"site_data": str(dest / "site_data.json"), "figures": str(n)}
