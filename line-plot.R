# ================================================================
# MULTI-PARAMETER / MULTI-TRANSECT WATER COLUMN PROFILE
# ================================================================

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
# TIFF file saved in the same folder as the selected Excel file.
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
  
  match_index <- match_index[
    !is.na(match_index)
  ]
  
  if (length(match_index) == 0) {
    
    return(NA_character_)
    
  }
  
  actual_names[
    match_index[1]
  ]
  
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
  
  stop(
    "ERROR: Station column was not found."
  )
  
}


if (is.na(depth_col)) {
  
  stop(
    "ERROR: Depth column was not found."
  )
  
}


cat(
  "Station column:",
  station_col,
  "\n"
)


cat(
  "Depth column:",
  depth_col,
  "\n"
)


# ================================================================
# 9. CLEAN STATION AND DEPTH
# ================================================================

data[[station_col]] <- trimws(
  
  as.character(
    data[[station_col]]
  )
  
)


data[[depth_col]] <- suppressWarnings(
  
  as.numeric(
    data[[depth_col]]
  )
  
)


# ================================================================
# 10. IDENTIFY PARAMETER COLUMNS
# ================================================================

excluded_columns <- c(
  
  station_col,
  depth_col
  
)


possible_parameters <- names(data)[
  
  !(names(data) %in% excluded_columns)
  
]


parameter_columns <- possible_parameters[
  
  sapply(
    
    data[possible_parameters],
    
    function(x) {
      
      values <- suppressWarnings(
        as.numeric(x)
      )
      
      sum(!is.na(values)) > 0
      
    }
    
  )
  
]


if (length(parameter_columns) == 0) {
  
  stop(
    "ERROR: No numeric parameter columns were found."
  )
  
}


cat("\nParameters available:\n\n")


