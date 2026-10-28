#!/usr/bin/env python3
"""
Comprehensive Data Analysis with Auto-Profiling

This module provides automated exploratory data analysis (EDA) capabilities
for tabular datasets using modern Python libraries. It generates detailed
profiling reports and handles common data quality issues.

Author: Data Analysis Team
Version: 1.0.0
"""
# pip install pandas numpy ydata-sdk evidently

### USAGE ###
'''
# Basic usage with a CSV file
python eda_report.py your_dataset.csv

# Basic usage with a Parquet file
python eda_report.py your_dataset.parquet

# Specify custom output directory
python eda_report.py your_dataset.csv --output-dir my_reports

# Skip YData profiling (if you only want basic analysis)
python eda_report.py your_dataset.csv --skip-ydata

# Skip Evidently reports (already being skipped due to import issues)
python eda_report.py your_dataset.csv --skip-evidently

# Enable debug logging for troubleshooting
python eda_report.py your_dataset.csv --log-level DEBUG

# Full example with all options
python eda_report.py your_dataset.csv --output-dir detailed_reports --log-level INFO --skip-evidently
'''

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional, Union, Dict, Any, Tuple
import warnings

import pandas as pd
import numpy as np

# YData SDK imports
try:
    from ydata_sdk import ProfileReport
except ImportError:
    try:
        from ydata_profiling import ProfileReport
    except ImportError:
        print("Neither ydata-sdk nor ydata-profiling found. Please install one of them.")
        sys.exit(1)

# Evidently imports - updated for current version
try:
    from evidently.report import Report
    from evidently.metric_preset import DataQualityPreset, DataDriftPreset
    from evidently import ColumnMapping
    EVIDENTLY_AVAILABLE = True
except ImportError:
    try:
        # Try alternative import structure
        from evidently.report import Report
        from evidently.presets import DataQualityPreset, DataDriftPreset
        from evidently import ColumnMapping
        EVIDENTLY_AVAILABLE = True
    except ImportError:
        try:
            # Try another alternative structure
            from evidently.report import Report
            from evidently.metrics import DataQualityPreset, DataDriftPreset
            from evidently import ColumnMapping
            EVIDENTLY_AVAILABLE = True
        except ImportError:
            print("Warning: Evidently not properly installed. Evidently reports will be skipped.")
            EVIDENTLY_AVAILABLE = False

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Configure logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        Configured logger instance
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('eda_analysis.log')
        ]
    )
    return logging.getLogger(__name__)


