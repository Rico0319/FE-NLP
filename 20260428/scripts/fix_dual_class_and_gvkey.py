"""
Fix dual-class share duplicates and missing gvkey/cik.

Issues:
1. Dual-class shares (GOOG/GOOGL, FOX/FOXA, NWS/NWSA) create duplicate rows
   with same accession_number. Need to keep only primary class.
2. BF-B, BRK-B have gvkey/cik missing because controls use BF.B, BRK.B.
   Need to map tickers and fill in gvkey/cik.
"""

import pandas as pd
import numpy as np

# Load data
df = pd.read_csv("/home/ricoz/econ_lab/FE-NLP/20260426/firm_year_panel_regression_ready.csv")
controls = pd.read_csv("/home/ricoz/econ_lab/FE-NLP/Data_Cleaning_NEW/data/final/control_variables.csv")

print(f"Original rows: {len(df)}")

# ---------------------------------------------------------------------------
# 1. Fix ticker mapping for BF-B and BRK-B
# ---------------------------------------------------------------------------
# BF-B -> BF.B, BRK-B -> BRK.B for controls lookup
ticker_fix_map = {'BF-B': 'BF.B', 'BRK-B': 'BRK.B'}

# Create a column for controls lookup
df['tic_lookup'] = df['ticker'].replace(ticker_fix_map)

# For BF-B and BRK-B, fill gvkey and cik from controls
for tic in ['BF-B', 'BRK-B']:
    lookup_tic = ticker_fix_map[tic]
    # Get gvkey/cik mapping from controls
    ctrl_subset = controls[controls['tic'] == lookup_tic][['gvkey', 'cik']].drop_duplicates()
    if len(ctrl_subset) == 1:
        gvkey_val = ctrl_subset['gvkey'].iloc[0]
        cik_val = ctrl_subset['cik'].iloc[0]
        # Fill in df
        mask = df['ticker'] == tic
        df.loc[mask, 'gvkey'] = gvkey_val
        df.loc[mask, 'cik'] = cik_val
        print(f"Filled {tic}: gvkey={gvkey_val}, cik={cik_val} for {mask.sum()} rows")

# ---------------------------------------------------------------------------
# 2. Handle dual-class shares
# ---------------------------------------------------------------------------
# Define dual-class pairs: (secondary, primary)
# Keep primary, drop secondary
dual_class_pairs = [
    ('GOOG', 'GOOGL'),   # GOOGL is primary (has gvkey/cik)
    ('FOX', 'FOXA'),     # FOXA is primary (has gvkey/cik)
    ('NWS', 'NWSA'),     # NWSA is primary (has gvkey/cik)
]

# For each pair, copy gvkey/cik from primary to secondary, then drop secondary
for secondary, primary in dual_class_pairs:
    # Get primary rows with gvkey/cik
    primary_rows = df[df['ticker'] == primary].copy()
    secondary_rows = df[df['ticker'] == secondary].copy()
    
    if len(secondary_rows) == 0:
        continue
    
    print(f"\n{secondary} -> {primary}:")
    print(f"  {secondary} rows: {len(secondary_rows)}")
    print(f"  {primary} rows: {len(primary_rows)}")
    
    # Check if they share accession numbers
    shared_acc = set(secondary_rows['accession_number']) & set(primary_rows['accession_number'])
    print(f"  Shared accession numbers: {len(shared_acc)}")
    
    # Drop secondary rows that have a matching primary row with same accession
    # This avoids double-counting the same 10-K filing
    for acc in shared_acc:
        # Keep primary, drop secondary
        sec_mask = (df['ticker'] == secondary) & (df['accession_number'] == acc)
        if sec_mask.any():
            df = df[~sec_mask].copy()
            print(f"    Dropped {secondary} for accession {acc}")

print(f"\nAfter dual-class dedup: {len(df)} rows")

# ---------------------------------------------------------------------------
# 3. Verify no duplicate accession numbers remain
# ---------------------------------------------------------------------------
acc_dup = df.groupby('accession_number').size().reset_index(name='count')
acc_dup = acc_dup[acc_dup['count'] > 1]
print(f"\nRemaining duplicate accession numbers: {len(acc_dup)}")
if len(acc_dup) > 0:
    print(acc_dup)
    for acc in acc_dup['accession_number']:
        subset = df[df['accession_number'] == acc][['ticker', 'fiscal_year', 'accession_number']]
        print(f"  {acc}: {subset['ticker'].tolist()}")

# ---------------------------------------------------------------------------
# 4. Verify gvkey/cik coverage
# ---------------------------------------------------------------------------
print(f"\n=== gvkey/cik coverage ===")
print(f"gvkey missing: {df['gvkey'].isna().sum()}/{len(df)}")
print(f"cik missing: {df['cik'].isna().sum()}/{len(df)}")

for ticker in ['BF-B', 'BRK-B', 'NWS', 'FOX', 'GOOG', 'GOOGL', 'NWSA', 'FOXA']:
    subset = df[df['ticker'] == ticker]
    if len(subset) > 0:
        print(f"{ticker}: {len(subset)} rows, gvkey missing: {subset['gvkey'].isna().sum()}")

# ---------------------------------------------------------------------------
# 5. Save
# ---------------------------------------------------------------------------
# Drop temporary column
df = df.drop(columns=['tic_lookup'], errors='ignore')

out_path = "/home/ricoz/econ_lab/FE-NLP/20260426/firm_year_panel_regression_ready.csv"
df.to_csv(out_path, index=False)

print(f"\n=== Saved to {out_path} ===")
print(f"Total rows: {len(df)}")
print(f"Total columns: {len(df.columns)}")
