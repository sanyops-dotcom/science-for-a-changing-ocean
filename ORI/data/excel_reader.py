"""ORI Phase 1 - Excel reader.

Reads the Master sheet, maps columns to canonical parameters, and converts
everything into ONE normalized (tidy) table. It describes the dataset; it does
not interpret the oceanography and it never edits observations.

Outputs (ReadResult):
  long          one row per (Excel row x parameter)  - full traceability to the Excel row
  wide          parsed Master sheet, one row per Excel row (used by QC)
  station_level one row per station (shallowest-depth row)  - the unit of analysis
  manifest      dataset description (files, sheets, parameters, stations ...)
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

import config
from quality.issues import IssueLog

STATION_RE = re.compile(r"^\s*T\s*(\d+)\s*[-_ ]*\s*S\s*(\d+)\s*$", re.I)
DEPTH_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*m?\s*$", re.I)
COORD_RE = re.compile(r"^\s*(\d+)\s+(\d+(?:\.\d+)?)\s*([NSEW])\s*$", re.I)
HEADER_UNIT_RE = re.compile(r"[\[\(]([^\]\)]+)[\]\)]\s*$")


def normalise_header(h) -> str:
    """'Depth.(m)' and 'Depth (m)' become the same header."""
    return re.sub(r"\s+", " ", re.sub(r"\.+", " ", str(h))).strip()


def parse_station(s):
    m = STATION_RE.match(str(s))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def parse_depth(v) -> float:
    m = DEPTH_RE.match(str(v))
    return float(m.group(1)) if m else np.nan


def parse_coord(v) -> float:
    """'08 50.94N' (deg decimal-minutes + hemisphere) -> signed decimal degrees."""
    m = COORD_RE.match(str(v))
    if not m:
        return np.nan
    deg = int(m.group(1)) + float(m.group(2)) / 60.0
    return -deg if m.group(3).upper() in "SW" else deg


@dataclass
class ReadResult:
    path: Path
    long: pd.DataFrame
    wide: pd.DataFrame
    station_level: pd.DataFrame
    manifest: dict
    column_map: dict
    derived_sheets: Dict[str, pd.DataFrame]


def map_columns(headers: List[str], log: IssueLog) -> dict:
    """Map normalized headers to station/depth/lat/lon/parameters."""
    cmap = {"station": None, "depth": None, "lat": None, "lon": None, "params": {}, "unmapped": []}
    for h in headers:
        hl = h.lower()
        if hl.startswith("station"):
            cmap["station"] = h
        elif hl.startswith("depth"):
            cmap["depth"] = h
        elif hl.startswith("lat"):
            cmap["lat"] = h
        elif hl.startswith("lon"):
            cmap["lon"] = h
        else:
            for spec in config.PARAMETERS:
                if re.search(spec.header_pattern, hl, re.I):
                    m = HEADER_UNIT_RE.search(h)
                    cmap["params"][spec.key] = {"column": h, "header_unit": m.group(1) if m else None}
                    break
            else:
                cmap["unmapped"].append(h)
    for role in ("station", "depth", "lat", "lon"):
        if cmap[role] is None:
            log.add("ERROR", "structure", f"Required column '{role}' not found in Master sheet.")
    for key in [p.key for p in config.PARAMETERS if p.key not in cmap["params"]]:
        log.add("WARNING", "structure", f"Expected parameter '{key}' not found in Master sheet.", parameter=key)
    for h in cmap["unmapped"]:
        log.add("INFO", "structure", f"Column '{h}' is not a recognised parameter and was not analysed.")
    return cmap


def _units_match(a: Optional[str], b: str) -> bool:
    fix = lambda s: str(s).lower().replace("μ", "µ").replace(" ", "")
    return a is not None and fix(a) == fix(b)


def read_dataset(path: Path, log: IssueLog) -> ReadResult:
    path = Path(path)
    xl = pd.ExcelFile(path)
    sheets = xl.sheet_names
    if config.MASTER_SHEET not in sheets:
        raise ValueError(f"Sheet '{config.MASTER_SHEET}' not found. Sheets: {sheets}")

    raw = xl.parse(config.MASTER_SHEET, dtype=object)
    raw.columns = [normalise_header(c) for c in raw.columns]
    raw = raw.dropna(how="all").copy()
    raw["excel_row"] = raw.index + 2          # header is row 1
    cmap = map_columns([c for c in raw.columns if c != "excel_row"], log)

    # ---- parse station / depth / coordinates -----------------------------
    w = pd.DataFrame({"excel_row": raw["excel_row"].values})
    w["station"] = raw[cmap["station"]].astype(str).str.strip().str.replace(r"\s+", " ", regex=True).values
    parsed = w["station"].map(parse_station)
    w["transect_no"] = [p[0] for p in parsed]
    w["station_no"] = [p[1] for p in parsed]
    w["transect"] = w["transect_no"].map(lambda n: f"T{int(n)}" if pd.notna(n) else None)
    w["depth_m"] = raw[cmap["depth"]].map(parse_depth).values
    w["lat"] = raw[cmap["lat"]].map(parse_coord).values
    w["lon"] = raw[cmap["lon"]].map(parse_coord).values
    w["lat_raw"] = raw[cmap["lat"]].astype(str).values
    w["lon_raw"] = raw[cmap["lon"]].astype(str).values

    for label, mask in [("station name", w["transect_no"].isna()), ("depth", w["depth_m"].isna()),
                        ("latitude", w["lat"].isna()), ("longitude", w["lon"].isna())]:
        if mask.any():
            log.add("ERROR", "parsing", f"{int(mask.sum())} row(s) with unparseable {label}.",
                    stations=sorted(set(w.loc[mask, "station"])),
                    detail={"excel_rows": [int(r) for r in w.loc[mask, "excel_row"]]})

    # ---- parameters: numeric parse, BDL decision, units ------------------
    pieces = []
    for key, info in cmap["params"].items():
        spec = config.PARAM_BY_KEY[key]
        col, hunit = info["column"], info["header_unit"]
        vals = pd.to_numeric(raw[col], errors="coerce")
        nonnum = raw[col].notna() & vals.isna()
        if nonnum.any():
            log.add("ERROR", "parsing", f"{int(nonnum.sum())} non-numeric value(s) in {spec.label}.",
                    parameter=key, detail={"excel_rows": [int(r) for r in raw.loc[nonnum, 'excel_row']]})
        if spec.header_unit_is_unit:
            if hunit is None:
                log.add("WARNING", "units", f"No unit in header of {spec.label}; registry unit '{spec.unit}' used.", parameter=key)
            elif not _units_match(hunit, spec.unit):
                log.add("WARNING", "units", f"Header unit '{hunit}' differs from registry unit '{spec.unit}' for {spec.label}.", parameter=key)
        elif spec.note:
            log.add("INFO", "units", spec.note, parameter=key)

        v_raw = vals.values.astype(float)
        bdl = (v_raw <= config.BDL_MAX_VALUE) if spec.bdl_rule else np.zeros(len(v_raw), bool)
        bdl &= ~np.isnan(v_raw)
        v_an = np.where(bdl, np.nan, v_raw)
        pieces.append(pd.DataFrame({
            "obs_id": [f"R{r}-{key}" for r in w["excel_row"]],
            "excel_row": w["excel_row"].values, "station": w["station"].values,
            "transect": w["transect"].values, "station_no": w["station_no"].values,
            "depth_m": w["depth_m"].values, "lat": w["lat"].values, "lon": w["lon"].values,
            "parameter": key, "unit": spec.unit,
            "value_raw": v_raw, "value_analysis": v_an,
            "censor": np.where(bdl, "BDL", ""),
        }))
        w[key] = v_raw
    long = pd.concat(pieces, ignore_index=True)
    long = long.sort_values(["transect", "station_no", "depth_m", "parameter"], key=_natural_key,
                            kind="stable").reset_index(drop=True)

    # ---- station-level table (unit of analysis) ---------------------------
    ws = w.sort_values(["transect_no", "station_no", "depth_m"], kind="stable")
    rows = []
    for stn, g in ws.groupby("station", sort=False):
        top = g.iloc[0]
        r = {"station": stn, "transect": top["transect"], "station_no": top["station_no"],
             "lat": top["lat"], "lon": top["lon"], "n_depth_rows": len(g),
             "depths_m": "/".join(f"{d:g}" for d in g["depth_m"]), "max_depth_m": g["depth_m"].max()}
        for key in cmap["params"]:
            spec = config.PARAM_BY_KEY[key]
            v = top[key]
            is_bdl = bool(spec.bdl_rule and pd.notna(v) and v <= config.BDL_MAX_VALUE)
            r[key] = np.nan if (is_bdl or pd.isna(v)) else v
            r[f"{key}__raw"] = v
            r[f"{key}__bdl"] = is_bdl
        rows.append(r)
    station_level = pd.DataFrame(rows)
    station_level = station_level.sort_values(["transect", "station_no"], key=_natural_key).reset_index(drop=True)

    # ---- derived sheets (kept only for cross-checking) --------------------
    derived = {}
    for sh in sheets:
        if sh.startswith(config.DERIVED_SHEET_PREFIXES):
            d = xl.parse(sh, dtype=object)
            d.columns = [normalise_header(c) for c in d.columns]
            derived[sh] = d.dropna(how="all")

    manifest = build_manifest(path, sheets, raw, w, long, station_level, cmap, derived)
    return ReadResult(path, long, w, station_level, manifest, cmap, derived)


def _natural_key(col):
    """Sort 'T10' after 'T9' and keep numeric columns numeric."""
    if col.dtype == object:
        return col.map(lambda s: int(re.sub(r"\D", "", str(s)) or 0) if s is not None else 0)
    return col


def build_manifest(path, sheets, raw, w, long, st, cmap, derived) -> dict:
    params = []
    for key, info in cmap["params"].items():
        spec = config.PARAM_BY_KEY[key]
        sub = long[long["parameter"] == key]
        params.append({
            "key": key, "label": spec.label, "unit": spec.unit, "column": info["column"],
            "n_rows": int(len(sub)), "n_missing_rows": int(sub["value_raw"].isna().sum()),
            "n_bdl_rows": int((sub["censor"] == "BDL").sum()),
            "n_stations_valid": int(st[key].notna().sum()),
            "n_stations_bdl": int(st[f"{key}__bdl"].sum()),
        })
    return {
        "file": path.name,
        "sheets": sheets,
        "master_sheet": config.MASTER_SHEET,
        "derived_sheets_ignored_for_analysis": sorted(derived),
        "master_rows": int(len(raw)),
        "n_stations": int(st["station"].nunique()),
        "n_transects": int(st["transect"].nunique()),
        "transects": sorted(st["transect"].dropna().unique(), key=lambda s: int(s[1:])),
        "stations_per_transect": {t: int(n) for t, n in st.groupby("transect").size().items()},
        "depth_levels_m": sorted(float(d) for d in w["depth_m"].dropna().unique()),
        "lat_range": [float(st["lat"].min()), float(st["lat"].max())],
        "lon_range": [float(st["lon"].min()), float(st["lon"].max())],
        "date_time_column": None,
        "parameters": params,
        "unmapped_columns": cmap["unmapped"],
    }
