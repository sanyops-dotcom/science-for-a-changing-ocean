# ================================================================
# WATER COLUMN MULTI-PARAMETER / MULTI-TRANSECT PROFILE PLOTTER
# ================================================================
#
# EXCEL STRUCTURE:
#
# Station | Depth | DO | pH | Temperature | Salinity | ...
#
# Example:
#
# T1 S1 | 0  | ...
# T1 S1 | 5  | ...
# T1 S1 | 10 | ...
# T1 S2 | 0  | ...
# T2 S1 | 0  | ...
#
# ================================================================
#
# MODE 1
# -------
# One station + multiple parameters
#
# Example:
# T1 S1 + DO + pH + Temperature + Salinity
#
#
# MODE 2
# -------
# One station number + one parameter + multiple transects
#
# Example:
# S1 + DO + T1 + T2 + T3 + T4
#
# ================================================================
#
# OUTPUT:
#
# A TIFF file is automatically saved in the SAME FOLDER
# where the selected Excel file is located.
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

cat("\nColumns detected:\n\n")

print(names(data))

cat("\n")


# ================================================================
# 5. FIND STATION COLUMN
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
# 6. FIND DEPTH COLUMN
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
# 7. CHECK REQUIRED COLUMNS
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
# 8. CLEAN STATION / DEPTH
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
# 9. FIND PARAMETER COLUMNS
# ================================================================
#
# ONLY Station and Depth are excluded.
#
# Every other column is considered a possible parameter.
#
# Parameter names are copied directly from Excel.
#
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
# 10. COLOUR ORDER
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
# 11. SELECT OPERATING MODE
# ================================================================
#
# "parameters"
#     One station + multiple parameters
#
# "transects"
#     One station number + one parameter + multiple transects
#
# ================================================================

plot_type <- "parameters"


# ================================================================
# ================================================================
# MODE 1
# ONE STATION + MULTIPLE PARAMETERS
# ================================================================
# ================================================================

