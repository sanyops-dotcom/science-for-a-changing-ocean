# =============================================================
#  Excel Lookup & Merge Tool  (R Shiny)
# =============================================================
#  What it does:
#   1. You upload an INPUT excel file and an OUTPUT excel file.
#   2. You choose (via dropdowns, populated from the real column
#      names in your files):
#        - Key column in INPUT   (e.g. Name / ID)
#        - Key column in OUTPUT  (should represent the same thing)
#        - Source column in INPUT  (the data you want to copy)
#        - Target column in OUTPUT (where it should be pasted)
#   3. For every row in OUTPUT, the app looks for a matching key
#      value in INPUT:
#        - Match found  -> copy that row's Source value into Target
#        - No match     -> leave Target blank for that row
#   4. You download the finished OUTPUT file as .xlsx
#
#  Required packages (install once):
#     install.packages(c("shiny","readxl","openxlsx","DT"))
# =============================================================

library(shiny)
library(readxl)
library(openxlsx)
library(DT)

# ---------------------------- UI ------------------------------
ui <- fluidPage(
  titlePanel("Excel Lookup & Merge Tool"),

  sidebarLayout(
    sidebarPanel(
      width = 4,

      h4("1. Upload files"),
      fileInput("inputFile", "Input Excel file (data source)",
                accept = c(".xlsx", ".xls")),
      selectInput("inputSheet", "Input sheet", choices = NULL),

      fileInput("outputFile", "Output Excel file (to be updated)",
                accept = c(".xlsx", ".xls")),
      selectInput("outputSheet", "Output sheet", choices = NULL),

      hr(),
      h4("2. Choose columns"),

      selectInput("keyColInput", "Key column in INPUT file (e.g. Name/ID)",
                  choices = NULL),
      selectInput("keyColOutput", "Key column in OUTPUT file (should match the same thing)",
                  choices = NULL),
      selectInput("sourceCol", "Source column in INPUT (data to copy)",
                  choices = NULL),
      selectizeInput("targetCol",
                      "Target column in OUTPUT (where data is pasted). Type a new name if it doesn't exist yet.",
                      choices = NULL, options = list(create = TRUE)),

      hr(),
      actionButton("process", "Run Merge", class = "btn-primary"),
      br(), br(),
      downloadButton("downloadData", "Download Updated Output File")
    ),

    mainPanel(
      width = 8,
      h4("Key column preview (check both look the same before running)"),
      fluidRow(
        column(6, strong("Input key values (first 15):"), verbatimTextOutput("inputKeyPreview")),
        column(6, strong("Output key values (first 15):"), verbatimTextOutput("outputKeyPreview"))
      ),
      hr(),
      h4("Preview of result (after Run Merge)"),
      DTOutput("previewTable")
    )
  )
)

