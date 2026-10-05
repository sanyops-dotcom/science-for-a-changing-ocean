"""ORI Phase 1 - Data quality / QC.

QC detects problems; QC never silently corrects them. Every finding is an
Issue with a stable id (QC-###) so later phases can cite it.
"""
from collections import Counter
from typing import Dict

import numpy as np
import pandas as pd

import config
from data.excel_reader import ReadResult
from quality.issues import IssueLog


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def run_qc(rr: ReadResult, log: IssueLog) -> Dict:
    w, st, long = rr.wide, rr.station_level, rr.long
    keys = list(rr.column_map["params"])
    summary: Dict = {}

    _missing(rr, log, keys)
    _duplicates(w, log, keys)
    _consistency(w, st, log)
    _impossible_values(w, log, keys)
    summary["bdl"] = _bdl(st, log, keys)
    summary["depth_invariance"] = _depth_invariance(w, log, keys)
    summary["coordinates"] = _coordinates(w, st, log)
    _robust_outliers(st, log, keys)
    summary["derived_sheets"] = _derived_sheets(rr, log)
    _temporal(log)
    summary["coverage"] = _coverage(w, st, keys)
    return summary


# ---------------------------------------------------------------- checks
def _missing(rr, log, keys):
    for k in keys:
        sub = rr.long[rr.long["parameter"] == k]
        n = int(sub["value_raw"].isna().sum())
        if n:
            log.add("WARNING", "missing", f"{n} missing value(s) for {config.PARAM_BY_KEY[k].label}.",
                    stations=sorted(sub.loc[sub["value_raw"].isna(), "station"].unique()), parameter=k)
    n_all = int(rr.wide[keys].isna().all(axis=1).sum())
    if n_all:
        log.add("WARNING", "missing", f"{n_all} row(s) with no parameter values at all.")


def _duplicates(w, log, keys):
    dup = w[w.duplicated(["station", "depth_m"], keep=False)]
    if len(dup):
        log.add("ERROR", "duplicates", f"{len(dup)} rows share the same station and depth.",
                stations=sorted(dup["station"].unique()), detail={"excel_rows": [int(r) for r in dup["excel_row"]]})
    full = w[w.duplicated(["station", "depth_m"] + keys, keep=False)]
    if len(full):
        log.add("ERROR", "duplicates", f"{len(full)} rows are fully identical duplicates.",
                stations=sorted(full["station"].unique()))


def _consistency(w, st, log):
    nums = sorted(st["transect"].map(lambda s: int(s[1:])).unique())
    gaps = sorted(set(range(nums[0], nums[-1] + 1)) - set(nums))
    if gaps:
        log.add("WARNING", "consistency", f"Transect numbering has gaps: {['T%d' % g for g in gaps]}.")
    for t, g in st.groupby("transect"):
        sn = sorted(g["station_no"].astype(int))
        miss = sorted(set(range(1, sn[-1] + 1)) - set(sn))
        if miss:
            log.add("WARNING", "consistency", f"{t}: station numbers missing {miss}.", stations=[f"{t} S{m}" for m in miss])
    per = st.groupby("transect").size()
    if per.nunique() > 1:
        log.add("INFO", "consistency", "Stations per transect are not equal: " +
                ", ".join(f"{t}={n}" for t, n in per.items()) + ".")
    # depth consistency
    ordering_bad = []
    for stn, g in w.groupby("station", sort=False):
        d = g.sort_values("excel_row")["depth_m"].tolist()
        if d != sorted(d):
            ordering_bad.append(stn)
    if ordering_bad:
        log.add("WARNING", "depth", "Depth rows are not in increasing order within station.", stations=ordering_bad)
    one = st.loc[st["n_depth_rows"] == 1, "station"].tolist()
    if one:
        log.add("INFO", "depth", "Stations with a single depth row.", stations=one)
    levels = sorted(w["depth_m"].dropna().unique())
    log.add("INFO", "depth", f"Depth levels present: {[f'{d:g}' for d in levels]} m; "
            f"stations sampled at {int(st['n_depth_rows'].min())}-{int(st['n_depth_rows'].max())} levels "
            f"(max depth per station {st['max_depth_m'].min():g}-{st['max_depth_m'].max():g} m).")
    # identical parameter vectors at two different stations (possible copy error)
    keys = [c for c in st.columns if c.endswith("__raw")]
    vec = st.assign(_v=st[keys].round(6).astype(str).agg("|".join, axis=1))
    dupv = vec[vec.duplicated("_v", keep=False)]
    if len(dupv):
        log.add("WARNING", "duplicates", "Different stations have identical values for every parameter.",
                stations=sorted(dupv["station"]))


