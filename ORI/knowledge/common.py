"""ORI Phase 4 - shared context. Reads Phase 2 (statistical) and Phase 3 (reasoning) records only."""
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List

import numpy as np


@dataclass
class KContext:
    stat_records: List[dict]
    reasoning: dict   # {"importance": [...], "confounding": [...], "patterns": [...], "questions": [...]}

    def __post_init__(self):
        self._stat_idx = {r["id"]: r for r in self.stat_records}
        self._conf_idx = {(tuple(sorted(c["parameters"]))): c for c in self.reasoning["confounding"]}

    def stat(self, sid: str) -> dict:
        return self._stat_idx[sid]

    def relational(self) -> List[dict]:
        return [r for r in self.stat_records if r["module"] == "relational" and r["level"] == "statistical_result"
               and r.get("evidence_strength") not in (None, "NONE", "n/a") and len(r["parameters"]) == 2]

    def confounding_for(self, a: str, b: str) -> dict:
        return self._conf_idx.get(tuple(sorted((a, b))))

    def patterns(self, kind: str = None) -> List[dict]:
        return [p for p in self.reasoning["patterns"] if kind is None or p["kind"] == kind]


class KRegistry:
    def __init__(self) -> None:
        self.items: List[dict] = []
        self._n = 0

    def add(self, kind: str, key: str, label: str, confidence: str, description: str, *, parameters=None,
            stations=None, stat_ids=None, pattern_ids=None, caveats=None, detail=None) -> str:
        self._n += 1
        kid = f"KNOW-{self._n:03d}"
        self.items.append({"id": kid, "kind": kind, "process_key": key, "label": label, "confidence": confidence,
                           "description": description, "parameters": parameters or [], "stations": stations or [],
                           "stat_ids": stat_ids or [], "pattern_ids": pattern_ids or [], "caveats": caveats or [],
                           "detail": _clean(detail or {})})
        return kid


def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if np.isnan(o) else round(float(o), 6)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o
