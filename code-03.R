
#                                                                              #
#              SANYO OCEAN MAPPING SUITE (SOMS) Version 1.0                    #                                                                              #          Publication Quality Oceanographic Surface Mapping in R              #
#                          Developed by: Sanyo                                 #
#
# PART 1 : INSTALL PACKAGES (Run only once)
# _______________________________SECTION 1

required_packages <- c(
  
  "terra",
  "sf",
  "ggplot2",
  "tidyterra",
  "readxl",
  "dplyr",
  "stringr",
  "ggrepel",
  "ggspatial",
  "rnaturalearth",
  "rnaturalearthdata",
  "viridis",
  "grid",
  "extrafont",
  "gstat",
  "geosphere",
  "metR",
  "R.utils"
)

missing_packages <-
  required_packages[
    !(required_packages %in% installed.packages()[,"Package"])
  ]

if(length(missing_packages)>0){
  
  install.packages(missing_packages)
  
}

#__________________________________SECTION 2 : LOAD LIBRARIES

library(terra)
library(sf)
library(ggplot2)
library(tidyterra)
library(readxl)
library(dplyr)
library(stringr)
library(ggrepel)
library(ggspatial)
library(rnaturalearth)
library(rnaturalearthdata)
library(viridis)
library(grid)
library(extrafont)
library(gstat)
library(sp)
library(geosphere)
library(metR)
library(R.utils)

# Load Windows Fonts (only if installed)

try(
  
  loadfonts(device="win", quiet=TRUE),
  
  silent=TRUE
  
)

#___________________________SECTION 3 : USER SETTINGS

#______________________________CHANGE ONLY THESE ####################

parameter_col <- 4

interpolation_method <- "IDW"

cat("Interpolation method:", interpolation_method, "\n")

colour_palette <- "turbo"

smooth_surface <- TRUE

smooth_sigma <- 1.2

clip_to_coast <- TRUE

mask_land <- TRUE

mask_depth <- FALSE

extrapolation_distance <- 50      # km

grid_resolution <- 500

save_output <- TRUE

#_____________________________-SECTION 4 : SELECT INPUT FILES

cat("\n")
cat("=============================================================\n")
cat("             SANYO OCEAN MAPPING SUITE (SOMS) V1.0\n")
cat("                 Developed by Sanyo\n")
cat("=============================================================\n\n")

cat("[1/2] Select Excel Data File...\n")
excel_file <- file.choose()

cat("[2/2] Select GEBCO Bathymetry File...\n")
gebco_file <- file.choose()

#_____________________________________SECTION 5 : READ EXCEL DATA

data <- read_excel(excel_file)

excel_name <- tools::file_path_sans_ext(basename(excel_file))
excel_dir  <- dirname(excel_file)  

# _________________________________________SECTION 5.1 : Check number of columns

if (parameter_col > ncol(data)) {
  
  cat("\n")
  cat("=============================================\n")
  cat("ERROR : PARAMETER COLUMN NOT FOUND\n")
  cat("=============================================\n")
  cat("This Excel file contains only", ncol(data), "columns.\n")
  cat("Requested parameter column :", parameter_col, "\n\n")
  
  readline("Press <Enter> to exit...")
  
  stop("Parameter column missing.", call. = FALSE)
}

# __________________________________SECTION 5.2 : Get selected column name

parameter_column <- names(data)[parameter_col]

#___________________________________SECTION 6 : COLLECTING PARAMETER INFORMATION

if (!is.na(parameter_column) && grepl("\\(", parameter_column)) {
  
  parameter_name <- trimws(gsub("\\s*\\(.*\\)", "", parameter_column))
  
  parameter_unit <- trimws(sub(".*\\((.*)\\).*", "\\1", parameter_column))
  
} else {
  
  parameter_name <- trimws(parameter_column)
  
  parameter_unit <- ""
  
}

cat("\n")
cat("---------------------------------------------\n")
cat("Selected Parameter\n")
cat("---------------------------------------------\n")
cat("Column Number :", parameter_col, "\n")
cat("Column Name   :", parameter_column, "\n")
cat("Parameter     :", parameter_name, "\n")
cat("Units         :", parameter_unit, "\n")
cat("---------------------------------------------\n\n")

# ____________________________________________________Rename selected parameter

data <- data %>%
  rename(Value = all_of(parameter_column))

