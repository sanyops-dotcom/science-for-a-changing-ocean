"""Human-readable QC + eligibility report (Markdown)."""
from typing import Dict

import pandas as pd

import config
from quality.issues import IssueLog


def _md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for r in df.itertuples(index=False):
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def build_report(manifest: dict, log: IssueLog, qc: Dict, gate: Dict, st: pd.DataFrame) -> str:
    c = log.counts()
    L = ["# ORI - Phase 1 report: data reading, QC and eligibility",
         f"\n**File:** `{manifest['file']}`  |  **Master rows:** {manifest['master_rows']}  |  "
         f"**Stations (independent observations):** {manifest['n_stations']}  |  **Transects:** {manifest['n_transects']}",
         f"\n**QC findings:** {c['ERROR']} errors, {c['WARNING']} warnings, {c['INFO']} info. "
         "QC flags problems; it never changes observations.",
         "\n## 1. Decisions applied",
         f"- Nutrients (nitrate, nitrite, ammonia, phosphate, silicate): values <= {config.BDL_MAX_VALUE:g} are **below detection (BDL)**. "
         "Raw values preserved; BDL excluded from statistics, not substituted.",
         "- Depth is used as given in the file.",
         "- Only the `Master` sheet is analysed. `Transect_*` and `Station_*` sheets are cross-checked, never merged.",
         "\n## 2. Analysis eligibility (what ORI may and may not do with this file)",
         f"Unit of analysis: {gate['unit_of_analysis']}.\n"]
    rows = [{"analysis": a, "status": v["status"], "why": "; ".join(v["reasons"])} for a, v in gate["analyses"].items()]
    L.append(_md_table(pd.DataFrame(rows)))
    L.append("\n## 3. Parameter coverage and BDL")
    prow = []
    for k, p in gate["parameters"].items():
        prow.append({"parameter": f"{p['label']} ({p['unit']})", "valid stations": p["stations_valid"],
                     "BDL stations": p["stations_bdl"], "% BDL": f"{p['fraction_bdl']:.0%}",
                     "correlation/regression": "yes" if p["relational_allowed"] else "no"})
    L.append(_md_table(pd.DataFrame(prow)))
    L.append("\n## 4. Findings")
    for sev in ("ERROR", "WARNING", "INFO"):
        items = [i for i in log.issues if i.severity == sev]
        if not items:
            continue
        L.append(f"\n### {sev} ({len(items)})")
        for i in items:
            stn = f" [{', '.join(i.stations[:12])}{'...' if len(i.stations) > 12 else ''}]" if i.stations else ""
            L.append(f"- **{i.id}** ({i.category}) {i.message}{stn}")
    L.append("\n## 5. Station table (unit of analysis)")
    show = st[["station", "transect", "lat", "lon", "n_depth_rows", "max_depth_m"]].copy()
    show["lat"] = show["lat"].round(3)
    show["lon"] = show["lon"].round(3)
    L.append(_md_table(show))
    return "\n".join(L) + "\n"
