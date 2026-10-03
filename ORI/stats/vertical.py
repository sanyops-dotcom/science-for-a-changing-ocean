"""Module 3/6 - vertical.py.

Runs ONLY when the eligibility gate says depth carries independent information.
For the current Master file the gate says NOT_SUPPORTED (every parameter has one value per
station repeated on each depth row), so a `not_run` record is written instead of numbers.
The code path below activates automatically once depth-resolved values are supplied.
"""
import numpy as np
import pandas as pd
from scipy import stats as sps

import config
from stats.common import Context, benjamini_hochberg, bdl_caveat, fmt, fmt_p, strength
from stats.util import fv, pstr, sfv, skip_if_unsupported


def run(ctx: Context) -> None:
    if skip_if_unsupported(ctx, "vertical", "vertical", "Vertical analysis"):
        return
    rows, summaries = [], []
    for k in ctx.keys:
        d = ctx.long[ctx.long["parameter"] == k][["station", "transect", "depth_m", "value_analysis"]].dropna()
        for stn, g in d.groupby("station"):
            g = g.sort_values("depth_m")
            if g["depth_m"].nunique() < 2:
                continue
            top, bot = g.iloc[0], g.iloc[-1]
            slope = sps.linregress(g["depth_m"], g["value_analysis"]).slope if g["depth_m"].nunique() >= 3 else np.nan
            steps = np.abs(np.diff(g["value_analysis"].values) / np.diff(g["depth_m"].values))
            j = int(np.argmax(steps)) if len(steps) else 0
            rows.append({"parameter": k, "station": stn, "transect": top["transect"], "depth_top": top["depth_m"],
                         "depth_bottom": bot["depth_m"], "value_top": top["value_analysis"], "value_bottom": bot["value_analysis"],
                         "change": bot["value_analysis"] - top["value_analysis"],
                         "pct_change": 100 * (bot["value_analysis"] - top["value_analysis"]) / top["value_analysis"]
                         if top["value_analysis"] else np.nan,
                         "slope_per_m": slope, "max_gradient_per_m": float(steps.max()) if len(steps) else np.nan,
                         "max_gradient_between_m": f"{g['depth_m'].iloc[j]:g}-{g['depth_m'].iloc[j + 1]:g}" if len(steps) else ""})
    tab = pd.DataFrame(rows)
    ctx.save_table(tab, "vertical_profiles.csv")
    tests = []
    for k in ctx.keys:
        t = tab[tab["parameter"] == k] if len(tab) else tab
        if len(t) < 6:
            continue
        p = sps.wilcoxon(t["change"]).pvalue if (t["change"] != 0).any() else 1.0
        tests.append({"parameter": k, "n": len(t), "p": float(p), "median_change": float(t["change"].median()),
                      "median_pct": float(t["pct_change"].median()), "share_negative": float((t["change"] < 0).mean()),
                      "share_positive": float((t["change"] > 0).mean())})
    for x, a in zip(tests, benjamini_hochberg([x["p"] for x in tests])):
        x["p_adj"] = float(a)
        k = x["parameter"]
        consistent = max(x["share_negative"], x["share_positive"])
        direction = "decreased" if x["median_change"] < 0 else "increased"
        stmt = (f"{ctx.label(k)} {direction} from the shallowest to the deepest sample at {consistent:.0%} of {x['n']} stations "
                f"(median change {sfv(k, x['median_change'])} {ctx.unit(k)}, {fmt(x['median_pct'], 3)}%; Wilcoxon signed-rank "
                f"FDR-adjusted {pstr(x['p_adj'])}).")
        ctx.reg.add(k.upper(), "vertical", "statistical_result", stmt, [k, "depth"], statistic=x,
                    strength=strength(x["p_adj"], abs(x["share_negative"] - x["share_positive"]), x["n"]),
                    caveats=bdl_caveat(ctx, k) + ["stations differ in maximum sampled depth"],
                    qc_ids=ctx.qc_ids("depth", "depth_invariance"), gate_status=ctx.status("vertical"),
                    table="tables/vertical_profiles.csv", n=x["n"])
    ctx.save_table(pd.DataFrame(tests), "vertical_summary.csv")

