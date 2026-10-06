# -*- coding: utf-8 -*-
#                                                                              #
#              SANYO OCEAN MAPPING SUITE (SOMS) Version 1.0                    #
#          Publication Quality Oceanographic Surface Mapping in Python         #
#                          Developed by: Sanyo                                 #
#
# Python / Streamlit version of the original R script (code-03.R).
# Section numbers below match the R script.
#
# RUN:    streamlit run surface_plot.py
#
# PART 1 : INSTALL PACKAGES (Run only once)
# _______________________________SECTION 1
#
#   pip install -r requirements.txt
#
# (terra / sf / sp / gstat / tidyterra / readxl ... are replaced by
#  numpy / pandas / geopandas / shapely / rasterio / xarray / openpyxl)

# _______________________________SECTION 2 : LOAD LIBRARIES

import io
import os
import re
import tempfile
import urllib.request

import numpy as np
import pandas as pd
import streamlit as st

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon, Rectangle, Circle
from matplotlib import colors as mcolors

# Fonts (R: family = "serif" / "sans")
plt.rcParams["font.serif"] = ["Times New Roman", "Times", "DejaVu Serif"]
plt.rcParams["font.sans-serif"] = ["Arial", "Helvetica", "DejaVu Sans"]

APP_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(APP_DIR, "outputs")   # replaces R's  excel_dir

# ggplot2 size helpers (mm -> pt)
PT = 72.27 / 25.4                 # ggplot2 .pt
def lw(x):                        # ggplot linewidth -> matplotlib points
    return x * PT * 72.0 / 96.0

# Everything R prints with cat() is collected here and shown in the app.
_LOG = []


def cat(*args, sep=" "):
    _LOG.append(sep.join(str(a) for a in args))


def num(v):
    return f"{v:.7g}"


# _______________________________SECTION 3 : USER SETTINGS
# (the values that are used by the script are set in the sidebar of the app;
#  the ones below are fixed exactly as in the R script)

interpolation_method = "IDW"
colour_palette = "turbo"
smooth_sigma = 1.2
clip_to_coast = True
mask_land = True
mask_depth = False

# Study area (SECTION 11)
xmin = 74.5
xmax = 79.5
ymin = 6.8
ymax = 12.2


# ============================================================================
#  HELPER FUNCTIONS
# ============================================================================

# ---- R's pretty() ----------------------------------------------------------
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


# ---- SECTION 7 : CONVERT DDM TO DECIMAL DEGREES ----------------------------
def convert_ddm(coord):
    def _one(x):
        try:
            x = str(x).strip()
            hemi = x[-1:]
            x = re.sub(r"[NSEW]", "", x).strip()
            # R split on "°";  this Excel stores e.g. "08 50.94N", so split on "°" or spaces
            part = [p for p in re.split(r"[°\s]+", x) if p != ""]
            deg = float(part[0])
            minute = float(part[1])
            dd = deg + minute / 60
            if hemi in ("S", "W"):
                dd = -dd
            return dd
        except (ValueError, IndexError):
            return np.nan

    return pd.Series([_one(x) for x in coord], index=coord.index, dtype=float)


# ---- SECTION 12 : INDIA COASTLINE (Natural Earth 1:50m = rnaturalearth "medium")
NE_URLS = [
    "https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip",
    "https://naturalearth.s3.amazonaws.com/50m_cultural/ne_50m_admin_0_countries.zip",
]


@st.cache_data(show_spinner="Loading India coastline (Natural Earth)...")
def load_india():
    import geopandas as gpd

    zip_path = os.path.join(APP_DIR, "ne_50m_admin_0_countries.zip")
    if not os.path.exists(zip_path):
        last_err = None
        for url in NE_URLS:
            try:
                urllib.request.urlretrieve(url, zip_path)
                last_err = None
                break
            except Exception as e:  # noqa
                last_err = e
                if os.path.exists(zip_path):
                    os.remove(zip_path)
        if last_err is not None:
            raise RuntimeError(
                "Could not download Natural Earth countries. Download "
                "'ne_50m_admin_0_countries.zip' manually from naturalearthdata.com "
                f"and place it next to this app file.  ({last_err})"
            )
    world = gpd.read_file(zip_path)
    name_cols = [c for c in ("ADMIN", "NAME", "name", "admin") if c in world.columns]
    sel = np.zeros(len(world), dtype=bool)
    for c in name_cols:
        sel |= (world[c] == "India").to_numpy()
    india = world[sel]
    # Keep geometry only
    india = gpd.GeoSeries(india.geometry.values, crs="EPSG:4326")
    # Crop to study area
    india = india.clip_by_rect(xmin, ymin, xmax, ymax)
    india = india[~india.is_empty]
    return india


