"""Phase 2 tests: numbers are re-computed independently, and the 'no explanation' rule is enforced."""
import re
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
import main
from stats import spatial, vertical
from stats.common import Context, Registry, benjamini_hochberg, spearman_with_ci

_CACHE = {}


def _run():
    if "res" not in _CACHE:
        out = Path(tempfile.mkdtemp())
        _CACHE["out"] = out
        _CACHE["res"] = main.run(config.INPUT_DATA_DIR / config.DEFAULT_FILE, out)
        _CACHE["st"] = pd.read_csv(out / "data" / "station_level.csv")
    return _CACHE["res"], _CACHE["st"], _CACHE["out"]


def _by_prefix(res, module, param=None):
    return [i for i in res["stats"].items if i["module"] == module and (param is None or param in i["parameters"])]


def test_bh_fdr_known_values():
    got = benjamini_hochberg([0.01, 0.04, 0.03, 0.005])
    assert np.allclose(got, [0.02, 0.04, 0.04, 0.02])


def test_spearman_ci_perfect_monotone():
    x = np.arange(20.0)
    rho, p, lo, hi = spearman_with_ci(x, x ** 3)
    assert rho == 1.0 and lo == 1.0 and hi == 1.0


def test_independent_recalculation_of_key_numbers():
    res, st, _ = _run()
    # relational: Salinity vs Temperature
    rec = next(i for i in _by_prefix(res, "relational") if set(i["parameters"]) == {"salinity", "temperature"})
    d = st[["salinity", "temperature"]].dropna()
    rho, _ = sps.spearmanr(d["salinity"], d["temperature"])
    assert abs(rec["statistic"]["rho"] - rho) < 1e-12 and rec["statistic"]["n"] == len(d) == 34
    # relational with BDL: Nitrite vs DO uses only detected stations
    rec = next(i for i in _by_prefix(res, "relational") if set(i["parameters"]) == {"nitrite", "DO"})
    d = st[["nitrite", "DO"]].dropna()
    assert rec["statistic"]["n"] == len(d) == 18
    assert abs(rec["statistic"]["rho"] - sps.spearmanr(d["nitrite"], d["DO"])[0]) < 1e-12
    # transect: Kruskal-Wallis for salinity
    rec = _by_prefix(res, "transect", "salinity")[0]
    groups = [g["salinity"].values for _, g in st.groupby("transect")]
    H, p = sps.kruskal(*groups)
    assert abs(rec["statistic"]["H"] - H) < 1e-9 and abs(rec["statistic"]["p"] - p) < 1e-12
    # descriptive
    rec = _by_prefix(res, "descriptive", "DO")[0]
    assert abs(rec["statistic"]["mean"] - st["DO"].mean()) < 1e-12 and abs(rec["statistic"]["sd"] - st["DO"].std(ddof=1)) < 1e-12


def test_moran_matches_loop_implementation():
    rng = np.random.default_rng(1)
    xy = rng.uniform(0, 100, size=(25, 2))
    x = xy[:, 0] * 0.05 + rng.normal(0, 0.5, 25)          # spatially structured field
    I, E, p = spatial._moran(x, xy, 4, 199, 7)
    n, k = len(x), 4
    z = x - x.mean()
    num = 0.0
    for i in range(n):
        d = np.sqrt(((xy - xy[i]) ** 2).sum(1)); d[i] = np.inf
        for j in np.argsort(d, kind="stable")[:k]:
            num += z[i] * z[j] / k
    assert abs(I - num / (z ** 2).sum()) < 1e-12 and I > 0.3 and p < 0.05
    I2, _, p2 = spatial._moran(rng.normal(size=25), xy, 4, 199, 7)   # random field
    assert p2 > 0.05


def test_bdl_values_never_used():
    res, st, _ = _run()
    assert st.loc[st["nitrite__bdl"], "nitrite"].isna().all()
    assert (st.loc[st["nitrite__bdl"], "nitrite__raw"] <= 0).all()
    d = _by_prefix(res, "descriptive", "nitrite")[0]
    assert d["statistic"]["n"] == 18 and d["statistic"]["min"] > 0


def test_gate_respected_no_numbers_for_unsupported_analyses():
    res, _, _ = _run()
    for m in ("vertical", "temporal"):
        recs = _by_prefix(res, m)
        assert len(recs) == 1 and recs[0]["level"] == "not_run" and recs[0]["statistic"] == {}


def test_no_explanations_in_statistical_statements():
    """Level-2 rule: this layer may not say WHY. Fails if a mechanism word slips in."""
    res, _, _ = _run()
    banned = r"\b(because|caused|causes|due to|driven|drives|remineralis|remineraliz|upwelling|downwelling|ventilat|mixing|" \
             r"advection|respiration|productivity|consumption|explained by|indicates that|suggests that)\b"
    for i in res["stats"].items:
        assert not re.search(banned, i["statement"], re.I), (i["id"], i["statement"])


def test_ids_unique_and_qc_ids_exist():
    res, _, _ = _run()
    ids = [i["id"] for i in res["stats"].items]
    assert len(ids) == len(set(ids))
    valid_qc = {q.id for q in res["log"].issues}
    for i in res["stats"].items:
        assert set(i["qc_ids"]) <= valid_qc, i["id"]
        assert i["gate_status"], i["id"]


def test_reproducible():
    res, _, _ = _run()
    res2 = main.run(config.INPUT_DATA_DIR / config.DEFAULT_FILE, Path(tempfile.mkdtemp()))
    assert [i["statement"] for i in res["stats"].items] == [i["statement"] for i in res2["stats"].items]


def test_excluded_coordinate_stations_not_in_spatial_tests():
    res, _, _ = _run()
    excluded = set(res["gate"]["analyses"]["spatial"]["stations_excluded"])
    assert excluded == {"T1 S4", "T5 S1", "T6 S2", "T7 S4"}
    lat_tests = [t for r in _by_prefix(res, "spatial", "salinity") if "tests" in r["statistic"]
                 for t in r["statistic"]["tests"] if t["predictor"] == "latitude"]
    assert lat_tests and all(t["n"] == 34 - len(excluded) for t in lat_tests)


def test_vertical_module_works_when_depth_data_exist():
    """Synthetic depth-resolved data: switches on and finds the built-in decrease."""
    rows, sts = [], []
    rng = np.random.default_rng(3)
    for s in range(1, 11):
        for depth in (0, 10, 20, 50):
            rows.append({"parameter": "DO", "station": f"T1 S{s}", "transect": "T1", "depth_m": depth,
                         "value_analysis": 4.5 - 0.02 * depth + rng.normal(0, 0.03)})
        sts.append({"station": f"T1 S{s}", "transect": "T1"})
    long = pd.DataFrame(rows)
    gate = {"analyses": {"vertical": {"status": "SUPPORTED", "reasons": [], "qc_ids": []}},
            "parameters": {"DO": {"stations_bdl": 0}}, "n_independent_observations": 10}
    ctx = Context(st=pd.DataFrame(sts), long=long, gate=gate, qc={}, qc_records=[], keys=["DO"],
                  tables_dir=Path(tempfile.mkdtemp()))
    ctx.reg = Registry()
    vertical.run(ctx)
    rec = [i for i in ctx.reg.items if i["module"] == "vertical"][0]
    assert rec["level"] == "statistical_result" and rec["statistic"]["median_change"] < -0.9
    assert "decreased" in rec["statement"] and "100%" in rec["statement"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
