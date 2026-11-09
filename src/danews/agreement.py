"""Stage `agreement`: human vs judge and judge vs judge agreement → results/agreement.md (§6.5)."""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from .analysis import bt_ratings
from .config import Config
from .judge import TONE_TASKS, _judges, _read_jsonl
from .schemas import FluencyRecord, GroundingRecord, TonePairRecord

PUBLICATION_THRESHOLD = 0.4


@dataclass
class AgreementResult:
    n_human_rows: int = 0
    n_raters: int = 0
    grounding_r: float = math.nan
    grounding_mad: float = math.nan
    contradicted_exact: float = math.nan
    fluency_kappa: float = math.nan
    fluency_within1: float = math.nan
    tone_rho: float = math.nan
    ab_fluency_kappa: float = math.nan
    ab_grounding_exact: float = math.nan
    ab_grounding_r: float = math.nan
    ab_tone_winner_agreement: float = math.nan
    human_fluency_kappa: float = math.nan
    human_tone_kappa: float = math.nan
    human_grounding_r: float = math.nan
    notes: list[str] = field(default_factory=list)

    @property
    def fluency_indicative(self) -> bool:
        return math.isnan(self.fluency_kappa) or self.fluency_kappa < PUBLICATION_THRESHOLD

    @property
    def tone_indicative(self) -> bool:
        return math.isnan(self.tone_rho) or self.tone_rho < PUBLICATION_THRESHOLD


def _float(x: str) -> float | None:
    try:
        return float(str(x).replace(",", ".")) if str(x).strip() else None
    except ValueError:
        return None


def _pearson(a: list[float], b: list[float]) -> float:
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return math.nan
    return float(np.corrcoef(a, b)[0, 1])


def _spearman(a: list[float], b: list[float]) -> float:
    from scipy.stats import spearmanr

    if len(a) < 3:
        return math.nan
    return float(spearmanr(a, b).statistic)


def _qwk(a: list[int], b: list[int]) -> float:
    from sklearn.metrics import cohen_kappa_score

    if len(a) < 3 or len(set(a)) < 2 and len(set(b)) < 2:
        return math.nan
    return float(cohen_kappa_score(a, b, weights="quadratic"))


def _load_human(cfg: Config) -> tuple[dict[str, str], list[dict[str, str]]]:
    key_path = cfg.paths.scores / "spotcheck_key.csv"
    human_path = cfg.paths.scores / "spotcheck_human.csv"
    key: dict[str, str] = {}
    if key_path.exists():
        with key_path.open() as f:
            key = {r["sample_id"]: r["output_ref"] for r in csv.DictReader(f)}
    rows: list[dict[str, str]] = []
    if human_path.exists():
        with human_path.open() as f:
            rows = [r for r in csv.DictReader(f) if r.get("sample_id") in key]
    return key, rows


