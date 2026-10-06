# -*- coding: utf-8 -*-
# ================================================================
# MULTI-PARAMETER / MULTI-TRANSECT WATER COLUMN PROFILE
# (Python / Streamlit version of line-plot.R)
# ================================================================
#
# Excel structure:
#
# Station | Depth | Parameter 1 | Parameter 2 | Parameter 3 | ...
#
# Example station names:
# T1 S1
# T1 S2
# T2 S1
# T2 S2
#
# MODE 1:
# One station + multiple parameters
#
# MODE 2:
# One station number + one parameter + multiple transects
#
# Maximum number of profiles/parameters = 10
#
# Output:
# - The plot is shown in the browser (so you can check it before/without
#   opening the file).
# - A TIFF file is also saved (in the "outputs" folder next to this file)
#   and can be downloaded from the app.
#
# RUN:    streamlit run Line_plot.py
#
# ================================================================


# ================================================================
# 1. REQUIRED PACKAGE
# ================================================================
#
#   pip install streamlit numpy pandas openpyxl matplotlib pillow
#
# (readxl -> pandas/openpyxl, base R graphics -> matplotlib)

import io
import os
import re

import numpy as np
import pandas as pd
import streamlit as st

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

plt.rcParams["font.sans-serif"] = ["Arial", "Helvetica", "DejaVu Sans"]

APP_DIR = os.path.dirname(os.path.abspath(__file__))
excel_folder = os.path.join(APP_DIR, "outputs")   # replaces R's  excel_folder  (TIFF is saved here)

LWD = 0.75        # R: lwd 1 = 1/96 inch = 0.75 pt

# Everything R prints with cat()/print() is collected here and shown in the app.
_LOG = []


def cat(*args, sep=" "):
    _LOG.append(sep.join(str(a) for a in args))


# ------------------------------------------------------------
# R helpers:  pretty()  and  format(trim = TRUE, scientific = FALSE)
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


def r_format(vals):
    """R: format(vals, trim = TRUE, scientific = FALSE)  (common number of decimals)."""
    vals = [float(v) for v in vals]
    decs = 0
    for v in vals:
        if v == 0:
            continue
        s = float(f"{v:.7g}")
        for d in range(0, 16):
            if abs(round(s, d) - s) <= 1e-12 * abs(s):
                decs = max(decs, d)
                break
    return [f"{v:.{decs}f}" for v in vals]


def r_num(v):
    """R: as.character / paste of a number."""
    return f"{float(v):.15g}"


# ================================================================
# 11. COLOUR ORDER
# ================================================================

profile_colours = [
    "#FF0000",   # red
    "#00FF00",   # green
    "#0000FF",   # blue
    "#FFA500",   # orange
    "#FFC0CB",   # pink
    "#A52A2A",   # brown
    "#EE82EE",   # violet
    "#87CEEB",   # skyblue
    "#FFFF00",   # yellow
    "#BEBEBE",   # grey
]


# ================================================================
# 5. FUNCTION TO FIND A COLUMN
# ================================================================

def find_column(data, possible_names):

    actual_names = list(data.columns)
    lower_actual = [str(a).lower() for a in actual_names]

    match_index = [lower_actual.index(p.lower()) for p in possible_names
                   if p.lower() in lower_actual]

    if len(match_index) == 0:
        return None

    return actual_names[match_index[0]]


def to_numeric(x):
    return pd.to_numeric(x, errors="coerce")


