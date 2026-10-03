"""Module 2/6 - spatial.py: station-wise, transect-wise and geographic variation.

Unit of analysis = station.  Statements describe numbers only; they never explain them.
"""
import numpy as np
import pandas as pd
from scipy import stats as sps

import config
from stats.common import (Context, benjamini_hochberg, bdl_caveat, fmt, fmt_p, pct_diff,
                          spearman_with_ci, strength, valid_series)
from stats.util import fv, pstr, sfv, skip_if_unsupported

LOW_POWER = ("3-4 stations per transect: low statistical power", )


# =============================================================== STATION-WISE
def run_station(ctx: Context) -> None:
    if skip_if_unsupported(ctx, "station", "station", "Station-wise analysis"):
        return
    dev_rows = []
    for k in ctx.keys:
        d = valid_series(ctx, k).copy()
        g = d.groupby("transect")[k]
        d["n_in_transect"] = g.transform("count")
        d["transect_mean"] = g.transform("mean")
        d = d[d["n_in_transect"] >= 2].copy()
        if d.empty:
            continue
        d["deviation"] = d[k] - d["transect_mean"]
        d["pct_deviation"] = [pct_diff(a, b) if b else np.nan for a, b in zip(d[k], d["transect_mean"])]
        for r in d.itertuples():
            dev_rows.append({"parameter": k, "station": r.station, "transect": r.transect, "value": getattr(r, k),
                             "transect_mean": r.transect_mean, "deviation": r.deviation, "pct_deviation": r.pct_deviation})
        rng = d.groupby("transect")[k].agg(["count", "min", "max"])
        rng["range"] = rng["max"] - rng["min"]
        t_big = rng["range"].idxmax()
        sub = d[d["transect"] == t_big]
        s_lo, s_hi = sub.loc[sub[k].idxmin()], sub.loc[sub[k].idxmax()]
        big = d.loc[d["deviation"].abs().idxmax()]
        stmt = (f"Within-transect ranges of {ctx.label(k)} spanned {fv(k, rng['range'].min())} to {fv(k, rng['range'].max())} "
                f"{ctx.unit(k)}; the largest was at {t_big} ({fv(k, rng.loc[t_big, 'range'])}), between {s_lo['station']} "
                f"({fv(k, s_lo[k])}) and {s_hi['station']} ({fv(k, s_hi[k])}). The largest departure from a transect mean was at "
                f"{big['station']} ({sfv(k, big['deviation'])} {ctx.unit(k)}, {fmt(big['pct_deviation'], 3)}% of that mean).")
        ctx.reg.add(k.upper(), "station", "observation", stmt, [k], stations=[big["station"], s_lo["station"], s_hi["station"]],
                    statistic={"largest_range_transect": t_big, "range_min": rng["range"].min(), "range_max": rng["range"].max(),
                               "largest_departure_station": big["station"], "largest_departure": big["deviation"],
                               "largest_departure_pct": big["pct_deviation"], "n_transects": len(rng)},
                    caveats=bdl_caveat(ctx, k) + ["departure from a 3-4 station transect mean is mechanically bounded"],
                    qc_ids=ctx.qc_ids("bdl", "outlier", parameter=k), gate_status=ctx.status("station"),
                    table="tables/station_deviation.csv", n=len(d))
    ctx.save_table(pd.DataFrame(dev_rows), "station_deviation.csv")


