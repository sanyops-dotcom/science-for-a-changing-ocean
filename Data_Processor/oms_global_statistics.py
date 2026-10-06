"""
OCEAN MONITORING SYSTEM (OMS)
GLOBAL STATISTICS ANALYZER v2.0  -  Python / Streamlit edition

How to run (VS Code terminal):
    pip install -r requirements.txt
    streamlit run soms_global_statistics.py

The app opens in your web browser at http://localhost:8501
"""

from __future__ import annotations

import base64
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

APP_TITLE = "OCEAN MONITORING SYSTEM (OMS)"
APP_SUBTITLE = "GLOBAL STATISTICS ANALYZER v2.0"

# Files whose names contain these words are reports made by OMS itself,
# so they are never read as input data.
EXCLUDED_NAME_PARTS = ("global min max", "global statistics")

RESULT_COLUMNS = [
    "Column",
    "Parameter",
    "Observations",
    "Missing",
    "Global_Min",
    "Global_Max",
    "Global_Mean",
    "Global_SD",
    "Mean_Minus_SD",
    "Mean_Plus_SD",
]


# =============================================================================
# CORE LOGIC  (same method as the R script)
# =============================================================================
class InputError(Exception):
    """A problem the user can fix (bad folder, bad column list, ...)."""


def parse_columns(text: str) -> list[int]:
    """Turn '5:12,15,18' into a sorted list of unique 1-based column numbers.

    Same idea as R's  sort(unique(c(5:12, 15, 18))).
    """
    if not text.strip():
        raise InputError("No parameter columns entered.")

    columns: set[int] = set()
    for token in text.split(","):
        token = token.strip()
        as_range = re.fullmatch(r"(\d+)\s*:\s*(\d+)", token)
        if as_range:
            start, stop = int(as_range.group(1)), int(as_range.group(2))
            step = 1 if start <= stop else -1  # R also allows 12:5
            columns.update(range(start, stop + step, step))
        elif re.fullmatch(r"\d+", token):
            columns.add(int(token))
        else:
            raise InputError(
                f"Cannot read '{token}'. Use numbers and ranges such as 5, 5:12 or 5:12,15,18."
            )

    if min(columns) < 1:
        raise InputError("Column numbers start at 1.")
    return sorted(columns)


def find_excel_files(folder: Path) -> list[Path]:
    """All .xlsx files in the folder, except reports made by this program."""
    files = [
        p
        for p in folder.iterdir()
        if p.is_file()
        and p.suffix.lower() == ".xlsx"
        and not p.name.startswith("~$")  # Excel's temporary lock files
        and not any(part in p.name.lower() for part in EXCLUDED_NAME_PARTS)
    ]
    return sorted(files, key=lambda p: p.name.lower())


def to_numeric(series: pd.Series) -> np.ndarray:
    """Equivalent of R's suppressWarnings(as.numeric(x)): text that is not a number becomes NaN."""
    if pd.api.types.is_bool_dtype(series):
        return series.astype(float).to_numpy()
    if pd.api.types.is_datetime64_any_dtype(series):
        # R turns date-times into seconds since 1970-01-01
        seconds = (series - pd.Timestamp("1970-01-01")) / pd.Timedelta(seconds=1)
        return seconds.to_numpy(dtype=float)
    return pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)


