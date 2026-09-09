# ============================================================
# CTD .ASC FILE TO EXCEL DEPTH EXTRACTOR
# ============================================================
#
# Purpose:
# Read a CTD .asc file, identify the parameters automatically,
# separate downcast and upcast data, extract observations close
# to selected standard depths, and save the result as Excel.
#
# Standard depths:
# 5, 10, 20, 30, 50, 75, 100, 200, 500, 750, 1000 m
#
# The actual minimum and maximum depths are also included.
#
# Both downcast and upcast are retained separately.
#
# ============================================================


# ============================================================
# 1. REQUIRED PACKAGE
# ============================================================

if (!requireNamespace("writexl", quietly = TRUE)) {
  
  install.packages("writexl")
  
}

library(writexl)


# ============================================================
# 2. SELECT THE CTD .ASC FILE
# ============================================================

asc_file <- file.choose()


# ============================================================
# 3. CREATE OUTPUT FILE NAME
# ============================================================

output_file <- file.path(
  
  dirname(asc_file),
  
  paste0(
    tools::file_path_sans_ext(
      basename(asc_file)
    ),
    "_selected_depths.xlsx"
  )
  
)


# ============================================================
# 4. READ THE CTD FILE
# ============================================================

cat("\n")
cat("Reading CTD file...\n")
cat(basename(asc_file), "\n\n")


# Read the complete file as text
all_lines <- readLines(
  asc_file,
  warn = FALSE
)


# Remove empty lines
all_lines <- all_lines[
  nzchar(trimws(all_lines))
]


if (length(all_lines) < 2) {
  
  stop(
    "\nERROR: The ASC file does not contain enough data.\n"
  )
  
}


# ============================================================
# 5. FIND THE HEADER
# ============================================================
#
# The header contains parameter names such as:
#
# DepSM
# Tv290C
# Potemp090C
# Sal00
# Density00
# ...
#
# We identify the line containing "DepSM".
#
# ============================================================


header_index <- which(
  grepl(
    "(^|[[:space:]])DepSM([[:space:]]|$)",
    all_lines[1:min(length(all_lines), 100)],
    ignore.case = TRUE
  )
)


if (length(header_index) == 0) {
  
  stop(
    paste0(
      "\nERROR: Could not find the CTD header containing 'DepSM'.\n",
      "Please check the ASC file format."
    )
  )
  
}


header_index <- header_index[1]


header_line <- all_lines[header_index]


# ============================================================
# 6. READ THE HEADER
# ============================================================
#
# CTD files may use tabs or spaces between parameter names.
#
# Therefore, use one-or-more whitespace characters as the
# separator.
#
# ============================================================


column_names <- strsplit(
  trimws(header_line),
  "[[:space:]]+"
)[[1]]


# Remove empty names
column_names <- column_names[
  nzchar(column_names)
]


# Make duplicate names unique
column_names <- make.unique(
  column_names,
  sep = "_"
)


cat("Number of CTD parameters detected:",
    length(column_names), "\n\n")


# ============================================================
# 7. READ THE DATA LINES
# ============================================================

data_lines <- all_lines[
  (header_index + 1):length(all_lines)
]


# Keep only lines that contain numerical data.
#
# A valid CTD data line should begin with a number because
# DepSM is the first parameter.

data_lines <- data_lines[
  grepl(
    "^[[:space:]]*[-+]?([0-9]*\\.?[0-9]+|[0-9]+\\.?[0-9]*)([eE][-+]?[0-9]+)?",
    data_lines
  )
]


if (length(data_lines) == 0) {
  
  stop(
    "\nERROR: No numerical CTD data rows were found.\n"
  )
  
}


# ============================================================
# 8. CONVERT DATA LINES INTO A DATA FRAME
# ============================================================
#
# The separator is one-or-more spaces/tabs.
#
# This allows the code to work whether the ASC file uses
# spaces, tabs, or a mixture of both.
#
# ============================================================


raw_data <- read.table(
  
  text = data_lines,
  
  header = FALSE,
  
  sep = "",
  
  stringsAsFactors = FALSE,
  
  check.names = FALSE,
  
  fill = TRUE,
  
  comment.char = ""
  
)

# ============================================================
# 9. CHECK DATA COLUMN COUNT
# ============================================================

if (ncol(raw_data) < length(column_names)) {
  
  stop(
    paste0(
      "\nERROR: The CTD data contain fewer columns than the header.\n",
      "Header columns: ",
      length(column_names),
      "\nData columns: ",
      ncol(raw_data),
      "\n\n",
      "Please check the ASC file format."
    )
  )
  
}


