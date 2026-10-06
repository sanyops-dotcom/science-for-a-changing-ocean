# -*- coding: utf-8 -*-
# ============================================================
# TRANSECT-WISE VERTICAL SECTION PROFILER
# ODV-STYLE PROFILE WITH IDW + BATHYMETRY MASK
# (Python / Streamlit version of code-05.R)
# ============================================================
#
# PURPOSE:
#   Plot ONE transect containing MULTIPLE stations.
#
# Example:
#   T1 -> S1, S2, S3, S4, S5, S6, S7...
#
# X-axis = Station
# Y-axis = Depth (m)
# Colour = Selected parameter
# Interpolation = IDW
# Bottom = Bathymetry mask
#
# Missing parameter values:
#   Circle + small cross
#
# RUN:    streamlit run Transect_profiler.py
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
from matplotlib.patches import Polygon

plt.rcParams["font.sans-serif"] = ["Arial", "Helvetica", "DejaVu Sans"]

APP_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(APP_DIR, "outputs")   # folder where the TIFF is saved

PT = 72.27 / 25.4                 # ggplot2 .pt  (mm -> pt)

# Everything R prints with cat()/print() is collected here and shown in the app.
_LOG = []


def cat(*args, sep=" "):
    _LOG.append(sep.join(str(a) for a in args))


def num(v):
    return f"{v:.7g}"


# ------------------------------------------------------------
# R's pretty()  (used in section 26)
# ------------------------------------------------------------
def r_pretty(lo, up, n=5):
    """Port of R's pretty(c(lo, up), n)."""
    min_n = n // 3
    shrink_sml, h, h5 = 0.75, 1.5, 0.5 + 1.5 * 1.5
    eps = np.finfo(float).eps
    dx = up - lo
    if dx == 0 and up == 0:
        cell, i_small = 1.0, True
    else:
        cell = max(abs(lo), abs(up))
        U = 1 + (1 / (1 + h) if h5 >= 1.5 * h + 0.5 else 1.5 / (1 + h5))
        U *= max(1, n) * eps
        i_small = dx < cell * U * 3
    if i_small:
        if cell > 10:
            cell = 9 + cell / 10
        cell *= shrink_sml
        if min_n > 1:
            cell /= min_n
    else:
        cell = dx
        if n > 1:
            cell /= n
    base = 10.0 ** np.floor(np.log10(cell))
    unit = base
    if 2 * base - cell < h * (cell - unit):
        unit = 2 * base
        if 5 * base - cell < h5 * (cell - unit):
            unit = 5 * base
            if 10 * base - cell < h * (cell - unit):
                unit = 10 * base
    ns = np.floor(lo / unit + 1e-7)
    nu = np.ceil(up / unit - 1e-7)
    while ns * unit > lo + 1e-10 * unit:
        ns -= 1
    while nu * unit < up - 1e-10 * unit:
        nu += 1
    k = int(0.5 + nu - ns)
    if k < min_n:
        k = min_n - k
        if ns >= 0:
            nu += k // 2
            ns -= k // 2 + k % 2
        else:
            ns -= k // 2
            nu += k // 2 + k % 2
    return np.round(np.arange(ns, nu + 1) * unit, 12)


