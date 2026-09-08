# ============================================================
# SAMPLING LOCATION + GEBCO BATHYMETRY MAP
# ============================================================
#
# Excel:
#   Transect | Latitude | Longitude
#
# Example:
#
#   T1 S1    | 8.20 | 76.10
#   T1 S2    | 8.35 | 76.30
#   T2 S1    | 8.80 | 76.50
#   T4 S2    | 9.70 | 77.20
#
# The complete Transect value is used as the map label.
#
# ============================================================


# ============================================================
# 1. REQUIRED PACKAGES
# ============================================================

required_packages <- c(
  "terra",
  "readxl",
  "ggplot2",
  "dplyr",
  "sf",
  "rnaturalearth",
  "rnaturalearthdata",
  "ggspatial",
  "metR",
  "ggrepel"
)

installed <- rownames(installed.packages())

for (pkg in required_packages) {
  
  if (!(pkg %in% installed)) {
    
    install.packages(
      pkg,
      dependencies = TRUE
    )
    
  }
  
}


library(terra)
library(readxl)
library(ggplot2)
library(dplyr)
library(sf)
library(rnaturalearth)
library(rnaturalearthdata)
library(ggspatial)
library(metR)
library(ggrepel)


# ============================================================
# 1b. DMM (DEGREES + DECIMAL MINUTES) TO DECIMAL DEGREES
# ============================================================
#
# Converts coordinates like "8\u00b03.342N" or "77\u00b030.175E" into
# plain decimal degrees (e.g. 8.0557).
#
# Handles a leading degree symbol, decimal minutes, and a
# trailing compass direction (N/S/E/W), with optional stray
# whitespace around the value.
#
# ============================================================

dmm_to_decimal <- function(x) {
  
  m <- regmatches(
    x,
    regexec("([0-9]+)[\u00b0\u00b0]([0-9.]+)([NSEWnsew])", x)
  )
  
  sapply(m, function(part) {
    
    if (length(part) != 4) return(NA_real_)
    
    deg <- as.numeric(part[2])
    min <- as.numeric(part[3])
    dir <- toupper(part[4])
    
    dec <- deg + min / 60
    
    if (dir %in% c("S", "W")) dec <- -dec
    
    dec
    
  })
  
}


# ============================================================
# 2. SELECT INPUT FILES
# ============================================================

cat("\n")
cat("Select the EXCEL file containing sampling locations.\n")

excel_file <- file.choose()


cat("\n")
cat("Select the GEBCO NetCDF (.nc) file.\n")

gebco_file <- file.choose()


# ============================================================
# 3. MANUAL MAP EXTENT
# ============================================================

map_lon_min <- 74.5
map_lon_max <- 79

map_lat_min <- 6.8
map_lat_max <- 12


# ============================================================
# 4. BATHYMETRY SETTINGS
# ============================================================

min_depth <- 0

max_depth <- 2500


# ============================================================
# 5. CONTOUR SETTINGS
# ============================================================

#contour_label_interval<- 250

#contour_interval<- 500

contour_line_size <- 0.50

#contour_label_size <- 3.0

#contour_label_skip <- 4


# ---- Selected highlighted contours (own colour each) ----
#
# These are drawn as a SEPARATE, additional layer on top of
# the regular grey contour lines above (which are left
# unchanged). Each one gets its own colour, and its own entry
# in the legend on the right, replacing the bathymetry
# colour-bar legend.

selected_contour_levels <- c(10, 20, 30, 50, 100, 200, 500)

selected_contour_colours <- c(
  
  "10"  = "#C83E4D",
  
  "20"  = "#3A8F6B",
  
  "30"  = "#D98C2B",
  
  "50"  = "#D95F8D",
  
  "100" = "#8B654A",
  
  "200" = "#B57AC3",
  
  "500" = "#3F3F46"
  
)

selected_contour_line_size <- 0.50


# ============================================================
# 6. SAMPLING POINT SETTINGS
# ============================================================

