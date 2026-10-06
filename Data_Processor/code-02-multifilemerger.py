# =============================================================
#  Excel Lookup & Merge Tool  (Streamlit) - MULTI-FILE EDITION
# =============================================================
#  Python/Streamlit conversion of code-02-multifilemerger.R
#
#  Run it with:
#       streamlit run code-02-multifilemerger.py
#  A browser tab opens automatically with the tool.
#
#  Required packages (install once):
#       pip install streamlit pandas openpyxl xlrd
#
#  What it does:
#   1. Upload ONE Master file (the file that gets updated).
#   2. Upload UP TO N_SLOTS Input files (data sources). Each input
#      file is independent: its own sheet, key column(s) and
#      columns to copy.
#   3. Click "Run Merge". For every Master row and every input
#      file, the app looks for a matching key (trim spaces, ignore
#      case, compare as text; optionally name + 2nd key such as
#      Depth):
#        - match found -> source value(s) copied into the target
#                         column(s) of that Master row
#        - no match    -> target cell(s) left as they were (blank
#                         for new columns)
#   4. Download the finished Master file as .xlsx.
#
#  Re-running "Run Merge" always rebuilds from the ORIGINAL Master
#  file, so changing a mapping and merging again never double-
#  applies old results.
# =============================================================

import io
import os

import numpy as np
import pandas as pd
import streamlit as st

# How many input-file tabs to show. Raise this if you regularly
# have more source files than this to merge in at once.
N_SLOTS = 6
NONE = "(none)"


# ------------------------------------------------------------
#  Shared helpers (name identification / matching process)
# ------------------------------------------------------------
def normalize_key(v):
    """Trim spaces, upper-case, compare as text. Blank cells -> None (never match)."""
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)  # 1.0 -> "1", like R's as.character()
    return str(v).strip().upper()


def build_key(df, key1, key2=None):
    """Lookup key per row: key1, or key1||key2 if a 2nd key column is given."""
    if not key1 or key1 not in df.columns:
        return [None] * len(df)
    k = [normalize_key(v) for v in df[key1]]
    if key2 and key2 != NONE and key2 in df.columns:
        k2 = [normalize_key(v) for v in df[key2]]
        k = [None if (a is None or b is None) else f"{a}||{b}" for a, b in zip(k, k2)]
    return k


@st.cache_data(show_spinner=False)
def get_sheet_names(data: bytes):
    return pd.ExcelFile(io.BytesIO(data)).sheet_names


@st.cache_data(show_spinner=False)
def read_sheet(data: bytes, sheet: str):
    df = pd.read_excel(io.BytesIO(data), sheet_name=sheet)
    df.columns = [str(c) for c in df.columns]
    return df


def run_merge(master_df, mk1, mk2, slots):
    """Apply every configured input file to a fresh copy of the Master."""
    out = master_df.copy()
    master_key = build_key(out, mk1, mk2)
    stats = []

    for s in slots:
        if s is None or not s["key1"] or not s["tmap"]:
            continue
        in_df = s["df"]
        in_key = build_key(in_df, s["key1"], s["key2"])

        # first occurrence wins for duplicate keys (same as R's match())
        lookup = {}
        for pos, k in enumerate(in_key):
            if k is not None and k not in lookup:
                lookup[k] = pos
        idx = np.array([lookup.get(k, -1) if k is not None else -1 for k in master_key], dtype=int)
        matched = idx >= 0

        for src, tgt in s["tmap"].items():
            if src not in in_df.columns:
                continue
            if len(in_df) == 0:
                vals = np.full(len(out), None, dtype=object)
            else:
                vals = in_df[src].to_numpy(dtype=object)[np.where(matched, idx, 0)]
            repl = pd.Series(vals, index=out.index, dtype=object)
            if tgt in out.columns:
                base = out[tgt].astype(object)
            else:
                base = pd.Series([None] * len(out), index=out.index, dtype=object)
            out[tgt] = base.where(~matched, repl).infer_objects()

        stats.append(
            dict(
                fileName=s["fileName"],
                n_total=len(master_key),
                n_matched=int(matched.sum()),
                n_missing=int((~matched).sum()),
                cols=", ".join(f"{a} -> {b}" for a, b in s["tmap"].items()),
            )
        )
    return out, stats


def to_xlsx_bytes(df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False)
    return buf.getvalue()


