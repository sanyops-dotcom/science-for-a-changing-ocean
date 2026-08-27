# ============================================================
# VERTICAL SECTION PROFILER
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
# ============================================================


# ------------------------------------------------------------
# 1. REQUIRED PACKAGES
# ------------------------------------------------------------

required_packages <- c(
  "readxl",
  "dplyr",
  "stringr",
  "ggplot2",
  "gstat",
  "sp",
  "scales"
)

for (pkg in required_packages) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    install.packages(pkg)
  }
}

library(readxl)
library(dplyr)
library(stringr)
library(ggplot2)
library(gstat)
library(sp)
library(scales)


# ------------------------------------------------------------
# 2. SELECT EXCEL FILE
# ------------------------------------------------------------

excel_file <- file.choose()

cat("\nExcel file selected:\n")
cat(excel_file, "\n")


# ------------------------------------------------------------
# 3. READ SHEET 1
# ------------------------------------------------------------
#
# Sheet 1 contains:
#
# Station Name
# depth (m)
# DO(mg/L)
# Tem(°C)
# TPAE (µg/L)
# TPAH (µg/L)
#
# ------------------------------------------------------------

data_raw <- read_excel(
  excel_file,
  sheet = 1
)

cat("\nColumns detected:\n")
print(names(data_raw))


# ------------------------------------------------------------
# 4. DEFINE IMPORTANT COLUMN NAMES
# ------------------------------------------------------------

station_column <- "Station Name"
depth_column   <- "depth (m)"


# ------------------------------------------------------------
# 5. SELECT THE STATION NUMBER
# ------------------------------------------------------------
#
# IMPORTANT:
#
# Enter ONLY the station number here.
#
# Example:
#
# "S1"
#
# The code will then find:
#
# T1 S1
# T2 S1
# T3 S1
# T4 S1
#
# from the Station Name column.
#
# ------------------------------------------------------------

selected_station <- "S1"


# ------------------------------------------------------------
# 6. SELECT PARAMETER TO PLOT
# ------------------------------------------------------------
#
# Enter the EXACT column name from Excel.
#
# Examples:
#
# "DO(mg/L)"
# "Tem(°C)"
# "TPAE (µg/L)"
# "TPAH (µg/L)"
#
# ------------------------------------------------------------

parameter_column <- "DO(mg/L)"


# ------------------------------------------------------------
# 7. CHECK REQUIRED COLUMNS
# ------------------------------------------------------------

if (!station_column %in% names(data_raw)) {
  stop(
    paste0(
      "\nERROR: '", station_column,
      "' column was not found.\n\nAvailable columns:\n",
      paste(names(data_raw), collapse = "\n")
    )
  )
}

if (!depth_column %in% names(data_raw)) {
  stop(
    paste0(
      "\nERROR: '", depth_column,
      "' column was not found.\n\nAvailable columns:\n",
      paste(names(data_raw), collapse = "\n")
    )
  )
}

if (!parameter_column %in% names(data_raw)) {
  stop(
    paste0(
      "\nERROR: '", parameter_column,
      "' column was not found.\n\nAvailable columns:\n",
      paste(names(data_raw), collapse = "\n")
    )
  )
}


# ------------------------------------------------------------
# 8. PREPARE DATA
# ------------------------------------------------------------

data <- data_raw %>%
  mutate(
    Station = as.character(.data[[station_column]]),
    Depth = as.numeric(.data[[depth_column]]),
    Value = as.numeric(.data[[parameter_column]])
  ) %>%
  filter(
    !is.na(Station),
    !is.na(Depth)
  )


# ------------------------------------------------------------
# 9. EXTRACT TRANSECT FROM STATION NAME
# ------------------------------------------------------------
#
# Your station names are written like:
#
# T1 S1
# T2 S1
# T3 S1
# T4 S1
#
# This extracts:
#
# T1
# T2
# T3
# T4
#
# ------------------------------------------------------------

data <- data %>%
  mutate(
    Transect = str_extract(
      Station,
      "^T[0-9]+"
    )
  )


# ------------------------------------------------------------
# 10. EXTRACT STATION NUMBER
# ------------------------------------------------------------
#
# Examples:
#
# T1 S1 -> S1
# T2 S1 -> S1
# T2 S2 -> S2
#
# ------------------------------------------------------------

data <- data %>%
  mutate(
    StationNumber = str_extract(
      Station,
      "S[0-9]+"
    )
  )