# ______________________________SECTION 6.1 : Convert to numeric

data$Value <- suppressWarnings(as.numeric(data$Value))


# _____________________________SECTION 6.2 : Check if parameter column contains any numeric data

if (all(is.na(data$Value))) {
  
  cat("\n")
  cat("=============================================\n")
  cat("ERROR : PARAMETER COLUMN CONTAINS NO DATA\n")
  cat("=============================================\n")
  cat("Selected Parameter :", parameter_column, "\n")
  cat("The selected column contains no numeric values.\n\n")
  
  readline("Press <Enter> to exit...")
  
  stop("Parameter data missing.", call. = FALSE)
}

cat("\n========================================\n")
cat("DEBUG STAGE 1 : AFTER RENAME\n")
cat("========================================\n")

cat("Column names:\n")
print(names(data))

cat("\nClass of Value:\n")
print(class(data$Value))

cat("\nType of Value:\n")
print(typeof(data$Value))

cat("\nStructure:\n")
str(data$Value)

cat("\nFirst 10 Values:\n")
print(head(data$Value,10))

cat("\nAny NA? ", any(is.na(data$Value)), "\n")
cat("Any Inf? ", any(is.infinite(data$Value)), "\n")

# END OF PART 1

# PART 2 : CONVERT DDM TO DECIMAL DEGREES

# ______________________________________________________________SECTION 7

convert_ddm <- function(coord){
  
  sapply(coord, function(x){
    
    x <- trimws(as.character(x))
    
    hemi <- substr(x, nchar(x), nchar(x))
    
    x <- gsub("[NSEW]", "", x)
    
    x <- trimws(x)
    
    part <- strsplit(x, "°")[[1]]
    
    deg <- as.numeric(part[1])
    
    minute <- as.numeric(part[2])
    
    dd <- deg + minute/60
    
    if(hemi %in% c("S","W"))
      dd <- -dd
    
    return(dd)
    
  })
  
}

# __________________________________________SECTION 8 : CREATE DECIMAL COORDINATES

data$Lat_DD <- convert_ddm(data$Latitude)

data$Lon_DD <- convert_ddm(data$Longitude)

#_____________________________________________SECTION 9 : REMOVE INVALID RECORDS (coordinates only)

data <- data %>%
  filter(
    !is.na(Lon_DD),
    !is.na(Lat_DD)
  )

#____________________________________________SECTION 10 : QUICK DATA SUMMARY

cat("---------------------------------------------\n")
cat("Data Summary\n")
cat("---------------------------------------------\n")

cat("Number of Stations :", nrow(data), "\n")

cat("Minimum            :", min(data$Value, na.rm = TRUE), "\n")
cat("Maximum            :", max(data$Value, na.rm = TRUE), "\n")
cat("Mean               :", mean(data$Value, na.rm = TRUE), "\n")
cat("Median             :", median(data$Value, na.rm = TRUE), "\n")

cat("---------------------------------------------\n\n")

#___________________________________SECTION 11 : STUDY AREA

xmin <- 74.5

xmax <- 79.5

ymin <- 6.8

ymax <- 12.2

#________________________________SECTION 12 : INDIA COASTLINE

india <- ne_countries(
  country = "India",
  scale = "medium",
  returnclass = "sf"
  
)

# Keep geometry only
india <- st_geometry(india)

# Crop to study area
india <- st_crop(
  india,
  xmin = xmin,
  xmax = xmax,
  ymin = ymin,
  ymax = ymax
)

#_______________________________SECTION 13 : READ GEBCO BATHYMETRY

gebco <- rast(gebco_file)

gebco <- crop(
  
  gebco,
  
  ext(
    
    xmin,
    
    xmax,
    
    ymin,
    
    ymax
    
  )
  
)

bath_df <- as.data.frame(
  
  gebco,
  
  xy = TRUE,
  
  na.rm = TRUE
  
)

names(bath_df)[3] <- "depth"

#____________________________SECTION 14 : TRANSECT LABELS