# ================================================================
# 4. - 10. PREPARE THE EXCEL DATA
# ================================================================
def prepare_data(data_raw):
    """Returns (data, station_col, depth_col, parameter_columns). Raises ValueError on the R stop() cases."""
    data = data_raw.copy()

    # ================================================================
    # 6. FIND STATION COLUMN
    # ================================================================
    station_col = find_column(
        data,
        [
            "Station",
            "Station_ID",
            "Station ID",
            "Station Name",
            "Station_Name",
        ]
    )

    # ================================================================
    # 7. FIND DEPTH COLUMN
    # ================================================================
    depth_col = find_column(
        data,
        [
            "Depth",
            "Depth_m",
            "Depth (m)",
            "Depth_meters",
            "Depth (meters)",
        ]
    )

    # ================================================================
    # 8. CHECK REQUIRED COLUMNS
    # ================================================================
    if station_col is None:
        raise ValueError("ERROR: Station column was not found.")

    if depth_col is None:
        raise ValueError("ERROR: Depth column was not found.")

    # ================================================================
    # 9. CLEAN STATION AND DEPTH
    #    (depths are written like "0m", "5m", "10m" in this Excel -> keep the number)
    # ================================================================
    data[station_col] = data[station_col].map(lambda v: None if pd.isna(v) else str(v).strip())
    data[depth_col] = to_numeric(
        data[depth_col].astype(str).str.extract(r"(-?\d+(?:\.\d+)?)")[0])

    # ================================================================
    # 10. IDENTIFY PARAMETER COLUMNS
    # ================================================================
    excluded_columns = [station_col, depth_col]

    possible_parameters = [c for c in data.columns if c not in excluded_columns]

    parameter_columns = [c for c in possible_parameters
                         if to_numeric(data[c]).notna().sum() > 0]

    if len(parameter_columns) == 0:
        raise ValueError("ERROR: No numeric parameter columns were found.")

    return data, station_col, depth_col, parameter_columns


# ================================================================
# 12. SHARED CANVAS / LAYOUT ENGINE
# ================================================================
#
# This is the ONE place that draws the two-panel figure
# (stacked X-axes on top, coloured depth profile below) for BOTH
# Mode 1 (parameters) and Mode 2 (transects), so the two modes
# can never drift out of sync with each other.
#
# HOW THE ALIGNMENT IS GUARANTEED
# --------------------------------
# Both panels plot on the exact same internal x-scale, 0 to 1
# ("profile_left" to "profile_right"), and - critically - both
# panels are forced to use the EXACT SAME left/right physical
# boundary on the page (`panel_left_frac` / `panel_right_frac`,
# expressed as fractions of the page width). That is what makes:
#
#   - every stacked X-axis exactly the same width,
#   - axis minimum  = left edge of the profile,
#   - axis maximum  = right edge of the profile,
#   - the depth axis touch the left end of the bottom line,
#   - the bottom line's right end meet the X-axes' right end,
#
# ...all true automatically, rather than by manually nudging
# numbers until it "looks right".
#
# The left-hand gutter (reserved for the parameter/transect names
# and the depth axis) and the right-hand gutter (reserved for the
# legend) are both sized AUTOMATICALLY from the actual text, so
# long names are never cropped, however long they are.
#
# ================================================================

# ----------------------------------------------------------------
# TUNABLE SETTINGS
# ----------------------------------------------------------------
# label_gap_in:
#   Distance (in inches) between the start of the coloured axis
#   and the parameter/transect name.
#   INCREASE this to push the names further LEFT.
#   DECREASE this to bring them closer to the axis.
# ----------------------------------------------------------------

label_gap_in = 0.12