def build_global_dataset(files, columns, log, on_progress=None):
    """PART 2 - collect every valid value of each parameter from ALL files."""
    log("=" * 61)
    log("               BUILDING GLOBAL DATASET")
    log("=" * 61)

    # Each file is read once and reused for every parameter (faster than R's re-reading).
    cache: dict[Path, pd.DataFrame] = {}

    def load(path: Path) -> pd.DataFrame:
        if path not in cache:
            cache[path] = pd.read_excel(path)
        return cache[path]

    # SECTION 6 : verify column numbers against the first file
    n_available = load(files[0]).shape[1]
    if max(columns) > n_available:
        raise InputError(
            f"Column {max(columns)} does not exist. Maximum available column is {n_available}."
        )

    global_data = []
    for i, col in enumerate(columns):
        log("")
        log("-" * 61)
        log(f"Processing Column : {col}")
        log("-" * 61)
        if on_progress:
            on_progress(i / len(columns), f"Reading column {col} from {len(files)} files")

        chunks: list[np.ndarray] = []
        parameter_name = None
        total_missing = 0
        total_valid = 0

        for path in files:
            log(f"Reading : {path.name}")
            data = load(path)

            if col > data.shape[1]:
                log("   Skipped (Column Missing)")
                continue

            # Parameter name is taken once, from the first file that has the column
            if parameter_name is None:
                parameter_name = str(data.columns[col - 1])

            values = to_numeric(data.iloc[:, col - 1])
            is_missing = np.isnan(values)
            valid_values = values[~is_missing]

            total_valid += int(valid_values.size)
            total_missing += int(is_missing.sum())
            chunks.append(valid_values)

            log(f"   Valid : {valid_values.size}  Missing : {int(is_missing.sum())}")

        all_values = np.concatenate(chunks) if chunks else np.array([], dtype=float)
        global_data.append(
            {
                "Column": col,
                "Parameter": parameter_name,
                "Values": all_values,
                "N": total_valid,
                "Missing": total_missing,
            }
        )

        log("-" * 61)
        log(f"Parameter : {parameter_name}")
        log(f"Global Values : {all_values.size}")
        log(f"Missing : {total_missing}")
        log("-" * 61)

    log("")
    log("=" * 61)
    log("PART 2 COMPLETED SUCCESSFULLY")
    log("=" * 61)
    return global_data


def calculate_statistics(global_data, log):
    """PART 3 - min, max, mean, sample SD (n - 1, like R's sd()), mean -/+ SD."""
    log("")
    log("=" * 61)
    log("            CALCULATING GLOBAL STATISTICS")
    log("=" * 61)

    rows = []
    for item in global_data:
        v = item["Values"]
        nan = float("nan")
        g_min = float(v.min()) if v.size else nan
        g_max = float(v.max()) if v.size else nan
        g_mean = float(v.mean()) if v.size else nan
        g_sd = float(v.std(ddof=1)) if v.size > 1 else nan

        log("")
        log("-" * 61)
        log(f"Parameter : {item['Parameter']}")
        log("-" * 61)
        log(f"Observations   : {item['N']}")
        log(f"Missing Values : {item['Missing']}")
        log(f"Minimum        : {g_min:.6f}")
        log(f"Maximum        : {g_max:.6f}")
        log(f"Mean           : {g_mean:.6f}")
        log(f"Std. Deviation : {g_sd:.6f}")
        log(f"Mean - SD      : {g_mean - g_sd:.6f}")
        log(f"Mean + SD      : {g_mean + g_sd:.6f}")

        rows.append(
            {
                "Column": item["Column"],
                "Parameter": item["Parameter"],
                "Observations": item["N"],
                "Missing": item["Missing"],
                "Global_Min": g_min,
                "Global_Max": g_max,
                "Global_Mean": g_mean,
                "Global_SD": g_sd,
                "Mean_Minus_SD": g_mean - g_sd,
                "Mean_Plus_SD": g_mean + g_sd,
            }
        )

    results = pd.DataFrame(rows, columns=RESULT_COLUMNS)

    log("")
    log("=" * 61)
    log("          GLOBAL STATISTICS SUMMARY")
    log("=" * 61)
    log("")
    log(results.to_string(index=False))
    log("")
    log("=" * 61)
    log("PART 3 COMPLETED SUCCESSFULLY")
    log("=" * 61)
    return results


def export_results(results: pd.DataFrame, folder: Path, label: str | None = None) -> Path:
    """SECTION 8 - write '<name> - Global Statistics.xlsx' next to the data.

    <name> is the folder name when all files are used, otherwise `label`.
    """
    from openpyxl.styles import Font

    output = folder / f"{label or folder.name or 'Data'} - Global Statistics.xlsx"
    try:
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            results.to_excel(writer, index=False, sheet_name="Sheet 1")
            sheet = writer.sheets["Sheet 1"]
            sheet.freeze_panes = "A2"
            for cell in sheet[1]:
                cell.font = Font(bold=True)
            for idx, name in enumerate(results.columns, start=1):
                widest = max(len(str(name)), *(len(str(x)) for x in results[name]))
                sheet.column_dimensions[sheet.cell(row=1, column=idx).column_letter].width = min(
                    widest + 3, 40
                )
    except PermissionError as exc:
        raise InputError(
            f"Cannot save '{output.name}'. If it is open in Excel, close it and run again."
        ) from exc
    return output