# ---- SECTION 13 : READ GEBCO BATHYMETRY -------------------------------------
def read_gebco(gebco_file):
    """Returns (lon_vector, lat_vector, depth_2d) cropped to the study area."""
    ext = os.path.splitext(gebco_file)[1].lower()
    if ext in (".nc", ".nc4", ".cdf"):
        import xarray as xr

        with xr.open_dataset(gebco_file) as ds:
            var = "elevation" if "elevation" in ds.data_vars else list(ds.data_vars)[0]
            latn = "lat" if "lat" in ds.coords else "latitude"
            lonn = "lon" if "lon" in ds.coords else "longitude"
            da = ds[var].sortby(latn).sortby(lonn)
            da = da.sel({latn: slice(ymin, ymax), lonn: slice(xmin, xmax)})
            lons = da[lonn].values.astype(float)
            lats = da[latn].values.astype(float)
            Z = da.values.astype(float)
    else:
        import rasterio
        from rasterio.windows import Window

        with rasterio.open(gebco_file) as src:
            r0, c0 = src.index(xmin, ymax)
            r1, c1 = src.index(xmax, ymin)
            r0, r1 = max(0, min(r0, r1)), min(src.height, max(r0, r1) + 1)
            c0, c1 = max(0, min(c0, c1)), min(src.width, max(c0, c1) + 1)
            win = Window(c0, r0, c1 - c0, r1 - r0)
            Z = src.read(1, window=win, masked=True).astype(float).filled(np.nan)
            tr = src.window_transform(win)
            lons = tr.c + (np.arange(Z.shape[1]) + 0.5) * tr.a
            lats = tr.f + (np.arange(Z.shape[0]) + 0.5) * tr.e
        if lats[0] > lats[-1]:
            lats, Z = lats[::-1], Z[::-1]
    return lons, lats, Z


# ---- SECTION 33 : mask cells touched by the India polygon (land) ------------
def land_mask(india, nx, ny):
    """Boolean (ny, nx) array, row 0 = southernmost. True = land."""
    from rasterio import features
    from rasterio.transform import Affine

    dx = (xmax - xmin) / (nx - 1)
    dy = (ymax - ymin) / (ny - 1)
    transform = Affine(dx, 0, xmin - dx / 2, 0, -dy, ymax + dy / 2)
    geoms = [(g, 1) for g in india.geometry if g is not None and not g.is_empty]
    if not geoms:
        return np.zeros((ny, nx), dtype=bool)
    m = features.rasterize(geoms, out_shape=(ny, nx), transform=transform,
                           fill=0, all_touched=True, dtype="uint8")
    return m[::-1].astype(bool)


# ---- SECTION 20 : IDW (true Inverse Distance Weighting, like gstat::idw) ----
def idw(x, y, z, gx, gy, idp):
    num_ = np.zeros(gx.shape, dtype=float)
    den_ = np.zeros(gx.shape, dtype=float)
    exact = np.full(gx.shape, np.nan)
    for xi, yi, zi in zip(x, y, z):
        d = np.hypot(gx - xi, gy - yi)
        hit = d == 0
        with np.errstate(divide="ignore"):
            w = 1.0 / d ** idp
        w[hit] = 0.0
        num_ += w * zi
        den_ += w
        exact[hit] = zi
    with np.errstate(divide="ignore", invalid="ignore"):
        pred = num_ / den_
    return np.where(np.isnan(exact), pred, exact)


# ---- SECTION 37 : haversine -------------------------------------------------
def haversine_km(lon1, lat1, lon2, lat2):
    R = 6371
    lon1 = lon1 * np.pi / 180
    lat1 = lat1 * np.pi / 180
    lon2 = lon2 * np.pi / 180
    lat2 = lat2 * np.pi / 180
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    cc = 2 * np.arcsin(np.minimum(1, np.sqrt(a)))
    return R * cc


# ---- scale_alpha_continuous(range = c(0,1)) behaviour of ggplot2 ------------
def ggplot_alpha(a):
    a = np.asarray(a, dtype=float)
    fin = np.isfinite(a)
    out = np.full(a.shape, np.nan)
    if fin.any():
        lo, hi = a[fin].min(), a[fin].max()
        out[fin] = 0.5 if hi == lo else (a[fin] - lo) / (hi - lo)
    return np.where(np.isnan(out), 1.0, out)   # NA alpha -> colour left opaque


