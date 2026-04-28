"""
Add momentum_12m and volatility_12m from original panel_final to current panel.

These variables were fetched from CRSP in fetch_additional_controls.py but were
lost during the fiscal year correction process. We'll merge them back from the
original panel_final.csv using (ticker, fiscal_year) as the merge key.
"""

import pandas as pd
import numpy as np

# Load current panel and original panel_final
current = pd.read_csv("/home/ricoz/econ_lab/FE-NLP/20260426/firm_year_panel_regression_ready.csv")
orig = pd.read_csv("/home/ricoz/econ_lab/FE-NLP/20260426/firm_year_panel_final.csv")

print(f"Current panel: {len(current)} rows, {len(current.columns)} columns")
print(f"Original panel_final: {len(orig)} rows, {len(orig.columns)} columns")

# Check if momentum_12m and volatility_12m exist in orig
for col in ['momentum_12m', 'volatility_12m']:
    if col in orig.columns:
        print(f"{col} in orig: {orig[col].notna().sum()}/{len(orig)} non-null")
    else:
        print(f"{col}: NOT FOUND in orig!")

# Merge momentum and volatility from orig to current
# Use ticker + fiscal_year as merge key
merge_cols = ['ticker', 'fiscal_year']
momentum_data = orig[merge_cols + ['momentum_12m', 'volatility_12m']].copy()

# Remove duplicates from orig (it had dual-class duplicates)
momentum_data = momentum_data.drop_duplicates(subset=merge_cols, keep='first')

print(f"\nMomentum data after dedup: {len(momentum_data)} rows")

# Merge into current panel
current = current.merge(
    momentum_data,
    on=merge_cols,
    how='left'
)

print(f"\nAfter merge: {len(current)} rows, {len(current.columns)} columns")

# Check coverage
for col in ['momentum_12m', 'volatility_12m']:
    if col in current.columns:
        non_null = current[col].notna().sum()
        print(f"{col}: {non_null}/{len(current)} non-null ({non_null/len(current)*100:.1f}%)")

# Create winsorized version of momentum_12m
if 'momentum_12m' in current.columns:
    raw = current['momentum_12m'].copy()
    valid_mask = raw.notna()
    if valid_mask.sum() > 0:
        lower = raw[valid_mask].quantile(0.01)
        upper = raw[valid_mask].quantile(0.99)
        current['momentum_12m_winsorized'] = raw.clip(lower=lower, upper=upper)
        print(f"\nmomentum_12m_winsorized: {current['momentum_12m_winsorized'].notna().sum()}/{len(current)} non-null")

# Check specific examples
print("\n=== Sample data ===")
for ticker in ['AAPL', 'MSFT', 'GOOGL', 'WMT']:
    subset = current[current['ticker'] == ticker][['ticker', 'fiscal_year', 'momentum_12m', 'momentum_12m_winsorized', 'volatility_12m']].head(3)
    if len(subset) > 0:
        print(f"\n{ticker}:")
        print(subset.to_string())

# Save
out_path = "/home/ricoz/econ_lab/FE-NLP/20260426/firm_year_panel_regression_ready.csv"
current.to_csv(out_path, index=False)

print(f"\n=== Saved to {out_path} ===")
print(f"Total rows: {len(current)}")
print(f"Total columns: {len(current.columns)}")