if (ncol(raw_data) > length(column_names)) {
  
  warning(
    paste0(
      "\nWARNING: The data contain ",
      ncol(raw_data),
      " columns, while the header contains ",
      length(column_names),
      " columns.\n",
      "Extra columns will be ignored."
    )
  )
  
  raw_data <- raw_data[
    ,
    seq_len(length(column_names)),
    drop = FALSE
  ]
  
}


# Assign CTD parameter names
colnames(raw_data) <- column_names

# ============================================================
# 10. FIND THE DEPTH COLUMN
# ============================================================


depth_column <- which(
  tolower(trimws(column_names)) == "depsm"
)


if (length(depth_column) == 0) {
  
  stop(
    "\nERROR: The 'DepSM' depth column could not be found.\n"
  )
  
}


depth_column <- depth_column[1]


# ============================================================
# 11. CONVERT ALL DATA TO NUMERIC
# ============================================================
#
# CTD data are numerical.
#
# This also handles scientific notation such as:
#
# 7.2180e+02
#
# ============================================================


for (j in seq_len(ncol(raw_data))) {
  
  raw_data[[j]] <- suppressWarnings(
    as.numeric(
      as.character(raw_data[[j]])
    )
  )
  
}


# ============================================================
# 12. REMOVE ROWS WITHOUT A VALID DEPTH
# ============================================================


raw_data <- raw_data[
  !is.na(raw_data[[depth_column]]),
  ,
  drop = FALSE
]


# Reset row numbers
rownames(raw_data) <- NULL


# Add original file row number
raw_data$OriginalFileRow <- seq_len(
  nrow(raw_data)
)


# ============================================================
# 13. CHECK DATA
# ============================================================


if (nrow(raw_data) == 0) {
  
  stop(
    "\nERROR: No valid depth observations were found.\n"
  )
  
}


# ============================================================
# 14. GET ACTUAL MINIMUM AND MAXIMUM DEPTH
# ============================================================


depth <- raw_data[[depth_column]]


actual_min_depth <- min(
  depth,
  na.rm = TRUE
)


actual_max_depth <- max(
  depth,
  na.rm = TRUE
)


cat("Actual minimum depth:",
    actual_min_depth,
    "m\n")


cat("Actual maximum depth:",
    actual_max_depth,
    "m\n\n")


# ============================================================
# 15. FIND MAXIMUM DEPTH POSITION
# ============================================================
#
# The deepest observation is used as the turning point.
#
# Everything before it = DOWNCAST
# Everything after it  = UPCAST
#
# The maximum-depth observation itself belongs to the
# downcast, and is also used as the starting point of the
# upcast.
#
# ============================================================


max_index <- which.max(
  depth
)


# ============================================================
# 16. CREATE DOWNCAST
# ============================================================


downcast <- raw_data[
  1:max_index,
  ,
  drop = FALSE
]


# ============================================================
# 17. CREATE UPCAST
# ============================================================


if (max_index < nrow(raw_data)) {
  
  upcast <- raw_data[
    max_index:nrow(raw_data),
    ,
    drop = FALSE
  ]
  
} else {
  
  upcast <- raw_data[
    FALSE,
    ,
    drop = FALSE
  ]
  
}


cat("Downcast observations:",
    nrow(downcast),
    "\n")


cat("Upcast observations:",
    nrow(upcast),
    "\n\n")


# ============================================================
# 18. STANDARD DEPTHS
# ============================================================


standard_depths <- c(
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
  1000
)


# ============================================================
# 19. FUNCTION TO SELECT CLOSEST OBSERVATIONS
# ============================================================