label_data <- data %>%
  
  mutate(
    
    Transect = str_extract(
      
      `Station Name`,
      
      "T\\d+"
      
    ),
    
    StationNo = as.numeric(
      
      str_extract(
        
        `Station Name`,
        
        "(?<=S)\\d+"
        
      )
      
    ),
    
    Label = recode(
      
      Transect,
      
      "T4"="Cap",
      
      "T5"="Col",
      
      "T6"="Viz",
      
      "T7"="Kol",
      
      "T8"="Kar",
      
      "T9"="Ala",
      
      "T10"="Art",
      
      "T11"="Koc",
      
      "T12"="Mun",
      
      "T13"="Koz"
      
    )
    
  ) %>%
  
  group_by(Transect) %>%
  
  slice_min(
    
    StationNo,
    
    n = 1,
    
    with_ties = FALSE
    
  ) %>%
  
  ungroup()

#___________________SECTION 15 : LABEL POSITIONS

label_data <- label_data %>%
  
  mutate(
    
    label_lon = Lon_DD + 0.20,
    
    label_lat = Lat_DD + 0.10
    
  )

#______________________________ SECTION 16 : Manual adjustments

label_data$label_lon[label_data$Label=="Koc"] <-
  label_data$label_lon[label_data$Label=="Koc"] + 0.25

label_data$label_lon[label_data$Label=="Mun"] <-
  label_data$label_lon[label_data$Label=="Mun"] + 0.35

label_data$label_lon[label_data$Label=="Art"] <-
  label_data$label_lon[label_data$Label=="Art"] + 0.18

label_data$label_lon[label_data$Label=="Koz"] <-
  label_data$label_lon[label_data$Label=="Koz"] + 0.20

#________________________________________SECTION 17 : PREVIEW DATA

cat("\nFirst Five Stations\n")

head(data)

cat("\nBathymetry Summary\n")

summary(bath_df$depth)

# END OF PART 2

# PART 3

#_________________________SECTION 18 : CREATE INTERPOLATION INPUT

xyz <- cbind(
  
  data$Lon_DD,
  
  data$Lat_DD,
  
  data$Value
  
)

#_________________________SECTION 18.1 :Observed data range

obs_min <- min(data$Value, na.rm = TRUE)
obs_max <- max(data$Value, na.rm = TRUE)

#_________________________SECTION 19 : INTERPOLATION

cat("---------------------------------------------\n")
cat("Interpolation Method :", interpolation_method, "\n")
cat("---------------------------------------------\n\n")

#_________________________SECTION 20 : IDW INTERPOLATION (true Inverse Distance Weighting)

if(interpolation_method=="IDW"){
  
  library(gstat)
  library(sp)
  
  # Use only points with actual values for interpolation input
  data_valid <- data[!is.na(data$Value), ]
  
  data_sp <- data_valid
  coordinates(data_sp) <- ~Lon_DD+Lat_DD
  
  grid_pts <- expand.grid(
    Lon_DD = seq(xmin, xmax, length = grid_resolution),
    Lat_DD = seq(ymin, ymax, length = grid_resolution)
  )
  coordinates(grid_pts) <- ~Lon_DD+Lat_DD
  gridded(grid_pts) <- TRUE
  
  idw_result <- idw(
    formula = Value ~ 1,
    locations = data_sp,
    newdata = grid_pts,
    idp = 2          # power parameter -- 2 is standard IDW; raise for sharper falloff
  )
  
  grid <- as.data.frame(idw_result)
  grid <- grid[, c("Lon_DD", "Lat_DD", "var1.pred")]
  names(grid) <- c("lon", "lat", "Value")
  
}

#_________________________________SECTION 24 : CHECK GRID

cat("\nColumns in grid:\n")
print(names(grid))

cat("\nStructure of grid:\n")
str(grid)

if (!"Value" %in% names(grid)) {
  stop("ERROR: 'Value' column was never created.")
}

#__________________________________SECTION 25 : REMOVE EMPTY CELLS

grid <- grid %>% filter(!is.na(Value))

#_________________________________SECTION 26 : OPTIONAL GAUSSIAN SMOOTHING

if(smooth_surface){
  raster_grid <- rast(grid[, c("lon","lat","Value")], type="xyz")
  raster_grid <- focal(
    raster_grid,
    w = matrix(c(1,2,1,2,4,2,1,2,1), 3, 3),
    fun = mean,
    na.policy = "omit"
  )
  grid <- as.data.frame(raster_grid, xy=TRUE, na.rm=FALSE)
  names(grid) <- c("lon","lat","Value")
}

#_________________________________SECTION 27 : CLAMP INTERPOLATED VALUES TO OBSERVED RANGE