def _impossible_values(w, log, keys):
    for k in keys:
        spec = config.PARAM_BY_KEY[k]
        lo, hi = spec.hard_range
        v = w[k]
        if spec.bdl_rule:      # <= 0 is handled by the BDL rule, so only check the upper bound
            bad = v > hi
            msg = f"{spec.label} above the plausible maximum ({hi:g} {spec.unit})."
        else:
            bad = (v < lo) | (v > hi)
            msg = f"{spec.label} outside the physically plausible range ({lo:g}-{hi:g} {spec.unit})."
        if bad.any():
            log.add("ERROR", "impossible", f"{int(bad.sum())} row(s): {msg}",
                    stations=sorted(w.loc[bad, "station"].unique()), parameter=k,
                    detail={"values": sorted(set(np.round(v[bad], 4)))})


def _bdl(st, log, keys):
    out = {}
    n = len(st)
    for k in keys:
        spec = config.PARAM_BY_KEY[k]
        if not spec.bdl_rule:
            continue
        raw = st[f"{k}__raw"]
        n_zero = int((raw == 0).sum())
        n_neg = int((raw < 0).sum())
        n_bdl = int(st[f"{k}__bdl"].sum())
        frac = n_bdl / n
        out[k] = {"n_stations": n, "n_bdl": n_bdl, "n_zero": n_zero, "n_negative": n_neg,
                  "fraction_bdl": round(frac, 3), "n_valid": n - n_bdl}
        if n_bdl:
            sev = "WARNING" if frac > config.BDL_WARN_FRACTION else "INFO"
            extra = (" No correlation/regression will be run on this parameter." if frac > config.BDL_NO_RELATIONAL_FRACTION else "")
            log.add(sev, "bdl",
                    f"{spec.label}: {n_bdl}/{n} stations are below detection (value <= 0: {n_zero} zero, {n_neg} negative). "
                    f"Raw values kept; BDL values excluded from statistics, not substituted.{extra}",
                    stations=st.loc[st[f"{k}__bdl"], "station"].tolist(), parameter=k,
                    action="BDL rule applied (user decision); raw value preserved")
    return out


def _depth_invariance(w, log, keys):
    """Does any parameter change with depth inside a station?"""
    res = {"per_parameter": {}, "series_total": 0, "series_varying": 0}
    multi = [g for _, g in w.groupby("station") if len(g) >= 2]
    for k in keys:
        varying = sum(1 for g in multi if g[k].dropna().round(9).nunique() > 1)
        res["per_parameter"][k] = {"series": len(multi), "varying": varying}
        res["series_total"] += len(multi)
        res["series_varying"] += varying
    res["fraction_varying"] = round(res["series_varying"] / res["series_total"], 4) if res["series_total"] else 0.0
    if res["series_total"] and res["series_varying"] == 0:
        log.add("WARNING", "depth_invariance",
                f"Every parameter has ONE value per station, repeated on every depth row "
                f"({len(w)} rows carry only {w['station'].nunique()} independent observations). "
                f"Depth is retained as given, but no vertical structure exists in this file.",
                detail={"rows": int(len(w)), "independent_observations": int(w['station'].nunique())},
                action="depth kept as given (user decision); vertical analysis will not be supported by the eligibility gate")
    elif res["series_varying"]:
        log.add("INFO", "depth_invariance",
                f"{res['series_varying']}/{res['series_total']} station x parameter series vary with depth.")
    return res


def _coordinates(w, st, log):
    out = {"conflict_stations": [], "outlier_stations": [], "identical_across_transects": []}
    # 1. position changes inside a station
    for stn, g in w.groupby("station", sort=False):
        if g["lat"].round(5).nunique() > 1 or g["lon"].round(5).nunique() > 1:
            g = g.sort_values("depth_m")
            steps = np.diff(g["lat"].values)
            out["conflict_stations"].append(stn)
            drag = bool(len(steps) and np.allclose(steps, steps[0], atol=1e-6) and abs(steps[0]) > 0.5)
            log.add("WARNING", "coordinates",
                    f"{stn}: latitude/longitude change between depth rows of the same station "
                    f"({g['lat_raw'].iloc[0]}, {g['lon_raw'].iloc[0]} ... {g['lat_raw'].iloc[-1]}, {g['lon_raw'].iloc[-1]})."
                    + (" Pattern (+1 deg per row) looks like a spreadsheet drag-fill." if drag else ""),
                    stations=[stn], detail={"lat_raw": g["lat_raw"].tolist(), "lon_raw": g["lon_raw"].tolist()},
                    action="flagged only; shallowest-row position used provisionally, station excluded from spatial statistics until confirmed")
    # 2. station far from the rest of its own transect
    for t, g in st.groupby("transect"):
        if len(g) < 3:
            continue
        for i, r in g.iterrows():
            others = g.drop(index=i)
            mlat, mlon = others["lat"].median(), others["lon"].median()
            d = float(haversine_km(r["lat"], r["lon"], mlat, mlon))
            pair = [haversine_km(a.lat, a.lon, b.lat, b.lon) for a in others.itertuples()
                    for b in others.itertuples() if a.Index < b.Index]
            spacing = float(np.median(pair)) if pair else 0.0
            if d > config.COORD_OUTLIER_MIN_KM and d > config.COORD_OUTLIER_FACTOR * spacing:
                out["outlier_stations"].append(r["station"])
                log.add("WARNING", "coordinates",
                        f"{r['station']} lies {d:.0f} km from the other stations of {t} (typical spacing {spacing:.0f} km); "
                        f"position ({r['lat']:.3f}N, {r['lon']:.3f}E) may be a typing error.",
                        stations=[r["station"]], detail={"distance_km": round(d, 1), "spacing_km": round(spacing, 1)},
                        action="flagged only; station excluded from spatial statistics until confirmed")
    # 3. identical positions in different transects
    key = st.assign(_k=st["lat"].round(4).astype(str) + "/" + st["lon"].round(4).astype(str))
    for k, g in key.groupby("_k"):
        if g["transect"].nunique() > 1:
            out["identical_across_transects"].append(sorted(g["station"]))
    if out["identical_across_transects"]:
        groups = out["identical_across_transects"]
        log.add("INFO", "coordinates",
                f"{len(groups)} position(s) are shared by stations of different transects "
                f"(e.g. {' = '.join(groups[0])}). Fine for repeat sampling; check if it is a copied coordinate.",
                stations=sorted({s for g in groups for s in g}))
    lat_ok = st["lat"].between(-90, 90).all() and st["lon"].between(-180, 180).all()
    if not lat_ok:
        log.add("ERROR", "coordinates", "Coordinates outside valid geographic bounds.")
    return out