# ============================================================= TRANSECT-WISE
def run_transect(ctx: Context) -> None:
    if skip_if_unsupported(ctx, "transect", "transect", "Transect-wise analysis"):
        return
    summ, tests = [], []
    for k in ctx.keys:
        d = valid_series(ctx, k)
        tsum = d.groupby("transect")[k].agg(n_valid="count", mean="mean", median="median", min="min", max="max")
        tsum["range"] = tsum["max"] - tsum["min"]
        tsum["n_bdl"] = ctx.st.groupby("transect")[f"{k}__bdl"].sum().reindex(tsum.index).fillna(0).astype(int)
        for t, r in tsum.iterrows():
            summ.append({"parameter": k, "transect": t, **r.to_dict()})
        groups = {t: g[k].values for t, g in d.groupby("transect") if len(g) >= config.MIN_STATIONS_PER_TRANSECT}
        dropped = sorted(set(tsum.index) - set(groups), key=lambda s: int(s[1:]))
        if len(groups) >= 3:
            H, p = sps.kruskal(*groups.values())
            N, kk = sum(len(v) for v in groups.values()), len(groups)
            eps2 = float(np.clip((H - kk + 1) / (N - kk), 0, 1))
            tests.append({"parameter": k, "H": float(H), "df": kk - 1, "p": float(p), "epsilon2": eps2, "N": N,
                          "n_groups": kk, "dropped": dropped})
        else:
            tests.append({"parameter": k, "p": np.nan, "dropped": dropped})
    ctx.save_table(pd.DataFrame(summ), "transect_summary.csv")

    ok = [t for t in tests if not np.isnan(t["p"])]
    for t, padj in zip(ok, benjamini_hochberg([t["p"] for t in ok])):
        t["p_adj"] = float(padj)
    tsum_df = pd.DataFrame(summ)
    for t in tests:
        k = t["parameter"]
        sub = tsum_df[(tsum_df["parameter"] == k) & (tsum_df["n_valid"] >= config.MIN_STATIONS_PER_TRANSECT)]
        if sub.empty:
            continue
        hi, lo = sub.loc[sub["mean"].idxmax()], sub.loc[sub["mean"].idxmin()]
        means = (f"Transect means ranged from {fv(k, lo['mean'])} ({lo['transect']}) to {fv(k, hi['mean'])} "
                 f"({hi['transect']}) {ctx.unit(k)}, a difference of {fmt(pct_diff(hi['mean'], lo['mean']), 3)}% of the lower mean.")
        cav = list(LOW_POWER) + ["transects differ geographically, so transect and location effects cannot be separated"] + bdl_caveat(ctx, k)
        if t["dropped"]:
            cav.append(f"transects with < {config.MIN_STATIONS_PER_TRANSECT} valid stations excluded from the test: {', '.join(t['dropped'])}")
        common = dict(stations=[], caveats=cav, qc_ids=ctx.qc_ids("bdl", "consistency", parameter=k),
                      gate_status=ctx.status("transect"), table="tables/transect_summary.csv")
        if "p_adj" in t:
            sig = t["p_adj"] < config.ALPHA
            verdict = "differed among transects" if sig else "did not differ detectably among transects"
            stmt = (f"{ctx.label(k)} {verdict} (Kruskal-Wallis H = {fmt(t['H'])}, df = {t['df']}, FDR-adjusted {pstr(t['p_adj'])}, "
                    f"epsilon² = {fmt(t['epsilon2'], 2)}, N = {t['N']} stations in {t['n_groups']} transects). {means}")
            ctx.reg.add(k.upper(), "transect", "statistical_result", stmt, [k],
                        statistic={**{x: t[x] for x in ("H", "df", "p", "p_adj", "epsilon2", "N", "n_groups")},
                                   "highest_transect": hi["transect"], "lowest_transect": lo["transect"],
                                   "highest_mean": hi["mean"], "lowest_mean": lo["mean"]},
                        strength=strength(t["p_adj"], t["epsilon2"], t["N"]), n=t["N"], **common)
        else:
            ctx.reg.add(k.upper(), "transect", "observation", f"{means} (No test: fewer than 3 transects with enough valid stations.)",
                        [k], statistic={"highest_transect": hi["transect"], "lowest_transect": lo["transect"]}, **common)


# ================================================================== SPATIAL
PREDICTORS = {"latitude": ("lat", "northward", "southward", True),
              "longitude": ("lon", "eastward", "westward", True),
              "transect number": ("transect_no", "from T1 towards T9", "from T9 towards T1", False),
              "station number": ("station_no", "from S1 towards S4", "from S4 towards S1", False)}


def _moran(x, xy_km, k, n_perm, seed):
    n = len(x)
    D = np.sqrt(((xy_km[:, None, :] - xy_km[None, :, :]) ** 2).sum(-1))
    np.fill_diagonal(D, np.inf)
    nn = np.argsort(D, axis=1, kind="stable")[:, :k]
    W = np.zeros((n, n))
    W[np.arange(n)[:, None], nn] = 1.0 / k
    z = x - x.mean()
    den = float((z ** 2).sum())
    I = float(z @ W @ z / den)
    rng = np.random.default_rng(seed)
    perm = np.array([rng.permutation(n) for _ in range(n_perm)])
    zp = z[perm]
    Ip = np.einsum("pi,ij,pj->p", zp, W, zp) / den
    E = -1.0 / (n - 1)
    p = (np.sum(np.abs(Ip - E) >= abs(I - E)) + 1) / (n_perm + 1)
    return I, E, float(p)


