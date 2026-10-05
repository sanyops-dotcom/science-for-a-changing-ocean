"""Small helpers shared by the statistical modules."""
import numpy as np

import config


def fv(key: str, x, extra: int = 0) -> str:
    """Format a value with the parameter's reporting precision."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    return f"{float(x):.{config.DECIMALS.get(key, 3) + extra}f}"


def sfv(key: str, x) -> str:
    """Signed value: +0.12 / -0.12."""
    s = fv(key, x)
    return s if s.startswith("-") or s == "n/a" else "+" + s


def skip_if_unsupported(ctx, analysis: str, module: str, label: str) -> bool:
    """If the eligibility gate says NOT_SUPPORTED, record that fact (never silently skip)."""
    a = ctx.gate["analyses"][analysis]
    if a["status"] == "NOT_SUPPORTED":
        ctx.reg.add("SYS", module, "not_run", f"{label} was not performed: " + " ".join(a["reasons"]), [],
                    caveats=list(a["reasons"]), qc_ids=list(a.get("qc_ids", [])), gate_status=a["status"])
        return True
    return False


def pstr(p) -> str:
    """'p < 0.001' or 'p = 0.012' (never 'p = < 0.001')."""
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return "p = n/a"
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"
