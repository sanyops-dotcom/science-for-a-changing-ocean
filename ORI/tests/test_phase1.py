"""Phase 1 safety tests: the reader must never alter observations."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
from data.excel_reader import read_dataset
from quality.issues import IssueLog

FILE = config.INPUT_DATA_DIR / config.DEFAULT_FILE


def test_raw_values_preserved():
    rr = read_dataset(FILE, IssueLog())
    master = pd.read_excel(FILE, sheet_name="Master")
    master.columns = [c for c in master.columns]
    for key, info in rr.column_map["params"].items():
        src = pd.to_numeric(master[[c for c in master.columns if c.replace(".", " ").strip() == info["column"]][0]])
        got = rr.long[rr.long["parameter"] == key].sort_values("excel_row")["value_raw"].values
        assert np.allclose(np.sort(got), np.sort(src.values), equal_nan=True), key


def test_bdl_rule_only_on_nutrients_and_nonpositive():
    rr = read_dataset(FILE, IssueLog())
    b = rr.long[rr.long["censor"] == "BDL"]
    assert (b["value_raw"] <= 0).all()
    assert set(b["parameter"]) <= {p.key for p in config.PARAMETERS if p.bdl_rule}
    assert b["value_analysis"].isna().all()


def test_one_row_per_station_in_station_table():
    rr = read_dataset(FILE, IssueLog())
    assert rr.station_level["station"].is_unique
    assert len(rr.station_level) == 34


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
