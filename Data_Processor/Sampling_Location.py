# -*- coding: utf-8 -*-
# ============================================================
# SAMPLING LOCATION + GEBCO BATHYMETRY MAP
# (Python / Streamlit version of Sampling_Location_mapmodifiyed.R)
# ============================================================
#
# Excel:
#   Station Name | Latitude | Longitude | (additional parameter columns...)
#
# Example:
#
#   T1 S1    | 8.20 | 76.10
#   T1 S2    | 8.35 | 76.30
#   T2 S1    | 8.80 | 76.50
#   T4 S2    | 9.70 | 77.20
#
# Any additional columns (e.g. DO(mg/L), Tem(°C), ...) after
# Longitude are ignored by this script.
#
# The complete Station Name value is used as the map label.
#
# RUN:    streamlit run Sampling_Location.py
#
# ============================================================


# ============================================================
# 1. REQUIRED PACKAGES
# ============================================================
#
#   pip install streamlit numpy pandas openpyxl matplotlib pillow geopandas shapely xarray netCDF4
#
# (terra/readxl/dplyr/sf/rnaturalearth -> xarray/pandas/geopandas/shapely,
#  ggplot2/ggspatial/ggrepel -> matplotlib)

import io
import os
import re
import urllib.request

import numpy as np
import pandas as pd
import streamlit as st

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon, Rectangle
from PIL import Image

Image.MAX_IMAGE_PIXELS = None   # 1200 dpi output is a very large image

plt.rcParams["font.sans-serif"] = ["Arial", "Helvetica", "DejaVu Sans"]

APP_DIR = os.path.dirname(os.path.abspath(__file__))

PT = 72.27 / 25.4                 # ggplot2 .pt  (mm -> pt)


def lw(x):                        # ggplot linewidth (mm) -> matplotlib points
    return x * PT * 72.0 / 96.0


# Everything R prints with cat()/print() is collected here and shown in the app.
_LOG = []
_WARNINGS = []


def cat(*args, sep=" "):
    _LOG.append(sep.join(str(a) for a in args))


def num(v):
    return f"{v:.7g}"


# ============================================================
# 1b. DMM (DEGREES + DECIMAL MINUTES) TO DECIMAL DEGREES
# ============================================================
#
# Converts coordinates like "8°3.342N" or "77°30.175E" into
# plain decimal degrees (e.g. 8.0557).
#
# Handles a leading degree symbol, decimal minutes, and a
# trailing compass direction (N/S/E/W), with optional stray
# whitespace around the value.
#
# (this Excel writes them as "08 50.94N", so a space is accepted
#  in place of the degree symbol)
#
# ============================================================

def dmm_to_decimal(x):

    def one(v):
        m = re.search(r"([0-9]+)[°\s]+([0-9.]+)([NSEWnsew])", str(v))

        if m is None:
            return np.nan

        try:
            deg = float(m.group(1))
            minute = float(m.group(2))
        except ValueError:
            return np.nan
        direction = m.group(3).upper()

        dec = deg + minute / 60

        if direction in ("S", "W"):
            dec = -dec

        return dec

    return pd.Series([one(v) for v in x], index=x.index, dtype=float)


# ============================================================
# 3. MANUAL MAP EXTENT
# ============================================================

map_lon_min = 74.5
map_lon_max = 79

map_lat_min = 6.8
map_lat_max = 12


# ============================================================
# 4. BATHYMETRY SETTINGS
# ============================================================

min_depth = 0

max_depth = 2500


# ============================================================
# 5. CONTOUR SETTINGS
# ============================================================

contour_line_size = 0.50

# ---- Selected highlighted contours (own colour each) ----
#
# These are drawn as a SEPARATE, additional layer on top of
# the regular grey contour lines above (which are left
# unchanged). Each one gets its own colour, and its own entry
# in the legend on the right, replacing the bathymetry
# colour-bar legend.

selected_contour_levels = [10, 20, 30, 50, 100, 200, 500]

selected_contour_colours = {

    "10": "#C83E4D",

    "20": "#3A8F6B",

    "30": "#D98C2B",

    "50": "#D95F8D",

    "100": "#8B654A",

    "200": "#B57AC3",

    "500": "#3F3F46",

}

selected_contour_line_size = 0.50


# ============================================================
# 6. SAMPLING POINT SETTINGS
# ============================================================

sampling_point_size = 1.5

sampling_point_stroke = 0.8


# ============================================================
# 7. AUTOMATIC LABEL OFFSET
# ============================================================

default_label_x_offset = 0.06

default_label_y_offset = 0.06


# ============================================================
# 8. MANUAL TRANSECT/STATION LABEL POSITIONS
# ============================================================
#
# IMPORTANT:
#
# The values here MUST EXACTLY MATCH the values in the
# Station Name column of your Excel file.
#
# Example:
#
# "T4 S2": (77.20, 9.80)
#
# This moves ONLY the label.
#
# The actual sampling point remains at the Excel coordinate.
#
# ============================================================


manual_label_positions = {

    # Example:
    #
    # "T1 S1": (76.10, 8.30),
    # "T1 S2": (76.30, 8.45),
    # "T2 S1": (76.55, 8.90),
    # "T4 S2": (77.30, 9.80),

}


