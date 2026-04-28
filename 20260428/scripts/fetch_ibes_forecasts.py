#!/usr/bin/env python3
"""Pull IBES analyst forecast consensus from WRDS using CRSP-IBES link and merge with firm-year panel."""

import os
import sys
from pathlib import Path

import pandas as pd
import numpy as np
import psycopg2

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PANEL_PATH = PROJECT_ROOT / "20260426" / "firm_year_ai_disclosure_summary_with_controls.csv"
OUTPUT_PATH = PROJECT_ROOT / "20260426" / "firm_year_ai_disclosure_summary_with_controls_and_forecasts.csv"

# ------------------------------------------------------------------
# WRDS connection
# ------------------------------------------------------------------
WRDS_HOST = "wrds-pgdata.wharton.upenn.edu"
WRDS_PORT = 9737
WRDS_DB = "wrds"
WRDS_USER = "fedorico"
WRDS_PASS = "Yang@230379033"

def wrds_query(query, params=None):
    """Execute a WRDS query and return a DataFrame."""
    conn = psycopg2.connect(
        host=WRDS_HOST, port=WRDS_PORT, database=WRDS_DB,
        user=WRDS_USER, password=WRDS_PASS, sslmode="require",
    )
    conn.autocommit = True
    cursor = conn.cursor()
    cursor.execute(query, params or ())
    cols = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return pd.DataFrame(rows, columns=cols)

# ------------------------------------------------------------------
# 1. Load panel
# ------------------------------------------------------------------
print("[1/5] Loading panel...")
panel = pd.read_csv(PANEL_PATH)
print(f"        {len(panel):,} rows")

valid_mask = panel['gvkey_ctrl'].notna()
valid_panel = panel[valid_mask].copy()
print(f"        {len(valid_panel):,} rows with Compustat match")

# Parse gvkey as zero-padded string
valid_panel['gvkey_str'] = valid_panel['gvkey_ctrl'].astype(float).astype(int).astype(str).str.zfill(6)
valid_panel['datadate'] = pd.to_datetime(valid_panel['datadate'], errors='coerce')

unique_gvkeys = valid_panel['gvkey_str'].unique().tolist()
print(f"        {len(unique_gvkeys):,} unique gvkeys")

# ------------------------------------------------------------------
# 2. Get CRSP permno for each gvkey
# ------------------------------------------------------------------
print("\n[2/5] Querying CRSP-Compustat link...")

gvkey_placeholders = ",".join(["%s"] * len(unique_gvkeys))
ccm_query = f"""
    SELECT  DISTINCT gvkey, lpermno
    FROM    crsp.ccmxpf_lnkhist
    WHERE   gvkey IN ({gvkey_placeholders})
        AND linktype IN ('LU', 'LC')
        AND linkprim IN ('P', 'C')
"""
ccm_df = wrds_query(ccm_query, tuple(unique_gvkeys))
print(f"        CCM links fetched: {len(ccm_df):,}")
ccm_df['lpermno'] = ccm_df['lpermno'].astype(float).astype(int).astype(str)
ccm_df = ccm_df.dropna(subset=['lpermno'])
ccm_df = ccm_df.drop_duplicates(subset=['gvkey'])
print(f"        Unique gvkey->permno mappings: {len(ccm_df):,}")

# ------------------------------------------------------------------
# 3. Get IBES ticker for each permno
# ------------------------------------------------------------------
print("\n[3/5] Querying CRSP-IBES link...")

permno_list = ccm_df['lpermno'].dropna().unique().tolist()
permno_placeholders = ",".join(["%s"] * len(permno_list))
ibes_link_query = f"""
    SELECT  DISTINCT permno, ticker as ibes_ticker
    FROM    wrdsapps_link_crsp_ibes.ibcrsphist
    WHERE   permno IN ({permno_placeholders})
        AND score <= 2
"""
ibes_link_df = wrds_query(ibes_link_query, tuple(permno_list))
print(f"        IBES links fetched: {len(ibes_link_df):,}")
ibes_link_df['permno'] = ibes_link_df['permno'].astype(float).astype(int).astype(str)
ibes_link_df = ibes_link_df.dropna(subset=['ibes_ticker'])
ibes_link_df = ibes_link_df.drop_duplicates(subset=['permno'])
print(f"        Unique permno->IBES ticker mappings: {len(ibes_link_df):,}")