# ------------------------------------------------------------
# 11. KEEP ONLY THE SELECTED STATION
# ------------------------------------------------------------

station_data <- data %>%
  filter(
    StationNumber == selected_station
  )


if (nrow(station_data) == 0) {

  stop(
    paste0(
      "\nNo data found for station ",
      selected_station,
      ".\n\nStations available in the Excel file:\n",
      paste(
        sort(unique(data$StationNumber)),
        collapse = "\n"
      )
    )
  )

}


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

transect_names <- c(

  "T1" = "Uvari",
  "T2" = "Cape",
  "T3" = "Colachel",
  "T4" = "Kollam"

  # Add more here when required:
  # ,"T5" = "XXXXX"
  # ,"T6" = "XXXXX"
  # ,"T7" = "XXXXX"
  # ,"T8" = "XXXXX"

)


# ------------------------------------------------------------
# 13. CHECK THAT TRANSECT NAMES EXIST
# ------------------------------------------------------------

detected_transects <- unique(
  station_data$Transect
)

missing_names <- detected_transects[
  !detected_transects %in% names(transect_names)
]

if (length(missing_names) > 0) {

  warning(
    paste0(
      "\nThe following transects do not yet have a place name:\n",
      paste(missing_names, collapse = ", "),
      "\n\nTheir T-number will be used temporarily."
    )
  )

}


# ------------------------------------------------------------
# 14. SET TRANSECT ORDER
# ------------------------------------------------------------
#
# Transects are ordered numerically:
#
# T1
# T2
# T3
# T4
# ...
#
# ------------------------------------------------------------

transect_order <- paste0(
  "T",
  sort(
    as.numeric(
      str_extract(
        detected_transects,
        "[0-9]+"
      )
    )
  )
)

transect_order <- transect_order[
  transect_order %in% detected_transects
]


station_data$Transect <- factor(
  station_data$Transect,
  levels = transect_order
)


# ------------------------------------------------------------
# 15. CREATE X POSITION
# ------------------------------------------------------------
#
# Each transect gets one X position.
#
# T1 = 1
# T2 = 2
# T3 = 3
# T4 = 4
#
# ------------------------------------------------------------

station_data <- station_data %>%
  mutate(
    X = as.numeric(Transect)
  )


# ------------------------------------------------------------
# 16. CHECK AVAILABLE DEPTHS
# ------------------------------------------------------------

available_depths <- sort(
  unique(
    station_data$Depth
  )
)

cat("\nDepths found for selected station:\n")
print(available_depths)


# ------------------------------------------------------------
# 17. VALID DATA FOR IDW
# ------------------------------------------------------------
#
# Missing values are NOT converted to zero.
#
# At this stage your current Excel has no missing parameter
# observations, but this structure is prepared for them.
#
# ------------------------------------------------------------

idw_data <- station_data %>%
  filter(
    !is.na(Value),
    is.finite(Value)
  )


if (nrow(idw_data) < 3) {

  stop(
    "\nNot enough valid observations for IDW interpolation."
  )

}


# ------------------------------------------------------------
# 18. AUTOMATIC PARAMETER MINIMUM AND MAXIMUM
# ------------------------------------------------------------

parameter_min <- min(
  idw_data$Value,
  na.rm = TRUE
)

parameter_max <- max(
  idw_data$Value,
  na.rm = TRUE
)


cat("\n--------------------------------------\n")
cat("Selected station :", selected_station, "\n")
cat("Selected parameter:", parameter_column, "\n")
cat("Minimum value     :", parameter_min, "\n")
cat("Maximum value     :", parameter_max, "\n")
cat("--------------------------------------\n")


# ------------------------------------------------------------
# 19. CREATE IDW GRID
# ------------------------------------------------------------
#
# X = transect position
# Y = depth
#
# A fine grid creates the coloured vertical section.
#
# ------------------------------------------------------------

x_min <- min(station_data$X)
x_max <- max(station_data$X)

y_min <- min(station_data$Depth)
y_max <- max(station_data$Depth)


grid <- expand.grid(

  X = seq(
    x_min,
    x_max,
    length.out = 300
  ),

  Depth = seq(
    y_min,
    y_max,
    length.out = 300
  )

)


# ------------------------------------------------------------
# 20. PREPARE DATA FOR GSTAT
# ------------------------------------------------------------

