"""ORI Phase 3 - confounding.py.

Phase 2 found that several parameters correlate with each other AND with transect number
(a spatial proxy). That raises a specific statistical question: does a parameter pair
correlate because of a real pairwise relationship, or mostly because both drift along the
same spatial gradient? This module answers with a partial Spearman correlation controlling
for transect number - still level 2 evidence (a number), not an explanation of why.
"""
import numpy as np
import pandas as pd
from scipy import stats as sps

import config
from reasoning.common import RContext, Registry


def partial_spearman(x, y, z):
    """Partial Spearman rho of x,y controlling for z (residuals-of-ranks method)."""
    x, y, z = (sps.rankdata(v) for v in (np.asarray(x, float), np.asarray(y, float), np.asarray(z, float)))
    n = len(x)
    def resid(a, b):
        slope, intercept, *_ = sps.linregress(b, a)
        return a - (intercept + slope * b)
    rx, ry = resid(x, z), resid(y, z)
    r, _ = sps.pearsonr(rx, ry)
    df = n - 2 - 1  # n - 2 - k, k = 1 control variable
    if df <= 0 or abs(r) >= 1:
        return float(r), np.nan, n, df
    t = r * np.sqrt(df / (1 - r ** 2))
    p = 2 * (1 - sps.t.cdf(abs(t), df))
    return float(r), float(p), n, df


def run(ctx: RContext):
    reg = Registry()
    rel = [r for r in ctx.stat_records if r["module"] == "relational" and r["level"] == "statistical_result"
           and r.get("evidence_strength") not in (None, "NONE", "n/a") and len(r["parameters"]) == 2]
    rows = []
    for r in rel:
        a, b = r["parameters"]
        d = ctx.st[[config.CONFOUND_CONTROL, a, b]].dropna()
        if len(d) < 8:
            continue
        raw_rho = r["statistic"]["rho"]
        p_rho, p_p, n, df = partial_spearman(d[a], d[b], d[config.CONFOUND_CONTROL])
        drop_frac = None if raw_rho == 0 else (abs(raw_rho) - abs(p_rho)) / abs(raw_rho)
        attenuates = bool(drop_frac is not None and drop_frac >= config.CONFOUND_ATTENUATION_STRONG
                          and abs(p_rho) < config.CONFOUND_RESIDUAL_MIN)
        sign_flip = bool(np.sign(p_rho) != np.sign(raw_rho) and abs(p_rho) > 0.05)
        rows.append({"stat_id": r["id"], "a": a, "b": b, "n": n, "raw_rho": raw_rho, "partial_rho": p_rho,
                     "partial_p": p_p, "drop_fraction": drop_frac, "control": config.CONFOUND_CONTROL,
                     "attenuates_strongly": attenuates, "sign_flip": sign_flip})
        if attenuates:
            verdict = (f"consistent with both parameters tracking the shared {config.CONFOUND_CONTROL.replace('_', ' ')} "
                       f"gradient rather than a pairwise relationship independent of it")
        elif sign_flip:
            verdict = "sign reverses after controlling for the shared gradient - treat the raw correlation with particular caution"
        else:
            verdict = f"association persists after controlling for {config.CONFOUND_CONTROL.replace('_', ' ')}"
        text = (f"{r['id']} ({a} vs {b}, raw rho = {raw_rho:.2f}): "
                f"partial Spearman rho controlling for {config.CONFOUND_CONTROL.replace('_', ' ')} = "
                f"{p_rho:.2f} (n = {n}, p = {'n/a' if np.isnan(p_p) else f'{p_p:.3f}'}); {verdict}.")
        reg.add("CONF", "confound_check", text, parameters=[a, b], stat_ids=[r["id"]],
                detail={"raw_rho": raw_rho, "partial_rho": p_rho, "partial_p": p_p, "n": n,
                       "drop_fraction": drop_frac, "attenuates_strongly": attenuates, "sign_flip": sign_flip},
                caveats=["one control variable (transect number) only; does not rule out other shared drivers",
                        "partial correlation is still descriptive - it does not identify a mechanism"])
    df = pd.DataFrame(rows)
    ctx.save_table(df, "confounding_checks.csv")
    return reg, df