grid$Value <- pmin(pmax(grid$Value, obs_min), obs_max)

#_________________________________SECTION 28-29 : CONVERT TO RASTER

interp_raster <- rast(grid[, c("lon","lat","Value")], type = "xyz")
crs(interp_raster) <- "EPSG:4326"

#_________________________________SECTION 31-32 : India coastline, matching CRS

india_vect <- vect(india)
india_vect <- project(india_vect, crs(interp_raster))

#_________________________________SECTION 33 : Remove interpolation over land

interp_raster <- mask(interp_raster, india_vect, inverse = TRUE)

#_________________________________SECTION 36 : Convert back to dataframe (FINAL grid, only lon/lat/Value here)

grid <- as.data.frame(interp_raster, xy = TRUE, na.rm = FALSE)
names(grid) <- c("lon", "lat", "Value")
cat(">>> After land mask, NA count:", sum(is.na(grid$Value)), "out of", nrow(grid), "\n")

#__________________________________SECTION 37 : DISTANCE-BASED FADES (edge-only, full saturation elsewhere)

haversine_km <- function(lon1, lat1, lon2, lat2) {
  R <- 6371
  lon1 <- lon1 * pi/180; lat1 <- lat1 * pi/180
  lon2 <- lon2 * pi/180; lat2 <- lat2 * pi/180
  dlon <- lon2 - lon1
  dlat <- lat2 - lat1
  a <- sin(dlat/2)^2 + cos(lat1) * cos(lat2) * sin(dlon/2)^2
  cc <- 2 * asin(pmin(1, sqrt(a)))
  R * cc
}

# --- Fade 1: extrapolation edge -- full opacity until near the 25km boundary ---

fade_zone_km <-25   # width of the fade band, right at the edge

obs_pts <- data[!is.na(data$Value), c("Lon_DD","Lat_DD")]
grid$dist_to_nearest_obs <- sapply(1:nrow(grid), function(i) {
  min(haversine_km(grid$lon[i], grid$lat[i], obs_pts$Lon_DD, obs_pts$Lat_DD))
})
grid$Value[grid$dist_to_nearest_obs > extrapolation_distance] <- NA

grid$alpha_fade <- 1
edge_zone <- grid$dist_to_nearest_obs > (extrapolation_distance - fade_zone_km)
grid$alpha_fade[edge_zone] <- (extrapolation_distance - grid$dist_to_nearest_obs[edge_zone]) / fade_zone_km
grid$alpha_fade[grid$alpha_fade < 0] <- 0
grid$alpha_fade[grid$alpha_fade > 1] <- 1
grid$alpha_fade[is.na(grid$alpha_fade)] <- 0

#__________________________________SECTION 37b : IDW-BASED PRESENCE SURFACE (replaces fixed-radius blank fade)

# Assign presence score to every station: 1 = has a real reading, 0 = blank cell
presence_data <- data
presence_data$presence <- ifelse(is.na(presence_data$Value), 0, 1)

presence_sp <- presence_data
coordinates(presence_sp) <- ~Lon_DD+Lat_DD

grid_pts_presence <- expand.grid(
  Lon_DD = seq(xmin, xmax, length = grid_resolution),
  Lat_DD = seq(ymin, ymax, length = grid_resolution)
)
coordinates(grid_pts_presence) <- ~Lon_DD+Lat_DD
gridded(grid_pts_presence) <- TRUE

presence_idw <- idw(
  formula = presence ~ 1,
  locations = presence_sp,
  newdata = grid_pts_presence,
  idp = 5
)

presence_grid <- as.data.frame(presence_idw)
presence_grid <- presence_grid[, c("Lon_DD", "Lat_DD", "var1.pred")]
names(presence_grid) <- c("lon", "lat", "alpha_blank")

# Clamp to valid alpha range [0,1] -- IDW can slightly overshoot
presence_grid$alpha_blank <- pmin(1, pmax(0, presence_grid$alpha_blank))

# Merge onto grid by matching lon/lat (grid_pts_presence uses the same seq() as your main grid,
# so coordinates should align exactly -- but round defensively in case of floating-point drift)
grid$lon_r <- round(grid$lon, 6)
grid$lat_r <- round(grid$lat, 6)
presence_grid$lon_r <- round(presence_grid$lon, 6)
presence_grid$lat_r <- round(presence_grid$lat, 6)

