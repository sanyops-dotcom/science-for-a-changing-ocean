"""ORI Phase 4 - match.py: matches the process library against statistically supported patterns.

Confidence labels (never "proven", never "likely" without a stated basis):
  CANDIDATE - PLAUSIBLE            signature matches; the underlying correlation did NOT attenuate
                                    strongly when the Phase 3 confounding check controlled for transect number
                                    (or no confounding check applies)
  CANDIDATE - WEAK (SPATIAL CONFOUND)  signature matches, but the correlation attenuated strongly:
                                    equally consistent with the two parameters just tracking the same spatial gradient
  CANDIDATE - PLAUSIBLE (COMBINED EVIDENCE)   a combo process whose required sub-patterns are ALL plausible
  CANDIDATE - MIXED EVIDENCE        a combo process where some but not all required sub-patterns are plausible
"""
from typing import Dict, List

from knowledge.common import KContext, KRegistry
from knowledge.library import LIBRARY, BY_KEY, ProcessSpec

PLAUSIBLE, WEAK_CONFOUND = "CANDIDATE - PLAUSIBLE", "CANDIDATE - WEAK (SPATIAL CONFOUND)"
COMBINED, MIXED = "CANDIDATE - PLAUSIBLE (COMBINED EVIDENCE)", "CANDIDATE - MIXED EVIDENCE"


def _sign(rho: float) -> str:
    return "+" if rho > 0 else "-"


def match_pairwise(ctx: KContext, spec: ProcessSpec):
    """Returns ('match'|'sign_mismatch', record, extra) or None if the pair was never tested."""
    pair, want_sign = spec.signature
    for r in ctx.relational():
        if frozenset(r["parameters"]) != pair:
            continue
        rho = r["statistic"]["rho"]
        if _sign(rho) != want_sign:
            return ("sign_mismatch", r, None)
        conf = ctx.confounding_for(*r["parameters"])
        weak = bool(conf and conf["detail"]["attenuates_strongly"])
        return ("match", r, (WEAK_CONFOUND if weak else PLAUSIBLE, conf))
    return None


def run(ctx: KContext) -> KRegistry:
    reg = KRegistry()
    fired: Dict[str, dict] = {}       # process_key -> {"confidence", "stat_id", "kid"}

    # ---- simple pairwise specs -------------------------------------------------
    for spec in LIBRARY:
        if spec.signature is None:
            continue
        result = match_pairwise(ctx, spec)
        if result is None:
            continue
        status, r, extra = result
        if status == "sign_mismatch":
            continue
        confidence, conf = extra
        cav = ["candidate explanation only - not distinguished from other explanations with the same statistical signature",
              "requires literature confirmation for this specific region (Phase 5)"]
        if confidence == WEAK_CONFOUND:
            cav.append(f"the underlying correlation ({r['id']}) attenuates strongly once transect number is "
                       f"controlled for ({conf['id']}): equally consistent with both parameters simply tracking the "
                       f"same spatial gradient as with this specific mechanism")
        kid = reg.add("pairwise", spec.key, spec.label, confidence, spec.description, parameters=list(spec.signature[0]),
                     stat_ids=[r["id"]] + ([conf["id"]] if conf else []), caveats=cav,
                     detail={"rho": r["statistic"]["rho"], "n": r["n"],
                            "partial_rho": conf["detail"]["partial_rho"] if conf else None})
        fired[spec.key] = {"confidence": confidence, "stat_id": r["id"], "kid": kid}

    # ---- combo specs (require every member key to have fired) -----------------
    for spec in LIBRARY:
        if not spec.requires:
            continue
        members = [fired.get(k) for k in spec.requires]
        if any(m is None for m in members):
            continue
        all_plausible = all(m["confidence"] == PLAUSIBLE for m in members)
        confidence = COMBINED if all_plausible else MIXED
        member_labels = [BY_KEY[k].label for k in spec.requires]
        params = sorted({p for k in spec.requires for p in BY_KEY[k].signature[0]})
        cav = [f"built from {len(spec.requires)} pairwise candidates: " + "; ".join(member_labels),
              "candidate explanation only - requires literature confirmation for this specific region (Phase 5)"]
        if confidence == MIXED:
            cav.append("not all supporting correlations survive the spatial confounding check - treat with extra caution")
        reg.add("combo", spec.key, spec.label, confidence, spec.description, parameters=params,
                stat_ids=sorted({m["stat_id"] for m in members}), caveats=cav,
                detail={"member_keys": list(spec.requires), "member_confidences": [m["confidence"] for m in members]})

    # ---- relational results with NO library match (traceability of gaps) -----------------
    matched_stat_ids = {sid for item in reg.items for sid in item["stat_ids"]}
    for r in ctx.relational():
        if r["id"] in matched_stat_ids:
            continue
        reg.add("unmatched", "none", f"No candidate mechanism in the library for {' vs '.join(r['parameters'])}",
                "NOT ASSESSED", "This statistically supported relationship does not match any process currently in "
                "the knowledge library. It is not rejected - the library is intentionally small and will grow; a gap "
                "here means 'not yet assessed', not 'no plausible mechanism exists'.",
                parameters=r["parameters"], stat_ids=[r["id"]],
                caveats=["extend knowledge/library.py to cover this pattern, or wait for a literature match in Phase 5"])

    # ---- anomaly co-occurrence patterns: candidate explanation TEMPLATE, not a process match --------
    for p in ctx.patterns("anomaly_cooccurrence"):
        stn = p["stations"][0]
        reg.add("anomaly_template", "anomaly_local_vs_analytical", "Localized event vs analytical artifact",
                "CANDIDATE - UNRANKED",
                (f"Two explanation classes are both consistent with {stn} being flagged on {len(p['parameters'])} "
                 f"parameters at once ({', '.join(p['parameters'])}): (1) a genuine, spatially localized "
                 f"oceanographic or biogeochemical event at this station: (2) an analytical or sampling artifact "
                 f"affecting the same batch of measurements. The statistics here cannot rank these two explanations "
                 f"against each other; see the questions raised for this pattern in Phase 3."),
                parameters=p["parameters"], stations=[stn], stat_ids=p["stat_ids"], pattern_ids=[p["id"]],
                caveats=["cannot be ranked from this dataset alone - needs field/lab metadata or literature context"])
    return reg