# ------------------------------------------------------------
# 20. RUN IDW  (gstat: idp = 2, nmax = 12)
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
#  MAIN PIPELINE   (sections 2 - 30 of the R script)
# ============================================================
def run_profiler(data_raw, excel_name, sheet_name, selected_transect, parameter_column):
    _LOG.clear()

    # ------------------------------------------------------------
    # 2. SELECT EXCEL FILE  /  3. READ EXCEL SHEET   (done in the app: file + sheet are chosen in the sidebar)
    # ------------------------------------------------------------
    cat("\nExcel file selected:\n")
    cat(excel_name, "\n")
    cat("\nSheet selected:\n")
    cat(sheet_name, "\n")

    cat("\nColumns detected:\n")
    cat(list(data_raw.columns), "\n")

    # ------------------------------------------------------------
    # 4. COLUMN NAMES
    #    (this Excel writes them as "station name" and "Depth (m)")
    # ------------------------------------------------------------
    station_column = find_column(data_raw.columns, "Station Name")
    depth_column = find_column(data_raw.columns, "depth (m)")

    # ------------------------------------------------------------
    # 7. CHECK COLUMNS
    # ------------------------------------------------------------
    avail = "\n".join(str(c) for c in data_raw.columns)
    if station_column is None:
        st.error(f"ERROR: Column 'Station Name' was not found.\n\nAvailable columns:\n{avail}")
        st.stop()
    if depth_column is None:
        st.error(f"ERROR: Column 'depth (m)' was not found.\n\nAvailable columns:\n{avail}")
        st.stop()
    if parameter_column not in list(data_raw.columns):
        st.error(f"ERROR: Parameter column '{parameter_column}' was not found.\n\n"
                 f"Available columns:\n{avail}")
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
    # 9. EXTRACT TRANSECT
    # ------------------------------------------------------------
    data["Transect"] = data["Station"].str.extract(r"^(T[0-9]+)")[0]

    # ------------------------------------------------------------
    # 10. EXTRACT STATION NUMBER
    # ------------------------------------------------------------
    data["StationNumber"] = data["Station"].str.extract(r"(S[0-9]+)")[0]

    # ------------------------------------------------------------
    # 11. KEEP ONLY SELECTED TRANSECT
    # ------------------------------------------------------------
    transect_data = data[data["Transect"] == selected_transect].copy()

    if len(transect_data) == 0:
        found = sorted(data["Transect"].dropna().unique())
        st.error(f"No data found for {selected_transect}.\n\nAvailable transects:\n"
                 + "\n".join(found))
        st.stop()

    # ------------------------------------------------------------
    # 12. ORDER STATIONS NUMERICALLY   (S1, S2, ... S10)
    # ------------------------------------------------------------
    station_order = sorted(transect_data["StationNumber"].dropna().unique(),
                           key=lambda s: int(re.search(r"[0-9]+", s).group()))

    # ------------------------------------------------------------
    # 13. CREATE X POSITION
    # ------------------------------------------------------------
    x_pos = {s: i + 1 for i, s in enumerate(station_order)}
    transect_data["X"] = transect_data["StationNumber"].map(x_pos)

    # ------------------------------------------------------------
    # 14. FIND ACTUAL DEPTH RANGE
    # ------------------------------------------------------------
    min_depth = transect_data["Depth"].min()
    max_depth = transect_data["Depth"].max()

    cat("\n--------------------------------------\n")
    cat("Selected transect :", selected_transect, "\n")
    cat("Stations          :", len(station_order), "\n")
    cat("Minimum depth     :", num(min_depth), "m\n")
    cat("Maximum depth     :", num(max_depth), "m\n")
    cat("--------------------------------------\n")

    # ------------------------------------------------------------
    # 15. BATHYMETRY DEPTH FOR EACH STATION
    #     (deepest ACTUAL depth at each station = local ocean bottom)
    # ------------------------------------------------------------
    bathymetry = (transect_data.dropna(subset=["StationNumber"])
                  .groupby("StationNumber", sort=False)
                  .agg(X=("X", "first"), BottomDepth=("Depth", "max"))
                  .reset_index()
                  .sort_values("X").reset_index(drop=True))

    # ------------------------------------------------------------
    # 16. VALID DATA FOR IDW   (missing values are NOT converted to zero)
    # ------------------------------------------------------------
    idw_data = transect_data[transect_data["Value"].notna() & np.isfinite(transect_data["Value"])]

    if len(idw_data) < 3:
        st.error("Not enough valid observations for IDW interpolation.")
        st.stop()

    # ------------------------------------------------------------
    # 17. AUTOMATIC PARAMETER RANGE
    # ------------------------------------------------------------
    parameter_min = idw_data["Value"].min()
    parameter_max = idw_data["Value"].max()

    cat("\nParameter:", parameter_column, "\n")
    cat("Minimum  :", num(parameter_min), "\n")
    cat("Maximum  :", num(parameter_max), "\n")

    # ------------------------------------------------------------
    # 18. CREATE IDW GRID   (covers the complete depth range)
    # ------------------------------------------------------------
    x_min = transect_data["X"].min()
    x_max = transect_data["X"].max()

    if x_min == x_max or min_depth == max_depth:
        st.error("The vertical section needs at least 2 stations and 2 depths in this transect.")
        st.stop()

    nx = ny = 400
    gX, gD = np.meshgrid(np.linspace(x_min, x_max, nx), np.linspace(min_depth, max_depth, ny))

    # ------------------------------------------------------------
    # 19. CONVERT DATA TO SPATIAL OBJECT  /  20. RUN IDW  (idp = 2, nmax = 12)
    # ------------------------------------------------------------
    cat("\nRunning IDW interpolation...\n")

    pred = idw_nmax(idw_data["X"].to_numpy(float), idw_data["Depth"].to_numpy(float),
                    idw_data["Value"].to_numpy(float), gX, gD, idp=2, nmax=12)

    # ------------------------------------------------------------
    # 21. CONVERT IDW RESULT
    # ------------------------------------------------------------
    idw_plot = pd.DataFrame({"X": gX.ravel(), "Depth": gD.ravel(), "Value": pred.ravel()})

    # ------------------------------------------------------------
    # 22. BATHYMETRY MASK
    #     (linear interpolation ONLY for the bottom boundary, NOT for parameter values)
    # ------------------------------------------------------------
    bottom_depth_at_x = np.interp(idw_plot["X"].to_numpy(),
                                  bathymetry["X"].to_numpy(float),
                                  bathymetry["BottomDepth"].to_numpy(float))   # rule = 2

    idw_plot["BottomDepth"] = bottom_depth_at_x

    # ------------------------------------------------------------
    # 23. REMOVE EVERYTHING BELOW OCEAN BOTTOM
    # ------------------------------------------------------------
    idw_plot = idw_plot[idw_plot["Depth"] <= idw_plot["BottomDepth"]]

    # ------------------------------------------------------------
    # 24. PREPARE OBSERVATION POINTS   (missing parameter observations are retained)
    # ------------------------------------------------------------
    observation_points = transect_data.copy()
    observation_points["ParameterMissing"] = observation_points["Value"].isna()

    # ------------------------------------------------------------
    # 25. PREPARE BATHYMETRY POLYGON   (dark-brown ocean-bottom area)
    # ------------------------------------------------------------
    bathymetry_polygon = pd.concat([
        pd.DataFrame({"X": bathymetry["X"], "Depth": bathymetry["BottomDepth"]}),
        pd.DataFrame({"X": bathymetry["X"][::-1].to_numpy(),
                      "Depth": np.repeat(max_depth, len(bathymetry))}),
    ], ignore_index=True)

    # ------------------------------------------------------------
    # 26. DEPTH AXIS   (preferred depth labels inside the actual depth range)
    # ------------------------------------------------------------
    standard_depths = np.array([
        0,
        5,
        10,
        20,
        30,
        50,
        75,
        100,
        200,
        500,
        750,
        1000,
        1500,
        2000,
    ], dtype=float)

    depth_breaks = standard_depths[(standard_depths >= min_depth) & (standard_depths <= max_depth)]

    if len(depth_breaks) < 2:
        depth_breaks = r_pretty(min_depth, max_depth, n=8)

    # ------------------------------------------------------------
    # 27. CREATE VERTICAL SECTION
    # ------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(12, 8), layout="constrained")
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

    # IDW COLOUR FIELD   (geom_raster; cells below the ocean bottom are removed)
    dx = (x_max - x_min) / (nx - 1)
    dy = (max_depth - min_depth) / (ny - 1)
    V = np.full(nx * ny, np.nan)
    V[idw_plot.index.to_numpy()] = idw_plot["Value"].to_numpy()
    V = V.reshape(ny, nx)
    im = ax.imshow(V, cmap=cmap, norm=norm, origin="lower", aspect="auto",
                   interpolation="nearest", zorder=1,
                   extent=[x_min - dx / 2, x_max + dx / 2,
                           min_depth - dy / 2, max_depth + dy / 2])

    # BATHYMETRY   (geom_polygon, fill #4A2F1B)
    ax.add_patch(Polygon(bathymetry_polygon[["X", "Depth"]].to_numpy(), closed=True,
                         fc="#4A2F1B", ec="none", zorder=2))

    # BATHYMETRY BOUNDARY   (geom_line, linewidth 0.7, black)
    ax.plot(bathymetry["X"], bathymetry["BottomDepth"], color="black",
            lw=0.7 * PT * 0.75, zorder=3)

    # ACTUAL VALID OBSERVATIONS   (shape 21, size 2.2, stroke 0.5, fill white)
    ok = observation_points[~observation_points["ParameterMissing"]]
    ax.scatter(ok["X"], ok["Depth"], s=(2.2 * PT) ** 2, marker="o", facecolors="white",
               edgecolors="black", linewidths=0.5 * 3.78 / 2 * 0.75, zorder=4)

    # MISSING PARAMETER OBSERVATIONS   (circle: shape 21 size 3 + cross: shape 4 size 2)
    miss = observation_points[observation_points["ParameterMissing"]]
    if len(miss):
        ax.scatter(miss["X"], miss["Depth"], s=(3 * PT) ** 2, marker="o", facecolors="white",
                   edgecolors="black", linewidths=0.8 * 3.78 / 2 * 0.75, zorder=4)
        ax.scatter(miss["X"], miss["Depth"], s=(2 * PT) ** 2, marker="x", color="black",
                   linewidths=0.8 * 3.78 / 2 * 0.75, zorder=5)

    # limits: ggplot uses the range of all layers (expand = 0)
    rows_kept = np.isfinite(V).any(axis=1)
    depth_rows = np.linspace(min_depth, max_depth, ny)[rows_kept]
    y_lo = min(depth_rows.min() - dy / 2, min_depth)
    y_hi = max(depth_rows.max() + dy / 2, max_depth)
    x_lo, x_hi = x_min - dx / 2, x_max + dx / 2

    # DEPTH AXIS   (scale_y_reverse, breaks = depth_breaks, expand = 0)
    ax.set_yticks([d for d in depth_breaks if y_lo <= d <= y_hi])
    ax.set_yticklabels([f"{d:g}" for d in depth_breaks if y_lo <= d <= y_hi])
    ax.set_ylim(y_hi, y_lo)

    # X AXIS   (breaks = 1..n, labels = station_order, expand = 0)
    ax.set_xticks(range(1, len(station_order) + 1))
    ax.set_xticklabels(station_order, fontsize=10, rotation=0, ha="center")
    ax.set_xlim(x_lo, x_hi)

    # LABELS
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
    # 28. DISPLAY PROFILER
    # ------------------------------------------------------------
    png = io.BytesIO()
    fig.savefig(png, format="png", dpi=100, facecolor="white")

    # ------------------------------------------------------------
    # 29. EXPORT TIFF
    # ------------------------------------------------------------
    safe_parameter_name = re.sub(r"[^A-Za-z0-9]+", "_", parameter_column)

    output_file = (
        selected_transect
        + "_"
        + safe_parameter_name
        + "_Vertical_Section_IDW.tif"
    )

    tiff = io.BytesIO()
    fig.savefig(tiff, format="tiff", dpi=600, facecolor="white",
                pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    saved_to = os.path.join(OUTPUT_DIR, output_file)
    with open(saved_to, "wb") as f:
        f.write(tiff.getvalue())

    # ------------------------------------------------------------
    # 30. FINAL MESSAGE
    # ------------------------------------------------------------
    cat("\n======================================\n")
    cat("VERTICAL SECTION CREATED\n")
    cat("Transect :", selected_transect, "\n")
    cat("Station  :", ", ".join(station_order), "\n")
    cat("Parameter:", parameter_column, "\n")
    cat("IDW power: 2\n")
    cat("Output   :", saved_to, "\n")
    cat("======================================\n")

    return {"png": png.getvalue(), "tiff": tiff.getvalue(), "filename": output_file,
            "saved_to": saved_to, "log": "".join(_LOG)}


# ============================================================
#  STREAMLIT APP
# ============================================================
def main():
    st.set_page_config(page_title="Transect Vertical Section Profiler", page_icon="🌊",
                       layout="wide")
    st.title("TRANSECT-WISE VERTICAL SECTION PROFILER")
    st.caption("ODV-style profile of ONE transect with MULTIPLE stations  |  IDW + bathymetry mask")

    # ------------------------------------------------------------
    # 2. SELECT EXCEL FILE
    # ------------------------------------------------------------
    st.sidebar.header("Excel selection")
    excel_upload = st.sidebar.file_uploader("Select Excel file", type=["xlsx", "xlsm", "xls"])

    res = st.session_state.get("transect_result")

    if excel_upload is None:
        st.info("Upload an Excel file in the sidebar to begin.")
        if res:
            _show_result(res)
        return

    # ------------------------------------------------------------
    # 3. READ EXCEL SHEET   (any sheet can be selected)
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
    # 5. SELECT TRANSECT   (T1, T2, T3 ...)
    # ------------------------------------------------------------
    station_column = find_column(data_raw.columns, "Station Name")
    if station_column is None:
        st.error("ERROR: Column 'Station Name' was not found.\n\nAvailable columns:\n"
                 + "\n".join(str(c) for c in data_raw.columns))
        return
    transects = (data_raw[station_column].astype(str).str.extract(r"^\s*(T[0-9]+)")[0]
                 .dropna().unique().tolist())
    transects = sorted(transects, key=lambda t: int(t[1:]))
    if not transects:
        st.error("No transects like 'T1' were found in the Station Name column.")
        return
    selected_transect = st.sidebar.selectbox("Transect (selected_transect)", transects,
                                             key=f"tr_{sheet_name}")

    # ------------------------------------------------------------
    # 6. SELECT PARAMETER   (exact Excel column name)
    # ------------------------------------------------------------
    skip = ("station", "depth", "latitude", "longitude")
    param_options = [str(c) for c in data_raw.columns
                     if not str(c).strip().lower().startswith(skip)]
    if not param_options:
        st.error("No parameter columns found in this sheet.")
        return
    parameter_column = st.sidebar.selectbox("Parameter (parameter_column)", param_options,
                                            key=f"par_{sheet_name}")

    if st.sidebar.button("Generate vertical section", type="primary"):
        with st.spinner("Running IDW interpolation and drawing the vertical section..."):
            st.session_state["transect_result"] = run_profiler(
                data_raw, excel_name, sheet_name, selected_transect, parameter_column)
        res = st.session_state.get("transect_result")

    if res:
        _show_result(res)
    else:
        st.info("Choose the sheet, transect and parameter in the sidebar, "
                "then press **Generate vertical section**.")


def _show_result(res):
    st.image(res["png"])
    st.download_button("Download vertical section (TIFF)", data=res["tiff"],
                       file_name=res["filename"], mime="image/tiff")
    st.success(f"Saved as: {res['saved_to']}")
    with st.expander("Console output"):
        st.code(res["log"])


if __name__ == "__main__":
    main()