# ============================================================================
#  MAP  (PART 4)
# ============================================================================
def build_map(grid, nx, ny, bath, india, data, label_data, contour_breaks,
              obs_min, obs_max):
    lons_g = np.sort(grid["lon"].unique())
    lats_g = np.sort(grid["lat"].unique())
    V = grid["Value"].to_numpy().reshape(ny, nx)
    A = ggplot_alpha(grid["alpha_final"].to_numpy()).reshape(ny, nx)

    fig, ax = plt.subplots(figsize=(8, 7))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    fig.subplots_adjust(left=0.12, right=0.97, bottom=0.085, top=0.97)

    # SECTION 40 : Interpolated surface  (scale_fill_viridis_c "turbo")
    norm = mcolors.Normalize(vmin=obs_min, vmax=obs_max, clip=True)
    rgba = plt.get_cmap("turbo")(norm(np.ma.masked_invalid(V)))
    rgba[..., 3] = np.where(np.isnan(V), 0.0, A)
    dx = lons_g[1] - lons_g[0]
    dy = lats_g[1] - lats_g[0]
    ax.imshow(rgba, origin="lower", interpolation="nearest", zorder=1,
              extent=[lons_g[0] - dx / 2, lons_g[-1] + dx / 2,
                      lats_g[0] - dy / 2, lats_g[-1] + dy / 2])

    # SECTION 41 : Parameter contours + labels
    Vm = np.ma.masked_invalid(V)
    if Vm.count() > 0:
        gmin, gmax = float(Vm.min()), float(Vm.max())
        lv = [b for b in contour_breaks if gmin < b < gmax]
        if lv:
            cs = ax.contour(lons_g, lats_g, Vm, levels=lv, colors="black",
                            linewidths=lw(0.5), zorder=2)
            try:
                texts = ax.clabel(cs, levels=lv, inline=True, fontsize=4 * PT,
                                  fmt=lambda v: f"{v:g}")
                for t in texts:
                    t.set_fontweight("bold")
                    t.set_color("black")
                    t.set_path_effects([pe.withStroke(linewidth=2.0, foreground="white")])
                    t.set_zorder(3)
            except Exception:
                pass

    # SECTION 42 : Bathymetry
    if bath is not None:
        blon, blat, Z = bath
        Zm = np.ma.masked_invalid(Z)
        bl = [b for b in (-3000, -2000, -1000, -500, -200, -100, -50)
              if Zm.count() > 0 and Zm.min() < b < Zm.max()]
        if bl:
            ax.contour(blon, blat, Zm, levels=bl, colors="#333333",
                       linewidths=lw(0.30), linestyles="dashed", zorder=4)

    # SECTION 43 : Coastline
    if india is not None and len(india) > 0:
        india.plot(ax=ax, facecolor="#E5E5E5", edgecolor="black",
                   linewidth=lw(0.50), zorder=5)

    # SECTION 44 : Station locations
    avail = data[~data["Value"].isna()]
    miss = data[data["Value"].isna()]
    ax.scatter(avail["Lon_DD"], avail["Lat_DD"], s=62, marker="o",
               facecolors="white", edgecolors="black", linewidths=1.4, zorder=6)
    if len(miss):
        ax.scatter(miss["Lon_DD"], miss["Lat_DD"], s=95, marker=r"$\otimes$",
                   color="red", zorder=6)

    # SECTION 45 : Transect labels
    for _, r in label_data.iterrows():
        if isinstance(r["Label"], str):
            ax.text(r["label_lon"], r["label_lat"], r["Label"], family="serif",
                    fontweight="bold", fontsize=4 * PT, ha="center", va="center",
                    zorder=7)

    # SECTION 49 : Study area  (coord_sf)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect(1 / np.cos(np.radians((ymin + ymax) / 2)))
    ax.apply_aspect()

    # SECTION 51 : Theme
    xt = np.arange(np.ceil(xmin), np.floor(xmax) + 1)
    yt = np.arange(np.ceil(ymin), np.floor(ymax) + 1)
    ax.set_xticks(xt)
    ax.set_yticks(yt)
    ax.set_xticklabels([f"{v:g}°E" for v in xt], fontfamily="sans-serif",
                       fontweight="bold", fontsize=18)
    ax.set_yticklabels([f"{v:g}°N" for v in yt], fontfamily="sans-serif",
                       fontweight="bold", fontsize=18)
    ax.tick_params(length=0.2 / 2.54 * 72, width=lw(1.2), color="black",
                   direction="out")
    for s in ax.spines.values():
        s.set_linewidth(lw(1.5))
        s.set_color("black")
        s.set_zorder(30)

    pos = ax.get_position()
    w_in = pos.width * fig.get_figwidth()
    h_in = pos.height * fig.get_figheight()
    cm = 1 / 2.54
    deg_x = (xmax - xmin) / w_in      # degrees per inch
    deg_y = (ymax - ymin) / h_in

    # SECTION 47 : Scale bar (bottom-left)
    mid_lat = (ymin + ymax) / 2
    km_per_deg = 111.320 * np.cos(np.radians(mid_lat))
    hint_km = 0.35 * (xmax - xmin) * km_per_deg
    cands = [m * 10.0 ** k for k in range(0, 5) for m in (1, 2, 5)]
    nice = max([c for c in cands if c <= hint_km] or [1])
    bar_deg = nice / km_per_deg
    x0 = xmin + 0.25 * cm * deg_x
    y0 = ymin + 0.25 * cm * deg_y
    bh = 0.25 * cm * deg_y
    ax.add_patch(Rectangle((x0, y0), bar_deg / 2, bh, fc="black", ec="black",
                           lw=1.2, zorder=8))
    ax.add_patch(Rectangle((x0 + bar_deg / 2, y0), bar_deg / 2, bh, fc="white",
                           ec="black", lw=1.2, zorder=8))
    ty = y0 + bh + 0.05 * cm * deg_y
    for xx, lab in ((x0, "0"), (x0 + bar_deg / 2, f"{nice / 2:g}"),
                    (x0 + bar_deg, f"{nice:g} km")):
        ax.text(xx, ty, lab, ha="center", va="bottom", fontsize=1.3 * 8.5,
                family="sans-serif", zorder=8)

    # SECTION 48 : North arrow (top-right)
    size_in = 1.5 * cm
    ia = ax.inset_axes([1 - (0.7 * cm + size_in) / w_in,
                        1 - (0.6 * cm + size_in) / h_in,
                        size_in / w_in, size_in / h_in], zorder=9)
    ia.set_xlim(0, 1)
    ia.set_ylim(0, 1)
    ia.axis("off")
    ia.add_patch(Polygon([(0.5, 0.80), (0.22, 0.10), (0.5, 0.30)], closed=True,
                         fc="black", ec="black", lw=1.0))
    ia.add_patch(Polygon([(0.5, 0.80), (0.78, 0.10), (0.5, 0.30)], closed=True,
                         fc="white", ec="black", lw=1.0))
    ia.text(0.5, 0.97, "N", color="red", ha="center", va="top", fontsize=13,
            fontweight="bold", family="serif")

    # SECTION 44b : Station marker legend  (bottom-left)
    handles = [
        Line2D([], [], marker="o", ls="", markerfacecolor="white",
               markeredgecolor="black", markeredgewidth=1.2, markersize=6),
        Line2D([], [], marker=r"$\otimes$", ls="", color="red", markersize=9),
    ]
    leg = ax.legend(handles, ["Available", "Missing"], title="Data Status",
                    loc="lower left", bbox_to_anchor=(0.02, 0.05), borderaxespad=0,
                    frameon=True, facecolor="white", edgecolor="white", framealpha=1,
                    fancybox=False,
                    prop={"family": "serif", "size": 11, "weight": "normal"},
                    title_fontproperties={"family": "serif", "weight": "bold", "size": 14})
    leg.set_zorder(7.5)
    return fig