# Merge: gvkey -> permno -> IBES ticker
ccm_df = ccm_df.rename(columns={'lpermno': 'permno'})
link_df = ccm_df.merge(ibes_link_df, on='permno', how='inner')
print(f"        Total gvkey->IBES ticker links: {len(link_df):,}")

# Some gvkeys map to multiple IBES tickers; keep one per gvkey
link_df = link_df.drop_duplicates(subset=['gvkey'], keep='first')
print(f"        After dedup on gvkey: {len(link_df):,}")

# ------------------------------------------------------------------
# 4. Merge IBES ticker onto panel
# ------------------------------------------------------------------
print("\n[4/5] Merging IBES ticker onto panel...")
valid_panel = valid_panel.merge(link_df[['gvkey', 'ibes_ticker']], left_on='gvkey_str', right_on='gvkey', how='left')
valid_panel = valid_panel.drop(columns=['gvkey_y'], errors='ignore')
valid_panel = valid_panel.rename(columns={'gvkey_x': 'gvkey_panel'})

ibes_tickers = valid_panel['ibes_ticker'].dropna().unique().tolist()
print(f"        {len(ibes_tickers):,} unique IBES tickers to query")

# Deduplicate valid_panel on (gvkey_ctrl, fiscal_year) before computing next_datadate
# This prevents share-class duplicates (e.g., GOOG + GOOGL) from breaking the shift logic
valid_panel = valid_panel.sort_values(['ibes_ticker', 'fiscal_year']).reset_index(drop=True)
valid_panel_dedup = valid_panel.drop_duplicates(subset=['gvkey_ctrl', 'fiscal_year'], keep='first').copy()
print(f"        After dedup on gvkey_ctrl+fiscal_year: {len(valid_panel_dedup):,}")

# ------------------------------------------------------------------
# 5. Query IBES forecasts
# ------------------------------------------------------------------
print("\n[5/5] Querying IBES statsum_epsus...")

CHUNK_SIZE = 500
all_results = []

conn = psycopg2.connect(
    host=WRDS_HOST, port=WRDS_PORT, database=WRDS_DB,
    user=WRDS_USER, password=WRDS_PASS, sslmode="require",
)
cursor = conn.cursor()

for i in range(0, len(ibes_tickers), CHUNK_SIZE):
    chunk = ibes_tickers[i:i + CHUNK_SIZE]
    placeholders = ",".join(["%s"] * len(chunk))

    query = f"""
        SELECT  ticker,
                statpers,
                measure,
                fpi,
                fpedats,
                meanest,
                medest,
                numest,
                stdev,
                actual,
                usfirm
        FROM    ibes.statsum_epsus
        WHERE   ticker IN ({placeholders})
            AND measure = 'EPS'
            AND fiscalp = 'ANN'
            AND fpi IN ('1', '2')
            AND statpers BETWEEN '2018-01-01' AND '2026-12-31'
            AND usfirm = 1
        ORDER BY ticker, statpers, fpi;
    """
    cursor.execute(query, chunk)
    rows = cursor.fetchall()
    if rows:
        all_results.extend(rows)
    print(f"        Chunk {i//CHUNK_SIZE + 1}/{(len(ibes_tickers)-1)//CHUNK_SIZE + 1}: {len(rows):,} rows")

cursor.close()
conn.close()

print(f"\n        Total IBES rows fetched: {len(all_results):,}")

if len(all_results) == 0:
    print("[ERROR] No IBES data returned.")
    sys.exit(1)