if (plot_type == "parameters") {
  
  
  # ==============================================================
  # SELECT STATION
  # ==============================================================
  
  selected_station <- "T1 S1"
  
  
  # ==============================================================
  # SELECT PARAMETERS
  # ==============================================================
  #
  # DEFAULT:
  # ALL available parameters
  #
  # OR manually select:
  #
  # selected_parameters <- c(
  #   "DO",
  #   "Temperature",
  #   "Salinity"
  # )
  #
  # ==============================================================
  
  selected_parameters <- parameter_columns
  
  
  # ==============================================================
  # MAXIMUM 10 PARAMETERS
  # ==============================================================
  
  if (length(selected_parameters) > 10) {
    
    stop(
      paste(
        "More than 10 parameters selected.",
        "\nPlease select a maximum of 10 parameters."
      )
    )
    
  }
  
  
  # ==============================================================
  # CHECK PARAMETERS
  # ==============================================================
  
  missing_parameters <- selected_parameters[
    !(selected_parameters %in% parameter_columns)
  ]
  
  
  if (length(missing_parameters) > 0) {
    
    stop(
      paste(
        "The following selected parameters were not found:",
        paste(
          missing_parameters,
          collapse = ", "
        )
      )
    )
    
  }
  
  
  # ==============================================================
  # EXTRACT STATION
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
  # DEPTH RANGE
  # ==============================================================
  
  max_depth <- max(
    
    unlist(
      
      lapply(
        parameter_data,
        function(x) x$depth
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
  # TIFF DEVICE
  # ==============================================================
  
  tiff(
    
    filename = output_file,
    
    width = 1800,
    
    height = 2400,
    
    res = 200,
    
    compression = "lzw"
    
  )
  
  
  # ==============================================================
  # TRUE MULTI-PANEL LAYOUT
  # ==============================================================
  #
  # PANEL 1 = AXES
  #
  # PANEL 2 = PROFILE
  #
  # They have completely separate plotting regions.
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
      0.32,
      0.68
    )
    
  )
  
  
  # ==============================================================
  # PANEL 1
  # TOP STACKED AXES
  # ==============================================================
  
  par(
    
    mar = c(
      1,
      8,
      2,
      8
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
    
    ylab = ""
    
  )
  
  
  # ------------------------------------------------
  # DRAW EACH AXIS
  # ------------------------------------------------
  
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
    
    
    # ------------------------------------------------
    # HANDLE CONSTANT DATA
    # ------------------------------------------------
    
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
    
    
    # ------------------------------------------------
    # AXIS POSITION
    # ------------------------------------------------
    
    y_position <-
      length(selected_parameters) -
      i + 1
    
    
    # ------------------------------------------------
    # AXIS LINE
    # ------------------------------------------------
    
    segments(
      
      x0 = 0.08,
      
      y0 = y_position,
      
      x1 = 0.92,
      
      y1 = y_position,
      
      col = current_colour,
      
      lwd = 2
      
    )
    
    
    # ------------------------------------------------
    # TICKS
    # ------------------------------------------------
    
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
    
    
    tick_x <- 0.08 +
      
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
      
      0.84
    
    
    # ------------------------------------------------
    # TICK MARKS
    # ------------------------------------------------
    
    segments(
      
      x0 = tick_x,
      
      y0 = y_position,
      
      x1 = tick_x,
      
      y1 = y_position - 0.10,
      
      col = current_colour,
      
      lwd = 1.5
      
    )
    
    
    # ------------------------------------------------
    # TICK VALUES
    # ------------------------------------------------
    
    text(
      
      x = tick_x,
      
      y = y_position - 0.28,
      
      labels = format(
        
        ticks,
        
        trim = TRUE,
        
        scientific = FALSE
        
      ),
      
      col = current_colour,
      
      cex = 0.8
      
    )
    
    
    # ------------------------------------------------
    # PARAMETER NAME
    # ------------------------------------------------
    
    text(
      
      x = 0.075,
      
      y = y_position + 0.18,
      
      labels = parameter_name,
      
      col = current_colour,
      
      font = 2,
      
      pos = 2,
      
      cex = 0.9
      
    )
    
  }
  
  
  # ==============================================================
  # PANEL 2
  # ACTUAL DEPTH PROFILE
  # ==============================================================
  
  par(
    
    mar = c(
      5,
      8,
      1,
      8
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
    
    ylab = ""
    
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
    
    line = 4.5,
    
    font = 2
    
  )
  
  
  # ==============================================================
  # PROFILE BORDER
  # ==============================================================
  
  segments(
    
    x0 = 0.08,
    
    y0 = 0,
    
    x1 = 0.08,
    
    y1 = max_depth,
    
    lwd = 1.5
    
  )
  
  
  segments(
    
    x0 = 0.92,
    
    y0 = 0,
    
    x1 = 0.92,
    
    y1 = max_depth,
    
    lwd = 1.5
    
  )
  
  
  # ==============================================================
  # DRAW PROFILES
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
    
    
    # ------------------------------------------------
    # NORMALIZE PARAMETER TO PROFILE WIDTH
    # ------------------------------------------------
    
    normalized_x <- (
      
      current_data$value -
        current_min
      
    ) /
      
      (
        current_max -
          current_min
      )
    
    
    profile_x <- 0.08 +
      
      normalized_x *
      
      0.84
    
    
    # ------------------------------------------------
    # DRAW LINE
    # ------------------------------------------------
    
    lines(
      
      profile_x,
      
      current_data$depth,
      
      col = current_colour,
      
      lwd = 3
      
    )
    
  }
  
  
  # ==============================================================
  # RIGHT SIDE LEGEND
  # ==============================================================
  
  legend(
    
    "right",
    
    inset = c(
      -0.20,
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
    
    title = "Profiles",
    
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
    
    line = -0.5,
    
    font = 2,
    
    cex = 1.2
    
  )
  
  
  # ==============================================================
  # CLOSE TIFF
  # ==============================================================
  
  dev.off()
  
  
  # ==============================================================
  # DISPLAY INFORMATION
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
    "\nTIFF saved in:\n"
  )
  
  cat(
    output_file,
    "\n"
  )
  
}


# ================================================================
# ================================================================
# MODE 2
# ONE STATION NUMBER + ONE PARAMETER + MULTIPLE TRANSECTS
# ================================================================
# ================================================================

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
        "was not found."
      )
    )
    
  }
  
  
  # ==============================================================
  # FIND STATIONS MATCHING S1
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
  # DEPTH RANGE
  # ==============================================================
  
  max_depth <- max(
    
    unlist(
      
      lapply(
        transect_data,
        function(x) x$depth
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
  # TIFF DEVICE
  # ==============================================================
  
  tiff(
    
    filename = output_file,
    
    width = 1800,
    
    height = 2400,
    
    res = 200,
    
    compression = "lzw"
    
  )
  
  
  # ==============================================================
  # TRUE MULTI-PANEL LAYOUT
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
      0.32,
      0.68
    )
    
  )
  
  
  # ==============================================================
  # PANEL 1
  # TOP TRANSECT AXES
  # ==============================================================
  
  par(
    
    mar = c(
      1,
      8,
      2,
      8
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
    
    ylab = ""
    
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
    
    
    # ------------------------------------------------
    # CONSTANT DATA
    # ------------------------------------------------
    
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
    
    
    # ------------------------------------------------
    # AXIS POSITION
    # ------------------------------------------------
    
    y_position <-
      length(transect_names) -
      i + 1
    
    
    # ------------------------------------------------
    # AXIS
    # ------------------------------------------------
    
    segments(
      
      x0 = 0.08,
      
      y0 = y_position,
      
      x1 = 0.92,
      
      y1 = y_position,
      
      col = current_colour,
      
      lwd = 2
      
    )
    
    
    # ------------------------------------------------
    # TICKS
    # ------------------------------------------------
    
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
    
    
    tick_x <- 0.08 +
      
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
      
      0.84
    
    
    # ------------------------------------------------
    # TICKS
    # ------------------------------------------------
    
    segments(
      
      x0 = tick_x,
      
      y0 = y_position,
      
      x1 = tick_x,
      
      y1 = y_position - 0.10,
      
      col = current_colour,
      
      lwd = 1.5
      
    )
    
    
    # ------------------------------------------------
    # TICK VALUES
    # ------------------------------------------------
    
    text(
      
      x = tick_x,
      
      y = y_position - 0.28,
      
      labels = format(
        
        ticks,
        
        trim = TRUE,
        
        scientific = FALSE
        
      ),
      
      col = current_colour,
      
      cex = 0.8
      
    )
    
    
    # ------------------------------------------------
    # TRANSECT NAME
    # ------------------------------------------------
    
    text(
      
      x = 0.075,
      
      y = y_position + 0.18,
      
      labels = transect_name,
      
      col = current_colour,
      
      font = 2,
      
      pos = 2,
      
      cex = 0.9
      
    )
    
  }
  
  
  # ==============================================================
  # PANEL 2
  # DEPTH PROFILE
  # ==============================================================
  
  par(
    
    mar = c(
      5,
      8,
      1,
      8
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
    
    ylab = ""
    
  )
  
  
  # ==============================================================
  # DEPTH AXIS
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
    
    line = 4.5,
    
    font = 2
    
  )
  
  
  # ==============================================================
  # PROFILE BORDER
  # ==============================================================
  
  segments(
    
    x0 = 0.08,
    
    y0 = 0,
    
    x1 = 0.08,
    
    y1 = max_depth,
    
    lwd = 1.5
    
  )
  
  
  segments(
    
    x0 = 0.92,
    
    y0 = 0,
    
    x1 = 0.92,
    
    y1 = max_depth,
    
    lwd = 1.5
    
  )
  
  
  # ==============================================================
  # DRAW TRANSECT PROFILES
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
    
    
    # ------------------------------------------------
    # NORMALIZE
    # ------------------------------------------------
    
    normalized_x <- (
      
      current_data$value -
        current_min
      
    ) /
      
      (
        current_max -
          current_min
      )
    
    
    # ------------------------------------------------
    # PROFILE X POSITION
    # ------------------------------------------------
    
    profile_x <- 0.08 +
      
      normalized_x *
      
      0.84
    
    
    # ------------------------------------------------
    # DRAW PROFILE
    # ------------------------------------------------
    
    lines(
      
      profile_x,
      
      current_data$depth,
      
      col = current_colour,
      
      lwd = 3
      
    )
    
  }
  
  
  # ==============================================================
  # RIGHT SIDE LEGEND
  # ==============================================================
  
  legend(
    
    "right",
    
    inset = c(
      -0.20,
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
    
    title = selected_parameter,
    
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
    
    line = -0.5,
    
    font = 2,
    
    cex = 1.2
    
  )
  
  
  # ==============================================================
  # CLOSE TIFF
  # ==============================================================
  
  dev.off()
  
  
  # ==============================================================
  # MESSAGE
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
    "\nTIFF saved in:\n"
  )
  
  cat(
    output_file,
    "\n"
  )
  
}


# ================================================================
# END OF CODE
# ================================================================
