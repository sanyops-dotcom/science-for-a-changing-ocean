# ============================================================
# EXCEL STATION NAME ARRANGER
# ============================================================
#
# Expected station-name format:
#     T1 S1
#     T2 S5
#     T10 S3
#
# Sorting priority:
#     1. T number
#     2. S number
#
# If duplicate station names exist, e.g.
#     T3 S2
#     T3 S2
#
# both rows are retained and kept together.
#
# The original Excel file is NOT changed.
# A new arranged Excel file is saved in the same folder.
# ============================================================


# ------------------------------------------------------------
# 1. INSTALL / LOAD REQUIRED PACKAGES
# ------------------------------------------------------------

required_packages <- c("readxl", "openxlsx")

for (pkg in required_packages) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    install.packages(pkg)
  }
}

library(readxl)
library(openxlsx)


# ------------------------------------------------------------
# 2. SELECT THE EXCEL FILE
# ------------------------------------------------------------

input_file <- file.choose()

cat("\nSelected file:\n")
cat(input_file, "\n\n")


# ------------------------------------------------------------
# 3. READ THE EXCEL FILE
# ------------------------------------------------------------

# Read the first sheet
data <- read_excel(input_file)

if (nrow(data) == 0) {
  stop("The selected Excel file contains no data.")
}

if (ncol(data) == 0) {
  stop("The selected Excel file contains no columns.")
}


# ------------------------------------------------------------
# 4. DISPLAY COLUMN NAMES
# ------------------------------------------------------------

cat("Columns found in the Excel file:\n")

for (i in seq_along(names(data))) {
  cat(i, ":", names(data)[i], "\n")
}

cat("\n")


# ------------------------------------------------------------
# 5. FIND THE STATION-NAME COLUMN
# ------------------------------------------------------------
#
# The code looks for a column containing values such as:
#
#     T1 S1
#     T2 S4
#     T10 S3
#
# If more than one column appears suitable, the user can
# select the correct one manually.
# ------------------------------------------------------------

station_pattern <- "^T[0-9]+[[:space:]]+S[0-9]+$"

possible_columns <- c()

for (i in seq_along(data)) {

  values <- as.character(data[[i]])

  values <- trimws(values)

  # Ignore empty cells
  values <- values[!is.na(values) & values != ""]

  if (length(values) > 0) {

    matching_values <- grepl(
      station_pattern,
      values,
      ignore.case = TRUE
    )

    # At least one matching station name
    if (any(matching_values)) {
      possible_columns <- c(possible_columns, i)
    }
  }
}


# ------------------------------------------------------------
# 6. ASK FOR STATION COLUMN IF NECESSARY
# ------------------------------------------------------------

if (length(possible_columns) == 0) {

  cat("Could not automatically identify the station-name column.\n\n")

  station_col <- as.integer(
    readline(
      "Enter the column number containing station names (Tx Sy): "
    )
  )

  if (
    is.na(station_col) ||
    station_col < 1 ||
    station_col > ncol(data)
  ) {
    stop("Invalid column number.")
  }

} else if (length(possible_columns) == 1) {

  station_col <- possible_columns[1]

  cat(
    "Station-name column automatically identified as:",
    names(data)[station_col],
    "\n\n"
  )

} else {

  cat("More than one possible station-name column was found:\n\n")

  for (i in possible_columns) {
    cat(i, ":", names(data)[i], "\n")
  }

  cat("\n")

  station_col <- as.integer(
    readline(
      "Enter the correct station-name column number: "
    )
  )

  if (
    is.na(station_col) ||
    station_col < 1 ||
    station_col > ncol(data)
  ) {
    stop("Invalid column number.")
  }
}


# ------------------------------------------------------------
# 7. EXTRACT STATION NAMES
# ------------------------------------------------------------

station_names <- trimws(
  as.character(data[[station_col]])
)


# ------------------------------------------------------------
# 8. CHECK STATION-NAME FORMAT
# ------------------------------------------------------------
#
# Valid examples:
#
# T1 S1
# T2 S5
# T10 S3
#
# The check starts from Excel row 2 because row 1 is the
# column header and has already been converted to column names
# by read_excel().
# ------------------------------------------------------------

