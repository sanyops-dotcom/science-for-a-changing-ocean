"""Module 1/6 - descriptive statistics (station level, BDL values excluded, never substituted)."""
import numpy as np
import pandas as pd

from stats.common import Context, fmt
from stats.util import fv


def run(ctx: Context) -> None:
    N = len(ctx.st)
    rows = []
    for k in ctx.keys:
        label, unit = ctx.label(k), ctx.unit(k)
        col = ctx.st[k]
        v = col.dropna()
        n = len(v)
        n_bdl = int(ctx.st[f"{k}__bdl"].sum())
        raw = ctx.st[f"{k}__raw"]
        n_zero, n_neg = int((raw == 0).sum()), int((raw < 0).sum())
        if n < 3:
            continue
        mean, sd, med = float(v.mean()), float(v.std(ddof=1)), float(v.median())
        q1, q3 = float(v.quantile(0.25)), float(v.quantile(0.75))
        lo, hi = float(v.min()), float(v.max())
        s_lo, s_hi = ctx.st.loc[col.idxmin(), "station"], ctx.st.loc[col.idxmax(), "station"]
        cv = 100 * sd / mean if mean > 0 else np.nan
        pct = 100 * (hi - lo) / lo if lo > 0 else np.nan
        rows.append({"parameter": k, "unit": unit, "n_stations": N, "n_valid": n, "n_bdl": n_bdl,
                     "min": lo, "station_min": s_lo, "max": hi, "station_max": s_hi, "range": hi - lo,
                     "mean": mean, "median": med, "sd": sd, "cv_percent": cv, "q1": q1, "q3": q3,
                     "pct_max_over_min": pct})
        basis = f"across {n} stations" if not n_bdl else f"across the {n} stations above detection"
        stmt = (f"{label} ranged from {fv(k, lo)} to {fv(k, hi)} {unit} {basis} "
                f"(mean {fv(k, mean)} ± {fv(k, sd)} SD, median {fv(k, med)}); "
                f"the lowest value was at {s_lo} and the highest at {s_hi}.")
        caveats = []
        if n_bdl:
            caveats.append(f"{n_bdl}/{N} stations below detection are excluded from these statistics (not substituted).")
        ctx.reg.add(k.upper(), "descriptive", "observation", stmt, [k], stations=[s_lo, s_hi],
                    statistic={"n": n, "min": lo, "max": hi, "range": hi - lo, "mean": mean, "sd": sd,
                               "median": med, "q1": q1, "q3": q3, "cv_percent": cv, "pct_max_over_min": pct},
                    caveats=caveats, qc_ids=ctx.qc_ids("bdl", "outlier", parameter=k),
                    gate_status=ctx.status("descriptive"), table="tables/descriptive.csv", n=n)
        if n_bdl:
            stns = ctx.st.loc[ctx.st[f"{k}__bdl"], "station"].tolist()
            ctx.reg.add(k.upper(), "descriptive", "observation",
                        f"{label} was below detection (value ≤ 0) at {n_bdl} of {N} stations "
                        f"({n_zero} zero, {n_neg} negative values): {', '.join(stns)}.",
                        [k], stations=stns,
                        statistic={"n_bdl": n_bdl, "n_stations": N, "fraction_bdl": n_bdl / N,
                                   "n_zero": n_zero, "n_negative": n_neg},
                        qc_ids=ctx.qc_ids("bdl", parameter=k), gate_status=ctx.status("descriptive"),
                        table="tables/descriptive.csv", n=N)
    ctx.save_table(pd.DataFrame(rows), "descriptive.csv")
