import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
import main
from reasoning.confounding import partial_spearman

_CACHE = {}


def _run():
    if "res" not in _CACHE:
        out = Path(tempfile.mkdtemp())
        _CACHE["res"] = main.run(config.INPUT_DATA_DIR / config.DEFAULT_FILE, out)
        _CACHE["st"] = pd.read_csv(out / "data" / "station_level.csv")
    return _CACHE["res"], _CACHE["st"]


def test_partial_spearman_recovers_zero_when_z_explains_everything():
    """y is purely a (noisy) function of z: partial correlation of x (independent) and y controlling z ~ 0."""
    rng = np.random.default_rng(0)
    z = rng.uniform(0, 10, 200)
    y = 2 * z + rng.normal(0, 0.01, 200)
    x = rng.normal(size=200)          # independent of z and y
    r, p, n, df = partial_spearman(x, y, z)
    assert abs(r) < 0.15 and n == 200


def test_partial_spearman_matches_manual_ols_residual_method():
    rng = np.random.default_rng(2)
    z = rng.uniform(0, 10, 60)
    x = 0.7 * z + rng.normal(0, 1, 60)
    y = 0.7 * z + rng.normal(0, 1, 60)
    r, p, n, df = partial_spearman(x, y, z)
    rz, xz, yz = sps.rankdata(z), sps.rankdata(x), sps.rankdata(y)
    bx = np.polyfit(rz, xz, 1); by = np.polyfit(rz, yz, 1)
    rx = xz - np.polyval(bx, rz); ry = yz - np.polyval(by, rz)
    manual_r, _ = sps.pearsonr(rx, ry)
    assert abs(r - manual_r) < 1e-9


def test_importance_scores_recomputed_independently():
    res, st = _run()
    idx = {r["id"]: r for r in res["stats"].items}
    n_stations = res["gate"]["n_independent_observations"]
    strength_val = {"STRONG": 1.0, "MODERATE": 0.66, "WEAK": 0.33, "NONE": 0.0}
    corrob = {}
    for r in res["stats"].items:
        if r["level"] != "statistical_result" or r.get("evidence_strength") in (None, "NONE", "n/a"):
            continue
        for p in r["parameters"]:
            corrob.setdefault(p, set()).add(r["module"])
    for item in res["reasoning"]["importance"]:
        sid = item["stat_ids"][0]
        rec = idx[sid]
        m, s = rec["module"], rec["statistic"]
        if m == "transect":
            eff = abs(s.get("epsilon2") or 0)
        elif m == "relational":
            eff = abs(s.get("rho") or 0)
        elif m == "spatial" and "I" in s:
            eff = abs(s["I"])
        elif m == "spatial":
            eff = max((abs(t["rho"]) for t in s.get("tests", [])), default=0.0)
        elif m == "vertical":
            eff = abs((s.get("share_negative") or 0) - (s.get("share_positive") or 0))
        else:
            eff = 0.0
        c = max((len(corrob.get(p, {m})) for p in rec["parameters"]), default=1)
        corrob_norm = min((c - 1) / 2.0, 1.0)
        expect = 100 * (config.IMPORTANCE_W_STRENGTH * strength_val.get(rec["evidence_strength"], 0.0) +
                        config.IMPORTANCE_W_EFFECT * min(eff, 1.0) +
                        config.IMPORTANCE_W_N * min(rec["n"] / n_stations, 1.0) +
                        config.IMPORTANCE_W_CORROBORATION * corrob_norm)
        assert abs(item["detail"]["score"] - round(expect, 1)) < 0.05, sid


def test_confounding_matches_relational_rho_sign_pairing():
    res, st = _run()
    for item in res["reasoning"]["confounding"]:
        a, b = item["parameters"]
        d = item["detail"]
        dd = st[["transect_no" if "transect_no" in st.columns else "transect", a, b]].dropna() \
            if "transect_no" in st.columns else None
        # recompute transect_no if absent
        tn = st["transect"].map(lambda s: int(s[1:]))
        dsub = pd.DataFrame({"z": tn, a: st[a], b: st[b]}).dropna()
        r, p, n, df = partial_spearman(dsub[a], dsub[b], dsub["z"])
        assert abs(r - d["partial_rho"]) < 1e-6
        assert n == d["n"]


def test_patterns_reference_only_existing_stat_ids():
    res, _ = _run()
    valid = {r["id"] for r in res["stats"].items}
    for p in res["reasoning"]["patterns"]:
        assert set(p["stat_ids"]) <= valid, p["id"]


def test_anomaly_cooccurrence_patterns_match_phase2_ano_records():
    res, _ = _run()
    ano_ids = {r["id"] for r in res["stats"].items if r["id"].startswith("STAT-ANO")}
    pat_ano = [p for p in res["reasoning"]["patterns"] if p["kind"] == "anomaly_cooccurrence"]
    assert {p["stat_ids"][0] for p in pat_ano} == ano_ids
    assert len(ano_ids) == 3


def test_no_mechanism_language_in_reasoning_layer():
    import re
    res, _ = _run()
    banned = r"\b(because|remineralis|remineraliz|upwelling|downwelling|ventilat|respiration|caused by)\b"
    for bucket in ("importance", "confounding", "patterns"):
        for item in res["reasoning"][bucket]:
            assert not re.search(banned, item["text"], re.I), item["id"]


def test_reproducible():
    res, _ = _run()
    res2 = main.run(config.INPUT_DATA_DIR / config.DEFAULT_FILE, Path(tempfile.mkdtemp()))
    a = [i["detail"]["score"] for i in res["reasoning"]["importance"]]
    b = [i["detail"]["score"] for i in res2["reasoning"]["importance"]]
    assert a == b


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