def _robust_outliers(st, log, keys):
    for k in keys:
        v = st[k].dropna()
        if len(v) < 8:
            continue
        med = v.median()
        mad = 1.4826 * (v - med).abs().median()
        if mad == 0:
            continue
        z = (st[k] - med) / mad
        flag = st.loc[z.abs() > config.ROBUST_Z_FLAG, ["station", k]]
        if len(flag):
            log.add("INFO", "outlier",
                    f"{config.PARAM_BY_KEY[k].label}: {len(flag)} station(s) differ strongly from the median "
                    f"(robust z > {config.ROBUST_Z_FLAG:g}). Statistical flag only - the anomaly engine decides later "
                    f"whether it is analytical or oceanographic.",
                    stations=flag["station"].tolist(), parameter=k,
                    detail={"values": {r.station: round(float(getattr(r, k)), 4) for r in flag.itertuples()},
                            "median": round(float(med), 4)})


def _row_key(vals):
    out = []
    for x in vals:
        try:
            out.append(round(float(x), 9))
        except (TypeError, ValueError):
            out.append(str(x).strip())
    return tuple(out)


def _derived_sheets(rr, log):
    """Transect_*/Station_* should be copies of Master rows. Verify - never merge them in."""
    master = pd.read_excel(rr.path, sheet_name=config.MASTER_SHEET, dtype=object).dropna(how="all")
    mc = Counter(_row_key(r) for r in master.itertuples(index=False))
    res = {}
    for prefix in config.DERIVED_SHEET_PREFIXES:
        sheets = {n: d for n, d in rr.derived_sheets.items() if n.startswith(prefix)}
        cnt, total = Counter(), 0
        for d in sheets.values():
            for r in d.itertuples(index=False):
                cnt[_row_key(r)] += 1
                total += 1
        extra = cnt - mc          # in derived sheets but not in Master
        missing = mc - cnt        # in Master but not in derived sheets
        res[prefix] = {"n_sheets": len(sheets), "n_rows": total,
                       "rows_not_in_master": sum(extra.values()), "master_rows_not_covered": sum(missing.values())}
        if extra:
            log.add("ERROR", "derived_sheets",
                    f"{sum(extra.values())} row(s) in the {prefix}* sheets are not identical to any Master row "
                    f"(values may have been edited in one place only).",
                    action="derived sheets are not used; resolve which version is correct")
        elif missing:
            log.add("INFO", "derived_sheets", f"{sum(missing.values())} Master row(s) are not present in the {prefix}* sheets.")
        else:
            log.add("INFO", "derived_sheets",
                    f"{prefix}* sheets ({len(sheets)} sheets, {total} rows) are exact copies of the Master rows. "
                    f"Ignored for analysis so nothing is counted twice.")
    return res


def _temporal(log):
    log.add("INFO", "temporal", "No date/time column in the dataset: temporal and seasonal analyses are not applicable.")


def _coverage(w, st, keys):
    cov = {"rows": int(len(w)), "stations": int(len(st)),
           "independent_observations": int(len(st)),
           "stations_by_depth_level": {f"{d:g}": int((w[w["depth_m"] == d]["station"].nunique())) for d in sorted(w["depth_m"].unique())},
           "parameters": {}}
    for k in keys:
        cov["parameters"][k] = {"stations_valid": int(st[k].notna().sum()),
                                "stations_bdl": int(st[f"{k}__bdl"].sum()),
                                "stations_missing": int(st[f"{k}__raw"].isna().sum())}
    return cov
