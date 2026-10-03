"""ORI Phase 5 - match.py: connects Phase 4 candidate mechanisms to claims already in the store.

This module only RETRIEVES. It never writes a new claim, never paraphrases a paper on the fly, and
never invents a citation. If the store has nothing relevant, the result is NOT_CHECKED - an honest
gap, exactly like Phase 4's NOT ASSESSED - not a fabricated citation and not silence.

Match strength (best available match per paper):
  STRONG      claim shares BOTH a process tag with the candidate AND a region tag with config.LITERATURE_REGION_TAGS
  MECHANISTIC claim shares a process tag with the candidate, region unmatched or unset
  REGIONAL    claim shares a region tag and at least one parameter tag, but no process tag
  (no match)  nothing shared -> paper not returned for this candidate
"""
from collections import defaultdict
from typing import Dict, List

from literature.schema import Paper


class LRegistry:
    def __init__(self) -> None:
        self.items: List[dict] = []
        self._n = 0

    def add(self, kind: str, know_id: str, status: str, text: str, *, matches=None, caveats=None) -> str:
        self._n += 1
        lid = f"LIT-{self._n:03d}"
        self.items.append({"id": lid, "kind": kind, "knowledge_id": know_id, "status": status, "text": text,
                           "matches": matches or [], "caveats": caveats or []})
        return lid


def _claim_strength(claim, process_key: str, parameters: List[str], region_tags: List[str]):
    proc = process_key in claim.process_tags
    region = bool(region_tags) and bool(set(claim.region_tags) & set(region_tags))
    param = bool(set(claim.parameter_tags) & set(parameters))
    if proc and region:
        return "STRONG"
    if proc:
        return "MECHANISTIC"
    if region and param:
        return "REGIONAL"
    return None


def match_knowledge_record(k: dict, papers: List[Paper], region_tags: List[str]) -> List[dict]:
    out = []
    for p in papers:
        best = None
        for ci, c in enumerate(p.claims):
            s = _claim_strength(c, k["process_key"], k["parameters"], region_tags)
            if s and (best is None or _rank(s) > _rank(best[0])):
                best = (s, ci, c)
        if best:
            strength, ci, c = best
            out.append({"zotero_key": p.zotero_key, "citation": p.citation(), "title": p.title,
                        "claim": c.claim, "source_location": c.source_location, "match_strength": strength,
                        "claim_index": ci})
    return sorted(out, key=lambda m: -_rank(m["match_strength"]))


def _rank(s: str) -> int:
    return {"STRONG": 3, "MECHANISTIC": 2, "REGIONAL": 1}.get(s, 0)


def run(knowledge_records: List[dict], papers: List[Paper], region_tags: List[str], store_errors: List[str]) -> LRegistry:
    reg = LRegistry()
    assessable = [k for k in knowledge_records if k["kind"] in ("pairwise", "combo")]
    for k in assessable:
        matches = match_knowledge_record(k, papers, region_tags)
        if not papers:
            reg.add("literature_check", k["id"], "NOT_CHECKED",
                    f"No papers in the literature store yet - {k['id']} ({k['label']}) has not been checked against "
                    f"the literature.", caveats=["add papers to input/literature/papers.json (or import a Zotero CSV "
                    "export with literature/zotero_csv.py) and add claims with process/parameter/region tags"])
        elif matches:
            top = matches[0]
            reg.add("literature_check", k["id"], "MATCHED",
                    f"{k['id']} ({k['label']}) is supported in the literature store by {len(matches)} paper(s); "
                    f"strongest match: {top['citation']} ({top['match_strength']}) - \"{top['claim']}\" "
                    f"[{top['source_location']}].", matches=matches,
                    caveats=["a claim in the store is only as reliable as whoever entered it checked it to be - "
                            "confirm the wording against the actual paper before it goes into the final write-up (Phase 6)"])
        else:
            reg.add("literature_check", k["id"], "NOT_CHECKED",
                    f"{k['id']} ({k['label']}) does not match any claim currently in the literature store "
                    f"(checked against {len(papers)} paper(s)). This means 'not found yet', not 'contradicted'.",
                    caveats=["add a paper with matching process_tags/parameter_tags (and region_tags, to reach STRONG) "
                            "to input/literature/papers.json"])
    if store_errors:
        reg.add("store_error", "", "STORE_ERROR", f"{len(store_errors)} problem(s) in the literature store were "
                "found and those entries were skipped: " + "; ".join(store_errors[:5]) +
                (" ..." if len(store_errors) > 5 else ""))
    return reg
