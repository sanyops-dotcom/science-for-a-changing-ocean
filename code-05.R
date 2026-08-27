# ============================================================
# TRANSECT-WISE VERTICAL SECTION PROFILER
# ODV-STYLE PROFILE WITH IDW + BATHYMETRY MASK
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
# 3. READ EXCEL SHEET
# ------------------------------------------------------------
#
# Sheet 1 is used.
#
# Expected columns:
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
# 4. COLUMN NAMES
# ------------------------------------------------------------

station_column <- "Station Name"
depth_column   <- "depth (m)"


# ------------------------------------------------------------
# 5. SELECT TRANSECT
# ------------------------------------------------------------
#
# Change this whenever you want another transect.
#
# Examples:
#
# "T1"
# "T2"
# "T3"
# "T4"
#
# ------------------------------------------------------------

selected_transect <- "T1"


# ------------------------------------------------------------
# 6. SELECT PARAMETER
# ------------------------------------------------------------
#
# Enter the EXACT Excel column name.
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
# 7. CHECK COLUMNS
# ------------------------------------------------------------

if (!station_column %in% names(data_raw)) {
  
  stop(
    paste0(
      "\nERROR: Column '",
      station_column,
      "' was not found.\n\n",
      "Available columns:\n",
      paste(names(data_raw), collapse = "\n")
    )
  )
  
}


if (!depth_column %in% names(data_raw)) {
  
  stop(
    paste0(
      "\nERROR: Column '",
      depth_column,
      "' was not found.\n\n",
      "Available columns:\n",
      paste(names(data_raw), collapse = "\n")
    )
  )
  
}


if (!parameter_column %in% names(data_raw)) {
  
  stop(
    paste0(
      "\nERROR: Parameter column '",
      parameter_column,
      "' was not found.\n\n",
      "Available columns:\n",
      paste(names(data_raw), collapse = "\n")
    )
  )
  
}


# ------------------------------------------------------------
# 8. PREPARE DATA
# ------------------------------------------------------------

data <- data_raw %>%
  
  mutate(
    
    Station = as.character(
      .data[[station_column]]
    ),
    
    Depth = as.numeric(
      .data[[depth_column]]
    ),
    
    Value = as.numeric(
      .data[[parameter_column]]
    )
    
  ) %>%
  
  filter(
    
    !is.na(Station),
    
    !is.na(Depth)
    
  )


# ------------------------------------------------------------
# 9. EXTRACT TRANSECT
# ------------------------------------------------------------
#
# Examples:
#
# T1 S1
# T1 S2
# T1 S3
#
# becomes:
#
# T1
# T1
# T1
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
# T1 S2 -> S2
# T1 S10 -> S10
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
# 11. KEEP ONLY SELECTED TRANSECT
# ------------------------------------------------------------

transect_data <- data %>%
  
  filter(
    Transect == selected_transect
  )


if (nrow(transect_data) == 0) {
  
  stop(
    paste0(
      "\nNo data found for ",
      selected_transect,
      ".\n\nAvailable transects:\n",
      paste(
        sort(unique(data$Transect)),
        collapse = "\n"
      )
    )
  )
  
}


# ------------------------------------------------------------
# 12. ORDER STATIONS NUMERICALLY
# ------------------------------------------------------------
#
# S1
# S2
# S3
# ...
# S10
#
# rather than:
#
# S1
# S10
# S2
#
# ------------------------------------------------------------

station_order <- transect_data %>%
  
  distinct(StationNumber) %>%
  
  mutate(
    
    StationNumberNumeric = as.numeric(
      str_extract(
        StationNumber,
        "[0-9]+"
      )
    )
    
  ) %>%
  
  arrange(
    StationNumberNumeric
  ) %>%
  
  pull(
    StationNumber
  )


transect_data$StationNumber <- factor(
  
  transect_data$StationNumber,
  
  levels = station_order
  
)


# ------------------------------------------------------------
# 13. CREATE X POSITION
# ------------------------------------------------------------

transect_data <- transect_data %>%
  
  mutate(
    
    X = as.numeric(
      StationNumber
    )
    
  )


# ------------------------------------------------------------
# 14. FIND ACTUAL DEPTH RANGE
# ------------------------------------------------------------

min_depth <- min(
  transect_data$Depth,
  na.rm = TRUE
)

max_depth <- max(
  transect_data$Depth,
  na.rm = TRUE
)