sampling_point_size <- 1.5

sampling_point_stroke <- 0.8


# ============================================================
# 7. AUTOMATIC LABEL OFFSET
# ============================================================

default_label_x_offset <- 0.06

default_label_y_offset <- 0.06


# ============================================================
# 8. MANUAL TRANSECT/STATION LABEL POSITIONS
# ============================================================
#
# IMPORTANT:
#
# The values here MUST EXACTLY MATCH the values in the
# Transect column of your Excel file.
#
# Example:
#
# "T4 S2" = c(77.20, 9.80)
#
# This moves ONLY the label.
#
# The actual sampling point remains at the Excel coordinate.
#
# ============================================================


manual_label_positions <- list(
  
  # Example:
  #
  # "T1 S1" = c(76.10, 8.30),
  # "T1 S2" = c(76.30, 8.45),
  # "T2 S1" = c(76.55, 8.90),
  # "T4 S2" = c(77.30, 9.80)
  
)


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
# "T4"  = c(77.55, 8.40),
# "T13" = c(75.10, 11.10)
#
# ============================================================

manual_transect_label_positions <- list(
  
  # Example:
  #
  # "T4"  = c(77.55, 8.40),
  # "T13" = c(75.10, 11.10)
  
)


# Default extra push (in decimal degrees) applied eastward
# (onto land) from the coast-side station of each transect.

transect_label_land_offset <- 0.12


# ============================================================
# 9. LABEL APPEARANCE
# ============================================================

# ---- Station (Sx) labels, placed at each point ----

station_label_size <- 3.0

station_label_fontface <- "plain"

station_label_colour <- "black"


# ---- Transect (Tx) labels, one per transect, on land ----

transect_label_size <- 4.2

transect_label_fontface <- "bold"

transect_label_colour <- "black"


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

label_box_padding <- 0.3

label_point_padding <- 0.25

label_min_segment_length <- 0

label_max_overlaps <- Inf

label_repel_seed <- 42


# ============================================================
# 10. NORTH ARROW
# ============================================================
#
# This version uses a fixed corner position.
#
# We will make it completely longitude/latitude adjustable
# in the next refinement if required.
#
# ============================================================

north_arrow_location <- "tr"


# ============================================================
# 11. SCALE BAR
# ============================================================

scale_bar_location <- "bl"

scale_bar_width_hint <- 0.25


# ============================================================
# 12. OUTPUT SETTINGS
# ============================================================

output_width <- 8

output_height <- 9

output_dpi <- 1200


# ============================================================
# 13. OUTPUT FOLDER
# ============================================================

output_folder <- dirname(excel_file)


png_file <- file.path(
  output_folder,
  "Sampling_Location_Bathymetry_Map.png"
)


tiff_file <- file.path(
  output_folder,
  "Sampling_Location_Bathymetry_Map.tiff"
)


# ============================================================
# 14. READ EXCEL
# ============================================================

cat("\n")
cat("====================================================\n")
cat("READING EXCEL FILE\n")
cat("====================================================\n")


excel_data <- read_excel(excel_file)


cat("\nExcel columns found:\n")

print(names(excel_data))


# ============================================================
# 15. FIND REQUIRED COLUMNS
# ============================================================

column_names_lower <- tolower(
  trimws(names(excel_data))
)


# ------------------------------------------------------------
# TRANSECT
# ------------------------------------------------------------

transect_candidates <- c(
  "transect",
  "transect_name",
  "transectname",
  "station",
  "name"
)


transect_index <- which(
  
  column_names_lower %in%
    transect_candidates
  
)


if (length(transect_index) == 0) {
  
  stop(
    "\nERROR: Could not find the Transect column.\n",
    "Please name the column 'Transect'.\n"
  )
  
}


transect_column <- names(
  excel_data
)[transect_index[1]]


# ------------------------------------------------------------
# LATITUDE
# ------------------------------------------------------------