invalid_rows <- which(
  is.na(station_names) |
    station_names == "" |
    !grepl(
      station_pattern,
      station_names,
      ignore.case = TRUE
    )
)

if (length(invalid_rows) > 0) {

  cat("\nERROR: Invalid station name(s) found.\n\n")

  for (r in invalid_rows) {

    excel_row <- r + 1

    cat(
      "Excel row",
      excel_row,
      ":",
      station_names[r],
      "\n"
    )
  }

  cat(
    "\nExpected format is, for example:\n",
    "T1 S1\n",
    "T2 S4\n",
    "T10 S3\n\n"
  )

  stop(
    "Please correct the station names and run the program again."
  )
}


# ------------------------------------------------------------
# 9. EXTRACT T AND S NUMBERS
# ------------------------------------------------------------

# Extract T number
T_number <- as.integer(
  sub(
    "^T([0-9]+)[[:space:]]+S([0-9]+)$",
    "\\1",
    station_names,
    ignore.case = TRUE
  )
)


# Extract S number
S_number <- as.integer(
  sub(
    "^T([0-9]+)[[:space:]]+S([0-9]+)$",
    "\\2",
    station_names,
    ignore.case = TRUE
  )
)


# ------------------------------------------------------------
# 10. CHECK THAT NUMBERS WERE EXTRACTED CORRECTLY
# ------------------------------------------------------------

if (
  any(is.na(T_number)) ||
  any(is.na(S_number))
) {
  stop(
    "Could not extract T and S numbers from one or more station names."
  )
}


# ------------------------------------------------------------
# 11. ADD TEMPORARY SORTING COLUMNS
# ------------------------------------------------------------

data$.__T_ORDER__ <- T_number
data$.__S_ORDER__ <- S_number

# Keep the original row order as a final tie-breaker.
#
# This is important for duplicate stations.
#
# Example:
#
# T2 S3   original row 5
# T2 S3   original row 12
# T2 S3   original row 20
#
# They will remain in that same relative order.

data$.__ORIGINAL_ORDER__ <- seq_len(nrow(data))


# ------------------------------------------------------------
# 12. SORT THE COMPLETE DATASET
# ------------------------------------------------------------
#
# First:
#     T number
#
# Then:
#     S number
#
# Then:
#     original row position
#
# Because the COMPLETE data frame is sorted, every column
# belonging to a station moves together.
# ------------------------------------------------------------

data <- data[
  order(
    data$.__T_ORDER__,
    data$.__S_ORDER__,
    data$.__ORIGINAL_ORDER__
  ),
]


# ------------------------------------------------------------
# 13. REMOVE TEMPORARY COLUMNS
# ------------------------------------------------------------

data$.__T_ORDER__ <- NULL
data$.__S_ORDER__ <- NULL
data$.__ORIGINAL_ORDER__ <- NULL


# ------------------------------------------------------------
# 14. CREATE OUTPUT FILE NAME
# ------------------------------------------------------------

input_folder <- dirname(input_file)

output_file <- file.path(
  input_folder,
  "arranged_station_data.xlsx"
)


# ------------------------------------------------------------
# 15. SAVE ARRANGED DATA
# ------------------------------------------------------------

write.xlsx(
  data,
  output_file,
  overwrite = TRUE
)


# ------------------------------------------------------------
# 16. DISPLAY RESULT
# ------------------------------------------------------------

cat("\n")
cat("============================================================\n")
cat("STATION ARRANGEMENT COMPLETED\n")
cat("============================================================\n\n")

cat(
  "Station column:",
  names(data)[station_col],
  "\n"
)

cat(
  "Number of rows arranged:",
  nrow(data),
  "\n"
)

cat(
  "Output file:\n",
  output_file,
  "\n\n"
)


# ------------------------------------------------------------
# 17. SHOW FIRST 20 ARRANGED STATIONS
# ------------------------------------------------------------

cat("First arranged stations:\n\n")

show_n <- min(20, nrow(data))

for (i in seq_len(show_n)) {
  cat(
    i,
    ":",
    as.character(data[[station_col]][i]),
    "\n"
  )
}

if (nrow(data) > 20) {
  cat("\n... and", nrow(data) - 20, "more rows.\n")
}


cat("\n============================================================\n")
cat("Original Excel file was not changed.\n")
cat("============================================================\n")