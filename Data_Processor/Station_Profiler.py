# -*- coding: utf-8 -*-
# ============================================================
# VERTICAL SECTION PROFILER   (Python / Streamlit version of code-04.R)
# ============================================================
#
# Purpose:
#   Create an ODV-style vertical section for ONE station
#   number across MULTIPLE transects.
#
# Example:
#   Selected station = S1
#
#   T1 S1
#   T2 S1
#   T3 S1
#   T4 S1
#
# X-axis = Transect
# Y-axis = Depth (m)
# Z-axis = Selected parameter / colour
#
# Interpolation = IDW
#
# RUN:    streamlit run Station_Profiler.py
#
# ============================================================


# ------------------------------------------------------------
# 1. REQUIRED PACKAGES
# ------------------------------------------------------------
#
#   pip install streamlit numpy pandas openpyxl matplotlib pillow
#
# (readxl -> pandas/openpyxl, dplyr/stringr -> pandas, ggplot2/scales -> matplotlib,
#  gstat/sp -> numpy IDW)

import io
import os
import re

import numpy as np
import pandas as pd
import streamlit as st

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize

plt.rcParams["font.sans-serif"] = ["Arial", "Helvetica", "DejaVu Sans"]

APP_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(APP_DIR, "outputs")   # folder where the TIFF is saved

# Everything R prints with cat()/print() is collected here and shown in the app.
_LOG = []
_WARNINGS = []


def cat(*args, sep=" "):
    _LOG.append(sep.join(str(a) for a in args))


def num(v):
    return f"{v:.7g}"


# ------------------------------------------------------------
# 12. TRANSECT NAMES
# ------------------------------------------------------------
#
# ADD YOUR REAL TRANSECT / PLACE NAMES HERE.
#
# Current information:
#
# T1 = Uvari
# T2 = Cape
# T3 = Colachel
# T4 = Kollam
#
# You can continue later:
#
# T5 = "Your place"
# T6 = "Your place"
# T7 = "Your place"
# T8 = "Your place"
#
# ------------------------------------------------------------

transect_names = {

    "T1": "Uvari",
    "T2": "Cape",
    "T3": "Colachel",
    "T4": "Kollam",

    # Add more here when required:
    # "T5": "XXXXX",
    # "T6": "XXXXX",
    # "T7": "XXXXX",
    # "T8": "XXXXX",

}


# ------------------------------------------------------------
# 21. IDW INTERPOLATION  (gstat: idp = 2, nmax = 12)
# ------------------------------------------------------------
def idw_nmax(x, y, z, gx, gy, idp=2, nmax=12, chunk=20000):
    """Inverse distance weighting using the `nmax` nearest observations."""
    n = len(x)
    k = min(nmax, n)
    gxf, gyf = gx.ravel(), gy.ravel()
    out = np.empty(len(gxf))
    for s in range(0, len(gxf), chunk):
        sl = slice(s, s + chunk)
        d = np.hypot(gxf[sl, None] - x[None, :], gyf[sl, None] - y[None, :])
        if k < n:
            idx = np.argpartition(d, k - 1, axis=1)[:, :k]
            d = np.take_along_axis(d, idx, axis=1)
            zz = z[idx]
        else:
            zz = np.broadcast_to(z, d.shape)
        hit = d == 0
        with np.errstate(divide="ignore"):
            w = 1.0 / d ** idp
        w[hit] = 0.0
        pred = (w * zz).sum(axis=1) / w.sum(axis=1)
        anyhit = hit.any(axis=1)
        if anyhit.any():
            pred[anyhit] = (zz * hit).sum(axis=1)[anyhit] / hit.sum(axis=1)[anyhit]
        out[sl] = pred
    return out.reshape(gx.shape)


def find_column(columns, wanted):
    """Excel header that matches `wanted` (ignoring upper/lower case and spaces at the ends)."""
    for c in columns:
        if str(c).strip().lower() == wanted.strip().lower():
            return c
    return None


