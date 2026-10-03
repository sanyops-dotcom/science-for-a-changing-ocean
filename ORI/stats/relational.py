"""Module 5/6 - relational.py: relationships between parameters (station level).

Spearman rank correlation with bootstrap CI, leave-one-out robustness, OLS slope/R2 as supplementary
numbers, Benjamini-Hochberg FDR across ALL tested pairs.  Correlation is never converted to causation.
"""
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats as sps

import config
from stats.common import Context, benjamini_hochberg, bdl_caveat, fmt, fmt_p, spearman_with_ci, strength
from stats.util import pstr, skip_if_unsupported


def _label(rho: float) -> str:
    a = abs(rho)
    return ("very weak" if a < 0.2 else "weak" if a < 0.4 else "moderate" if a < 0.6
            else "strong" if a < 0.8 else "very strong")


def run(ctx: Context) -> None:
    if skip_if_unsupported(ctx, "relational", "relational", "Relational analysis"):
        return
    eligible = [k for k in ctx.keys if ctx.gate["parameters"][k]["relational_allowed"]]
    tests, too_few = [], []
    for a, b in combinations(eligible, 2):
        d = ctx.st[["station", a, b]].dropna()
        if len(d) < config.MIN_STATIONS_FOR_STATS:
            too_few.append(f"{a}-{b} (n={len(d)})")
            continue
        x, y = d[a].values, d[b].values
        rho, p, lo, hi = spearman_with_ci(x, y)
        lr = sps.linregress(x, y)
        loo = [sps.spearmanr(np.delete(x, i), np.delete(y, i))[0] for i in range(len(x))]
        tests.append({"a": a, "b": b, "n": len(d), "rho": rho, "p": p, "ci_low": lo, "ci_high": hi,
                      "pearson_r": float(lr.rvalue), "ols_slope_b_per_a": float(lr.slope), "ols_r2": float(lr.rvalue ** 2),
                      "loo_rho_min": float(np.min(loo)), "loo_rho_max": float(np.max(loo)),
                      "stations": d["station"].tolist()})
    for t, adj in zip(tests, benjamini_hochberg([t["p"] for t in tests])):
        t["p_adj"] = float(adj)
        t["strength"] = strength(adj, t["rho"], t["n"])
        t["ci_excludes_0"] = bool(t["ci_low"] > 0 or t["ci_high"] < 0)
        t["loo_sign_stable"] = bool(t["loo_rho_min"] * t["loo_rho_max"] > 0)
    ctx.save_table(pd.DataFrame([{k: v for k, v in t.items() if k != "stations"} for t in tests]), "relational_pairs.csv")

    common_cav = ["stations, not depth rows, are the unit (n <= %d)" % len(ctx.st),
                  f"{len(tests)} pairs tested; p-values are FDR-adjusted across all of them",
                  "neighbouring stations are not independent (p-values optimistic)",
                  "a rank correlation does not imply causation"]
    sig = sorted([t for t in tests if t["p_adj"] < config.ALPHA], key=lambda t: -abs(t["rho"]))
    for t in sig:
        a, b = t["a"], t["b"]
        direction = "positive" if t["rho"] > 0 else "negative"
        stmt = (f"{ctx.label(a)} and {ctx.label(b)} showed a {_label(t['rho'])} {direction} rank correlation "
                f"(Spearman rho = {fmt(t['rho'], 2)}, 95% CI {fmt(t['ci_low'], 2)} to {fmt(t['ci_high'], 2)}, n = {t['n']}, "
                f"FDR-adjusted {pstr(t['p_adj'])}); leaving out any single station kept rho between "
                f"{fmt(t['loo_rho_min'], 2)} and {fmt(t['loo_rho_max'], 2)}. Linear fit: {ctx.label(b)} changed by "
                f"{fmt(t['ols_slope_b_per_a'], 3)} {ctx.unit(b)} per unit increase in {ctx.label(a)} ({ctx.unit(a)}; R² = {fmt(t['ols_r2'], 2)}).")
        cav = list(common_cav) + bdl_caveat(ctx, a) + bdl_caveat(ctx, b)
        if not t["loo_sign_stable"]:
            cav.append("sign of rho changes when single stations are left out")
        ctx.reg.add("REL", "relational", "statistical_result", stmt, [a, b], stations=[],
                    statistic={k: v for k, v in t.items() if k != "stations"},
                    strength=t["strength"] if t["loo_sign_stable"] else "WEAK", caveats=cav,
                    qc_ids=sorted(set(ctx.qc_ids("bdl", parameter=a) + ctx.qc_ids("bdl", parameter=b))),
                    gate_status=ctx.status("relational"), table="tables/relational_pairs.csv", n=t["n"])

    rest = [t for t in tests if t["p_adj"] >= config.ALPHA]
    if tests:
        strongest = max(rest, key=lambda t: abs(t["rho"])) if rest else None
        extra = (f" The strongest of these was {ctx.label(strongest['a'])} vs {ctx.label(strongest['b'])} "
                 f"(rho = {fmt(strongest['rho'], 2)}, n = {strongest['n']}, FDR-adjusted {pstr(strongest['p_adj'])})." if strongest else "")
        ctx.reg.add("REL", "relational", "statistical_result",
                    f"Of {len(tests)} parameter pairs tested, {len(sig)} showed a statistically supported rank correlation "
                    f"(FDR-adjusted p < {config.ALPHA}) and {len(rest)} did not.{extra}",
                    [], statistic={"n_pairs": len(tests), "n_supported": len(sig), "n_not_supported": len(rest)},
                    caveats=common_cav, qc_ids=ctx.qc_ids("bdl"), gate_status=ctx.status("relational"),
                    table="tables/relational_pairs.csv", n=len(ctx.st))
    excl = ctx.gate["analyses"]["relational"].get("parameters_excluded", [])
    if excl or too_few:
        ctx.reg.add("REL", "relational", "not_run",
                    "Some relationships were not tested: " + "; ".join(
                        ([f"parameters excluded by the gate ({', '.join(excl)})"] if excl else []) +
                        ([f"pairs with too few common stations ({', '.join(too_few)})"] if too_few else [])),
                    [], caveats=[], gate_status=ctx.status("relational"))
    ctx.reg.add("REL", "relational", "not_run",
                "Relationships between parameters and depth were not tested: depth carries no independent information in this file "
                "(see vertical analysis).", ["depth"], gate_status=ctx.status("vertical"),
                qc_ids=ctx.qc_ids("depth_invariance"))
