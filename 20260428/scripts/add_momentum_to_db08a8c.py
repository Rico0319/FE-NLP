"""
Add momentum_12m_winsorized and volatility_12m to the 20260427ver_commit_db08a8c version.

This is the db08a8c commit version (before dual-class dedup and gvkey fix).
We only add these two control variables, without changing anything else.
No dedup, no ticker/gvkey fixes.
"""

import pandas as pd
import numpy as np

# Load the db08a8c version
db08a8c = pd.read_csv("/home/ricoz/econ_lab/FE-NLP/20260427ver_commit_db08a8c/firm_year_panel_regression_ready.csv")

# Load original panel_final which has momentum/volatility data
orig = pd.read_csv("/home/ricoz/econ_lab/FE-NLP/20260428/firm_year_panel_final.csv")

print(f"db08a8c version: {len(db08a8c)} rows, {len(db08a8c.columns)} columns")
print(f"Original panel_final: {len(orig)} rows, {len(orig.columns)} columns")

# Check if momentum_12m and volatility_12m exist in orig
for col in ['momentum_12m', 'volatility_12m']:
    if col in orig.columns:
        print(f"{col} in orig: {orig[col].notna().sum()}/{len(orig)} non-null")
    else:
        print(f"{col}: NOT FOUND in orig!")

# Merge momentum and volatility from orig to db08a8c
# Use ticker + fiscal_year as merge key
merge_cols = ['ticker', 'fiscal_year']
momentum_data = orig[merge_cols + ['momentum_12m', 'volatility_12m']].copy()

# Remove duplicates from orig (it had dual-class duplicates)
momentum_data = momentum_data.drop_duplicates(subset=merge_cols, keep='first')

print(f"\nMomentum data after dedup: {len(momentum_data)} rows")

# Merge into db08a8c panel
db08a8c = db08a8c.merge(
    momentum_data,
    on=merge_cols,
    how='left'
)

print(f"\nAfter merge: {len(db08a8c)} rows, {len(db08a8c.columns)} columns")

# Check coverage
for col in ['momentum_12m', 'volatility_12m']:
    if col in db08a8c.columns:
        non_null = db08a8c[col].notna().sum()
        print(f"{col}: {non_null}/{len(db08a8c)} non-null ({non_null/len(db08a8c)*100:.1f}%)")

# Create winsorized version of momentum_12m
if 'momentum_12m' in db08a8c.columns:
    raw = db08a8c['momentum_12m'].copy()
    valid_mask = raw.notna()
    if valid_mask.sum() > 0:
        lower = raw[valid_mask].quantile(0.01)
        upper = raw[valid_mask].quantile(0.99)
        db08a8c['momentum_12m_winsorized'] = raw.clip(lower=lower, upper=upper)
        print(f"\nmomentum_12m_winsorized: {db08a8c['momentum_12m_winsorized'].notna().sum()}/{len(db08a8c)} non-null")

# Verify no new duplicates created
pk_dup = db08a8c.groupby(['ticker', 'fiscal_year']).size().reset_index(name='count')
dup_count = (pk_dup['count'] > 1).sum()
print(f"\nDuplicates (ticker + fiscal_year): {dup_count}")

# Verify no accession duplicates created
acc_dup = db08a8c.groupby('accession_number').size().reset_index(name='count')
acc_dup_count = (acc_dup['count'] > 1).sum()
print(f"Duplicates (accession_number): {acc_dup_count}")

# Check specific examples
print("\n=== Sample data ===")
for ticker in ['AAPL', 'MSFT', 'GOOGL', 'WMT', 'BF-B']:
    subset = db08a8c[db08a8c['ticker'] == ticker][['ticker', 'fiscal_year', 'momentum_12m', 'momentum_12m_winsorized', 'volatility_12m']].head(3)
    if len(subset) > 0:
        print(f"\n{ticker}:")
        print(subset.to_string())

# Save
out_path = "/home/ricoz/econ_lab/FE-NLP/20260427ver_commit_db08a8c/firm_year_panel_regression_ready.csv"
db08a8c.to_csv(out_path, index=False)

print(f"\n=== Saved to {out_path} ===")
print(f"Total rows: {len(db08a8c)}")
print(f"Total columns: {len(db08a8c.columns)}")