# ============================================================================
#  MAIN PIPELINE   (PART 1 - PART 4 of the R script)
# ============================================================================
def run_soms(data, excel_name, parameter_col, depth_choice, gebco_file,
             smooth_surface, extrapolation_distance, grid_resolution, save_output):
    _LOG.clear()

    cat("Interpolation method:", interpolation_method, "\n")
    cat("\n")
    cat("=============================================================\n")
    cat("             SANYO OCEAN MAPPING SUITE (SOMS) V1.0\n")
    cat("                 Developed by Sanyo\n")
    cat("=============================================================\n\n")

    # _____________________________________SECTION 5 : READ EXCEL DATA
    # (the Excel file / sheet are chosen in the app; `data` is the selected sheet)
    excel_dir = OUTPUT_DIR
    os.makedirs(excel_dir, exist_ok=True)

    # _________________________________SECTION 5.1 : Check number of columns
    if parameter_col > data.shape[1]:
        st.error(
            f"ERROR : PARAMETER COLUMN NOT FOUND - this Excel sheet contains only "
            f"{data.shape[1]} columns. Requested parameter column : {parameter_col}"
        )
        st.stop()

    # _________________________________SECTION 5.2 : Get selected column name
    parameter_column = str(data.columns[parameter_col - 1])

    # _________________________________SECTION 5.3 : Pick the required columns of THIS Excel layout
    # Excel headers   ->  names used by the script
    #   "station name"     -> "Station Name"
    #   "Latitude (°N)"    -> "Latitude"
    #   "Longitude (°E)"   -> "Longitude"
    #   "Depth (m)"        -> "Depth"   (used to choose one depth, see below)
    wanted = {"station": "Station Name", "lat": "Latitude", "lon": "Longitude",
              "depth": "Depth"}
    renames = {}
    for i, c in enumerate(data.columns):
        if i == parameter_col - 1:
            continue
        key = str(c).strip().lower()
        for prefix, newname in wanted.items():
            if key.startswith(prefix) and newname not in renames.values():
                renames[c] = newname
                break
    data = data.rename(columns=renames)
    missing_cols = [n for n in ("Station Name", "Latitude", "Longitude")
                    if n not in data.columns]
    if missing_cols:
        st.error("Required column(s) not found in this sheet: " + ", ".join(missing_cols))
        st.stop()

    # Several depths per station in this file -> keep only the chosen depth
    if depth_choice is not None and "Depth" in data.columns:
        data = data[data["Depth"].astype(str).str.strip() == depth_choice]
    data = data.reset_index(drop=True)

    # ___________________________________SECTION 6 : COLLECTING PARAMETER INFORMATION
    if re.search(r"[\(\[]", parameter_column):
        parameter_name = re.sub(r"\s*[\(\[].*[\)\]]", "", parameter_column).strip()
        parameter_unit = re.sub(r".*[\(\[](.*)[\)\]].*", r"\1", parameter_column).strip()
    else:
        parameter_name = parameter_column.strip()
        parameter_unit = ""

    cat("\n")
    cat("---------------------------------------------\n")
    cat("Selected Parameter\n")
    cat("---------------------------------------------\n")
    cat("Column Number :", parameter_col, "\n")
    cat("Column Name   :", parameter_column, "\n")
    cat("Parameter     :", parameter_name, "\n")
    cat("Units         :", parameter_unit, "\n")
    if depth_choice is not None:
        cat("Depth         :", depth_choice, "\n")
    cat("---------------------------------------------\n\n")

    # ____________________________________________________Rename selected parameter
    data = data.rename(columns={data.columns[parameter_col - 1]: "Value"})

    # ______________________________SECTION 6.1 : Convert to numeric
    data["Value"] = pd.to_numeric(data["Value"], errors="coerce")

    # _____________________________SECTION 6.2 : Check if parameter column contains any numeric data
    if data["Value"].isna().all():
        st.error(
            f"ERROR : PARAMETER COLUMN CONTAINS NO DATA - Selected Parameter : "
            f"{parameter_column}. The selected column contains no numeric values "
            f"(for the chosen depth)."
        )
        st.stop()

    cat("\n========================================\n")
    cat("DEBUG STAGE 1 : AFTER RENAME\n")
    cat("========================================\n")
    cat("Column names:\n")
    cat(list(data.columns), "\n")
    cat("\nType of Value:\n")
    cat(data["Value"].dtype, "\n")
    cat("\nFirst 10 Values:\n")
    cat(data["Value"].head(10).tolist(), "\n")
    cat("\nAny NA? ", bool(data["Value"].isna().any()), "\n")
    cat("Any Inf? ", bool(np.isinf(data["Value"]).any()), "\n")

    # END OF PART 1

    # PART 2 : CONVERT DDM TO DECIMAL DEGREES
    # __________________________________________SECTION 8 : CREATE DECIMAL COORDINATES
    data["Lat_DD"] = convert_ddm(data["Latitude"])
    data["Lon_DD"] = convert_ddm(data["Longitude"])

    # _____________________________________________SECTION 9 : REMOVE INVALID RECORDS (coordinates only)
    data = data[data["Lon_DD"].notna() & data["Lat_DD"].notna()].reset_index(drop=True)

    # ____________________________________________SECTION 10 : QUICK DATA SUMMARY
    cat("---------------------------------------------\n")
    cat("Data Summary\n")
    cat("---------------------------------------------\n")
    cat("Number of Stations :", len(data), "\n")
    cat("Minimum            :", num(data["Value"].min()), "\n")
    cat("Maximum            :", num(data["Value"].max()), "\n")
    cat("Mean               :", num(data["Value"].mean()), "\n")
    cat("Median             :", num(data["Value"].median()), "\n")
    cat("---------------------------------------------\n\n")

    # ___________________________________SECTION 11 : STUDY AREA  (xmin, xmax, ymin, ymax set at the top)

    # ________________________________SECTION 12 : INDIA COASTLINE
    india = load_india()

    # _______________________________SECTION 13 : READ GEBCO BATHYMETRY
    blon, blat, Z = read_gebco(gebco_file)
    bath_df = pd.DataFrame({
        "x": np.tile(blon, len(blat)),
        "y": np.repeat(blat, len(blon)),
        "depth": Z.ravel(),
    }).dropna()

    # ____________________________SECTION 14 : TRANSECT LABELS
    label_data = data.copy()
    sn = label_data["Station Name"].astype(str)
    label_data["Transect"] = sn.str.extract(r"(T\d+)")[0]
    label_data["StationNo"] = pd.to_numeric(sn.str.extract(r"(?<=S)(\d+)")[0],
                                            errors="coerce")
    recode_map = {"T4": "Cap", "T5": "Col", "T6": "Viz", "T7": "Kol", "T8": "Kar",
                  "T9": "Ala", "T10": "Art", "T11": "Koc", "T12": "Mun", "T13": "Koz"}
    # dplyr::recode leaves unmatched values unchanged
    label_data["Label"] = label_data["Transect"].map(lambda t: recode_map.get(t, t))
    label_data = (label_data.sort_values("StationNo", kind="stable")
                  .groupby("Transect", dropna=False, sort=False).head(1)
                  .reset_index(drop=True))

    # ___________________SECTION 15 : LABEL POSITIONS
    label_data["label_lon"] = label_data["Lon_DD"] + 0.20
    label_data["label_lat"] = label_data["Lat_DD"] + 0.10

    # ______________________________ SECTION 16 : Manual adjustments
    for lab, add in (("Koc", 0.25), ("Mun", 0.35), ("Art", 0.18), ("Koz", 0.20)):
        label_data.loc[label_data["Label"] == lab, "label_lon"] += add

    # ________________________________________SECTION 17 : PREVIEW DATA
    cat("\nFirst Five Stations\n")
    cat(data.head().to_string(), "\n")
    cat("\nBathymetry Summary\n")
    cat(bath_df["depth"].describe().to_string(), "\n")

    # END OF PART 2

    # PART 3
    # _________________________SECTION 18 : CREATE INTERPOLATION INPUT
    xyz = np.column_stack([data["Lon_DD"], data["Lat_DD"], data["Value"]])

    # _________________________SECTION 18.1 :Observed data range
    obs_min = data["Value"].min()
    obs_max = data["Value"].max()

    # _________________________SECTION 19 : INTERPOLATION
    cat("---------------------------------------------\n")
    cat("Interpolation Method :", interpolation_method, "\n")
    cat("---------------------------------------------\n\n")

    # _________________________SECTION 20 : IDW INTERPOLATION (true Inverse Distance Weighting)
    nx = ny = int(grid_resolution)
    lons = np.linspace(xmin, xmax, nx)
    lats = np.linspace(ymin, ymax, ny)
    LON, LAT = np.meshgrid(lons, lats)          # lon varies fastest, like expand.grid

    if interpolation_method == "IDW":
        # Use only points with actual values for interpolation input
        data_valid = data[~data["Value"].isna()]
        pred = idw(data_valid["Lon_DD"].to_numpy(), data_valid["Lat_DD"].to_numpy(),
                   data_valid["Value"].to_numpy(), LON, LAT, idp=2)
        grid = pd.DataFrame({"lon": LON.ravel(), "lat": LAT.ravel(),
                             "Value": pred.ravel()})

    # _________________________________SECTION 24 : CHECK GRID
    cat("\nColumns in grid:\n")
    cat(list(grid.columns), "\n")
    cat("\nStructure of grid:\n")
    cat(grid.dtypes.to_string(), "\n")
    if "Value" not in grid.columns:
        raise RuntimeError("ERROR: 'Value' column was never created.")

    # __________________________________SECTION 25 : REMOVE EMPTY CELLS
    # (IDW leaves no empty cells, so the full regular grid is kept)
    Value2d = grid["Value"].to_numpy().reshape(ny, nx)

    # _________________________________SECTION 26 : OPTIONAL GAUSSIAN SMOOTHING
    if smooth_surface:
        w = np.array([[1, 2, 1], [2, 4, 2], [1, 2, 1]], dtype=float)
        acc = np.zeros((ny - 2, nx - 2))
        for i in range(3):
            for j in range(3):
                acc += w[i, j] * Value2d[i:ny - 2 + i, j:nx - 2 + j]
        sm = np.full((ny, nx), np.nan)             # outer ring of cells -> NA (as focal())
        sm[1:-1, 1:-1] = acc / w.sum()
        Value2d = sm

    # _________________________________SECTION 27 : CLAMP INTERPOLATED VALUES TO OBSERVED RANGE
    Value2d = np.clip(Value2d, obs_min, obs_max)

    # _________________________________SECTION 28-29 : CONVERT TO RASTER   (grid arrays: lons / lats, EPSG:4326)
    # _________________________________SECTION 31-32 : India coastline, matching CRS   (already EPSG:4326)

    # _________________________________SECTION 33 : Remove interpolation over land
    Value2d[land_mask(india, nx, ny)] = np.nan

    # _________________________________SECTION 36 : Convert back to dataframe
    grid = pd.DataFrame({"lon": LON.ravel(), "lat": LAT.ravel(),
                         "Value": Value2d.ravel()})
    cat(">>> After land mask, NA count:", int(grid["Value"].isna().sum()), "out of",
        len(grid), "\n")

    # __________________________________SECTION 37 : DISTANCE-BASED FADES (edge-only, full saturation elsewhere)
    # --- Fade 1: extrapolation edge -- full opacity until near the boundary ---
    fade_zone_km = 25   # width of the fade band, right at the edge

    obs_pts = data[~data["Value"].isna()][["Lon_DD", "Lat_DD"]]
    glon = grid["lon"].to_numpy()
    glat = grid["lat"].to_numpy()
    dist = np.full(len(grid), np.inf)
    for lo_, la_ in zip(obs_pts["Lon_DD"], obs_pts["Lat_DD"]):
        dist = np.minimum(dist, haversine_km(glon, glat, lo_, la_))
    grid["dist_to_nearest_obs"] = dist
    grid.loc[grid["dist_to_nearest_obs"] > extrapolation_distance, "Value"] = np.nan

    alpha_fade = np.ones(len(grid))
    edge_zone = dist > (extrapolation_distance - fade_zone_km)
    alpha_fade[edge_zone] = (extrapolation_distance - dist[edge_zone]) / fade_zone_km
    alpha_fade[alpha_fade < 0] = 0
    alpha_fade[alpha_fade > 1] = 1
    alpha_fade[np.isnan(alpha_fade)] = 0
    grid["alpha_fade"] = alpha_fade

    # __________________________________SECTION 37b : IDW-BASED PRESENCE SURFACE
    # Presence score for every station: 1 = has a real reading, 0 = blank cell
    presence_data = data.copy()
    presence_data["presence"] = np.where(presence_data["Value"].isna(), 0, 1)

    presence_pred = idw(presence_data["Lon_DD"].to_numpy(),
                        presence_data["Lat_DD"].to_numpy(),
                        presence_data["presence"].to_numpy(float), LON, LAT, idp=5)
    presence_grid = pd.DataFrame({"lon": LON.ravel(), "lat": LAT.ravel(),
                                  "alpha_blank": presence_pred.ravel()})

    # Clamp to valid alpha range [0,1] -- IDW can slightly overshoot
    presence_grid["alpha_blank"] = presence_grid["alpha_blank"].clip(0, 1)

    # Merge onto grid by matching lon/lat (rounded defensively)
    grid["lon_r"] = grid["lon"].round(6)
    grid["lat_r"] = grid["lat"].round(6)
    presence_grid["lon_r"] = presence_grid["lon"].round(6)
    presence_grid["lat_r"] = presence_grid["lat"].round(6)

    grid = grid.merge(presence_grid[["lon_r", "lat_r", "alpha_blank"]],
                      on=["lon_r", "lat_r"], how="left", sort=False)
    grid = grid.drop(columns=["lon_r", "lat_r"])

    ab = grid["alpha_blank"].to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        ab = (ab - np.nanmin(ab)) / (np.nanmax(ab) - np.nanmin(ab))
        # try 0.3-0.6 -- lower number = more saturation overall
        ab = ab ** 0.4
    grid["alpha_blank"] = ab

    grid["alpha_final"] = grid["alpha_fade"] * grid["alpha_blank"]
    grid.loc[grid["Value"].isna(), "alpha_final"] = 0

    if np.isfinite(grid["alpha_blank"]).any():
        cat(">>> Range of IDW-based alpha_blank:", num(np.nanmin(ab)), num(np.nanmax(ab)), "\n")
    else:
        cat(">>> Range of IDW-based alpha_blank: n/a (all stations have data)\n")
    cat(">>> Rows at full opacity (alpha_final == 1):", int((grid["alpha_final"] == 1).sum()), "\n")
    cat(">>> Rows with alpha_final == 0 (fully transparent):", int((grid["alpha_final"] == 0).sum()), "\n")

    # _________________________________SECTION 37.1:INTERPOLATION SUMMARY
    zmin = obs_min
    zmax = obs_max

    cat("---------------------------------------------\n")
    cat("Interpolation Finished\n")
    cat("---------------------------------------------\n")
    cat("Observed Minimum :", num(obs_min), "\n")
    cat("Observed Maximum :", num(obs_max), "\n\n")
    cat("Interpolated Minimum :", num(np.nanmin(grid["Value"])), "\n")
    cat("Interpolated Maximum :", num(np.nanmax(grid["Value"])), "\n")
    cat("Mean :", num(np.nanmean(grid["Value"])), "\n")
    cat("Median :", num(np.nanmedian(grid["Value"])), "\n")
    cat("---------------------------------------------\n\n")

    # END OF PART 3

    # PART 4
    # _________________________________SECTION 38:LEGEND TITLE
    if parameter_unit == "":
        legend_title = parameter_name
    else:
        legend_title = parameter_name + "\n(" + parameter_unit + ")"

    # _________________________________SECTION 39:CREATE PUBLICATION QUALITY MAP
    contour_breaks = r_pretty(obs_min, obs_max, n=5)

    fig = build_map(grid, nx, ny, (blon, blat, Z), india, data, label_data,
                    contour_breaks, obs_min, obs_max)

    # _________________________________SECTION 52 : SAVE FIGURE
    fname = f"{excel_name} - {parameter_name}"
    if depth_choice is not None:
        fname += f" - {depth_choice}"
    fname = re.sub(r'[\\/:*?"<>|]', "_", fname) + ".tiff"
    output_file = os.path.join(excel_dir, fname)

    tiff = io.BytesIO()
    fig.savefig(tiff, format="tiff", dpi=200, facecolor="white",
                pil_kwargs={"compression": "tiff_lzw"})
    saved_to = None
    if save_output:
        with open(output_file, "wb") as f:
            f.write(tiff.getvalue())
        saved_to = output_file
        cat("\n")
        cat("Map exported successfully.\n")
        cat("File :", output_file, "\n")

    # _________________________________SECTION 53 : DISPLAY MAP
    png = io.BytesIO()
    fig.savefig(png, format="png", dpi=150, facecolor="white")
    plt.close(fig)

    return {"png": png.getvalue(), "tiff": tiff.getvalue(), "filename": fname,
            "saved_to": saved_to, "log": "".join(_LOG)}