cat("\n--------------------------------------\n")
cat("Selected transect :", selected_transect, "\n")
cat("Stations          :", length(station_order), "\n")
cat("Minimum depth     :", min_depth, "m\n")
cat("Maximum depth     :", max_depth, "m\n")
cat("--------------------------------------\n")


# ------------------------------------------------------------
# 15. BATHYMETRY DEPTH FOR EACH STATION
# ------------------------------------------------------------
#
# The deepest ACTUAL depth available at each station is used
# as the local ocean-bottom boundary.
#
# Example:
#
# S1 = 10 m
# S2 = 20 m
# S3 = 30 m
# S4 = 50 m
# S5 = 100 m
# S6 = 200 m
# S7 = 500 m
#
# Everything below those depths is masked.
#
# ------------------------------------------------------------

bathymetry <- transect_data %>%
  
  group_by(
    StationNumber
  ) %>%
  
  summarise(
    
    X = first(X),
    
    BottomDepth = max(
      Depth,
      na.rm = TRUE
    ),
    
    .groups = "drop"
    
  ) %>%
  
  arrange(X)


# ------------------------------------------------------------
# 16. VALID DATA FOR IDW
# ------------------------------------------------------------
#
# Missing values are NOT converted to zero.
#
# They are excluded from the IDW calculation.
#
# ------------------------------------------------------------

idw_data <- transect_data %>%
  
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
# 17. AUTOMATIC PARAMETER RANGE
# ------------------------------------------------------------

parameter_min <- min(
  idw_data$Value,
  na.rm = TRUE
)

parameter_max <- max(
  idw_data$Value,
  na.rm = TRUE
)


cat("\nParameter:", parameter_column, "\n")
cat("Minimum  :", parameter_min, "\n")
cat("Maximum  :", parameter_max, "\n")


# ------------------------------------------------------------
# 18. CREATE IDW GRID
# ------------------------------------------------------------
#
# The grid covers the complete depth range.
#
# Bathymetry masking is applied later so IDW values below
# the ocean bottom are not displayed.
#
# ------------------------------------------------------------

grid <- expand.grid(
  
  X = seq(
    
    min(transect_data$X),
    
    max(transect_data$X),
    
    length.out = 400
    
  ),
  
  Depth = seq(
    
    min_depth,
    
    max_depth,
    
    length.out = 400
    
  )
  
)


# ------------------------------------------------------------
# 19. CONVERT DATA TO SPATIAL OBJECT
# ------------------------------------------------------------

coordinates(idw_data) <- ~ X + Depth

coordinates(grid) <- ~ X + Depth


# ------------------------------------------------------------
# 20. RUN IDW
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
# 21. CONVERT IDW RESULT
# ------------------------------------------------------------

idw_plot <- as.data.frame(
  idw_prediction
)


names(idw_plot)[
  names(idw_plot) == "var1.pred"
] <- "Value"


# ------------------------------------------------------------
# 22. BATHYMETRY MASK
# ------------------------------------------------------------
#
# For every interpolated X position, calculate the bottom
# depth from the neighbouring station bathymetry.
#
# Linear interpolation is used ONLY to create the bottom
# boundary.
#
# It is NOT used to create parameter values.
#
# ------------------------------------------------------------

bottom_depth_at_x <- approx(
  
  x = bathymetry$X,
  
  y = bathymetry$BottomDepth,
  
  xout = idw_plot$X,
  
  rule = 2
  
)$y


idw_plot$BottomDepth <- bottom_depth_at_x


# ------------------------------------------------------------
# 23. REMOVE EVERYTHING BELOW OCEAN BOTTOM
# ------------------------------------------------------------

idw_plot <- idw_plot %>%
  
  filter(
    
    Depth <= BottomDepth
    
  )


# ------------------------------------------------------------
# 24. PREPARE OBSERVATION POINTS
# ------------------------------------------------------------
#
# Actual observations remain visible.
#
# Missing parameter observations are retained.
#
# ------------------------------------------------------------

observation_points <- transect_data %>%
  
  mutate(
    
    ParameterMissing = is.na(Value)
    
  )


# ------------------------------------------------------------
# 25. PREPARE BATHYMETRY POLYGON
# ------------------------------------------------------------
#
# This creates the dark-brown ocean-bottom area.
#
# ------------------------------------------------------------