def validate_file_path(file_path: Union[str, Path]) -> Path:
    """
    Validate if the file path exists and is accessible.
    
    Args:
        file_path: Path to the dataset file
        
    Returns:
        Validated Path object
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is not supported
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    if path.suffix.lower() not in ['.csv', '.parquet']:
        raise ValueError(f"Unsupported file format: {path.suffix}. Only CSV and Parquet files are supported.")
    
    return path


def load_dataset(file_path: Union[str, Path], logger: logging.Logger) -> pd.DataFrame:
    """
    Load dataset from CSV or Parquet file with error handling.
    
    Args:
        file_path: Path to the dataset file
        logger: Logger instance for logging operations
        
    Returns:
        Loaded pandas DataFrame
        
    Raises:
        Exception: If loading fails
    """
    path = validate_file_path(file_path)
    logger.info(f"Loading dataset from: {path}")
    
    try:
        if path.suffix.lower() == '.csv':
            # Try different encodings and separators
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    df = pd.read_csv(path, encoding=encoding, low_memory=False)
                    logger.info(f"Successfully loaded CSV with {encoding} encoding")
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("Unable to load CSV with any supported encoding")
                
        elif path.suffix.lower() == '.parquet':
            df = pd.read_parquet(path)
            logger.info("Successfully loaded Parquet file")
        
        logger.info(f"Dataset shape: {df.shape}")
        logger.info(f"Memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
        
        return df
        
    except Exception as e:
        logger.error(f"Failed to load dataset: {str(e)}")
        raise


def perform_basic_eda(df: pd.DataFrame, logger: logging.Logger) -> Dict[str, Any]:
    """
    Perform basic exploratory data analysis and return summary statistics.
    
    Args:
        df: Input DataFrame
        logger: Logger instance
        
    Returns:
        Dictionary containing basic EDA results
    """
    logger.info("Performing basic EDA...")
    
    eda_results = {
        'shape': df.shape,
        'columns': list(df.columns),
        'dtypes': df.dtypes.to_dict(),
        'missing_values': df.isnull().sum().to_dict(),
        'missing_percentage': (df.isnull().sum() / len(df) * 100).to_dict(),
        'duplicated_rows': df.duplicated().sum(),
        'memory_usage_mb': df.memory_usage(deep=True).sum() / 1024**2
    }
    
    # Identify column types
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    datetime_cols = df.select_dtypes(include=['datetime64']).columns.tolist()
    
    eda_results.update({
        'numeric_columns': numeric_cols,
        'categorical_columns': categorical_cols,
        'datetime_columns': datetime_cols
    })
    
    # Basic statistics for numeric columns
    if numeric_cols:
        eda_results['numeric_stats'] = df[numeric_cols].describe().to_dict()
    
    # Cardinality for categorical columns
    if categorical_cols:
        eda_results['categorical_cardinality'] = {
            col: df[col].nunique() for col in categorical_cols
        }
    
    logger.info(f"Basic EDA completed. Found {len(numeric_cols)} numeric, "
                f"{len(categorical_cols)} categorical, and {len(datetime_cols)} datetime columns")
    
    return eda_results


def handle_data_quality_issues(df: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    """
    Identify and handle common data quality issues.
    
    Args:
        df: Input DataFrame
        logger: Logger instance
        
    Returns:
        DataFrame with basic quality improvements
    """
    logger.info("Analyzing data quality issues...")
    
    df_clean = df.copy()
    issues_found = []
    
    # Check for mixed data types in object columns
    for col in df_clean.select_dtypes(include=['object']).columns:
        # Try to convert to numeric if possible
        numeric_count = pd.to_numeric(df_clean[col], errors='coerce').notna().sum()
        total_non_null = df_clean[col].notna().sum()
        
        if total_non_null > 0 and numeric_count / total_non_null > 0.8:
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
            issues_found.append(f"Converted {col} to numeric (mixed types detected)")
    
    # Identify potential datetime columns
    for col in df_clean.select_dtypes(include=['object']).columns:
        try:
            # Sample a few values to test datetime conversion
            sample_size = min(100, df_clean[col].dropna().shape[0])
            if sample_size > 0:
                sample = df_clean[col].dropna().sample(n=sample_size)
                pd.to_datetime(sample, errors='raise')
                df_clean[col] = pd.to_datetime(df_clean[col], errors='coerce')
                issues_found.append(f"Converted {col} to datetime")
        except:
            continue
    
    # Identify outliers in numeric columns using IQR method
    numeric_cols = df_clean.select_dtypes(include=[np.number]).columns
    outlier_info = {}
    
    for col in numeric_cols:
        Q1 = df_clean[col].quantile(0.25)
        Q3 = df_clean[col].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        outliers = df_clean[(df_clean[col] < lower_bound) | (df_clean[col] > upper_bound)][col]
        if len(outliers) > 0:
            outlier_info[col] = {
                'count': len(outliers),
                'percentage': len(outliers) / len(df_clean) * 100,
                'lower_bound': lower_bound,
                'upper_bound': upper_bound
            }
    
    if issues_found:
        logger.info(f"Data quality issues addressed: {', '.join(issues_found)}")
    
    if outlier_info:
        logger.info(f"Outliers detected in columns: {list(outlier_info.keys())}")
    
    return df_clean


def generate_ydata_profile(df: pd.DataFrame, output_dir: Path, logger: logging.Logger) -> str:
    """
    Generate comprehensive data profiling report using ydata-profiling.
    
    Args:
        df: Input DataFrame
        output_dir: Directory to save the report
        logger: Logger instance
        
    Returns:
        Path to the generated HTML report
    """
    logger.info("Generating ydata-profiling report...")
    
    try:
        # Configure profile settings
        profile_config = {
            "title": "Comprehensive Data Profiling Report",
            "minimal": False,
            "explorative": True,
        }
        
        # Add configuration based on available options
        try:
            profile_config.update({
                "interactions": {"continuous": True},
                "correlations": {
                    "pearson": {"calculate": True},
                    "spearman": {"calculate": True},
                    "kendall": {"calculate": False}  # Kendall can be slow for large datasets
                },
                "missing_diagrams": {"heatmap": True, "dendrogram": True}
            })
        except:
            # If advanced options are not available, use basic config
            pass
        
        profile = ProfileReport(df, **profile_config)
        report_path = output_dir / "ydata_profiling_report.html"
        profile.to_file(report_path)
        
        logger.info(f"YData profiling report saved to: {report_path}")
        return str(report_path)
        
    except Exception as e:
        logger.error(f"Failed to generate ydata-profiling report: {str(e)}")
        raise


def generate_evidently_report(df: pd.DataFrame, output_dir: Path, logger: logging.Logger) -> str:
    """
    Generate data quality report using Evidently.
    
    Args:
        df: Input DataFrame
        output_dir: Directory to save the report
        logger: Logger instance
        
    Returns:
        Path to the generated HTML report
    """
    if not EVIDENTLY_AVAILABLE:
        logger.warning("Evidently not available. Skipping Evidently report generation.")
        return ""
    
    logger.info("Generating Evidently data quality report...")
    
    try:
        # For demonstration, we'll use the same dataset as both reference and current
        # In practice, you'd compare with a reference dataset
        reference_data = df.sample(frac=0.5, random_state=42)
        current_data = df.drop(reference_data.index)
        
        if len(current_data) == 0:
            current_data = df
        
        # Create column mapping
        numeric_features = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_features = df.select_dtypes(include=['object', 'category']).columns.tolist()
        
        column_mapping = ColumnMapping(
            numerical_features=numeric_features,
            categorical_features=categorical_features
        )
        
        # Generate data quality report
        data_quality_report = Report(metrics=[DataQualityPreset()])
        data_quality_report.run(
            reference_data=reference_data,
            current_data=current_data,
            column_mapping=column_mapping
        )
        
        report_path = output_dir / "evidently_data_quality_report.html"
        data_quality_report.save_html(str(report_path))
        
        logger.info(f"Evidently data quality report saved to: {report_path}")
        return str(report_path)
        
    except Exception as e:
        logger.error(f"Failed to generate Evidently report: {str(e)}")
        raise


def create_summary_report(eda_results: Dict[str, Any], output_dir: Path, logger: logging.Logger) -> str:
    """
    Create a summary report with key findings.
    
    Args:
        eda_results: Results from basic EDA
        output_dir: Directory to save the report
        logger: Logger instance
        
    Returns:
        Path to the generated summary report
    """
    logger.info("Creating summary report...")
    
    summary_path = output_dir / "summary_report.txt"
    
    with open(summary_path, 'w') as f:
        f.write("=== COMPREHENSIVE DATA ANALYSIS SUMMARY ===\n\n")
        
        # Dataset overview
        f.write("DATASET OVERVIEW:\n")
        f.write(f"- Shape: {eda_results['shape']}\n")
        f.write(f"- Memory Usage: {eda_results['memory_usage_mb']:.2f} MB\n")
        f.write(f"- Duplicated Rows: {eda_results['duplicated_rows']}\n\n")
        
        # Column information
        f.write("COLUMN INFORMATION:\n")
        f.write(f"- Numeric Columns ({len(eda_results['numeric_columns'])}): {', '.join(eda_results['numeric_columns'])}\n")
        f.write(f"- Categorical Columns ({len(eda_results['categorical_columns'])}): {', '.join(eda_results['categorical_columns'])}\n")
        f.write(f"- Datetime Columns ({len(eda_results['datetime_columns'])}): {', '.join(eda_results['datetime_columns'])}\n\n")
        
        # Missing values
        f.write("MISSING VALUES:\n")
        for col, missing_pct in eda_results['missing_percentage'].items():
            if missing_pct > 0:
                f.write(f"- {col}: {missing_pct:.2f}%\n")
        
        # High cardinality warnings
        if 'categorical_cardinality' in eda_results:
            f.write("\nHIGH CARDINALITY WARNINGS:\n")
            for col, cardinality in eda_results['categorical_cardinality'].items():
                if cardinality > len(eda_results['columns']) * 0.1:  # More than 10% of total rows
                    f.write(f"- {col}: {cardinality} unique values (consider reviewing)\n")
    
    logger.info(f"Summary report saved to: {summary_path}")
    return str(summary_path)


def main():
    """
    Main function to orchestrate the comprehensive data analysis.
    """
    parser = argparse.ArgumentParser(
        description="Comprehensive Data Analysis with Auto-Profiling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python eda_report.py sample_dataset.csv
  python eda_report.py data.parquet --output-dir custom_reports --log-level DEBUG
        """)
    
    parser.add_argument("input_file", help="Path to the input dataset (CSV or Parquet)")
    parser.add_argument("--output-dir", "-o", default="reports", 
                       help="Output directory for reports (default: reports)")
    parser.add_argument("--log-level", "-l", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                       help="Logging level (default: INFO)")
    parser.add_argument("--skip-evidently", action="store_true",
                       help="Skip Evidently report generation")
    parser.add_argument("--skip-ydata", action="store_true",
                       help="Skip YData profiling report generation")
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging(args.log_level)
    
    try:
        # Create output directory
        output_dir = Path(args.output_dir)
        output_dir.mkdir(exist_ok=True, parents=True)
        logger.info(f"Output directory: {output_dir}")
        
        # Load dataset
        df = load_dataset(args.input_file, logger)
        
        # Perform basic EDA
        eda_results = perform_basic_eda(df, logger)
        
        # Handle data quality issues
        df_clean = handle_data_quality_issues(df, logger)
        
        # Generate reports
        generated_reports = []
        
        if not args.skip_ydata:
            try:
                ydata_report = generate_ydata_profile(df_clean, output_dir, logger)
                generated_reports.append(ydata_report)
            except Exception as e:
                logger.error(f"YData profiling failed: {e}")
        
        if not args.skip_evidently and EVIDENTLY_AVAILABLE:
            try:
                evidently_report = generate_evidently_report(df_clean, output_dir, logger)
                if evidently_report:
                    generated_reports.append(evidently_report)
            except Exception as e:
                logger.error(f"Evidently reporting failed: {e}")
        
        # Create summary report
        summary_report = create_summary_report(eda_results, output_dir, logger)
        generated_reports.append(summary_report)
        
        # Final summary
        logger.info("=== ANALYSIS COMPLETE ===")
        logger.info(f"Generated {len(generated_reports)} reports:")
        for report in generated_reports:
            logger.info(f"  - {report}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())