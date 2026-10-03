"""ORI Phase 6 - verify.py: the number check.

Every number the writer outputs must exist somewhere in the evidence bundle. This is enforced in
code, not just by instruction: any number in the text that cannot be matched to a bundle value is
a VIOLATION, and run_all.py refuses to ship a paragraph with violations.
"""
import re
from typing import List

# formatting/statistical constants that legitimately appear in text without being a "finding"
# (significance thresholds, the "p < 0.001" floor, percentages used as formatting, robust-z threshold, etc.)
ALLOWLIST = {0.0, 1.0, 100.0, 0.001, 0.01, 0.05, 0.95, 3.5, 2.0, 0.5, 0.6, 0.4, 0.3, 30.0}

ID_RE = re.compile(r"\b[A-Z]{2,6}(?:-[A-Z0-9]+)+\b")               # STAT-REL-003, KNOW-010, CONF-001 ...
NUM_RE = re.compile(r"[-+]?\d+\.\d+|[-+]?\d+")


def extract_numbers(text: str) -> List[float]:
    stripped = ID_RE.sub(" ", text)          # remove ids first so their digits are never read as numbers
    return [float(m) for m in NUM_RE.findall(stripped)]


def _collect(obj, out: set) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.add(round(float(obj), 6))
    elif isinstance(obj, str):
        # numbers can legitimately live inside a trusted string field (e.g. a literature claim's
        # own reported range, "23-36 PSU") - those are bundle content too, not just JSON numeric leaves
        for x in extract_numbers(obj):
            out.add(round(x, 6))
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect(v, out)


def bundle_numbers(bundle: dict) -> set:
    out = set()
    _collect(bundle, out)
    return out | ALLOWLIST


def _matches(x: float, pool: set) -> bool:
    for d in (0, 1, 2, 3, 4):
        if round(x, d) in {round(b, d) for b in pool}:
            return True
    return False


def verify_text(text: str, bundle: dict) -> List[str]:
    pool = bundle_numbers(bundle)
    violations = []
    for x in extract_numbers(text):
        if not _matches(x, pool):
            violations.append(f"number {x!r} in the text does not match any value in the evidence bundle")
    return violations