def run_spatial(ctx: Context) -> None:
    if skip_if_unsupported(ctx, "spatial", "spatial", "Spatial analysis"):
        return
    excluded = ctx.spatial_excluded()
    st = ctx.st.copy()
    st["transect_no"] = st["transect"].map(lambda s: int(s[1:]))

    # ---- monotonic gradients (Spearman) --------------------------------------
    tests = []
    for k in ctx.keys:
        if not ctx.gate["parameters"][k]["relational_allowed"]:
            continue
        for pname, (col, *_rest, needs_coord) in PREDICTORS.items():
            d = st.dropna(subset=[k])
            if needs_coord:
                d = d[~d["station"].isin(excluded)]
            if len(d) < config.MIN_STATIONS_FOR_STATS:
                continue
            rho, p, lo, hi = spearman_with_ci(d[col].values, d[k].values)
            tests.append({"parameter": k, "predictor": pname, "n": len(d), "rho": rho, "p": p, "ci_low": lo, "ci_high": hi})
    padj = benjamini_hochberg([t["p"] for t in tests])
    for t, a in zip(tests, padj):
        t["p_adj"] = float(a)
        t["strength"] = strength(a, t["rho"], t["n"])
    ctx.save_table(pd.DataFrame(tests), "spatial_gradients.csv")

    for k in ctx.keys:
        tk = [t for t in tests if t["parameter"] == k]
        if not tk:
            continue
        sig = [t for t in tk if t["p_adj"] < config.ALPHA]
        cav = (["stations, not depth rows, are the unit; neighbouring stations are not independent (p-values optimistic)",
                f"{len(tests)} gradient tests were run; p-values are FDR-adjusted across all of them",
                "a monotonic rank association does not imply causation"] + bdl_caveat(ctx, k))
        if excluded:
            cav.append(f"latitude/longitude tests exclude stations with unconfirmed coordinates: {', '.join(excluded)}")
        if sig:
            parts = []
            for t in sorted(sig, key=lambda t: -abs(t["rho"])):
                word = "increased" if t["rho"] > 0 else "decreased"
                parts.append(f"{word} with {t['predictor']} (rho = {fmt(t['rho'], 2)}, 95% CI {fmt(t['ci_low'], 2)} to {fmt(t['ci_high'], 2)}, "
                             f"n = {t['n']}, FDR-adjusted {pstr(t['p_adj'])})")
            stmt = f"{ctx.label(k)} showed a statistically supported monotonic gradient; it " + "; ".join(parts) + "."
            top = max(sig, key=lambda t: abs(t["rho"]))
        else:
            top = max(tk, key=lambda t: abs(t["rho"]))
            stmt = (f"No statistically supported monotonic gradient of {ctx.label(k)} with latitude, longitude, transect number or "
                    f"station number (all FDR-adjusted p ≥ {config.ALPHA}); the strongest association was with {top['predictor']} "
                    f"(rho = {fmt(top['rho'], 2)}, n = {top['n']}, FDR-adjusted {pstr(top['p_adj'])}).")
        ctx.reg.add(k.upper(), "spatial", "statistical_result", stmt, [k],
                    stations=[], statistic={"tests": tk}, strength=top["strength"], caveats=cav,
                    qc_ids=ctx.qc_ids("coordinates", "bdl", parameter=k), gate_status=ctx.status("spatial"),
                    table="tables/spatial_gradients.csv", n=top["n"])

    # ---- spatial autocorrelation (Moran's I, k nearest neighbours) ------------------
    lat0, lon0 = st["lat"].mean(), st["lon"].mean()
    st["x_km"] = (st["lon"] - lon0) * 111.32 * np.cos(np.radians(lat0))
    st["y_km"] = (st["lat"] - lat0) * 110.57
    mtests = []
    for k in ctx.keys:
        if not ctx.gate["parameters"][k]["relational_allowed"]:
            continue
        d = st.dropna(subset=[k])
        d = d[~d["station"].isin(excluded)]
        if len(d) < config.MIN_STATIONS_MORAN:
            continue
        xy = d[["x_km", "y_km"]].values
        I, E, p = _moran(d[k].values, xy, config.MORAN_K, config.N_PERMUTATIONS, config.RANDOM_SEED)
        dup = int(d.duplicated(["lat", "lon"], keep=False).sum())
        mtests.append({"parameter": k, "n": len(d), "I": I, "E": E, "p": p, "stations_sharing_position": dup})
    for t, a in zip(mtests, benjamini_hochberg([t["p"] for t in mtests])):
        t["p_adj"] = float(a)
    ctx.save_table(pd.DataFrame(mtests), "spatial_autocorrelation.csv")
    for t in mtests:
        k = t["parameter"]
        clustered = t["p_adj"] < config.ALPHA and t["I"] > t["E"]
        verdict = ("stations close together had more similar values than expected by chance" if clustered else
                   "the spatial arrangement of values was not distinguishable from random" if t["p_adj"] >= config.ALPHA else
                   "neighbouring stations had less similar values than expected by chance")
        stmt = (f"Spatial autocorrelation of {ctx.label(k)} (Moran's I, {config.MORAN_K} nearest neighbours): I = {fmt(t['I'], 2)} "
                f"(expected {fmt(t['E'], 2)}), permutation {pstr(t['p'])}, FDR-adjusted {pstr(t['p_adj'])}, n = {t['n']}; {verdict}.")
        cav = ["neighbours are defined from station coordinates; stations with unconfirmed coordinates were excluded"]
        if t["stations_sharing_position"]:
            cav.append(f"{t['stations_sharing_position']} stations share an identical position with another station (distance 0 km), "
                       f"which can raise apparent clustering")
        ctx.reg.add(k.upper(), "spatial", "statistical_result", stmt, [k], statistic=t,
                    strength=strength(t["p_adj"], t["I"], t["n"]), caveats=cav + bdl_caveat(ctx, k),
                    qc_ids=ctx.qc_ids("coordinates", parameter=k), gate_status=ctx.status("spatial"),
                    table="tables/spatial_autocorrelation.csv", n=t["n"])
