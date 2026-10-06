"""
EXCEL STATION NAME ARRANGER  (v2 - handles messy names)
Python / Streamlit version of station_name_sorter.R

Messy station names such as
    T4 - 01     T5 S2 S     T11S2 B     T7 - 01-10m     T1-S2-20m
are cleaned into a proper station name plus a Depth column
(T4 S1 | 10m ...), then the whole sheet is sorted.

RULES (same as the R program)
  * Station   : T<number> followed by S<number> (T4 S2) or by - <number> (T4 - 01).
                In the dash type the number IS the station: T4 - 01 = T4 S1.
  * S / M / B : one letter AFTER the station = Surface / Mid / Bottom.
  * Depth     : numbers such as 10m, 50m, or a bare 5 (= 5m).
  * Depth col : depth (10m) or layer letter (S/M/B); both are joined ("S 10m").
  * Other names (e.g. PAE_A48) are kept unchanged, blank Depth, placed at the bottom.

SORTING
  1. T number  2. Station number  3. Surface -> Mid -> Bottom
  4. Depth (small to large)  5. Original row order
  Non-T names come last, in natural order (PAE_A48, PAE_A69, ...).

Run:   pip install streamlit pandas openpyxl
       streamlit run station_name_sorter_app.py
"""

import io
import re

import pandas as pd
import streamlit as st

# ------------------------------------------------------------
# 1. STATION NAME PARSER
# ------------------------------------------------------------

PATTERN = re.compile(
    r"^T\s*(\d+)\s*"                       # T number
    r"(?:(?:-\s*)?S\s*(\d+)|-\s*(\d+))"    # S number (dash before S optional) OR - number
    r"\s*(?:-\s*)?"                        # optional dash
    r"(?:([SMB])\b)?"                      # layer letter (never followed by a digit)
    r"\s*(?:-\s*)?"                        # optional dash
    r"(?:(\d+(?:\.\d+)?)\s*M?)?$"          # depth, optional 'm'
)


def _normalise(x) -> str:
    """Upper-case, fix odd spaces/dashes, collapse whitespace."""
    if x is None or (not isinstance(x, str) and pd.isna(x)):
        return ""
    s = str(x).strip().upper()
    s = re.sub("[\u00A0\u2007\u202F]", " ", s)      # non-breaking spaces
    s = re.sub("[\u2010-\u2015\u2212]", "-", s)     # every kind of dash
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_station_names(values):
    """Return one dict per name: T_number, number, layer, depth (None if unknown)."""
    out = []
    for v in values:
        m = PATTERN.match(_normalise(v))
        if not m:
            out.append(dict(T_number=None, number=None, layer=None, depth=None))
            continue
        t, s_num, d_num, layer, depth = m.groups()
        num = s_num if s_num is not None else d_num
        out.append(
            dict(
                T_number=int(t),
                number=int(num),
                layer=layer,
                depth=float(depth) if depth is not None else None,
            )
        )
    return out


def natural_key(x) -> str:
    """A2 comes before A10."""
    s = "" if x is None or (not isinstance(x, str) and pd.isna(x)) else str(x).strip().lower()
    return re.sub(r"\d+", lambda m: str(int(m.group())).zfill(12), s)


def depth_to_text(d):
    return None if d is None else f"{d:g}m"


# ------------------------------------------------------------
# 2. FIND STATION COLUMN / ARRANGE DATA
# ------------------------------------------------------------

def find_station_columns(df: pd.DataFrame):
    """Columns where at least one value can be read as a T-station name."""
    found = []
    for col in df.columns:
        vals = [str(v).strip() for v in df[col].dropna()]
        vals = [v for v in vals if v]
        if vals and any(p["T_number"] is not None for p in parse_station_names(vals)):
            found.append(col)
    return found


def arrange(df: pd.DataFrame, station_col):
    """Return (arranged_df, raw_names, unrecognised_flags)."""
    df = df.copy()
    n = len(df)

    raw_names = ["" if pd.isna(v) else str(v).strip() for v in df[station_col]]
    parsed = parse_station_names(raw_names)
    unrec = [p["T_number"] is None for p in parsed]

    # Clean station name  "T4 S2"  (leading zeros removed)
    clean_station = [
        raw if u else f"T{p['T_number']} S{p['number']}"
        for raw, p, u in zip(raw_names, parsed, unrec)
    ]

    # Depth column = depth, or S/M/B, or both, or blank
    depth_col = []
    for p in parsed:
        d = depth_to_text(p["depth"])
        if p["layer"] and d:
            depth_col.append(f"{p['layer']} {d}")
        else:
            depth_col.append(p["layer"] or d)

    # Keep the file's own "Depth" column for rows where the name had no depth details
    existing = [
        c for c in df.columns
        if c != station_col and str(c).strip().lower() == "depth"
    ]
    if existing:
        old = [
            None if pd.isna(v) or str(v).strip() == "" else str(v).strip()
            for v in df[existing[0]]
        ]
        depth_col = [d if d is not None else o for d, o in zip(depth_col, old)]
        df = df.drop(columns=existing)

    # Put the clean name and Depth next to each other
    cols = list(df.columns)
    pos = cols.index(station_col)
    before = cols[:pos]
    after = [c for c in cols if c not in before and c != station_col and c != "Depth"]

    df[station_col] = clean_station
    df["Depth"] = depth_col
    df = df[before + [station_col, "Depth"] + after]

    # Sort the COMPLETE dataset so every column moves with its station
    rank = {"S": 1, "M": 2, "B": 3}

    def sort_key(i):
        p = parsed[i]
        return (
            unrec[i],                                   # T-stations first
            p["T_number"] or 0,
            p["number"] or 0,
            rank.get(p["layer"], 0),                    # no letter first
            p["depth"] if p["depth"] is not None else float("-inf"),
            natural_key(raw_names[i]),                  # non-T names: natural order
            i,                                          # original order last
        )

    order = sorted(range(n), key=sort_key)
    df = df.iloc[order].reset_index(drop=True)
    return df, raw_names, unrec


