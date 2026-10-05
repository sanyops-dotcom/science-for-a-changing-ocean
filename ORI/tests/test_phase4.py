import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
import main
from knowledge.common import KContext
from knowledge.library import LIBRARY
from knowledge.match import PLAUSIBLE, WEAK_CONFOUND, match_pairwise, run as match_run

_CACHE = {}


def _res():
    if "res" not in _CACHE:
        _CACHE["res"] = main.run(config.INPUT_DATA_DIR / config.DEFAULT_FILE, Path(tempfile.mkdtemp()))
    return _CACHE["res"]


def _ctx(res):
    return KContext(stat_records=res["stats"].items, reasoning=res["reasoning"])


def test_every_stat_id_cited_by_knowledge_exists():
    res = _res()
    valid = {r["id"] for r in res["stats"].items} | {c["id"] for c in res["reasoning"]["confounding"]}
    for k in res["knowledge"]["records"]:
        assert set(k["stat_ids"]) <= valid, k["id"]


def test_sign_mismatch_never_fires():
    """A library entry whose expected sign is wrong for the data must not appear as a match."""
    res = _res()
    ctx = _ctx(res)
    for spec in LIBRARY:
        if spec.signature is None:
            continue
        result = match_pairwise(ctx, spec)
        if result and result[0] == "sign_mismatch":
            fired_keys = {r["process_key"] for r in res["knowledge"]["records"]}
            assert spec.key not in fired_keys


def test_confidence_matches_confounding_flag():
    res = _res()
    conf_by_id = {c["id"]: c for c in res["reasoning"]["confounding"]}
    for k in res["knowledge"]["records"]:
        if k["kind"] != "pairwise":
            continue
        conf_ids = [i for i in k["stat_ids"] if i.startswith("CONF-")]
        if not conf_ids:
            continue
        c = conf_by_id[conf_ids[0]]
        if c["detail"]["attenuates_strongly"]:
            assert k["confidence"] == WEAK_CONFOUND, k["id"]
        else:
            assert k["confidence"] == PLAUSIBLE, k["id"]


def test_combo_requires_all_members_present():
    res = _res()
    combos = [k for k in res["knowledge"]["records"] if k["kind"] == "combo"]
    pairwise_keys = {k["process_key"] for k in res["knowledge"]["records"] if k["kind"] == "pairwise"}
    for c in combos:
        for member in c["detail"]["member_keys"]:
            assert member in pairwise_keys, (c["id"], member)


def test_no_library_process_asserted_as_fact():
    """Every non-NOT-ASSESSED record must be phrased as a candidate."""
    res = _res()
    for k in res["knowledge"]["records"]:
        if k["confidence"] == "NOT ASSESSED":
            continue
        assert "CANDIDATE" in k["confidence"]


def test_unmatched_covers_every_relational_result_not_otherwise_used():
    res = _res()
    rel_ids = {r["id"] for r in res["stats"].items if r["module"] == "relational" and r["level"] == "statistical_result"
              and r.get("evidence_strength") not in (None, "NONE", "n/a") and len(r["parameters"]) == 2}
    used_ids = {sid for k in res["knowledge"]["records"] if k["kind"] in ("pairwise", "combo") for sid in k["stat_ids"]
               if sid.startswith("STAT-REL")}
    unmatched_ids = {sid for k in res["knowledge"]["records"] if k["kind"] == "unmatched" for sid in k["stat_ids"]}
    assert used_ids | unmatched_ids == rel_ids


def test_anomaly_templates_cover_every_cooccurrence_pattern():
    res = _res()
    n_patterns = len([p for p in res["reasoning"]["patterns"] if p["kind"] == "anomaly_cooccurrence"])
    n_templates = len([k for k in res["knowledge"]["records"] if k["kind"] == "anomaly_template"])
    assert n_patterns == n_templates == 3


def test_reproducible():
    res1, res2 = _res(), main.run(config.INPUT_DATA_DIR / config.DEFAULT_FILE, Path(tempfile.mkdtemp()))
    a = [(k["process_key"], k["confidence"]) for k in res1["knowledge"]["records"]]
    b = [(k["process_key"], k["confidence"]) for k in res2["knowledge"]["records"]]
    assert a == b


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