latitude_candidates <- c(
  "latitude",
  "lat"
)


latitude_index <- which(
  
  column_names_lower %in%
    latitude_candidates
  
)


if (length(latitude_index) == 0) {
  
  stop(
    "\nERROR: Could not find Latitude column.\n",
    "Please name the column 'Latitude'.\n"
  )
  
}


latitude_column <- names(
  excel_data
)[latitude_index[1]]


# ------------------------------------------------------------
# LONGITUDE
# ------------------------------------------------------------

longitude_candidates <- c(
  "longitude",
  "lon",
  "long"
)


longitude_index <- which(
  
  column_names_lower %in%
    longitude_candidates
  
)


if (length(longitude_index) == 0) {
  
  stop(
    "\nERROR: Could not find Longitude column.\n",
    "Please name the column 'Longitude'.\n"
  )
  
}


longitude_column <- names(
  excel_data
)[longitude_index[1]]


cat("\n")
cat("Transect column :", transect_column, "\n")
cat("Latitude column :", latitude_column, "\n")
cat("Longitude column:", longitude_column, "\n")


# ============================================================
# 16. CLEAN SAMPLING DATA
# ============================================================

sampling_data <- excel_data %>%
  
  transmute(
    
    Transect = trimws(
      as.character(
        .data[[transect_column]]
      )
    ),
    
    Latitude = dmm_to_decimal(
      .data[[latitude_column]]
    ),
    
    Longitude = dmm_to_decimal(
      .data[[longitude_column]]
    )
    
  ) %>%
  
  filter(
    
    !is.na(Transect),
    
    !is.na(Latitude),
    
    !is.na(Longitude)
    
  )


# ============================================================
# 17. DISPLAY SAMPLING DATA
# ============================================================

cat("\n")
cat("====================================================\n")
cat("SAMPLING LOCATIONS\n")
cat("====================================================\n\n")


print(sampling_data)


cat("\nNumber of sampling locations:",
    nrow(sampling_data),
    "\n\n")


# ============================================================
# 18. CHECK MAP EXTENT
# ============================================================

outside_points <- sampling_data %>%
  
  filter(
    
    Longitude < map_lon_min |
      
      Longitude > map_lon_max |
      
      Latitude < map_lat_min |
      
      Latitude > map_lat_max
    
  )


if (nrow(outside_points) > 0) {
  
  warning(
    
    "\nSome Excel sampling points are outside the selected ",
    "map extent.\n\n",
    
    paste(
      outside_points$Transect,
      collapse = ", "
    )
    
  )
  
}


# ============================================================
# 19. READ GEBCO USING TERRA
# ============================================================

cat("\n")
cat("====================================================\n")
cat("READING GEBCO FILE\n")
cat("====================================================\n\n")


cat("GEBCO file:\n")
cat(gebco_file)
cat("\n\n")


gebco <- tryCatch(
  
  {
    
    rast(gebco_file)
    
  },
  
  error = function(e) {
    
    stop(
      
      "\nERROR while reading GEBCO NetCDF file:\n",
      
      e$message,
      
      "\n\nPlease check that the selected file is a valid ",
      "GEBCO NetCDF bathymetry file.\n"
      
    )
    
  }
  
)


cat("GEBCO successfully loaded.\n\n")


cat("GEBCO information:\n")

print(gebco)


# ============================================================
# 20. CHECK GEBCO CRS
# ============================================================

cat("\nGEBCO CRS:\n")

print(crs(gebco))


# ============================================================
# 21. SET CRS IF NECESSARY
# ============================================================

if (is.na(crs(gebco))) {
  
  crs(gebco) <- "EPSG:4326"
  
}


# ============================================================
# 22. CROP GEBCO TO MANUAL MAP EXTENT
# ============================================================

cat("\nCropping GEBCO to selected region...\n")


map_extent <- ext(
  
  map_lon_min,
  
  map_lon_max,
  
  map_lat_min,
  
  map_lat_max
  
)