def make_histogram(values: np.ndarray, bins: int = 30) -> pd.DataFrame | None:
    if values.size == 0:
        return None
    counts, edges = np.histogram(values, bins=bins)
    return pd.DataFrame({"start": edges[:-1], "end": edges[1:], "count": counts})


def run_analysis(files, columns, folder, on_progress=None, report_label=None):
    lines: list[str] = []
    log = lines.append

    global_data = build_global_dataset(files, columns, log, on_progress)
    results = calculate_statistics(global_data, log)
    if on_progress:
        on_progress(1.0, "Saving Excel report")
    output = export_results(results, folder, report_label)

    log("")
    log("=" * 61)
    log("          ANALYSIS COMPLETED SUCCESSFULLY")
    log("=" * 61)
    log("")
    log("Output File")
    log("-" * 45)
    log(str(output))
    log("")
    log(f"Total Excel Files Processed : {len(files)}")
    log(f"Total Parameters Processed  : {len(columns)}")

    return {
        "results": results,
        "output": output,
        "output_bytes": output.read_bytes(),
        "log": "\n".join(lines),
        "n_files": len(files),
        "n_params": len(columns),
        "histograms": {item["Column"]: make_histogram(item["Values"]) for item in global_data},
    }


# =============================================================================
# FILE PICKER  (the app runs on your own PC, so it can open a normal dialog)
# =============================================================================
def browse_for_excel_file() -> tuple[str, str | None]:
    """Open the operating-system file dialog. Returns (path, error_message)."""
    script = (
        "import tkinter as tk\n"
        "from tkinter import filedialog\n"
        "root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True)\n"
        "print(filedialog.askopenfilename(\n"
        "    title='Select ANY Excel file from your working folder',\n"
        "    filetypes=[('Excel files', '*.xlsx'), ('All files', '*.*')]))\n"
    )
    try:
        done = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            timeout=600,
        )
    except Exception as exc:  # noqa: BLE001
        return "", f"The file dialog could not open ({exc}). Paste the folder path instead."
    if done.returncode != 0:
        return "", "The file dialog is not available on this computer. Paste the folder path instead."
    return done.stdout.strip(), None


def on_browse_clicked():
    path, error = browse_for_excel_file()
    st.session_state["browse_error"] = error
    if path:
        st.session_state["folder_path"] = str(Path(path).parent)


@st.cache_data(show_spinner=False)
def read_headers(path: str, modified: float) -> list[str]:
    return [str(c) for c in pd.read_excel(path, nrows=0).columns]


# =============================================================================
# LOOK AND FEEL
# =============================================================================
def _contour_background() -> str:
    """Depth-contour lines (like a bathymetric chart) drawn as the header background."""
    rings = []
    for k, rx in enumerate(range(40, 460, 42)):
        rings.append(
            f'<ellipse cx="980" cy="150" rx="{rx * 1.35:.0f}" ry="{rx * 0.62:.0f}" '
            f'transform="rotate(-14 980 150)" opacity="{0.20 - k * 0.011:.3f}"/>'
        )
    for k, rx in enumerate(range(30, 240, 35)):
        rings.append(
            f'<ellipse cx="170" cy="270" rx="{rx * 1.2:.0f}" ry="{rx * 0.5:.0f}" '
            f'transform="rotate(9 170 270)" opacity="{0.16 - k * 0.02:.3f}"/>'
        )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="320" viewBox="0 0 1400 320" '
        'fill="none" stroke="#9fd4e2" stroke-width="1.4">' + "".join(rings) + "</svg>"
    )
    return base64.b64encode(svg.encode()).decode()


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

:root {
  --abyss: #0a2540;
  --shelf: #1f6f8b;
  --shallows: #dcebef;
  --chart: #f2f6f7;
  --buoy: #e4572e;
  --ink: #12263a;
}

