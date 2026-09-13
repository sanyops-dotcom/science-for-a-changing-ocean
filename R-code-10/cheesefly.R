# ============================================================
# VERTICAL SECTION PROFILER — COMBINED SHINY APP
# ============================================================
#
# Combines two workflows into one interactive app:
#
#  MODE 1 "By Transect"  (was code-05)
#    Fix ONE transect, vary STATIONS along it.
#    X = Station, includes bathymetry mask (ocean bottom).
#
#  MODE 2 "By Station"   (was code-04)
#    Fix ONE station number, vary TRANSECTS across it.
#    X = Transect (labelled with real place names).
#
# Everything that used to be edited by hand inside the R
# script (file path, transect, station, parameter, IDW
# settings, transect names) is now a control in the sidebar.
#
# ============================================================

required_packages <- c(
  "shiny", "readxl", "dplyr", "stringr",
  "ggplot2", "gstat", "sp", "scales"
)

for (pkg in required_packages) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    install.packages(pkg)
  }
}


library(shiny)
library(readxl)
library(dplyr)
library(stringr)
library(ggplot2)
library(gstat)
library(sp)
library(scales)
library(htmltools)
packageVersion("htmltools")

# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

# Sort labels like S1, S2, S10 (or T1, T2, T10) in numeric order
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

idw_palette <- c(
  "#313695", "#4575B4", "#74ADD1", "#ABD9E9", "#E0F3F8",
  "#FFFFBF", "#FEE090", "#FDAE61", "#F46D43", "#D73027", "#A50026"
)


# ------------------------------------------------------------
# UI
# ------------------------------------------------------------

ui <- fluidPage(

  titlePanel("Vertical Section Profiler"),

  sidebarLayout(

    sidebarPanel(
      width = 3,

      fileInput(
        "excel_file", "1. Upload Excel file",
        accept = c(".xlsx", ".xls")
      ),

      uiOutput("column_selectors"),
      uiOutput("parameter_selector"),

      tags$hr(),

      radioButtons(
        "mode", "2. Plot mode",
        choices = c(
          "By Transect \u2014 vary Station (with seafloor)" = "transect",
          "By Station \u2014 vary Transect (named sections)"  = "station"
        )
      ),

      conditionalPanel(
        condition = "input.mode == 'transect'",
        uiOutput("transect_selector")
      ),

      conditionalPanel(
        condition = "input.mode == 'station'",
        uiOutput("station_selector"),
        tags$hr(),
        strong("Transect name mapping"),
        helpText("One per line, format T1=Place name. Edit freely — no need to touch code when a new transect is added."),
        uiOutput("transect_names_box")
      ),

      tags$hr(),

      checkboxInput("show_advanced", "Advanced settings", FALSE),

      conditionalPanel(
        condition = "input.show_advanced == true",
        sliderInput("idw_power", "IDW power (idp)", min = 0.5, max = 5, value = 2, step = 0.5),
        sliderInput("idw_nmax", "IDW max neighbours (nmax)", min = 3, max = 30, value = 12, step = 1),
        sliderInput("grid_res", "Grid resolution", min = 100, max = 500, value = 300, step = 50),
        tags$hr(),
        radioButtons("export_format", "Export format", choices = c("TIFF" = "tiff", "PNG" = "png"), selected = "tiff"),
        numericInput("export_width", "Export width (in)", value = 10, min = 4, max = 24),
        numericInput("export_height", "Export height (in)", value = 7, min = 3, max = 18),
        numericInput("export_dpi", "Export DPI", value = 600, min = 72, max = 1200)
      ),

      tags$hr(),

      downloadButton("download_plot", "Download plot")
    ),

    mainPanel(
      width = 9,
      plotOutput("section_plot", height = "600px"),
      tags$hr(),
      verbatimTextOutput("summary_text")
    )
  )
)


# ------------------------------------------------------------
# SERVER
# ------------------------------------------------------------

