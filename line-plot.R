# ================================================================
# MULTI-PARAMETER / MULTI-TRANSECT WATER COLUMN PROFILE
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
# - The plot is shown in R's own plotting window (so you can check
#   it before/without opening the file).
# - A TIFF file is also saved in the same folder as the selected
#   Excel file.
#
# ================================================================


# ================================================================
# 1. REQUIRED PACKAGE
# ================================================================

if (!requireNamespace("readxl", quietly = TRUE)) {
  install.packages("readxl")
}

library(readxl)


# ================================================================
# 2. SELECT EXCEL FILE
# ================================================================

cat("\nSelect the Excel file:\n")

excel_file <- file.choose()

data <- read_excel(excel_file)


# ================================================================
# 3. FIND EXCEL FOLDER
# ================================================================

excel_folder <- dirname(
  normalizePath(
    excel_file,
    winslash = "/",
    mustWork = TRUE
  )
)

cat(
  "\nExcel folder:\n",
  excel_folder,
  "\n"
)


# ================================================================
# 4. SHOW EXCEL COLUMNS
# ================================================================

cat("\nColumns detected in Excel:\n\n")
print(names(data))
cat("\n")


# ================================================================
# 5. FUNCTION TO FIND A COLUMN
# ================================================================

find_column <- function(data, possible_names) {

  actual_names <- names(data)

  match_index <- match(
    tolower(possible_names),
    tolower(actual_names)
  )

  match_index <- match_index[!is.na(match_index)]

  if (length(match_index) == 0) {
    return(NA_character_)
  }

  actual_names[match_index[1]]
}


# ================================================================
# 6. FIND STATION COLUMN
# ================================================================

station_col <- find_column(
  data,
  c(
    "Station",
    "Station_ID",
    "Station ID",
    "Station Name",
    "Station_Name"
  )
)


# ================================================================
# 7. FIND DEPTH COLUMN
# ================================================================

depth_col <- find_column(
  data,
  c(
    "Depth",
    "Depth_m",
    "Depth (m)",
    "Depth_meters",
    "Depth (meters)"
  )
)


# ================================================================
# 8. CHECK REQUIRED COLUMNS
# ================================================================

if (is.na(station_col)) {
  stop("ERROR: Station column was not found.")
}

if (is.na(depth_col)) {
  stop("ERROR: Depth column was not found.")
}

cat("Station column:", station_col, "\n")
cat("Depth column:", depth_col, "\n")


# ================================================================
# 9. CLEAN STATION AND DEPTH
# ================================================================

data[[station_col]] <- trimws(as.character(data[[station_col]]))
data[[depth_col]] <- suppressWarnings(as.numeric(data[[depth_col]]))


# ================================================================
# 10. IDENTIFY PARAMETER COLUMNS
# ================================================================

excluded_columns <- c(station_col, depth_col)

possible_parameters <- names(data)[!(names(data) %in% excluded_columns)]

parameter_columns <- possible_parameters[
  sapply(
    data[possible_parameters],
    function(x) {
      values <- suppressWarnings(as.numeric(x))
      sum(!is.na(values)) > 0
    }
  )
]

if (length(parameter_columns) == 0) {
  stop("ERROR: No numeric parameter columns were found.")
}

cat("\nParameters available:\n\n")

for (i in seq_along(parameter_columns)) {
  cat(i, ":", parameter_columns[i], "\n")
}


# ================================================================
# 11. COLOUR ORDER
# ================================================================

profile_colours <- c(
  "red",
  "green",
  "blue",
  "orange",
  "pink",
  "brown",
  "violet",
  "skyblue",
  "yellow",
  "grey"
)


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
# ("profile_left" to "profile_right"), and — critically — both
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

label_gap_in <- 0.12


