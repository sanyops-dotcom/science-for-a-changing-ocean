"""ORI Phase 3 - patterns.py: pattern compression.

Two kinds of pattern, both built only from Phase 2 record ids (no new numbers, no explanation):
  correlation_cluster     parameters connected by a statistically supported relational result
  anomaly_cooccurrence    a station flagged as anomalous on >=2 parameters at once (from Phase 2 STAT-ANO-*)

Each pattern carries every stat_id and confounding-check id behind it, so the writer (Phase 6)
can cite the whole chain instead of one isolated correlation.
"""
from collections import defaultdict
from typing import Dict, List

from reasoning.common import RContext, Registry


def _connected_components(edges: List[tuple]) -> List[set]:
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for a, b in edges:
        union(a, b)
    groups: Dict[str, set] = defaultdict(set)
    for node in parent:
        groups[find(node)].add(node)
    return list(groups.values())


def run(ctx: RContext, importance_df, confound_df) -> Registry:
    reg = Registry()
    score_of = dict(zip(importance_df["stat_id"], importance_df["score"]))

    # ---- correlation clusters -----------------------------------------------------
    rel = [r for r in ctx.stat_records if r["module"] == "relational" and r["level"] == "statistical_result"
           and r.get("evidence_strength") not in (None, "NONE", "n/a") and len(r["parameters"]) == 2]
    edges = [(r["parameters"][0], r["parameters"][1]) for r in rel]
    for group in _connected_components(edges):
        if len(group) < 2:
            continue
        members = sorted(group)
        pair_recs = [r for r in rel if set(r["parameters"]) <= group]
        support_ids = [r["id"] for r in pair_recs]
        # bring in transect + spatial-gradient support for the same parameters, if significant
        extra_ids = [r["id"] for r in ctx.stat_records
                    if r["module"] in ("transect", "spatial") and r["level"] == "statistical_result"
                    and r.get("evidence_strength") not in (None, "NONE", "n/a")
                    and set(r["parameters"]) & group]
        conf = confound_df[confound_df["stat_id"].isin(support_ids)] if len(confound_df) else confound_df
        n_attenuate = int(conf["attenuates_strongly"].sum()) if len(conf) else 0
        avg_score = round(sum(score_of.get(i, 0) for i in support_ids) / max(len(support_ids), 1), 1)
        param_labels = ", ".join(members)
        pair_txt = "; ".join(f"{r['parameters'][0]}-{r['parameters'][1]} (rho={r['statistic']['rho']:.2f}, {r['id']})"
                             for r in pair_recs)
        if n_attenuate == len(conf) and len(conf) > 0:
            conf_note = (f"All {len(conf)} within-cluster correlation(s) checked attenuate strongly when transect number is "
                         f"controlled for: consistent with a single shared spatial gradient rather than {len(pair_recs)} "
                         f"independent pairwise relationships.")
        elif n_attenuate:
            conf_note = f"{n_attenuate}/{len(conf)} within-cluster correlations attenuate strongly after controlling for transect number; the rest persist."
        else:
            conf_note = "Confounding check not available for this cluster (fewer than 8 stations, or no shared control variable)." if not len(conf) else \
                        "None of the within-cluster correlations attenuate after controlling for transect number."
        text = (f"{len(members)} parameters form a correlation cluster: {param_labels}. Pairwise: {pair_txt}. {conf_note}")
        reg.add("PAT", "correlation_cluster", text, parameters=members,
                stat_ids=sorted(set(support_ids + extra_ids)), detail={"n_pairs": len(pair_recs), "avg_importance": avg_score,
                                                                       "n_attenuate": n_attenuate, "n_checked": len(conf)},
                caveats=["a correlation cluster is a statistical grouping, not a proposed mechanism",
                        "membership is transitive (A-B and B-C linked means A joins the cluster even if A-C was never "
                        "itself significant) - the pairwise list above is what was actually tested"])

    # ---- anomaly co-occurrence (already computed as STAT-ANO-* in Phase 2; re-expose as patterns) ------
    for r in ctx.stat_records:
        if r["module"] != "anomaly" or r["id"].split("-")[1] != "ANO":
            continue
        stn = r["stations"][0]
        params = r["parameters"]
        qc_note = ""  # QC ids already carried on the STAT record; reasoning layer does not duplicate detection logic
        reg.add("PAT", "anomaly_cooccurrence",
                f"Station {stn} is flagged on {len(params)} parameters at once ({', '.join(params)}); see {r['id']}.",
                parameters=params, stations=[stn], stat_ids=[r["id"]],
                detail={"n_parameters": len(params)},
                caveats=["co-occurring flags may share one cause (sampling/analytical) or reflect a real local feature - "
                        "not distinguished at this layer"])
    return reg
