"""Stage `report`: aggregate committed scores into tables, figures and site_data.json (§6.6).

Never calls an API. Aggregation unit is the source text; every mean carries a bootstrap interval.
No composite score exists anywhere in this module.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from .agreement import compute_agreement, render_agreement_md
from .analysis import bootstrap_ci, bt_bootstrap
from .check import load_outputs
from .config import Config
from .judge import TONE_TASKS, _judges, _read_jsonl, single_judge_cells
from .schemas import CheckRecord, FluencyRecord, GroundingRecord, Output, TonePairRecord

# Validated categorical palette (dataviz reference instance), one slot per tier, fixed order.
TIER_ORDER = ["frontier_proprietary", "mid_proprietary", "eu", "open_global", "open_nordic"]
TIER_LABEL = {
    "frontier_proprietary": "Frontier (proprietær)",
    "mid_proprietary": "Mellemklasse (proprietær)",
    "eu": "Europæisk",
    "open_global": "Åbne vægte (global)",
    "open_nordic": "Dansk/nordisk åben",
}
TIER_COLOUR = dict(
    zip(TIER_ORDER, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"], strict=True)
)
TIER_MARKER = dict(zip(TIER_ORDER, ["o", "s", "D", "^", "v"], strict=True))
TEXT_PRIMARY, TEXT_SECONDARY, GRID = "#0b0b0b", "#52514e", "#e3e2dd"

LIMITATIONS_FIXED = [
    "Én fælles prompt pr. opgave; produktionsbrug ville tune prompts pr. model og brand. Resultaterne undervurderer derfor tunede opsætninger.",
    "40 kildetekster giver brede konfidensintervaller; forskelle inden for overlappende intervaller er ikke forskelle.",
    "Tone-scoren er dommer-relativ; enigheden med menneskelige bedømmere var κ/ρ = {kappa_rho}.",
    "Arketyperne er opfundne; de er ikke rigtige mediers stemmer. Udskift `styleguides/` og kør igen.",
    "Sprogkvalitet er overvejende bedømt af modeller; mennesker rettede flest fejl netop her.",
    "Modelversioner ændrer sig på uger; alle tabeller er dateret, og `make rerun` gentager målingen.",
    "Dommer A er selv en åben model i testen; dens egne output er ikke tonebedømt af den (krydsfamilie-reglen), og de celler er markeret.",
]
V2_LIST = [
    "Tunede prompts pr. model og pr. arketype (den første og vigtigste udvidelse).",
    "Flere kildetekster (80–100) for smallere intervaller.",
    "Flere menneskelige bedømmere og parvis tonebedømmelse også for mennesker.",
    "Rigtige mediers stilguider, kørt af medierne selv.",
    "Journalistisk produktivitet og adoption, målt i en redaktion.",
]


@dataclass
class CI:
    point: float
    lo: float
    hi: float

    def fmt(self, digits: int = 1, unit: str = "") -> str:
        if math.isnan(self.point):
            return "–"
        return f"{self.point:.{digits}f}{unit} [{self.lo:.{digits}f}; {self.hi:.{digits}f}]"


@dataclass
class TaskRow:
    model_id: str
    display: str
    tier: str
    n_outputs: int
    pct_supported: CI
    n_contradicted: int
    facts_preserved_pct: float | None
    fluency: CI
    tone_bt: dict[str, CI]  # archetype → rating
    format_pass_pct: float
    single_judge_tone: bool


@dataclass
class DependencyRow:
    model_id: str
    display: str
    tier: str
    cost_per_1000_t1_usd: float | None
    latency_median_ms: float | None
    latency_p95_ms: float | None
    open_weights: bool
    licence: str
    eu_residency: str
    params_b: float | None
    pinned_version: str
    snapshot_date: str
    billing: str


# Loading --------------------------------------------------------------------------


@dataclass
class Scores:
    outputs: dict[str, Output]
    checks: dict[str, CheckRecord]
    grounding: dict[str, GroundingRecord]  # judge A only
    fluency: dict[str, FluencyRecord]  # judge A only
    tone: list[TonePairRecord]  # judge A only


def load_scores(cfg: Config) -> Scores:
    judge_a = _judges(cfg)[0].id
    outputs = {o.ref: o for o in load_outputs(cfg) if not o.error}  # API failures are not results
    checks = {c.output_ref: c for c in _read_jsonl(cfg.paths.scores / "checks.jsonl", CheckRecord)}
    grounding = {
        g.output_ref: g
        for g in _read_jsonl(cfg.paths.scores / "grounding.jsonl", GroundingRecord)
        if g.judge_id == judge_a and not g.error
    }
    fluency = {
        f.output_ref: f
        for f in _read_jsonl(cfg.paths.scores / "fluency.jsonl", FluencyRecord)
        if f.judge_id == judge_a and not f.error and f.score is not None
    }
    tone = [
        t
        for t in _read_jsonl(cfg.paths.scores / "tone_pairs.jsonl", TonePairRecord)
        if t.judge_id == judge_a and t.winner is not None
    ]
    return Scores(outputs, checks, grounding, fluency, tone)


# Aggregation --------------------------------------------------------------------------


def _ci(groups: list[list[float]], n_boot: int) -> CI:
    return CI(*bootstrap_ci(groups, n_boot=n_boot))


def task_table(cfg: Config, sc: Scores, task_id: str, n_boot: int) -> list[TaskRow]:
    task = cfg.task(task_id)
    single = {m for m, _ in single_judge_cells(cfg)}
    rows: list[TaskRow] = []
    for model in cfg.models:
        outs = [o for o in sc.outputs.values() if o.model_id == model.id and o.task_id == task_id]
        if not outs:
            continue
        by_src: dict[str, list[Output]] = defaultdict(list)
        for o in outs:
            by_src[o.source_id].append(o)
        g_groups = [
            [sc.grounding[o.ref].pct_supported for o in os_ if o.ref in sc.grounding]
            for os_ in by_src.values()
        ]
        f_groups = [
            [float(sc.fluency[o.ref].score) for o in os_ if o.ref in sc.fluency]  # type: ignore[arg-type]
            for os_ in by_src.values()
        ]
        n_contra = sum(sc.grounding[o.ref].n_contradicted for o in outs if o.ref in sc.grounding)
        chk = [sc.checks[o.ref] for o in outs if o.ref in sc.checks]
        fp = None
        tot = sum(c.facts_total for c in chk)
        if tot:
            fp = 100.0 * sum(c.facts_preserved for c in chk) / tot
        fmt_pass = 100.0 * sum(c.format_pass for c in chk) / len(chk) if chk else 0.0
        tone_bt: dict[str, CI] = {}
        if task_id in TONE_TASKS:
            for arch in task.uses_archetypes:
                pairs = [
                    p
                    for p in sc.tone
                    if p.slot_ref.startswith(task_id + "/") and p.slot_ref.endswith("__" + arch)
                ]
                models = sorted({m for p in pairs for m in (p.left_model, p.right_model)})
                if model.id in models:
                    bt = bt_bootstrap(
                        pairs, models, lambda s: s.split("/", 1)[1].split("__")[0], n_boot=n_boot
                    )
                    tone_bt[arch] = CI(*bt[model.id])
                else:
                    tone_bt[arch] = CI(math.nan, math.nan, math.nan)
        rows.append(
            TaskRow(
                model_id=model.id,
                display=model.display,
                tier=model.tier,
                n_outputs=len(outs),
                pct_supported=_ci(g_groups, n_boot),
                n_contradicted=n_contra,
                facts_preserved_pct=fp,
                fluency=_ci(f_groups, n_boot),
                tone_bt=tone_bt,
                format_pass_pct=fmt_pass,
                single_judge_tone=model.id in single,
            )
        )
    return rows


def dependency_table(cfg: Config, sc: Scores) -> list[DependencyRow]:
    rows = []
    snapshot = _run_date(sc)
    for m in cfg.models:
        t1 = [
            o
            for o in sc.outputs.values()
            if o.model_id == m.id and o.task_id == "t1_telegram" and not o.error
        ]
        cost = None
        if t1 and (m.price_in_per_m or m.price_out_per_m):
            per = [
                (o.prompt_tokens * m.price_in_per_m + o.completion_tokens * m.price_out_per_m) / 1e6
                for o in t1
            ]
            cost = float(np.mean(per)) * 1000
        lat = [o.latency_ms for o in t1]
        rows.append(
            DependencyRow(
                model_id=m.id,
                display=m.display,
                tier=m.tier,
                cost_per_1000_t1_usd=cost,
                latency_median_ms=float(np.median(lat)) if lat else None,
                latency_p95_ms=float(np.percentile(lat, 95)) if lat else None,
                open_weights=m.open_weights,
                licence=m.licence,
                eu_residency=m.eu_residency,
                params_b=m.params_b,
                pinned_version=m.pinned_version,
                snapshot_date=snapshot,
                billing=m.billing,
            )
        )
    return rows


def indicator_table(cfg: Config, sc: Scores) -> list[dict]:
    rows = []
    for m in cfg.models:
        chk = [
            sc.checks[o.ref]
            for o in sc.outputs.values()
            if o.model_id == m.id and o.ref in sc.checks
        ]
        if not chk:
            continue
        med = [c.medianism for c in chk]
        n = len(med)
        rows.append(
            {
                "model_id": m.id,
                "display": m.display,
                "hedges_per_output": sum(x.hedges for x in med) / n,
                "fillers_per_output": sum(x.fillers for x in med) / n,
                "generic_per_output": sum(x.generic_phrases for x in med) / n,
                "anglicisms_per_output": sum(x.anglicisms for x in med) / n,
                "passive_share": sum(x.passive_share for x in med) / n,
                "mean_sentence_len": sum(x.mean_sentence_len for x in med) / n,
                "lang_leak_tokens_per_output": sum(c.lang_leak_tokens for c in chk) / n,
                "saerskrivning_per_output": sum(len(c.saerskrivning_suspects) for c in chk) / n,
            }
        )
    return rows


def _run_date(sc: Scores) -> str:
    if not sc.outputs:
        return datetime.now(UTC).date().isoformat()
    return max(o.created for o in sc.outputs.values()).date().isoformat()


# Markdown -------------------------------------------------------------------------------


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def _fmt_num(x: float | None, digits: int = 0, unit: str = "") -> str:
    return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{digits}f}{unit}"


def task_table_md(
    cfg: Config, task_id: str, rows: list[TaskRow], indicative_tone: bool, indicative_fluency: bool
) -> str:
    task = cfg.task(task_id)
    headers = ["Model", "Niveau", "n", "Understøttede påstande % [CI]", "Modsigelser (sum)"]
    if any(r.facts_preserved_pct is not None for r in rows):
        headers.append("Fakta bevaret %")
    headers.append("Sprogkvalitet 1–5 [CI]" + (" *" if indicative_fluency else ""))
    for arch in task.uses_archetypes if task_id in TONE_TASKS else []:
        headers.append(f"Tone BT {arch} [CI]" + (" *" if indicative_tone else ""))
    headers.append("Format OK %")
    body = []
    for r in rows:
        cells = [
            r.display,
            TIER_LABEL[r.tier],
            str(r.n_outputs),
            r.pct_supported.fmt(1),
            str(r.n_contradicted),
        ]
        if "Fakta bevaret %" in headers:
            cells.append(_fmt_num(r.facts_preserved_pct, 0))
        cells.append(r.fluency.fmt(2))
        for arch in task.uses_archetypes if task_id in TONE_TASKS else []:
            cells.append(r.tone_bt[arch].fmt(0) + (" †" if r.single_judge_tone else ""))
        cells.append(_fmt_num(r.format_pass_pct, 0))
        body.append(cells)
    note = []
    if indicative_tone or indicative_fluency:
        note.append(
            "\\* **Vejledende**: enigheden med menneskelige bedømmere lå under tærsklen (se Enighed)."
        )
    if task_id in TONE_TASKS and any(r.single_judge_tone for r in rows):
        note.append("† Tone bedømt af én dommer (krydsfamilie-reglen).")
    return (
        f"### {task.name} ({task_id})\n\n"
        + _md_table(headers, body)
        + ("\n\n" + "\n".join(note) if note else "")
    )


def dependency_md(rows: list[DependencyRow]) -> str:
    headers = [
        "Model",
        "Niveau",
        "USD pr. 1.000 T1",
        "Latens median/p95 ms",
        "Åbne vægte",
        "Licens",
        "EU-residens",
        "Params (mia.)",
        "Version",
        "Dato",
    ]
    body = []
    for r in rows:
        cost = _fmt_num(r.cost_per_1000_t1_usd, 2) if r.billing != "local" else "selvhostet*"
        lat = (
            f"{_fmt_num(r.latency_median_ms)}/{_fmt_num(r.latency_p95_ms)}"
            + (" (lokal)" if r.billing == "local" else "")
            if r.latency_median_ms is not None
            else "–"
        )
        body.append(
            [
                r.display,
                TIER_LABEL[r.tier],
                cost,
                lat,
                "ja" if r.open_weights else "nej",
                r.licence,
                r.eu_residency,
                _fmt_num(r.params_b, 1),
                f"`{r.pinned_version}`",
                r.snapshot_date,
            ]
        )
    return (
        _md_table(headers, body)
        + "\n\n\\* Selvhostede modeller: GPU-time ÷ gennemløb, se `docs/serving.md`."
    )


def indicators_md(rows: list[dict]) -> str:
    headers = [
        "Model",
        "Hedges",
        "Fyldord",
        "Generiske",
        "Anglicismer",
        "Passiv-andel",
        "Gns. sætningslængde",
        "Sprog-lækage (ord)",
        "Særskrivning",
    ]
    target = [
        "*Stilguidernes mål*",
        "0",
        "0",
        "0",
        "0",
        "lav",
        "Lynposten < 14; Landsavisen 16–22; Erhvervsnyt 15–20",
        "0",
        "0",
    ]
    body = [target] + [
        [
            r["display"],
            f"{r['hedges_per_output']:.2f}",
            f"{r['fillers_per_output']:.2f}",
            f"{r['generic_per_output']:.2f}",
            f"{r['anglicisms_per_output']:.2f}",
            f"{r['passive_share']:.2f}",
            f"{r['mean_sentence_len']:.1f}",
            f"{r['lang_leak_tokens_per_output']:.2f}",
            f"{r['saerskrivning_per_output']:.2f}",
        ]
        for r in rows
    ]
    return _md_table(headers, body) + "\n\nTallene er *indikatorer* pr. output, ikke scorer."


def lead_md(
    cfg: Config,
    sc: Scores,
    tables: dict[str, list[TaskRow]],
    dep: list[DependencyRow],
    run_date: str,
) -> str:
    n_models = len({o.model_id for o in sc.outputs.values()})
    n_out = len(sc.outputs)
    s1 = f"Cavling-bench målte {n_models} sprogmodeller på {len(cfg.tasks)} redaktionelle opgaver over {len(cfg.sources)} danske offentlige kildetekster ({n_out} output, kørt {run_date})."
    t4 = tables.get("t4_versionering") or next(iter(tables.values()), [])
    valid = [r for r in t4 if not math.isnan(r.pct_supported.point)]
    s2 = ""
    if valid:
        best = max(valid, key=lambda r: r.pct_supported.point)
        worst = min(valid, key=lambda r: r.pct_supported.point)
        s2 = f" På versioneringsopgaven lå andelen af understøttede påstande mellem {worst.pct_supported.point:.0f} % ({worst.display}) og {best.pct_supported.point:.0f} % ({best.display}); intervallerne overlapper for de fleste modeller."
    costs = [r for r in dep if r.cost_per_1000_t1_usd]
    s3 = ""
    if costs:
        cheap, dear = (
            min(costs, key=lambda r: r.cost_per_1000_t1_usd),
            max(costs, key=lambda r: r.cost_per_1000_t1_usd),
        )
        s3 = f" Prisen for 1.000 telegrammer spændte fra USD {cheap.cost_per_1000_t1_usd:.2f} ({cheap.display}) til USD {dear.cost_per_1000_t1_usd:.2f} ({dear.display})."
    return s1 + s2 + s3


def leaderboard_md(
    cfg: Config,
    sc: Scores,
    tables: dict[str, list[TaskRow]],
    dep: list[DependencyRow],
    ind: list[dict],
    agreement_md: str,
    kappa_rho: str,
    indicative_tone: bool,
    indicative_fluency: bool,
    cuts: list[str],
    run_date: str,
) -> str:
    parts = [
        "# Cavling-bench – resultater",
        "",
        f"*Målt {run_date}. Ingen samlet score: hver tabel rangerer pr. opgave og pr. dimension. Alle tal har 95 % bootstrap-intervaller over kildetekster.*",
        "",
        lead_md(cfg, sc, tables, dep, run_date),
        "",
        "## Afhængighed",
        "",
        dependency_md(dep),
        "",
        "## Resultater pr. opgave",
        "",
    ]
    for tid in [t.id for t in cfg.tasks]:
        if tid in tables:
            parts += [task_table_md(cfg, tid, tables[tid], indicative_tone, indicative_fluency), ""]
    parts += [
        "## Median-isme-indikatorer",
        "",
        indicators_md(ind),
        "",
        "## Enighed",
        "",
        agreement_md.split("\n", 1)[1].strip(),
        "",
    ]
    cells = single_judge_cells(cfg)
    parts += ["## Celler med én dommer (krydsfamilie-reglen)", ""]
    parts += [f"- {m} / {d}" for m, d in cells] or ["- ingen"]
    parts += ["", "## Begrænsninger", ""]
    parts += [
        f"{i}. {lim.format(kappa_rho=kappa_rho)}" for i, lim in enumerate(LIMITATIONS_FIXED, 1)
    ]
    parts += [f"{len(LIMITATIONS_FIXED) + i}. {c}" for i, c in enumerate(cuts, 1)]
    parts += ["", "## v2", ""] + [f"{i}. {v}" for i, v in enumerate(V2_LIST, 1)]
    parts += [
        "",
        "## Reproducér",
        "",
        "```bash",
        "uv sync",
        "uv run danews report      # genberegner alle tabeller og figurer fra scores/ uden API-nøgler",
        "make rerun                # (kræver nøgler) generate → check → judge → report",
        "```",
        "",
        "Figurer: `results/figures/`. Rådata: `outputs/`, `scores/`. Modelversioner og priser: `models.yaml`, `DECISIONS.md`.",
    ]
    return "\n".join(parts) + "\n"


# Figures --------------------------------------------------------------------------------


def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=8)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def _dot_whisker_panels(
    cfg: Config,
    tables: dict[str, list[TaskRow]],
    metric: str,
    xlabel: str,
    xlim: tuple[float, float],
    path: Path,
    title: str,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    tasks = [t for t in cfg.tasks if t.id in tables and tables[t.id]]
    if not tasks:
        return
    ncols = min(3, len(tasks))
    nrows = math.ceil(len(tasks) / ncols)
    n_models = max(len(tables[t.id]) for t in tasks)
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(3.4 * ncols + 1.5, (0.36 * n_models + 1.4) * nrows),
        sharey=True,
        squeeze=False,
    )
    flat = axes.ravel()
    for ax in flat[len(tasks) :]:
        ax.set_visible(False)
    for ax, task in zip(flat, tasks, strict=False):
        rows = tables[task.id]
        for i, r in enumerate(rows):
            ci: CI = getattr(r, metric)
            if math.isnan(ci.point):
                continue
            c = TIER_COLOUR[r.tier]
            ax.plot([ci.lo, ci.hi], [i, i], color=c, linewidth=2, solid_capstyle="round")
            ax.plot(
                ci.point,
                i,
                marker=TIER_MARKER[r.tier],
                color=c,
                markersize=7,
                markeredgecolor="white",
                markeredgewidth=1.2,
            )
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels([r.display for r in rows], fontsize=8, color=TEXT_PRIMARY)
        ax.invert_yaxis()
        ax.set_xlim(*xlim)
        ax.set_title(task.name, fontsize=10, color=TEXT_PRIMARY, loc="left")
        ax.set_xlabel(xlabel, fontsize=8, color=TEXT_SECONDARY)
        _style(ax)
    handles = [
        plt.Line2D(
            [],
            [],
            color=TIER_COLOUR[t],
            marker=TIER_MARKER[t],
            linestyle="",
            markersize=7,
            label=TIER_LABEL[t],
        )
        for t in TIER_ORDER
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        ncol=len(TIER_ORDER),
        frameon=False,
        fontsize=8,
        bbox_to_anchor=(0.5, -0.02),
    )
    fig.suptitle(title, fontsize=11, color=TEXT_PRIMARY, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def fig_tone_t4(cfg: Config, tables: dict[str, list[TaskRow]], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = tables.get("t4_versionering", [])
    archs = cfg.task("t4_versionering").uses_archetypes if rows else []
    if not rows or not archs:
        return
    fig, axes = plt.subplots(
        1, len(archs), figsize=(2.8 * len(archs) + 1.5, 0.38 * len(rows) + 1.6), sharey=True
    )
    axes = np.atleast_1d(axes)
    for ax, arch in zip(axes, archs, strict=True):
        for i, r in enumerate(rows):
            ci = r.tone_bt.get(arch)
            if ci is None or math.isnan(ci.point):
                continue
            c = TIER_COLOUR[r.tier]
            ax.plot([ci.lo, ci.hi], [i, i], color=c, linewidth=2, solid_capstyle="round")
            ax.plot(
                ci.point,
                i,
                marker=TIER_MARKER[r.tier],
                color=c,
                markersize=7,
                markeredgecolor="white",
                markeredgewidth=1.2,
            )
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels([r.display for r in rows], fontsize=8, color=TEXT_PRIMARY)
        ax.invert_yaxis()
        ax.set_xlim(0, 100)
        ax.axvline(50, color=GRID, linewidth=1)
        ax.set_title(arch.capitalize(), fontsize=10, color=TEXT_PRIMARY, loc="left")
        ax.set_xlabel("Bradley–Terry-rating (gns. 50)", fontsize=8, color=TEXT_SECONDARY)
        _style(ax)
    fig.suptitle(
        "F3 · Tonefit, versionering (T4), pr. arketype",
        fontsize=11,
        color=TEXT_PRIMARY,
        x=0.01,
        ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def fig_quality_cost(
    cfg: Config, tables: dict[str, list[TaskRow]], dep: list[DependencyRow], path: Path
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = {r.model_id: r for r in tables.get("t4_versionering", [])}
    pts = []
    for d in dep:
        r = rows.get(d.model_id)
        if (
            not r
            or not d.cost_per_1000_t1_usd
            or math.isnan(r.pct_supported.point)
            or math.isnan(r.fluency.point)
        ):
            continue
        quality = (
            r.pct_supported.point / 100 * r.fluency.point / 5 * 100
        )  # T4 grounding × fluency, 0–100
        pts.append((d, quality))
    if not pts:
        return
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for d, q in pts:
        ax.scatter(
            d.cost_per_1000_t1_usd,
            q,
            s=70,
            color=TIER_COLOUR[d.tier],
            marker=TIER_MARKER[d.tier],
            edgecolor="white",
            linewidth=1.2,
            zorder=3,
        )
        ax.annotate(
            d.display,
            (d.cost_per_1000_t1_usd, q),
            xytext=(6, 4),
            textcoords="offset points",
            fontsize=8,
            color=TEXT_PRIMARY,
        )
    ax.set_xscale("log")
    ax.set_xlabel("USD pr. 1.000 T1-opgaver (listepris, log)", fontsize=9, color=TEXT_SECONDARY)
    ax.set_ylabel(
        "T4-kvalitet: understøttede påstande × sprogkvalitet (0–100)",
        fontsize=9,
        color=TEXT_SECONDARY,
    )
    ax.set_title(
        "F4 · Kvalitet mod pris (kun betalte API-modeller)",
        fontsize=11,
        color=TEXT_PRIMARY,
        loc="left",
    )
    handles = [
        plt.Line2D(
            [],
            [],
            color=TIER_COLOUR[t],
            marker=TIER_MARKER[t],
            linestyle="",
            markersize=7,
            label=TIER_LABEL[t],
        )
        for t in TIER_ORDER
        if any(d.tier == t for d, _ in pts)
    ]
    ax.legend(handles=handles, frameon=False, fontsize=8, loc="lower right")
    _style(ax)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# Entry point --------------------------------------------------------------------------------


def _ci_json(ci: CI) -> dict:
    return {k: (None if math.isnan(v) else round(v, 3)) for k, v in asdict(ci).items()}


def run_report(cfg: Config, n_boot: int = 1000, cuts: list[str] | None = None) -> dict:
    import pandas as pd

    sc = load_scores(cfg)
    res = cfg.paths.results
    figdir = res / "figures"
    figdir.mkdir(parents=True, exist_ok=True)
    run_date = _run_date(sc)
    tables = {t.id: task_table(cfg, sc, t.id, n_boot) for t in cfg.tasks}
    tables = {k: v for k, v in tables.items() if v}
    dep = dependency_table(cfg, sc)
    ind = indicator_table(cfg, sc)
    agr = compute_agreement(cfg)
    agreement_md = render_agreement_md(agr)
    (res / "agreement.md").write_text(agreement_md)
    kappa_rho = (
        f"κ = {agr.fluency_kappa:.2f}, ρ = {agr.tone_rho:.2f}"
        if not math.isnan(agr.fluency_kappa)
        else "endnu ikke målt"
    )
    cuts = cuts if cuts is not None else _read_cuts(cfg)

    # CSVs
    for tid, rows in tables.items():
        pd.DataFrame(
            [
                {
                    "model_id": r.model_id,
                    "n": r.n_outputs,
                    "pct_supported": r.pct_supported.point,
                    "pct_supported_lo": r.pct_supported.lo,
                    "pct_supported_hi": r.pct_supported.hi,
                    "n_contradicted": r.n_contradicted,
                    "facts_preserved_pct": r.facts_preserved_pct,
                    "fluency": r.fluency.point,
                    "fluency_lo": r.fluency.lo,
                    "fluency_hi": r.fluency.hi,
                    **{f"tone_bt_{a}": c.point for a, c in r.tone_bt.items()},
                    "format_pass_pct": r.format_pass_pct,
                }
                for r in rows
            ]
        ).to_csv(res / f"task_{tid}.csv", index=False)
    pd.DataFrame([asdict(d) for d in dep]).to_csv(res / "dependency.csv", index=False)
    pd.DataFrame(ind).to_csv(res / "indicators.csv", index=False)
    (res / "dependency.md").write_text("# Afhængighed\n\n" + dependency_md(dep) + "\n")

    # Figures
    _dot_whisker_panels(
        cfg,
        tables,
        "pct_supported",
        "% understøttede påstande",
        (0, 100),
        figdir / "f1_grounding.png",
        "F1 · Kildetroskab pr. opgave (dommer A, 95 % CI over kildetekster)",
    )
    _dot_whisker_panels(
        cfg,
        tables,
        "fluency",
        "Sprogkvalitet 1–5",
        (1, 5),
        figdir / "f2_fluency.png",
        "F2 · Dansk sprogkvalitet pr. opgave (dommer A, 95 % CI)",
    )
    fig_tone_t4(cfg, tables, figdir / "f3_tone_t4.png")
    fig_quality_cost(cfg, tables, dep, figdir / "f4_quality_cost.png")

    md = leaderboard_md(
        cfg,
        sc,
        tables,
        dep,
        ind,
        agreement_md,
        kappa_rho,
        agr.tone_indicative,
        agr.fluency_indicative,
        cuts,
        run_date,
    )
    (res / "leaderboard.md").write_text(md)

    site = {
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "run_date": run_date,
        "n_sources": len(cfg.sources),
        "n_outputs": len(sc.outputs),
        "tier_labels": TIER_LABEL,
        "models": [asdict(d) for d in dep],
        "tasks": [
            {
                "id": tid,
                "name": cfg.task(tid).name,
                "archetypes": cfg.task(tid).uses_archetypes,
                "rows": [
                    {
                        "model_id": r.model_id,
                        "display": r.display,
                        "tier": r.tier,
                        "n": r.n_outputs,
                        "pct_supported": _ci_json(r.pct_supported),
                        "n_contradicted": r.n_contradicted,
                        "facts_preserved_pct": r.facts_preserved_pct,
                        "fluency": _ci_json(r.fluency),
                        "tone_bt": {a: _ci_json(c) for a, c in r.tone_bt.items()},
                        "format_pass_pct": r.format_pass_pct,
                        "single_judge_tone": r.single_judge_tone,
                    }
                    for r in rows
                ],
            }
            for tid, rows in tables.items()
        ],
        "indicators": ind,
        "agreement": {
            k: (None if isinstance(v, float) and math.isnan(v) else v)
            for k, v in asdict(agr).items()
            if k != "notes"
        },
        "indicative": {"tone": agr.tone_indicative, "fluency": agr.fluency_indicative},
        "single_judge_cells": single_judge_cells(cfg),
        "figures": [p.name for p in sorted(figdir.glob("*.png"))],
        "limitations": [lim.format(kappa_rho=kappa_rho) for lim in LIMITATIONS_FIXED] + cuts,
        "v2": V2_LIST,
        "repo": "https://github.com/erasmus/cavling-bench",
    }
    (res / "site_data.json").write_text(json.dumps(site, ensure_ascii=False, indent=1))
    return {
        "tasks": len(tables),
        "models": len(dep),
        "figures": len(site["figures"]),
        "leaderboard": str(res / "leaderboard.md"),
    }


def _read_cuts(cfg: Config) -> list[str]:
    """Optional results/cuts.md: one Danish bullet per cut, appended to Begrænsninger."""
    p = cfg.paths.results / "cuts.md"
    if not p.exists():
        return []
    return [
        ln.lstrip("-* ").strip()
        for ln in p.read_text().splitlines()
        if ln.strip().startswith(("-", "*"))
    ]
