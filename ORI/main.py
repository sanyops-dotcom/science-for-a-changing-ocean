"""ORI - Oceanic Research Intelligence.  Phase 1: data foundation.

    python main.py                      # uses input/data/Master_file_ORI.xlsx
    python main.py --file path/to.xlsx

Pipeline:  Excel -> normalized table -> QC -> eligibility gate -> outputs
"""
import argparse
import json
from pathlib import Path

import numpy as np

import config
from data.excel_reader import read_dataset
from quality.data_quality import run_qc
from quality.eligibility import evaluate
from quality.issues import IssueLog
from quality.report import build_report
from stats.run_all import run_statistics
from reasoning.run_all import run_reasoning
from knowledge.run_all import run_knowledge
from literature.run_all import run_literature
from writer.run_all import run_writer


class _Enc(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return None if np.isnan(o) else float(o)
        if isinstance(o, (np.bool_,)):
            return bool(o)
        return super().default(o)


def dump(obj, path: Path):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, cls=_Enc), encoding="utf-8")


def run(file: Path, out: Path, do_stats: bool = True) -> dict:
    (out / "data").mkdir(parents=True, exist_ok=True)
    (out / "qc").mkdir(parents=True, exist_ok=True)

    log = IssueLog()
    rr = read_dataset(file, log)
    qc = run_qc(rr, log)
    keys = list(rr.column_map["params"])
    gate = evaluate(rr.station_level, qc, log, keys)

    # normalized data (raw values always preserved next to analysis values)
    rr.long.to_csv(out / "data" / "normalized_long.csv", index=False)
    rr.station_level.to_csv(out / "data" / "station_level.csv", index=False)
    dump(rr.manifest, out / "data" / "dataset_manifest.json")

    # QC + eligibility
    dump({"counts": log.counts(), "issues": log.to_records(), "summary": qc}, out / "qc" / "qc_report.json")
    dump(gate, out / "qc" / "eligibility.json")
    (out / "qc" / "qc_report.md").write_text(build_report(rr.manifest, log, qc, gate, rr.station_level), encoding="utf-8")
    reg = run_statistics(rr, log, qc, gate, out) if do_stats else None
    reasoning = run_reasoning(rr.station_level, gate, reg.items, out) if (do_stats and reg is not None) else None
    knowledge = run_knowledge(reg.items, reasoning, out) if (do_stats and reasoning is not None) else None
    literature = run_literature(knowledge["records"], out) if knowledge is not None else None
    writer = (run_writer(rr.manifest, gate, reg.items, reasoning, knowledge, literature, out)
             if literature is not None else None)
    return {"manifest": rr.manifest, "log": log, "qc": qc, "gate": gate, "stats": reg, "reasoning": reasoning,
           "knowledge": knowledge, "literature": literature, "writer": writer}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(config.INPUT_DATA_DIR / config.DEFAULT_FILE))
    ap.add_argument("--out", default=str(config.OUTPUT_DIR))
    ap.add_argument("--no-stats", action="store_true", help="stop after QC + eligibility gate")
    a = ap.parse_args()
    res = run(Path(a.file), Path(a.out), do_stats=not a.no_stats)
    c = res["log"].counts()
    print(f"Read {res['manifest']['master_rows']} rows -> {res['manifest']['n_stations']} stations, "
          f"{res['manifest']['n_transects']} transects")
    print(f"QC: {c['ERROR']} errors, {c['WARNING']} warnings, {c['INFO']} info")
    for name, v in res["gate"]["analyses"].items():
        print(f"  {name:<12} {v['status']}")
    if res["stats"] is not None:
        from collections import Counter
        cnt = Counter(i["module"] for i in res["stats"].items)
        print("Statistics: " + ", ".join(f"{m}={n}" for m, n in cnt.items()) + f"  (total {len(res['stats'].items)})")
    if res["reasoning"] is not None:
        r = res["reasoning"]
        print(f"Reasoning: importance={len(r['importance'])} confounding={len(r['confounding'])} "
              f"patterns={len(r['patterns'])} questions={len(r['questions'])}")
    if res["knowledge"] is not None:
        from collections import Counter
        cnt = Counter(i["confidence"] for i in res["knowledge"]["records"])
        print("Knowledge: " + ", ".join(f"{k}={v}" for k, v in cnt.items()) + f"  (total {len(res['knowledge']['records'])})")
    if res["literature"] is not None:
        from collections import Counter
        li = res["literature"]
        cnt = Counter(i["status"] for i in li["records"] if i["kind"] == "literature_check")
        print(f"Literature: papers={li['n_papers']} " + ", ".join(f"{k}={v}" for k, v in cnt.items()))
    if res["writer"] is not None:
        w = res["writer"]
        print(f"Writer: shipped={w['shipped']} violations={len(w['violations'])}")
    print(f"Outputs written to {a.out}")