def to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Arranged") -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        sheet_name = str(sheet_name)[:31]
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets[sheet_name]
        for i, col in enumerate(df.columns, start=1):
            longest = max([len(str(col))] + [len(str(v)) for v in df[col].dropna()])
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = min(longest + 3, 45)
    return buf.getvalue()


# ------------------------------------------------------------
# 3. STREAMLIT APP
# ------------------------------------------------------------

def main():
    st.set_page_config(page_title="Station Name Arranger", page_icon="🌊", layout="wide")

    st.markdown(
        """
        <style>
        .hero {background: linear-gradient(120deg,#0b3c5d 0%,#1d70a2 60%,#3aa6b9 100%);
               padding: 1.6rem 2rem; border-radius: 16px; color: white; margin-bottom: 1.2rem;}
        .hero h1 {margin: 0; font-size: 2rem; color: white;}
        .hero p {margin: .3rem 0 0 0; opacity: .9;}
        div[data-testid="stMetric"] {background: #f3f8fb; border: 1px solid #d5e5ee;
               padding: .8rem 1rem; border-radius: 12px;}
        div[data-testid="stMetric"] * {color: #0b3c5d !important;}
        </style>
        <div class="hero">
          <h1>🌊 Excel Station Name Arranger</h1>
          <p>Clean messy station names, add a Depth column and sort everything in the right order.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("How the names are cleaned and sorted"):
        st.markdown(
            """
            **Station:** `T4 S2` or dash type `T4 - 01` (the dash number *is* the station → `T4 S1`).
            **S / M / B:** a single letter after the station = Surface / Mid / Bottom.
            **Depth:** `10m`, `50m`, or a bare `5` (= 5m). If both letter and depth exist: `S 10m`.
            **Other names** (e.g. `PAE_A48`) are kept unchanged, with blank Depth, at the bottom.

            **Sorting:** T number → station number → Surface / Mid / Bottom → depth → original row order.
            Your original file is never changed; you download a new arranged file.
            """
        )

    uploaded = st.file_uploader("Select the Excel file", type=["xlsx", "xlsm", "xls"])
    if uploaded is None:
        st.info("Upload an Excel file to begin, then choose the sheet you want to arrange.")
        return

    try:
        workbook = pd.ExcelFile(uploaded)
        sheet_names = workbook.sheet_names
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not read the Excel file: {e}")
        return

    if len(sheet_names) == 1:
        sheet = sheet_names[0]
        st.caption(f"Sheet: **{sheet}** (only sheet in the file)")
    else:
        sheet = st.selectbox(f"Select the sheet ({len(sheet_names)} found)", sheet_names)

    try:
        data = workbook.parse(sheet)
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not read sheet '{sheet}': {e}")
        return

    if data.shape[1] == 0:
        st.error("The selected Excel file contains no columns.")
        return
    if data.shape[0] == 0:
        st.error("The selected Excel file contains no data.")
        return

    st.success(f"Loaded **{uploaded.name}** / sheet **{sheet}** — {len(data)} rows, {data.shape[1]} columns")

    with st.expander("Columns found in the Excel file"):
        for i, c in enumerate(data.columns, start=1):
            st.write(f"{i} : {c}")

    # ---- station column ----
    candidates = find_station_columns(data)
    if not candidates:
        st.warning("Could not automatically identify the station-name column.")
        station_col = st.selectbox("Choose the column containing station names (Tx Sy)", list(data.columns))
    elif len(candidates) == 1:
        station_col = candidates[0]
        st.info(f"Station-name column automatically identified as: **{station_col}**")
    else:
        st.warning("More than one possible station-name column was found.")
        station_col = st.selectbox("Choose the correct station-name column", candidates)

    result, raw_names, unrec = arrange(data, station_col)

    # ---- summary ----
    c1, c2, c3 = st.columns(3)
    c1.metric("Rows arranged", len(result))
    c2.metric("T-stations", len(result) - sum(unrec))
    c3.metric("Other names (kept as is)", sum(unrec))

    if any(unrec):
        with st.expander(f"Names that are not T-stations ({sum(unrec)}) — kept unchanged at the bottom"):
            st.dataframe(
                pd.DataFrame(
                    {"Excel row": [i + 2 for i, u in enumerate(unrec) if u],   # +1 header, +1 for 1-based
                     "Name": [raw_names[i] for i, u in enumerate(unrec) if u]}
                ),
                hide_index=True,
                use_container_width=True,
            )

    # ---- results ----
    show = result.fillna("").astype(str)
    tab1, tab2 = st.tabs(["Arranged data", "First 20 stations"])
    with tab1:
        st.dataframe(show, use_container_width=True, hide_index=True, height=480)
    with tab2:
        st.dataframe(show[[station_col, "Depth"]].head(20), use_container_width=True, hide_index=True)
        if len(show) > 20:
            st.caption(f"... and {len(show) - 20} more rows.")

    st.download_button(
        "⬇️  Download arranged_station_data.xlsx",
        data=to_excel_bytes(result, sheet),
        file_name="arranged_station_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )
    st.caption("Original Excel file was not changed.")


if __name__ == "__main__":
    main()
