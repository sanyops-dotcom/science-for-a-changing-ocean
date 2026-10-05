"""ORI Phase 2 - shared machinery for the statistical modules.

Every module emits the SAME record type (a "statement"):

    id            STAT-DO-003            stable id, cited later by the evidence ledger
    module        descriptive | station | transect | spatial | vertical | temporal | relational | anomaly
    level         observation | statistical_result | not_run
    statement     plain-language sentence containing only numbers computed here
    parameters    ["DO", "depth"]
    stations      stations the statement is about
    statistic     dict of the exact numbers (rho, ci, p, p_adj, n ...)
    evidence_strength   STRONG | MODERATE | WEAK | NONE | n/a
    caveats       list of strings (BDL, low n, spatial autocorrelation ...)
    qc_ids        QC findings that affect this statement
    gate_status   status of this analysis in the eligibility gate
    table         CSV file holding the full numbers

Rule for this layer: describe what the numbers show, never why the ocean behaves so.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats as sps

import config


# ----------------------------------------------------------------- context
@dataclass
class Context:
    st: pd.DataFrame            # station-level table (one row per station)
    long: pd.DataFrame          # normalized long table (all depth rows)
    gate: dict                  # eligibility gate
    qc: dict                    # QC summary
    qc_records: List[dict]      # QC issues
    keys: List[str]             # parameter keys present
    tables_dir: Path
    reg: "Registry" = None

    def label(self, k: str) -> str:
        return config.PARAM_BY_KEY[k].label if k in config.PARAM_BY_KEY else k

    def unit(self, k: str) -> str:
        return config.PARAM_BY_KEY[k].unit if k in config.PARAM_BY_KEY else ""

    def status(self, analysis: str) -> str:
        return self.gate["analyses"][analysis]["status"]

    def qc_ids(self, *categories: str, parameter: str = "") -> List[str]:
        return [r["id"] for r in self.qc_records
                if r["category"] in categories and (not parameter or r["parameter"] in ("", parameter))]

    def spatial_excluded(self) -> List[str]:
        return list(self.gate["analyses"]["spatial"].get("stations_excluded", []))

    def save_table(self, df: pd.DataFrame, name: str) -> str:
        self.tables_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(self.tables_dir / name, index=False)
        return f"tables/{name}"


# ------------------------------------------------------------ registry
class Registry:
    def __init__(self) -> None:
        self.items: List[dict] = []
        self._count: Dict[str, int] = defaultdict(int)

    def add(self, prefix: str, module: str, level: str, statement: str, parameters: List[str],
            statistic: Optional[dict] = None, stations: Optional[List[str]] = None,
            strength: str = "n/a", caveats: Optional[List[str]] = None, qc_ids: Optional[List[str]] = None,
            gate_status: str = "", table: str = "", n: Optional[int] = None) -> str:
        self._count[prefix] += 1
        sid = f"STAT-{prefix}-{self._count[prefix]:03d}"
        self.items.append({
            "id": sid, "module": module, "level": level, "statement": statement,
            "parameters": parameters, "stations": stations or [], "n": n,
            "statistic": _clean(statistic or {}), "evidence_strength": strength,
            "caveats": caveats or [], "qc_ids": qc_ids or [], "gate_status": gate_status, "table": table})
        return sid

    def by_module(self, module: str) -> List[dict]:
        return [i for i in self.items if i["module"] == module]


def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


# ---------------------------------------------------------------- formatting
def fmt(x, sig: int = 4) -> str:
    """Compact number formatting used inside statements."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    x = float(x)
    if x == 0:
        return "0"
    if abs(x) >= 1e-3 and abs(x) < 1e5:
        return f"{x:.{sig}g}"
    return f"{x:.2e}"


def fmt_p(p) -> str:
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return "n/a"
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def pct_diff(a: float, b: float) -> Optional[float]:
    """Percent difference of a relative to b (None when b == 0)."""
    return None if b == 0 else 100.0 * (a - b) / abs(b)


# ------------------------------------------------------------------ statistics
def benjamini_hochberg(p) -> np.ndarray:
    p = np.asarray(p, dtype=float)
    n = len(p)
    if n == 0:
        return p
    order = np.argsort(p)
    ranked = p[order] * n / np.arange(1, n + 1)
    adj = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.clip(adj, 0, 1)
    return out


def spearman_with_ci(x, y, seed: int = config.RANDOM_SEED, n_boot: int = config.N_BOOTSTRAP):
    """Spearman rho, p-value and percentile-bootstrap CI (pairs resampled)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    n = len(x)
    rho, p = sps.spearmanr(x, y)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    rx = sps.rankdata(x[idx], axis=1)
    ry = sps.rankdata(y[idx], axis=1)
    rx -= rx.mean(axis=1, keepdims=True)
    ry -= ry.mean(axis=1, keepdims=True)
    den = np.sqrt((rx ** 2).sum(1) * (ry ** 2).sum(1))
    with np.errstate(invalid="ignore", divide="ignore"):
        r = (rx * ry).sum(1) / den
    r = r[np.isfinite(r)]
    lo, hi = np.percentile(r, [(1 - config.CI_LEVEL) / 2 * 100, (1 + config.CI_LEVEL) / 2 * 100]) if len(r) else (np.nan, np.nan)
    return float(rho), float(p), float(lo), float(hi)


def strength(p_adj: float, effect: float, n: int) -> str:
    """Statistical evidence strength (NOT oceanographic importance)."""
    if p_adj is None or np.isnan(p_adj) or np.isnan(effect):
        return "NONE"
    e = abs(effect)
    if p_adj < config.ALPHA and e >= config.STRONG_EFFECT and n >= 20:
        return "STRONG"
    if p_adj < config.ALPHA and e >= config.MODERATE_EFFECT:
        return "MODERATE"
    if p_adj < config.ALPHA:
        return "WEAK"
    return "NONE"


def bdl_caveat(ctx: Context, key: str) -> List[str]:
    p = ctx.gate["parameters"].get(key)
    if p and p["stations_bdl"]:
        return [f"{ctx.label(key)}: {p['stations_bdl']}/{ctx.gate['n_independent_observations']} stations below detection "
                f"and excluded (results describe detected stations only)."]
    return []


def valid_series(ctx: Context, key: str, exclude: Optional[List[str]] = None) -> pd.DataFrame:
    """Stations with a valid (non-BDL, non-missing) value for `key`."""
    d = ctx.st[["station", "transect", "lat", "lon", key]].dropna(subset=[key])
    if exclude:
        d = d[~d["station"].isin(exclude)]
    return d


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))