# Build DataFrame
ibes_cols = ['ticker', 'statpers', 'measure', 'fpi', 'fpedats', 'meanest', 'medest', 'numest', 'stdev', 'actual', 'usfirm']
ibes_df = pd.DataFrame(all_results, columns=ibes_cols)
ibes_df['statpers'] = pd.to_datetime(ibes_df['statpers'])
ibes_df['fpedats'] = pd.to_datetime(ibes_df['fpedats'])
ibes_df['meanest'] = pd.to_numeric(ibes_df['meanest'], errors='coerce')
ibes_df['medest'] = pd.to_numeric(ibes_df['medest'], errors='coerce')
ibes_df['numest'] = pd.to_numeric(ibes_df['numest'], errors='coerce')
ibes_df['stdev'] = pd.to_numeric(ibes_df['stdev'], errors='coerce')
ibes_df['actual'] = pd.to_numeric(ibes_df['actual'], errors='coerce')

print(f"        IBES FY1 rows: {(ibes_df['fpi'] == '1').sum():,}")
print(f"        IBES FY2 rows: {(ibes_df['fpi'] == '2').sum():,}")
print(f"        Unique tickers in IBES: {ibes_df['ticker'].nunique():,}")

# ------------------------------------------------------------------
# 6. Merge IBES forecasts onto deduplicated panel
# ------------------------------------------------------------------
print("\n[6/6] Merging forecasts onto panel...")

ibes_fy1 = ibes_df[ibes_df['fpi'] == '1'].copy()
ibes_fy2 = ibes_df[ibes_df['fpi'] == '2'].copy()

# Compute next fiscal year end date on DEDUPLICATED panel
valid_panel_dedup = valid_panel_dedup.sort_values(['gvkey_ctrl', 'fiscal_year']).reset_index(drop=True)
valid_panel_dedup['next_datadate'] = valid_panel_dedup.groupby('gvkey_ctrl')['datadate'].shift(-1)
valid_panel_dedup['next_datadate_est'] = valid_panel_dedup['next_datadate'].fillna(
    valid_panel_dedup['datadate'] + pd.Timedelta(days=365)
)

# FY1 merge
merge_keys = valid_panel_dedup[['ibes_ticker', 'datadate', 'next_datadate_est']].drop_duplicates().copy()
merge_keys = merge_keys.dropna(subset=['ibes_ticker', 'next_datadate_est'])

needed_fpedats = merge_keys['next_datadate_est'].unique()
ibes_fy1_match = ibes_fy1[ibes_fy1['fpedats'].isin(needed_fpedats)].copy()

print(f"        FY1 rows with matching fpedats: {len(ibes_fy1_match):,}")

forecast_records = []
for ticker, group in merge_keys.groupby('ibes_ticker'):
    ibes_t = ibes_fy1_match[ibes_fy1_match['ticker'] == ticker].sort_values('statpers')
    if len(ibes_t) == 0:
        continue
    
    for _, row in group.iterrows():
        fpedats_target = row['next_datadate_est']
        candidates = ibes_t[ibes_t['fpedats'] == fpedats_target]
        if len(candidates) > 0:
            best = candidates.sort_values('statpers').iloc[0]
            forecast_records.append({
                'ibes_ticker': ticker,
                'datadate': row['datadate'],
                'fy1_meanest': best['meanest'],
                'fy1_medest': best['medest'],
                'fy1_numest': best['numest'],
                'fy1_stdev': best['stdev'],
                'fy1_actual': best['actual'],
                'fy1_statpers': best['statpers'],
            })

fy1_df = pd.DataFrame(forecast_records)
print(f"        FY1 matches: {len(fy1_df):,} rows")

# FY2 merge
valid_panel_dedup['next_next_datadate_est'] = valid_panel_dedup.groupby('gvkey_ctrl')['datadate'].shift(-2)
valid_panel_dedup['next_next_datadate_est'] = valid_panel_dedup['next_next_datadate_est'].fillna(
    valid_panel_dedup['datadate'] + pd.Timedelta(days=730)
)