# ============================================================
# 8b. MANUAL Tx (TRANSECT-LEVEL) LABEL POSITIONS
# ============================================================
#
# One "Tx" label is drawn per transect (e.g. "T4", "T5", ...),
# placed on the land side of that transect, instead of
# repeating the transect name at every station.
#
# By default, the Tx label is placed near the coast-side
# station of the transect (the station with the HIGHEST
# longitude, i.e. closest to shore) and then nudged further
# east (onto land) by 'transect_label_land_offset'.
#
# If a Tx label lands in the water instead of on land for a
# particular transect, override it manually here using ONLY
# the transect number, e.g.:
#
# "T4":  (77.55, 8.40),
# "T13": (75.10, 11.10),
#
# ============================================================

manual_transect_label_positions = {

    # Example:
    #
    # "T4":  (77.55, 8.40),
    # "T13": (75.10, 11.10),

}


# Default extra push (in decimal degrees) applied eastward
# (onto land) from the coast-side station of each transect.

transect_label_land_offset = 0.12


# ============================================================
# 9. LABEL APPEARANCE
# ============================================================

# ---- Station (Sx) labels, placed at each point ----

station_label_size = 3.0

station_label_fontface = "plain"

station_label_colour = "black"


# ---- Transect (Tx) labels, one per transect, on land ----

transect_label_size = 4.2

transect_label_fontface = "bold"

transect_label_colour = "black"


# ---- Auto-repel settings (prevents labels overlapping) ----
#
# box.padding      : empty space kept around each label
# point.padding    : empty space kept around each anchor point
# min.segment.length : draw a leader line if the label moves
#                       further than this from its point
#                       (0 = always draw a line if it moved)
# max.overlaps     : allow unlimited attempts to resolve overlaps
# seed             : fixes the layout so it looks the same every
#                     time you re-run the script

label_box_padding = 0.3

label_point_padding = 0.25

label_min_segment_length = 0

label_max_overlaps = float("inf")

label_repel_seed = 42


# ============================================================
# 10. NORTH ARROW
# ============================================================

north_arrow_location = "tr"


# ============================================================
# 11. SCALE BAR
# ============================================================

scale_bar_location = "bl"

scale_bar_width_hint = 0.25


# ============================================================
# 12. OUTPUT SETTINGS
# ============================================================

output_width = 8

output_height = 9

output_dpi = 1200      # can be changed in the app (Advanced settings)


# ============================================================
# 13. OUTPUT FOLDER
# ============================================================

output_folder = os.path.join(APP_DIR, "outputs")   # replaces R's  dirname(excel_file)

png_file = os.path.join(
    output_folder,
    "Sampling_Location_Bathymetry_Map.png"
)

tiff_file = os.path.join(
    output_folder,
    "Sampling_Location_Bathymetry_Map.tiff"
)


# ============================================================
# 30. LOAD LAND  (rnaturalearth::ne_countries(scale = "medium") = Natural Earth 1:50m)
# ============================================================
NE_URLS = [
    "https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip",
    "https://naturalearth.s3.amazonaws.com/50m_cultural/ne_50m_admin_0_countries.zip",
]


@st.cache_data(show_spinner="Loading land polygons (Natural Earth)...")
def load_land():
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

    if world.crs is not None:
        world = world.to_crs(4326)

    # ============================================================
    # 31. CROP LAND TO MAP REGION
    # ============================================================
    land = world.geometry.clip_by_rect(map_lon_min, map_lat_min, map_lon_max, map_lat_max)
    land = land[land.notna() & ~land.is_empty]
    return land


# ============================================================
# 19. READ GEBCO  (NetCDF)
# ============================================================
def read_gebco(gebco_file):
    """Returns (lons, lats, elevation_2d, info_text) cropped to the map extent (Section 22)."""
    import xarray as xr

    with xr.open_dataset(gebco_file) as ds:
        var = "elevation" if "elevation" in ds.data_vars else list(ds.data_vars)[0]
        latn = next(n for n in ("lat", "latitude", "y") if n in ds.coords)
        lonn = next(n for n in ("lon", "longitude", "x") if n in ds.coords)
        da = ds[var].sortby(latn).sortby(lonn)
        res_x = float(np.abs(np.diff(da[lonn].values)).mean())
        res_y = float(np.abs(np.diff(da[latn].values)).mean())
        info = (f"variable   : {var}\n"
                f"dimensions : {da.shape[1]} cols x {da.shape[0]} rows\n"
                f"resolution : {res_x:.6f}, {res_y:.6f} degrees\n"
                f"extent     : {float(da[lonn].min()):.4f}, {float(da[lonn].max()):.4f}, "
                f"{float(da[latn].min()):.4f}, {float(da[latn].max()):.4f} (xmin, xmax, ymin, ymax)\n")
        da = da.sel({lonn: slice(map_lon_min - res_x / 2, map_lon_max + res_x / 2),
                     latn: slice(map_lat_min - res_y / 2, map_lat_max + res_y / 2)})
        lons = da[lonn].values.astype(float)
        lats = da[latn].values.astype(float)
        Z = da.values.astype(float)
    return lons, lats, Z, info