grid <- merge(
  grid, presence_grid[, c("lon_r","lat_r","alpha_blank")],
  by = c("lon_r","lat_r"), all.x = TRUE, sort = FALSE
)
grid$lon_r <- NULL
grid$lat_r <- NULL

grid$alpha_blank <- (grid$alpha_blank - min(grid$alpha_blank, na.rm=TRUE)) / 
  (max(grid$alpha_blank, na.rm=TRUE) - min(grid$alpha_blank, na.rm=TRUE))

# try 0.3-0.6 -- lower number = more saturation overall
grid$alpha_blank <- grid$alpha_blank ^ 0.4   

grid$alpha_final <- grid$alpha_fade * grid$alpha_blank
grid$alpha_final[is.na(grid$Value)] <- 0

cat(">>> Range of IDW-based alpha_blank:", range(grid$alpha_blank, na.rm=TRUE), "\n")
cat(">>> Rows at full opacity (alpha_final == 1):", sum(grid$alpha_final == 1, na.rm=TRUE), "\n")
cat(">>> Rows with alpha_final == 0 (fully transparent):", sum(grid$alpha_final == 0, na.rm=TRUE), "\n")

#_________________________________SECTION 37.1:INTERPOLATION SUMMARY

zmin <- obs_min
zmax <- obs_max

cat("---------------------------------------------\n")
cat("Interpolation Finished\n")
cat("---------------------------------------------\n")

cat("Observed Minimum :", obs_min, "\n")
cat("Observed Maximum :", obs_max, "\n\n")

cat("Interpolated Minimum :", min(grid$Value), "\n")
cat("Interpolated Maximum :", max(grid$Value), "\n")
cat("Mean :", mean(grid$Value), "\n")
cat("Median :", median(grid$Value), "\n")

cat("---------------------------------------------\n\n")

# END OF PART 3

# PART 4

#_________________________________SECTION 38:LEGEND TITLE

if (is.na(parameter_unit) || parameter_unit == "") {
  
  legend_title <- parameter_name
  
} else {
  
  legend_title <- paste0(parameter_name, "\n(", parameter_unit, ")")
  
}

#_________________________________SECTION 39:CREATE PUBLICATION QUALITY MAP

contour_breaks <- pretty(c(obs_min, obs_max), n = 5)

