# Comprehensive Data Analysis with Auto-Profiling

A robust, production-level Python script for automated exploratory data analysis (EDA) that generates comprehensive profiling reports for any tabular dataset.

## 🎯 Features

- **Automated EDA**: Performs comprehensive exploratory data analysis on CSV and Parquet files
- **Multiple Profiling Libraries**: Integrates `ydata-profiling` and `Evidently` for detailed reports
- **Data Quality Assessment**: Identifies and handles common data quality issues
- **Type Detection**: Automatically detects and converts mixed data types
- **Outlier Detection**: Uses IQR method to identify statistical outliers
- **Missing Value Analysis**: Comprehensive missing data profiling
- **CLI Interface**: Easy-to-use command-line interface for automation
- **Production Ready**: Full typing, logging, error handling, and modular design

## 📦 Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Install Dependencies

```bash
# Install required packages
pip install pandas numpy ydata-profiling evidently pyarrow

# Or install from requirements.txt (create this file with the packages above)
pip install -r requirements.txt
```

### Required Python Packages

```
evidently                         0.7.7
numpy                             2.1.3
ydata-core                        0.7.0
ydata-datascience                 0.7.0
ydata-profiling                   4.16.1
ydata-sdk                         3.0.8
pandas                            2.3.0
pyarrow                           18.1.0
```

## 🚀 Quick Start

### Basic Usage

```bash
# Analyze the sample dataset
python eda_report.py sample_dataset.csv

# Analyze with custom output directory
python eda_report.py sample_dataset.csv --output-dir my_reports

# Enable debug logging
python eda_report.py sample_dataset.csv --log-level DEBUG
```

### Generate Sample Dataset

First, generate the mock dataset with realistic data quality issues:

```bash
python generate_sample_dataset.py
```

This creates `sample_dataset.csv` with 100 rows containing:
- Mixed data types
- Missing values
- Outliers
- Inconsistent formatting
- High cardinality columns
- Date format variations

### Analyze the Dataset

```bash
python eda_report.py sample_dataset.csv
```

## 📁 Project Structure

```
├── eda_report.py              # Main analysis script
├── generate_sample_dataset.py # Sample data generator
├── sample_dataset.csv         # Mock dataset with quality issues
├── README.md                  # This file
├── requirements.txt           # Python dependencies
├── reports/                   # Generated reports directory
│   ├── ydata_profiling_report.html
│   ├── evidently_data_quality_report.html
│   └── summary_report.txt
└── eda_analysis.log          # Application logs
```

## 🛠️ Command Line Options

```bash
python eda_report.py [-h] [--output-dir OUTPUT_DIR] [--log-level LOG_LEVEL] 
                     [--skip-evidently] [--skip-ydata] input_file

positional arguments:
  input_file            Path to the input dataset (CSV or Parquet)

optional arguments:
  -h, --help            Show help message and exit
  --output-dir, -o      Output directory for reports (default: reports)
  --log-level, -l       Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL
  --skip-evidently      Skip Evidently report generation
  --skip-ydata          Skip YData profiling report generation
```

### Examples

```bash
# Basic analysis
python eda_report.py data.csv

# Custom output directory with debug logging
python eda_report.py data.parquet -o custom_reports -l DEBUG

# Skip Evidently reports (faster for large datasets)
python eda_report.py large_dataset.csv --skip-evidently

# Only generate summary and Evidently reports
python eda_report.py data.csv --skip-ydata
```

## 📊 Generated Reports

### 1. YData Profiling Report (`ydata_profiling_report.html`)
- **Overview**: Dataset summary, missing values, duplicates
- **Variables**: Detailed analysis of each column
- **Interactions**: Correlation matrices and scatter plots
- **Missing**: Missing value patterns and heatmaps
- **Samples**: Sample data and duplicates

### 2. Evidently Data Quality Report (`evidently_data_quality_report.html`)
- **Data Quality Metrics**: Completeness, validity, consistency
- **Column-level Analysis**: Type detection and quality scores
- **Data Drift Detection**: Statistical drift analysis
- **Anomaly Detection**: Outlier identification

### 3. Summary Report (`summary_report.txt`)
- **Dataset Overview**: Shape, memory usage, duplicates
- **Column Information**: Type classification and counts
- **Missing Values**: Percentage and patterns
- **Quality Issues**: High cardinality warnings and recommendations

## 🔧 Data Quality Issues Handled

### Automatic Detection and Handling

1. **Mixed Data Types**
   - Detects numeric values stored as strings
   - Converts currency formatted numbers ($1,234.56)
   - Handles percentage and comma-separated values

