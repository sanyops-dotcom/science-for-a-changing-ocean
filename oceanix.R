# ============================================================
# OCEANIX
# "Science for a Changing Ocean"
# ============================================================
#
# A page-by-page (wizard) Shiny app covering four plot types:
#
#   1. Section map     (ggplot, depth vs station/transect, IDW)
#   2. Line profile     (base R, depth-vs-parameter lines)
#   3. Surface map      (ggplot, IDW of a parameter over real
#                         geography, coastline-masked)
#   4. Station location  (ggplot, sampling points + bathymetry
#                         on a real map, no parameter)
#
# Navigation: Step 1 Plot type -> Step 2 Sub-mode -> Step 3
# Upload -> Step 4 Columns -> Step 5 Style -> Step 6 Plot.
# Only one step is visible at a time; Back/Next move between
# them. The OCEANIX header stays fixed at the top throughout.
#
# NOTE ON SCOPE: the two map types are adapted from much larger
# hand-tuned scripts (Sampling_Location_map.R, code-03.R). To
# keep this buildable and maintainable, a few of their most
# elaborate features were simplified - see the message alongside
# this file for exactly what was left out and why.
# ============================================================

required_packages <- c(
  "shiny", "shinyjs", "readxl", "dplyr", "stringr",
  "ggplot2", "gstat", "sp", "scales",
  "terra", "sf", "rnaturalearth", "rnaturalearthdata",
  "ggrepel", "ggspatial"
)

for (pkg in required_packages) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    install.packages(pkg)
  }
}

library(shiny)
library(shinyjs)
library(readxl)
library(dplyr)
library(stringr)
library(ggplot2)
library(gstat)
library(sp)
library(scales)
library(terra)
library(sf)
library(rnaturalearth)
library(rnaturalearthdata)
library(ggrepel)
library(ggspatial)

`%||%` <- function(a, b) if (is.null(a) || (length(a) == 1 && is.na(a))) b else a


# ------------------------------------------------------------
# BRANDING
# ------------------------------------------------------------

APP_NAME <- "OCEANIX"
APP_TAGLINE <- "Science for a Changing Ocean"


# ------------------------------------------------------------
# SHARED HELPERS (numbers, depth axes, section theme)
# ------------------------------------------------------------

numeric_sort <- function(x) {
  x[order(as.numeric(str_extract(x, "[0-9]+")))]
}

standard_depths <- c(0, 5, 10, 20, 30, 50, 75, 100, 200, 500, 750, 1000, 1500, 2000)

depth_axis_breaks <- function(min_depth, max_depth) {
  breaks <- standard_depths[standard_depths >= min_depth & standard_depths <= max_depth]
  if (length(breaks) < 2) breaks <- pretty(c(min_depth, max_depth), n = 8)
  breaks
}

section_theme <- function() {
  theme_bw() +
    theme(
      panel.grid = element_blank(),
      axis.text.x = element_text(size = 11, hjust = 0.5),
      axis.text.y = element_text(size = 10),
      axis.title.y = element_text(size = 11),
      legend.position = "right",
      legend.title = element_text(size = 10),
      legend.text = element_text(size = 9),
      plot.margin = margin(10, 15, 10, 10)
    )
}

geo_theme <- function() {
  theme_bw(base_size = 12) +
    theme(
      panel.grid.major = element_line(colour = "grey85", linewidth = 0.25),
      panel.grid.minor = element_blank(),
      panel.border = element_rect(colour = "black", fill = NA, linewidth = 0.7),
      axis.title = element_text(size = 11, face = "bold"),
      axis.text = element_text(size = 9, colour = "black"),
      plot.title = element_text(size = 14, face = "bold", hjust = 0.5),
      legend.title = element_text(face = "bold"),
      legend.text = element_text(size = 9),
      legend.position = "right"
    )
}

idw_palette <- c(
  "#313695", "#4575B4", "#74ADD1", "#ABD9E9", "#E0F3F8",
  "#FFFFBF", "#FEE090", "#FDAE61", "#F46D43", "#D73027", "#A50026"
)

profile_colours <- c(
  "red", "green", "blue", "orange", "pink",
  "brown", "violet", "skyblue", "yellow", "grey"
)

label_gap_in <- 0.12


# ------------------------------------------------------------
# COLOUR CHOICES (station markers + IDW colour packages)
# ------------------------------------------------------------

marker_colour_choices <- c(
  "Red" = "#E31A1C", "Orange" = "#FF7F00", "Yellow" = "#E6C200",
  "Green" = "#33A02C", "Blue" = "#1F78B4", "Indigo" = "#4B0082",
  "Violet" = "#6A3D9A", "Black" = "#000000", "White" = "#FFFFFF"
)

palette_choices <- c(
  "ODV Blue-Red (default)" = "default",
  "Viridis" = "viridis",
  "Turbo" = "turbo",
  "Plasma" = "plasma",
  "Magma" = "magma",
  "Cividis" = "cividis",
  "Spectral" = "spectral"
)

get_fill_scale <- function(palette_key, limits, legend_name, show_legend) {
  guide <- if (isTRUE(show_legend)) "colourbar" else "none"
  key <- palette_key %||% "default"
  if (key == "viridis") {
    scale_fill_viridis_c(option = "viridis", limits = limits, oob = scales::squish,
                          na.value = "transparent", name = legend_name, guide = guide)
  } else if (key == "turbo") {
    scale_fill_viridis_c(option = "turbo", limits = limits, oob = scales::squish,
                          na.value = "transparent", name = legend_name, guide = guide)
  } else if (key == "plasma") {
    scale_fill_viridis_c(option = "plasma", limits = limits, oob = scales::squish,
                          na.value = "transparent", name = legend_name, guide = guide)
  } else if (key == "magma") {
    scale_fill_viridis_c(option = "magma", limits = limits, oob = scales::squish,
                          na.value = "transparent", name = legend_name, guide = guide)
  } else if (key == "cividis") {
    scale_fill_viridis_c(option = "cividis", limits = limits, oob = scales::squish,
                          na.value = "transparent", name = legend_name, guide = guide)
  } else if (key == "spectral") {
    scale_fill_distiller(palette = "Spectral", direction = -1, limits = limits,
                          oob = scales::squish, na.value = "transparent",
                          name = legend_name, guide = guide)
  } else {
    scale_fill_gradientn(colours = idw_palette, limits = limits, oob = scales::squish,
                          na.value = "transparent", name = legend_name, guide = guide)
  }
}


# ------------------------------------------------------------
# WATERMARK — drawn last, on top of the finished plot, so it
# works identically for ggplot maps/sections AND base-R line
# profiles without disturbing the plot itself.
# ------------------------------------------------------------

draw_watermark <- function() {
  grid::grid.text(
    APP_TAGLINE,
    x = grid::unit(0.995, "npc"), y = grid::unit(0.5, "npc"),
    rot = 90,
    gp = grid::gpar(col = grDevices::adjustcolor("grey35", alpha.f = 0.55),
                     fontsize = 9, fontface = "italic")
  )
}


# ------------------------------------------------------------
# COORDINATE PARSING (handles both plain decimals AND
# degrees+decimal-minutes like 8°3.342N)
# ------------------------------------------------------------

