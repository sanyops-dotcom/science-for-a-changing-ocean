"""ORI Phase 5 - zotero_csv.py: import paper METADATA from a Zotero library export.

In Zotero: select the items or collection -> right-click -> Export Items... -> CSV.
This gives paper metadata (title, authors, year, tags) but NOT claims - Zotero's own export has
no per-claim data, because a "claim" is a specific sentence-level judgement someone makes while
reading the PDF. This importer creates Paper stubs with empty claims lists; claims are then added
by hand in the JSON store (or by a future PDF-reading pass, out of scope for Phase 5).

This path needs no network access and works fully offline in this sandbox.
"""
import csv
from pathlib import Path
from typing import List

from literature.schema import Paper

COLUMN_ALIASES = {
    "key": ["Key", "Zotero Key", "Item Key"],
    "title": ["Title"],
    "authors": ["Author", "Authors", "Creator"],
    "year": ["Publication Year", "Year", "Date"],
    "tags": ["Manual Tags", "Automatic Tags", "Tags"],
}


def _pick(row: dict, names: List[str]) -> str:
    for n in names:
        if n in row and row[n]:
            return row[n]
    return ""


def _year(v: str):
    digits = "".join(ch for ch in v if ch.isdigit())
    return int(digits[:4]) if len(digits) >= 4 else None


def from_zotero_csv(path: Path) -> List[Paper]:
    path = Path(path)
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    papers = []
    for row in rows:
        key = _pick(row, COLUMN_ALIASES["key"]) or f"NOKEY-{len(papers) + 1}"
        title = _pick(row, COLUMN_ALIASES["title"])
        if not title:
            continue   # not a real bibliographic entry (e.g. a blank or note row)
        tags_raw = _pick(row, COLUMN_ALIASES["tags"])
        tags = [t.strip() for t in tags_raw.split(";") if t.strip()] if tags_raw else []
        papers.append(Paper(zotero_key=key, title=title, authors=_pick(row, COLUMN_ALIASES["authors"]),
                            year=_year(_pick(row, COLUMN_ALIASES["year"])), region_tags=tags, claims=[]))
    return papers