# ============================================================
#  MAIN PIPELINE   (sections 2 - 26 of the R script)
# ============================================================
def run_profiler(data_raw, excel_name, sheet_name, selected_station, parameter_column):
    _LOG.clear()
    _WARNINGS.clear()

    # ------------------------------------------------------------
    # 2. SELECT EXCEL FILE  /  3. READ SHEET   (done in the app: file + sheet are chosen in the sidebar)
    # ------------------------------------------------------------
    cat("\nExcel file selected:\n")
    cat(excel_name, "\n")
    cat("\nSheet selected:\n")
    cat(sheet_name, "\n")

    cat("\nColumns detected:\n")
    cat(list(data_raw.columns), "\n")

    # ------------------------------------------------------------
    # 4. DEFINE IMPORTANT COLUMN NAMES
    #    (this Excel writes them as "station name" and "Depth (m)")
    # ------------------------------------------------------------
    station_column = find_column(data_raw.columns, "Station Name")
    depth_column = find_column(data_raw.columns, "depth (m)")

    # ------------------------------------------------------------
    # 7. CHECK REQUIRED COLUMNS
    # ------------------------------------------------------------
    avail = "\n".join(str(c) for c in data_raw.columns)
    if station_column is None:
        st.error(f"ERROR: 'Station Name' column was not found.\n\nAvailable columns:\n{avail}")
        st.stop()
    if depth_column is None:
        st.error(f"ERROR: 'depth (m)' column was not found.\n\nAvailable columns:\n{avail}")
        st.stop()
    if parameter_column not in list(data_raw.columns):
        st.error(f"ERROR: '{parameter_column}' column was not found.\n\nAvailable columns:\n{avail}")
        st.stop()

    # ------------------------------------------------------------
    # 8. PREPARE DATA
    #    Depth is written like "0m", "5m", "10m" in this Excel -> keep the number
    # ------------------------------------------------------------
    data = pd.DataFrame({
        "Station": data_raw[station_column].map(lambda v: None if pd.isna(v) else str(v)),
        "Depth": pd.to_numeric(
            data_raw[depth_column].astype(str).str.extract(r"(-?\d+(?:\.\d+)?)")[0],
            errors="coerce"),
        "Value": pd.to_numeric(data_raw[parameter_column], errors="coerce"),
    })
    data = data[data["Station"].notna() & data["Depth"].notna()].reset_index(drop=True)

    # ------------------------------------------------------------
    # 9. EXTRACT TRANSECT FROM STATION NAME
    # ------------------------------------------------------------
    data["Transect"] = data["Station"].str.extract(r"^(T[0-9]+)")[0]

    # ------------------------------------------------------------
    # 10. EXTRACT STATION NUMBER
    # ------------------------------------------------------------
    data["StationNumber"] = data["Station"].str.extract(r"(S[0-9]+)")[0]

    # ------------------------------------------------------------
    # 11. KEEP ONLY THE SELECTED STATION
    # ------------------------------------------------------------
    station_data = data[data["StationNumber"] == selected_station].copy()

    if len(station_data) == 0:
        found = sorted(data["StationNumber"].dropna().unique())
        st.error(f"No data found for station {selected_station}.\n\n"
                 "Stations available in the Excel file:\n" + "\n".join(found))
        st.stop()

    # ------------------------------------------------------------
    # 13. CHECK THAT TRANSECT NAMES EXIST
    # ------------------------------------------------------------
    detected_transects = list(station_data["Transect"].dropna().unique())

    missing_names = [t for t in detected_transects if t not in transect_names]

    if len(missing_names) > 0:
        _WARNINGS.append(
            "The following transects do not yet have a place name:\n"
            + ", ".join(missing_names)
            + "\n\nTheir T-number will be used temporarily."
        )

    # ------------------------------------------------------------
    # 14. SET TRANSECT ORDER   (T1, T2, T3 ... numerically)
    # ------------------------------------------------------------
    transect_order = sorted(detected_transects, key=lambda t: int(re.search(r"[0-9]+", t).group()))
    transect_order = [t for t in transect_order if t in detected_transects]

    # ------------------------------------------------------------
    # 15. CREATE X POSITION  (T1 = 1, T2 = 2, ...)
    # ------------------------------------------------------------
    x_pos = {t: i + 1 for i, t in enumerate(transect_order)}
    station_data["X"] = station_data["Transect"].map(x_pos)

    # ------------------------------------------------------------
    # 16. CHECK AVAILABLE DEPTHS
    # ------------------------------------------------------------
    available_depths = [float(d) for d in sorted(station_data["Depth"].unique())]

    cat("\nDepths found for selected station:\n")
    cat([f"{d:g}" for d in available_depths], "\n")

    # ------------------------------------------------------------
    # 17. VALID DATA FOR IDW   (missing values are NOT converted to zero)
    # ------------------------------------------------------------
    idw_data = station_data[station_data["Value"].notna() & np.isfinite(station_data["Value"])]

    if len(idw_data) < 3:
        st.error("Not enough valid observations for IDW interpolation.")
        st.stop()

    # ------------------------------------------------------------
    # 18. AUTOMATIC PARAMETER MINIMUM AND MAXIMUM
    # ------------------------------------------------------------
    parameter_min = idw_data["Value"].min()
    parameter_max = idw_data["Value"].max()

    cat("\n--------------------------------------\n")
    cat("Selected station :", selected_station, "\n")
    cat("Selected parameter:", parameter_column, "\n")
    cat("Minimum value     :", num(parameter_min), "\n")
    cat("Maximum value     :", num(parameter_max), "\n")
    cat("--------------------------------------\n")

    # ------------------------------------------------------------
    # 19. CREATE IDW GRID   (X = transect position, Y = depth)
    # ------------------------------------------------------------
    x_min = station_data["X"].min()
    x_max = station_data["X"].max()

    y_min = station_data["Depth"].min()
    y_max = station_data["Depth"].max()

    if x_min == x_max or y_min == y_max:
        st.error("The vertical section needs at least 2 transects and 2 depths for this station.")
        st.stop()

    nx = ny = 300
    gX, gD = np.meshgrid(np.linspace(x_min, x_max, nx), np.linspace(y_min, y_max, ny))

    # ------------------------------------------------------------
    # 20. PREPARE DATA FOR GSTAT   /   21. IDW INTERPOLATION (idp = 2, nmax = 12)
    # ------------------------------------------------------------
    cat("\nRunning IDW interpolation...\n")

    pred = idw_nmax(idw_data["X"].to_numpy(float), idw_data["Depth"].to_numpy(float),
                    idw_data["Value"].to_numpy(float), gX, gD, idp=2, nmax=12)

    # ------------------------------------------------------------
    # 22. CONVERT IDW OUTPUT TO DATA FRAME
    # ------------------------------------------------------------
    idw_plot = pd.DataFrame({"X": gX.ravel(), "Depth": gD.ravel(), "Value": pred.ravel()})

    # ------------------------------------------------------------
    # 23. CREATE TRANSECT LABELS
    # ------------------------------------------------------------
    transect_label_vector = [transect_names[t] if t in transect_names else t
                             for t in transect_order]

    # ------------------------------------------------------------
    # 24. CREATE PROFILER
    # ------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 7), layout="constrained")
    fig.patch.set_facecolor("white")

    cmap = LinearSegmentedColormap.from_list("profiler", [
        "#313695",
        "#4575B4",
        "#74ADD1",
        "#ABD9E9",
        "#E0F3F8",
        "#FFFFBF",
        "#FEE090",
        "#FDAE61",
        "#F46D43",
        "#D73027",
        "#A50026",
    ])
    norm = Normalize(vmin=parameter_min, vmax=parameter_max, clip=True)

    # IDW COLOUR FIELD   (geom_raster)
    dx = (x_max - x_min) / (nx - 1)
    dy = (y_max - y_min) / (ny - 1)
    x_lo, x_hi = x_min - dx / 2, x_max + dx / 2
    y_lo, y_hi = y_min - dy / 2, y_max + dy / 2
    im = ax.imshow(idw_plot["Value"].to_numpy().reshape(ny, nx), cmap=cmap, norm=norm,
                   origin="lower", extent=[x_lo, x_hi, y_lo, y_hi], aspect="auto",
                   interpolation="nearest", zorder=1)

    # ACTUAL OBSERVATION POINTS   (shape 21, size 2.2, stroke 0.5, fill white)
    pts = station_data[station_data["Value"].notna()]
    ax.scatter(pts["X"], pts["Depth"], s=40, marker="o", facecolors="white",
               edgecolors="black", linewidths=0.7, zorder=3)

    # DEPTH AXIS   (scale_y_reverse, breaks = available_depths, expand = 0)
    ax.set_ylim(y_hi, y_lo)
    ax.set_yticks(available_depths)
    ax.set_yticklabels([f"{d:g}" for d in available_depths])

    # X-AXIS   (breaks = 1..n, labels = transect names, expand = 0)
    ax.set_xlim(x_lo, x_hi)
    ax.set_xticks(range(1, len(transect_order) + 1))
    ax.set_xticklabels(transect_label_vector, fontsize=11, rotation=0, ha="center")

    # AXIS LABELS
    ax.set_ylabel("Depth (m)", fontsize=11)

    # THEME   (theme_bw, no grid, legend on the right)
    ax.tick_params(axis="y", labelsize=10)
    ax.tick_params(axis="both", colors="#333333", labelcolor="#4D4D4D")
    for s in ax.spines.values():
        s.set_color("#333333")
        s.set_linewidth(0.8)

    cb = fig.colorbar(im, ax=ax, shrink=0.3, aspect=6, pad=0.02)
    cb.ax.set_title(parameter_column, fontsize=10, loc="left")
    cb.ax.tick_params(labelsize=9, colors="#4D4D4D")
    cb.outline.set_visible(False)

    # ------------------------------------------------------------
    # 25. DISPLAY PROFILER
    # ------------------------------------------------------------
    png = io.BytesIO()
    fig.savefig(png, format="png", dpi=110, facecolor="white")

    # ------------------------------------------------------------
    # 26. EXPORT TIFF
    # ------------------------------------------------------------
    output_file = (
        selected_station
        + "_"
        + re.sub(r"[^A-Za-z0-9]+", "_", parameter_column)
        + "_Vertical_Profiler_IDW.tif"
    )

    tiff = io.BytesIO()
    fig.savefig(tiff, format="tiff", dpi=600, facecolor="white",
                pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    saved_to = os.path.join(OUTPUT_DIR, output_file)
    with open(saved_to, "wb") as f:
        f.write(tiff.getvalue())

    cat("\n--------------------------------------\n")
    cat("Profiler saved as:\n")
    cat(saved_to, "\n")
    cat("--------------------------------------\n")

    return {"png": png.getvalue(), "tiff": tiff.getvalue(), "filename": output_file,
            "saved_to": saved_to, "log": "".join(_LOG), "warnings": list(_WARNINGS)}


# ============================================================
#  STREAMLIT APP
# ============================================================
def main():
    st.set_page_config(page_title="Vertical Section Profiler", page_icon="🌊", layout="wide")
    st.title("VERTICAL SECTION PROFILER")
    st.caption("ODV-style vertical section for ONE station number across MULTIPLE transects (IDW)")

    # ------------------------------------------------------------
    # 2. SELECT EXCEL FILE
    # ------------------------------------------------------------
    st.sidebar.header("Excel selection")
    excel_upload = st.sidebar.file_uploader("Select Excel file", type=["xlsx", "xlsm", "xls"])

    res = st.session_state.get("profiler_result")

    if excel_upload is None:
        st.info("Upload an Excel file in the sidebar to begin.")
        if res:
            _show_result(res)
        return

    # ------------------------------------------------------------
    # 3. READ SHEET   (any sheet can be selected)
    # ------------------------------------------------------------
    try:
        xl = pd.ExcelFile(excel_upload)
    except Exception as e:  # noqa
        st.error(f"Could not read the Excel file: {e}")
        return
    sheet_name = st.sidebar.selectbox("Excel sheet", xl.sheet_names)
    data_raw = pd.read_excel(xl, sheet_name=sheet_name)
    excel_name = excel_upload.name

    with st.expander(f"Preview of sheet '{sheet_name}'  ({data_raw.shape[0]} rows x "
                     f"{data_raw.shape[1]} columns)"):
        st.dataframe(data_raw.head(30))

    # ------------------------------------------------------------
    # 5. SELECT THE STATION NUMBER   (e.g. S1 -> T1 S1, T2 S1, T3 S1 ...)
    # ------------------------------------------------------------
    station_column = find_column(data_raw.columns, "Station Name")
    if station_column is None:
        st.error("ERROR: 'Station Name' column was not found.\n\nAvailable columns:\n"
                 + "\n".join(str(c) for c in data_raw.columns))
        return
    stn_numbers = (data_raw[station_column].astype(str).str.extract(r"(S[0-9]+)")[0]
                   .dropna().unique().tolist())
    stn_numbers = sorted(stn_numbers, key=lambda s: int(s[1:]))
    if not stn_numbers:
        st.error("No station numbers like 'S1' were found in the Station Name column.")
        return
    selected_station = st.sidebar.selectbox("Station number (selected_station)", stn_numbers,
                                            key=f"stn_{sheet_name}")

    # ------------------------------------------------------------
    # 6. SELECT PARAMETER TO PLOT   (exact column name from Excel)
    # ------------------------------------------------------------
    skip = ("station", "depth", "latitude", "longitude")
    param_options = [str(c) for c in data_raw.columns
                     if not str(c).strip().lower().startswith(skip)]
    if not param_options:
        st.error("No parameter columns found in this sheet.")
        return
    parameter_column = st.sidebar.selectbox("Parameter (parameter_column)", param_options,
                                            key=f"par_{sheet_name}")

    if st.sidebar.button("Generate profiler", type="primary"):
        with st.spinner("Running IDW interpolation and drawing the profiler..."):
            st.session_state["profiler_result"] = run_profiler(
                data_raw, excel_name, sheet_name, selected_station, parameter_column)
        res = st.session_state.get("profiler_result")

    if res:
        _show_result(res)
    else:
        st.info("Choose the sheet, station number and parameter in the sidebar, "
                "then press **Generate profiler**.")


def _show_result(res):
    for w in res.get("warnings", []):
        st.warning(w)
    st.image(res["png"])
    st.download_button("Download profiler (TIFF)", data=res["tiff"], file_name=res["filename"],
                       mime="image/tiff")
    st.success(f"Profiler saved as: {res['saved_to']}")
    with st.expander("Console output"):
        st.code(res["log"])


if __name__ == "__main__":
    main()
