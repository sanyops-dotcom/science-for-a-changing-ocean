"""ORI Phase 4 - runs the knowledge-matching engine and writes records + a Markdown report."""
import json
from pathlib import Path

from knowledge.common import KContext
from knowledge.match import run as match_run

ORDER = ["pairwise", "combo", "unmatched", "anomaly_template"]
TITLES = {"pairwise": "Pairwise candidate mechanisms", "combo": "Combined-evidence candidate mechanisms",
          "unmatched": "Statistically supported patterns with no library match yet",
          "anomaly_template": "Localized anomaly candidate explanations"}


def run_knowledge(stat_records: list, reasoning: dict, out_dir: Path) -> dict:
    out = Path(out_dir) / "knowledge"
    ctx = KContext(stat_records=stat_records, reasoning=reasoning)
    reg = match_run(ctx)
    out.mkdir(parents=True, exist_ok=True)
    (out / "knowledge_records.json").write_text(json.dumps({"n_records": len(reg.items), "records": reg.items},
                                                            indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "knowledge_report.md").write_text(build_report(reg), encoding="utf-8")
    return {"records": reg.items}


def build_report(reg) -> str:
    L = ["# ORI - Phase 4 report: oceanographic knowledge (candidate mechanisms)",
         "\nEvery entry below is a CANDIDATE explanation matched from a small, curated process library "
         "(knowledge/library.py) against Phase 2 statistical results and the Phase 3 confounding check. "
         "None of these are conclusions. Phase 5 (literature) checks each candidate against published evidence "
         "for this specific region before anything is written as a finding (Phase 6).",
         "\n## Confidence labels",
         "- `CANDIDATE - PLAUSIBLE` - the correlation behind this candidate did not attenuate when the spatial "
         "confounding check controlled for transect number",
         "- `CANDIDATE - WEAK (SPATIAL CONFOUND)` - the correlation attenuated strongly: equally consistent with a "
         "shared spatial gradient as with this specific mechanism",
         "- `CANDIDATE - PLAUSIBLE (COMBINED EVIDENCE)` / `CANDIDATE - MIXED EVIDENCE` - combined patterns built from "
         "more than one pairwise candidate",
         "- `NOT ASSESSED` - no library entry covers this statistically supported pattern yet",
         "- `CANDIDATE - UNRANKED` - two or more explanation classes fit equally; the data do not rank them"]
    for kind in ORDER:
        items = [r for r in reg.items if r["kind"] == kind]
        if not items:
            continue
        L.append(f"\n## {TITLES[kind]}")
        for r in items:
            L.append(f"\n### {r['id']} - {r['label']} `{r['confidence']}`")
            L.append(r["description"])
            if r["stat_ids"] or r["pattern_ids"]:
                L.append(f"- evidence: {', '.join(r['stat_ids'] + r['pattern_ids'])}")
            if r["caveats"]:
                L.append("- caveats: " + "; ".join(r["caveats"]))
    return "\n".join(L) + "\n"
