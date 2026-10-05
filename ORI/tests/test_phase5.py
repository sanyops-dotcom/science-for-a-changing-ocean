"""Phase 5 tests. The papers used here are 100% synthetic test fixtures - obviously fake
titles/authors/keys - used only to prove the matching code works. They are never written to
the real store and never presented to the user as real literature.
"""
import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
import main
from literature.match import run as match_run
from literature.schema import Claim, Paper, paper_from_dict
from literature.store import load_store, save_store
from literature.zotero_csv import from_zotero_csv

FAKE_PAPER_1 = Paper(
    zotero_key="SYNTH001", title="[SYNTHETIC TEST FIXTURE] A made-up study of a made-up process",
    authors="Testauthor et al.", year=2020, region_tags=["Testland Sea"],
    claims=[Claim(claim="Made-up finding: nitrite and DO are linked in the test fixture region.",
                  source_location="p.1 (synthetic)", region_tags=["Testland Sea"],
                  process_tags=["bio_o2_consumption_n_cycle"], parameter_tags=["nitrite", "DO"])])
FAKE_PAPER_2 = Paper(
    zotero_key="SYNTH002", title="[SYNTHETIC TEST FIXTURE] Another made-up study",
    authors="Fakename et al.", year=2021, region_tags=["Other Sea"],
    claims=[Claim(claim="Made-up finding: process tag matches but region does not.",
                  source_location="p.2 (synthetic)", region_tags=["Other Sea"],
                  process_tags=["bio_o2_consumption_n_cycle"], parameter_tags=["nitrite", "DO"])])
FAKE_PAPER_UNTAGGED = Paper(zotero_key="SYNTH003", title="[SYNTHETIC] untagged claim", authors="X", year=2022,
                            claims=[Claim(claim="no tags", source_location="p.1")])


def _res():
    return main.run(config.INPUT_DATA_DIR / config.DEFAULT_FILE, Path(tempfile.mkdtemp()))


def test_empty_store_yields_not_checked_never_a_fabricated_match():
    res = _res()
    reg = match_run(res["knowledge"]["records"], [], [], [])
    checks = [r for r in reg.items if r["kind"] == "literature_check"]
    assert checks and all(r["status"] == "NOT_CHECKED" for r in checks)
    assert all(r["matches"] == [] for r in checks)


def test_real_store_now_has_papers_and_produces_real_matches():
    """The real store was populated from a user-provided literature synthesis (Sep 2026); this
    checks the pipeline actually uses it, not that ORI shipped with an empty store forever."""
    res = _res()
    lit = res["literature"]
    assert lit["n_papers"] >= 5
    checks = [r for r in lit["records"] if r["kind"] == "literature_check"]
    assert any(r["status"] == "MATCHED" for r in checks)
    matched = next(r for r in checks if r["status"] == "MATCHED")
    assert matched["matches"][0]["match_strength"] in ("STRONG", "MECHANISTIC", "REGIONAL")


def test_strong_match_requires_process_and_region_synthetic_fixture():
    res = _res()
    know = res["knowledge"]["records"]
    target = next(k for k in know if k["process_key"] == "bio_o2_consumption_n_cycle")
    reg = match_run(know, [FAKE_PAPER_1], ["Testland Sea"], [])
    rec = next(r for r in reg.items if r["knowledge_id"] == target["id"])
    assert rec["status"] == "MATCHED"
    assert rec["matches"][0]["match_strength"] == "STRONG"
    assert rec["matches"][0]["zotero_key"] == "SYNTH001"


def test_mechanistic_match_when_region_does_not_align():
    res = _res()
    know = res["knowledge"]["records"]
    target = next(k for k in know if k["process_key"] == "bio_o2_consumption_n_cycle")
    reg = match_run(know, [FAKE_PAPER_2], ["Testland Sea"], [])   # region tag doesn't match paper's "Other Sea"
    rec = next(r for r in reg.items if r["knowledge_id"] == target["id"])
    assert rec["status"] == "MATCHED" and rec["matches"][0]["match_strength"] == "MECHANISTIC"


def test_no_region_config_never_produces_strong():
    res = _res()
    know = res["knowledge"]["records"]
    target = next(k for k in know if k["process_key"] == "bio_o2_consumption_n_cycle")
    reg = match_run(know, [FAKE_PAPER_1], [], [])   # no region tags configured at all
    rec = next(r for r in reg.items if r["knowledge_id"] == target["id"])
    assert rec["matches"][0]["match_strength"] == "MECHANISTIC"


def test_untagged_claim_flagged_as_store_error_not_silently_dropped():
    p = FAKE_PAPER_UNTAGGED
    errs = p.validate()
    assert any("no region/process/parameter tags" in e for e in errs)


def test_store_round_trip():
    d = Path(tempfile.mkdtemp()) / "papers.json"
    save_store([FAKE_PAPER_1], d)
    papers, errors = load_store(d)
    assert errors == [] and len(papers) == 1 and papers[0].zotero_key == "SYNTH001"
    assert papers[0].claims[0].claim == FAKE_PAPER_1.claims[0].claim


def test_duplicate_zotero_key_flagged():
    d = Path(tempfile.mkdtemp()) / "papers.json"
    save_store([FAKE_PAPER_1, FAKE_PAPER_1], d)
    papers, errors = load_store(d)
    assert len(papers) == 1 and any("duplicate" in e for e in errors)


def test_zotero_csv_import_creates_claimless_stubs():
    d = Path(tempfile.mkdtemp()) / "export.csv"
    with open(d, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Key", "Title", "Author", "Publication Year", "Manual Tags"])
        w.writerow(["ZKEY1", "[SYNTHETIC] CSV import test paper", "Someone", "2019", "Testland Sea; upwelling"])
        w.writerow(["", "", "", "", ""])   # blank row should be skipped
    papers = from_zotero_csv(d)
    assert len(papers) == 1
    assert papers[0].zotero_key == "ZKEY1" and papers[0].year == 2019
    assert papers[0].claims == []
    assert "Testland Sea" in papers[0].region_tags


def test_real_store_loads_cleanly_with_only_real_citations():
    """Every paper in the real store must be a genuine, named, dated citation - never a fixture."""
    papers, errors = load_store(config.LITERATURE_STORE_PATH)
    assert errors == []
    for p in papers:
        assert "SYNTHETIC" not in p.title.upper() and "TEST FIXTURE" not in p.title.upper()
        assert p.year and 1900 < p.year <= 2026


def test_no_literature_check_for_unmatched_or_anomaly_knowledge_kinds():
    res = _res()
    checked_ids = {r["knowledge_id"] for r in res["literature"]["records"] if r["kind"] == "literature_check"}
    know_kinds = {k["id"]: k["kind"] for k in res["knowledge"]["records"]}
    assert all(know_kinds[kid] in ("pairwise", "combo") for kid in checked_ids)
    assert len(checked_ids) == sum(1 for k in res["knowledge"]["records"] if k["kind"] in ("pairwise", "combo"))


def test_reproducible():
    a = _res()["literature"]["records"]
    b = _res()["literature"]["records"]
    assert [(r["knowledge_id"], r["status"]) for r in a] == [(r["knowledge_id"], r["status"]) for r in b]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
