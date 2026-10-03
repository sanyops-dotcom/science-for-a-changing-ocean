"""ORI Phase 3 - questions.py: question engine.

Turns each pattern into 2-4 concrete, answerable questions that point at what would be needed
to move from a statistical pattern to an oceanographic interpretation (Phase 4) or a literature
check (Phase 5). Every question cites the pattern/stat ids it comes from. No answers are given
here - this module only asks.
"""
from reasoning.common import RContext, Registry


def run(ctx: RContext, patterns_reg: Registry) -> Registry:
    reg = Registry()
    for p in patterns_reg.items:
        if p["kind"] == "correlation_cluster":
            members = p["parameters"]
            qs = [
                f"[{p['id']}] Which one or two parameters, if measured or modelled independently, would best test "
                f"whether {', '.join(members)} are responding to the same physical driver rather than to each other?",
                f"[{p['id']}] The confounding check controlled for transect number only. Would controlling directly for "
                f"latitude/longitude, or for a water-mass indicator, change the result (see {', '.join(p['stat_ids'][:3])}{'...' if len(p['stat_ids']) > 3 else ''})?",
                f"[{p['id']}] Do published studies of this region report {', '.join(members)} covarying for a known "
                f"physical reason (e.g. mixing, a river plume, a coastal gradient)? This is a literature question, not "
                f"answered by the data alone.",
            ]
            if p["detail"].get("n_attenuate", 0) == p["detail"].get("n_checked", -1) and p["detail"].get("n_checked", 0) > 0:
                qs.append(f"[{p['id']}] Since every pairwise correlation in this cluster attenuates after controlling for "
                          f"transect number, is transect number itself standing in for a real spatial gradient (e.g. "
                          f"distance from shore, depth of the shelf) that should be measured directly next time?")
        elif p["kind"] == "anomaly_cooccurrence":
            stn = p["stations"][0]
            qs = [
                f"[{p['id']}] Is there field or laboratory metadata for {stn} (sample time, storage, calibration batch, "
                f"weather) that could explain the {len(p['parameters'])} co-occurring flags analytically rather than "
                f"oceanographically?",
                f"[{p['id']}] Do neighbouring stations on the same transect as {stn} show any secondary signal in the "
                f"same parameters, even below the flagging threshold?",
                f"[{p['id']}] If {stn} is confirmed as a real (non-analytical) feature, what process would produce this "
                f"particular combination of {', '.join(p['parameters'])} moving together? This is a knowledge-engine "
                f"question, not one this layer answers.",
            ]
        else:
            continue
        reg.add("Q", "question_set", f"{len(qs)} question(s) for {p['id']}.", parameters=p["parameters"],
                stations=p.get("stations", []), stat_ids=p["stat_ids"], detail={"pattern_id": p["id"], "questions": qs})
    return reg