for (i in seq_along(parameter_columns)) {
  
  cat(
    i,
    ":",
    parameter_columns[i],
    "\n"
  )
  
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
# 12. SELECT PLOTTING MODE
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
        paste(
          missing_parameters,
          collapse = ", "
        )
      )
    )
    
  }
  
  
  # ==============================================================
  # EXTRACT SELECTED STATION
  # ==============================================================
  
  station_data <- data[
    
    data[[station_col]] ==
      selected_station,
    
    ,
    
    drop = FALSE
    
  ]
  
  
  if (nrow(station_data) == 0) {
    
    stop(
      paste(
        "No data found for station:",
        selected_station
      )
    )
    
  }
  
  
  # ==============================================================
  # CREATE PARAMETER DATA
  # ==============================================================
  
  parameter_data <- list()
  
  
  for (parameter_name in selected_parameters) {
    
    
    values <- suppressWarnings(
      
      as.numeric(
        station_data[[parameter_name]]
      )
      
    )
    
    
    depths <- suppressWarnings(
      
      as.numeric(
        station_data[[depth_col]]
      )
      
    )
    
    
    valid <- !is.na(values) &
      !is.na(depths)
    
    
    temp <- data.frame(
      
      depth = depths[valid],
      
      value = values[valid]
      
    )
    
    
    temp <- temp[
      
      order(temp$depth),
      
      ,
      
      drop = FALSE
      
    ]
    
    
    if (nrow(temp) > 0) {
      
      parameter_data[[parameter_name]] <-
        temp
      
    }
    
  }
  
  
  # ==============================================================
  # REMOVE EMPTY PARAMETERS
  # ==============================================================
  
  parameter_data <- parameter_data[
    
    sapply(
      parameter_data,
      nrow
    ) > 0
    
  ]
  
  
  selected_parameters <- names(
    parameter_data
  )
  
  
  if (length(selected_parameters) == 0) {
    
    stop(
      "No valid parameter data were found."
    )
    
  }
  
  
  # ==============================================================
  # MAXIMUM DEPTH
  # ==============================================================
  
  max_depth <- max(
    
    unlist(
      
      lapply(
        
        parameter_data,
        
        function(x) {
          x$depth
        }
        
      )
      
    ),
    
    na.rm = TRUE
    
  )
  
  
  # ==============================================================
  # OUTPUT FILE
  # ==============================================================
  
  output_file <- file.path(
    
    excel_folder,
    
    "Multi_Parameter_Profile.tiff"
    
  )
  
  
  # ==============================================================
  # OPEN TIFF
  # ==============================================================
  
  tiff(
    
    filename = output_file,
    
    width = 1800,
    
    height = 2400,
    
    res = 200,
    
    compression = "lzw"
    
  )
  
  
  # ==============================================================
  # TWO-PANEL LAYOUT
  # ==============================================================
  #
  # TOP:
  # Stacked X-axes
  #
  # BOTTOM:
  # Actual coloured profile
  #
  # ==============================================================
  
  layout(
    
    matrix(
      
      c(
        1,
        2
      ),
      
      nrow = 2,
      
      byrow = TRUE
      
    ),
    
    heights = c(
      
      0.34,
      0.66
      
    )
    
  )
  
  
  # ==============================================================
  # COMMON HORIZONTAL COORDINATES
  # ==============================================================
  #
  # THESE ARE USED IN BOTH PANELS.
  #
  # Therefore:
  #
  # X-axis minimum = profile minimum
  #
  # X-axis maximum = profile maximum
  #
  # ==============================================================
  
  profile_left <- 0.08
  
  profile_right <- 0.92
  
  profile_width <-
    
    profile_right -
    profile_left
  
  
  # ==============================================================
  # TOP PANEL
  # STACKED PARAMETER AXES
  # ==============================================================
  
  par(
    
    mar = c(
      
      1,
      16,
      2,
      3
      
    )
    
  )
  
  
  plot(
    
    NA,
    
    NA,
    
    type = "n",
    
    xlim = c(
      0,
      1
    ),
    
    ylim = c(
      0,
      length(selected_parameters) + 1
    ),
    
    axes = FALSE,
    
    xlab = "",
    
    ylab = "",
    
    xaxs = "i",
    
    yaxs = "i"
    
  )
  
  
  # ==============================================================
  # DRAW STACKED AXES
  # ==============================================================
  
  for (i in seq_along(selected_parameters)) {
    
    
    parameter_name <-
      selected_parameters[i]
    
    
    current_data <-
      parameter_data[[parameter_name]]
    
    
    current_colour <-
      profile_colours[i]
    
    
    current_min <- min(
      
      current_data$value,
      
      na.rm = TRUE
      
    )
    
    
    current_max <- max(
      
      current_data$value,
      
      na.rm = TRUE
      
    )
    
    
    # ------------------------------------------------------------
    # HANDLE CONSTANT VALUES
    # ------------------------------------------------------------
    
    if (current_min == current_max) {
      
      padding <- ifelse(
        
        current_min == 0,
        
        1,
        
        abs(current_min) * 0.05
        
      )
      
      current_min <-
        current_min - padding
      
      current_max <-
        current_max + padding
      
    }
    
    
    # ------------------------------------------------------------
    # AXIS VERTICAL POSITION
    # ------------------------------------------------------------
    
    y_position <-
      
      length(selected_parameters) -
      i + 1
    
    
    # ------------------------------------------------------------
    # MAIN COLOURED AXIS
    # ------------------------------------------------------------
    
    segments(
      
      x0 = profile_left,
      
      y0 = y_position,
      
      x1 = profile_right,
      
      y1 = y_position,
      
      col = current_colour,
      
      lwd = 2
      
    )
    
    
    # ------------------------------------------------------------
    # CREATE TICKS
    # ------------------------------------------------------------
    
    ticks <- pretty(
      
      c(
        current_min,
        current_max
      )
      
    )
    
    
    ticks <- ticks[
      
      ticks >= current_min &
        ticks <= current_max
      
    ]
    
    
    if (length(ticks) < 2) {
      
      ticks <- seq(
        
        current_min,
        
        current_max,
        
        length.out = 5
        
      )
      
    }
    
    
    # ------------------------------------------------------------
    # CONVERT VALUES TO COMMON AXIS SPACE
    # ------------------------------------------------------------
    
    tick_x <-
      
      profile_left +
      
      (
        
        (
          ticks -
            current_min
        ) /
          
          (
            current_max -
              current_min
          )
        
      ) *
      
      profile_width
    
    
    # ------------------------------------------------------------
    # TICK MARKS
    # ------------------------------------------------------------
    
    segments(
      
      x0 = tick_x,
      
      y0 = y_position,
      
      x1 = tick_x,
      
      y1 = y_position - 0.10,
      
      col = current_colour,
      
      lwd = 1.5
      
    )
    
    
    # ------------------------------------------------------------
    # TICK LABELS
    # ------------------------------------------------------------
    
    text(
      
      x = tick_x,
      
      y = y_position - 0.27,
      
      labels = format(
        
        ticks,
        
        trim = TRUE,
        
        scientific = FALSE
        
      ),
      
      col = current_colour,
      
      cex = 0.8
      
    )
    
    
    # ------------------------------------------------------------
    # PARAMETER NAME
    # ------------------------------------------------------------
    #
    # The name is placed to the LEFT of the axis.
    #
    # It does NOT reduce the axis width.
    #
    # ------------------------------------------------------------
    
    text(
      
      x = profile_left - 0.035,
      
      y = y_position,
      
      labels = parameter_name,
      
      col = current_colour,
      
      font = 2,
      
      pos = 2,
      
      cex = 0.88,
      
      xpd = NA
      
    )
    
  }
  
  
  # ==============================================================
  # BOTTOM PANEL
  # ACTUAL PROFILE
  # ==============================================================
  
  par(
    
    mar = c(
      
      5,
      9,
      2,
      9
      
    )
    
  )
  
  
  plot(
    
    NA,
    
    NA,
    
    type = "n",
    
    xlim = c(
      0,
      1
    ),
    
    ylim = c(
      max_depth,
      0
    ),
    
    axes = FALSE,
    
    xlab = "",
    
    ylab = "",
    
    xaxs = "i",
    
    yaxs = "i"
    
  )
  
  
  # ==============================================================
  # DEPTH TICKS
  # ==============================================================
  
  depth_ticks <- pretty(
    
    c(
      0,
      max_depth
    )
    
  )
  
  
  depth_ticks <- depth_ticks[
    
    depth_ticks >= 0 &
      depth_ticks <= max_depth
    
  ]
  
  
  # ==============================================================
  # DEPTH AXIS
  # ==============================================================
  
  axis(
    
    side = 2,
    
    at = depth_ticks,
    
    labels = paste0(
      
      depth_ticks,
      
      " m"
      
    ),
    
    las = 1,
    
    col = "black",
    
    col.axis = "black",
    
    lwd = 1.5
    
  )
  
  
  # ==============================================================
  # DEPTH GRID
  # ==============================================================
  
  abline(
    
    h = depth_ticks,
    
    col = "grey85",
    
    lty = 3
    
  )
  
  
  # ==============================================================
  # DEPTH LABEL
  # ==============================================================
  
  mtext(
    
    "Depth (m)",
    
    side = 2,
    
    line = 5,
    
    font = 2
    
  )
  
  
  # ==============================================================
  # DRAW COLOURED PROFILES
  # ==============================================================
  #
  # IMPORTANT:
  #
  # The normalized profile uses exactly the same:
  #
  # profile_left
  # profile_right
  #
  # as the stacked X-axes.
  #
  # ==============================================================
  
  for (i in seq_along(selected_parameters)) {
    
    
    parameter_name <-
      selected_parameters[i]
    
    
    current_data <-
      parameter_data[[parameter_name]]
    
    
    current_colour <-
      profile_colours[i]
    
    
    current_min <- min(
      
      current_data$value,
      
      na.rm = TRUE
      
    )
    
    
    current_max <- max(
      
      current_data$value,
      
      na.rm = TRUE
      
    )
    
    
    # ------------------------------------------------------------
    # HANDLE CONSTANT VALUES
    # ------------------------------------------------------------
    
    if (current_min == current_max) {
      
      padding <- ifelse(
        
        current_min == 0,
        
        1,
        
        abs(current_min) * 0.05
        
      )
      
      current_min <-
        current_min - padding
      
      current_max <-
        current_max + padding
      
    }
    
    
    # ------------------------------------------------------------
    # NORMALIZE PARAMETER VALUES
    # ------------------------------------------------------------
    
    normalized_x <- (
      
      current_data$value -
        current_min
      
    ) /
      
      (
        current_max -
          current_min
      )
    
    
    # ------------------------------------------------------------
    # CONVERT TO PROFILE SPACE
    # ------------------------------------------------------------
    
    profile_x <-
      
      profile_left +
      
      normalized_x *
      
      profile_width
    
    
    # ------------------------------------------------------------
    # DRAW PROFILE
    # ------------------------------------------------------------
    
    lines(
      
      profile_x,
      
      current_data$depth,
      
      col = current_colour,
      
      lwd = 3
      
    )
    
  }
  
  
  # ==============================================================
  # BOTTOM HORIZONTAL LINE
  # ==============================================================
  #
  # Starts exactly at the depth-axis position.
  #
  # Ends exactly at the X-axis maximum.
  #
  # NO VERTICAL SIDE LINES ARE DRAWN.
  #
  # ==============================================================
  
  segments(
    
    x0 = profile_left,
    
    y0 = max_depth,
    
    x1 = profile_right,
    
    y1 = max_depth,
    
    col = "black",
    
    lwd = 1.5
    
  )
  
  
  # ==============================================================
  # LEGEND
  # ==============================================================
  
  legend(
    
    "right",
    
    inset = c(
      -0.22,
      0
    ),
    
    legend = selected_parameters,
    
    col =
      profile_colours[
        
        seq_along(
          selected_parameters
        )
        
      ],
    
    lwd = 3,
    
    bty = "n",
    
    title = "Parameter",
    
    xpd = TRUE,
    
    cex = 0.85
    
  )
  
  
  # ==============================================================
  # TITLE
  # ==============================================================
  
  mtext(
    
    paste(
      
      "Water Column Profile —",
      
      selected_station
      
    ),
    
    side = 3,
    
    line = 0.2,
    
    font = 2,
    
    cex = 1.2
    
  )
  
  
  # ==============================================================
  # CLOSE TIFF
  # ==============================================================
  
  dev.off()
  
  
  # ==============================================================
  # OUTPUT MESSAGE
  # ==============================================================
  
  cat(
    "\n============================================\n"
  )
  
  cat(
    "PROFILE CREATED SUCCESSFULLY\n"
  )
  
  cat(
    "============================================\n"
  )
  
  cat(
    "Station:",
    selected_station,
    "\n"
  )
  
  cat(
    "Parameters:",
    paste(
      selected_parameters,
      collapse = ", "
    ),
    "\n"
  )
  
  cat(
    "\nTIFF saved at:\n"
  )
  
  cat(
    output_file,
    "\n"
  )
  
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
  
  station_values <- unique(
    data[[station_col]]
  )
  
  
  station_values <- station_values[
    
    !is.na(station_values)
    
  ]
  
  
  matching_stations <- station_values[
    
    grepl(
      
      paste0(
        "\\b",
        selected_station_number,
        "$"
      ),
      
      station_values
      
    )
    
  ]
  
  
  if (length(matching_stations) == 0) {
    
    stop(
      paste(
        "No stations found for:",
        selected_station_number
      )
    )
    
  }
  
  
  # ==============================================================
  # EXTRACT TRANSECT NAMES
  # ==============================================================
  
  transect_names <- sub(
    
    paste0(
      "\\s+",
      selected_station_number,
      "$"
    ),
    
    "",
    
    matching_stations
    
  )
  
  
  # ==============================================================
  # SORT TRANSECTS
  # ==============================================================
  
  numeric_transect <- suppressWarnings(
    
    as.numeric(
      
      sub(
        
        "^T",
        
        "",
        
        transect_names
        
      )
      
    )
    
  )
  
  
  transect_order <- order(
    
    is.na(
      numeric_transect
    ),
    
    numeric_transect,
    
    transect_names
    
  )
  
  
  matching_stations <-
    
    matching_stations[
      transect_order
    ]
  
  
  transect_names <-
    
    transect_names[
      transect_order
    ]
  
  
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
    
    
    station_value <-
      matching_stations[i]
    
    
    transect_name <-
      transect_names[i]
    
    
    temp <- data[
      
      data[[station_col]] ==
        station_value,
      
      ,
      
      drop = FALSE
      
    ]
    
    
    depths <- suppressWarnings(
      
      as.numeric(
        temp[[depth_col]]
      )
      
    )
    
    
    values <- suppressWarnings(
      
      as.numeric(
        temp[[selected_parameter]]
      )
      
    )
    
    
    valid <- !is.na(depths) &
      !is.na(values)
    
    
    profile <- data.frame(
      
      depth = depths[valid],
      
      value = values[valid]
      
    )
    
    
    profile <- profile[
      
      order(profile$depth),
      
      ,
      
      drop = FALSE
      
    ]
    
    
    if (nrow(profile) > 0) {
      
      transect_data[[transect_name]] <-
        profile
      
    }
    
  }
  
  
  # ==============================================================
  # REMOVE EMPTY TRANSECTS
  # ==============================================================
  
  transect_data <- transect_data[
    
    sapply(
      
      transect_data,
      
      nrow
      
    ) > 0
    
  ]
  
  
  transect_names <- names(
    transect_data
  )
  
  
  if (length(transect_names) == 0) {
    
    stop(
      "No valid transect data were found."
    )
    
  }
  
  
  # ==============================================================
  # MAXIMUM DEPTH
  # ==============================================================
  
  max_depth <- max(
    
    unlist(
      
      lapply(
        
        transect_data,
        
        function(x) {
          x$depth
        }
        
      )
      
    ),
    
    na.rm = TRUE
    
  )
  
  
  # ==============================================================
  # OUTPUT FILE
  # ==============================================================
  
  output_file <- file.path(
    
    excel_folder,
    
    "Multi_Transect_Profile.tiff"
    
  )
  
  
  # ==============================================================
  # OPEN TIFF
  # ==============================================================
  
  tiff(
    
    filename = output_file,
    
    width = 1800,
    
    height = 2400,
    
    res = 200,
    
    compression = "lzw"
    
  )
  
  
  # ==============================================================
  # TWO-PANEL LAYOUT
  # ==============================================================
  
  layout(
    
    matrix(
      
      c(
        1,
        2
      ),
      
      nrow = 2,
      
      byrow = TRUE
      
    ),
    
    heights = c(
      
      0.34,
      0.66
      
    )
    
  )
  
  
  # ==============================================================
  # COMMON HORIZONTAL COORDINATES
  # ==============================================================
  
  profile_left <- 0.08
  
  profile_right <- 0.92
  
  profile_width <-
    
    profile_right -
    profile_left
  
  
  # ==============================================================
  # TOP PANEL
  # STACKED TRANSECT AXES
  # ==============================================================
  
  par(
    
    mar = c(
      
      1,
      16,
      2,
      3
      
    )
    
  )
  
  
  plot(
    
    NA,
    
    NA,
    
    type = "n",
    
    xlim = c(
      0,
      1
    ),
    
    ylim = c(
      0,
      length(transect_names) + 1
    ),
    
    axes = FALSE,
    
    xlab = "",
    
    ylab = "",
    
    xaxs = "i",
    
    yaxs = "i"
    
  )
  
  
  # ==============================================================
  # DRAW TRANSECT AXES
  # ==============================================================
  
  for (i in seq_along(transect_names)) {
    
    
    transect_name <-
      transect_names[i]
    
    
    current_data <-
      transect_data[[transect_name]]
    
    
    current_colour <-
      profile_colours[i]
    
    
    current_min <- min(
      
      current_data$value,
      
      na.rm = TRUE
      
    )
    
    
    current_max <- max(
      
      current_data$value,
      
      na.rm = TRUE
      
    )
    
    
    if (current_min == current_max) {
      
      padding <- ifelse(
        
        current_min == 0,
        
        1,
        
        abs(current_min) * 0.05
        
      )
      
      current_min <-
        current_min - padding
      
      current_max <-
        current_max + padding
      
    }
    
    
    y_position <-
      
      length(transect_names) -
      i + 1
    
    
    # ------------------------------------------------------------
    # COLOURED AXIS
    # ------------------------------------------------------------
    
    segments(
      
      x0 = profile_left,
      
      y0 = y_position,
      
      x1 = profile_right,
      
      y1 = y_position,
      
      col = current_colour,
      
      lwd = 2
      
    )
    
    
    # ------------------------------------------------------------
    # TICKS
    # ------------------------------------------------------------
    
    ticks <- pretty(
      
      c(
        current_min,
        current_max
      )
      
    )
    
    
    ticks <- ticks[
      
      ticks >= current_min &
        ticks <= current_max
      
    ]
    
    
    if (length(ticks) < 2) {
      
      ticks <- seq(
        
        current_min,
        
        current_max,
        
        length.out = 5
        
      )
      
    }
    
    
    tick_x <-
      
      profile_left +
      
      (
        
        (
          ticks -
            current_min
        ) /
          
          (
            current_max -
              current_min
          )
        
      ) *
      
      profile_width
    
    
    # ------------------------------------------------------------
    # TICK MARKS
    # ------------------------------------------------------------
    
    segments(
      
      x0 = tick_x,
      
      y0 = y_position,
      
      x1 = tick_x,
      
      y1 = y_position - 0.10,
      
      col = current_colour,
      
      lwd = 1.5
      
    )
    
    
    # ------------------------------------------------------------
    # TICK LABELS
    # ------------------------------------------------------------
    
    text(
      
      x = tick_x,
      
      y = y_position - 0.27,
      
      labels = format(
        
        ticks,
        
        trim = TRUE,
        
        scientific = FALSE
        
      ),
      
      col = current_colour,
      
      cex = 0.8
      
    )
    
    
    # ------------------------------------------------------------
    # TRANSECT NAME
    # ------------------------------------------------------------
    
    text(
      
      x = profile_left - 0.035,
      
      y = y_position,
      
      labels = transect_name,
      
      col = current_colour,
      
      font = 2,
      
      pos = 2,
      
      cex = 0.88,
      
      xpd = NA
      
    )
    
  }
  
  
  # ==============================================================
  # BOTTOM PANEL
  # PROFILE
  # ==============================================================
  
  par(
    
    mar = c(
      
      5,
      9,
      2,
      9
      
    )
    
  )
  
  
  plot(
    
    NA,
    
    NA,
    
    type = "n",
    
    xlim = c(
      0,
      1
    ),
    
    ylim = c(
      max_depth,
      0
    ),
    
    axes = FALSE,
    
    xlab = "",
    
    ylab = "",
    
    xaxs = "i",
    
    yaxs = "i"
    
  )
  
  
  # ==============================================================
  # DEPTH TICKS
  # ==============================================================
  
  depth_ticks <- pretty(
    
    c(
      0,
      max_depth
    )
    
  )
  
  
  depth_ticks <- depth_ticks[
    
    depth_ticks >= 0 &
      depth_ticks <= max_depth
    
  ]
  
  
  # ==============================================================
  # DEPTH AXIS
  # ==============================================================
  
  axis(
    
    side = 2,
    
    at = depth_ticks,
    
    labels = paste0(
      
      depth_ticks,
      
      " m"
      
    ),
    
    las = 1,
    
    col = "black",
    
    col.axis = "black",
    
    lwd = 1.5
    
  )
  
  
  # ==============================================================
  # DEPTH GRID
  # ==============================================================
  
  abline(
    
    h = depth_ticks,
    
    col = "grey85",
    
    lty = 3
    
  )
  
  
  # ==============================================================
  # DEPTH LABEL
  # ==============================================================
  
  mtext(
    
    "Depth (m)",
    
    side = 2,
    
    line = 5,
    
    font = 2
    
  )
  
  
  # ==============================================================
  # DRAW COLOURED TRANSECT PROFILES
  # ==============================================================
  
  for (i in seq_along(transect_names)) {
    
    
    transect_name <-
      transect_names[i]
    
    
    current_data <-
      transect_data[[transect_name]]
    
    
    current_colour <-
      profile_colours[i]
    
    
    current_min <- min(
      
      current_data$value,
      
      na.rm = TRUE
      
    )
    
    
    current_max <- max(
      
      current_data$value,
      
      na.rm = TRUE
      
    )
    
    
    if (current_min == current_max) {
      
      padding <- ifelse(
        
        current_min == 0,
        
        1,
        
        abs(current_min) * 0.05
        
      )
      
      current_min <-
        current_min - padding
      
      current_max <-
        current_max + padding
      
    }
    
    
    # ------------------------------------------------------------
    # NORMALIZE
    # ------------------------------------------------------------
    
    normalized_x <- (
      
      current_data$value -
        current_min
      
    ) /
      
      (
        current_max -
          current_min
      )
    
    
    # ------------------------------------------------------------
    # SAME HORIZONTAL SPACE AS X-AXES
    # ------------------------------------------------------------
    
    profile_x <-
      
      profile_left +
      
      normalized_x *
      
      profile_width
    
    
    # ------------------------------------------------------------
    # PROFILE LINE
    # ------------------------------------------------------------
    
    lines(
      
      profile_x,
      
      current_data$depth,
      
      col = current_colour,
      
      lwd = 3
      
    )
    
  }
  
  
  # ==============================================================
  # BOTTOM HORIZONTAL LINE
  # ==============================================================
  #
  # EXACTLY FROM:
  #
  # LEFT  = depth-axis/profile minimum
  #
  # RIGHT = X-axis maximum
  #
  # ==============================================================
  
  segments(
    
    x0 = profile_left,
    
    y0 = max_depth,
    
    x1 = profile_right,
    
    y1 = max_depth,
    
    col = "black",
    
    lwd = 1.5
    
  )
  
  
  # ==============================================================
  # LEGEND
  # ==============================================================
  
  legend(
    
    "right",
    
    inset = c(
      -0.22,
      0
    ),
    
    legend = transect_names,
    
    col =
      profile_colours[
        
        seq_along(
          transect_names
        )
        
      ],
    
    lwd = 3,
    
    bty = "n",
    
    title = "Parameter",
    
    xpd = TRUE,
    
    cex = 0.85
    
  )
  
  
  # ==============================================================
  # TITLE
  # ==============================================================
  
  mtext(
    
    paste(
      
      "Water Column Profile —",
      
      selected_parameter,
      
      "- Station",
      
      selected_station_number
      
    ),
    
    side = 3,
    
    line = 0.2,
    
    font = 2,
    
    cex = 1.2
    
  )
  
  
  # ==============================================================
  # CLOSE TIFF
  # ==============================================================
  
  dev.off()
  
  
  # ==============================================================
  # OUTPUT MESSAGE
  # ==============================================================
  
  cat(
    "\n============================================\n"
  )
  
  cat(
    "PROFILE CREATED SUCCESSFULLY\n"
  )
  
  cat(
    "============================================\n"
  )
  
  cat(
    "Station number:",
    selected_station_number,
    "\n"
  )
  
  cat(
    "Parameter:",
    selected_parameter,
    "\n"
  )
  
  cat(
    "Transects:",
    paste(
      transect_names,
      collapse = ", "
    ),
    "\n"
  )
  
  cat(
    "\nTIFF saved at:\n"
  )
  
  cat(
    output_file,
    "\n"
  )
  
}


# ================================================================
# END OF SCRIPT
# ================================================================
