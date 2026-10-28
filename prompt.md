Prompt: Python Script for Comprehensive Data Analysis with Auto-Profiling

You are an expert Python developer and data analyst. Your task is to create a modular, reusable, and production-level Python script that performs comprehensive exploratory data analysis (EDA) on any tabular dataset, automatically generating profiling reports using modern Python libraries.
🎯 Objectives
1. Build a Python script that:
   * Accepts a dataset (CSV or Parquet) as input.
   * Performs automated exploratory analysis using libraries like:
      * pandas-profiling (now called ydata-profiling)
      * Evidently for data quality and drift checks
   * Logs all major steps with logging.
   * Is fully typed using type hints.
   * Includes well-written docstrings for all functions and the main module.
   * Handles common data quality issues (missing values, type mismatches, outliers).
   * Generates an HTML report of the dataset analysis.
   * Offers CLI usage (argparse) for easy automation in consulting projects.
2. Also generate a mock dataset with 100 rows and diverse real-world issues:
   * Missing values
   * Mixed data types
   * High cardinality columns
   * Categorical, numerical, and datetime columns
   * Outliers
📦 Tools to Use
* pandas, numpy
* ydata-profiling (pip install ydata-profiling)
* evidently (pip install evidently)
* logging, argparse
* pyarrow (optional if dealing with Parquet files)
📁 Expected Files
* eda_report.py — Main script with CLI interface and modular code.
* sample_dataset.csv — Mock dataset with realistic issues.
📌 Notes
* Follow PEP8 and best engineering practices.
* Use try/except with informative error messages.
* Modularize the code: at least one function per concern.
* Output profiling reports to reports/ folder, creating it if needed.
✅ Deliverables
Please generate:
1. ✅ A script named eda_report.py as specified above.
2. ✅ A sample dataset file sample_dataset.csv with 100 rows and described anomalies.
3. ✅ Create a robust README.md file.