2. **Date/Time Parsing**
   - Multiple date format detection (ISO, US, European)
   - Automatic conversion to datetime objects
   - Handles missing and malformed dates

3. **Missing Value Analysis**
   - Comprehensive missing pattern analysis
   - Visualization of missing data relationships
   - Missing value percentage calculations

4. **Outlier Detection**
   - IQR-based outlier identification
   - Statistical bounds calculation
   - Outlier count and percentage reporting

5. **Categorical Data Issues**
   - High cardinality detection
   - Case sensitivity variations
   - Leading/trailing whitespace handling

## 🏗️ Architecture

### Modular Design

The script follows a modular architecture with separate functions for each concern:

- `setup_logging()`: Configurable logging system
- `validate_file_path()`: File validation and format checking
- `load_dataset()`: Robust data loading with encoding detection
- `perform_basic_eda()`: Core exploratory data analysis
- `handle_data_quality_issues()`: Data quality assessment and basic cleaning
- `generate_ydata_profile()`: YData profiling report generation
- `generate_evidently_report()`: Evidently report generation
- `create_summary_report()`: Summary statistics and insights

### Error Handling

- Comprehensive try-catch blocks
- Informative error messages
- Graceful degradation (continues if one report fails)
- File encoding detection and fallback

### Logging

- Configurable log levels
- File and console logging
- Operation tracking and timing
- Error and warning capture

## 📈 Sample Dataset Details

The included `sample_dataset.csv` contains realistic data quality issues:

### Columns and Issues

1. **customer_id**: High cardinality with some duplicates
2. **age**: Numeric with outliers (150, 200, 5) and missing values
3. **income**: Mixed formats ($, commas) and missing values
4. **registration_date**: Multiple date formats and missing values
5. **category**: Categorical with typos and case variations
6. **product_rating**: Mixed numeric/text ratings
7. **email**: Valid/invalid email formats
8. **purchase_amount**: Currency formatting and negative values
9. **country**: Inconsistent country naming
10. **phone_number**: Multiple phone number formats
11. **status**: Case inconsistencies and extra spaces
12. **score**: Numeric with impossible values (150, -50, 999)

### Statistics
- **Rows**: 100
- **Columns**: 12
- **Missing Values**: ~15% across various columns
- **Outliers**: Multiple columns with statistical outliers
- **Data Types**: Mixed (numeric, categorical, datetime, text)

## 🔍 Use Cases

### Business Applications

1. **Data Quality Assessment**: Before data modeling or analysis
2. **Data Discovery**: Understanding new datasets quickly
3. **Consulting Projects**: Automated client data profiling
4. **Data Pipeline Validation**: Quality checks in ETL processes
5. **Regulatory Compliance**: Data quality documentation

### Research Applications

1. **Exploratory Data Analysis**: Initial dataset understanding
2. **Data Preparation**: Identifying cleaning requirements
3. **Feature Engineering**: Understanding variable relationships
4. **Model Preparation**: Data quality for ML pipelines

## 🎯 Best Practices

### Performance Optimization

- Use `--skip-ydata` for very large datasets (YData profiling can be slow)
- Consider sampling large datasets before profiling
- Use Parquet format for better performance with large files

### Memory Management

- Monitor memory usage in logs
- For large datasets, consider processing in chunks
- Use appropriate data types after cleaning

### Automation

- Integrate into data pipelines using CLI interface
- Use logging output for monitoring and alerting
- Configure output directories for organized reporting

## 🤝 Contributing

### Development Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run tests on sample data: `python eda_report.py sample_dataset.csv`

### Code Standards

- Follow PEP8 style guidelines
- Include type hints for all functions
- Add comprehensive docstrings
- Implement proper error handling
- Add logging for all major operations

## 📝 License

This project is provided as-is for educational and professional use. Feel free to modify and adapt for your specific needs.

## 🆘 Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed
   ```bash
   pip install ydata-profiling evidently pandas numpy pyarrow
   ```

2. **Memory Issues**: For large datasets, use sampling or skip intensive reports
   ```bash
   python eda_report.py large_file.csv --skip-ydata
   ```

3. **File Encoding**: Script handles multiple encodings automatically

4. **Permission Errors**: Ensure write permissions for output directory

### Getting Help

- Check the log file `eda_analysis.log` for detailed error information
- Use `--log-level DEBUG` for verbose output
- Ensure input file format is supported (CSV or Parquet)

## 🔮 Future Enhancements

- Support for additional file formats (Excel, JSON)
- Custom profiling configurations
- Interactive report generation
- Integration with cloud storage services
- Advanced anomaly detection algorithms
- Automated data cleaning suggestions