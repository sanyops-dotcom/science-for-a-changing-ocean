"""Module 6/6 - anomaly.py: statistical anomalies at station level.

This module FLAGS. It never decides whether a flag is analytical or oceanographic; that judgement needs
cross-parameter evidence and belongs to the reasoning phase.
"""
import numpy as np
import pandas as pd

import config
from stats.common import Context, fmt
from stats.util import fv, skip_if_unsupported


def run(ctx: Context) -> None:
    if skip_if_unsupported(ctx, "anomaly", "anomaly", "Anomaly detection"):
        return
    thr = config.ROBUST_Z_FLAG
    rows = []
    for k in ctx.keys:
        d = ctx.st[["station", "transect", k]].dropna()
        if len(d) < 8:
            continue
        med = float(d[k].median())
        mad = 1.4826 * float((d[k] - med).abs().median())
        if mad == 0:
            continue
        for r in d.itertuples():
            others = d[(d["transect"] == r.transect) & (d["station"] != r.station)][k]
            local = (getattr(r, k) - others.median()) / mad if len(others) >= 2 else np.nan
            z = (getattr(r, k) - med) / mad
            rows.append({"parameter": k, "station": r.station, "transect": r.transect, "value": getattr(r, k),
                         "median": med, "robust_sd": mad, "robust_z": z, "local_z": local,
                         "flag_global": abs(z) > thr, "flag_local": bool(pd.notna(local) and abs(local) > thr)})
    tab = pd.DataFrame(rows)
    ctx.save_table(tab, "anomaly_scores.csv")
    if tab.empty:
        return
    ctx.save_table(tab.pivot(index="station", columns="parameter", values="robust_z").round(2).reset_index(), "anomaly_matrix.csv")

    base_cav = ["statistical flag only: analytical vs oceanographic origin is not decided here",
                f"robust z = (value - median) / (1.4826 x MAD); flag threshold |z| > {thr:g}"]
    for k in ctx.keys:
        t = tab[tab["parameter"] == k]
        if t.empty:
            continue
        g = t[t["flag_global"]].sort_values("robust_z", key=lambda s: -s.abs())
        loc = t[t["flag_local"] & ~t["flag_global"]]
        med = float(t["median"].iloc[0])
        if len(g):
            items = ", ".join(f"{r.station} ({fv(k, r.value)} {ctx.unit(k)}, z = {fmt(r.robust_z, 3)})" for r in g.itertuples())
            stmt = (f"{len(g)} of {len(t)} stations departed strongly from the median {ctx.label(k)} ({fv(k, med)} {ctx.unit(k)}): {items}.")
        else:
            stmt = f"No station departed from the median {ctx.label(k)} ({fv(k, med)} {ctx.unit(k)}) by more than {thr:g} robust z units."
        if len(loc):
            stmt += " Departures from the rest of their own transect (but not from the dataset median): " + \
                    ", ".join(f"{r.station} (local z = {fmt(r.local_z, 3)})" for r in loc.itertuples()) + "."
        ctx.reg.add(k.upper(), "anomaly", "statistical_result", stmt, [k], stations=g["station"].tolist() + loc["station"].tolist(),
                    statistic={"median": med, "threshold": thr, "n": len(t), "n_flagged_global": len(g),
                               "flagged_global": {r.station: r.robust_z for r in g.itertuples()},
                               "flagged_local": {r.station: r.local_z for r in loc.itertuples()}},
                    caveats=base_cav + ([f"{ctx.gate['parameters'][k]['stations_bdl']} BDL stations not scored"]
                                        if ctx.gate["parameters"][k]["stations_bdl"] else []),
                    qc_ids=ctx.qc_ids("outlier", "bdl", parameter=k), gate_status=ctx.status("anomaly"),
                    table="tables/anomaly_scores.csv", n=len(t))

    # co-occurring anomalies: same station flagged for >= 2 parameters
    fl = tab[tab["flag_global"]]
    for stn, g in fl.groupby("station"):
        if g["parameter"].nunique() < 2:
            continue
        g = g.sort_values("robust_z", key=lambda s: -s.abs())
        items = ", ".join(f"{ctx.label(r.parameter)} {'above' if r.robust_z > 0 else 'below'} the median (z = {fmt(r.robust_z, 3)})"
                          for r in g.itertuples())
        qc = [r["id"] for r in ctx.qc_records if stn in r.get("stations", []) and r["category"] in
              ("coordinates", "duplicates", "impossible", "missing")]
        ctx.reg.add("ANO", "anomaly", "statistical_result",
                    f"Station {stn} was flagged for {g['parameter'].nunique()} parameters at once: {items}.",
                    list(g["parameter"]), stations=[stn],
                    statistic={"station": stn, "flags": {r.parameter: r.robust_z for r in g.itertuples()}},
                    caveats=base_cav + ["co-occurring flags may share one cause (e.g. a sampling or analytical batch)"],
                    qc_ids=sorted(set(qc + [q for p in g["parameter"] for q in ctx.qc_ids("outlier", parameter=p)])),
                    gate_status=ctx.status("anomaly"), table="tables/anomaly_scores.csv", n=int(g["parameter"].nunique()))
