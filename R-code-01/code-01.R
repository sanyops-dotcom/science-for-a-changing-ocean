################################################################################
# SANYO OCEAN MAPPING SUITE (SOMS)
# GLOBAL STATISTICS ANALYZER v2.0
#
# Author : Sanyo
################################################################################

cat("PROGRAM STARTED\n")

rm(list = ls())

options(stringsAsFactors = FALSE)

################################################################################
# SECTION 1 : LOAD REQUIRED PACKAGES
################################################################################

required_packages <- c(
  "readxl",
  "dplyr",
  "openxlsx",
  "tcltk"
)

for(pkg in required_packages){
  
  if(!requireNamespace(pkg, quietly = TRUE)){
    
    cat("Installing package :", pkg, "\n")
    
    install.packages(pkg)
    
  }
  
  library(pkg, character.only = TRUE)
  
}

################################################################################
# SECTION 2 : PROGRAM HEADER
################################################################################

cat("\n")
cat("=============================================================\n")
cat("         SANYO OCEAN MAPPING SUITE (SOMS)\n")
cat("          GLOBAL STATISTICS ANALYZER v2.0\n")
cat("=============================================================\n\n")

cat("This utility calculates GLOBAL statistical values\n")
cat("for one or more parameter columns from ALL Excel\n")
cat("files contained inside a selected folder.\n\n")

################################################################################
# SECTION 3 : SELECT WORKING FOLDER
################################################################################

cat("\n")
cat("Select ANY Excel file from your working folder...\n\n")

selected_file <- file.choose()

folder_path <- dirname(selected_file)

folder_name <- basename(folder_path)

cat("---------------------------------------------\n")
cat("Selected Folder\n")
cat("---------------------------------------------\n")
cat(folder_path, "\n\n")

################################################################################
# SECTION 4 : FIND EXCEL FILES
################################################################################

excel_files <- list.files(
    path = folder_path,
    pattern = "\\.xlsx$",
    full.names = TRUE
)

# Exclude previously generated reports
excel_files <- excel_files[
    !grepl("Global Min Max", basename(excel_files), ignore.case = TRUE)
]

if(length(excel_files) == 0){

    stop("No Excel data files found.")

}

cat("---------------------------------------------\n")
cat("Excel Files Found :", length(excel_files), "\n")
cat("---------------------------------------------\n\n")

print(basename(excel_files))

################################################################################
# SECTION 5 : PARAMETER COLUMN INPUT
################################################################################

cat("\n")
cat("Examples of Parameter Columns\n")
cat("---------------------------------------------\n")
cat("5\n")
cat("5:12\n")
cat("5,7,9,12\n")
cat("5:12,15,18\n")
cat("---------------------------------------------\n\n")

parameter_input <- readline(
  "Enter Parameter Columns : "
)

if (nchar(trimws(parameter_input)) == 0) {
  stop("No parameter columns entered.")
}

parameter_cols <- eval(parse(text = paste0("c(", parameter_input, ")")))

parameter_cols <- sort(unique(parameter_cols))

cat("\n")
cat("---------------------------------------------\n")
cat("Selected Columns\n")
cat("---------------------------------------------\n")

print(parameter_cols)

cat("---------------------------------------------\n\n")

################################################################################
# SECTION 6 : VERIFY COLUMN NUMBERS
################################################################################

sample_data <- read_excel(excel_files[1])

if(max(parameter_cols) > ncol(sample_data)){
  
  stop(
    paste(
      "Column",
      max(parameter_cols),
      "does not exist.\nMaximum available column is",
      ncol(sample_data)
    )
  )
  
}
################################################################################
# END OF PART 1
################################################################################

cat("PART 1 COMPLETED\n")

################################################################################
# PART 2 : BUILD GLOBAL DATASET
################################################################################

# List to store all parameter values
global_data <- list()

cat("\n")
cat("=============================================================\n")
cat("               BUILDING GLOBAL DATASET\n")
cat("=============================================================\n")

# -------------------------------------------------------------------------
# Loop through each selected parameter
# -------------------------------------------------------------------------