def compute_agreement(cfg: Config) -> AgreementResult:
    res = AgreementResult()
    judges = _judges(cfg)
    judge_a = judges[0].id
    judge_b = judges[1].id if len(judges) > 1 else None
    grounding = _read_jsonl(cfg.paths.scores / "grounding.jsonl", GroundingRecord)
    fluency = _read_jsonl(cfg.paths.scores / "fluency.jsonl", FluencyRecord)
    tone = _read_jsonl(cfg.paths.scores / "tone_pairs.jsonl", TonePairRecord)
    g_by = {(r.output_ref, r.judge_id): r for r in grounding if not r.error}
    f_by = {(r.output_ref, r.judge_id): r for r in fluency if not r.error}

    # BT rating per output (its model's rating within the (task, archetype) stratum, judge A)
    bt_by_output: dict[str, float] = {}
    strata: dict[tuple[str, str], list[TonePairRecord]] = defaultdict(list)
    for p in tone:
        if p.judge_id != judge_a or p.winner is None:
            continue
        task, slot = p.slot_ref.split("/", 1)
        arch = slot.partition("__")[2]
        strata[(task, arch)].append(p)
    for ps in strata.values():
        models = sorted({m for p in ps for m in (p.left_model, p.right_model)})
        for m, rating in bt_ratings(ps, models).items():
            for p in ps:
                for mm in (p.left_model, p.right_model):
                    if mm == m:
                        bt_by_output[f"{m}/{p.slot_ref}"] = rating

    # Human vs judge A
    key, rows = _load_human(cfg)
    res.n_human_rows = len(rows)
    res.n_raters = len({r.get("rater_id", "") for r in rows})
    hg, jg, hc, jc, hf, jf, ht, jt = [], [], [], [], [], [], [], []
    by_sample: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        by_sample[r["sample_id"]].append(r)
    for sid, rs in by_sample.items():
        ref = key[sid]
        g = g_by.get((ref, judge_a))
        f = f_by.get((ref, judge_a))
        hgs = [v for v in (_float(r.get("h_grounding_pct", "")) for r in rs) if v is not None]
        hcs = [v for v in (_float(r.get("h_contradicted", "")) for r in rs) if v is not None]
        hfs = [v for v in (_float(r.get("h_fluency_1to5", "")) for r in rs) if v is not None]
        hts = [v for v in (_float(r.get("h_tone_1to5", "")) for r in rs) if v is not None]
        if g and hgs:
            hg.append(float(np.mean(hgs)))
            jg.append(g.pct_supported)
        if g and hcs:
            hc.append(int(round(np.mean(hcs))))
            jc.append(g.n_contradicted)
        if f and f.score is not None and hfs:
            hf.append(int(round(np.mean(hfs))))
            jf.append(f.score)
        if ref in bt_by_output and hts:
            ht.append(float(np.mean(hts)))
            jt.append(bt_by_output[ref])
    res.grounding_r = _pearson(hg, jg)
    res.grounding_mad = float(np.mean(np.abs(np.array(hg) - np.array(jg)))) if hg else math.nan
    res.contradicted_exact = (
        float(np.mean([a == b for a, b in zip(hc, jc, strict=True)])) if hc else math.nan
    )
    res.fluency_kappa = _qwk(hf, jf)
    res.fluency_within1 = (
        float(np.mean([abs(a - b) <= 1 for a, b in zip(hf, jf, strict=True)])) if hf else math.nan
    )
    res.tone_rho = _spearman(ht, jt)

    # Judge A vs Judge B on the overlap
    if judge_b:
        af, bf, ag, bg, ac, bc = [], [], [], [], [], []
        for (ref, jid), r in f_by.items():
            if jid == judge_b and (ref, judge_a) in f_by and r.score is not None:
                a = f_by[(ref, judge_a)].score
                if a is not None:
                    af.append(a)
                    bf.append(r.score)
        for (ref, jid), r in g_by.items():
            if jid == judge_b and (ref, judge_a) in g_by:
                a = g_by[(ref, judge_a)]
                ag.append(a.pct_supported)
                bg.append(r.pct_supported)
                ac.append(a.n_contradicted > 0)
                bc.append(r.n_contradicted > 0)
        res.ab_fluency_kappa = _qwk(af, bf)
        res.ab_grounding_r = _pearson(ag, bg)
        res.ab_grounding_exact = (
            float(np.mean([x == y for x, y in zip(ac, bc, strict=True)])) if ac else math.nan
        )
        a_pairs = {
            (p.slot_ref, p.left_model, p.right_model): p.winner
            for p in tone
            if p.judge_id == judge_a and p.winner
        }
        agree = [
            a_pairs[(p.slot_ref, p.left_model, p.right_model)] == p.winner
            for p in tone
            if p.judge_id == judge_b
            and p.winner
            and (p.slot_ref, p.left_model, p.right_model) in a_pairs
        ]
        res.ab_tone_winner_agreement = float(np.mean(agree)) if agree else math.nan

    # Inter-rater agreement among humans (first two raters per sample with ≥ 2 raters)
    pf1, pf2, pt1, pt2, pg1, pg2 = [], [], [], [], [], []
    for rs in by_sample.values():
        raters = sorted({r.get("rater_id", "") for r in rs})
        if len(raters) < 2:
            continue
        r1 = next(r for r in rs if r.get("rater_id") == raters[0])
        r2 = next(r for r in rs if r.get("rater_id") == raters[1])
        for col, (l1, l2), cast in (
            ("h_fluency_1to5", (pf1, pf2), int),
            ("h_tone_1to5", (pt1, pt2), int),
            ("h_grounding_pct", (pg1, pg2), float),
        ):
            v1, v2 = _float(r1.get(col, "")), _float(r2.get(col, ""))
            if v1 is not None and v2 is not None:
                l1.append(cast(round(v1)) if cast is int else v1)
                l2.append(cast(round(v2)) if cast is int else v2)
    res.human_fluency_kappa = _qwk(pf1, pf2)
    res.human_tone_kappa = _qwk(pt1, pt2)
    res.human_grounding_r = _pearson(pg1, pg2)
    if res.n_human_rows == 0:
        res.notes.append("Ingen menneskelige vurderinger endnu; alle human-mål er tomme.")
    return res


