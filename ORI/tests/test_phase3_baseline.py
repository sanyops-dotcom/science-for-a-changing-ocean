import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
import main
from reasoning import baseline

_CACHE = {}


def _res():
    if "res" not in _CACHE:
        _CACHE["res"] = main.run(config.INPUT_DATA_DIR / config.DEFAULT_FILE, Path(tempfile.mkdtemp()))
    return _CACHE["res"]


def test_ph_has_no_baseline():
    res = _res()
    items = res["reasoning"]["baseline_ranges"]
    ph = next(i for i in items if i["parameters"] == ["pH"])
    assert ph["detail"]["status"] == "NO_BASELINE"


def test_do_and_nitrate_flagged_notable_below_baseline():
    res = _res()
    items = {i["parameters"][0]: i for i in res["reasoning"]["baseline_ranges"] if i["parameters"]}
    d = items["DO"]["detail"]
    assert d["status"] == "NOTABLE"
    tol = (d["baseline_max"] - d["baseline_min"]) * config.BASELINE_TOLERANCE
    assert d["observed_min"] < d["baseline_min"] - tol
    assert items["nitrate"]["detail"]["status"] == "NOTABLE"


def test_salinity_temperature_familiar():
    res = _res()
    items = {i["parameters"][0]: i for i in res["reasoning"]["baseline_ranges"] if i["parameters"]}
    assert items["salinity"]["detail"]["status"] == "FAMILIAR"
    assert items["temperature"]["detail"]["status"] == "FAMILIAR"


def test_do_temperature_relationship_is_familiar():
    res = _res()
    rel = {frozenset(i["parameters"]): i for i in res["reasoning"]["baseline_relationships"]}
    item = rel[frozenset({"DO", "temperature"})]
    assert item["detail"]["status"] == "FAMILIAR"
    assert item["detail"]["expected_sign"] == "-" and item["detail"]["observed_sign"] == "-"


def test_do_phosphate_relationship_contradicts_baseline():
    res = _res()
    rel = {frozenset(i["parameters"]): i for i in res["reasoning"]["baseline_relationships"]}
    item = rel[frozenset({"DO", "phosphate"})]
    assert item["detail"]["status"] == "CONTRADICTS_BASELINE"
    assert item["detail"]["expected_sign"] == "+" and item["detail"]["observed_sign"] == "-"


def test_unclassified_relationship_flagged_not_in_baseline():
    res = _res()
    rel = {frozenset(i["parameters"]): i for i in res["reasoning"]["baseline_relationships"]}
    item = rel[frozenset({"salinity", "temperature"})]
    assert item["detail"]["status"] == "NOT_IN_BASELINE"


def test_region_priority_prefers_most_specific():
    picked = baseline._pick_range("DO", ["Gulf of Mannar", "Indian Ocean coastal"])
    assert picked[0] == "Gulf of Mannar"
    picked2 = baseline._pick_range("DO", [])
    assert picked2[0] in ("Gulf of Mannar", "Indian Ocean coastal")


def test_reproducible():
    a = _res()["reasoning"]["baseline_ranges"]
    b = main.run(config.INPUT_DATA_DIR / config.DEFAULT_FILE, Path(tempfile.mkdtemp()))["reasoning"]["baseline_ranges"]
    assert [i["text"] for i in a] == [i["text"] for i in b]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
