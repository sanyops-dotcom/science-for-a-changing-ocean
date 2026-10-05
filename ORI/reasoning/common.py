"""ORI Phase 3 - shared machinery for the reasoning layer.

Reasoning records ("patterns" and "scores") are built ONLY from Phase 2 statistical records
and the station table - never from raw Excel values, and never with an oceanographic claim
attached. That belongs to Phase 4 (oceanographic_knowledge.py), which is not built yet.
"""
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

import config


@dataclass
class RContext:
    st: pd.DataFrame          # station-level table
    stat_records: List[dict]  # Phase 2 records (output/stats/stat_records.json -> "records")
    gate: dict
    tables_dir: Path

    def stat_by_id(self, sid: str) -> dict:
        return self._index[sid]

    def __post_init__(self):
        self._index = {r["id"]: r for r in self.stat_records}
        self.st = self.st.copy()
        self.st["transect_no"] = self.st["transect"].map(lambda s: int(s[1:]))

    def save_table(self, df: pd.DataFrame, name: str) -> str:
        self.tables_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(self.tables_dir / name, index=False)
        return f"tables/{name}"


class Registry:
    """Same shape/spirit as stats/common.py Registry, for reasoning-layer records."""
    def __init__(self) -> None:
        self.items: List[dict] = []
        self._count: Dict[str, int] = defaultdict(int)

    def add(self, prefix: str, kind: str, text: str, *, parameters=None, stations=None,
            stat_ids=None, detail=None, caveats=None) -> str:
        self._count[prefix] += 1
        sid = f"{prefix}-{self._count[prefix]:03d}"
        self.items.append({"id": sid, "kind": kind, "text": text, "parameters": parameters or [],
                           "stations": stations or [], "stat_ids": stat_ids or [],
                           "detail": _clean(detail or {}), "caveats": caveats or []})
        return sid


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