.stApp { background: var(--chart); color: var(--ink); }
.stApp, .stApp p, .stApp label, .stApp li, .stApp input, .stApp button {
  font-family: 'IBM Plex Sans', system-ui, -apple-system, 'Segoe UI', sans-serif;
}
.stApp .block-container { max-width: 1120px; padding-top: 2.5rem; padding-bottom: 4rem; }

/* header */
.stApp .soms-hero {
  background-color: var(--abyss);
  background-image: url("data:image/svg+xml;base64,__CONTOURS__");
  background-size: cover;
  background-position: center;
  border-radius: 6px;
  padding: 2.6rem 2.4rem 2.4rem;
  margin-bottom: 1.6rem;
}
.stApp .soms-hero h1 {
  font-family: 'Bricolage Grotesque', 'IBM Plex Sans', system-ui, sans-serif;
  font-weight: 700; font-size: 2.35rem; line-height: 1.1; letter-spacing: -0.01em;
  color: #ffffff; margin: 0; padding: 0;
}
.stApp .soms-hero .soms-sub {
  font-family: 'Bricolage Grotesque', 'IBM Plex Sans', system-ui, sans-serif;
  font-weight: 500; font-size: 1.15rem; color: #9fd4e2; margin: 0.45rem 0 0; }
.stApp .soms-hero .soms-desc { color: #d3e6ec; max-width: 62ch; margin: 1.1rem 0 0; line-height: 1.55; }

/* section headings */
.stApp .soms-section h2 {
  font-family: 'Bricolage Grotesque', 'IBM Plex Sans', system-ui, sans-serif;
  font-weight: 700; font-size: 1.35rem; color: var(--abyss); margin: 0; padding: 0;
}
.stApp .soms-section p { color: #4a6072; margin: 0.25rem 0 0.9rem; max-width: 75ch; }

/* boxes */
.stApp [data-testid="stVerticalBlockBorderWrapper"] { background: #ffffff; border-color: #cfdde2; border-radius: 6px; }

/* main action */
.stApp button[kind="primary"], .stApp [data-testid="stBaseButton-primary"] {
  background: var(--buoy); border-color: var(--buoy); color: #fff; font-weight: 600;
}
.stApp button[kind="primary"]:hover, .stApp [data-testid="stBaseButton-primary"]:hover {
  background: #c9431d; border-color: #c9431d; color: #fff;
}
.stApp button:focus-visible { outline: 3px solid var(--shelf); outline-offset: 2px; }

/* numbers */
.stApp [data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; color: var(--abyss); }
.stApp [data-testid="stMetricLabel"] { color: #4a6072; }

.stApp .soms-footer { color: #4a6072; text-align: center; margin-top: 2.5rem; font-size: 0.9rem; }
</style>
""".replace("__CONTOURS__", _contour_background())


def section(title: str, hint: str = ""):
    hint_html = f"<p>{hint}</p>" if hint else ""
    st.markdown(f'<div class="soms-section"><h2>{title}</h2>{hint_html}</div>', unsafe_allow_html=True)


def histogram_chart(hist: pd.DataFrame, row: pd.Series):
    import altair as alt

    bars = (
        alt.Chart(hist)
        .mark_bar(color="#1f6f8b")
        .encode(
            x=alt.X("start:Q", title=str(row["Parameter"])),
            x2="end:Q",
            y=alt.Y("count:Q", title="Observations"),
            tooltip=[
                alt.Tooltip("start:Q", title="From", format=".4g"),
                alt.Tooltip("end:Q", title="To", format=".4g"),
                alt.Tooltip("count:Q", title="Observations"),
            ],
        )
    )
    lines = pd.DataFrame(
        {
            "x": [row["Mean_Minus_SD"], row["Global_Mean"], row["Mean_Plus_SD"]],
            "label": ["Mean - SD", "Mean", "Mean + SD"],
        }
    ).dropna()
    rules = (
        alt.Chart(lines)
        .mark_rule(strokeWidth=2)
        .encode(
            x="x:Q",
            color=alt.Color(
                "label:N",
                title=None,
                scale=alt.Scale(
                    domain=["Mean - SD", "Mean", "Mean + SD"],
                    range=["#0a2540", "#e4572e", "#0a2540"],
                ),
            ),
            strokeDash=alt.StrokeDash(
                "label:N",
                legend=None,
                scale=alt.Scale(
                    domain=["Mean - SD", "Mean", "Mean + SD"], range=[[5, 4], [1, 0], [5, 4]]
                ),
            ),
            tooltip=[alt.Tooltip("label:N", title=""), alt.Tooltip("x:Q", title="Value", format=".6f")],
        )
    )
    return (bars + rules).properties(height=260)


# =============================================================================
# THE APP
# =============================================================================
def main():
    st.set_page_config(page_title="OMS - Global Statistics Analyzer", page_icon="🌊", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    st.session_state.setdefault("folder_path", "")

    st.markdown(
        f"""
        <div class="soms-hero">
          <h1>{APP_TITLE}</h1>
          <p class="soms-sub">{APP_SUBTITLE}</p>
          <p class="soms-desc">Calculates global statistics for one or more parameter columns
          from all Excel files in a folder, and saves the result as a new Excel report.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------ folder
    files: list[Path] = []  # every Excel file found in the folder
    analysis_files: list[Path] = []  # the files that will actually be analysed
    report_label: str | None = None
    folder: Path | None = None

    with st.container(border=True):
        section(
            "1. Choose the working folder",
            "Pick any Excel file from the folder, or paste the folder path. "
            "You can then analyse every .xlsx file in the folder, or only the files you select.",
        )
        col_path, col_browse = st.columns([5, 2], vertical_alignment="bottom")
        col_path.text_input("Folder path", key="folder_path", placeholder=r"C:\Data\Survey_2026")
        col_browse.button("Browse for an Excel file", on_click=on_browse_clicked)

        if st.session_state.get("browse_error"):
            st.warning(st.session_state["browse_error"])

        folder_text = st.session_state["folder_path"].strip().strip('"').strip("'")
        if not folder_text:
            st.info("Select a folder to begin.")
        else:
            candidate = Path(folder_text).expanduser()
            if candidate.is_file():
                candidate = candidate.parent
            if not candidate.is_dir():
                st.error("That folder does not exist. Check the path or use Browse.")
            else:
                folder = candidate
                files = find_excel_files(folder)
                if not files:
                    st.error("No Excel data files found. Choose a folder that contains .xlsx files.")
                else:
                    st.success(f"Excel files found: {len(files)}")
                    with st.expander("Show file names"):
                        st.dataframe(pd.DataFrame({"File": [f.name for f in files]}), hide_index=True)

                    mode = st.radio(
                        "Files to analyse",
                        ["All Excel files in the folder", "Only the files I select"],
                        key="file_mode",
                        horizontal=True,
                    )
                    if mode == "All Excel files in the folder":
                        analysis_files = files
                    else:
                        names = [f.name for f in files]
                        # drop selections that belong to a previously chosen folder
                        st.session_state["selected_names"] = [
                            n for n in st.session_state.get("selected_names", []) if n in names
                        ]
                        chosen = st.multiselect("Select file(s)", names, key="selected_names")
                        analysis_files = [f for f in files if f.name in chosen]
                        if not analysis_files:
                            st.info("Select at least one file.")
                        elif len(analysis_files) == 1:
                            report_label = analysis_files[0].stem
                        else:
                            report_label = f"{folder.name or 'Data'} (selected files)"

    if not analysis_files or folder is None:
        return

    # ---------------------------------------------------------------- columns
    columns: list[int] = []
    with st.container(border=True):
        section(
            "2. Enter the parameter columns",
            "Column numbers start at 1. Examples: 5 | 5:12 | 5,7,9,12 | 5:12,15,18",
        )
        try:
            headers = read_headers(str(analysis_files[0]), analysis_files[0].stat().st_mtime)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not read '{analysis_files[0].name}': {exc}")
            return

        with st.expander(f"Columns in the first selected file ({len(headers)})"):
            st.dataframe(
                pd.DataFrame({"Column": range(1, len(headers) + 1), "Parameter": headers}),
                hide_index=True,
            )

        text = st.text_input("Parameter columns", key="parameter_input", placeholder="5:12,15,18")
        if text.strip():
            try:
                columns = parse_columns(text)
                if max(columns) > len(headers):
                    st.error(
                        f"Column {max(columns)} does not exist. "
                        f"Maximum available column is {len(headers)}."
                    )
                    columns = []
                else:
                    chosen = ", ".join(f"{c} ({headers[c - 1]})" for c in columns)
                    st.caption(f"Selected: {chosen}")
            except InputError as exc:
                st.error(str(exc))

        run_clicked = st.button("Calculate global statistics", type="primary", disabled=not columns)

    # ------------------------------------------------------------------- run
    if run_clicked:
        with st.status("Building global dataset", expanded=True) as status:
            bar = st.progress(0.0)

            def on_progress(fraction: float, label: str):
                bar.progress(min(fraction, 1.0))
                status.update(label=label)

            try:
                st.session_state["result"] = run_analysis(analysis_files, columns, folder, on_progress, report_label)
                status.update(label="Analysis complete", state="complete", expanded=False)
                st.toast("Global Statistics Analysis Completed Successfully!")
            except InputError as exc:
                status.update(label="Stopped", state="error")
                st.session_state.pop("result", None)
                st.error(str(exc))
            except Exception as exc:  # noqa: BLE001
                status.update(label="Stopped", state="error")
                st.session_state.pop("result", None)
                st.error(f"Analysis stopped: {exc}")

    # --------------------------------------------------------------- results
    result = st.session_state.get("result")
    if not result:
        return

    results: pd.DataFrame = result["results"]
    with st.container(border=True):
        section("3. Results")
        st.success(
            "Global Statistics Analysis Completed Successfully. The Excel report has been saved "
            "in the working folder."
        )
        m1, m2, m3 = st.columns(3)
        m1.metric("Excel files processed", result["n_files"])
        m2.metric("Parameters processed", result["n_params"])
        m3.metric("Report file", result["output"].name)
        st.code(str(result["output"]), language=None)

        number_format = st.column_config.NumberColumn(format="%.6f")
        st.dataframe(
            results,
            hide_index=True,
            column_config={
                "Column": st.column_config.NumberColumn(format="%d"),
                "Observations": st.column_config.NumberColumn(format="%d"),
                "Missing": st.column_config.NumberColumn(format="%d"),
                "Global_Min": number_format,
                "Global_Max": number_format,
                "Global_Mean": number_format,
                "Global_SD": number_format,
                "Mean_Minus_SD": number_format,
                "Mean_Plus_SD": number_format,
            },
        )
        st.download_button(
            "Download Excel report",
            data=result["output_bytes"],
            file_name=result["output"].name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with st.container(border=True):
        section("Each parameter", "Distribution of all values, with the mean and mean plus or minus one SD.")
        tabs = st.tabs([f"{int(r.Column)}: {r.Parameter}" for r in results.itertuples()])
        for tab, (_, row) in zip(tabs, results.iterrows()):
            with tab:
                a, b, c, d = st.columns(4)
                a.metric("Observations", f"{int(row['Observations']):,}")
                b.metric("Missing", f"{int(row['Missing']):,}")
                c.metric("Minimum", f"{row['Global_Min']:.6f}")
                d.metric("Maximum", f"{row['Global_Max']:.6f}")
                e, f, g, h = st.columns(4)
                e.metric("Mean", f"{row['Global_Mean']:.6f}")
                f.metric("Std. deviation", f"{row['Global_SD']:.6f}")
                g.metric("Mean - SD", f"{row['Mean_Minus_SD']:.6f}")
                h.metric("Mean + SD", f"{row['Mean_Plus_SD']:.6f}")

                hist = result["histograms"].get(int(row["Column"]))
                if hist is not None:
                    st.altair_chart(histogram_chart(hist, row))

    with st.expander("Processing log"):
        st.code(result["log"], language=None)

    st.markdown(
        f'<div class="soms-footer">Thank you for using {APP_TITLE}<br>{APP_SUBTITLE}</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