def draw_two_panel_profile(
        item_names,
        item_data,
        max_depth,
        plot_title,
        legend_title,
        label_gap_in=0.12
):

    n_items = len(item_names)

    # Page = 1800 x 2400 px at 200 dpi (as the R tiff() call)
    dev_width_in = 9.0
    dev_height_in = 12.0
    fig = plt.figure(figsize=(dev_width_in, dev_height_in), dpi=200)
    fig.patch.set_facecolor("white")
    renderer = fig.canvas.get_renderer()

    def strwidth_in(labels, size, weight):
        w = 0.0
        for s in labels:
            t = fig.text(0, 0, s, fontsize=size, fontweight=weight)
            w = max(w, t.get_window_extent(renderer).width / fig.dpi)
            t.remove()
        return w

    # --------------------------------------------------------------
    # DYNAMIC LEFT GUTTER
    # Sized to the widest parameter/transect name so nothing is ever
    # cropped, then shifted further left by `label_gap_in`.
    # --------------------------------------------------------------
    max_label_in = strwidth_in(item_names, 12 * 0.88, "bold")

    edge_pad_in = 0.08
    left_gutter_in = max_label_in + label_gap_in + edge_pad_in
    panel_left_frac = min(max(left_gutter_in / dev_width_in, 0.15), 0.55)

    # --------------------------------------------------------------
    # DYNAMIC RIGHT GUTTER
    # Sized to fit the legend text so it is never cut off.
    # --------------------------------------------------------------
    max_legend_in = strwidth_in(item_names, 12 * 0.85, "normal")

    legend_swatch_in = 0.45
    right_gutter_in = legend_swatch_in + max_legend_in * 1.12 + edge_pad_in + 0.15
    panel_right_frac = max(min(1 - right_gutter_in / dev_width_in, 0.85), 0.55)

    plot_width_in = dev_width_in * (panel_right_frac - panel_left_frac)
    data_units_per_inch = 1 / plot_width_in
    label_gap_data = label_gap_in * data_units_per_inch

    # --------------------------------------------------------------
    # TWO-PANEL LAYOUT
    # TOP    = stacked X-axes
    # BOTTOM = coloured profile
    # heights = c(0.34, 0.66);  margins: top panel mar = c(1,1,2,1), bottom panel mar = c(5,1,2,1)
    # --------------------------------------------------------------
    line_in = 0.2
    region2_h = 0.66 * dev_height_in
    top_y0, top_y1 = region2_h + 1 * line_in, dev_height_in - 2 * line_in
    bot_y0, bot_y1 = 5 * line_in, region2_h - 2 * line_in
    left_in = panel_left_frac * dev_width_in

    def add_panel(y0, y1):
        ax = fig.add_axes([left_in / dev_width_in, y0 / dev_height_in,
                           plot_width_in / dev_width_in, (y1 - y0) / dev_height_in])
        ax.set_axis_off()
        return ax

    profile_left = 0
    profile_right = 1
    profile_width = profile_right - profile_left

    # ================================================================
    # TOP PANEL - STACKED AXES
    # ================================================================

    ax1 = add_panel(top_y0, top_y1)
    ax1.set_xlim(0, 1)
    ax1.set_ylim(0, n_items + 1)

    for i, item_name in enumerate(item_names, start=1):

        current_data = item_data[item_name]
        current_colour = profile_colours[i - 1]

        current_min = current_data["value"].min()
        current_max = current_data["value"].max()

        # ------------------------------------------------------------
        # HANDLE CONSTANT VALUES
        # ------------------------------------------------------------
        if current_min == current_max:
            padding = 1 if current_min == 0 else abs(current_min) * 0.05
            current_min = current_min - padding
            current_max = current_max + padding

        y_position = n_items - i + 1

        # ------------------------------------------------------------
        # MAIN COLOURED AXIS
        # Runs EXACTLY from profile_left to profile_right - identical
        # width for every stacked axis, and identical to the profile
        # panel's left/right edges below.
        # ------------------------------------------------------------
        ax1.plot([profile_left, profile_right], [y_position, y_position],
                 color=current_colour, lw=2 * LWD, solid_capstyle="butt", clip_on=False)

        # ------------------------------------------------------------
        # TICKS
        # ------------------------------------------------------------
        ticks = r_pretty(current_min, current_max)
        ticks = ticks[(ticks >= current_min) & (ticks <= current_max)]

        if len(ticks) < 2:
            ticks = np.linspace(current_min, current_max, 5)

        tick_x = profile_left + ((ticks - current_min) / (current_max - current_min)) * profile_width

        for tx in tick_x:
            ax1.plot([tx, tx], [y_position, y_position - 0.10], color=current_colour,
                     lw=1.5 * LWD, solid_capstyle="butt", clip_on=False)

        for tx, lab in zip(tick_x, r_format(ticks)):
            ax1.text(tx, y_position - 0.27, lab, color=current_colour, fontsize=12 * 0.8,
                     ha="center", va="center", clip_on=False)

        # ------------------------------------------------------------
        # PARAMETER / TRANSECT NAME
        # Placed in the left-hand gutter, `label_gap_in` inches to the
        # left of the axis start. The gutter is always wide enough for
        # the longest name in the set, so it is never cropped.
        # ------------------------------------------------------------
        name_offset_data = (0.5 * 0.15 * 0.88) * data_units_per_inch   # pos = 2 offset
        ax1.text(profile_left - label_gap_data - name_offset_data, y_position, item_name,
                 color=current_colour, fontweight="bold", fontsize=12 * 0.88,
                 ha="right", va="center", clip_on=False)

    # ================================================================
    # BOTTOM PANEL - PROFILE
    # ================================================================

    ax2 = add_panel(bot_y0, bot_y1)
    ax2.set_xlim(0, 1)
    ax2.set_ylim(max_depth, 0)

    # ----------------------------------------------------------------
    # DEPTH TICKS / AXIS
    # Drawn at x = profile_left = 0, exactly where every stacked
    # X-axis and the bottom horizontal line also start.
    # ----------------------------------------------------------------
    depth_ticks = r_pretty(0, max_depth)
    depth_ticks = depth_ticks[(depth_ticks >= 0) & (depth_ticks <= max_depth)]

    ax2.plot([0, 0], [depth_ticks[0], depth_ticks[-1]], color="black", lw=1.5 * LWD,
             solid_capstyle="butt", clip_on=False)
    for d in depth_ticks:
        ax2.plot([0, -0.1 * data_units_per_inch], [d, d], color="black", lw=1.5 * LWD,
                 solid_capstyle="butt", clip_on=False)
        ax2.text(-0.2 * data_units_per_inch, d, r_num(d) + " m", color="black", fontsize=12,
                 ha="right", va="center", clip_on=False)

    # abline(h = depth_ticks, col = "grey85", lty = 3)
    for d in depth_ticks:
        ax2.plot([0, 1], [d, d], color="#D9D9D9", lw=LWD, linestyle=(0, (1, 3)), zorder=0)

    # mtext("Depth (m)", side = 2, line = 3.3, font = 2)
    ax2.text(-3.3 * line_in * data_units_per_inch, max_depth / 2, "Depth (m)", rotation=90,
             rotation_mode="anchor", ha="center", va="baseline", fontweight="bold",
             fontsize=12, clip_on=False)

    # ----------------------------------------------------------------
    # COLOURED PROFILES
    # Normalised onto the SAME profile_left/profile_right span as the
    # stacked axes above, so the plotted line for each parameter runs
    # exactly between its own axis minimum and maximum.
    # ----------------------------------------------------------------
    for i, item_name in enumerate(item_names, start=1):

        current_data = item_data[item_name]
        current_colour = profile_colours[i - 1]

        current_min = current_data["value"].min()
        current_max = current_data["value"].max()

        if current_min == current_max:
            padding = 1 if current_min == 0 else abs(current_min) * 0.05
            current_min = current_min - padding
            current_max = current_max + padding

        normalized_x = (current_data["value"] - current_min) / (current_max - current_min)
        profile_x = profile_left + normalized_x * profile_width

        ax2.plot(profile_x, current_data["depth"], color=current_colour, lw=3 * LWD)

    # ----------------------------------------------------------------
    # BOTTOM HORIZONTAL LINE
    # Left end  = exactly where the depth axis is (profile_left).
    # Right end = exactly where every stacked X-axis ends
    #             (profile_right).
    # ----------------------------------------------------------------
    ax2.plot([profile_left, profile_right], [max_depth, max_depth], color="black",
             lw=1.5 * LWD, solid_capstyle="butt", clip_on=False)

    # ----------------------------------------------------------------
    # LEGEND
    # Placed explicitly just outside the profile's right edge, inside
    # the right-hand gutter that was sized to fit it.
    # ----------------------------------------------------------------
    handles = [Line2D([], [], color=profile_colours[i], lw=3 * LWD) for i in range(n_items)]
    ax2.legend(handles, item_names, loc="upper left", bbox_to_anchor=(1.03, 1.0),
               frameon=False, title=legend_title, fontsize=12 * 0.85,
               title_fontsize=12 * 0.85, handlelength=1.8, borderaxespad=0, borderpad=0)

    # ----------------------------------------------------------------
    # TITLE      mtext(plot_title, side = 3, line = 0.2, font = 2, cex = 1.2)
    # ----------------------------------------------------------------
    fig.text((left_in + plot_width_in / 2) / dev_width_in, (bot_y1 + 0.2 * line_in) / dev_height_in,
             plot_title, ha="center", va="baseline", fontweight="bold", fontsize=12 * 1.2)

    return fig