merge_keys_fy2 = valid_panel_dedup[['ibes_ticker', 'datadate', 'next_next_datadate_est']].drop_duplicates().copy()
merge_keys_fy2 = merge_keys_fy2.dropna()

needed_fpedats_fy2 = merge_keys_fy2['next_next_datadate_est'].unique()
ibes_fy2_match = ibes_fy2[ibes_fy2['fpedats'].isin(needed_fpedats_fy2)].copy()

print(f"        FY2 rows with matching fpedats: {len(ibes_fy2_match):,}")

forecast_records_fy2 = []
for ticker, group in merge_keys_fy2.groupby('ibes_ticker'):
    ibes_t = ibes_fy2_match[ibes_fy2_match['ticker'] == ticker].sort_values('statpers')
    if len(ibes_t) == 0:
        continue
    
    for _, row in group.iterrows():
        fpedats_target = row['next_next_datadate_est']
        candidates = ibes_t[ibes_t['fpedats'] == fpedats_target]
        if len(candidates) > 0:
            best = candidates.sort_values('statpers').iloc[0]
            forecast_records_fy2.append({
                'ibes_ticker': ticker,
                'datadate': row['datadate'],
                'fy2_meanest': best['meanest'],
                'fy2_medest': best['medest'],
                'fy2_numest': best['numest'],
                'fy2_stdev': best['stdev'],
                'fy2_actual': best['actual'],
                'fy2_statpers': best['statpers'],
            })

fy2_df = pd.DataFrame(forecast_records_fy2)
print(f"        FY2 matches: {len(fy2_df):,} rows")

# ------------------------------------------------------------------
# 7. Merge forecasts back into full panel
# ------------------------------------------------------------------
print("\n[7/7] Final merge into panel...")

panel_out = panel.copy()
panel_out['datadate'] = pd.to_datetime(panel_out['datadate'], errors='coerce')

# Merge IBES ticker first (use deduplicated mapping)
panel_out = panel_out.merge(
    valid_panel_dedup[['gvkey_ctrl', 'fiscal_year', 'ibes_ticker']].drop_duplicates(),
    left_on=['gvkey_ctrl', 'fiscal_year'],
    right_on=['gvkey_ctrl', 'fiscal_year'],
    how='left'
)

# Merge FY1
panel_out = panel_out.merge(
    fy1_df,
    left_on=['ibes_ticker', 'datadate'],
    right_on=['ibes_ticker', 'datadate'],
    how='left'
)

# Merge FY2
panel_out = panel_out.merge(
    fy2_df,
    left_on=['ibes_ticker', 'datadate'],
    right_on=['ibes_ticker', 'datadate'],
    how='left'
)

# Drop helper column
panel_out = panel_out.drop(columns=['ibes_ticker'], errors='ignore')

# ------------------------------------------------------------------
# 8. Save
# ------------------------------------------------------------------
panel_out.to_csv(OUTPUT_PATH, index=False)
print(f"\nSaved to: {OUTPUT_PATH}")
print(f"Total rows: {len(panel_out)}")
print(f"Total columns: {len(panel_out.columns)}")

# Coverage report
print("\n=== FORECAST COVERAGE ===")
for col in ['fy1_meanest', 'fy1_medest', 'fy1_numest', 'fy1_stdev', 'fy1_actual',
            'fy2_meanest', 'fy2_medest', 'fy2_numest', 'fy2_stdev', 'fy2_actual']:
    if col in panel_out.columns:
        non_null = panel_out[col].notna().sum()
        print(f"  {col}: {non_null}/{len(panel_out)} ({non_null/len(panel_out)*100:.1f}%)")

# Sample
print("\n=== SAMPLE ===")
sample = panel_out[panel_out['ticker'].isin(['AAPL', 'GOOG', 'GOOGL', 'AAL', 'AMZN'])][[
    'ticker', 'fiscal_year', 'datadate', 'fy1_meanest', 'fy1_numest', 'fy1_actual',
    'fy2_meanest', 'fy2_numest'
]].head(15)
print(sample.to_string(index=False))