def _fmt(x: float, pct: bool = False) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    return f"{100 * x:.0f} %" if pct else f"{x:.2f}"


def render_agreement_md(res: AgreementResult, tone_tasks: tuple[str, ...] = TONE_TASKS) -> str:
    lines = [
        "# Enighed mellem dommere og mennesker",
        "",
        f"Menneskelige rækker: {res.n_human_rows} fra {res.n_raters} bedømmer(e).",
        "",
        "| Dimension | Mål | Menneske vs. dommer A | Dommer A vs. dommer B | Menneske vs. menneske |",
        "| --- | --- | --- | --- | --- |",
        f"| Kildetroskab | Pearson r på andel understøttede påstande | {_fmt(res.grounding_r)} | {_fmt(res.ab_grounding_r)} | {_fmt(res.human_grounding_r)} |",
        f"| Kildetroskab | Gns. absolut forskel (procentpoint) | {_fmt(res.grounding_mad)} | – | – |",
        f"| Kildetroskab | Eksakt enighed om modsigelser | {_fmt(res.contradicted_exact, pct=True)} | {_fmt(res.ab_grounding_exact, pct=True)} | – |",
        f"| Sprogkvalitet | Kvadratisk vægtet Cohen's κ | {_fmt(res.fluency_kappa)} | {_fmt(res.ab_fluency_kappa)} | {_fmt(res.human_fluency_kappa)} |",
        f"| Sprogkvalitet | Andel inden for ±1 | {_fmt(res.fluency_within1, pct=True)} | – | – |",
        f"| Tone | Spearman ρ (menneskelig 1–5 vs. BT-rating) | {_fmt(res.tone_rho)} | – | {_fmt(res.human_tone_kappa)} (κ) |",
        f"| Tone | Enighed om vinder i par | – | {_fmt(res.ab_tone_winner_agreement, pct=True)} | – |",
        "",
        "## Publiceringsregel",
        "",
        f"Tærskel: κ/ρ ≥ {PUBLICATION_THRESHOLD}. Under tærsklen mærkes tabellen **Vejledende**.",
        f"- Sprogkvalitet: {'**Vejledende**' if res.fluency_indicative else 'publiceres'} (κ = {_fmt(res.fluency_kappa)}).",
        f"- Tone ({', '.join(tone_tasks)}): {'**Vejledende**' if res.tone_indicative else 'publiceres'} (ρ = {_fmt(res.tone_rho)}).",
    ]
    if res.notes:
        lines += ["", "## Noter", ""] + [f"- {n}" for n in res.notes]
    return "\n".join(lines) + "\n"


def run_agreement(cfg: Config) -> dict[str, float | int]:
    res = compute_agreement(cfg)
    cfg.paths.results.mkdir(parents=True, exist_ok=True)
    (cfg.paths.results / "agreement.md").write_text(render_agreement_md(res))
    return {
        "n_human_rows": res.n_human_rows,
        "fluency_kappa": res.fluency_kappa,
        "tone_rho": res.tone_rho,
        "ab_fluency_kappa": res.ab_fluency_kappa,
    }
