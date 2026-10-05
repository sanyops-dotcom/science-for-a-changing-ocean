"""Traceable QC issue log. Every flag gets a stable id (QC-001, QC-002 ...)
that later phases (evidence ledger, writer caveats) can cite."""
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List

SEVERITIES = ("ERROR", "WARNING", "INFO")


@dataclass
class Issue:
    id: str
    severity: str          # ERROR | WARNING | INFO
    category: str
    message: str
    stations: List[str] = field(default_factory=list)
    parameter: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)
    action: str = "flagged only - data not modified"


class IssueLog:
    def __init__(self) -> None:
        self.issues: List[Issue] = []

    def add(self, severity: str, category: str, message: str, stations=None,
            parameter: str = "", detail=None, action: str = "flagged only - data not modified") -> Issue:
        assert severity in SEVERITIES
        issue = Issue(id=f"QC-{len(self.issues) + 1:03d}", severity=severity, category=category,
                      message=message, stations=list(stations or []), parameter=parameter,
                      detail=dict(detail or {}), action=action)
        self.issues.append(issue)
        return issue

    def counts(self) -> Dict[str, int]:
        return {s: sum(1 for i in self.issues if i.severity == s) for s in SEVERITIES}

    def to_records(self) -> List[dict]:
        return [asdict(i) for i in self.issues]
