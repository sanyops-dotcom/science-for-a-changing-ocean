"""ORI Phase 6 - bundle.py: assembles the ONE evidence bundle the writer is allowed to use.

This is the traceability object your original plan described in section 10 (ORI RESULT ID,
DATA / STATISTICS / KNOWLEDGE / LITERATURE / SYNTHESIS). Nothing is summarized or trimmed here -
every field from Phases 1-5 that could end up in the final paragraph is carried through unchanged,
so a number in the paragraph can always be traced back to the exact record it came from.
"""
from pathlib import Path
from typing import Dict


def build_bundle(manifest: dict, gate: dict, stat_records: list, reasoning: dict, knowledge: dict,
                 literature: dict) -> Dict:
    result_id = f"ORI-{Path(manifest['file']).stem}-001"
    # keep every level (statistical_result, observation, not_run) - descriptive/observation records
    # carry the per-parameter min/max ranges the parameter-wise writer needs; filtering them out here
    # was a bug that silently dropped every descriptive number from the bundle
    stat_results = list(stat_records)
    not_run = [r for r in stat_records if r["level"] == "not_run"]
    top_importance = sorted(reasoning["importance"], key=lambda i: -i["detail"]["score"])[:10]
    return {
        "result_id": result_id,
        "data": {
            "file": manifest["file"], "n_stations": manifest["n_stations"], "n_transects": manifest["n_transects"],
            "transects": manifest["transects"], "parameters": [p["key"] for p in manifest["parameters"]],
            "parameter_labels": {p["key"]: p["label"] for p in manifest["parameters"]},
            "parameter_units": {p["key"]: p["unit"] for p in manifest["parameters"]},
            "depth_levels_m": manifest["depth_levels_m"], "lat_range": manifest["lat_range"],
            "lon_range": manifest["lon_range"],
        },
        "eligibility": gate["analyses"],
        "statistics": stat_results,
        "statistics_not_run": not_run,
        "reasoning": {"top_importance": top_importance, "all_importance": reasoning["importance"],
                     "confounding": reasoning["confounding"], "patterns": reasoning["patterns"],
                     "questions": reasoning["questions"], "baseline_ranges": reasoning["baseline_ranges"],
                     "baseline_relationships": reasoning["baseline_relationships"]},
        "knowledge": knowledge["records"],
        "literature": literature["records"],
        "literature_n_papers": literature["n_papers"],
    }