# ================================================================
# 13. SELECT PLOTTING MODE
# ================================================================
#
# "parameters" = one station + multiple parameters
#
# "transects" = one station number + one parameter
#               + multiple transects
#
# ================================================================

def run_profile(data_raw, excel_name, sheet_name, plot_type, selected_station,
                selected_parameters, selected_station_number, selected_parameter,
                label_gap_in):
    _LOG.clear()

    # ================================================================
    # 2. SELECT EXCEL FILE  (done in the app: file + sheet are chosen in the sidebar)
    # ================================================================
    cat("\nExcel file selected:\n")
    cat(excel_name, "\n")
    cat("\nSheet selected:\n")
    cat(sheet_name, "\n")

    # ================================================================
    # 4. SHOW EXCEL COLUMNS
    # ================================================================
    cat("\nColumns detected in Excel:\n\n")
    cat(list(data_raw.columns), "\n")
    cat("\n")

    try:
        data, station_col, depth_col, parameter_columns = prepare_data(data_raw)
    except ValueError as e:
        st.error(str(e))
        st.stop()

    cat("Station column:", station_col, "\n")
    cat("Depth column:", depth_col, "\n")

    cat("\nParameters available:\n\n")

    for i, p in enumerate(parameter_columns, start=1):
        cat(i, ":", p, "\n")

    # ################################################################
    # MODE 1
    # ONE STATION + MULTIPLE PARAMETERS
    # ################################################################

    if plot_type == "parameters":

        # ==============================================================
        # MAXIMUM 10 PARAMETERS
        # ==============================================================
        if len(selected_parameters) > 10:
            st.error("More than 10 parameters were selected.\n"
                     "Please select a maximum of 10 parameters.")
            st.stop()

        # ==============================================================
        # CHECK PARAMETER NAMES
        # ==============================================================
        missing_parameters = [p for p in selected_parameters if p not in parameter_columns]

        if len(missing_parameters) > 0:
            st.error("The following selected parameters were not found as Excel column names: "
                     + ", ".join(missing_parameters))
            st.stop()

        # ==============================================================
        # EXTRACT SELECTED STATION
        # ==============================================================
        station_data = data[data[station_col] == selected_station]

        if len(station_data) == 0:
            st.error(f"No data found for station: {selected_station}")
            st.stop()

        # ==============================================================
        # CREATE PARAMETER DATA
        # ==============================================================
        parameter_data = {}

        for parameter_name in selected_parameters:

            values = to_numeric(station_data[parameter_name])
            depths = to_numeric(station_data[depth_col])

            valid = values.notna() & depths.notna()

            temp = pd.DataFrame({
                "depth": depths[valid].to_numpy(),
                "value": values[valid].to_numpy(),
            })

            temp = temp.sort_values("depth", kind="stable").reset_index(drop=True)

            if len(temp) > 0:
                parameter_data[parameter_name] = temp

        # ==============================================================
        # REMOVE EMPTY PARAMETERS
        # ==============================================================
        selected_parameters = list(parameter_data.keys())

        if len(selected_parameters) == 0:
            st.error("No valid parameter data were found.")
            st.stop()

        # ==============================================================
        # MAXIMUM DEPTH
        # ==============================================================
        max_depth = max(x["depth"].max() for x in parameter_data.values())

        # ==============================================================
        # OUTPUT FILE
        # ==============================================================
        output_file = os.path.join(excel_folder, "Multi_Parameter_Profile.tiff")

        plot_title = "Water Column Profile — " + selected_station

        # ==============================================================
        # DRAW THE PLOT  (shown in the app, and saved as TIFF below)
        # ==============================================================
        fig = draw_two_panel_profile(
            item_names=selected_parameters,
            item_data=parameter_data,
            max_depth=max_depth,
            plot_title=plot_title,
            legend_title="Parameter",
            label_gap_in=label_gap_in
        )

        # ==============================================================
        # OUTPUT MESSAGE
        # ==============================================================
        final_msg = (
            "\n============================================\n"
            "PROFILE CREATED SUCCESSFULLY\n"
            "============================================\n"
            f"Station: {selected_station} \n"
            f"Parameters: {', '.join(selected_parameters)} \n"
        )

    # ################################################################
    # MODE 2
    # ONE STATION NUMBER + ONE PARAMETER + MULTIPLE TRANSECTS
    # ################################################################

    if plot_type == "transects":

        # ==============================================================
        # CHECK PARAMETER
        # ==============================================================
        if selected_parameter not in parameter_columns:
            st.error(f"Parameter {selected_parameter} was not found as an Excel column.")
            st.stop()

        # ==============================================================
        # FIND MATCHING STATIONS
        # ==============================================================
        station_values = list(pd.unique(data[station_col].dropna()))

        matching_stations = [s for s in station_values
                             if re.search(r"\b" + re.escape(selected_station_number) + r"$", s)]

        if len(matching_stations) == 0:
            st.error(f"No stations found for: {selected_station_number}")
            st.stop()

        # ==============================================================
        # EXTRACT TRANSECT NAMES
        # ==============================================================
        transect_names = [re.sub(r"\s+" + re.escape(selected_station_number) + r"$", "", s,
                                 count=1) for s in matching_stations]

        # ==============================================================
        # SORT TRANSECTS
        # ==============================================================
        def _num(t):
            m = re.fullmatch(r"[+-]?\d+(?:\.\d+)?", re.sub(r"^T", "", t, count=1))
            return float(m.group()) if m else np.nan

        numeric_transect = [_num(t) for t in transect_names]

        transect_order = sorted(
            range(len(transect_names)),
            key=lambda k: (np.isnan(numeric_transect[k]),
                           0 if np.isnan(numeric_transect[k]) else numeric_transect[k],
                           transect_names[k]))

        matching_stations = [matching_stations[k] for k in transect_order]
        transect_names = [transect_names[k] for k in transect_order]

        # ==============================================================
        # MAXIMUM 10 TRANSECTS
        # ==============================================================
        if len(transect_names) > 10:
            st.error("More than 10 transects were found.\nMaximum allowed is 10.")
            st.stop()

        # ==============================================================
        # CREATE TRANSECT DATA
        # ==============================================================
        transect_data = {}

        for station_value, transect_name in zip(matching_stations, transect_names):

            temp = data[data[station_col] == station_value]

            depths = to_numeric(temp[depth_col])
            values = to_numeric(temp[selected_parameter])

            valid = depths.notna() & values.notna()

            profile = pd.DataFrame({
                "depth": depths[valid].to_numpy(),
                "value": values[valid].to_numpy(),
            })

            profile = profile.sort_values("depth", kind="stable").reset_index(drop=True)

            if len(profile) > 0:
                transect_data[transect_name] = profile

        # ==============================================================
        # REMOVE EMPTY TRANSECTS
        # ==============================================================
        transect_names = list(transect_data.keys())

        if len(transect_names) == 0:
            st.error("No valid transect data were found.")
            st.stop()

        # ==============================================================
        # MAXIMUM DEPTH
        # ==============================================================
        max_depth = max(x["depth"].max() for x in transect_data.values())

        # ==============================================================
        # OUTPUT FILE
        # ==============================================================
        output_file = os.path.join(excel_folder, "Multi_Transect_Profile.tiff")

        plot_title = ("Water Column Profile — " + selected_parameter
                      + " - Station " + selected_station_number)

        # ==============================================================
        # DRAW THE PLOT  (shown in the app, and saved as TIFF below)
        # ==============================================================
        fig = draw_two_panel_profile(
            item_names=transect_names,
            item_data=transect_data,
            max_depth=max_depth,
            plot_title=plot_title,
            legend_title="Transect",
            label_gap_in=label_gap_in
        )

        # ==============================================================
        # OUTPUT MESSAGE
        # ==============================================================
        final_msg = (
            "\n============================================\n"
            "PROFILE CREATED SUCCESSFULLY\n"
            "============================================\n"
            f"Station number: {selected_station_number} \n"
            f"Parameter: {selected_parameter} \n"
            f"Transects: {', '.join(transect_names)} \n"
        )

    # ==============================================================
    # SAVE THE SAME PLOT AS TIFF   (width = 1800, height = 2400, res = 200, lzw)
    # ==============================================================
    tiff = io.BytesIO()
    fig.savefig(tiff, format="tiff", dpi=200, facecolor="white",
                pil_kwargs={"compression": "tiff_lzw"})
    png = io.BytesIO()
    fig.savefig(png, format="png", dpi=100, facecolor="white")
    plt.close(fig)

    os.makedirs(excel_folder, exist_ok=True)
    with open(output_file, "wb") as f:
        f.write(tiff.getvalue())

    cat(final_msg)
    cat("\nTIFF saved at:\n")
    cat(output_file, "\n")

    return {"png": png.getvalue(), "tiff": tiff.getvalue(),
            "filename": os.path.basename(output_file), "saved_to": output_file,
            "log": "".join(_LOG)}


