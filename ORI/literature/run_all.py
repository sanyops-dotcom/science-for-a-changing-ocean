"""ORI Phase 5 - runs the literature check and writes records + a Markdown report."""
import json
from pathlib import Path

import config
from literature.match import run as match_run
from literature.store import load_store


def run_literature(knowledge_records: list, out_dir: Path, store_path: Path = None) -> dict:
    store_path = store_path or config.LITERATURE_STORE_PATH
    papers, errors = load_store(store_path)
    reg = match_run(knowledge_records, papers, config.LITERATURE_REGION_TAGS, errors)

    out = Path(out_dir) / "literature"
    out.mkdir(parents=True, exist_ok=True)
    (out / "literature_records.json").write_text(
        json.dumps({"store_path": str(store_path), "n_papers": len(papers), "n_records": len(reg.items),
                   "records": reg.items}, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "literature_report.md").write_text(build_report(reg, papers, errors, store_path), encoding="utf-8")
    return {"records": reg.items, "n_papers": len(papers), "store_errors": errors}


def build_report(reg, papers, errors, store_path) -> str:
    n_matched = sum(1 for r in reg.items if r["status"] == "MATCHED")
    n_notchecked = sum(1 for r in reg.items if r["status"] == "NOT_CHECKED")
    L = [f"# ORI - Phase 5 report: literature check",
         f"\nStore: `{store_path}`  |  Papers loaded: {len(papers)}  |  Candidates checked: {n_matched + n_notchecked}  |  "
         f"Matched: {n_matched}  |  Not checked (no matching claim in the store): {n_notchecked}",
         "\nThis layer only retrieves claims that already exist in the literature store; it never generates a "
         "citation from a paper ORI has not been shown a specific, tagged claim from. `NOT_CHECKED` means the store "
         "has no matching claim yet, not that the literature disagrees."]
    if not papers:
        L.append(f"\n**The literature store is currently empty.** Add papers to `{store_path}` (see "
                 "`input/literature/README.md`) or import Zotero metadata with `literature/zotero_csv.py`, then add "
                 "claims by hand with process/parameter/region tags.")
    if errors:
        L.append(f"\n**{len(errors)} store problem(s):**")
        for e in errors:
            L.append(f"- {e}")
    L.append("\n## Results by candidate")
    for r in reg.items:
        if r["kind"] != "literature_check":
            continue
        L.append(f"\n### {r['id']} - {r['knowledge_id']} `{r['status']}`")
        L.append(r["text"])
        for m in r["matches"]:
            L.append(f"  - {m['citation']} - {m['title']} ({m['match_strength']}): \"{m['claim']}\" [{m['source_location']}]")
        if r["caveats"]:
            L.append("- caveats: " + "; ".join(r["caveats"]))
    return "\n".join(L) + "\n"
