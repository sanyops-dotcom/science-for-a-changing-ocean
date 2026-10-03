"""ORI Phase 3 - importance.py: rule-based importance scoring.

Every statistical_result record from Phase 2 gets a transparent 0-100 score built from
four documented components (config.IMPORTANCE_W_*). This is NOT an oceanographic judgement -
it only says how strong, how large, how well-sampled and how corroborated a statistical
finding is. No LLM, no hidden weights: every score can be recomputed by hand from the formula
printed in the report.
"""
from typing import Dict, List

import numpy as np
import pandas as pd

import config
from reasoning.common import RContext, Registry

STRENGTH_VALUE = {"STRONG": 1.0, "MODERATE": 0.66, "WEAK": 0.33, "NONE": 0.0}
EFFECT_KEY = {  # which statistic field is this module's effect size, and its saturation scale
    "transect": ("epsilon2", 1.0),
    "relational": ("rho", 1.0),
    "vertical": ("share_negative", None),   # handled specially (max deviation from 0.5)
}


def _effect_size(rec: dict) -> float:
    m, s = rec["module"], rec["statistic"]
    if m == "transect":
        return abs(s.get("epsilon2") or 0)
    if m == "relational":
        return abs(s.get("rho") or 0)
    if m == "spatial":
        if "I" in s:                                   # autocorrelation record
            return abs(s.get("I") or 0)
        tests = s.get("tests") or []                    # gradient record: strongest tested predictor
        return max((abs(t["rho"]) for t in tests), default=0.0)
    if m == "vertical":
        return abs((s.get("share_negative") or 0) - (s.get("share_positive") or 0))
    return 0.0


def _n(rec: dict) -> int:
    return int(rec.get("n") or 0)


def score_record(rec: dict, n_stations: int, corroboration: float) -> Dict:
    strength_c = STRENGTH_VALUE.get(rec.get("evidence_strength"), 0.0)
    effect_c = min(_effect_size(rec), 1.0)
    n_c = min(_n(rec) / n_stations, 1.0) if n_stations else 0.0
    corrob_c = min(corroboration, 1.0)
    total = 100 * (config.IMPORTANCE_W_STRENGTH * strength_c + config.IMPORTANCE_W_EFFECT * effect_c +
                   config.IMPORTANCE_W_N * n_c + config.IMPORTANCE_W_CORROBORATION * corrob_c)
    band = ("HIGH" if total >= config.IMPORTANCE_BAND_HIGH else
            "MEDIUM" if total >= config.IMPORTANCE_BAND_MEDIUM else "LOW")
    return {"score": round(total, 1), "band": band,
            "components": {"strength": round(strength_c, 3), "effect": round(effect_c, 3),
                           "n": round(n_c, 3), "corroboration": round(corrob_c, 3)}}


def _corroboration_counts(records: List[dict]) -> Dict[str, int]:
    """For each parameter, how many distinct modules found a supported (non-NONE) result."""
    by_param: Dict[str, set] = {}
    for r in records:
        if r["level"] != "statistical_result" or r.get("evidence_strength") in (None, "NONE", "n/a"):
            continue
        for p in r["parameters"]:
            by_param.setdefault(p, set()).add(r["module"])
    return {p: len(mods) for p, mods in by_param.items()}


def run(ctx: RContext) -> Registry:
    reg = Registry()
    scored = [r for r in ctx.stat_records if r["level"] == "statistical_result"]
    corrob = _corroboration_counts(ctx.stat_records)
    n_stations = ctx.gate["n_independent_observations"]
    rows = []
    for r in scored:
        c = max((corrob.get(p, 1) for p in r["parameters"]), default=1)
        corrob_norm = (c - 1) / 2.0   # 1 module -> 0, 2 -> 0.5, >=3 -> 1
        s = score_record(r, n_stations, corrob_norm)
        rows.append({"stat_id": r["id"], "module": r["module"], "parameters": "|".join(r["parameters"]),
                     "evidence_strength": r["evidence_strength"], "n": r["n"], "score": s["score"], "band": s["band"],
                     "component_strength": s["components"]["strength"], "component_effect": s["components"]["effect"],
                     "component_n": s["components"]["n"], "component_corroboration": s["components"]["corroboration"]})
        reg.add("IMP", "importance_score", f"{r['id']} scored {s['score']}/100 ({s['band']}).",
                parameters=r["parameters"], stat_ids=[r["id"]], detail={**s, "n_stations": n_stations})
    df = pd.DataFrame(rows).sort_values("score", ascending=False)
    ctx.save_table(df, "importance_scores.csv")
    return reg, df