# ============================================================
# 42. geom_text_repel  (automatic label placement)
# ============================================================
def repel_labels(ax, fig, px, py, labels, nudge_x, nudge_y, fontsize, fontweight,
                 colour, seg_colour, seg_size, zorder, point_radius_pt=3.0, seed=42):
    """Places each label at (point + nudge), then pushes labels away from each other and from
    the points until they no longer overlap. A leader line joins every label to its point."""
    n = len(labels)
    if n == 0:
        return
    fontweight = "bold" if fontweight in ("bold", "bold.italic") else "normal"   # R fontface "plain" -> "normal"
    pos = ax.get_position()
    W = pos.width * fig.get_figwidth() * 72       # panel size in points
    H = pos.height * fig.get_figheight() * 72
    sx = W / (map_lon_max - map_lon_min)
    sy = H / (map_lat_max - map_lat_min)

    A = np.c_[(np.asarray(px, float) - map_lon_min) * sx, (np.asarray(py, float) - map_lat_min) * sy]
    C0 = A + np.c_[np.asarray(nudge_x, float) * sx, np.asarray(nudge_y, float) * sy]

    renderer = fig.canvas.get_renderer()
    wh = []
    for lab in labels:
        t = fig.text(0, 0, lab, fontsize=fontsize, fontweight=fontweight)
        bb = t.get_window_extent(renderer)
        wh.append((bb.width / fig.dpi * 72, bb.height / fig.dpi * 72))
        t.remove()
    wh = np.array(wh)
    half = wh / 2.0

    box_pad = label_box_padding * fontsize          # box.padding   (lines)
    pt_pad = label_point_padding * fontsize + point_radius_pt   # point.padding (lines)
    hb = half + box_pad / 2.0

    rng = np.random.default_rng(seed)
    C = C0 + rng.normal(0, 0.05, C0.shape)

    for it in range(600):
        F = np.zeros_like(C)

        # --- label <-> label overlap ---
        d = C[:, None, :] - C[None, :, :]
        ov = (hb[:, None, :] + hb[None, :, :]) - np.abs(d)
        for i in range(n):
            for j in range(i + 1, n):
                if ov[i, j, 0] > 0 and ov[i, j, 1] > 0:
                    k = 0 if ov[i, j, 0] < ov[i, j, 1] else 1
                    sgn = np.sign(d[i, j, k]) or (1.0 if rng.random() < 0.5 else -1.0)
                    push = ov[i, j, k] / 2.0 * sgn
                    F[i, k] += push
                    F[j, k] -= push

        # --- label <-> points (every label avoids every point) ---
        for i in range(n):
            lo = C[i] - hb[i]
            hi = C[i] + hb[i]
            for k in range(n):
                q = np.minimum(np.maximum(A[k], lo), hi)
                dv = A[k] - q
                dist = np.hypot(*dv)
                if dist < pt_pad:
                    if dist > 1e-9:
                        F[i] -= dv / dist * (pt_pad - dist)
                    else:                              # point inside the label box
                        away = C[i] - A[k]
                        if np.hypot(*away) < 1e-9:
                            away = np.array([1.0, 1.0])
                        F[i] += away / np.hypot(*away) * pt_pad

        # --- weak spring back to the starting position ---
        F += 0.02 * (C0 - C)

        C += F * 0.6
        C[:, 0] = np.clip(C[:, 0], half[:, 0], W - half[:, 0])
        C[:, 1] = np.clip(C[:, 1], half[:, 1], H - half[:, 1])

        if np.abs(F).max() < 0.02:
            break

    lx = map_lon_min + C[:, 0] / sx
    ly = map_lat_min + C[:, 1] / sy

    for i in range(n):
        # leader line from the label border to the point
        dv = A[i] - C[i]
        t_hit = np.inf
        if abs(dv[0]) > 1e-9:
            t_hit = min(t_hit, half[i, 0] / abs(dv[0]))
        if abs(dv[1]) > 1e-9:
            t_hit = min(t_hit, half[i, 1] / abs(dv[1]))
        if t_hit < 1.0:
            end = C[i] + dv * t_hit
            seg_len = np.hypot(*(A[i] - end))
            if seg_len > label_min_segment_length:
                ax.plot([map_lon_min + end[0] / sx, px[i]], [map_lat_min + end[1] / sy, py[i]],
                        color=seg_colour, lw=lw(seg_size), zorder=zorder, solid_capstyle="butt")
        ax.text(lx[i], ly[i], labels[i], fontsize=fontsize, fontweight=fontweight,
                color=colour, ha="center", va="center", zorder=zorder + 0.1)