# ============================================================================
#  STREAMLIT APP
# ============================================================================
def main():
    st.set_page_config(page_title="SOMS - Sanyo Ocean Mapping Suite",
                       page_icon="🌊", layout="wide")
    st.title("SANYO OCEAN MAPPING SUITE (SOMS) V1.0")
    st.caption("Publication Quality Oceanographic Surface Mapping  |  Developed by Sanyo")

    # _____________________________________SECTION 4 : SELECT INPUT FILES
    st.sidebar.header("Input files")
    excel_upload = st.sidebar.file_uploader("[1/2] Select Excel Data File",
                                            type=["xlsx", "xlsm", "xls"])
    gebco_upload = st.sidebar.file_uploader("[2/2] Select GEBCO Bathymetry File",
                                            type=["nc", "tif", "tiff"])
    gebco_path_text = st.sidebar.text_input(
        "...or type the full path of a local GEBCO file (for very large files)", "")

    # Results of the last run stay on screen (also after pressing a download button)
    res = st.session_state.get("soms_result")

    if excel_upload is None:
        st.info("Upload an Excel file in the sidebar to begin.")
        if res:
            _show_result(res)
        return

    # ---- choose sheet ------------------------------------------------------
    try:
        xl = pd.ExcelFile(excel_upload)
    except Exception as e:  # noqa
        st.error(f"Could not read the Excel file: {e}")
        return
    st.sidebar.header("Excel selection")
    sheet_name = st.sidebar.selectbox("Excel sheet", xl.sheet_names)
    data_in = pd.read_excel(xl, sheet_name=sheet_name)
    excel_name = os.path.splitext(excel_upload.name)[0]

    with st.expander(f"Preview of sheet '{sheet_name}'  ({data_in.shape[0]} rows x "
                     f"{data_in.shape[1]} columns)"):
        st.dataframe(data_in.head(30))

    # ---- parameter column (R: parameter_col) -------------------------------
    cols = [str(c) for c in data_in.columns]
    skip = ("station", "lat", "lon", "depth")
    default_i = next((i for i, c in enumerate(cols)
                      if not c.strip().lower().startswith(skip)), 0)
    parameter_col = st.sidebar.selectbox(
        "Parameter column (parameter_col)", list(range(1, len(cols) + 1)),
        index=default_i, format_func=lambda i: f"{i} - {cols[i - 1]}",
        key=f"pcol_{sheet_name}")

    # ---- depth (this Excel has several depths per station) -----------------
    depth_col = next((c for i, c in enumerate(data_in.columns)
                      if str(c).strip().lower().startswith("depth")
                      and i != parameter_col - 1), None)
    depth_choice = None
    if depth_col is not None:
        depths = list(pd.unique(data_in[depth_col].astype(str).str.strip()))
        depth_choice = st.sidebar.selectbox("Depth", depths, key=f"depth_{sheet_name}")

    # ---- settings used by the script (SECTION 3) ---------------------------
    with st.sidebar.expander("Advanced settings"):
        smooth_surface = st.checkbox("smooth_surface", value=True)
        extrapolation_distance = st.number_input("extrapolation_distance (km)", value=50,
                                                 min_value=1, step=5)
        grid_resolution = st.number_input("grid_resolution", value=500, min_value=50,
                                          max_value=2000, step=50)
        save_output = st.checkbox(f"save_output (also write the TIFF to '{OUTPUT_DIR}')",
                                  value=True)

    run = st.sidebar.button("Generate map", type="primary")

    if run:
        # ---- GEBCO file -----------------------------------------------------
        tmp_path = None
        if gebco_upload is not None:
            suffix = os.path.splitext(gebco_upload.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(gebco_upload.getbuffer())
                tmp_path = tmp.name
            gebco_file = tmp_path
        elif gebco_path_text.strip() and os.path.isfile(gebco_path_text.strip().strip('"')):
            gebco_file = gebco_path_text.strip().strip('"')
        else:
            st.error("Please select the GEBCO bathymetry file (upload it, or type a valid local path).")
            return
        try:
            with st.spinner("Interpolating and drawing the map..."):
                st.session_state["soms_result"] = run_soms(
                    data_in, excel_name, int(parameter_col), depth_choice, gebco_file,
                    smooth_surface, float(extrapolation_distance), int(grid_resolution),
                    save_output)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
        res = st.session_state.get("soms_result")

    if res:
        _show_result(res)
    else:
        st.info("Choose the sheet, parameter and depth in the sidebar, upload the GEBCO file, "
                "then press **Generate map**.")


def _show_result(res):
    st.image(res["png"])
    st.download_button("Download map (TIFF)", data=res["tiff"], file_name=res["filename"],
                       mime="image/tiff")
    if res["saved_to"]:
        st.success(f"Map exported successfully: {res['saved_to']}")
    with st.expander("Console output"):
        st.code(res["log"])


if __name__ == "__main__":
    main()
