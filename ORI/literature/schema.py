"""ORI Phase 5 - schema.py: the literature record format.

A PAPER is metadata only. Every scientific statement it can support lives in its own CLAIM -
a short, ALREADY-PARAPHRASED summary the researcher writes once (not machine-extracted text,
not a verbatim quotation), with a page/section reference so it can be checked by hand. This
mirrors your plan's point: "the literature engine should retain the reference associated with
every important scientific statement" - and it keeps ORI from ever citing text it hasn't
actually been shown.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class Claim:
    claim: str                      # short, paraphrased in the researcher's own words
    source_location: str            # e.g. "p.4, section 3.2" - required, so it can be checked by hand
    region_tags: List[str] = field(default_factory=list)
    process_tags: List[str] = field(default_factory=list)     # match knowledge/library.py ProcessSpec.key where possible
    parameter_tags: List[str] = field(default_factory=list)   # canonical config.PARAMETERS keys where possible

    def validate(self, paper_key: str) -> List[str]:
        errs = []
        if not self.claim or not self.claim.strip():
            errs.append(f"{paper_key}: claim text is empty")
        if len(self.claim.split()) > 60:
            errs.append(f"{paper_key}: claim is {len(self.claim.split())} words - keep claims short paraphrases, "
                        f"not reproduced passages")
        if not self.source_location or not self.source_location.strip():
            errs.append(f"{paper_key}: claim has no source_location (page/section) - cannot be checked by hand")
        if not (self.region_tags or self.process_tags or self.parameter_tags):
            errs.append(f"{paper_key}: claim has no region/process/parameter tags - it can never be matched")
        return errs


@dataclass
class Paper:
    zotero_key: str
    title: str
    authors: str
    year: Optional[int] = None
    region_tags: List[str] = field(default_factory=list)
    claims: List[Claim] = field(default_factory=list)

    def validate(self) -> List[str]:
        errs = []
        if not self.zotero_key:
            errs.append("paper missing zotero_key")
        if not self.title:
            errs.append(f"{self.zotero_key}: missing title")
        if not self.claims:
            errs.append(f"{self.zotero_key}: no claims - paper is in the store but contributes nothing to matching yet")
        for c in self.claims:
            errs += c.validate(self.zotero_key)
        return errs

    def citation(self) -> str:
        return f"{self.authors} ({self.year})" if self.year else self.authors


def paper_from_dict(d: dict) -> Paper:
    claims = [Claim(**c) for c in d.get("claims", [])]
    return Paper(zotero_key=d["zotero_key"], title=d.get("title", ""), authors=d.get("authors", ""),
                year=d.get("year"), region_tags=d.get("region_tags", []), claims=claims)


def paper_to_dict(p: Paper) -> dict:
    return {"zotero_key": p.zotero_key, "title": p.title, "authors": p.authors, "year": p.year,
           "region_tags": p.region_tags, "claims": [asdict(c) for c in p.claims]}