draw_two_panel_profile <- function(
    item_names,
    item_data,
    max_depth,
    plot_title,
    legend_title,
    label_gap_in = 0.12
) {

  n_items <- length(item_names)
  dev_width_in <- par("din")[1]

  # --------------------------------------------------------------
  # DYNAMIC LEFT GUTTER
  # Sized to the widest parameter/transect name so nothing is ever
  # cropped, then shifted further left by `label_gap_in`.
  # --------------------------------------------------------------
  old_cex <- par("cex"); old_font <- par("font")
  par(cex = 0.88, font = 2)
  max_label_in <- max(strwidth(item_names, units = "inches"))
  par(cex = old_cex, font = old_font)

  edge_pad_in <- 0.08
  left_gutter_in <- max_label_in + label_gap_in + edge_pad_in
  panel_left_frac <- min(max(left_gutter_in / dev_width_in, 0.15), 0.55)

  # --------------------------------------------------------------
  # DYNAMIC RIGHT GUTTER
  # Sized to fit the legend text so it is never cut off.
  # --------------------------------------------------------------
  old_cex <- par("cex")
  par(cex = 0.85)
  max_legend_in <- max(strwidth(item_names, units = "inches"))
  par(cex = old_cex)

  legend_swatch_in <- 0.45
  right_gutter_in <- legend_swatch_in + max_legend_in * 1.12 + edge_pad_in + 0.15
  panel_right_frac <- max(min(1 - right_gutter_in / dev_width_in, 0.85), 0.55)

  plot_width_in <- dev_width_in * (panel_right_frac - panel_left_frac)
  data_units_per_inch <- 1 / plot_width_in
  label_gap_data <- label_gap_in * data_units_per_inch

  # --------------------------------------------------------------
  # TWO-PANEL LAYOUT
  # TOP    = stacked X-axes
  # BOTTOM = coloured profile
  # --------------------------------------------------------------
  layout(
    matrix(c(1, 2), nrow = 2, byrow = TRUE),
    heights = c(0.34, 0.66)
  )

  profile_left  <- 0
  profile_right <- 1
  profile_width <- profile_right - profile_left

  # ================================================================
  # TOP PANEL - STACKED AXES
  # ================================================================

  par(mar = c(1, 1, 2, 1))
  plot.new()
  plt <- par("plt")
  par(plt = c(panel_left_frac, panel_right_frac, plt[3], plt[4]))
  par(new = TRUE)

  plot(
    NA, NA,
    type = "n",
    xlim = c(0, 1),
    ylim = c(0, n_items + 1),
    axes = FALSE, xlab = "", ylab = "",
    xaxs = "i", yaxs = "i"
  )

  for (i in seq_along(item_names)) {

    item_name <- item_names[i]
    current_data <- item_data[[item_name]]
    current_colour <- profile_colours[i]

    current_min <- min(current_data$value, na.rm = TRUE)
    current_max <- max(current_data$value, na.rm = TRUE)

    # ------------------------------------------------------------
    # HANDLE CONSTANT VALUES
    # ------------------------------------------------------------
    if (current_min == current_max) {
      padding <- ifelse(current_min == 0, 1, abs(current_min) * 0.05)
      current_min <- current_min - padding
      current_max <- current_max + padding
    }

    y_position <- n_items - i + 1

    # ------------------------------------------------------------
    # MAIN COLOURED AXIS
    # Runs EXACTLY from profile_left to profile_right - identical
    # width for every stacked axis, and identical to the profile
    # panel's left/right edges below.
    # ------------------------------------------------------------
    segments(
      x0 = profile_left, y0 = y_position,
      x1 = profile_right, y1 = y_position,
      col = current_colour, lwd = 2
    )

    # ------------------------------------------------------------
    # TICKS
    # ------------------------------------------------------------
    ticks <- pretty(c(current_min, current_max))
    ticks <- ticks[ticks >= current_min & ticks <= current_max]

    if (length(ticks) < 2) {
      ticks <- seq(current_min, current_max, length.out = 5)
    }

    tick_x <- profile_left +
      ((ticks - current_min) / (current_max - current_min)) * profile_width

    segments(
      x0 = tick_x, y0 = y_position,
      x1 = tick_x, y1 = y_position - 0.10,
      col = current_colour, lwd = 1.5
    )

    text(
      x = tick_x, y = y_position - 0.27,
      labels = format(ticks, trim = TRUE, scientific = FALSE),
      col = current_colour, cex = 0.8, xpd = NA
    )

    # ------------------------------------------------------------
    # PARAMETER / TRANSECT NAME
    # Placed in the left-hand gutter, `label_gap_in` inches to the
    # left of the axis start. The gutter is always wide enough for
    # the longest name in the set, so it is never cropped.
    # ------------------------------------------------------------
    text(
      x = profile_left - label_gap_data,
      y = y_position,
      labels = item_name,
      col = current_colour,
      font = 2,
      pos = 2,
      cex = 0.88,
      xpd = NA
    )
  }

  # ================================================================
  # BOTTOM PANEL - PROFILE
  # ================================================================

  par(mar = c(5, 1, 2, 1))
  plot.new()
  plt <- par("plt")
  par(plt = c(panel_left_frac, panel_right_frac, plt[3], plt[4]))
  par(new = TRUE)

  plot(
    NA, NA,
    type = "n",
    xlim = c(0, 1),
    ylim = c(max_depth, 0),
    axes = FALSE, xlab = "", ylab = "",
    xaxs = "i", yaxs = "i"
  )

  # ----------------------------------------------------------------
  # DEPTH TICKS / AXIS
  # Drawn at x = profile_left = 0, exactly where every stacked
  # X-axis and the bottom horizontal line also start.
  # ----------------------------------------------------------------
  depth_ticks <- pretty(c(0, max_depth))
  depth_ticks <- depth_ticks[depth_ticks >= 0 & depth_ticks <= max_depth]

  axis(
    side = 2, at = depth_ticks,
    labels = paste0(depth_ticks, " m"),
    las = 1, col = "black", col.axis = "black", lwd = 1.5
  )

  abline(h = depth_ticks, col = "grey85", lty = 3)

  mtext("Depth (m)", side = 2, line = 3.3, font = 2)

  # ----------------------------------------------------------------
  # COLOURED PROFILES
  # Normalised onto the SAME profile_left/profile_right span as the
  # stacked axes above, so the plotted line for each parameter runs
  # exactly between its own axis minimum and maximum.
  # ----------------------------------------------------------------
  for (i in seq_along(item_names)) {

    item_name <- item_names[i]
    current_data <- item_data[[item_name]]
    current_colour <- profile_colours[i]

    current_min <- min(current_data$value, na.rm = TRUE)
    current_max <- max(current_data$value, na.rm = TRUE)

    if (current_min == current_max) {
      padding <- ifelse(current_min == 0, 1, abs(current_min) * 0.05)
      current_min <- current_min - padding
      current_max <- current_max + padding
    }

    normalized_x <- (current_data$value - current_min) / (current_max - current_min)
    profile_x <- profile_left + normalized_x * profile_width

    lines(profile_x, current_data$depth, col = current_colour, lwd = 3)
  }

  # ----------------------------------------------------------------
  # BOTTOM HORIZONTAL LINE
  # Left end  = exactly where the depth axis is (profile_left).
  # Right end = exactly where every stacked X-axis ends
  #             (profile_right).
  # ----------------------------------------------------------------
  segments(
    x0 = profile_left, y0 = max_depth,
    x1 = profile_right, y1 = max_depth,
    col = "black", lwd = 1.5
  )

  # ----------------------------------------------------------------
  # LEGEND
  # Placed explicitly just outside the profile's right edge, inside
  # the right-hand gutter that was sized to fit it.
  # ----------------------------------------------------------------
  legend(
    x = 1.03, y = 0, yjust = 1,
    legend = item_names,
    col = profile_colours[seq_along(item_names)],
    lwd = 3, bty = "n", title = legend_title,
    xpd = NA, cex = 0.85
  )

  # ----------------------------------------------------------------
  # TITLE
  # ----------------------------------------------------------------
  mtext(plot_title, side = 3, line = 0.2, font = 2, cex = 1.2)
}


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