gebco_crop <- crop(
  
  gebco,
  
  map_extent
  
)


cat("GEBCO crop complete.\n")


# ============================================================
# 23. CHECK CROPPED DATA
# ============================================================

if (ncell(gebco_crop) == 0) {
  
  stop(
    
    "\nERROR: No GEBCO cells were found inside the selected ",
    "map extent.\n\n",
    
    "Longitude: ",
    map_lon_min,
    " to ",
    map_lon_max,
    "\n",
    
    "Latitude: ",
    map_lat_min,
    " to ",
    map_lat_max,
    "\n"
    
  )
  
}


# ============================================================
# 24. CONVERT GEBCO ELEVATION TO DEPTH
# ============================================================
#
# GEBCO:
#
# Land      = positive elevation
# Ocean     = negative elevation
#
# We want:
#
# Ocean depth = positive value
#
# ============================================================


depth_raster <- -gebco_crop


# ============================================================
# 25. CREATE BATHYMETRY DATA FRAME
# ============================================================

cat("\nConverting bathymetry to plotting data...\n")


bathymetry_df <- as.data.frame(
  
  depth_raster,
  
  xy = TRUE,
  
  na.rm = FALSE
  
)


# Rename raster value column

names(bathymetry_df)[3] <- "Depth"


# ============================================================
# 26. REMOVE LAND FROM BATHYMETRY DATA
# ============================================================

bathymetry_df <- bathymetry_df %>%
  
  mutate(
    
    OceanDepth = ifelse(
      
      Depth > 0,
      
      Depth,
      
      NA_real_
      
    )
    
  )


# ============================================================
# 27. LIMIT DEPTH TO 2000 M FOR COLOUR SCALE
# ============================================================

bathymetry_df <- bathymetry_df %>%
  
  mutate(
    
    PlotDepth = ifelse(
      
      !is.na(OceanDepth),
      
      pmin(
        OceanDepth,
        max_depth
      ),
      
      NA_real_
      
    )
    
  )


# ============================================================
# 28. CHECK BATHYMETRY VALUES
# ============================================================

valid_depths <- bathymetry_df$OceanDepth[
  
  !is.na(
    bathymetry_df$OceanDepth
  )
  
]


if (length(valid_depths) == 0) {
  
  stop(
    
    "\nERROR: No ocean bathymetry was detected in the ",
    "selected GEBCO region.\n"
    
  )
  
}


cat("\nBathymetry statistics:\n")

cat(
  "Minimum ocean depth:",
  min(valid_depths),
  "m\n"
)

cat(
  "Maximum ocean depth:",
  max(valid_depths),
  "m\n"
)


# ============================================================
# 29. CONTOUR LEVELS
# ============================================================
#contour_levels <- seq(
  #contour_interval,
  #max_depth,
 # by = contour_interval
#)
#label_levels <- seq(
  #contour_label_interval,
  #max_depth,
  #by = contour_label_interval
#)
# ============================================================
# 30. LOAD LAND
# ============================================================

cat("\nLoading India/land polygons...\n")


world <- ne_countries(
  
  scale = "medium",
  
  returnclass = "sf"
  
)


world <- st_transform(
  
  world,
  
  crs = 4326
  
)


# ============================================================
# 31. CROP LAND TO MAP REGION
# ============================================================

bbox <- st_bbox(
  
  c(
    
    xmin = map_lon_min,
    
    xmax = map_lon_max,
    
    ymin = map_lat_min,
    
    ymax = map_lat_max
    
  ),
  
  crs = st_crs(4326)
  
)


bbox_sf <- st_as_sfc(bbox)


land <- suppressWarnings(
  
  st_intersection(
    
    world,
    
    bbox_sf
    
  )
  
)


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

