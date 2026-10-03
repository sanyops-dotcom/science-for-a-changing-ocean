import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
import main
from writer.render import render
from writer.verify import bundle_numbers, extract_numbers, verify_text

_CACHE = {}


def _res():
    if "res" not in _CACHE:
        _CACHE["res"] = main.run(config.INPUT_DATA_DIR / config.DEFAULT_FILE, Path(tempfile.mkdtemp()))
    return _CACHE["res"]


def test_extract_numbers_ignores_ids():
    text = "STAT-REL-003 shows rho = 0.82 (KNOW-010, CONF-005) with n = 34."
    nums = extract_numbers(text)
    assert 0.82 in nums and 34.0 in nums
    assert 3.0 not in nums and 10.0 not in nums and 5.0 not in nums   # digits inside the ids must not leak


def test_verifier_catches_a_fabricated_number():
    res = _res()
    bundle = res["writer"]["bundle"]
    fake_text = "This is a fabricated claim: DO explains 87.3% of the variance in temperature."
    violations = verify_text(fake_text, bundle)
    assert violations and any("87.3" in v for v in violations)


def test_verifier_passes_a_real_bundle_number():
    res = _res()
    bundle = res["writer"]["bundle"]
    real_rho = next(r["statistic"]["rho"] for r in bundle["statistics"]
                    if r["module"] == "relational" and set(r["parameters"]) == {"salinity", "temperature"})
    text = f"Salinity and temperature correlate with rho = {real_rho:.2f}."
    assert verify_text(text, bundle) == []


def test_shipped_result_has_zero_violations_end_to_end():
    res = _res()
    w = res["writer"]
    assert w["shipped"] is True
    assert w["violations"] == []
    assert verify_text(w["text"], w["bundle"]) == []


def test_top_level_sections_present():
    res = _res()
    text = res["writer"]["text"]
    for header in ("## Data Observation", "## Results by Parameter", "## Synthesis"):
        assert header in text


def test_every_parameter_has_a_subsection_with_numerical_evidence():
    res = _res()
    text = res["writer"]["text"]
    bundle = res["writer"]["bundle"]
    body = text.split("## Results by Parameter")[1].split("## Synthesis")[0]
    for p in bundle["data"]["parameters"]:
        label = bundle["data"]["parameter_labels"][p]
        assert f"### {label}" in body
    # every parameter's descriptive statement (min/max) must appear under its own subsection
    sections = body.split("\n### ")[1:]
    for sec in sections:
        assert any(kw in sec for kw in ("ranged from", "No baseline", "No statistically important"))


def test_every_stat_id_in_text_exists_in_bundle():
    res = _res()
    text = res["writer"]["text"]
    bundle = res["writer"]["bundle"]
    valid = {r["id"] for r in bundle["statistics"]} | {k["id"] for k in bundle["knowledge"]} | \
            {c["id"] for c in bundle["reasoning"]["confounding"]}
    ids_in_text = set(re.findall(r"\b[A-Z]{2,6}(?:-[A-Z0-9]+)+\b", text))
    assert ids_in_text <= valid, ids_in_text - valid


def test_no_confidence_label_stripped_of_candidate_in_results_section():
    res = _res()
    text = res["writer"]["text"]
    body = text.split("## Results by Parameter")[1].split("## Synthesis")[0]
    for line in body.splitlines():
        if "Candidate mechanism:" in line:
            assert "CANDIDATE" in line


def test_literature_citations_in_text_trace_to_real_bundle_matches():
    res = _res()
    text = res["writer"]["text"]
    bundle = res["writer"]["bundle"]
    assert bundle["literature_n_papers"] > 0
    cited = {m["citation"] for r in bundle["literature"] if r["kind"] == "literature_check"
            for m in r["matches"]}
    assert cited and any(c in text for c in cited)


def test_baseline_notable_and_contradicts_appear_in_their_owner_parameter_section():
    res = _res()
    text = res["writer"]["text"]
    body = text.split("## Results by Parameter")[1].split("## Synthesis")[0]
    assert "### Dissolved oxygen" in body
    do_sec = body.split("### Dissolved oxygen")[1].split("### ")[0]
    assert "NOTABLE" in do_sec
    phos_sec = body.split("### Orthophosphate")[1].split("### ")[0]
    assert "CONTRADICTS_BASELINE" in phos_sec


def test_bundle_numbers_includes_key_manifest_values():
    res = _res()
    pool = bundle_numbers(res["writer"]["bundle"])
    assert 34.0 in pool and 9.0 in pool


def test_reproducible():
    a = render(_res()["writer"]["bundle"])
    b = render(main.run(config.INPUT_DATA_DIR / config.DEFAULT_FILE, Path(tempfile.mkdtemp()))["writer"]["bundle"])
    assert a == b


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