dmm_to_decimal <- function(x) {
  m <- regmatches(x, regexec("([0-9]+)[\u00b0\u00ba]([0-9.]+)([NSEWnsew])", x))
  sapply(m, function(part) {
    if (length(part) != 4) return(NA_real_)
    deg <- as.numeric(part[2]); minute <- as.numeric(part[3]); dir <- toupper(part[4])
    dec <- deg + minute / 60
    if (dir %in% c("S", "W")) dec <- -dec
    dec
  })
}

parse_coordinate <- function(x) {
  x_chr <- trimws(as.character(x))
  dmm_val <- suppressWarnings(dmm_to_decimal(x_chr))
  numeric_val <- suppressWarnings(as.numeric(x_chr))
  ifelse(!is.na(dmm_val), dmm_val, numeric_val)
}


# --------------------------------------------------------------
# Two-panel base-R line profile engine (from line-plot.R).
# Draws stacked colour-coded X-axes on top + a depth profile
# below. show_legend controls whether the side legend is drawn.
# --------------------------------------------------------------
draw_two_panel_profile <- function(
    item_names, item_data, max_depth,
    plot_title, legend_title, label_gap_in = 0.12, show_legend = TRUE
) {

  n_items <- length(item_names)
  dev_width_in <- par("din")[1]

  old_cex <- par("cex"); old_font <- par("font")
  par(cex = 0.88, font = 2)
  max_label_in <- max(strwidth(item_names, units = "inches"))
  par(cex = old_cex, font = old_font)

  edge_pad_in <- 0.08
  left_gutter_in <- max_label_in + label_gap_in + edge_pad_in
  panel_left_frac <- min(max(left_gutter_in / dev_width_in, 0.15), 0.55)

  old_cex <- par("cex")
  par(cex = 0.85)
  max_legend_in <- max(strwidth(item_names, units = "inches"))
  par(cex = old_cex)

  legend_swatch_in <- if (show_legend) 0.45 else 0
  right_gutter_in <- legend_swatch_in + (if (show_legend) max_legend_in * 1.12 else 0) + edge_pad_in + 0.15
  panel_right_frac <- max(min(1 - right_gutter_in / dev_width_in, 0.85), 0.55)

  plot_width_in <- dev_width_in * (panel_right_frac - panel_left_frac)
  data_units_per_inch <- 1 / plot_width_in
  label_gap_data <- label_gap_in * data_units_per_inch

  layout(matrix(c(1, 2), nrow = 2, byrow = TRUE), heights = c(0.34, 0.66))

  profile_left <- 0
  profile_right <- 1
  profile_width <- profile_right - profile_left

  # ---- top panel: stacked axes ----
  par(mar = c(1, 1, 2, 1))
  plot.new()
  plt <- par("plt")
  par(plt = c(panel_left_frac, panel_right_frac, plt[3], plt[4]))
  par(new = TRUE)

  plot(NA, NA, type = "n", xlim = c(0, 1), ylim = c(0, n_items + 1),
       axes = FALSE, xlab = "", ylab = "", xaxs = "i", yaxs = "i")

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

    y_position <- n_items - i + 1

    segments(x0 = profile_left, y0 = y_position, x1 = profile_right, y1 = y_position,
             col = current_colour, lwd = 2)

    ticks <- pretty(c(current_min, current_max))
    ticks <- ticks[ticks >= current_min & ticks <= current_max]
    if (length(ticks) < 2) ticks <- seq(current_min, current_max, length.out = 5)

    tick_x <- profile_left + ((ticks - current_min) / (current_max - current_min)) * profile_width

    segments(x0 = tick_x, y0 = y_position, x1 = tick_x, y1 = y_position - 0.10,
             col = current_colour, lwd = 1.5)

    text(x = tick_x, y = y_position - 0.27,
         labels = format(ticks, trim = TRUE, scientific = FALSE),
         col = current_colour, cex = 0.8, xpd = NA)

    text(x = profile_left - label_gap_data, y = y_position, labels = item_name,
         col = current_colour, font = 2, pos = 2, cex = 0.88, xpd = NA)
  }

  # ---- bottom panel: profile ----
  par(mar = c(5, 1, 2, 1))
  plot.new()
  plt <- par("plt")
  par(plt = c(panel_left_frac, panel_right_frac, plt[3], plt[4]))
  par(new = TRUE)

  plot(NA, NA, type = "n", xlim = c(0, 1), ylim = c(max_depth, 0),
       axes = FALSE, xlab = "", ylab = "", xaxs = "i", yaxs = "i")

  depth_ticks <- pretty(c(0, max_depth))
  depth_ticks <- depth_ticks[depth_ticks >= 0 & depth_ticks <= max_depth]

  axis(side = 2, at = depth_ticks, labels = paste0(depth_ticks, " m"),
       las = 1, col = "black", col.axis = "black", lwd = 1.5)

  abline(h = depth_ticks, col = "grey85", lty = 3)
  mtext("Depth (m)", side = 2, line = 3.3, font = 2)

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

  segments(x0 = profile_left, y0 = max_depth, x1 = profile_right, y1 = max_depth,
           col = "black", lwd = 1.5)

  if (show_legend) {
    legend(x = 1.03, y = 0, yjust = 1, legend = item_names,
           col = profile_colours[seq_along(item_names)], lwd = 3, bty = "n",
           title = legend_title, xpd = NA, cex = 0.85)
  }

  mtext(plot_title, side = 3, line = 0.2, font = 2, cex = 1.2)
}


# ------------------------------------------------------------
# UI
# ------------------------------------------------------------

