"""ORI Phase 3 addition - baseline.py: familiar vs new/notable classification.

Compares this dataset's observed ranges and relationships against a small baseline drawn from a
literature synthesis the user supplied (Naik et al. 2020; Kumar & Geetha 2012; Kumar et al. 2009 -
see input/literature/papers.json for the exact claims and citations). This is NOT machine learning
and nothing here is "trained" - it is a lookup table checked against Phase 2 numbers, same spirit as
the rest of ORI. Two outputs:
  - range classification per parameter: FAMILIAR / NOTABLE / NO_BASELINE
  - relationship classification per significant pair: FAMILIAR / CONTRADICTS_BASELINE / NOT_IN_BASELINE
"""
from typing import Dict, List

import config
from reasoning.common import RContext, Registry

# (parameter -> {region_tag: (min, max, unit)}); more specific regions listed first
RANGES: Dict[str, Dict[str, tuple]] = {
    "DO": {"Gulf of Mannar": (4.1, 5.6, "ml/l"), "Indian Ocean coastal": (3.0, 6.0, "ml/l")},
    "salinity": {"Gulf of Mannar": (27.0, 35.9, "psu"), "Indian Ocean coastal": (23.0, 36.0, "psu")},
    "temperature": {"Gulf of Mannar": (25.5, 32.3, "°C"), "Indian Ocean coastal": (26.0, 33.0, "°C")},
    "nitrate": {"Southeastern Arabian Sea": (4.1, 11.6, "µmol/L"), "Indian Ocean coastal": (0.89, 25.66, "µmol/L")},
    "nitrite": {"Indian Ocean coastal": (0.215, 5.99, "µmol/L")},
    "phosphate": {"Indian Ocean coastal": (0.17, 2.96, "µmol/L")},
    "silicate": {"Indian Ocean coastal": (0.89, 168.0, "µmol/L")},
    "ammonia": {"Indian Ocean coastal": (0.078, 6.81, "µmol/L")},
    # pH: no baseline given in the literature synthesis provided
}
RANGE_SOURCE = {"Gulf of Mannar": "Kumar & Geetha (2012)", "Southeastern Arabian Sea": "Kumar et al. (2009)",
               "Indian Ocean coastal": "Naik et al. (2020)"}

# known relationship direction: frozenset({a,b}) -> (expected_sign, label, source)
RELATIONSHIPS = {
    frozenset({"DO", "temperature"}): ("-", "DO-temperature (oxygen solubility decreases as water warms)", "Naik et al. (2020)"),
    frozenset({"DO", "nitrate"}): ("+", "DO-nutrient (generally positive across Indian Ocean coastal waters)", "Naik et al. (2020)"),
    frozenset({"DO", "phosphate"}): ("+", "DO-nutrient (generally positive across Indian Ocean coastal waters)", "Naik et al. (2020)"),
    frozenset({"DO", "silicate"}): ("+", "DO-nutrient (generally positive across Indian Ocean coastal waters)", "Naik et al. (2020)"),
    frozenset({"nitrate", "salinity"}): ("-", "nitrate-salinity (negative in the southeastern Arabian Sea)", "Kumar et al. (2009)"),
}


def _pick_range(param: str, region_tags: List[str]):
    table = RANGES.get(param)
    if not table:
        return None
    for r in config.BASELINE_REGION_PRIORITY:
        if r in table and (not region_tags or r in region_tags or r == "Indian Ocean coastal"):
            return r, table[r]
    return None


def classify_ranges(ctx: RContext, descriptive_records: List[dict], region_tags: List[str]) -> Registry:
    reg = Registry()
    for r in descriptive_records:
        if len(r["parameters"]) != 1 or "min" not in r["statistic"]:
            continue
        p = r["parameters"][0]
        picked = _pick_range(p, region_tags)
        if picked is None:
            reg.add("BASE", "range", f"No baseline range available for {p} in the literature provided; cannot "
                    "classify as familiar or notable.", parameters=[p], stat_ids=[r["id"]],
                    detail={"status": "NO_BASELINE"})
            continue
        region, (lo, hi, unit) = picked
        obs_lo, obs_hi = r["statistic"]["min"], r["statistic"]["max"]
        span = hi - lo
        tol = span * config.BASELINE_TOLERANCE
        within = obs_lo >= lo - tol and obs_hi <= hi + tol
        status = "FAMILIAR" if within else "NOTABLE"
        text = (f"{p}: observed {obs_lo:.3g}-{obs_hi:.3g} {unit} vs the {region} baseline {lo:g}-{hi:g} {unit} "
               f"({RANGE_SOURCE[region]}) - {status}")
        if status == "NOTABLE":
            bits = ([f"exceeds the baseline maximum"] if obs_hi > hi + tol else []) + \
                   ([f"falls below the baseline minimum"] if obs_lo < lo - tol else [])
            text += " (" + "; ".join(bits) + ")"
        text += "."
        reg.add("BASE", "range", text, parameters=[p], stat_ids=[r["id"]],
                detail={"status": status, "observed_min": obs_lo, "observed_max": obs_hi, "baseline_min": lo,
                       "baseline_max": hi, "baseline_region": region, "baseline_source": RANGE_SOURCE[region]})
    return reg


def classify_relationships(ctx: RContext, relational_records: List[dict]) -> Registry:
    reg = Registry()
    for r in relational_records:
        if r["module"] != "relational" or r["level"] != "statistical_result" or len(r["parameters"]) != 2:
            continue
        pair = frozenset(r["parameters"])
        known = RELATIONSHIPS.get(pair)
        rho = r["statistic"]["rho"]
        obs_sign = "+" if rho > 0 else "-"
        if known is None:
            reg.add("BASE", "relationship", f"{' vs '.join(r['parameters'])} (rho = {rho:.2f}): not covered by the "
                    "literature provided - not classified as familiar or new.", parameters=r["parameters"],
                    stat_ids=[r["id"]], detail={"status": "NOT_IN_BASELINE"})
            continue
        exp_sign, label, source = known
        status = "FAMILIAR" if obs_sign == exp_sign else "CONTRADICTS_BASELINE"
        text = (f"{label}: baseline expects a {'positive' if exp_sign == '+' else 'negative'} relationship "
               f"({source}); this dataset shows rho = {rho:.2f} ({r['id']}) - {status}.")
        reg.add("BASE", "relationship", text, parameters=r["parameters"], stat_ids=[r["id"]],
                detail={"status": status, "expected_sign": exp_sign, "observed_sign": obs_sign, "rho": rho,
                       "source": source})
    return reg


def run(ctx: RContext, stat_records: List[dict], region_tags: List[str]) -> Dict[str, Registry]:
    descriptive = [r for r in stat_records if r["module"] == "descriptive" and r["level"] == "observation"]
    relational = [r for r in stat_records if r["module"] == "relational"]
    return {"ranges": classify_ranges(ctx, descriptive, region_tags), "relationships": classify_relationships(ctx, relational)}
