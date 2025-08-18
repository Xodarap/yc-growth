# %%

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import sqlite3
import re
import cpi
#cpi.update()
from datetime import date
import warnings
warnings.filterwarnings('ignore')

# Set plotting style
plt.style.use('default')
sns.set_palette("husl")
plt.rcParams['figure.figsize'] = (12, 8)

# Configure pandas display options to show full content
pd.set_option('display.max_columns', None)
pd.set_option('display.max_colwidth', None)
pd.set_option('display.width', None)
pd.set_option('display.max_rows', 100)

print("📊 Libraries loaded successfully")

# Connect to the SQLite database and load data
conn = sqlite3.connect('yc_valuations.db')

# Load companies data
companies_df = pd.read_sql_query("""
    SELECT company, batch, yc_year, status, final_year, end_reason
    FROM companies
    WHERE status = 'completed'
""", conn)

# Load valuations data with company info
valuations_df = pd.read_sql_query("""
    SELECT v.company, v.year, v.valuation, v.source, v.notes,
           c.yc_year, c.batch, c.final_year, c.end_reason
    FROM valuations v
    JOIN companies c ON v.company = c.company
    WHERE c.status = 'completed'
    ORDER BY c.yc_year, v.company, v.year
""", conn)

conn.close()

print(f"📈 Loaded data for {len(companies_df)} companies")
print(f"📊 Total valuations: {len(valuations_df)}")
print(f"🗓️  YC years range: {companies_df['yc_year'].min()} - {companies_df['yc_year'].max()}")
# %%
def parse_valuation(valuation_str):
    """
    Parse valuation string to numeric value in USD.
    Returns None for non-numeric valuations.
    """
    if pd.isna(valuation_str) or not isinstance(valuation_str, str):
        return None
    
    val_str = valuation_str.lower().strip()
    
    # Skip non-numeric valuations
    skip_phrases = ['not found', 'not disclosed', 'no public', 'undisclosed']
    if any(phrase in val_str for phrase in skip_phrases):
        return None
    
    # Extract numeric value and multiplier
    # Look for patterns like $1.2B, $50M, $120K, etc.
    match = re.search(r'\$(\d+(,\d+)?(\.\d+)?)(-\d+)?(([kmb])|(\s+[mb]illion))?', val_str, re.IGNORECASE)
    if not match:
        return None
    
    try:
        number = float(match.group(1).replace(',', ''))
        multiplier = match.group(5)
        
        if multiplier == 'k':
            return number * 1_000
        elif multiplier == 'm' or multiplier == ' million':
            return number * 1_000_000
        elif multiplier == 'b' or multiplier == ' billion':
            return number * 1_000_000_000
        else:
            return number
    except:
        return None

def format_valuation(value):
    """
    Format numeric valuation to human-readable format like $1.5B, $50M, $120K
    """
    if pd.isna(value) or value == 0:
        return "$0"
    
    if value >= 1e9:
        return f"${value/1e9:.1f}B"
    elif value >= 1e6:
        return f"${value/1e6:.1f}M"
    elif value >= 1e3:
        return f"${value/1e3:.0f}K"
    else:
        return f"${value:,.0f}"

# Test the parsing function
test_values = ['$1.2B', '$50M', '$120K', 'Not found', 'Acquired for $2B', '$95,000', '$595-600M post-money valuation', '$8.2 Million']
for val in test_values:
    print(f"{val} -> {parse_valuation(val)}")
# %%
# Apply valuation parsing
valuations_df['valuation_numeric'] = valuations_df['valuation'].apply(parse_valuation)

# Filter to only numeric valuations
numeric_valuations = valuations_df[valuations_df['valuation_numeric'].notna()].copy()
inflators = {year: cpi.inflate(1, date(year, 6, 1), to=date(2025, 6, 1)) for year in numeric_valuations['year'].unique()}

# Calculate two-year post-founding valuations
def get_two_year_valuation(company_data):
    """
    Get the valuation closest to 2 years after the YC batch year.
    """
    company_data = company_data.sort_values('year')
    yc_year = company_data['yc_year'].iloc[0]
    target_year = yc_year + 2
    
    # Find the closest year to target_year that has a valuation
    available_years = company_data['year'].values
    closest_year = min(available_years, key=lambda x: abs(x - target_year))
    
    # Only consider it valid if within 1 year of target
    if abs(closest_year - target_year) < 1:
        valuation_row = company_data[company_data['year'] == closest_year].iloc[0]
        return {
            'company': valuation_row['company'],
            'yc_year': yc_year,
            'target_year': target_year,
            'actual_year': closest_year,
            'two_year_valuation': valuation_row['valuation_numeric'],
            'two_year_valuation_real': valuation_row['valuation_numeric'] * inflators[closest_year],
            'batch': valuation_row['batch'],
            'end_reason': valuation_row['end_reason'],
            'source': valuation_row['source']
        }
    return None