label_data <- sampling_data %>%
  
  mutate(
    
    TransectNumber = sub(
      "^\\s*(T[0-9]+).*$",
      "\\1",
      Transect
    ),
    
    StationLabel = sub(
      "^.*\\b(S[0-9]+)\\s*$",
      "\\1",
      Transect
    ),
    
    LabelLongitude =
      Longitude +
      default_label_x_offset,
    
    LabelLatitude =
      Latitude +
      default_label_y_offset
    
  )


if (any(label_data$TransectNumber == label_data$Transect)) {
  
  warning(
    
    "\nSome Transect values do not match the expected 'Tx Sx' ",
    "format (e.g. 'T4 S2'). Check these rows:\n\n",
    
    paste(
      label_data$Transect[
        label_data$TransectNumber == label_data$Transect
      ],
      collapse = ", "
    )
    
  )
  
}


# ============================================================
# 33. APPLY MANUAL LABEL POSITIONS
# ============================================================

if (length(manual_label_positions) > 0) {
  
  for (label_name in names(manual_label_positions)) {
    
    position <- manual_label_positions[[label_name]]
    
    matching_rows <- which(
      label_data$Transect == label_name
    )
    
    if (length(matching_rows) > 0) {
      
      label_data$LabelLongitude[
        matching_rows
      ] <- position[1]
      
      label_data$LabelLatitude[
        matching_rows
      ] <- position[2]
      
    }
    
  }
  
}

# ============================================================
# 34. DISPLAY LABEL POSITIONS
# ============================================================

cat("\n")
cat("====================================================\n")
cat("LABEL POSITIONS\n")
cat("====================================================\n\n")


print(
  
  label_data %>%
    
    select(
      
      Transect,
      
      Longitude,
      
      Latitude,
      
      LabelLongitude,
      
      LabelLatitude
      
    )
  
)


# ============================================================
# 34b. BUILD ONE Tx LABEL PER TRANSECT (ON LAND)
# ============================================================
#
# For each transect, pick the coast-side station (the one with
# the HIGHEST longitude -> closest to shore), then push the
# label further east by 'transect_label_land_offset' so it
# sits on land rather than on top of a sampling point.
#
# Any transect listed in 'manual_transect_label_positions' uses
# that position instead.
#
# ============================================================

transect_label_data <- label_data %>%
  
  group_by(TransectNumber) %>%
  
  slice_max(
    Longitude,
    n = 1,
    with_ties = FALSE
  ) %>%
  
  ungroup() %>%
  
  transmute(
    
    TransectNumber,
    
    AnchorLongitude = Longitude,
    
    AnchorLatitude = Latitude,
    
    LabelLongitude =
      Longitude +
      transect_label_land_offset,
    
    LabelLatitude =
      Latitude
    
  )


if (length(manual_transect_label_positions) > 0) {
  
  for (label_name in names(manual_transect_label_positions)) {
    
    position <- manual_transect_label_positions[[label_name]]
    
    matching_rows <- which(
      transect_label_data$TransectNumber == label_name
    )
    
    if (length(matching_rows) > 0) {
      
      transect_label_data$LabelLongitude[
        matching_rows
      ] <- position[1]
      
      transect_label_data$LabelLatitude[
        matching_rows
      ] <- position[2]
      
    }
    
  }
  
}


cat("\n")
cat("====================================================\n")
cat("TRANSECT (Tx) LABEL POSITIONS\n")
cat("====================================================\n\n")

print(transect_label_data)


# ============================================================
# 35. CREATE MAP
# ============================================================

cat("\nCreating map...\n")


map_plot <- ggplot()


# ============================================================
# 36. BATHYMETRY
# ============================================================

map_plot <- map_plot +
  
  geom_raster(
    
    data = bathymetry_df,
    
    aes(
      
      x = x,
      
      y = y,
      
      fill = PlotDepth
      
    )
    
  )


# ============================================================
# 37. BATHYMETRY COLOUR SCALE
# ============================================================