# ============================================================
# 35. CREATE MAP
# ============================================================
def build_map(bath, land, sampling_data, label_data, transect_label_data):
    lons, lats, PlotDepth = bath

    fig_w, fig_h = output_width, output_height
    fig = plt.figure(figsize=(fig_w, fig_h))
    fig.patch.set_facecolor("white")

    # ---- layout: fixed map aspect (coord_sf), title above, legend on the right ----
    aspect = 1 / np.cos(np.radians((map_lat_min + map_lat_max) / 2))
    left_in, legend_in, title_in, bottom_in = 0.85, 1.4, 0.45, 0.75
    Wp = fig_w - left_in - legend_in
    Hp = Wp * (map_lat_max - map_lat_min) / (map_lon_max - map_lon_min) * aspect
    max_h = fig_h - title_in - bottom_in - 0.2
    if Hp > max_h:
        Hp = max_h
        Wp = Hp / ((map_lat_max - map_lat_min) / (map_lon_max - map_lon_min) * aspect)
    x0_in = (fig_w - (left_in + Wp + legend_in)) / 2 + left_in
    y0_in = (fig_h - (Hp + title_in + bottom_in)) / 2 + bottom_in
    ax = fig.add_axes([x0_in / fig_w, y0_in / fig_h, Wp / fig_w, Hp / fig_h])
    ax.set_facecolor("white")

    # ============================================================
    # 47. THEME (theme_minimal): grey80 major grid lines
    # ============================================================
    for lon in np.arange(np.ceil(map_lon_min), np.floor(map_lon_max) + 1):
        ax.axvline(lon, color="#CCCCCC", lw=lw(0.25), zorder=0.5)
    for lat in np.arange(np.ceil(map_lat_min), np.floor(map_lat_max) + 1):
        ax.axhline(lat, color="#CCCCCC", lw=lw(0.25), zorder=0.5)

    # ============================================================
    # 36. BATHYMETRY    /    37. BATHYMETRY COLOUR SCALE
    # ============================================================
    cmap = LinearSegmentedColormap.from_list("bathy", [
        "#E5F7FC",
        "#B8E5F2",
        "#78C6E0",
        "#3A9BC0",
        "#176B99",
        "#063B68",
    ])
    norm = Normalize(vmin=min_depth, vmax=max_depth, clip=True)
    cmap.set_bad((0, 0, 0, 0))                     # na.value = "transparent"
    dx = (lons[-1] - lons[0]) / (len(lons) - 1)
    dy = (lats[-1] - lats[0]) / (len(lats) - 1)
    ax.imshow(np.ma.masked_invalid(PlotDepth), cmap=cmap, norm=norm, origin="lower",
              interpolation="nearest", aspect="auto", zorder=1,
              extent=[lons[0] - dx / 2, lons[-1] + dx / 2, lats[0] - dy / 2, lats[-1] + dy / 2])

    # ============================================================
    # 40. LAND
    # ============================================================
    if land is not None and len(land) > 0:
        land.plot(ax=ax, facecolor="#E0E0E0", edgecolor="#333333", linewidth=lw(0.35), zorder=2)

    # ============================================================
    # 40b. SELECTED HIGHLIGHTED CONTOURS (10/20/30/50/100/200/500 m)
    # ============================================================
    Zm = np.ma.masked_invalid(PlotDepth)
    legend_handles, legend_labels = [], []
    if Zm.count() > 0:
        lv = [l for l in selected_contour_levels if Zm.min() < l < Zm.max()]
        if lv:
            cs = ax.contour(lons, lats, Zm, levels=lv,
                            colors=[selected_contour_colours[str(l)] for l in lv],
                            linewidths=lw(selected_contour_line_size), zorder=3)
            for l, segs in zip(lv, cs.allsegs):
                if len(segs) > 0:
                    legend_handles.append(Line2D([], [], color=selected_contour_colours[str(l)],
                                                 lw=lw(selected_contour_line_size)))
                    legend_labels.append(f"{l} m")

    # ============================================================
    # 41. SAMPLING POINTS
    # ============================================================
    ax.scatter(sampling_data["Longitude"], sampling_data["Latitude"],
               s=(sampling_point_size * PT) ** 2, marker="o", facecolors="red",
               edgecolors="white", linewidths=sampling_point_stroke * 3.78 / 2 * 0.75, zorder=4)

    # ---- map extent (coord_sf, expand = FALSE) ----
    ax.set_xlim(map_lon_min, map_lon_max)
    ax.set_ylim(map_lat_min, map_lat_max)
    ax.set_aspect(aspect)
    ax.apply_aspect()

    # ============================================================
    # 42. STATION LABELS (Sx ONLY, AT EACH POINT)
    # ============================================================
    repel_labels(ax, fig, label_data["Longitude"].to_numpy(), label_data["Latitude"].to_numpy(),
                 list(label_data["StationLabel"]),
                 (label_data["LabelLongitude"] - label_data["Longitude"]).to_numpy(),
                 (label_data["LabelLatitude"] - label_data["Latitude"]).to_numpy(),
                 fontsize=station_label_size * PT, fontweight=station_label_fontface,
                 colour=station_label_colour, seg_colour="#666666", seg_size=0.25,
                 zorder=5, seed=label_repel_seed)

    # ============================================================
    # 42b. TRANSECT LABELS (Tx, ONE PER TRANSECT, ON LAND)
    # ============================================================
    repel_labels(ax, fig, transect_label_data["AnchorLongitude"].to_numpy(),
                 transect_label_data["AnchorLatitude"].to_numpy(),
                 list(transect_label_data["TransectNumber"]),
                 (transect_label_data["LabelLongitude"] - transect_label_data["AnchorLongitude"]).to_numpy(),
                 (transect_label_data["LabelLatitude"] - transect_label_data["AnchorLatitude"]).to_numpy(),
                 fontsize=transect_label_size * PT, fontweight=transect_label_fontface,
                 colour=transect_label_colour, seg_colour="#333333", seg_size=0.3,
                 zorder=5.5, seed=label_repel_seed)

    pos = ax.get_position()
    w_in = pos.width * fig_w
    h_in = pos.height * fig_h
    cm = 1 / 2.54
    deg_x = (map_lon_max - map_lon_min) / w_in      # degrees per inch
    deg_y = (map_lat_max - map_lat_min) / h_in

    # ============================================================
    # 43. NORTH ARROW   (top-right, 1 cm x 1 cm, fancy orienteering)
    # ============================================================
    size_in = 1.0 * cm
    pad_in = 0.25 * cm
    ia = ax.inset_axes([1 - (pad_in + size_in) / w_in, 1 - (pad_in + size_in) / h_in,
                        size_in / w_in, size_in / h_in], zorder=9)
    ia.set_xlim(0, 1)
    ia.set_ylim(0, 1)
    ia.axis("off")
    ia.add_patch(Polygon([(0.5, 0.80), (0.22, 0.10), (0.5, 0.30)], closed=True,
                         fc="black", ec="black", lw=0.8))
    ia.add_patch(Polygon([(0.5, 0.80), (0.78, 0.10), (0.5, 0.30)], closed=True,
                         fc="white", ec="black", lw=0.8))
    ia.text(0.5, 0.99, "N", color="black", ha="center", va="top", fontsize=9,
            fontweight="bold")

    # ============================================================
    # 44. SCALE BAR   (bottom-left, width hint 0.25, metric)
    # ============================================================
    mid_lat = (map_lat_min + map_lat_max) / 2
    km_per_deg = 111.320 * np.cos(np.radians(mid_lat))
    hint_km = scale_bar_width_hint * (map_lon_max - map_lon_min) * km_per_deg
    cands = [m * 10.0 ** k for k in range(0, 5) for m in (1, 2, 5)]
    nice = max([c for c in cands if c <= hint_km] or [1])
    bar_deg = nice / km_per_deg
    sx0 = map_lon_min + 0.25 * cm * deg_x
    sy0 = map_lat_min + 0.25 * cm * deg_y
    bh = 0.15 * cm * deg_y
    ax.add_patch(Rectangle((sx0, sy0), bar_deg / 2, bh, fc="black", ec="black",
                           lw=lw(0.7), zorder=8))
    ax.add_patch(Rectangle((sx0 + bar_deg / 2, sy0), bar_deg / 2, bh, fc="white", ec="black",
                           lw=lw(0.7), zorder=8))
    ty = sy0 + bh + 0.05 * cm * deg_y
    for xx, lab in ((sx0, "0"), (sx0 + bar_deg / 2, f"{nice / 2:g}"),
                    (sx0 + bar_deg, f"{nice:g} km")):
        ax.text(xx, ty, lab, ha="center", va="bottom", fontsize=0.8 * 8.5, zorder=8)

    # ============================================================
    # 46. AXIS / TITLE      /      47. THEME
    # ============================================================
    xt = np.arange(np.ceil(map_lon_min), np.floor(map_lon_max) + 1)
    yt = np.arange(np.ceil(map_lat_min), np.floor(map_lat_max) + 1)
    ax.set_xticks(xt)
    ax.set_yticks(yt)
    ax.set_xticklabels([f"{v:g}°E" for v in xt])
    ax.set_yticklabels([f"{v:g}°N" for v in yt])
    ax.tick_params(length=0, labelsize=10, labelcolor="black", pad=3)
    ax.set_xlabel("Longitude (°E)", fontsize=12, fontweight="bold", labelpad=6)
    ax.set_ylabel("Latitude (°N)", fontsize=12, fontweight="bold", labelpad=6)
    for s in ax.spines.values():
        s.set_color("black")
        s.set_linewidth(lw(0.7))
        s.set_zorder(30)
    fig.text((x0_in + Wp / 2) / fig_w, (y0_in + Hp + 0.12) / fig_h,
             "Sampling Location and Bathymetry Map", ha="center", va="bottom",
             fontsize=15, fontweight="bold")

    if legend_handles:
        leg = ax.legend(legend_handles, legend_labels, title="Depth (m)", loc="center left",
                        bbox_to_anchor=(1.03, 0.5), frameon=False, fontsize=9,
                        title_fontproperties={"weight": "bold", "size": 12},
                        handlelength=1.9, borderaxespad=0)
        leg._legend_box.align = "left"
        leg.set_zorder(10)

    return fig