# ------------------------------------------------------------
#  One "Input File" tab
# ------------------------------------------------------------
def slot_ui(i):
    label = f"Input File {i}"
    up = st.file_uploader(f"{label} - Excel file", type=["xlsx", "xls"], key=f"file_{i}")
    if up is None:
        st.info("Upload a file to configure this tab (leave empty to skip it).")
        return None

    data = up.getvalue()
    tag = f"{i}_{up.name}_{len(data)}"  # resets defaults when the file changes
    try:
        sheets = get_sheet_names(data)
        sheet = st.selectbox("Sheet", sheets, key=f"sheet_{tag}")
        df = read_sheet(data, sheet)
    except Exception as e:
        st.error(f"Could not read this file: {e}")
        return None

    cols = list(df.columns)
    if not cols:
        st.warning("This sheet has no columns.")
        return None

    t = f"{tag}_{sheet}"
    c1, c2 = st.columns(2)
    key1 = c1.selectbox("Key column in THIS file", cols, key=f"key1_{t}")
    key2 = c2.selectbox("2nd key column (optional, e.g. Depth)", [NONE] + cols, key=f"key2_{t}")
    src = st.multiselect("Column(s) to copy into Master (source columns)", cols, key=f"src_{t}")
    st.caption(
        "Each copied column defaults to the same name in the Master file. "
        "Only edit a box below if you want that column renamed/placed under a "
        "different Master column name (new names are created automatically)."
    )

    tmap = {}
    for cn in src:
        v = st.text_input(f"Master column for '{cn}'", value=cn, key=f"tgt_{t}_{cn}")
        tmap[cn] = v.strip() or cn

    st.markdown("**Key preview (first 10 rows) - check this matches the Master's key format:**")
    st.code(str(build_key(df, key1, key2)[:10]))

    return dict(fileName=up.name, df=df, key1=key1, key2=key2, tmap=tmap)


# ---------------------------- UI ------------------------------
st.set_page_config(page_title="Excel Lookup & Merge Tool", layout="wide")
st.title("Excel Lookup & Merge Tool - Multi-File Edition")

left, right = st.columns([1, 2], gap="large")

# ---------- MASTER FILE ----------
master_df, mk1, mk2, master_name = None, None, NONE, None
with left:
    with st.container(border=True):
        st.subheader("1. Master file (the file that gets updated)")
        mf = st.file_uploader("Master Excel file", type=["xlsx", "xls"], key="master_file")
        if mf is not None:
            mdata = mf.getvalue()
            master_name = mf.name
            try:
                msheets = get_sheet_names(mdata)
                msheet = st.selectbox("Master sheet", msheets, key=f"msheet_{mf.name}_{len(mdata)}")
                master_df = read_sheet(mdata, msheet)
                mcols = list(master_df.columns)
                mt = f"{mf.name}_{len(mdata)}_{msheet}"
                mk1 = st.selectbox("Master key column (e.g. station name)", mcols, key=f"mk1_{mt}")
                mk2 = st.selectbox(
                    "Master 2nd key column (optional, e.g. Depth)", [NONE] + mcols, key=f"mk2_{mt}"
                )
                st.markdown("**Master key preview (first 10 rows):**")
                st.code(str(build_key(master_df, mk1, mk2)[:10]))
            except Exception as e:
                master_df = None
                st.error(f"Could not read the Master file: {e}")

# ---------- INPUT FILE TABS ----------
with right:
    st.subheader("2. Input files (data sources) - fill in as many tabs as you need")
    tabs = st.tabs([f"Input File {i}" for i in range(1, N_SLOTS + 1)])
    slots = []
    for i, tab in enumerate(tabs, start=1):
        with tab:
            slots.append(slot_ui(i))

# ---------- RUN + DOWNLOAD ----------
with left:
    with st.container(border=True):
        st.subheader("3. Run")
        if st.button("Run Merge (apply all files)", type="primary", use_container_width=True):
            if master_df is None or not mk1:
                st.warning("Upload the Master file and choose its key column first.")
            else:
                # always rebuild from the ORIGINAL master
                result, stats = run_merge(master_df, mk1, mk2, slots)
                if not stats:
                    st.session_state.pop("result", None)
                    st.session_state["stats"] = []
                    st.warning(
                        "Nothing to merge: no input file tabs are filled in yet (upload a file, "
                        "choose a key column and at least one column to copy in at least one tab)."
                    )
                else:
                    st.session_state["result"] = result
                    st.session_state["stats"] = stats
                    st.session_state["xlsx"] = to_xlsx_bytes(result)
                    base = os.path.splitext(master_name)[0]
                    st.session_state["out_name"] = f"{base}_updated.xlsx"
                    st.success(f"Merge complete - processed {len(stats)} input file(s). See the summary below.")

        if "result" in st.session_state:
            st.download_button(
                "Download Updated Master File",
                data=st.session_state["xlsx"],
                file_name=st.session_state["out_name"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

st.divider()
st.subheader("Merge Summary")
stats = st.session_state.get("stats")
if not stats:
    st.caption("Run the merge to see match statistics per input file.")
else:
    for st_ in stats:
        st.markdown(
            f"**{st_['fileName']}**  \n"
            f"Matched {st_['n_matched']} / {st_['n_total']} rows ({st_['n_missing']} left blank).  \n"
            f"<span style='color:#666'>Columns copied: {st_['cols']}</span>",
            unsafe_allow_html=True,
        )

st.divider()
st.subheader("Preview of result (after Run Merge)")
if "result" in st.session_state:
    res = st.session_state["result"]
    try:
        st.dataframe(res, use_container_width=True)
    except Exception:
        st.dataframe(res.astype(str), use_container_width=True)