map_plot <- map_plot +
  
  scale_fill_gradientn(
    
    name = "Depth (m)",
    
    colours = c(
      
      "#E5F7FC",
      
      "#B8E5F2",
      
      "#78C6E0",
      
      "#3A9BC0",
      
      "#176B99",
      
      "#063B68"
      
    ),
    
    values = scales::rescale(
      
      c(
        
        0,
        
        500,
        
        1000,
        
        1500,
        
        2000,
        
        2500
        
      )
      
    ),
    
    limits = c(
      
      min_depth,
      
      max_depth
      
    ),
    
    breaks = c(
      
      0,
      
      500,
      
      1000,
      
      1500,
      
      2000,
      
      2500
      
    ),
    
    labels = c(
      
      "0",
      
      "500",
      
      "1000",
      
      "1500",
      
      "2000",
      
      "2500+"
      
    ),
    
    oob = scales::squish,
    
    na.value = "transparent",
    
    guide = "none"
    
  )


# ============================================================
# 38. CONTOUR LINES
# ============================================================

#map_plot <- map_plot +
  
  #geom_contour(
    
    #data = bathymetry_df,
    
    #aes(
      
     # x = x,
      
     # y = y,
      
    #  z = PlotDepth
      
   # ),
    
   # breaks = contour_levels,
    
    #colour = "grey30",
    
   # linewidth = contour_line_size,
    
   # alpha = 0.75,
    
   # na.rm = TRUE
    
  #)


# ============================================================
# 39. CONTOUR LABELS
# ============================================================

#map_plot <- map_plot +
  
  #metR::geom_text_contour(
    
    #data = bathymetry_df,
    
    #aes(
      
     # x = x,
      
      #y = y,
      
     # z = PlotDepth
      
   # ),
    
   # breaks = label_levels,
    
   # colour = "grey20",
    
   # size = contour_label_size,
    
   # stroke = 0.15,
    
    #check_overlap = TRUE,
    
    #skip = contour_label_skip,
    
    #na.rm = TRUE
    
  #)


# ============================================================
# 40. LAND
# ============================================================

map_plot <- map_plot +
  
  geom_sf(
    
    data = land,
    
    fill = "grey88",
    
    colour = "grey20",
    
    linewidth = 0.35
    
  )


# ============================================================
# 40b. SELECTED HIGHLIGHTED CONTOURS (10/20/30/50/100/200/500 m)
# ============================================================
#
# Drawn AFTER the land layer (unlike the regular grey contours
# in Section 38), so these specific depths stay fully visible
# even where GEBCO's raster coastline and the land polygon's
# vector coastline don't line up exactly near shore.
#
# Trade-off: in areas of coastline mismatch, a sliver of these
# lines may appear to run slightly onto land. If that looks
# wrong for your region, move this block to sit right after
# Section 38 instead (before Section 40) so land covers it
# again, like the other contours.
#
# This layer also supplies the "Depth (m)" legend on the right,
# replacing the bathymetry colour-bar legend (suppressed in
# Section 37 above).
#
# ============================================================

map_plot <- map_plot +
  
  geom_contour(
    
    data = bathymetry_df,
    
    aes(
      
      x = x,
      
      y = y,
      
      z = PlotDepth,
      
      colour = factor(after_stat(level))
      
    ),
    
    breaks = selected_contour_levels,
    
    linewidth = selected_contour_line_size,
    
    na.rm = TRUE
    
  ) +
  
  scale_colour_manual(
    
    name = "Depth (m)",
    
    values = selected_contour_colours,
    
    breaks = as.character(selected_contour_levels),
    
    labels = paste0(
      selected_contour_levels,
      " m"
    )
    
  )


# ============================================================
# 41. SAMPLING POINTS
# ============================================================

map_plot <- map_plot +
  
  geom_point(
    
    data = sampling_data,
    
    aes(
      
      x = Longitude,
      
      y = Latitude
      
    ),
    
    shape = 21,
    
    size = sampling_point_size,
    
    stroke = sampling_point_stroke,
    
    fill = "red",
    
    colour = "white"
    
  )


