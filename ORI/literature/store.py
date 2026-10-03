"""ORI Phase 5 - store.py: load/validate/save the literature store (a JSON file of Paper records).

The store is local and explicit - ORI never invents a paper or a claim. If the store is empty or
missing, the literature engine says so and produces NOT_CHECKED records rather than silence.
"""
import json
from pathlib import Path
from typing import List, Tuple

from literature.schema import Paper, paper_from_dict, paper_to_dict


def load_store(path: Path) -> Tuple[List[Paper], List[str]]:
    """Returns (papers, load_errors). Missing file -> ([], []) with no error - an empty store is a valid state."""
    path = Path(path)
    if not path.exists():
        return [], []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [], [f"{path}: invalid JSON ({e})"]
    papers, errors = [], []
    seen = set()
    for i, d in enumerate(raw.get("papers", [])):
        try:
            p = paper_from_dict(d)
        except (KeyError, TypeError) as e:
            errors.append(f"entry {i}: could not parse ({e})")
            continue
        if p.zotero_key in seen:
            errors.append(f"{p.zotero_key}: duplicate zotero_key - skipped")
            continue
        seen.add(p.zotero_key)
        errors += p.validate()
        papers.append(p)
    return papers, errors


def save_store(papers: List[Paper], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"papers": [paper_to_dict(p) for p in papers]}, indent=2, ensure_ascii=False),
                    encoding="utf-8")