ui <- fluidPage(
  useShinyjs(),

  tags$style(HTML("
    body { background: #f4f7f9; }
    .app-header { text-align: center; padding: 18px 10px 10px 10px; }
    .app-title {
      font-size: 34px; font-weight: 800; letter-spacing: 2px;
      color: #063B68; margin: 0;
    }
    .app-tagline {
      font-size: 14px; font-style: italic; color: #3A9BC0;
      margin-top: 2px; letter-spacing: 0.5px;
    }
    .step-indicator {
      text-align: center; font-size: 13px; color: #888;
      margin-bottom: 14px; text-transform: uppercase; letter-spacing: 1px;
    }
    .wizard-card {
      background: white; border-radius: 10px; padding: 26px 32px;
      max-width: 780px; margin: 0 auto 18px auto;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08);
      min-height: 320px;
    }
    .wizard-card-wide { max-width: 1100px; }
    .nav-row {
      max-width: 780px; margin: 0 auto 30px auto;
      display: flex; justify-content: space-between;
    }
    .nav-row-wide { max-width: 1100px; }
    .choice-tile {
      border: 2px solid #ddd; border-radius: 8px; padding: 14px 16px;
      margin-bottom: 10px; cursor: pointer;
    }
    .section-heading { font-weight: 700; color: #063B68; margin-bottom: 10px; }
  ")),

  div(class = "app-header",
    div(class = "app-title", APP_NAME),
    div(class = "app-tagline", APP_TAGLINE)
  ),
  div(class = "step-indicator", textOutput("step_indicator", inline = TRUE)),

  # ---------------- STEP 1: PLOT TYPE ----------------
  div(id = "page1", class = "wizard-card",
    div(class = "section-heading", "Step 1 \u2014 What do you want to plot?"),
    radioButtons(
      "plot_type_main", NULL,
      choices = c(
        "Section map \u2014 depth vs station/transect (colour, ggplot)" = "section",
        "Line profile \u2014 depth-vs-parameter lines"                  = "line",
        "Surface map \u2014 a parameter interpolated over real geography" = "surface",
        "Station location map \u2014 where your stations are, with seafloor depth" = "station"
      ),
      selected = "section", width = "100%"
    )
  ),

  # ---------------- STEP 2: SUB-MODE ----------------
  div(id = "page2", class = "wizard-card",
    div(class = "section-heading", "Step 2 \u2014 Sub-mode"),

    conditionalPanel(condition = "input.plot_type_main == 'section'",
      radioButtons("section_mode", "Section map sub-mode", choices = c(
        "By Transect (vary Station, seafloor shown)" = "transect",
        "By Station (vary Transect, named sections)" = "station"
      ))
    ),
    conditionalPanel(condition = "input.plot_type_main == 'line'",
      radioButtons("line_mode", "Line profile sub-mode", choices = c(
        "By Parameters (one station, many parameters)" = "parameters",
        "By Transects (one station no., one parameter)" = "transects"
      ))
    ),
    conditionalPanel(condition = "input.plot_type_main == 'surface'",
      p("Surface maps have no sub-mode \u2014 pick a parameter and extent later. Click Next.")
    ),
    conditionalPanel(condition = "input.plot_type_main == 'station'",
      p("Station location maps have no sub-mode \u2014 they always show every station. Click Next.")
    )
  ),

  # ---------------- STEP 3: UPLOAD ----------------
  div(id = "page3", class = "wizard-card",
    div(class = "section-heading", "Step 3 \u2014 Upload data"),

    strong("Excel file"),
    fileInput("excel_file", NULL, accept = c(".xlsx", ".xls"), buttonLabel = "Upload..."),

    conditionalPanel(
      condition = "input.plot_type_main == 'surface' || input.plot_type_main == 'station'",
      strong("GEBCO bathymetry file (.nc)"),
      helpText("Needed for surface maps and station location maps, for the seafloor depth background."),
      fileInput("gebco_file", NULL, accept = c(".nc"), buttonLabel = "Upload...")
    )
  ),

  # ---------------- STEP 4: COLUMNS ----------------
  div(id = "page4", class = "wizard-card",
    div(class = "section-heading", "Step 4 \u2014 Columns & selections"),

    conditionalPanel(
      condition = "input.plot_type_main == 'section' || input.plot_type_main == 'line'",
      selectInput("station_column", "Station name column", choices = NULL),
      selectInput("depth_column", "Depth column", choices = NULL),

      conditionalPanel(condition = "!(input.plot_type_main == 'line' && input.line_mode == 'parameters')",
        selectInput("parameter_column", "Parameter", choices = NULL)
      ),
      conditionalPanel(condition = "input.plot_type_main == 'section' && input.section_mode == 'transect'",
        selectInput("transect_select", "Select transect", choices = NULL)
      ),
      conditionalPanel(
        condition = "(input.plot_type_main == 'section' && input.section_mode == 'station') || (input.plot_type_main == 'line' && input.line_mode == 'transects')",
        selectInput("station_select", "Select station number", choices = NULL)
      ),
      conditionalPanel(condition = "input.plot_type_main == 'line' && input.line_mode == 'parameters'",
        selectInput("full_station_select", "Select station (Transect + Station)", choices = NULL),
        checkboxGroupInput("line_parameters", "Parameters to overlay (max 10)", choices = NULL)
      ),
      conditionalPanel(
        condition = "(input.plot_type_main == 'section' && input.section_mode == 'station') || (input.plot_type_main == 'line' && input.line_mode == 'transects')",
        strong("Transect name mapping"),
        helpText("One per line: T1=Place name."),
        textAreaInput("transect_names_input", NULL, rows = 4, width = "100%")
      )
    ),

    conditionalPanel(
      condition = "input.plot_type_main == 'surface' || input.plot_type_main == 'station'",
      selectInput("geo_station_column", "Station name column", choices = NULL),
      selectInput("geo_lat_column", "Latitude column", choices = NULL),
      selectInput("geo_lon_column", "Longitude column", choices = NULL),
      conditionalPanel(condition = "input.plot_type_main == 'surface'",
        selectInput("geo_parameter_column", "Parameter", choices = NULL)
      ),
      strong("Transect name mapping (optional)"),
      helpText("One per line: T1=Place name. Leave blank to show raw transect codes."),
      textAreaInput("geo_transect_names_input", NULL, rows = 4, width = "100%")
    )
  ),

  # ---------------- STEP 5: STYLE ----------------
  div(id = "page5", class = "wizard-card",
    div(class = "section-heading", "Step 5 \u2014 Style & map settings"),

    strong("Plot title"),
    helpText("Leave blank for the automatic title."),
    textInput("plot_title_input", NULL, value = "", placeholder = "Automatic title"),

    checkboxInput("show_legend", "Show colour bar / legend", TRUE),

    conditionalPanel(condition = "input.plot_type_main == 'surface' || input.plot_type_main == 'station'",
      strong("Station marker colour"),
      selectInput("marker_colour_choice", NULL, choices = marker_colour_choices, selected = "#E31A1C")
    ),

    conditionalPanel(condition = "input.plot_type_main == 'section' || input.plot_type_main == 'surface'",
      strong("IDW colour package"),
      selectInput("idw_palette_choice", NULL, choices = palette_choices, selected = "default")
    ),

    tags$hr(),
    strong("Picture size (sets the on-screen and downloaded aspect ratio)"),
    fluidRow(
      column(6, numericInput("export_width", "Width (in)", value = 10, min = 4, max = 24)),
      column(6, numericInput("export_height", "Height (in)", value = 7, min = 3, max = 18))
    ),

    conditionalPanel(condition = "input.plot_type_main == 'surface' || input.plot_type_main == 'station'",
      tags$hr(),
      strong("Map extent (adjust if your study area changes)"),
      fluidRow(
        column(6, numericInput("extent_lon_min", "Min longitude", value = 74)),
        column(6, numericInput("extent_lon_max", "Max longitude", value = 79))
      ),
      fluidRow(
        column(6, numericInput("extent_lat_min", "Min latitude", value = 6.5)),
        column(6, numericInput("extent_lat_max", "Max latitude", value = 12.5))
      )
    ),

    conditionalPanel(condition = "input.plot_type_main == 'section' || input.plot_type_main == 'surface'",
      tags$hr(),
      strong("Interpolation (IDW)"),
      sliderInput("idw_power", "IDW power (idp)", min = 0.5, max = 5, value = 2, step = 0.5),
      sliderInput("idw_nmax", "IDW max neighbours (nmax)", min = 3, max = 30, value = 12, step = 1),
      sliderInput("grid_res", "Grid resolution", min = 100, max = 500, value = 300, step = 50)
    ),

    tags$hr(),
    strong("Download format"),
    radioButtons("export_format", NULL, choices = c("TIFF" = "tiff", "PNG" = "png"), selected = "tiff", inline = TRUE),
    numericInput("export_dpi", "Export DPI", value = 300, min = 72, max = 1200)
  ),

  # ---------------- STEP 6: PLOT ----------------
  div(id = "page6", class = "wizard-card wizard-card-wide",
    div(class = "section-heading", "Step 6 \u2014 Your plot"),
    uiOutput("plot_canvas"),
    tags$hr(),
    verbatimTextOutput("summary_text"),
    downloadButton("download_plot", "Download plot")
  ),

  div(class = "nav-row",
    actionButton("prev_step", "\u2190 Back"),
    actionButton("next_step", "Next \u2192")
  )
)


# ------------------------------------------------------------
# SERVER
# ------------------------------------------------------------

server <- function(input, output, session) {

  # ============================================================
  # A. WIZARD NAVIGATION
  # ============================================================

  step_names <- c(
    "1" = "Plot type", "2" = "Sub-mode", "3" = "Upload data",
    "4" = "Columns & selections", "5" = "Style & map settings", "6" = "Your plot"
  )

  current_step <- reactiveVal(1)

  show_step <- function(n) {
    for (i in 1:6) {
      shinyjs::hide(paste0("page", i))
    }
    shinyjs::show(paste0("page", n))
    shinyjs::toggleState("prev_step", condition = (n > 1))
    if (n == 6) shinyjs::hide("next_step") else shinyjs::show("next_step")
  }

  observe({
    show_step(current_step())
  })

  output$step_indicator <- renderText({
    paste0("Step ", current_step(), " of 6 \u2014 ", step_names[[as.character(current_step())]])
  })

  can_advance <- reactive({
    n <- current_step()
    pt <- input$plot_type_main %||% "section"

    if (n == 3) {
      ok <- !is.null(input$excel_file)
      if (pt %in% c("surface", "station")) ok <- ok && !is.null(input$gebco_file)
      return(ok)
    }
    if (n == 4) {
      if (pt %in% c("section", "line")) {
        return(!is.null(input$station_column) && !is.null(input$depth_column) && nzchar(input$station_column %||% "") && nzchar(input$depth_column %||% ""))
      } else {
        return(!is.null(input$geo_station_column) && !is.null(input$geo_lat_column) && !is.null(input$geo_lon_column) &&
                 nzchar(input$geo_station_column %||% "") && nzchar(input$geo_lat_column %||% "") && nzchar(input$geo_lon_column %||% ""))
      }
    }
    TRUE
  })

  observe({
    shinyjs::toggleState("next_step", condition = can_advance())
  })

  observeEvent(input$next_step, {
    if (current_step() < 6 && can_advance()) current_step(current_step() + 1)
  })

  observeEvent(input$prev_step, {
    if (current_step() > 1) current_step(current_step() - 1)
  })

  # If the user picks a different plot type after being further in,
  # send them back to step 1 -> 2 so pages reflect the new type.
  observeEvent(input$plot_type_main, {
    if (current_step() > 2) current_step(2)
  }, ignoreInit = TRUE)

  # ============================================================
  # B. DATA READING
  # ============================================================

  raw_data <- reactive({
    req(input$excel_file)
    read_excel(input$excel_file$datapath, sheet = 1)
  })

  # ---- Section / Line column guesses ----
  observeEvent(raw_data(), {
    df <- raw_data()
    cols <- names(df)

    station_guess <- cols[grepl("station", cols, ignore.case = TRUE)][1]
    if (is.na(station_guess)) station_guess <- cols[1]
    depth_guess <- cols[grepl("depth", cols, ignore.case = TRUE)][1]
    if (is.na(depth_guess)) depth_guess <- cols[2]

    updateSelectInput(session, "station_column", choices = cols, selected = station_guess)
    updateSelectInput(session, "depth_column", choices = cols, selected = depth_guess)

    lat_guess <- cols[grepl("^lat", cols, ignore.case = TRUE)][1]
    if (is.na(lat_guess)) lat_guess <- cols[grepl("lat", cols, ignore.case = TRUE)][1]
    lon_guess <- cols[grepl("^lon", cols, ignore.case = TRUE)][1]
    if (is.na(lon_guess)) lon_guess <- cols[grepl("lon", cols, ignore.case = TRUE)][1]
    geo_station_guess <- cols[grepl("station|transect|name", cols, ignore.case = TRUE)][1]
    if (is.na(geo_station_guess)) geo_station_guess <- cols[1]

    updateSelectInput(session, "geo_station_column", choices = cols, selected = geo_station_guess)
    updateSelectInput(session, "geo_lat_column", choices = cols, selected = lat_guess %||% cols[1])
    updateSelectInput(session, "geo_lon_column", choices = cols, selected = lon_guess %||% cols[2])
  })

  parameter_columns_all <- reactive({
    df <- raw_data()
    req(df, input$station_column, input$depth_column)
    excluded <- c(input$station_column, input$depth_column)
    possible <- setdiff(names(df), excluded)
    possible[sapply(df[possible], function(x) {
      v <- suppressWarnings(as.numeric(x))
      sum(!is.na(v)) > 0
    })]
  })

  observeEvent(parameter_columns_all(), {
    params <- parameter_columns_all()
    req(length(params) > 0)
    updateSelectInput(session, "parameter_column", choices = params, selected = params[1])
    default_selection <- params[seq_len(min(5, length(params)))]
    updateCheckboxGroupInput(session, "line_parameters", choices = params, selected = default_selection)
  })

  geo_parameter_columns <- reactive({
    df <- raw_data()
    req(df, input$geo_station_column, input$geo_lat_column, input$geo_lon_column)
    excluded <- c(input$geo_station_column, input$geo_lat_column, input$geo_lon_column)
    possible <- setdiff(names(df), excluded)
    possible[sapply(df[possible], function(x) {
      v <- suppressWarnings(as.numeric(x))
      sum(!is.na(v)) > 0
    })]
  })

  observeEvent(geo_parameter_columns(), {
    params <- geo_parameter_columns()
    req(length(params) > 0)
    updateSelectInput(session, "geo_parameter_column", choices = params, selected = params[1])
  })

  station_meta <- reactive({
    df <- raw_data()
    req(df, input$station_column)
    stn <- trimws(as.character(df[[input$station_column]]))
    out <- data.frame(
      Station = stn, Transect = str_extract(stn, "^T[0-9]+"),
      StationNumber = str_extract(stn, "S[0-9]+"), stringsAsFactors = FALSE
    ) %>% filter(!is.na(Station), Station != "") %>% distinct(Station, .keep_all = TRUE)
    validate(need(nrow(out) > 0, "No station names detected. Check the Station column."))
    out
  })

  observeEvent(station_meta(), {
    meta <- station_meta()
    transects <- numeric_sort(unique(na.omit(meta$Transect)))
    if (length(transects) > 0) {
      updateSelectInput(session, "transect_select", choices = transects)
      updateTextAreaInput(session, "transect_names_input", value = paste0(transects, "=", transects, collapse = "\n"))
    }
    stations <- numeric_sort(unique(na.omit(meta$StationNumber)))
    if (length(stations) > 0) updateSelectInput(session, "station_select", choices = stations)

    meta_sorted <- meta %>%
      mutate(
        tn = suppressWarnings(as.numeric(str_extract(Transect, "[0-9]+"))),
        sn = suppressWarnings(as.numeric(str_extract(StationNumber, "[0-9]+")))
      ) %>% arrange(tn, sn)
    if (nrow(meta_sorted) > 0) updateSelectInput(session, "full_station_select", choices = meta_sorted$Station)
  })

  # ---- geo (surface / station) transect names + extent defaults ----
  observeEvent(list(input$geo_station_column, input$geo_lat_column, input$geo_lon_column), {
    req(raw_data(), input$geo_station_column, input$geo_lat_column, input$geo_lon_column)
    df <- raw_data()
    stn <- trimws(as.character(df[[input$geo_station_column]]))
    transects <- numeric_sort(unique(na.omit(str_extract(stn, "^T[0-9]+"))))
    if (length(transects) > 0) {
      updateTextAreaInput(session, "geo_transect_names_input", value = paste0(transects, "=", transects, collapse = "\n"))
    }

    lats <- parse_coordinate(df[[input$geo_lat_column]])
    lons <- parse_coordinate(df[[input$geo_lon_column]])
    lats <- lats[is.finite(lats)]; lons <- lons[is.finite(lons)]
    if (length(lats) > 0 && length(lons) > 0) {
      lat_pad <- max(0.3, diff(range(lats)) * 0.25)
      lon_pad <- max(0.3, diff(range(lons)) * 0.25)
      updateNumericInput(session, "extent_lat_min", value = round(min(lats) - lat_pad, 2))
      updateNumericInput(session, "extent_lat_max", value = round(max(lats) + lat_pad, 2))
      updateNumericInput(session, "extent_lon_min", value = round(min(lons) - lon_pad, 2))
      updateNumericInput(session, "extent_lon_max", value = round(max(lons) + lon_pad, 2))
    }
  }, ignoreInit = TRUE)

  transect_name_map <- function(text_input) {
    txt <- text_input %||% ""
    lines <- trimws(strsplit(txt, "\n")[[1]])
    lines <- lines[nchar(lines) > 0]
    if (length(lines) == 0) return(c())
    kv <- strsplit(lines, "=")
    keys <- trimws(sapply(kv, `[`, 1))
    vals <- trimws(sapply(kv, function(x) if (length(x) > 1) x[2] else x[1]))
    setNames(vals, keys)
  }

  apply_name_map <- function(codes, map) {
    sapply(codes, function(x) if (x %in% names(map)) map[[x]] else x)
  }

  resolve_title <- function(default_title) {
    custom <- trimws(input$plot_title_input %||% "")
    if (nzchar(custom)) custom else default_title
  }

  processed_data <- reactive({
    df <- raw_data()
    req(input$station_column, input$depth_column, input$parameter_column)
    out <- df %>%
      mutate(
        Station = trimws(as.character(.data[[input$station_column]])),
        Depth   = suppressWarnings(as.numeric(.data[[input$depth_column]])),
        Value   = suppressWarnings(as.numeric(.data[[input$parameter_column]]))
      ) %>%
      filter(!is.na(Station), !is.na(Depth)) %>%
      mutate(Transect = str_extract(Station, "^T[0-9]+"), StationNumber = str_extract(Station, "S[0-9]+"))
    validate(need(nrow(out) > 0, "No valid rows after parsing Station/Depth. Check your column selection."))
    out
  })

  # ============================================================
  # C. SECTION MAP (ggplot)
  # ============================================================

  section_plot_obj <- reactive({
    req(input$plot_type_main == "section")

    if (input$section_mode == "transect") {
      req(input$transect_select)
      transect_data <- processed_data() %>% filter(Transect == input$transect_select, !is.na(StationNumber))
      validate(need(nrow(transect_data) > 0, "No data found for the selected transect."))

      station_order <- numeric_sort(unique(transect_data$StationNumber))
      transect_data$StationNumber <- factor(transect_data$StationNumber, levels = station_order)
      transect_data <- transect_data %>% mutate(X = as.numeric(StationNumber))

      min_depth <- min(transect_data$Depth, na.rm = TRUE)
      max_depth <- max(transect_data$Depth, na.rm = TRUE)

      bathymetry <- transect_data %>%
        group_by(StationNumber) %>%
        summarise(X = first(X), BottomDepth = max(Depth, na.rm = TRUE), .groups = "drop") %>%
        arrange(X)

      idw_data <- transect_data %>% filter(!is.na(Value), is.finite(Value))
      validate(need(nrow(idw_data) >= 3, "Not enough valid observations for IDW interpolation (need at least 3)."))

      res <- input$grid_res %||% 300
      grid <- expand.grid(
        X = seq(min(transect_data$X), max(transect_data$X), length.out = res),
        Depth = seq(min_depth, max_depth, length.out = res)
      )

      coordinates(idw_data) <- ~ X + Depth
      coordinates(grid) <- ~ X + Depth

      idw_model <- gstat(formula = Value ~ 1, locations = idw_data,
                          nmax = input$idw_nmax %||% 12, set = list(idp = input$idw_power %||% 2))
      idw_plot <- as.data.frame(predict(idw_model, newdata = grid))
      names(idw_plot)[names(idw_plot) == "var1.pred"] <- "Value"

      bottom_depth_at_x <- approx(x = bathymetry$X, y = bathymetry$BottomDepth, xout = idw_plot$X, rule = 2)$y
      idw_plot$BottomDepth <- bottom_depth_at_x
      idw_plot <- idw_plot %>% filter(Depth <= BottomDepth)

      observation_points <- transect_data %>% mutate(ParameterMissing = is.na(Value))
      bathymetry_polygon <- rbind(
        data.frame(X = bathymetry$X, Depth = bathymetry$BottomDepth),
        data.frame(X = rev(bathymetry$X), Depth = rep(max_depth, nrow(bathymetry)))
      )

      parameter_min <- min(idw_data$Value, na.rm = TRUE)
      parameter_max <- max(idw_data$Value, na.rm = TRUE)

      p <- ggplot() +
        geom_raster(data = idw_plot, aes(x = X, y = Depth, fill = Value)) +
        geom_polygon(data = bathymetry_polygon, aes(x = X, y = Depth), fill = "#4A2F1B", colour = NA) +
        geom_line(data = bathymetry, aes(x = X, y = BottomDepth), linewidth = 0.7, colour = "black") +
        geom_point(data = observation_points %>% filter(!ParameterMissing),
                   aes(x = X, y = Depth), shape = 21, size = 2.2, stroke = 0.5, fill = "white") +
        geom_point(data = observation_points %>% filter(ParameterMissing),
                   aes(x = X, y = Depth), shape = 21, size = 3, stroke = 0.8, fill = "white", colour = "black") +
        geom_point(data = observation_points %>% filter(ParameterMissing),
                   aes(x = X, y = Depth), shape = 4, size = 2, stroke = 0.8, colour = "black") +
        scale_y_reverse(breaks = depth_axis_breaks(min_depth, max_depth), expand = c(0, 0)) +
        scale_x_continuous(breaks = seq_along(station_order), labels = station_order, expand = c(0, 0)) +
        get_fill_scale(input$idw_palette_choice, c(parameter_min, parameter_max), input$parameter_column, input$show_legend) +
        labs(x = NULL, y = "Depth (m)", title = resolve_title(paste("Transect", input$transect_select))) +
        section_theme()

      attr(p, "summary") <- paste0(
        "Mode: Section \u2014 By Transect\n", "Transect: ", input$transect_select, "\n",
        "Stations: ", paste(station_order, collapse = ", "), "\n", "Parameter: ", input$parameter_column, "\n",
        "Depth range: ", round(min_depth, 1), " - ", round(max_depth, 1), " m\n",
        "Parameter range: ", round(parameter_min, 3), " - ", round(parameter_max, 3)
      )
      p

    } else {
      req(input$station_select)
      station_data <- processed_data() %>% filter(StationNumber == input$station_select, !is.na(Transect))
      validate(need(nrow(station_data) > 0, "No data found for the selected station."))

      detected_transects <- numeric_sort(unique(station_data$Transect))
      station_data$Transect <- factor(station_data$Transect, levels = detected_transects)
      station_data <- station_data %>% mutate(X = as.numeric(Transect))

      idw_data <- station_data %>% filter(!is.na(Value), is.finite(Value))
      validate(need(nrow(idw_data) >= 3, "Not enough valid observations for IDW interpolation (need at least 3)."))

      x_min <- min(station_data$X); x_max <- max(station_data$X)
      y_min <- min(station_data$Depth); y_max <- max(station_data$Depth)

      res <- input$grid_res %||% 300
      grid <- expand.grid(
        X = seq(x_min, x_max, length.out = res),
        Depth = seq(y_min, y_max, length.out = res)
      )

      coordinates(idw_data) <- ~ X + Depth
      coordinates(grid) <- ~ X + Depth

      idw_model <- gstat(formula = Value ~ 1, locations = idw_data,
                          nmax = input$idw_nmax %||% 12, set = list(idp = input$idw_power %||% 2))
      idw_plot <- as.data.frame(predict(idw_model, newdata = grid))
      names(idw_plot)[names(idw_plot) == "var1.pred"] <- "Value"

      available_depths <- sort(unique(station_data$Depth))
      name_map <- transect_name_map(input$transect_names_input)
      transect_label_vector <- apply_name_map(levels(station_data$Transect), name_map)

      parameter_min <- min(idw_data$Value, na.rm = TRUE)
      parameter_max <- max(idw_data$Value, na.rm = TRUE)

      p <- ggplot() +
        geom_raster(data = idw_plot, aes(x = X, y = Depth, fill = Value)) +
        geom_point(data = station_data %>% filter(!is.na(Value)),
                   aes(x = X, y = Depth), shape = 21, size = 2.2, stroke = 0.5, fill = "white") +
        scale_y_reverse(breaks = available_depths, expand = c(0, 0)) +
        get_fill_scale(input$idw_palette_choice, c(parameter_min, parameter_max), input$parameter_column, input$show_legend) +
        scale_x_continuous(breaks = seq_along(levels(station_data$Transect)),
                            labels = transect_label_vector, expand = c(0, 0)) +
        labs(x = NULL, y = "Depth (m)", title = resolve_title(paste("Station", input$station_select))) +
        section_theme()

      attr(p, "summary") <- paste0(
        "Mode: Section \u2014 By Station\n", "Station: ", input$station_select, "\n",
        "Transects: ", paste(transect_label_vector, collapse = ", "), "\n", "Parameter: ", input$parameter_column, "\n",
        "Depth range: ", round(y_min, 1), " - ", round(y_max, 1), " m\n",
        "Parameter range: ", round(parameter_min, 3), " - ", round(parameter_max, 3)
      )
      p
    }
  })

  # ============================================================
  # D. LINE PROFILE (base R graphics)
  # ============================================================

  line_base_data <- reactive({
    df <- raw_data()
    req(df, input$station_column, input$depth_column)
    df[[input$station_column]] <- trimws(as.character(df[[input$station_column]]))
    df[[input$depth_column]] <- suppressWarnings(as.numeric(df[[input$depth_column]]))
    df
  })

  line_profile_inputs <- reactive({
    req(input$plot_type_main == "line")
    df <- line_base_data()

    if (input$line_mode == "parameters") {
      req(input$full_station_select)
      selected_parameters <- input$line_parameters
      validate(need(length(selected_parameters) >= 1, "Select at least one parameter."))
      validate(need(length(selected_parameters) <= 10, "Select a maximum of 10 parameters."))

      station_data <- df[df[[input$station_column]] == input$full_station_select, , drop = FALSE]
      validate(need(nrow(station_data) > 0, "No data found for the selected station."))

      parameter_data <- list()
      for (parameter_name in selected_parameters) {
        values <- suppressWarnings(as.numeric(station_data[[parameter_name]]))
        depths <- suppressWarnings(as.numeric(station_data[[input$depth_column]]))
        valid <- !is.na(values) & !is.na(depths)
        temp <- data.frame(depth = depths[valid], value = values[valid])
        temp <- temp[order(temp$depth), , drop = FALSE]
        if (nrow(temp) > 0) parameter_data[[parameter_name]] <- temp
      }
      parameter_data <- parameter_data[sapply(parameter_data, nrow) > 0]
      validate(need(length(parameter_data) > 0, "No valid parameter data were found for this station."))
      max_depth <- max(unlist(lapply(parameter_data, function(x) x$depth)), na.rm = TRUE)

      list(
        item_names = names(parameter_data), item_data = parameter_data, max_depth = max_depth,
        plot_title = resolve_title(paste("Water Column Profile \u2014", input$full_station_select)),
        legend_title = "Parameter",
        summary = paste0(
          "Mode: Line \u2014 By Parameters\n", "Station: ", input$full_station_select, "\n",
          "Parameters: ", paste(names(parameter_data), collapse = ", "), "\n", "Max depth: ", round(max_depth, 1), " m"
        )
      )

    } else {
      req(input$station_select, input$parameter_column)
      selected_station_number <- input$station_select
      selected_parameter <- input$parameter_column

      station_values <- unique(df[[input$station_column]])
      station_values <- station_values[!is.na(station_values)]
      matching_stations <- station_values[grepl(paste0("\\b", selected_station_number, "$"), station_values)]
      validate(need(length(matching_stations) > 0, paste("No stations found for:", selected_station_number)))

      transect_codes <- sub(paste0("\\s+", selected_station_number, "$"), "", matching_stations)
      numeric_transect <- suppressWarnings(as.numeric(sub("^T", "", transect_codes)))
      transect_order <- order(is.na(numeric_transect), numeric_transect, transect_codes)
      matching_stations <- matching_stations[transect_order]
      transect_codes <- transect_codes[transect_order]

      validate(need(length(transect_codes) <= 10, "More than 10 transects were found. Maximum allowed is 10."))

      name_map <- transect_name_map(input$transect_names_input)
      transect_labels <- apply_name_map(transect_codes, name_map)

      transect_data <- list()
      for (i in seq_along(matching_stations)) {
        station_value <- matching_stations[i]
        label <- transect_labels[i]
        temp <- df[df[[input$station_column]] == station_value, , drop = FALSE]
        depths <- suppressWarnings(as.numeric(temp[[input$depth_column]]))
        values <- suppressWarnings(as.numeric(temp[[selected_parameter]]))
        valid <- !is.na(depths) & !is.na(values)
        profile <- data.frame(depth = depths[valid], value = values[valid])
        profile <- profile[order(profile$depth), , drop = FALSE]
        if (nrow(profile) > 0) transect_data[[label]] <- profile
      }
      transect_data <- transect_data[sapply(transect_data, nrow) > 0]
      validate(need(length(transect_data) > 0, "No valid transect data were found."))
      max_depth <- max(unlist(lapply(transect_data, function(x) x$depth)), na.rm = TRUE)

      list(
        item_names = names(transect_data), item_data = transect_data, max_depth = max_depth,
        plot_title = resolve_title(paste("Water Column Profile \u2014", selected_parameter, "- Station", selected_station_number)),
        legend_title = "Transect",
        summary = paste0(
          "Mode: Line \u2014 By Transects\n", "Station number: ", selected_station_number, "\n",
          "Parameter: ", selected_parameter, "\n", "Transects: ", paste(names(transect_data), collapse = ", "), "\n",
          "Max depth: ", round(max_depth, 1), " m"
        )
      )
    }
  })

  # ============================================================
  # E. GEOGRAPHIC DATA (surface map + station location map)
  # ============================================================

  map_extent_reactive <- reactive({
    list(
      lon_min = input$extent_lon_min %||% 74, lon_max = input$extent_lon_max %||% 79,
      lat_min = input$extent_lat_min %||% 6.5, lat_max = input$extent_lat_max %||% 12.5
    )
  })

  gebco_raster <- reactive({
    req(input$gebco_file)
    r <- terra::rast(input$gebco_file$datapath)
    if (is.na(terra::crs(r)) || terra::crs(r) == "") terra::crs(r) <- "EPSG:4326"
    r
  })

  land_polygon <- reactive({
    ext <- map_extent_reactive()
    world <- rnaturalearth::ne_countries(scale = "medium", returnclass = "sf")
    world <- sf::st_transform(world, crs = 4326)
    bbox_sf <- sf::st_as_sfc(sf::st_bbox(
      c(xmin = ext$lon_min, xmax = ext$lon_max, ymin = ext$lat_min, ymax = ext$lat_max),
      crs = sf::st_crs(4326)
    ))
    suppressWarnings(sf::st_intersection(world, bbox_sf))
  })

  cropped_bathymetry_df <- reactive({
    ext <- map_extent_reactive()
    gebco <- gebco_raster()
    cropped <- terra::crop(gebco, terra::ext(ext$lon_min, ext$lon_max, ext$lat_min, ext$lat_max))
    validate(need(terra::ncell(cropped) > 0, "No GEBCO data found inside the selected extent."))
    depth_raster <- -cropped
    bath_df <- as.data.frame(depth_raster, xy = TRUE, na.rm = FALSE)
    names(bath_df) <- c("x", "y", "Depth")
    bath_df$OceanDepth <- ifelse(bath_df$Depth > 0, bath_df$Depth, NA_real_)
    bath_df
  })

  surface_data <- reactive({
    req(raw_data(), input$geo_station_column, input$geo_lat_column, input$geo_lon_column, input$geo_parameter_column)
    df <- raw_data()
    out <- df %>%
      transmute(
        Station = trimws(as.character(.data[[input$geo_station_column]])),
        Latitude = parse_coordinate(.data[[input$geo_lat_column]]),
        Longitude = parse_coordinate(.data[[input$geo_lon_column]]),
        Value = suppressWarnings(as.numeric(.data[[input$geo_parameter_column]]))
      ) %>%
      filter(!is.na(Station), !is.na(Latitude), !is.na(Longitude)) %>%
      mutate(Transect = str_extract(Station, "^T[0-9]+"))
    validate(need(nrow(out) > 0, "No valid rows. Check Station/Latitude/Longitude/Parameter columns."))
    out
  })

  station_location_data <- reactive({
    req(raw_data(), input$geo_station_column, input$geo_lat_column, input$geo_lon_column)
    df <- raw_data()
    out <- df %>%
      transmute(
        Station = trimws(as.character(.data[[input$geo_station_column]])),
        Latitude = parse_coordinate(.data[[input$geo_lat_column]]),
        Longitude = parse_coordinate(.data[[input$geo_lon_column]])
      ) %>%
      filter(!is.na(Station), !is.na(Latitude), !is.na(Longitude)) %>%
      mutate(Transect = str_extract(Station, "^T[0-9]+"), StationLabel = str_extract(Station, "S[0-9]+"))
    validate(need(nrow(out) > 0, "No valid coordinates parsed. Check Station/Latitude/Longitude columns."))
    out
  })

  # ============================================================
  # F. SURFACE MAP (ggplot - IDW of a parameter over geography)
  # ============================================================

  surface_plot_obj <- reactive({
    req(input$plot_type_main == "surface")
    ext <- map_extent_reactive()
    sd <- surface_data()
    bath_df <- cropped_bathymetry_df()
    land <- land_polygon()

    valid <- sd %>% filter(!is.na(Value), is.finite(Value))
    validate(need(nrow(valid) >= 3, "Need at least 3 valid parameter readings to interpolate."))

    res <- input$grid_res %||% 300
    sp_pts <- valid
    coordinates(sp_pts) <- ~ Longitude + Latitude
    grid_pts <- expand.grid(
      Lon = seq(ext$lon_min, ext$lon_max, length.out = res),
      Lat = seq(ext$lat_min, ext$lat_max, length.out = res)
    )
    coordinates(grid_pts) <- ~ Lon + Lat
    gridded(grid_pts) <- TRUE

    idw_res <- idw(Value ~ 1, locations = sp_pts, newdata = grid_pts, idp = input$idw_power %||% 2)
    grid_df <- as.data.frame(idw_res)[, 1:3]
    names(grid_df) <- c("Lon", "Lat", "Value")

    interp_raster <- terra::rast(grid_df[, c("Lon", "Lat", "Value")], type = "xyz")
    terra::crs(interp_raster) <- "EPSG:4326"
    land_vect <- terra::vect(land)
    interp_raster <- terra::mask(interp_raster, land_vect, inverse = TRUE)
    grid_df <- as.data.frame(interp_raster, xy = TRUE, na.rm = FALSE)
    names(grid_df) <- c("Lon", "Lat", "Value")

    mean_lat <- mean(valid$Latitude)
    km_per_deg_lon <- 111.32 * cos(mean_lat * pi / 180)
    km_per_deg_lat <- 111.32
    lon_diff <- outer(grid_df$Lon, valid$Longitude, "-")
    lat_diff <- outer(grid_df$Lat, valid$Latitude, "-")
    dist_matrix <- sqrt((lon_diff * km_per_deg_lon)^2 + (lat_diff * km_per_deg_lat)^2)
    grid_df$dist_km <- apply(dist_matrix, 1, min)

    fade_km <- 50; fade_zone_km <- 25
    grid_df$Value[grid_df$dist_km > fade_km] <- NA
    grid_df$alpha <- 1
    edge <- grid_df$dist_km > (fade_km - fade_zone_km)
    grid_df$alpha[edge] <- pmax(0, pmin(1, (fade_km - grid_df$dist_km[edge]) / fade_zone_km))
    grid_df$alpha[is.na(grid_df$Value)] <- 0

    parameter_min <- min(valid$Value, na.rm = TRUE)
    parameter_max <- max(valid$Value, na.rm = TRUE)

    name_map <- transect_name_map(input$geo_transect_names_input)
    transect_rows <- valid %>% filter(!is.na(Transect)) %>% group_by(Transect) %>% slice(1) %>% ungroup()
    transect_rows$Label <- apply_name_map(transect_rows$Transect, name_map)

    p <- ggplot() +
      geom_tile(data = grid_df, aes(x = Lon, y = Lat, fill = Value, alpha = alpha)) +
      geom_contour(data = bath_df, aes(x = x, y = y, z = Depth),
                   breaks = c(-50, -100, -200, -500, -1000, -2000, -3000),
                   colour = "grey30", linewidth = 0.3, linetype = "dashed") +
      geom_sf(data = land, fill = "grey88", colour = "grey20", linewidth = 0.35) +
      geom_point(data = valid, aes(x = Longitude, y = Latitude), shape = 21, size = 2.6,
                 stroke = 0.9, fill = input$marker_colour_choice %||% "#E31A1C", colour = "black") +
      geom_text_repel(data = transect_rows, aes(x = Longitude, y = Latitude, label = Label),
                       fontface = "bold", size = 3.6, max.overlaps = Inf, seed = 42) +
      get_fill_scale(input$idw_palette_choice, c(parameter_min, parameter_max), input$geo_parameter_column, input$show_legend) +
      scale_alpha_continuous(range = c(0, 1), guide = "none") +
      annotation_scale(location = "bl", width_hint = 0.3) +
      annotation_north_arrow(location = "tr", which_north = "true",
                              height = unit(1, "cm"), width = unit(1, "cm"),
                              style = north_arrow_fancy_orienteering) +
      coord_sf(xlim = c(ext$lon_min, ext$lon_max), ylim = c(ext$lat_min, ext$lat_max), expand = FALSE) +
      labs(title = resolve_title(paste("Parameter Surface \u2014", input$geo_parameter_column)),
           x = "Longitude", y = "Latitude") +
      geo_theme()

    attr(p, "summary") <- paste0(
      "Mode: Surface Map\n", "Parameter: ", input$geo_parameter_column, "\n",
      "Stations used: ", nrow(valid), "\n",
      "Parameter range: ", round(parameter_min, 3), " - ", round(parameter_max, 3), "\n",
      "Extent: ", ext$lon_min, "\u2013", ext$lon_max, "\u00b0E, ", ext$lat_min, "\u2013", ext$lat_max, "\u00b0N"
    )
    p
  })

  # ============================================================
  # G. STATION LOCATION MAP (ggplot - points + bathymetry)
  # ============================================================

  station_plot_obj <- reactive({
    req(input$plot_type_main == "station")
    ext <- map_extent_reactive()
    sd <- station_location_data()
    bath_df <- cropped_bathymetry_df()
    land <- land_polygon()

    name_map <- transect_name_map(input$geo_transect_names_input)
    transect_rows <- sd %>% filter(!is.na(Transect)) %>% group_by(Transect) %>%
      slice_max(Longitude, n = 1, with_ties = FALSE) %>% ungroup()
    transect_rows$Label <- apply_name_map(transect_rows$Transect, name_map)

    p <- ggplot() +
      geom_raster(data = bath_df, aes(x = x, y = y, fill = pmin(OceanDepth, 2500))) +
      scale_fill_gradientn(
        colours = c("#E5F7FC", "#B8E5F2", "#78C6E0", "#3A9BC0", "#176B99", "#063B68"),
        na.value = "transparent", name = "Depth (m)",
        guide = if (isTRUE(input$show_legend)) "colourbar" else "none"
      ) +
      geom_sf(data = land, fill = "grey88", colour = "grey20", linewidth = 0.35) +
      geom_point(data = sd, aes(x = Longitude, y = Latitude), shape = 21, size = 1.8,
                 stroke = 0.8, fill = input$marker_colour_choice %||% "#E31A1C", colour = "white") +
      geom_text_repel(data = sd, aes(x = Longitude, y = Latitude, label = StationLabel),
                       size = 3, max.overlaps = Inf, seed = 42, segment.colour = "grey40") +
      geom_text_repel(data = transect_rows, aes(x = Longitude, y = Latitude, label = Label),
                       fontface = "bold", size = 4.2, max.overlaps = Inf, seed = 42, segment.colour = "grey20") +
      annotation_scale(location = "bl", width_hint = 0.3) +
      annotation_north_arrow(location = "tr", which_north = "true",
                              height = unit(1, "cm"), width = unit(1, "cm"),
                              style = north_arrow_fancy_orienteering) +
      coord_sf(xlim = c(ext$lon_min, ext$lon_max), ylim = c(ext$lat_min, ext$lat_max), expand = FALSE) +
      labs(title = resolve_title("Sampling Location and Bathymetry Map"), x = "Longitude", y = "Latitude") +
      geo_theme()

    attr(p, "summary") <- paste0(
      "Mode: Station Location Map\n", "Stations: ", nrow(sd), "\n",
      "Transects: ", paste(unique(transect_rows$Label), collapse = ", "), "\n",
      "Extent: ", ext$lon_min, "\u2013", ext$lon_max, "\u00b0E, ", ext$lat_min, "\u2013", ext$lat_max, "\u00b0N"
    )
    p
  })

  # ============================================================
  # H. CANVAS, RENDER DISPATCH, SUMMARY, DOWNLOAD
  # ============================================================

  output$plot_canvas <- renderUI({
    w <- input$export_width %||% 10
    h <- input$export_height %||% 7
    px_width <- 760
    px_height <- max(300, round(px_width * (h / w)))
    plotOutput("main_plot", height = paste0(px_height, "px"))
  })

  output$main_plot <- renderPlot({
    pt <- input$plot_type_main
    if (pt == "line") {
      li <- line_profile_inputs()
      draw_two_panel_profile(
        item_names = li$item_names, item_data = li$item_data, max_depth = li$max_depth,
        plot_title = li$plot_title, legend_title = li$legend_title,
        label_gap_in = label_gap_in, show_legend = isTRUE(input$show_legend)
      )
    } else {
      p <- switch(pt,
        "section" = section_plot_obj(),
        "surface" = surface_plot_obj(),
        "station" = station_plot_obj()
      )
      print(p)
    }
    draw_watermark()
  })

  output$summary_text <- renderText({
    pt <- input$plot_type_main
    if (pt == "line") {
      line_profile_inputs()$summary
    } else {
      p <- switch(pt,
        "section" = section_plot_obj(),
        "surface" = surface_plot_obj(),
        "station" = station_plot_obj()
      )
      attr(p, "summary")
    }
  })

  output$download_plot <- downloadHandler(
    filename = function() {
      fmt <- input$export_format %||% "tiff"
      ext <- if (identical(fmt, "png")) "png" else "tif"
      pt <- input$plot_type_main
      base <- switch(pt,
        "section" = if (input$section_mode == "transect") input$transect_select else input$station_select,
        "line"    = if (input$line_mode == "parameters") input$full_station_select else input$station_select,
        "surface" = "surface_map",
        "station" = "station_location_map"
      )
      paste0(APP_NAME, "_", gsub("[^A-Za-z0-9]+", "_", base %||% "plot"), "_", Sys.Date(), ".", ext)
    },
    content = function(file) {
      fmt <- input$export_format %||% "tiff"
      w <- input$export_width %||% 10
      h <- input$export_height %||% 7
      dpi <- input$export_dpi %||% 300

      if (identical(fmt, "png")) {
        png(filename = file, width = w, height = h, units = "in", res = dpi)
      } else {
        tiff(filename = file, width = w, height = h, units = "in", res = dpi, compression = "lzw")
      }

      pt <- input$plot_type_main
      if (pt == "line") {
        li <- line_profile_inputs()
        draw_two_panel_profile(
          item_names = li$item_names, item_data = li$item_data, max_depth = li$max_depth,
          plot_title = li$plot_title, legend_title = li$legend_title,
          label_gap_in = label_gap_in, show_legend = isTRUE(input$show_legend)
        )
      } else {
        p <- switch(pt,
          "section" = section_plot_obj(),
          "surface" = surface_plot_obj(),
          "station" = station_plot_obj()
        )
        print(p)
      }
      draw_watermark()
      dev.off()
    }
  )
}

shinyApp(ui, server)