# ============================================================
# 42. STATION LABELS (Sx ONLY, AT EACH POINT)
# ============================================================
#
# Example labels drawn at each point:
#
# S1
# S2
# S3
#
# ============================================================

map_plot <- map_plot +
  
  geom_text_repel(
    
    data = label_data,
    
    aes(
      
      x = Longitude,
      
      y = Latitude,
      
      label = StationLabel
      
    ),
    
    nudge_x = label_data$LabelLongitude - label_data$Longitude,
    
    nudge_y = label_data$LabelLatitude - label_data$Latitude,
    
    size = station_label_size,
    
    fontface = station_label_fontface,
    
    colour = station_label_colour,
    
    box.padding = label_box_padding,
    
    point.padding = label_point_padding,
    
    min.segment.length = label_min_segment_length,
    
    segment.colour = "grey40",
    
    segment.size = 0.25,
    
    max.overlaps = label_max_overlaps,
    
    seed = label_repel_seed
    
  )


# ============================================================
# 42b. TRANSECT LABELS (Tx, ONE PER TRANSECT, ON LAND)
# ============================================================
#
# Example labels, one each, drawn on the land side:
#
# T4
# T5
# T6
#
# ============================================================

map_plot <- map_plot +
  
  geom_text_repel(
    
    data = transect_label_data,
    
    aes(
      
      x = AnchorLongitude,
      
      y = AnchorLatitude,
      
      label = TransectNumber
      
    ),
    
    nudge_x = transect_label_data$LabelLongitude -
      transect_label_data$AnchorLongitude,
    
    nudge_y = transect_label_data$LabelLatitude -
      transect_label_data$AnchorLatitude,
    
    size = transect_label_size,
    
    fontface = transect_label_fontface,
    
    colour = transect_label_colour,
    
    box.padding = label_box_padding,
    
    point.padding = label_point_padding,
    
    min.segment.length = label_min_segment_length,
    
    segment.colour = "grey20",
    
    segment.size = 0.3,
    
    max.overlaps = label_max_overlaps,
    
    seed = label_repel_seed
    
  )


# ============================================================
# 43. NORTH ARROW
# ============================================================

map_plot <- map_plot +
  
  annotation_north_arrow(
    
    location = north_arrow_location,
    
    which_north = "true",
    
    height = unit(
      1.0,
      "cm"
    ),
    
    width = unit(
      1.0,
      "cm"
    ),
    
    style =
      north_arrow_fancy_orienteering
    
  )


# ============================================================
# 44. SCALE BAR
# ============================================================

map_plot <- map_plot +
  
  annotation_scale(
    
    location = scale_bar_location,
    
    width_hint = scale_bar_width_hint,
    
    unit_category = "metric",
    
    text_cex = 0.8,
    
    line_width = 0.7,
    
    height = unit(
      0.15,
      "cm"
    )
    
  )


# ============================================================
# 45. MAP EXTENT
# ============================================================

map_plot <- map_plot +
  
  coord_sf(
    
    xlim = c(
      
      map_lon_min,
      
      map_lon_max
      
    ),
    
    ylim = c(
      
      map_lat_min,
      
      map_lat_max
      
    ),
    
    expand = FALSE
    
  )


# ============================================================
# 46. AXIS / TITLE
# ============================================================

map_plot <- map_plot +
  
  labs(
    
    title =
      "Sampling Location and Bathymetry Map",
    
    x =
      "Longitude (°E)",
    
    y =
      "Latitude (°N)"
    
  )


# ============================================================
# 47. THEME
# ============================================================

