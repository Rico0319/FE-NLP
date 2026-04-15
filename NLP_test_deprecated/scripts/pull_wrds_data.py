#!/usr/bin/env python3
"""
WRDS Data Pull for FE-NLP Project
====================================
Pulls:
1. Compustat Annual Fundamentals (key financial variables)
2. CIK ↔ GVKEY crosswalk
3. S&P 500 constituent list with GICS sectors

Usage:
    python pull_wrds_data.py

You'll be prompted for WRDS credentials on first run (saved to ~/.wrds).
"""

import os
import sys
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)

OUTPUT_DIR = Path(__file__).parent / "data" / "wrds"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("WRDS Data Pull — FE-NLP Project")
print("=" * 60)
print()

# ============================================================
# 1. Connect to WRDS
# ============================================================
print("Connecting to WRDS...")
import wrds
db = wrds.Connection()
print("✅ Connected!")
print()

# ============================================================
# 2. CIK ↔ GVKEY Crosswalk
# ============================================================
print("Pulling CIK ↔ GVKEY crosswalk...")
cik_query = """
SELECT cik, gvkey, conm, tic, sic, naics
FROM comp.names
WHERE cik IS NOT NULL
"""
cik_df = db.raw_sql(cik_query)
cik_df.to_csv(OUTPUT_DIR / "cik_gvkey_crosswalk.csv", index=False)
print(f"  ✅ {len(cik_df):,} records → {OUTPUT_DIR / 'cik_gvkey_crosswalk.csv'}")
print()

# ============================================================
# 3. Compustat Annual Fundamentals
# ============================================================
print("Pulling Compustat Annual Fundamentals (2018-2025)...")
fund_query = """
SELECT 
    f.gvkey, f.datadate, f.fyear, f.conm, f.tic, f.cik,
    c.sic, c.naics, c.gsubind,
    -- Size
    f.at,           -- Total Assets
    f.revt,         -- Total Revenue
    f.sale,         -- Sales/Turnover
    -- Profitability
    f.ni,           -- Net Income
    f.ib,           -- Income Before Extraordinary Items
    f.oiadp,        -- Operating Income After Depreciation
    f.ebit,         -- Earnings Before Interest & Taxes
    -- Per Share
    f.epspx,        -- Basic EPS
    f.csho,         -- Common Shares Outstanding
    -- Capital Structure
    f.ceq,          -- Common Equity
    f.lt,           -- Long-term Debt
    f.dltt,         -- Debt in Long Term
    f.dlc,          -- Debt in Current Liabilities
    f.seq,          -- Shareholders' Equity
    -- PPE
    f.ppent,        -- Net Property, Plant & Equipment
    -- R&D
    f.xrd,          -- R&D Expense
    -- Cash
    f.che,          -- Cash & Short-term Investments
    -- Other
    f.emp           -- Number of Employees
FROM comp.funda f
LEFT JOIN comp.company c ON f.gvkey = c.gvkey
WHERE f.indfmt = 'INDL'       -- Industrial
  AND f.datafmt = 'STD'       -- Standardized
  AND f.popsrc = 'D'          -- Domestic
  AND f.consol = 'C'          -- Consolidated
  AND f.fyear >= 2018
  AND f.fyear <= 2025
ORDER BY f.gvkey, f.fyear
"""
fund_df = db.raw_sql(fund_query)
fund_df.to_csv(OUTPUT_DIR / "compustat_annual_2018_2025.csv", index=False)
print(f"  ✅ {len(fund_df):,} firm-year records → {OUTPUT_DIR / 'compustat_annual_2018_2025.csv'}")
print()

# ============================================================
# 4. GICS Sector Mapping (from Compustat if available)
# ============================================================
print("Checking GICS sector data...")
if 'gsubind' in fund_df.columns and fund_df['gsubind'].notna().any():
    # Extract unique sector/sub-industry mapping
    gics = fund_df[['gvkey', 'conm', 'tic', 'fyear', 'gsubind', 'sic', 'naics']].drop_duplicates()
    gics.to_csv(OUTPUT_DIR / "gics_mapping.csv", index=False)
    print(f"  ✅ {len(gics):,} records → {OUTPUT_DIR / 'gics_mapping.csv'}")
else:
    print("  ⚠️ GICS sub-industry not available in this dataset")
print()

# ============================================================
# 5. Quick Summary
# ============================================================
print("=" * 60)
print("Summary")
print("=" * 60)
print(f"  CIK crosswalk:      {len(cik_df):,} records")
print(f"  Compustat annual:   {len(fund_df):,} firm-year records")
print(f"  Unique GVKEYs:      {fund_df['gvkey'].nunique():,}")
print(f"  Year range:         {fund_df['fyear'].min()} - {fund_df['fyear'].max()}")
print()
print("Files saved:")
for f in sorted(OUTPUT_DIR.iterdir()):
    size_mb = f.stat().st_size / 1024 / 1024
    print(f"  {f.name:<45s} {size_mb:>6.1f} MB")
print()
print("Next step: merge with AI disclosure data using CIK/GVKEY mapping")
print("=" * 60)

db.close()