select_closest_depths <- function(
    data,
    cast_name,
    standard_depths
) {
  
  
  # ----------------------------------------------------------
  # Check whether data exist
  # ----------------------------------------------------------
  
  if (nrow(data) == 0) {
    
    return(NULL)
    
  }
  
  
  # ----------------------------------------------------------
  # Get depth values
  # ----------------------------------------------------------
  
  d <- data[[depth_column]]
  
  
  # ----------------------------------------------------------
  # Minimum and maximum depth of this cast
  # ----------------------------------------------------------
  
  cast_min <- min(
    d,
    na.rm = TRUE
  )
  
  
  cast_max <- max(
    d,
    na.rm = TRUE
  )
  
  
  # ----------------------------------------------------------
  # Select standard depths that fall within the cast range
  # ----------------------------------------------------------
  
  available_standard_depths <- standard_depths[
    
    standard_depths >= cast_min &
      standard_depths <= cast_max
    
  ]
  
  
  # ----------------------------------------------------------
  # Create target depth list
  # ----------------------------------------------------------
  #
  # Actual minimum
  # Standard depths available
  # Actual maximum
  #
  # ----------------------------------------------------------
  
  targets <- c(
    
    cast_min,
    
    available_standard_depths,
    
    cast_max
    
  )
  
  
  # Remove duplicate target depths
  targets <- unique(
    targets
  )
  
  
  # ----------------------------------------------------------
  # Storage for selected rows
  # ----------------------------------------------------------
  
  selected_rows <- list()
  
  
  # ----------------------------------------------------------
  # Find closest observation for each target
  # ----------------------------------------------------------
  
  for (target in targets) {
    
    
    # Difference between every measured depth and target
    depth_difference <- abs(
      d - target
    )
    
    
    # Closest observation
    closest_index <- which.min(
      depth_difference
    )
    
    
    # Copy selected CTD row
    selected_row <- data[
      closest_index,
      ,
      drop = FALSE
    ]
    
    
    # Add cast information
    selected_row$Cast <- cast_name
    
    
    # Add requested target depth
    selected_row$TargetDepth_m <- target
    
    
    # Add difference between requested and actual depth
    selected_row$DepthDifference_m <-
      depth_difference[closest_index]
    
    
    # Add to list
    selected_rows[[length(selected_rows) + 1]] <- selected_row
    
  }
  
  
  # ----------------------------------------------------------
  # Combine selected rows
  # ----------------------------------------------------------
  
  result <- do.call(
    rbind,
    selected_rows
  )
  
  
  return(result)
  
}


# ============================================================
# 20. SELECT DOWNCAST DEPTHS
# ============================================================


downcast_selected <- select_closest_depths(
  
  data = downcast,
  
  cast_name = "Downcast",
  
  standard_depths = standard_depths
  
)


# ============================================================
# 21. SELECT UPCAST DEPTHS
# ============================================================


upcast_selected <- select_closest_depths(
  
  data = upcast,
  
  cast_name = "Upcast",
  
  standard_depths = standard_depths
  
)


# ============================================================
# 22. COMBINE BOTH CASTS
# ============================================================


selected_data <- rbind(
  downcast_selected,
  upcast_selected
)


# ============================================================
# 23. RESTORE ORIGINAL FILE ORDER
# ============================================================
#
# This is important.
#
# We do NOT sort the data by depth.
#
# The original CTD sequence is retained:
#
# DOWNCAST
#    ↓
# increasing depth
#    ↓
# maximum depth
#    ↓
# UPCAST
#    ↓
# decreasing depth
#
# ============================================================


selected_data <- selected_data[
  
  order(
    selected_data$OriginalFileRow
  ),
  
  ,
  drop = FALSE
  
]


# ============================================================
# 24. REORDER COLUMNS
# ============================================================


# CTD parameter columns
ctd_columns <- column_names[
  column_names %in%
    names(selected_data)
]


final_column_order <- c(
  
  "Cast",
  
  "TargetDepth_m",
  
  "DepSM",
  
  "DepthDifference_m",
  
  ctd_columns,
  
  "OriginalFileRow"
  
)


# Remove duplicate column names
final_column_order <- unique(
  final_column_order
)


# Keep only columns that exist
final_column_order <- final_column_order[
  
  final_column_order %in%
    names(selected_data)
  
]


selected_data <- selected_data[
  ,
  final_column_order,
  drop = FALSE
]


# ============================================================
# 25. WRITE EXCEL FILE
# ============================================================


write_xlsx(
  
  selected_data,
  
  output_file
  
)


# ============================================================
# 26. DISPLAY RESULTS
# ============================================================


cat("\n")
cat("============================================================\n")
cat("CTD PROCESSING COMPLETE\n")
cat("============================================================\n\n")


cat("Input file:\n")
cat(asc_file, "\n\n")


cat("Output file:\n")
cat(output_file, "\n\n")


cat("Total rows exported:",
    nrow(selected_data),
    "\n\n")


cat("Selected observations:\n\n")


print(
  selected_data[
    ,
    c(
      "Cast",
      "TargetDepth_m",
      "DepSM",
      "DepthDifference_m"
    )
  ]
)


cat("\n")
cat("Excel file successfully created.\n")
cat("============================================================\n")
