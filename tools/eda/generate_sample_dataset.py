#!/usr/bin/env python3
"""
Generate Sample Dataset with Realistic Data Quality Issues

This script creates a mock dataset with various data quality issues
commonly found in real-world datasets for testing the EDA pipeline.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import string

# Set random seeds for reproducibility
np.random.seed(42)
random.seed(42)

def generate_sample_dataset(n_rows: int = 100) -> pd.DataFrame:
    """
    Generate a sample dataset with realistic data quality issues.
    
    Args:
        n_rows: Number of rows to generate
        
    Returns:
        DataFrame with various data quality issues
    """
    data = {}
    
    # 1. Customer ID - High cardinality, some duplicates
    customer_ids = [f"CUST_{i:06d}" for i in range(1, n_rows + 1)]
    # Introduce some duplicates
    for i in range(5):
        customer_ids[random.randint(0, n_rows-1)] = customer_ids[random.randint(0, n_rows-1)]
    data['customer_id'] = customer_ids
    
    # 2. Age - Numeric with outliers and missing values
    ages = np.random.normal(35, 12, n_rows).astype(int)
    ages = np.clip(ages, 18, 80)  # Reasonable range
    # Add some outliers
    ages[random.sample(range(n_rows), 3)] = [150, 200, 5]
    # Add missing values
    missing_indices = random.sample(range(n_rows), 8)
    ages = ages.astype(float)
    ages[missing_indices] = np.nan
    data['age'] = ages
    
    # 3. Income - Numeric with extreme outliers and mixed data types (some as strings)
    incomes = np.random.lognormal(10.5, 0.8, n_rows)
    income_strings = []
    for i, income in enumerate(incomes):
        if i < 80:  # Most values are numeric
            income_strings.append(income)
        elif i < 90:  # Some values are strings with currency symbols
            income_strings.append(f"${income:,.2f}")
        elif i < 95:  # Some values have commas
            income_strings.append(f"{income:,.0f}")
        else:  # Some missing values
            income_strings.append(None)
    data['income'] = income_strings
    
    # 4. Registration Date - Mixed date formats and missing values
    base_date = datetime(2020, 1, 1)
    dates = []
    for i in range(n_rows):
        if i < 70:  # Standard ISO format
            date = base_date + timedelta(days=random.randint(0, 1400))
            dates.append(date.strftime('%Y-%m-%d'))
        elif i < 85:  # Different format
            date = base_date + timedelta(days=random.randint(0, 1400))
            dates.append(date.strftime('%m/%d/%Y'))
        elif i < 95:  # Another format
            date = base_date + timedelta(days=random.randint(0, 1400))
            dates.append(date.strftime('%d-%b-%Y'))
        else:  # Missing values
            dates.append(None)
    data['registration_date'] = dates
    
    # 5. Category - Categorical with high cardinality and typos
    categories = ['Electronics', 'Clothing', 'Books', 'Home & Garden', 'Sports']
    # Add some typos and variations
    categories.extend(['electronics', 'ELECTRONICS', 'Electronic', 'Clothng', 'clothing', 'Book'])
    category_values = [random.choice(categories) for _ in range(n_rows)]
    # Add some missing values
    for i in random.sample(range(n_rows), 7):
        category_values[i] = None
    data['category'] = category_values
    
    # 6. Product Rating - Numeric with some non-numeric values
    ratings = []
    for i in range(n_rows):
        if i < 80:  # Normal ratings 1-5
            ratings.append(random.randint(1, 5))
        elif i < 90:  # Some text ratings
            ratings.append(random.choice(['Excellent', 'Good', 'Poor', 'N/A']))
        elif i < 95:  # Some decimal ratings as strings
            ratings.append(f"{random.uniform(1, 5):.1f}")
        else:  # Missing values
            ratings.append(None)
    data['product_rating'] = ratings
    
    # 7. Email - Text with some invalid formats
    domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'company.com']
    emails = []
    for i in range(n_rows):
        if i < 75:  # Valid emails
            username = ''.join(random.choices(string.ascii_lowercase, k=random.randint(5, 10)))
            domain = random.choice(domains)
            emails.append(f"{username}@{domain}")
        elif i < 85:  # Invalid emails (missing @)
            username = ''.join(random.choices(string.ascii_lowercase, k=random.randint(5, 10)))
            domain = random.choice(domains)
            emails.append(f"{username}.{domain}")
        elif i < 95:  # Invalid emails (multiple @)
            username = ''.join(random.choices(string.ascii_lowercase, k=random.randint(5, 10)))
            domain = random.choice(domains)
            emails.append(f"{username}@@{domain}")
        else:  # Missing values
            emails.append(None)
    data['email'] = emails
    
    # 8. Purchase Amount - Numeric with negative values (returns) and currency formatting
    amounts = np.random.exponential(50, n_rows)
    # Add some negative values (returns)
    for i in random.sample(range(n_rows), 10):
        amounts[i] = -amounts[i]
    
    amount_strings = []
    for i, amount in enumerate(amounts):
        if i < 70:  # Regular numeric values
            amount_strings.append(round(amount, 2))
        elif i < 80:  # Currency formatted strings
            amount_strings.append(f"${amount:.2f}")
        elif i < 90:  # With commas
            amount_strings.append(f"{amount:,.2f}")
        else:  # Missing values
            amount_strings.append(None)
    data['purchase_amount'] = amount_strings
    
    # 9. Country - Categorical with inconsistent naming
    countries = ['USA', 'United States', 'US', 'Canada', 'CA', 'UK', 'United Kingdom', 
                'Germany', 'DE', 'France', 'FR', 'Australia', 'AU']
    country_values = [random.choice(countries) for _ in range(n_rows)]
    # Add some missing values
    for i in random.sample(range(n_rows), 6):
        country_values[i] = None
    data['country'] = country_values
    
    # 10. Phone Number - Mixed formats and invalid numbers
    phones = []
    for i in range(n_rows):
        if i < 40:  # Format: (123) 456-7890
            area = random.randint(200, 999)
            exchange = random.randint(200, 999)
            number = random.randint(1000, 9999)
            phones.append(f"({area}) {exchange}-{number}")
        elif i < 70:  # Format: 123-456-7890
            area = random.randint(200, 999)
            exchange = random.randint(200, 999)
            number = random.randint(1000, 9999)
            phones.append(f"{area}-{exchange}-{number}")
        elif i < 85:  # Format: +1 123 456 7890
            area = random.randint(200, 999)
            exchange = random.randint(200, 999)
            number = random.randint(1000, 9999)
            phones.append(f"+1 {area} {exchange} {number}")
        elif i < 95:  # Invalid formats
            phones.append(random.choice(['123-456', '12345', 'INVALID', '']))
        else:  # Missing values
            phones.append(None)
    data['phone_number'] = phones
    
    # 11. Status - Categorical with extra spaces and case inconsistencies
    statuses = ['Active', 'Inactive', 'Pending', 'Suspended']
    status_values = []
    for i in range(n_rows):
        if i < 80:  # Normal values with some variations
            status = random.choice(statuses)
            if random.random() < 0.2:  # 20% chance of case/space issues
                status = random.choice([
                    status.lower(),
                    status.upper(),
                    f" {status} ",
                    f"{status} "
                ])
            status_values.append(status)
        else:  # Missing values
            status_values.append(None)
    data['status'] = status_values
    
    # 12. Score - Numeric with some impossible values
    scores = np.random.beta(2, 5, n_rows) * 100  # Beta distribution scaled to 0-100
    # Add some impossible values
    scores[random.sample(range(n_rows), 3)] = [150, -50, 999]
    # Add missing values
    for i in random.sample(range(n_rows), 5):
        scores[i] = np.nan
    data['score'] = scores

    # 13. Data two columns with distinct datetime format
    # First column: ISO format, some missing, some invalid
    dt_col1 = []
    for i in range(n_rows):
        if i < 80:
            dt = base_date + timedelta(days=random.randint(0, 1400), hours=random.randint(0, 23), minutes=random.randint(0, 59))
            dt_col1.append(dt.strftime('%Y-%m-%dT%H:%M:%S'))
        elif i < 90:
            # Invalid or corrupted
            dt_col1.append(random.choice(['not_a_date', '2020-13-01T25:61:00', '']))
        else:
            dt_col1.append(None)
    data['event_time_iso'] = dt_col1

    # Second column: European format, some missing, some invalid
    dt_col2 = []
    for i in range(n_rows):
        if i < 75:
            dt = base_date + timedelta(days=random.randint(0, 1400), hours=random.randint(0, 23), minutes=random.randint(0, 59))
            dt_col2.append(dt.strftime('%d/%m/%Y %H:%M'))
        elif i < 90:
            # Invalid or corrupted
            dt_col2.append(random.choice(['32/01/2020 12:00', 'notadate', '']))
        else:
            dt_col2.append(None)
    data['event_time_eu'] = dt_col2
        
    return pd.DataFrame(data)

if __name__ == "__main__":
    # Generate the sample dataset
    df = generate_sample_dataset(100)
    
    # Save to CSV
    df.to_csv('sample_dataset.csv', index=False)
    print("Sample dataset saved as 'sample_dataset.csv'")
    print(f"Dataset shape: {df.shape}")
    print("\nFirst 5 rows:")
    print(df.head())
    print("\nData types:")
    print(df.dtypes)
    print("\nMissing values:")
    print(df.isnull().sum())