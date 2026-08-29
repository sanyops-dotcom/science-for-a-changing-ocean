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
  "metR"
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

map_lon_min <- 75
map_lon_max <- 79

map_lat_min <- 7
map_lat_max <- 12


# ============================================================
# 4. BATHYMETRY SETTINGS
# ============================================================

min_depth <- 0

max_depth <- 2000


# ============================================================
# 5. CONTOUR SETTINGS
# ============================================================

contour_interval <- 200

contour_label_interval <- 400

contour_line_size <- 0.30

contour_label_size <- 3.0


# ============================================================
# 6. SAMPLING POINT SETTINGS
# ============================================================

sampling_point_size <- 3.5

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
# 9. LABEL APPEARANCE
# ============================================================

transect_label_size <- 3.8

transect_label_fontface <- "bold"

transect_label_colour <- "black"


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

output_width <- 10

output_height <- 8

output_dpi <- 600


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
    
    Latitude = as.numeric(
      .data[[latitude_column]]
    ),
    
    Longitude = as.numeric(
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

contour_levels <- seq(
  
  contour_interval,
  
  max_depth,
  
  by = contour_interval
  
)


label_levels <- seq(
  
  contour_label_interval,
  
  max_depth,
  
  by = contour_label_interval
  
)


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

label_data <- sampling_data %>%
  
  mutate(
    
    LabelLongitude =
      Longitude +
      default_label_x_offset,
    
    LabelLatitude =
      Latitude +
      default_label_y_offset
    
  )


# ============================================================
# 33. APPLY MANUAL LABEL POSITIONS
# ============================================================

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
        
        250,
        
        500,
        
        1000,
        
        1500,
        
        2000
        
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
      
      2000
      
    ),
    
    labels = c(
      
      "0",
      
      "500",
      
      "1000",
      
      "1500",
      
      "2000+"
      
    ),
    
    oob = scales::squish,
    
    na.value = "transparent"
    
  )


# ============================================================
# 38. CONTOUR LINES
# ============================================================

map_plot <- map_plot +
  
  geom_contour(
    
    data = bathymetry_df,
    
    aes(
      
      x = x,
      
      y = y,
      
      z = PlotDepth
      
    ),
    
    breaks = contour_levels,
    
    colour = "grey30",
    
    linewidth = contour_line_size,
    
    alpha = 0.75,
    
    na.rm = TRUE
    
  )


# ============================================================
# 39. CONTOUR LABELS
# ============================================================

map_plot <- map_plot +
  
  metR::geom_text_contour(
    
    data = bathymetry_df,
    
    aes(
      
      x = x,
      
      y = y,
      
      z = PlotDepth
      
    ),
    
    breaks = label_levels,
    
    colour = "grey20",
    
    size = contour_label_size,
    
    stroke = 0.15,
    
    check_overlap = TRUE,
    
    skip = 1,
    
    na.rm = TRUE
    
  )


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
    
    fill = "white",
    
    colour = "black"
    
  )


# ============================================================
# 42. TRANSECT / STATION LABELS
# ============================================================
#
# Example labels:
#
# T1 S1
# T1 S2
# T2 S1
# T4 S2
#
# ============================================================

map_plot <- map_plot +
  
  geom_text(
    
    data = label_data,
    
    aes(
      
      x = LabelLongitude,
      
      y = LabelLatitude,
      
      label = Transect
      
    ),
    
    size = transect_label_size,
    
    fontface = transect_label_fontface,
    
    colour = transect_label_colour,
    
    hjust = 0,
    
    vjust = 0.5
    
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