map_plot <- map_plot +
  
  theme_minimal(
    
    base_size = 12
    
  ) +
  
  theme(
    
    panel.grid.major =
      element_line(
        
        colour = "grey80",
        
        linewidth = 0.25
        
      ),
    
    panel.grid.minor =
      element_blank(),
    
    panel.border =
      element_rect(
        
        colour = "black",
        
        fill = NA,
        
        linewidth = 0.7
        
      ),
    
    axis.title =
      element_text(
        
        size = 12,
        
        face = "bold"
        
      ),
    
    axis.text =
      element_text(
        
        size = 10,
        
        colour = "black"
        
      ),
    
    plot.title =
      element_text(
        
        size = 15,
        
        face = "bold",
        
        hjust = 0.5
        
      ),
    
    legend.title =
      element_text(
        
        face = "bold"
        
      ),
    
    legend.text =
      element_text(
        
        size = 9
        
      ),
    
    legend.position =
      "right"
    
  )


# ============================================================
# 48. DISPLAY MAP BEFORE SAVING
# ============================================================

cat("\n")
cat("Displaying map...\n\n")


print(map_plot)


# ============================================================
# 49. SAVE PNG
# ============================================================

cat("\n")
cat("Saving PNG...\n")


tryCatch(
  
  {
    
    ggsave(
      
      filename = png_file,
      
      plot = map_plot,
      
      width = output_width,
      
      height = output_height,
      
      units = "in",
      
      dpi = output_dpi,
      
      bg = "white",
      
      device = "png"
      
    )
    
  },
  
  error = function(e) {
    
    stop(
      
      "\nPNG CREATION FAILED:\n",
      
      e$message,
      
      "\n"
      
    )
    
  }
  
)


# ============================================================
# 50. SAVE TIFF
# ============================================================

cat("Saving TIFF...\n")


tryCatch(
  
  {
    
    ggsave(
      
      filename = tiff_file,
      
      plot = map_plot,
      
      width = output_width,
      
      height = output_height,
      
      units = "in",
      
      dpi = output_dpi,
      
      compression = "lzw",
      
      bg = "white",
      
      device = "tiff"
      
    )
    
  },
  
  error = function(e) {
    
    stop(
      
      "\nTIFF CREATION FAILED:\n",
      
      e$message,
      
      "\n"
      
    )
    
  }
  
)


# ============================================================
# 51. VERIFY OUTPUT FILES
# ============================================================

cat("\n")
cat("====================================================\n")
cat("VERIFYING OUTPUT FILES\n")
cat("====================================================\n\n")


if (!file.exists(png_file)) {
  
  stop(
    "\nERROR: PNG file was not created.\n"
  )
  
}


if (!file.exists(tiff_file)) {
  
  stop(
    "\nERROR: TIFF file was not created.\n"
  )
  
}


png_size <- file.info(
  png_file
)$size


tiff_size <- file.info(
  tiff_file
)$size


if (png_size <= 0) {
  
  stop(
    "\nERROR: PNG file exists but has 0 bytes.\n"
  )
  
}


if (tiff_size <= 0) {
  
  stop(
    "\nERROR: TIFF file exists but has 0 bytes.\n"
  )
  
}


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

cat(
  "PNG size:",
  round(
    png_size / 1024,
    1
  ),
  "KB\n\n"
)


cat("TIFF:\n")
cat(tiff_file)
cat("\n")

cat(
  "TIFF size:",
  round(
    tiff_size / 1024,
    1
  ),
  "KB\n\n"
)


cat("Map extent:\n")

cat(
  
  map_lon_min,
  "°E to",
  map_lon_max,
  "°E\n"
  
)

cat(
  
  map_lat_min,
  "°N to",
  map_lat_max,
  "°N\n"
  
)


cat("\nNumber of sampling locations:")

cat(
  nrow(sampling_data)
)


cat("\n\nBathymetry colour range: 0–")

cat(
  max_depth
)

cat(
  " m+\n"
)


cat(
  "Contour interval:",
  contour_interval,
  "m\n"
)


cat("\n")
cat("Output folder:\n")
cat(output_folder)
cat("\n\n")


cat("====================================================\n")