# ============================================================
#  MAIN PIPELINE   (sections 2 - 52 of the R script)
# ============================================================
def run_map(excel_data, excel_name, sheet_name, gebco_file, dpi):
    _LOG.clear()
    _WARNINGS.clear()

    # ============================================================
    # 2. SELECT INPUT FILES   (done in the app: Excel file, sheet and GEBCO file are chosen in the sidebar)
    # ============================================================
    cat("\n")
    cat("Excel file :", excel_name, "\n")
    cat("Sheet      :", sheet_name, "\n")
    cat("GEBCO file :", os.path.basename(gebco_file), "\n")

    # ============================================================
    # 14. READ EXCEL
    # ============================================================
    cat("\n")
    cat("====================================================\n")
    cat("READING EXCEL FILE\n")
    cat("====================================================\n")

    cat("\nExcel columns found:\n")
    cat(list(excel_data.columns), "\n")

    # ============================================================
    # 15. FIND REQUIRED COLUMNS
    #     (this Excel writes the headers with units, e.g. "Latitude (°N)" -> the unit part is ignored)
    # ============================================================
    column_names_lower = [re.sub(r"\s*[\(\[].*$", "", str(c).strip().lower()).strip()
                          for c in excel_data.columns]

    # ------------------------------------------------------------
    # STATION NAME
    # ------------------------------------------------------------
    station_name_candidates = [
        "station name",
        "station_name",
        "stationname",
    ]

    station_name_index = [i for i, c in enumerate(column_names_lower)
                          if c in station_name_candidates]

    if len(station_name_index) == 0:
        st.error("ERROR: Could not find the Station Name column.\n"
                 "Please name the column 'Station Name'.")
        st.stop()

    station_name_column = excel_data.columns[station_name_index[0]]

    # ------------------------------------------------------------
    # LATITUDE
    # ------------------------------------------------------------
    latitude_candidates = [
        "latitude",
        "lat",
    ]

    latitude_index = [i for i, c in enumerate(column_names_lower)
                      if c in latitude_candidates]

    if len(latitude_index) == 0:
        st.error("ERROR: Could not find Latitude column.\n"
                 "Please name the column 'Latitude'.")
        st.stop()

    latitude_column = excel_data.columns[latitude_index[0]]

    # ------------------------------------------------------------
    # LONGITUDE
    # ------------------------------------------------------------
    longitude_candidates = [
        "longitude",
        "lon",
        "long",
    ]

    longitude_index = [i for i, c in enumerate(column_names_lower)
                       if c in longitude_candidates]

    if len(longitude_index) == 0:
        st.error("ERROR: Could not find Longitude column.\n"
                 "Please name the column 'Longitude'.")
        st.stop()

    longitude_column = excel_data.columns[longitude_index[0]]

    cat("\n")
    cat("Station Name column :", station_name_column, "\n")
    cat("Latitude column :", latitude_column, "\n")
    cat("Longitude column:", longitude_column, "\n")

    # ============================================================
    # 16. CLEAN SAMPLING DATA
    # ============================================================
    sampling_data = pd.DataFrame({
        "Station Name": excel_data[station_name_column].map(
            lambda v: None if pd.isna(v) else str(v).strip()),
        "Latitude": dmm_to_decimal(excel_data[latitude_column]),
        "Longitude": dmm_to_decimal(excel_data[longitude_column]),
    })

    sampling_data = sampling_data[
        sampling_data["Station Name"].notna()
        & sampling_data["Latitude"].notna()
        & sampling_data["Longitude"].notna()
    ].reset_index(drop=True)

    # This Excel has one row per station AND depth: keep one point per station (first row = shallowest)
    n_rows = len(sampling_data)
    sampling_data = sampling_data.drop_duplicates(subset="Station Name", keep="first").reset_index(drop=True)
    if len(sampling_data) < n_rows:
        cat(f"\n({n_rows} rows found, several depths per station -> {len(sampling_data)} stations kept, "
            "first row of each station)\n")

    # ============================================================
    # 17. DISPLAY SAMPLING DATA
    # ============================================================
    cat("\n")
    cat("====================================================\n")
    cat("SAMPLING LOCATIONS\n")
    cat("====================================================\n\n")

    cat(sampling_data.to_string(index=False), "\n")

    cat("\nNumber of sampling locations:", len(sampling_data), "\n\n")

    # ============================================================
    # 18. CHECK MAP EXTENT
    # ============================================================
    outside_points = sampling_data[
        (sampling_data["Longitude"] < map_lon_min)
        | (sampling_data["Longitude"] > map_lon_max)
        | (sampling_data["Latitude"] < map_lat_min)
        | (sampling_data["Latitude"] > map_lat_max)
    ]

    if len(outside_points) > 0:
        _WARNINGS.append(
            "Some Excel sampling points are outside the selected map extent.\n\n"
            + ", ".join(outside_points["Station Name"])
        )

    # ============================================================
    # 19. READ GEBCO USING XARRAY (terra)
    # ============================================================
    cat("\n")
    cat("====================================================\n")
    cat("READING GEBCO FILE\n")
    cat("====================================================\n\n")

    cat("GEBCO file:\n")
    cat(gebco_file)
    cat("\n\n")

    try:
        lons, lats, Z, gebco_info = read_gebco(gebco_file)
    except Exception as e:  # noqa
        st.error("ERROR while reading GEBCO NetCDF file:\n" + str(e)
                 + "\n\nPlease check that the selected file is a valid GEBCO NetCDF bathymetry file.")
        st.stop()

    cat("GEBCO successfully loaded.\n\n")

    cat("GEBCO information:\n")

    cat(gebco_info)

    # ============================================================
    # 20. CHECK GEBCO CRS   /   21. SET CRS IF NECESSARY
    # ============================================================
    cat("\nGEBCO CRS:\n")
    cat("EPSG:4326 (longitude / latitude)\n")

    # ============================================================
    # 22. CROP GEBCO TO MANUAL MAP EXTENT   (done while reading)
    # ============================================================
    cat("\nCropping GEBCO to selected region...\n")

    cat("GEBCO crop complete.\n")

    # ============================================================
    # 23. CHECK CROPPED DATA
    # ============================================================
    if Z.size == 0:
        st.error("ERROR: No GEBCO cells were found inside the selected map extent.\n\n"
                 f"Longitude: {map_lon_min} to {map_lon_max}\n"
                 f"Latitude: {map_lat_min} to {map_lat_max}")
        st.stop()

    # ============================================================
    # 24. CONVERT GEBCO ELEVATION TO DEPTH   (land = positive elevation, ocean = negative)
    # ============================================================
    Depth = -Z

    # ============================================================
    # 25. CREATE BATHYMETRY DATA   (rows = latitude, columns = longitude)
    # ============================================================
    cat("\nConverting bathymetry to plotting data...\n")

    # ============================================================
    # 26. REMOVE LAND FROM BATHYMETRY DATA
    # ============================================================
    OceanDepth = np.where(Depth > 0, Depth, np.nan)

    # ============================================================
    # 27. LIMIT DEPTH TO 2500 M FOR COLOUR SCALE
    # ============================================================
    PlotDepth = np.where(~np.isnan(OceanDepth), np.minimum(OceanDepth, max_depth), np.nan)

    # ============================================================
    # 28. CHECK BATHYMETRY VALUES
    # ============================================================
    valid_depths = OceanDepth[~np.isnan(OceanDepth)]

    if len(valid_depths) == 0:
        st.error("ERROR: No ocean bathymetry was detected in the selected GEBCO region.")
        st.stop()

    cat("\nBathymetry statistics:\n")

    cat("Minimum ocean depth:", num(valid_depths.min()), "m\n")

    cat("Maximum ocean depth:", num(valid_depths.max()), "m\n")

    # ============================================================
    # 30. LOAD LAND
    # ============================================================
    cat("\nLoading India/land polygons...\n")

    land = load_land()

    # ============================================================
    # 32. PREPARE LABEL DATA
    # ============================================================
    #
    # Split "Tx Sx" (e.g. "T4 S2") into:
    #
    #   TransectNumber -> "T4"
    #   StationNumber  -> "S2"   (this is what gets drawn at the point)
    #
    # ============================================================

    label_data = sampling_data.copy()
    label_data["TransectNumber"] = [re.sub(r"^\s*(T[0-9]+).*$", r"\1", s) for s in label_data["Station Name"]]
    label_data["StationLabel"] = [re.sub(r"^.*\b(S[0-9]+)\s*$", r"\1", s) for s in label_data["Station Name"]]
    label_data["LabelLongitude"] = label_data["Longitude"] + default_label_x_offset
    label_data["LabelLatitude"] = label_data["Latitude"] + default_label_y_offset

    bad_format = label_data["TransectNumber"] == label_data["Station Name"]
    if bad_format.any():
        _WARNINGS.append(
            "Some Station Name values do not match the expected 'Tx Sx' format "
            "(e.g. 'T4 S2'). Check these rows:\n\n"
            + ", ".join(label_data.loc[bad_format, "Station Name"])
        )

    # ============================================================
    # 33. APPLY MANUAL LABEL POSITIONS
    # ============================================================
    if len(manual_label_positions) > 0:

        for label_name, position in manual_label_positions.items():

            matching_rows = label_data["Station Name"] == label_name

            if matching_rows.any():

                label_data.loc[matching_rows, "LabelLongitude"] = position[0]

                label_data.loc[matching_rows, "LabelLatitude"] = position[1]

    # ============================================================
    # 34. DISPLAY LABEL POSITIONS
    # ============================================================
    cat("\n")
    cat("====================================================\n")
    cat("LABEL POSITIONS\n")
    cat("====================================================\n\n")

    cat(label_data[["Station Name", "Longitude", "Latitude", "LabelLongitude",
                    "LabelLatitude"]].to_string(index=False), "\n")

    # ============================================================
    # 34b. BUILD ONE Tx LABEL PER TRANSECT (ON LAND)
    # ============================================================
    idx = label_data.groupby("TransectNumber")["Longitude"].idxmax()
    top = label_data.loc[idx]

    transect_label_data = pd.DataFrame({
        "TransectNumber": top["TransectNumber"].to_numpy(),
        "AnchorLongitude": top["Longitude"].to_numpy(),
        "AnchorLatitude": top["Latitude"].to_numpy(),
        "LabelLongitude": top["Longitude"].to_numpy() + transect_label_land_offset,
        "LabelLatitude": top["Latitude"].to_numpy(),
    })

    if len(manual_transect_label_positions) > 0:

        for label_name, position in manual_transect_label_positions.items():

            matching_rows = transect_label_data["TransectNumber"] == label_name

            if matching_rows.any():

                transect_label_data.loc[matching_rows, "LabelLongitude"] = position[0]

                transect_label_data.loc[matching_rows, "LabelLatitude"] = position[1]

    cat("\n")
    cat("====================================================\n")
    cat("TRANSECT (Tx) LABEL POSITIONS\n")
    cat("====================================================\n\n")

    cat(transect_label_data.to_string(index=False), "\n")

    # ============================================================
    # 35. CREATE MAP  ...  47. THEME
    # ============================================================
    cat("\nCreating map...\n")

    fig = build_map((lons, lats, PlotDepth), land, sampling_data, label_data, transect_label_data)

    # ============================================================
    # 48. DISPLAY MAP BEFORE SAVING   (preview shown in the app)
    # ============================================================
    cat("\n")
    cat("Displaying map...\n\n")

    preview = io.BytesIO()
    fig.savefig(preview, format="png", dpi=110, facecolor="white")

    # ============================================================
    # 49. SAVE PNG      /      50. SAVE TIFF  (lzw)
    # ============================================================
    cat("\n")
    cat("Saving PNG...\n")
    cat("Saving TIFF...\n")

    fig.set_dpi(dpi)
    fig.canvas.draw()
    rgb = np.asarray(fig.canvas.buffer_rgba())[..., :3]
    img = Image.fromarray(np.ascontiguousarray(rgb))
    plt.close(fig)

    png_bytes = io.BytesIO()
    img.save(png_bytes, format="PNG", dpi=(dpi, dpi))
    tiff_bytes = io.BytesIO()
    img.save(tiff_bytes, format="TIFF", compression="tiff_lzw", dpi=(dpi, dpi))
    del img, rgb

    os.makedirs(output_folder, exist_ok=True)
    with open(png_file, "wb") as f:
        f.write(png_bytes.getvalue())
    with open(tiff_file, "wb") as f:
        f.write(tiff_bytes.getvalue())

    # ============================================================
    # 51. VERIFY OUTPUT FILES
    # ============================================================
    cat("\n")
    cat("====================================================\n")
    cat("VERIFYING OUTPUT FILES\n")
    cat("====================================================\n\n")

    if not os.path.exists(png_file):
        st.error("ERROR: PNG file was not created.")
        st.stop()

    if not os.path.exists(tiff_file):
        st.error("ERROR: TIFF file was not created.")
        st.stop()

    png_size = os.path.getsize(png_file)

    tiff_size = os.path.getsize(tiff_file)

    if png_size <= 0:
        st.error("ERROR: PNG file exists but has 0 bytes.")
        st.stop()

    if tiff_size <= 0:
        st.error("ERROR: TIFF file exists but has 0 bytes.")
        st.stop()

    # ============================================================
    # 52. FINAL REPORT
    # ============================================================
    cat("\n")
    cat("====================================================\n")
    cat("MAP CREATION SUCCESSFUL\n")
    cat("====================================================\n\n")

    cat("PNG:\n")
    cat(png_file)
    cat("\n")

    cat("PNG size:", round(png_size / 1024, 1), "KB\n\n")

    cat("TIFF:\n")
    cat(tiff_file)
    cat("\n")

    cat("TIFF size:", round(tiff_size / 1024, 1), "KB\n\n")

    cat("Map extent:\n")

    cat(map_lon_min, "°E to", map_lon_max, "°E\n")

    cat(map_lat_min, "°N to", map_lat_max, "°N\n")

    cat("\nNumber of sampling locations:")

    cat(len(sampling_data))

    cat("\n\nBathymetry colour range: 0–")

    cat(max_depth)

    cat(" m+\n")

    cat("\n")
    cat("Output folder:\n")
    cat(output_folder)
    cat("\n\n")

    cat("====================================================\n")

    return {"preview": preview.getvalue(), "png": png_bytes.getvalue(),
            "tiff": tiff_bytes.getvalue(), "png_file": png_file, "tiff_file": tiff_file,
            "log": "".join(_LOG), "warnings": list(_WARNINGS)}


