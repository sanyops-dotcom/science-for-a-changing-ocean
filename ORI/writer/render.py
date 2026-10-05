"""ORI Phase 6 - render.py: the deterministic, parameter-wise writer.

No LLM is called. The text is composed almost entirely by joining statement strings already
generated (and already number-checked) by Phases 2-5. Structure follows the updated plan:
results reported PARAMETER BY PARAMETER, with numerical evidence for every parameter, a concise
line for parameters that match the literature baseline, and a detailed write-up (statistics +
candidate mechanisms + literature) for parameters that are statistically important, notable
against the baseline, or contradict the baseline.
"""
from typing import Dict, List

import config

BAND_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def _join(items):
    items = list(items)
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def _owner(params: List[str], order: List[str]) -> str:
    """Canonical single 'home' parameter for a multi-parameter record, so it appears once."""
    ranked = [p for p in order if p in params]
    return ranked[0] if ranked else (params[0] if params else "")


def _index_by_owner(records: List[dict], order: List[str], param_key=lambda r: r["parameters"]) -> Dict[str, list]:
    out: Dict[str, list] = {p: [] for p in order}
    for r in records:
        params = param_key(r)
        if not params:
            continue
        out.setdefault(_owner(params, order), []).append(r)
    return out


def render(bundle: Dict) -> str:
    d, elig = bundle["data"], bundle["eligibility"]
    order = d["parameters"]
    L = [f"# ORI Result {bundle['result_id']}\n"]

    # ---- Data Observation ---------------------------------------------------------------
    labels = [d["parameter_labels"][k] for k in order]
    L.append("## Data Observation")
    L.append(f"This result covers {d['n_stations']} stations across {d['n_transects']} transects "
             f"({_join(d['transects'])}), for {len(order)} parameters: {_join(labels)}. "
             f"Depths recorded in the source file: {_join(f'{m:g} m' for m in d['depth_levels_m'])}.")
    not_supported = [a for a, v in elig.items() if v["status"] == "NOT_SUPPORTED"]
    if not_supported:
        L.append(f"The following analyses were not performed because the data do not support them: "
                 f"{_join(not_supported)} (see the Phase 1 eligibility gate for the reason).")

    # ---- index everything by its "owner" parameter --------------------------------------
    stat_by_id = {r["id"]: r for r in bundle["statistics"]}
    imp_by_stat = {}
    for item in bundle["reasoning"]["all_importance"]:
        imp_by_stat[item["stat_ids"][0]] = item["detail"]
    know_by_owner = _index_by_owner(bundle["knowledge"], order)
    range_by_param = {i["parameters"][0]: i for i in bundle["reasoning"]["baseline_ranges"] if i["parameters"]}
    rel_by_owner = _index_by_owner(bundle["reasoning"]["baseline_relationships"], order)
    lit_by_know_id = {r["knowledge_id"]: r for r in bundle["literature"] if r["kind"] == "literature_check"}
    anomaly_by_owner = _index_by_owner([k for k in bundle["knowledge"] if k["kind"] == "anomaly_template"], order)

    # descriptive stats, one per parameter
    desc_by_param = {}
    for r in bundle["statistics"]:
        if r["module"] == "descriptive" and len(r["parameters"]) == 1 and "min" in r["statistic"]:
            desc_by_param[r["parameters"][0]] = r

    def other_stats_for(p: str, exclude_module="descriptive", min_band="MEDIUM"):
        out = []
        for r in bundle["statistics"]:
            if r["module"] == exclude_module or p not in r["parameters"]:
                continue
            imp = imp_by_stat.get(r["id"])
            if imp and BAND_ORDER.get(imp["band"], 9) <= BAND_ORDER[min_band]:
                out.append((imp["score"], r))
        out.sort(key=lambda t: -t[0])
        return out

    n_detailed = n_concise = 0

    # ---- one subsection per parameter -----------------------------------------------------
    L.append("\n## Results by Parameter")
    for p in order:
        label = d["parameter_labels"][p]
        L.append(f"\n### {label}")
        dr = desc_by_param.get(p)
        if dr:
            L.append(f"- {dr['statement']} ({dr['id']})")
        rng = range_by_param.get(p)
        if rng:
            L.append(f"- {rng['text']}")

        is_notable_baseline = bool(rng and rng["detail"]["status"] == "NOTABLE")
        contradicts = [r for r in rel_by_owner.get(p, []) if r["detail"]["status"] == "CONTRADICTS_BASELINE"]
        has_mechanism = bool(know_by_owner.get(p)) or bool(anomaly_by_owner.get(p))
        top_others = other_stats_for(p)
        detailed = is_notable_baseline or bool(contradicts) or has_mechanism or bool(top_others)

        if not detailed:
            n_concise += 1
            L.append("- No statistically important, notable, or baseline-contradicting findings for this "
                     "parameter beyond the above; treated concisely.")
            continue

        n_detailed += 1
        if top_others:
            L.append("- Statistical findings (by importance):")
            for score, r in top_others[:5]:
                L.append(f"  - {r['statement']} ({r['id']}, importance {score}/100)")
        for rr in rel_by_owner.get(p, []):
            if rr["detail"]["status"] in ("CONTRADICTS_BASELINE", "FAMILIAR"):
                L.append(f"  - Baseline check: {rr['text']}")
        for k in know_by_owner.get(p, []):
            if k["kind"] in ("pairwise", "combo"):
                L.append(f"  - Candidate mechanism: **{k['label']}** [{k['confidence']}] ({', '.join(k['stat_ids'])}): {k['description']}")
                lit = lit_by_know_id.get(k["id"])
                if lit and lit["status"] == "MATCHED":
                    top_m = lit["matches"][0]
                    L.append(f"    - Literature: {top_m['citation']} ({top_m['match_strength']}) - "
                             f"\"{top_m['claim']}\" [{top_m['source_location']}].")
                elif lit:
                    L.append("    - Literature: not yet checked against any claim in the store.")
            elif k["kind"] == "unmatched":
                L.append(f"  - {k['description']} ({', '.join(k['stat_ids'])})")
        for k in anomaly_by_owner.get(p, []):
            L.append(f"  - {k['description']}")

    L.append(f"\n{n_detailed} parameter(s) received detailed treatment (notable against the literature baseline, "
             f"contradicting an expected relationship, or statistically important); {n_concise} were concise "
             f"(consistent with the literature baseline, nothing statistically important beyond the basic range).")

    # ---- Synthesis ----------------------------------------------------------------------
    L.append("\n## Synthesis")
    n_plaus = sum(1 for k in bundle["knowledge"] if k["confidence"].startswith("CANDIDATE") and
                  "WEAK" not in k["confidence"] and "UNRANKED" not in k["confidence"])
    n_weak = sum(1 for k in bundle["knowledge"] if "WEAK" in k["confidence"] or "MIXED" in k["confidence"])
    n_matched = sum(1 for r in bundle["literature"] if r["kind"] == "literature_check" and r["status"] == "MATCHED")
    n_contra = sum(1 for r in bundle["reasoning"]["baseline_relationships"] if r["detail"]["status"] == "CONTRADICTS_BASELINE")
    # these counts are deterministic derivations of the bundle's own contents (not new facts) - stash them
    # on the bundle itself so the number-fidelity check in verify.py can find them too
    bundle["_derived_counts"] = {"n_detailed": n_detailed, "n_concise": n_concise, "n_plaus": n_plaus,
                                 "n_weak": n_weak, "n_matched": n_matched, "n_contra": n_contra}
    L.append(f"Of the statistically supported relationships in this dataset, {n_plaus} are matched to a candidate "
             f"oceanographic mechanism that held up under the spatial confounding check, and {n_weak} are matched "
             f"to a candidate mechanism that is statistically weaker once the shared transect gradient is "
             f"controlled for. {n_matched} candidate mechanism(s) currently have literature support in the store. "
             f"{n_contra} relationship(s) run opposite to the general baseline expectation from the literature "
             f"provided, which is itself a notable finding worth checking against region-specific literature rather "
             f"than a data error. None of the above should be read as a confirmed finding without further "
             f"literature review and, ideally, additional or depth-resolved sampling.")
    return "\n".join(L) + "\n"