plot_type <- "parameters"


# ################################################################
# ################################################################
# MODE 1
# ONE STATION + MULTIPLE PARAMETERS
# ################################################################
# ################################################################

if (plot_type == "parameters") {

  # ==============================================================
  # SELECT STATION
  # ==============================================================

  selected_station <- "T1 S1"

  # ==============================================================
  # SELECT PARAMETERS
  # ==============================================================
  #
  # CURRENT SETTING:
  # All available numeric parameters are selected.
  #
  # To manually select parameters, replace the next line with:
  #
  # selected_parameters <- c(
  #   "DO",
  #   "Temperature",
  #   "Salinity",
  #   "pH"
  # )
  #
  # The names must exactly match the Excel column names.
  #
  # ==============================================================

  selected_parameters <- parameter_columns

  # ==============================================================
  # MAXIMUM 10 PARAMETERS
  # ==============================================================

  if (length(selected_parameters) > 10) {
    stop(
      paste(
        "More than 10 parameters were selected.",
        "\nPlease select a maximum of 10 parameters."
      )
    )
  }

  # ==============================================================
  # CHECK PARAMETER NAMES
  # ==============================================================

  missing_parameters <- selected_parameters[
    !(selected_parameters %in% parameter_columns)
  ]

  if (length(missing_parameters) > 0) {
    stop(
      paste(
        "The following selected parameters were not found",
        "as Excel column names:",
        paste(missing_parameters, collapse = ", ")
      )
    )
  }

  # ==============================================================
  # EXTRACT SELECTED STATION
  # ==============================================================

  station_data <- data[data[[station_col]] == selected_station, , drop = FALSE]

  if (nrow(station_data) == 0) {
    stop(paste("No data found for station:", selected_station))
  }

  # ==============================================================
  # CREATE PARAMETER DATA
  # ==============================================================

  parameter_data <- list()

  for (parameter_name in selected_parameters) {

    values <- suppressWarnings(as.numeric(station_data[[parameter_name]]))
    depths <- suppressWarnings(as.numeric(station_data[[depth_col]]))

    valid <- !is.na(values) & !is.na(depths)

    temp <- data.frame(
      depth = depths[valid],
      value = values[valid]
    )

    temp <- temp[order(temp$depth), , drop = FALSE]

    if (nrow(temp) > 0) {
      parameter_data[[parameter_name]] <- temp
    }
  }

  # ==============================================================
  # REMOVE EMPTY PARAMETERS
  # ==============================================================

  parameter_data <- parameter_data[sapply(parameter_data, nrow) > 0]
  selected_parameters <- names(parameter_data)

  if (length(selected_parameters) == 0) {
    stop("No valid parameter data were found.")
  }

  # ==============================================================
  # MAXIMUM DEPTH
  # ==============================================================

  max_depth <- max(
    unlist(lapply(parameter_data, function(x) x$depth)),
    na.rm = TRUE
  )

  # ==============================================================
  # OUTPUT FILE
  # ==============================================================

  output_file <- file.path(excel_folder, "Multi_Parameter_Profile.tiff")

  plot_title <- paste("Water Column Profile —", selected_station)

  # ==============================================================
  # SHOW IN R's PLOTTING WINDOW FIRST
  # ==============================================================

  draw_two_panel_profile(
    item_names    = selected_parameters,
    item_data     = parameter_data,
    max_depth     = max_depth,
    plot_title    = plot_title,
    legend_title  = "Parameter",
    label_gap_in  = label_gap_in
  )

  # ==============================================================
  # SAVE THE SAME PLOT AS TIFF
  # ==============================================================

  tiff(
    filename = output_file,
    width = 1800,
    height = 2400,
    res = 200,
    compression = "lzw"
  )

  draw_two_panel_profile(
    item_names    = selected_parameters,
    item_data     = parameter_data,
    max_depth     = max_depth,
    plot_title    = plot_title,
    legend_title  = "Parameter",
    label_gap_in  = label_gap_in
  )

  dev.off()

  # ==============================================================
  # OUTPUT MESSAGE
  # ==============================================================

  cat("\n============================================\n")
  cat("PROFILE CREATED SUCCESSFULLY\n")
  cat("============================================\n")
  cat("Station:", selected_station, "\n")
  cat("Parameters:", paste(selected_parameters, collapse = ", "), "\n")
  cat("\nTIFF saved at:\n")
  cat(output_file, "\n")
}