# ============================================================
#  STREAMLIT APP
# ============================================================
def main():
    st.set_page_config(page_title="Water Column Profile", page_icon="🌊", layout="wide")
    st.title("MULTI-PARAMETER / MULTI-TRANSECT WATER COLUMN PROFILE")
    st.caption("Station | Depth | Parameter 1 | Parameter 2 | ...   (station names like 'T1 S1')")

    # ================================================================
    # 2. SELECT EXCEL FILE
    # ================================================================
    st.sidebar.header("Excel selection")
    excel_upload = st.sidebar.file_uploader("Select the Excel file", type=["xlsx", "xlsm", "xls"])

    res = st.session_state.get("lineplot_result")

    if excel_upload is None:
        st.info("Upload an Excel file in the sidebar to begin.")
        if res:
            _show_result(res)
        return

    # ================================================================
    # 3. READ EXCEL SHEET   (any sheet can be selected)
    # ================================================================
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

    try:
        data, station_col, depth_col, parameter_columns = prepare_data(data_raw)
    except ValueError as e:
        st.error(str(e))
        return

    # ================================================================
    # 13. SELECT PLOTTING MODE
    # ================================================================
    st.sidebar.header("Plot settings")
    plot_type = st.sidebar.radio(
        "Plot type (plot_type)", ["parameters", "transects"],
        format_func=lambda v: ("parameters  -  one station + multiple parameters"
                               if v == "parameters"
                               else "transects  -  one station number + one parameter + multiple transects"))

    selected_station = selected_parameters = selected_station_number = selected_parameter = None

    if plot_type == "parameters":
        # SELECT STATION
        stations = list(pd.unique(data[station_col].dropna()))
        selected_station = st.sidebar.selectbox("Station (selected_station)", stations,
                                                key=f"stn_{sheet_name}")
        # SELECT PARAMETERS  (default: all available numeric parameters)
        selected_parameters = st.sidebar.multiselect(
            "Parameters (selected_parameters)  -  maximum 10", parameter_columns,
            default=parameter_columns, key=f"pars_{sheet_name}")
    else:
        # SELECT STATION NUMBER
        numbers = (data[station_col].dropna().str.extract(r"(\S+)$")[0].dropna().unique().tolist())
        numbers = sorted(numbers, key=lambda s: (0, int(re.search(r"\d+", s).group()), s)
                         if re.search(r"\d+", s) else (1, 0, s))
        selected_station_number = st.sidebar.selectbox("Station number (selected_station_number)",
                                                       numbers, key=f"num_{sheet_name}")
        # SELECT PARAMETER
        selected_parameter = st.sidebar.selectbox("Parameter (selected_parameter)",
                                                  parameter_columns, key=f"par_{sheet_name}")

    with st.sidebar.expander("Advanced settings"):
        gap = st.number_input("label_gap_in  (increase to push the names further left)",
                              value=0.12, min_value=0.0, max_value=2.0, step=0.02, format="%.2f")

    if st.sidebar.button("Generate profile", type="primary"):
        with st.spinner("Drawing the profile..."):
            st.session_state["lineplot_result"] = run_profile(
                data_raw, excel_name, sheet_name, plot_type, selected_station,
                selected_parameters, selected_station_number, selected_parameter, float(gap))
        res = st.session_state.get("lineplot_result")

    if res:
        _show_result(res)
    else:
        st.info("Choose the sheet and plot settings in the sidebar, then press **Generate profile**.")


def _show_result(res):
    st.image(res["png"])
    st.download_button("Download profile (TIFF)", data=res["tiff"], file_name=res["filename"],
                       mime="image/tiff")
    st.success(f"TIFF saved at: {res['saved_to']}")
    with st.expander("Console output"):
        st.code(res["log"])


if __name__ == "__main__":
    main()