for(parameter_col in parameter_cols){

    cat("\n")
    cat("-------------------------------------------------------------\n")
    cat("Processing Column :", parameter_col, "\n")
    cat("-------------------------------------------------------------\n")

    all_values <- c()

    parameter_name <- NA

    total_missing <- 0

    total_valid <- 0

    # ---------------------------------------------------------------------
    # Read every Excel file
    # ---------------------------------------------------------------------

    for(file in excel_files){

        file_name <- basename(file)

        cat("Reading :", file_name, "\n")

        data <- read_excel(file)

        # Check column exists
        if(parameter_col > ncol(data)){

            cat("   Skipped (Column Missing)\n")

            next

        }

        # Store parameter name only once
        if(is.na(parameter_name)){

            parameter_name <- names(data)[parameter_col]

        }

        # Convert to numeric
        values <- suppressWarnings(
            as.numeric(data[[parameter_col]])
        )

        valid_values <- values[!is.na(values)]

        missing_values <- sum(is.na(values))

        total_valid <- total_valid + length(valid_values)

        total_missing <- total_missing + missing_values

        # Combine into GLOBAL vector
        all_values <- c(all_values, valid_values)

        cat("   Valid :", length(valid_values),
            " Missing :", missing_values, "\n")

    }

    # Save results into list

    global_data[[as.character(parameter_col)]] <- list(

        Column = parameter_col,

        Parameter = parameter_name,

        Values = all_values,

        N = total_valid,

        Missing = total_missing

    )

    cat("---------------------------------------------\n")
    cat("Parameter :", parameter_name, "\n")
    cat("Global Values :", length(all_values), "\n")
    cat("Missing :", total_missing, "\n")
    cat("---------------------------------------------\n")

}

################################################################################
# PART 2 COMPLETED
################################################################################

cat("\n")
cat("=============================================================\n")
cat("PART 2 COMPLETED SUCCESSFULLY\n")
cat("=============================================================\n")

################################################################################
# PART 3 : CALCULATE GLOBAL STATISTICS
################################################################################

cat("\n")
cat("=============================================================\n")
cat("            CALCULATING GLOBAL STATISTICS\n")
cat("=============================================================\n")

results <- data.frame()

for(item in global_data){

    values <- item$Values

    global_min <- min(values, na.rm = TRUE)

    global_max <- max(values, na.rm = TRUE)

    global_mean <- mean(values, na.rm = TRUE)

    global_sd <- sd(values, na.rm = TRUE)

    mean_minus_sd <- global_mean - global_sd

    mean_plus_sd <- global_mean + global_sd

    cat("\n")
    cat("-------------------------------------------------------------\n")
    cat("Parameter :", item$Parameter, "\n")
    cat("-------------------------------------------------------------\n")

    cat(sprintf("Observations   : %d\n", item$N))
    cat(sprintf("Missing Values : %d\n", item$Missing))
    cat(sprintf("Minimum        : %.6f\n", global_min))
    cat(sprintf("Maximum        : %.6f\n", global_max))
    cat(sprintf("Mean           : %.6f\n", global_mean))
    cat(sprintf("Std. Deviation : %.6f\n", global_sd))
    cat(sprintf("Mean - SD      : %.6f\n", mean_minus_sd))
    cat(sprintf("Mean + SD      : %.6f\n", mean_plus_sd))

results <- rbind(

        results,

        data.frame(

            Column = item$Column,

            Parameter = item$Parameter,

            Observations = item$N,

            Missing = item$Missing,

            Global_Min = global_min,

            Global_Max = global_max,

            Global_Mean = global_mean,

            Global_SD = global_sd,

            Mean_Minus_SD = mean_minus_sd,

            Mean_Plus_SD = mean_plus_sd,

            stringsAsFactors = FALSE

        )

    )

}   # <-- End of for-loop

################################################################################
# CREATE FINAL SUMMARY TABLE
################################################################################

statistics_summary <- results

cat("\n")
cat("=============================================================\n")
cat("          GLOBAL STATISTICS SUMMARY\n")
cat("=============================================================\n\n")

print(statistics_summary)

cat("\n")
cat("=============================================================\n")
cat("PART 3 COMPLETED SUCCESSFULLY\n")
cat("=============================================================\n")

################################################################################
# SECTION 8 : EXPORT RESULTS
################################################################################

folder_name <- basename(folder_path)

output_excel <- file.path(
    folder_path,
    paste0(folder_name, " - Global Statistics.xlsx")
)

openxlsx::write.xlsx(
    results,
    output_excel,
    overwrite = TRUE
)

################################################################################
# SECTION 9 : FINISH
################################################################################

cat("\n")
cat("=============================================================\n")
cat("          ANALYSIS COMPLETED SUCCESSFULLY\n")
cat("=============================================================\n\n")

cat("Output File\n")
cat("---------------------------------------------\n")
cat(output_excel, "\n\n")

cat("Total Excel Files Processed :", length(excel_files), "\n")
cat("Total Parameters Processed  :", length(parameter_cols), "\n\n")

cat("Thank you for using\n")
cat("SANYO OCEAN MAPPING SUITE (SOMS)\n")
cat("GLOBAL STATISTICS ANALYZER v2.0\n")

################################################################################
# POP-UP MESSAGE
################################################################################

tcltk::tkmessageBox(
    title = "SOMS",
    message =
"Global Statistics Analysis Completed Successfully!

Excel report has been saved.

Thank you for using
SANYO OCEAN MAPPING SUITE (SOMS).",
    icon = "info",
    type = "ok"
)

################################################################################
# END PROGRAM
################################################################################

cat("\nProgram Finished Successfully.\n")