# ============================================================
#  STREAMLIT APP
# ============================================================
def main():
    st.set_page_config(page_title="Sampling Location Map", page_icon="🗺️", layout="wide")
    st.title("SAMPLING LOCATION + GEBCO BATHYMETRY MAP")
    st.caption("Station Name | Latitude | Longitude | ...   (station names like 'T1 S1')")

    # ============================================================
    # 2. SELECT INPUT FILES
    # ============================================================
    st.sidebar.header("Input files")
    excel_upload = st.sidebar.file_uploader(
        "Select the EXCEL file containing sampling locations", type=["xlsx", "xlsm", "xls"])
    gebco_upload = st.sidebar.file_uploader("Select the GEBCO NetCDF (.nc) file", type=["nc"])
    gebco_path_text = st.sidebar.text_input(
        "...or type the full path of a local GEBCO .nc file (for very large files)", "")

    res = st.session_state.get("sampling_result")

    if excel_upload is None:
        st.info("Upload an Excel file in the sidebar to begin.")
        if res:
            _show_result(res)
        return

    # ============================================================
    # 14. READ EXCEL   (any sheet can be selected)
    # ============================================================
    try:
        xl = pd.ExcelFile(excel_upload)
    except Exception as e:  # noqa
        st.error(f"Could not read the Excel file: {e}")
        return
    sheet_name = st.sidebar.selectbox("Excel sheet", xl.sheet_names)
    excel_data = pd.read_excel(xl, sheet_name=sheet_name)

    with st.expander(f"Preview of sheet '{sheet_name}'  ({excel_data.shape[0]} rows x "
                     f"{excel_data.shape[1]} columns)"):
        st.dataframe(excel_data.head(30))

    with st.sidebar.expander("Advanced settings"):
        dpi = st.number_input("output_dpi  (R script: 1200; lower = faster / smaller files)",
                              value=1200, min_value=72, max_value=1200, step=100)

    if st.sidebar.button("Generate map", type="primary"):
        import tempfile
        tmp_path = None
        if gebco_upload is not None:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".nc") as tmp:
                tmp.write(gebco_upload.getbuffer())
                tmp_path = tmp.name
            gebco_file = tmp_path
        elif gebco_path_text.strip() and os.path.isfile(gebco_path_text.strip().strip('"')):
            gebco_file = gebco_path_text.strip().strip('"')
        else:
            st.error("Please select the GEBCO NetCDF file (upload it, or type a valid local path).")
            return
        try:
            with st.spinner("Creating the map (this can take a minute at 1200 dpi)..."):
                st.session_state["sampling_result"] = run_map(
                    excel_data, excel_upload.name, sheet_name, gebco_file, int(dpi))
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
        res = st.session_state.get("sampling_result")

    if res:
        _show_result(res)
    else:
        st.info("Choose the sheet in the sidebar, upload the GEBCO file, then press **Generate map**.")


def _show_result(res):
    for w in res.get("warnings", []):
        st.warning(w)
    st.image(res["preview"])
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("Download map (PNG)", data=res["png"],
                           file_name="Sampling_Location_Bathymetry_Map.png", mime="image/png")
    with c2:
        st.download_button("Download map (TIFF)", data=res["tiff"],
                           file_name="Sampling_Location_Bathymetry_Map.tiff", mime="image/tiff")
    st.success(f"Saved:  {res['png_file']}   and   {res['tiff_file']}")
    with st.expander("Console output"):
        st.code(res["log"])


if __name__ == "__main__":
    main()