# ---------------------------- SERVER ----------------------------
server <- function(input, output, session) {

  # ---- Update sheet dropdowns when a file is uploaded ----
  observeEvent(input$inputFile, {
    req(input$inputFile)
    sheets <- readxl::excel_sheets(input$inputFile$datapath)
    updateSelectInput(session, "inputSheet", choices = sheets, selected = sheets[1])
  })

  observeEvent(input$outputFile, {
    req(input$outputFile)
    sheets <- readxl::excel_sheets(input$outputFile$datapath)
    updateSelectInput(session, "outputSheet", choices = sheets, selected = sheets[1])
  })

  # ---- Read the two files reactively ----
  inputData <- reactive({
    req(input$inputFile, input$inputSheet)
    readxl::read_excel(input$inputFile$datapath, sheet = input$inputSheet)
  })

  outputData <- reactive({
    req(input$outputFile, input$outputSheet)
    readxl::read_excel(input$outputFile$datapath, sheet = input$outputSheet)
  })

  # ---- Update column dropdowns once data is loaded ----
  observeEvent(inputData(), {
    cols <- names(inputData())
    updateSelectInput(session, "keyColInput", choices = cols)
    updateSelectInput(session, "sourceCol", choices = cols)
  })

  observeEvent(outputData(), {
    cols <- names(outputData())
    updateSelectInput(session, "keyColOutput", choices = cols)
    updateSelectizeInput(session, "targetCol", choices = cols, server = FALSE)
  })

  # ---- Debug preview: show raw key values so you can spot mismatches ----
  output$inputKeyPreview <- renderPrint({
    req(inputData(), input$keyColInput)
    if (input$keyColInput %in% names(inputData())) {
      print(head(inputData()[[input$keyColInput]], 15))
    }
  })

  output$outputKeyPreview <- renderPrint({
    req(outputData(), input$keyColOutput)
    if (input$keyColOutput %in% names(outputData())) {
      print(head(outputData()[[input$keyColOutput]], 15))
    }
  })

  # ---- Store the merged result ----
  mergedResult <- reactiveVal(NULL)

  observeEvent(input$process, {
    req(inputData(), outputData(),
        input$keyColInput, input$keyColOutput,
        input$sourceCol, input$targetCol)

    inDf  <- inputData()
    outDf <- outputData()

    # Basic column existence checks
    if (!(input$keyColInput %in% names(inDf))) {
      showModal(modalDialog(title = "Error",
                             paste("Key column not found in Input file:", input$keyColInput)))
      return(NULL)
    }
    if (!(input$keyColOutput %in% names(outDf))) {
      showModal(modalDialog(title = "Error",
                             paste("Key column not found in Output file:", input$keyColOutput)))
      return(NULL)
    }
    if (!(input$sourceCol %in% names(inDf))) {
      showModal(modalDialog(title = "Error",
                             paste("Source column not found in Input file:", input$sourceCol)))
      return(NULL)
    }

    # If target column doesn't exist yet in output, create it (blank)
    if (!(input$targetCol %in% names(outDf))) {
      outDf[[input$targetCol]] <- NA
    }

    # ---- The core matching logic ----
    # Normalize keys before matching: convert to text, trim spaces, ignore case.
    # This avoids "no match" issues caused by trailing spaces, case differences,
    # or one file storing the key as text and the other as a number.
    normalize_key <- function(x) trimws(toupper(as.character(x)))

    outKeysNorm <- normalize_key(outDf[[input$keyColOutput]])
    inKeysNorm  <- normalize_key(inDf[[input$keyColInput]])

    idx <- match(outKeysNorm, inKeysNorm)
    matched <- !is.na(idx)

    # Fill target column: matched rows get the source value, unmatched rows are blanked
    outDf[[input$targetCol]] <- NA
    outDf[[input$targetCol]][matched] <- inDf[[input$sourceCol]][idx[matched]]

    mergedResult(outDf)

    n_total   <- nrow(outDf)
    n_matched <- sum(matched)
    n_missing <- n_total - n_matched

    # Popup summary
    showModal(modalDialog(
      title = "Merge complete - Thanks!",
      HTML(paste0(
        "<b>Total rows in Output file:</b> ", n_total, "<br>",
        "<b>Matches found:</b> ", n_matched, "<br>",
        "<b>Not found (left blank):</b> ", n_missing
      )),
      easyClose = TRUE,
      footer = modalButton("OK")
    ))

    if (n_missing > 0) {
      showNotification(
        paste(n_missing, "row(s) had no matching name/ID in the Input file - left blank."),
        type = "warning", duration = 8
      )
    } else {
      showNotification("All rows matched successfully!", type = "message", duration = 5)
    }
  })

  # ---- Preview table ----
  output$previewTable <- renderDT({
    req(mergedResult())
    datatable(mergedResult(), options = list(pageLength = 10, scrollX = TRUE))
  })

  # ---- Download handler ----
  output$downloadData <- downloadHandler(
    filename = function() {
      base <- tools::file_path_sans_ext(input$outputFile$name)
      paste0(base, "_updated.xlsx")
    },
    content = function(file) {
      req(mergedResult())
      openxlsx::write.xlsx(mergedResult(), file, overwrite = TRUE)
    }
  )
}

# ---------------------------- RUN APP ----------------------------
# launch.browser = TRUE makes this open automatically in your default
# web browser as soon as you source() or run this file.
shinyApp(ui = ui, server = server, options = list(launch.browser = TRUE))