# ################################################################
# ################################################################
# MODE 2
# ONE STATION NUMBER + ONE PARAMETER + MULTIPLE TRANSECTS
# ################################################################
# ################################################################

if (plot_type == "transects") {

  # ==============================================================
  # SELECT STATION NUMBER
  # ==============================================================

  selected_station_number <- "S1"

  # ==============================================================
  # SELECT PARAMETER
  # ==============================================================

  selected_parameter <- parameter_columns[1]

  # ==============================================================
  # CHECK PARAMETER
  # ==============================================================

  if (!(selected_parameter %in% parameter_columns)) {
    stop(
      paste(
        "Parameter",
        selected_parameter,
        "was not found as an Excel column."
      )
    )
  }

  # ==============================================================
  # FIND MATCHING STATIONS
  # ==============================================================

  station_values <- unique(data[[station_col]])
  station_values <- station_values[!is.na(station_values)]

  matching_stations <- station_values[
    grepl(paste0("\\b", selected_station_number, "$"), station_values)
  ]

  if (length(matching_stations) == 0) {
    stop(paste("No stations found for:", selected_station_number))
  }

  # ==============================================================
  # EXTRACT TRANSECT NAMES
  # ==============================================================

  transect_names <- sub(
    paste0("\\s+", selected_station_number, "$"),
    "",
    matching_stations
  )

  # ==============================================================
  # SORT TRANSECTS
  # ==============================================================

  numeric_transect <- suppressWarnings(
    as.numeric(sub("^T", "", transect_names))
  )

  transect_order <- order(is.na(numeric_transect), numeric_transect, transect_names)

  matching_stations <- matching_stations[transect_order]
  transect_names <- transect_names[transect_order]

  # ==============================================================
  # MAXIMUM 10 TRANSECTS
  # ==============================================================

  if (length(transect_names) > 10) {
    stop(
      paste(
        "More than 10 transects were found.",
        "\nMaximum allowed is 10."
      )
    )
  }

  # ==============================================================
  # CREATE TRANSECT DATA
  # ==============================================================

  transect_data <- list()

  for (i in seq_along(matching_stations)) {

    station_value <- matching_stations[i]
    transect_name <- transect_names[i]

    temp <- data[data[[station_col]] == station_value, , drop = FALSE]

    depths <- suppressWarnings(as.numeric(temp[[depth_col]]))
    values <- suppressWarnings(as.numeric(temp[[selected_parameter]]))

    valid <- !is.na(depths) & !is.na(values)

    profile <- data.frame(
      depth = depths[valid],
      value = values[valid]
    )

    profile <- profile[order(profile$depth), , drop = FALSE]

    if (nrow(profile) > 0) {
      transect_data[[transect_name]] <- profile
    }
  }

  # ==============================================================
  # REMOVE EMPTY TRANSECTS
  # ==============================================================

  transect_data <- transect_data[sapply(transect_data, nrow) > 0]
  transect_names <- names(transect_data)

  if (length(transect_names) == 0) {
    stop("No valid transect data were found.")
  }

  # ==============================================================
  # MAXIMUM DEPTH
  # ==============================================================

  max_depth <- max(
    unlist(lapply(transect_data, function(x) x$depth)),
    na.rm = TRUE
  )

  # ==============================================================
  # OUTPUT FILE
  # ==============================================================

  output_file <- file.path(excel_folder, "Multi_Transect_Profile.tiff")

  plot_title <- paste(
    "Water Column Profile —",
    selected_parameter,
    "- Station",
    selected_station_number
  )

  # ==============================================================
  # SHOW IN R's PLOTTING WINDOW FIRST
  # ==============================================================

  draw_two_panel_profile(
    item_names    = transect_names,
    item_data     = transect_data,
    max_depth     = max_depth,
    plot_title    = plot_title,
    legend_title  = "Transect",
    label_gap_in  = label_gap_in
  )

  # ==============================================================
  # SAVE THE SAME PLOT AS TIFF
  # ==============================================================

  tiff(
    filename = output_file,
    width = 1800,
    height = 2400,
    res = 200,
    compression = "lzw"
  )

  draw_two_panel_profile(
    item_names    = transect_names,
    item_data     = transect_data,
    max_depth     = max_depth,
    plot_title    = plot_title,
    legend_title  = "Transect",
    label_gap_in  = label_gap_in
  )

  dev.off()

  # ==============================================================
  # OUTPUT MESSAGE
  # ==============================================================

  cat("\n============================================\n")
  cat("PROFILE CREATED SUCCESSFULLY\n")
  cat("============================================\n")
  cat("Station number:", selected_station_number, "\n")
  cat("Parameter:", selected_parameter, "\n")
  cat("Transects:", paste(transect_names, collapse = ", "), "\n")
  cat("\nTIFF saved at:\n")
  cat(output_file, "\n")
}


# ================================================================
# END OF SCRIPT
# ================================================================