# Calculate one-year post-founding valuations
def get_one_year_valuation(company_data):
    """
    Get the valuation closest to 1 year after the YC batch year.
    """
    company_data = company_data.sort_values('year')
    yc_year = company_data['yc_year'].iloc[0]
    target_year = yc_year + 1
    
    # Find the closest year to target_year that has a valuation
    available_years = company_data['year'].values
    closest_year = min(available_years, key=lambda x: abs(x - target_year))
    
    # Only consider it valid if within 1 year of target
    if abs(closest_year - target_year) <= 1:
        valuation_row = company_data[company_data['year'] == closest_year].iloc[0]
        return {
            'company': valuation_row['company'],
            'yc_year': yc_year,
            'target_year': target_year,
            'actual_year': closest_year,
            'one_year_valuation': valuation_row['valuation_numeric'],
            'one_year_valuation_real': valuation_row['valuation_numeric'] * inflators[closest_year],
            'batch': valuation_row['batch'],
            'end_reason': valuation_row['end_reason'],
            'source': valuation_row['source']
        }
    return None

# Get two-year valuations for each company
two_year_valuations = []
for company in numeric_valuations['company'].unique():
    company_data = numeric_valuations[numeric_valuations['company'] == company]
    two_year_val = get_two_year_valuation(company_data)
    if two_year_val:
        two_year_valuations.append(two_year_val)

two_year_df = pd.DataFrame(two_year_valuations)

print(f"📊 Found two-year valuations for {len(two_year_df)} companies")
print(f"📈 YC years covered: {two_year_df['yc_year'].min()} - {two_year_df['yc_year'].max()}")

# Get one-year valuations for each company
one_year_valuations = []
for company in numeric_valuations['company'].unique():
    company_data = numeric_valuations[numeric_valuations['company'] == company]
    one_year_val = get_one_year_valuation(company_data)
    if one_year_val:
        one_year_valuations.append(one_year_val)

one_year_df = pd.DataFrame(one_year_valuations)

print(f"📊 Found one-year valuations for {len(one_year_df)} companies")
print(f"📈 YC years covered: {one_year_df['yc_year'].min()} - {one_year_df['yc_year'].max()}")

# Show sample data
print("Two-year data sample:")
print(two_year_df[two_year_df['yc_year'] == 2005].head(10))
print("\nOne-year data sample:")
print(one_year_df[one_year_df['yc_year'] == 2005].head(10))

# %%
import matplotlib.pyplot as plt

# Compute average two-year valuation per batch
# Sort batches by their corresponding year (yc_year)
batch_years = two_year_df.groupby('batch')['yc_year'].min()
avg_2yr_valuation = two_year_df.groupby('batch')['two_year_valuation_real'].mean()
avg_2yr_valuation = avg_2yr_valuation.loc[batch_years.sort_values().index]

plt.figure(figsize=(12, 6))
avg_2yr_valuation.plot(kind='bar')
plt.ylabel('Average 2-Year Valuation (numeric)')
plt.xlabel('YC Batch')
plt.title('Average 2-Year Lag Valuation by YC Batch')
plt.xticks(rotation=45, ha='right')
plt.yscale('log')
plt.tight_layout()
plt.show()

# %%
# Compute average one-year valuation per batch
batch_years_1yr = one_year_df.groupby('batch')['yc_year'].min()
avg_1yr_valuation = one_year_df.groupby('batch')['one_year_valuation_real'].mean()
avg_1yr_valuation = avg_1yr_valuation.loc[batch_years_1yr.sort_values().index]

plt.figure(figsize=(12, 6))
avg_1yr_valuation.plot(kind='bar')
plt.ylabel('Average 1-Year Valuation (numeric)')
plt.xlabel('YC Batch')
plt.title('Average 1-Year Lag Valuation by YC Batch')
plt.xticks(rotation=45, ha='right')
plt.yscale('log')
plt.tight_layout()
plt.show()

# %%
# Show companies with the biggest 2-year growth (by absolute valuation)
top_growth = two_year_df.sort_values('two_year_valuation_real', ascending=False).head(20)
# Add human-readable valuation column
top_growth['valuation_formatted'] = top_growth['two_year_valuation_real'].apply(format_valuation)
print("🚀 Companies with the biggest 2-year growth:")
display(top_growth[['company', 'batch', 'valuation_formatted', 'source']])

# %%
# Show companies with the biggest 1-year growth (by absolute valuation)
top_growth_1yr = one_year_df.sort_values('one_year_valuation_real', ascending=False).head(20)
# Add human-readable valuation column
top_growth_1yr['valuation_formatted'] = top_growth_1yr['one_year_valuation_real'].apply(format_valuation)
print("🚀 Companies with the biggest 1-year growth:")
display(top_growth_1yr[['company', 'batch', 'valuation_formatted', 'source']])

# %%