server <- function(input, output, session) {

  # ---- 1. Read uploaded Excel file --------------------------

  raw_data <- reactive({
    req(input$excel_file)
    read_excel(input$excel_file$datapath, sheet = 1)
  })

  # ---- 2. Column pickers (auto-guessed, user-overridable) ---

  output$column_selectors <- renderUI({
    df <- raw_data()
    cols <- names(df)

    station_guess <- cols[grepl("station", cols, ignore.case = TRUE)][1]
    if (is.na(station_guess)) station_guess <- cols[1]

    depth_guess <- cols[grepl("depth", cols, ignore.case = TRUE)][1]
    if (is.na(depth_guess)) depth_guess <- cols[2]

    tagList(
      selectInput("station_column", "Station name column", choices = cols, selected = station_guess),
      selectInput("depth_column", "Depth column", choices = cols, selected = depth_guess)
    )
  })

  output$parameter_selector <- renderUI({
    df <- raw_data()
    req(input$station_column, input$depth_column)
    param_choices <- setdiff(names(df), c(input$station_column, input$depth_column))
    selectInput("parameter_column", "Parameter to plot", choices = param_choices)
  })

  # ---- 3. Parse Station / Transect / StationNumber -----------

  processed_data <- reactive({
    df <- raw_data()
    req(input$station_column, input$depth_column, input$parameter_column)

    out <- df %>%
      mutate(
        Station = as.character(.data[[input$station_column]]),
        Depth   = as.numeric(.data[[input$depth_column]]),
        Value   = as.numeric(.data[[input$parameter_column]])
      ) %>%
      filter(!is.na(Station), !is.na(Depth)) %>%
      mutate(
        Transect      = str_extract(Station, "^T[0-9]+"),
        StationNumber = str_extract(Station, "S[0-9]+")
      )

    validate(need(nrow(out) > 0, "No valid rows after parsing the Station/Depth columns. Check your column selection."))
    validate(need(any(!is.na(out$Transect)), "Could not detect any transects (expected station names like 'T1 S1')."))

    out
  })

  # ---- 4. Mode-specific selectors -----------------------------

  output$transect_selector <- renderUI({
    df <- processed_data()
    choices <- numeric_sort(unique(na.omit(df$Transect)))
    selectInput("transect_select", "Select transect", choices = choices)
  })

  output$station_selector <- renderUI({
    df <- processed_data()
    choices <- numeric_sort(unique(na.omit(df$StationNumber)))
    selectInput("station_select", "Select station", choices = choices)
  })

  # Default transect-name mapping text, regenerated whenever new data loads
  default_names_text <- reactiveVal("")

  observeEvent(processed_data(), {
    df <- processed_data()
    detected <- numeric_sort(unique(na.omit(df$Transect)))
    if (length(detected) > 0) {
      default_names_text(paste0(detected, "=", detected, collapse = "\n"))
    }
  })

  output$transect_names_box <- renderUI({
    textAreaInput(
      "transect_names_input", NULL,
      value = default_names_text(),
      rows = 6, width = "100%"
    )
  })

  transect_name_map <- reactive({
    req(input$transect_names_input)
    lines <- trimws(strsplit(input$transect_names_input, "\n")[[1]])
    lines <- lines[nchar(lines) > 0]
    validate(need(length(lines) > 0, "Add at least one transect name mapping."))

    kv <- strsplit(lines, "=")
    keys <- trimws(sapply(kv, `[`, 1))
    vals <- trimws(sapply(kv, function(x) if (length(x) > 1) x[2] else x[1]))
    setNames(vals, keys)
  })

  # ---- 5. Build the plot (dispatches on mode) -----------------

  plot_obj <- reactive({

    if (input$mode == "transect") {

      # ============= MODE 1: fixed transect, vary station =============
      req(input$transect_select)

      transect_data <- processed_data() %>%
        filter(Transect == input$transect_select, !is.na(StationNumber))

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
      validate(need(
        nrow(bathymetry) >= 2,
        "This transect has only one station with data. The 'By Transect' view needs at least two stations along the transect to draw a section — try a different transect, or use 'By Station' mode instead."
      ))

      grid <- expand.grid(
        X = seq(min(transect_data$X), max(transect_data$X), length.out = input$grid_res %||% 300),
        Depth = seq(min_depth, max_depth, length.out = input$grid_res %||% 300)
      )

      coordinates(idw_data) <- ~ X + Depth
      coordinates(grid) <- ~ X + Depth

      idw_model <- gstat(
        formula = Value ~ 1, locations = idw_data,
        nmax = input$idw_nmax %||% 12,
        set = list(idp = input$idw_power %||% 2)
      )
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
        geom_point(
          data = observation_points %>% filter(!ParameterMissing),
          aes(x = X, y = Depth), shape = 21, size = 2.2, stroke = 0.5, fill = "white"
        ) +
        geom_point(
          data = observation_points %>% filter(ParameterMissing),
          aes(x = X, y = Depth), shape = 21, size = 3, stroke = 0.8, fill = "white", colour = "black"
        ) +
        geom_point(
          data = observation_points %>% filter(ParameterMissing),
          aes(x = X, y = Depth), shape = 4, size = 2, stroke = 0.8, colour = "black"
        ) +
        scale_y_reverse(breaks = depth_axis_breaks(min_depth, max_depth), expand = c(0, 0)) +
        scale_x_continuous(breaks = seq_along(station_order), labels = station_order, expand = c(0, 0)) +
        scale_fill_gradientn(
          colours = idw_palette, limits = c(parameter_min, parameter_max),
          oob = scales::squish, name = input$parameter_column
        ) +
        labs(x = NULL, y = "Depth (m)", title = paste("Transect", input$transect_select)) +
        section_theme()

      attr(p, "summary") <- paste0(
        "Mode: By Transect\n",
        "Transect: ", input$transect_select, "\n",
        "Stations: ", paste(station_order, collapse = ", "), "\n",
        "Parameter: ", input$parameter_column, "\n",
        "Depth range: ", round(min_depth, 1), " - ", round(max_depth, 1), " m\n",
        "Parameter range: ", round(parameter_min, 3), " - ", round(parameter_max, 3)
      )

      p

    } else {

      # ============= MODE 2: fixed station, vary transect =============
      req(input$station_select)

      station_data <- processed_data() %>%
        filter(StationNumber == input$station_select, !is.na(Transect))

      validate(need(nrow(station_data) > 0, "No data found for the selected station."))

      detected_transects <- numeric_sort(unique(station_data$Transect))
      station_data$Transect <- factor(station_data$Transect, levels = detected_transects)
      station_data <- station_data %>% mutate(X = as.numeric(Transect))

      idw_data <- station_data %>% filter(!is.na(Value), is.finite(Value))
      validate(need(nrow(idw_data) >= 3, "Not enough valid observations for IDW interpolation (need at least 3)."))

      x_min <- min(station_data$X); x_max <- max(station_data$X)
      y_min <- min(station_data$Depth); y_max <- max(station_data$Depth)

      grid <- expand.grid(
        X = seq(x_min, x_max, length.out = input$grid_res %||% 300),
        Depth = seq(y_min, y_max, length.out = input$grid_res %||% 300)
      )

      coordinates(idw_data) <- ~ X + Depth
      coordinates(grid) <- ~ X + Depth

      idw_model <- gstat(
        formula = Value ~ 1, locations = idw_data,
        nmax = input$idw_nmax %||% 12,
        set = list(idp = input$idw_power %||% 2)
      )
      idw_plot <- as.data.frame(predict(idw_model, newdata = grid))
      names(idw_plot)[names(idw_plot) == "var1.pred"] <- "Value"

      available_depths <- sort(unique(station_data$Depth))

      name_map <- transect_name_map()
      transect_label_vector <- sapply(levels(station_data$Transect), function(x) {
        if (x %in% names(name_map)) name_map[[x]] else x
      })

      parameter_min <- min(idw_data$Value, na.rm = TRUE)
      parameter_max <- max(idw_data$Value, na.rm = TRUE)

      p <- ggplot() +
        geom_raster(data = idw_plot, aes(x = X, y = Depth, fill = Value)) +
        geom_point(
          data = station_data %>% filter(!is.na(Value)),
          aes(x = X, y = Depth), shape = 21, size = 2.2, stroke = 0.5, fill = "white"
        ) +
        scale_y_reverse(breaks = available_depths, expand = c(0, 0)) +
        scale_fill_gradientn(
          colours = idw_palette, limits = c(parameter_min, parameter_max),
          oob = scales::squish, name = input$parameter_column
        ) +
        scale_x_continuous(
          breaks = seq_along(levels(station_data$Transect)),
          labels = transect_label_vector, expand = c(0, 0)
        ) +
        labs(x = NULL, y = "Depth (m)", title = paste("Station", input$station_select)) +
        section_theme()

      attr(p, "summary") <- paste0(
        "Mode: By Station\n",
        "Station: ", input$station_select, "\n",
        "Transects: ", paste(transect_label_vector, collapse = ", "), "\n",
        "Parameter: ", input$parameter_column, "\n",
        "Depth range: ", round(y_min, 1), " - ", round(y_max, 1), " m\n",
        "Parameter range: ", round(parameter_min, 3), " - ", round(parameter_max, 3)
      )

      p
    }
  })

  output$section_plot <- renderPlot({
    req(plot_obj())
    plot_obj()
  })

  output$summary_text <- renderText({
    p <- plot_obj()
    attr(p, "summary")
  })

  # ---- 6. Download handler ------------------------------------

  output$download_plot <- downloadHandler(
    filename = function() {
      base <- if (input$mode == "transect") {
        paste0(input$transect_select, "_", gsub("[^A-Za-z0-9]+", "_", input$parameter_column))
      } else {
        paste0(input$station_select, "_", gsub("[^A-Za-z0-9]+", "_", input$parameter_column))
      }
      ext <- if (identical(input$export_format, "png")) "png" else "tif"
      paste0(base, "_Vertical_Section.", ext)
    },
    content = function(file) {
      fmt <- input$export_format %||% "tiff"
      ggsave(
        filename = file,
        plot = plot_obj(),
        device = fmt,
        width = input$export_width %||% 10,
        height = input$export_height %||% 7,
        units = "in",
        dpi = input$export_dpi %||% 600,
        compression = if (fmt == "tiff") "lzw" else NULL
      )
    }
  )
}

# `%||%` helper (in case an older R/rlang without it is used)
`%||%` <- function(a, b) if (is.null(a)) b else a

shinyApp(ui, server)