bathymetry_polygon <- rbind(
  
  data.frame(
    
    X = bathymetry$X,
    
    Depth = bathymetry$BottomDepth
    
  ),
  
  data.frame(
    
    X = rev(
      bathymetry$X
    ),
    
    Depth = rep(
      max_depth,
      nrow(bathymetry)
    )
    
  )
  
)


# ------------------------------------------------------------
# 26. DEPTH AXIS
# ------------------------------------------------------------
#
# These are preferred depth labels.
#
# Only labels within the actual depth range are displayed.
#
# ------------------------------------------------------------

standard_depths <- c(
  
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
  2000
  
)


depth_breaks <- standard_depths[
  
  standard_depths >= min_depth &
    
    standard_depths <= max_depth
  
]


if (length(depth_breaks) < 2) {
  
  depth_breaks <- pretty(
    
    c(
      min_depth,
      max_depth
    ),
    
    n = 8
    
  )
  
}


# ------------------------------------------------------------
# 27. CREATE VERTICAL SECTION
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
# BATHYMETRY
# ----------------------------------------------------------

geom_polygon(
  
  data = bathymetry_polygon,
  
  aes(
    
    x = X,
    
    y = Depth
    
  ),
  
  fill = "#4A2F1B",
  
  colour = NA
  
) +
  
  
  # ----------------------------------------------------------
# BATHYMETRY BOUNDARY
# ----------------------------------------------------------

geom_line(
  
  data = bathymetry,
  
  aes(
    
    x = X,
    
    y = BottomDepth
    
  ),
  
  linewidth = 0.7,
  
  colour = "black"
  
) +
  
  
  # ----------------------------------------------------------
# ACTUAL VALID OBSERVATIONS
# ----------------------------------------------------------

geom_point(
  
  data = observation_points %>%
    
    filter(
      !ParameterMissing
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
# MISSING PARAMETER OBSERVATIONS
# ----------------------------------------------------------
#
# Circle with a small cross.
#
# Shape 4 gives the cross.
# Shape 21 gives the circle.
#
# Both are drawn at the same location.
#
# ----------------------------------------------------------

geom_point(
  
  data = observation_points %>%
    
    filter(
      ParameterMissing
    ),
  
  aes(
    
    x = X,
    
    y = Depth
    
  ),
  
  shape = 21,
  
  size = 3,
  
  stroke = 0.8,
  
  fill = "white",
  
  colour = "black"
  
) +
  
  
  geom_point(
    
    data = observation_points %>%
      
      filter(
        ParameterMissing
      ),
    
    aes(
      
      x = X,
      
      y = Depth
      
    ),
    
    shape = 4,
    
    size = 2,
    
    stroke = 0.8,
    
    colour = "black"
    
  ) +
  
  
  # ----------------------------------------------------------
# DEPTH AXIS
# ----------------------------------------------------------

scale_y_reverse(
  
  breaks = depth_breaks,
  
  expand = c(
    0,
    0
  )
  
) +
  
  
  # ----------------------------------------------------------
# X AXIS
# ----------------------------------------------------------

scale_x_continuous(
  
  breaks = seq_along(
    station_order
  ),
  
  labels = station_order,
  
  expand = c(
    0,
    0
  )
  
) +
  
  
  # ----------------------------------------------------------
# COLOUR SCALE
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
# LABELS
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
      
      size = 10,
      
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
# 28. DISPLAY PROFILER
# ------------------------------------------------------------

print(profiler)


# ------------------------------------------------------------
# 29. EXPORT TIFF
# ------------------------------------------------------------

safe_parameter_name <- gsub(
  
  "[^A-Za-z0-9]+",
  
  "_",
  
  parameter_column
  
)


output_file <- paste0(
  
  selected_transect,
  
  "_",
  
  safe_parameter_name,
  
  "_Vertical_Section_IDW.tif"
  
)


ggsave(
  
  filename = output_file,
  
  plot = profiler,
  
  width = 12,
  
  height = 8,
  
  units = "in",
  
  dpi = 600,
  
  compression = "lzw"
  
)


# ------------------------------------------------------------
# 30. FINAL MESSAGE
# ------------------------------------------------------------

cat("\n======================================\n")

cat("VERTICAL SECTION CREATED\n")

cat("Transect :", selected_transect, "\n")

cat("Station  :", paste(station_order, collapse = ", "), "\n")

cat("Parameter:", parameter_column, "\n")

cat("IDW power: 2\n")

cat("Output   :", output_file, "\n")

cat("======================================\n")


# ============================================================
# END OF CODE
# ============================================================