p <- ggplot() +
  
  #_________________________________SECTION 40 : Interpolated Surface
  
  geom_tile(
    data = grid,
    aes(x = lon, y = lat, fill = Value, alpha = alpha_final),
    width  = diff(sort(unique(grid$lon)))[1],
    height = diff(sort(unique(grid$lat)))[1]
  ) +
  
  #_________________________________SECTION 41 : Parameter Contours
  
  geom_contour(
    data = grid,
    aes(x = lon, y = lat, z = Value),
    colour = "black",
    linewidth = 0.5,
    breaks = contour_breaks
  ) +
  
  geom_text_contour(
    data = grid,
    aes(x = lon, y = lat, z = Value),
    breaks = contour_breaks,
    size = 4,
    fontface = "bold",
    colour = "black",
    stroke = 0.2,
    stroke.colour = "white",
    skip = 1              # keeps crowding down; raise to 3 if still too busy
  ) +
  
  #_________________________________SECTION 42 : Bathymetry
  
  geom_contour(
    data = bath_df,
    aes(x = x, y = y, z = depth),
    breaks = c(-50,-100,-200,-500,-1000,-2000,-3000),
    colour = "grey20",
    linewidth = 0.30,
    linetype = "dashed"
  ) +
  
  # ... rest of your layers continue here (coastline, stations, labels, scales, theme) ...
  
  #_________________________________SECTION 43 : Coastline
  
  geom_sf(
    data = india,
    fill = "gray90",
    colour = "black",
    linewidth = 0.50
  ) +
  
  #_________________________________SECTION 44 : Station Locations
  
  geom_point(
    data = data[!is.na(data$Value), ],
    aes(x = Lon_DD, y = Lat_DD),
    shape = 21,
    size = 2.8,
    fill = "white",
    colour = "black",
    stroke = 1
  ) +
  
  geom_point(
    data = data[is.na(data$Value), ],
    aes(x = Lon_DD, y = Lat_DD),
    shape = 13,          # asterisk/star shape
    size = 2.8,
    colour = "red",
    stroke = 1
  ) +
  
  #_________________________________SECTION 44b : STATION MARKER LEGEND
  
  geom_point(
    data = data.frame(x = NA, y = NA, type = c("Available", "Missing")),
    aes(x = x, y = y, shape = type, colour = type),
    size = 1,
    stroke = 1.2,
    na.rm = TRUE
  ) +
  
  scale_shape_manual(
    name = "Data Status",
    values = c("Available" = 21, "Missing" = 13)
  ) +
  
  scale_colour_manual(
    name = "Data Status",
    values = c("Available" = "black", "Missing" = "red")
  ) +
  
  #_________________________________SECTION 45 : Transect Labels
  
  geom_text(
    data = label_data,
    aes(
      x = label_lon,
      y = label_lat,
      label = Label
    ),
    family = "serif",
    fontface = "bold",
    size = 4
  ) +
  
  #_________________________________SECTION 46 : Colour Scale
  
  scale_fill_viridis_c(
    option = "turbo",
    direction = 1,
    limits = c(obs_min, obs_max),
    oob = scales::squish,
    na.value = "transparent",   # <-- add this line
    name = legend_title,
    guide = "none"          # <-- hides the colour bar/legend, but colour mapping still fully applies, add one ","
  ) +
  scale_alpha_continuous(range = c(0,1), guide = "none") +
  
  #_________________________________SECTION 47 : Scale Bar
  
  annotation_scale(
    location = "bl",
    width_hint = 0.35,
    text_cex = 1.3,        # bigger text (default is ~0.7-0.8)
    line_width = 1.5,       # thicker bar line
    height = unit(0.25, "cm")  # slightly taller bar
  ) +
  
  #_________________________________SECTION 48 : North Arrow
  
  annotation_north_arrow(
    location = "tr",
    which_north = "true",
    pad_x = unit(0.7, "cm"),   # nudge left/right -- increase to move further from edge
    pad_y = unit(0.6, "cm"),   # nudge up/down -- increase to move further from edge
    style = north_arrow_fancy_orienteering(
      fill = c("black", "white"),   # two-tone fill -- both set to red here
      text_col = "red"
    )
  ) +
  
  #_________________________________SECTION 49 : Study Area
  
  coord_sf(
    xlim = c(xmin, xmax),
    ylim = c(ymin, ymax),
    expand = FALSE
  ) +
  
  #_________________________________SECTION 50 : Axis Labels
  
  labs(
    x = NULL,
    y = NULL,
    title = NULL
  )+
  
  #_________________________________SECTION 51 : Theme
  
  theme_bw() +
  
  theme(
    
    panel.grid = element_blank(),
    
    panel.border = element_rect(
      colour = "black",
      fill = NA,
      linewidth = 1.5
    ),
    
    panel.background = element_rect(fill = "white", colour = NA),
    plot.background  = element_rect(fill = "white", colour = NA),
    
    legend.position = c(0.02, 0.05), # ( small value = closer to left, decrease to bring it closer down toward the scale bar)
    legend.justification = c(0, 0),
    legend.background = element_rect(fill = "white", colour = "white", linewidth = 0.3),
    legend.key = element_rect(fill = "white"),
    
    axis.title = element_blank(),
    
    axis.ticks = element_line(
      colour = "black",
      linewidth = 1.2
    ),
    
    axis.ticks.length = unit(0.2, "cm"),
    
    axis.text = element_text(
      family = "sans",
      face = "bold",
      size = 18,
      colour = "black"
    ),
    
    legend.title = element_text(
      family = "serif",
      face = "bold",
      size = 14
    ),
    
    legend.text = element_text(
      family = "serif",
      size = 11
    ),
    
  )
    
    plot.title = element_text(
      family = "serif",
      face = "bold",
      hjust = 0.5,
      size = 18
    )

#_________________________________SECTION 52 : SAVE FIGURE

output_file <- file.path(
  excel_dir,
  paste0(excel_name, " - ", parameter_name, ".tiff")
)

ggsave(
  filename = output_file,
  plot = p,
  width = 8,
  height = 7,
  dpi = 200,
  compression = "lzw",
  bg = "white"
)

cat("\n")
cat("Map exported successfully.\n")
cat("File :", output_file, "\n")

#_________________________________SECTION 53 : DISPLAY MAP

print(p)


