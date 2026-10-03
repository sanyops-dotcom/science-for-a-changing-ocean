"""ORI Phase 1 - Analysis eligibility gate.

Runs after QC and BEFORE any statistics. It decides which analyses the data can
honestly support, so later modules never produce results the design cannot back.
Every decision carries its reasons and the QC ids it depends on.
"""
from typing import Dict, List

import pandas as pd

import config
from quality.issues import IssueLog

SUPPORTED, CAVEATS, NOT_SUPPORTED = "SUPPORTED", "SUPPORTED_WITH_CAVEATS", "NOT_SUPPORTED"


def _ids(log: IssueLog, category: str, parameter: str = "") -> List[str]:
    return [i.id for i in log.issues if i.category == category and (not parameter or i.parameter == parameter)]


def evaluate(st: pd.DataFrame, qc: Dict, log: IssueLog, keys: List[str]) -> Dict:
    n = len(st)
    gate: Dict = {"unit_of_analysis": "station (shallowest-depth row; one independent observation per station)",
                  "n_independent_observations": n, "analyses": {}, "parameters": {}}
    A = gate["analyses"]

    # ---- per parameter -----------------------------------------------------
    for k in keys:
        spec = config.PARAM_BY_KEY[k]
        valid = int(st[k].notna().sum())
        bdl = int(st[f"{k}__bdl"].sum())
        frac_bdl = bdl / n
        reasons = []
        if valid < config.MIN_STATIONS_FOR_STATS:
            desc, relational = "descriptive_only", False
            reasons.append(f"only {valid} valid stations (< {config.MIN_STATIONS_FOR_STATS})")
        elif frac_bdl > config.BDL_NO_RELATIONAL_FRACTION:
            desc, relational = "descriptive_only", False
            reasons.append(f"{bdl}/{n} stations below detection (> {config.BDL_NO_RELATIONAL_FRACTION:.0%})")
        elif frac_bdl > config.BDL_WARN_FRACTION:
            desc, relational = CAVEATS, True
            reasons.append(f"{bdl}/{n} stations below detection - report as BDL, use rank-based methods")
        else:
            desc, relational = SUPPORTED, True
            if bdl:
                reasons.append(f"{bdl}/{n} stations below detection - excluded from statistics, reported as BDL")
        gate["parameters"][k] = {"label": spec.label, "unit": spec.unit, "stations_valid": valid,
                                 "stations_bdl": bdl, "fraction_bdl": round(frac_bdl, 3),
                                 "descriptive": SUPPORTED if valid >= 3 else NOT_SUPPORTED,
                                 "station_transect_spatial_relational": desc,
                                 "relational_allowed": relational, "reasons": reasons,
                                 "qc_ids": _ids(log, "bdl", k) + _ids(log, "outlier", k)}

    rel_params = [k for k in keys if gate["parameters"][k]["relational_allowed"]]
    n_pairs = len(rel_params) * (len(rel_params) - 1) // 2

    # ---- descriptive ------------------------------------------------------------
    A["descriptive"] = {"status": SUPPORTED, "n": n, "reasons": [f"{n} stations; BDL handled per parameter."],
                        "qc_ids": _ids(log, "bdl")}

    # ---- vertical -------------------------------------------------------------
    inv = qc["depth_invariance"]
    if inv["series_total"] == 0:
        A["vertical"] = {"status": NOT_SUPPORTED, "reasons": ["no station has more than one depth"], "qc_ids": []}
    elif inv["fraction_varying"] < config.VERTICAL_MIN_VARYING_FRACTION:
        A["vertical"] = {
            "status": NOT_SUPPORTED,
            "reasons": [f"{inv['series_varying']}/{inv['series_total']} station x parameter series vary with depth "
                        f"(< {config.VERTICAL_MIN_VARYING_FRACTION:.0%}): values are repeated on every depth row, "
                        f"so the file holds {n} independent observations, not {len(st) and int(st['n_depth_rows'].sum())}.",
                        "Depth is kept as given. Vertical statistics will switch on automatically if depth-resolved values are supplied."],
            "qc_ids": _ids(log, "depth_invariance")}
    else:
        A["vertical"] = {"status": CAVEATS if inv["fraction_varying"] < 0.5 else SUPPORTED,
                         "reasons": [f"{inv['fraction_varying']:.0%} of series vary with depth"],
                         "qc_ids": _ids(log, "depth_invariance")}

    # ---- station-wise -------------------------------------------------------------
    A["station"] = {"status": SUPPORTED, "n": n, "reasons": ["one value per station; no pseudo-replication if station is the unit"],
                    "qc_ids": []}

    # ---- transect-wise ------------------------------------------------------
    per = st.groupby("transect").size()
    small = per[per < config.MIN_STATIONS_PER_TRANSECT]
    low = per[(per >= config.MIN_STATIONS_PER_TRANSECT) & (per < config.LOW_POWER_STATIONS_PER_TRANSECT)]
    reasons = ["stations per transect: " + ", ".join(f"{t}={int(v)}" for t, v in per.items())]
    if len(low):
        reasons.append(f"{len(low)} transects have only {int(low.min())}-{int(low.max())} stations: "
                       f"differences are descriptive; no significance tests between single transects (low power)")
    if len(small):
        reasons.append(f"transects with < {config.MIN_STATIONS_PER_TRANSECT} stations excluded from comparison: {[str(t) for t in small.index]}")
    A["transect"] = {"status": CAVEATS if len(low) or len(small) else SUPPORTED, "reasons": reasons,
                     "transects_excluded": list(small.index), "qc_ids": _ids(log, "consistency")}

    # ---- spatial ----------------------------------------------------------------
    c = qc["coordinates"]
    flagged = sorted(set(c["conflict_stations"]) | set(c["outlier_stations"]))
    reasons = [f"{n - len(flagged)}/{n} stations have consistent coordinates"]
    if flagged:
        reasons.append(f"excluded from spatial statistics until coordinates are confirmed: {flagged}")
    A["spatial"] = {"status": CAVEATS if flagged else SUPPORTED, "stations_excluded": flagged,
                    "reasons": reasons, "qc_ids": _ids(log, "coordinates")}

    # ---- relational ---------------------------------------------------------------
    excluded = [k for k in keys if not gate["parameters"][k]["relational_allowed"]]
    reasons = [f"{len(rel_params)} parameters eligible -> {n_pairs} pairwise tests; multiple-testing correction is mandatory",
               "station is the unit (n <= %d); use Spearman with confidence intervals, report effect sizes" % n,
               "spatial autocorrelation between neighbouring stations means p-values are optimistic"]
    if excluded:
        reasons.append(f"excluded from correlation/regression: {excluded}")
    A["relational"] = {"status": CAVEATS, "n_pairs": n_pairs, "parameters_excluded": excluded, "reasons": reasons,
                       "qc_ids": _ids(log, "bdl")}

    # ---- anomaly ------------------------------------------------------------------
    A["anomaly"] = {"status": CAVEATS, "reasons": ["robust station-level outlier flags available; "
                                                    "analytical vs oceanographic decision needs cross-parameter evidence and (ideally) your metadata"],
                    "qc_ids": _ids(log, "outlier")}

    # ---- temporal -------------------------------------------------------------------
    A["temporal"] = {"status": NOT_SUPPORTED, "reasons": ["no date/time column in the dataset"],
                     "qc_ids": _ids(log, "temporal")}
    return gate
