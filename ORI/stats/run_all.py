"""ORI Phase 2 - runs the six statistical modules and writes records, tables and a report."""
import csv
import json
from pathlib import Path

import pandas as pd

from stats import anomaly, descriptive, relational, spatial, temporal, vertical
from stats.common import Context, Registry

ORDER = ["descriptive", "station", "transect", "spatial", "vertical", "temporal", "relational", "anomaly"]
TITLES = {"descriptive": "Descriptive", "station": "Station-wise", "transect": "Transect-wise", "spatial": "Spatial",
          "vertical": "Vertical", "temporal": "Temporal", "relational": "Relationships", "anomaly": "Anomalies"}


def run_statistics(rr, log, qc, gate, out_dir: Path) -> Registry:
    out = Path(out_dir) / "stats"
    ctx = Context(st=rr.station_level, long=rr.long, gate=gate, qc=qc, qc_records=log.to_records(),
                  keys=list(rr.column_map["params"]), tables_dir=out / "tables")
    ctx.reg = Registry()
    descriptive.run(ctx)
    spatial.run_station(ctx)
    spatial.run_transect(ctx)
    spatial.run_spatial(ctx)
    vertical.run(ctx)
    temporal.run(ctx)
    relational.run(ctx)
    anomaly.run(ctx)

    out.mkdir(parents=True, exist_ok=True)
    (out / "stat_records.json").write_text(json.dumps({"n_records": len(ctx.reg.items), "records": ctx.reg.items},
                                                      indent=2, ensure_ascii=False), encoding="utf-8")
    with open(out / "stat_records.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "module", "level", "parameters", "n", "evidence_strength", "gate_status", "qc_ids", "statement"])
        for i in ctx.reg.items:
            w.writerow([i["id"], i["module"], i["level"], "|".join(i["parameters"]), i["n"], i["evidence_strength"],
                        i["gate_status"], "|".join(i["qc_ids"]), i["statement"]])
    (out / "stats_report.md").write_text(build_report(ctx), encoding="utf-8")
    return ctx.reg


def build_report(ctx: Context) -> str:
    items = ctx.reg.items
    L = ["# ORI - Phase 2 report: statistical results",
         f"\n**{len(items)} statistical records** from {len(ctx.st)} stations (unit of analysis). "
         "Every record has an id (STAT-...), the exact numbers, caveats, the QC findings that affect it and the gate status. "
         "Records describe what the numbers show; they contain no oceanographic explanation.\n",
         "## 1. What ran"]
    rows = []
    for m in ORDER:
        recs = ctx.reg.by_module(m)
        status = ctx.gate["analyses"].get(m, {}).get("status", "-")
        ran = sum(1 for r in recs if r["level"] != "not_run")
        rows.append(f"| {TITLES[m]} | {status} | {ran} | {len(recs) - ran} |")
    L += ["| module | gate status | records | not run |", "|---|---|---|---|"] + rows
    L.append("\n## 2. Records by module")
    for m in ORDER:
        recs = ctx.reg.by_module(m)
        if not recs:
            continue
        L.append(f"\n### {TITLES[m]}")
        for r in recs:
            tag = "" if r["evidence_strength"] in ("n/a", None) else f" `{r['evidence_strength']}`"
            L.append(f"- **{r['id']}**{tag} {r['statement']}")
            if r["caveats"]:
                L.append(f"  - caveats: {'; '.join(r['caveats'][:3])}{' ...' if len(r['caveats']) > 3 else ''}")
    L.append("\n## 3. Tables written (output/stats/tables/)")
    for p in sorted((ctx.tables_dir).glob("*.csv")):
        L.append(f"- `{p.name}` ({len(pd.read_csv(p))} rows)")
    return "\n".join(L) + "\n"