coordinates(idw_data) <- ~ X + Depth

coordinates(grid) <- ~ X + Depth


# ------------------------------------------------------------
# 21. IDW INTERPOLATION
# ------------------------------------------------------------
#
# IDW power = 2
#
# nmax = maximum number of nearby observations used.
#
# ------------------------------------------------------------

cat("\nRunning IDW interpolation...\n")


idw_model <- gstat(

  formula = Value ~ 1,

  locations = idw_data,

  nmax = 12,

  set = list(
    idp = 2
  )

)


idw_prediction <- predict(

  idw_model,

  newdata = grid

)


# ------------------------------------------------------------
# 22. CONVERT IDW OUTPUT TO DATA FRAME
# ------------------------------------------------------------

idw_plot <- as.data.frame(
  idw_prediction
)


names(idw_plot)[
  names(idw_plot) == "var1.pred"
] <- "Value"


# ------------------------------------------------------------
# 23. CREATE TRANSECT LABELS
# ------------------------------------------------------------

transect_label_vector <- sapply(

  levels(station_data$Transect),

  function(x) {

    if (x %in% names(transect_names)) {

      transect_names[[x]]

    } else {

      x

    }

  }

)


# ------------------------------------------------------------
# 24. CREATE PROFILER
# ------------------------------------------------------------

profiler <- ggplot() +

  # ----------------------------------------------------------
  # IDW COLOUR FIELD
  # ----------------------------------------------------------

  geom_raster(

    data = idw_plot,

    aes(
      x = X,
      y = Depth,
      fill = Value
    )

  ) +

  # ----------------------------------------------------------
  # ACTUAL OBSERVATION POINTS
  # ----------------------------------------------------------
  #
  # The circles identify the actual sampling observations.
  #
  # ----------------------------------------------------------

  geom_point(

    data = station_data %>%
      filter(
        !is.na(Value)
      ),

    aes(
      x = X,
      y = Depth
    ),

    shape = 21,

    size = 2.2,

    stroke = 0.5,

    fill = "white"

  ) +

  # ----------------------------------------------------------
  # DEPTH AXIS
  # ----------------------------------------------------------

  scale_y_reverse(

    breaks = available_depths,

    expand = c(0, 0)

  ) +

  # ----------------------------------------------------------
  # AUTOMATIC COLOUR SCALE
  # ----------------------------------------------------------

  scale_fill_gradientn(

    colours = c(

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
      "#A50026"

    ),

    limits = c(
      parameter_min,
      parameter_max
    ),

    oob = scales::squish,

    name = parameter_column

  ) +

  # ----------------------------------------------------------
  # X-AXIS
  # ----------------------------------------------------------

  scale_x_continuous(

    breaks = seq_along(
      levels(station_data$Transect)
    ),

    labels = transect_label_vector,

    expand = c(
      0,
      0
    )

  ) +

  # ----------------------------------------------------------
  # AXIS LABELS
  # ----------------------------------------------------------

  labs(

    x = NULL,

    y = "Depth (m)"

  ) +

  # ----------------------------------------------------------
  # THEME
  # ----------------------------------------------------------

  theme_bw() +

  theme(

    panel.grid = element_blank(),

    axis.text.x = element_text(

      size = 11,

      angle = 0,

      hjust = 0.5

    ),

    axis.text.y = element_text(

      size = 10

    ),

    axis.title.y = element_text(

      size = 11

    ),

    legend.position = "right",

    legend.title = element_text(

      size = 10

    ),

    legend.text = element_text(

      size = 9

    ),

    plot.margin = margin(

      10,

      15,

      10,

      10

    )

  )


# ------------------------------------------------------------
# 25. DISPLAY PROFILER
# ------------------------------------------------------------

print(profiler)


# ------------------------------------------------------------
# 26. EXPORT TIFF
# ------------------------------------------------------------

output_file <- paste0(

  selected_station,
  "_",
  gsub(
    "[^A-Za-z0-9]+",
    "_",
    parameter_column
  ),
  "_Vertical_Profiler_IDW.tif"

)


ggsave(

  filename = output_file,

  plot = profiler,

  width = 10,

  height = 7,

  units = "in",

  dpi = 600,

  compression = "lzw"

)


cat("\n--------------------------------------\n")
cat("Profiler saved as:\n")
cat(output_file, "\n")
cat("--------------------------------------\n")


# ============================================================
# END
# ============================================================
