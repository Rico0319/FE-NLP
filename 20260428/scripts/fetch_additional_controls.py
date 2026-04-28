#!/usr/bin/env python3
"""Pull additional control variables from WRDS (Compustat + CRSP only)."""

import os
import sys
from pathlib import Path

import pandas as pd
import numpy as np
import psycopg2

WRDS_HOST = 'wrds-pgdata.wharton.upenn.edu'
WRDS_PORT = 9737
WRDS_DB = 'wrds'
WRDS_USER = 'fedorico'
WRDS_PASS = os.environ.get('WRDS_PASS', 'Yang@230379033')

PANEL_PATH = Path('/home/ricoz/econ_lab/FE-NLP/20260426/firm_year_ai_disclosure_summary_with_controls_and_forecasts.csv')
OUT_PATH = PANEL_PATH.with_stem(PANEL_PATH.stem + '_final')

print("[1/5] Loading panel...")
panel = pd.read_csv(PANEL_PATH)
print(f"        {len(panel):,} rows, {len(panel.columns)} columns")

# Build gvkey list
panel['gvkey_str'] = panel['gvkey_ctrl'].apply(
    lambda x: str(int(float(x))).zfill(6) if pd.notna(x) else None
)
gvkey_list = panel['gvkey_str'].dropna().unique().tolist()
fiscal_years = sorted(panel['fiscal_year'].dropna().unique().tolist())
print(f"        {len(gvkey_list)} unique gvkeys, fiscal years {fiscal_years[0]}-{fiscal_years[-1]}")

# ------------------------------------------------------------------
# 2. Pull additional Compustat variables
# ------------------------------------------------------------------
print("\n[2/5] Pulling additional Compustat variables...")
conn = psycopg2.connect(
    host=WRDS_HOST, port=WRDS_PORT, database=WRDS_DB,
    user=WRDS_USER, password=WRDS_PASS, sslmode="require",
)
conn.autocommit = True
cur = conn.cursor()

ph = ",".join(["%s"] * len(gvkey_list))
cur.execute(f"""
    SELECT  gvkey, datadate, fyear,
            xad, oancf, ceq, dvc, gp, oiadp, ebitda, xint,
            act, lct, seq, mkvalt, prcc_c, cshfd, dltis, sstk, prstkc, aqc,
            ib, xsga, wcap, che, ppent, gdwl, emp, cogs, dlc, invt, rect, ap, txp,
            fincf, ivncf, dp, re, pstk, ppegt, sppe, dltr, pi, txt, aco,
            at, sale, capx, xrd, ni, lt
    FROM    comp.funda
    WHERE   gvkey IN ({ph})
        AND indfmt = 'INDL'
        AND datafmt = 'STD'
        AND popsrc = 'D'
        AND consol = 'C'
        AND fyear IS NOT NULL
""", tuple(gvkey_list))
rows = cur.fetchall()
comp_df = pd.DataFrame(rows, columns=[
    'gvkey', 'datadate', 'fyear',
    'xad', 'oancf', 'ceq', 'dvc', 'gp', 'oiadp', 'ebitda', 'xint',
    'act', 'lct', 'seq', 'mkvalt', 'prcc_c', 'cshfd', 'dltis', 'sstk', 'prstkc', 'aqc',
    'ib', 'xsga', 'wcap', 'che', 'ppent', 'gdwl', 'emp', 'cogs', 'dlc', 'invt', 'rect', 'ap', 'txp',
    'fincf', 'ivncf', 'dp', 're', 'pstk', 'ppegt', 'sppe', 'dltr', 'pi', 'txt', 'aco',
    'at', 'sale', 'capx', 'xrd', 'ni', 'lt'
])
print(f"        Compustat rows: {len(comp_df):,}")

num_cols = ['xad', 'oancf', 'ceq', 'dvc', 'gp', 'oiadp', 'ebitda', 'xint',
            'act', 'lct', 'seq', 'mkvalt', 'prcc_c', 'cshfd', 'dltis', 'sstk',
            'prstkc', 'aqc', 'ib', 'xsga', 'wcap', 'che', 'ppent', 'gdwl', 'emp',
            'cogs', 'dlc', 'invt', 'rect', 'ap', 'txp', 'fincf', 'ivncf', 'dp',
            're', 'pstk', 'ppegt', 'sppe', 'dltr', 'pi', 'txt', 'aco',
            'at', 'sale', 'capx', 'xrd', 'ni', 'lt']
for c in num_cols:
    comp_df[c] = pd.to_numeric(comp_df[c], errors='coerce')

# ------------------------------------------------------------------
# 3. Compute additional ratios
# ------------------------------------------------------------------
print("\n[3/5] Computing additional ratios...")

comp_df['mkt_cap'] = comp_df['prcc_c'] * comp_df['cshfd']
comp_df['book_to_market'] = np.where(
    comp_df['mkt_cap'] > 0, comp_df['seq'] / comp_df['mkt_cap'], np.nan
)
comp_df['dividend_payer'] = (comp_df['dvc'] > 0).astype(int)
comp_df['dividend_yield'] = np.where(
    comp_df['mkt_cap'] > 0, comp_df['dvc'] / comp_df['mkt_cap'], np.nan
)
comp_df['advertising_intensity'] = np.where(
    comp_df['sale'] > 0, comp_df['xad'] / comp_df['sale'], np.nan
)
comp_df['sga_intensity'] = np.where(
    comp_df['sale'] > 0, comp_df['xsga'] / comp_df['sale'], np.nan
)
comp_df['gross_margin'] = np.where(
    comp_df['sale'] > 0, comp_df['gp'] / comp_df['sale'], np.nan
)
comp_df['operating_margin'] = np.where(
    comp_df['sale'] > 0, comp_df['oiadp'] / comp_df['sale'], np.nan
)
comp_df['ebitda_margin'] = np.where(
    comp_df['sale'] > 0, comp_df['ebitda'] / comp_df['sale'], np.nan
)
comp_df['net_margin'] = np.where(
    comp_df['sale'] > 0, comp_df['ni'] / comp_df['sale'], np.nan
)
comp_df['interest_coverage'] = np.where(
    comp_df['xint'] > 0, comp_df['oiadp'] / comp_df['xint'], np.nan
)
comp_df['current_ratio'] = np.where(
    comp_df['lct'] > 0, comp_df['act'] / comp_df['lct'], np.nan
)
comp_df['ROE'] = np.where(
    comp_df['seq'] != 0, comp_df['ni'] / comp_df['seq'], np.nan
)
comp_df['ppe_intensity'] = np.where(
    comp_df['at'] > 0, comp_df['ppent'] / comp_df['at'], np.nan
)
comp_df['goodwill_intensity'] = np.where(
    comp_df['at'] > 0, comp_df['gdwl'] / comp_df['at'], np.nan
)
comp_df['cash_holdings'] = np.where(
    comp_df['at'] > 0, comp_df['che'] / comp_df['at'], np.nan
)
comp_df['wc_to_assets'] = np.where(
    comp_df['at'] > 0, comp_df['wcap'] / comp_df['at'], np.nan
)
comp_df['debt_issuance'] = np.where(
    comp_df['at'] > 0, comp_df['dltis'] / comp_df['at'], np.nan
)
comp_df['equity_issuance'] = np.where(
    comp_df['at'] > 0, comp_df['sstk'] / comp_df['at'], np.nan
)
comp_df['acquisition'] = (comp_df['aqc'] > 0).astype(int)
comp_df['stock_repurchases'] = np.where(
    comp_df['at'] > 0, comp_df['prstkc'] / comp_df['at'], np.nan
)
comp_df['rd_dummy'] = (comp_df['xrd'] > 0).astype(int)
comp_df['loss_indicator'] = (comp_df['ni'] < 0).astype(int)
comp_df['ocf_to_assets'] = np.where(
    comp_df['at'] > 0, comp_df['oancf'] / comp_df['at'], np.nan
)
comp_df['fcf_to_assets'] = np.where(
    comp_df['at'] > 0, (comp_df['oancf'] - comp_df['capx']) / comp_df['at'], np.nan
)
comp_df['investment'] = np.where(
    comp_df['at'] > 0, (comp_df['ppent'] - comp_df['ppent'].groupby(comp_df['gvkey']).shift(1) + comp_df['dp']) / comp_df['at'], np.nan
)
comp_df['inventory_to_assets'] = np.where(
    comp_df['at'] > 0, comp_df['invt'] / comp_df['at'], np.nan
)
comp_df['receivables_to_assets'] = np.where(
    comp_df['at'] > 0, comp_df['rect'] / comp_df['at'], np.nan
)
comp_df['log_emp2'] = np.where(comp_df['emp'] > 0, np.log(comp_df['emp']), np.nan)
comp_df['depreciation_to_assets'] = np.where(
    comp_df['at'] > 0, comp_df['dp'] / comp_df['at'], np.nan
)
comp_df['tax_rate'] = np.where(
    comp_df['pi'] > 0, comp_df['txt'] / comp_df['pi'], np.where(comp_df['pi'] < 0, 0, np.nan)
)
comp_df['quick_ratio'] = np.where(
    comp_df['lct'] > 0, (comp_df['act'] - comp_df['invt']) / comp_df['lct'], np.nan
)
comp_df['debt_to_assets'] = np.where(
    comp_df['at'] > 0, comp_df['lt'] / comp_df['at'], np.nan
)
comp_df['asset_turnover'] = np.where(
    comp_df['at'] > 0, comp_df['sale'] / comp_df['at'], np.nan
)
comp_df['price_to_earnings'] = np.where(
    (comp_df['ib'] > 0) & (comp_df['cshfd'] > 0), comp_df['prcc_c'] / (comp_df['ib'] / comp_df['cshfd']), np.nan
)
# Note: peg_ratio will be computed after merge since fy1_eps_est is in the panel

print("        Computed ratios complete")

# ------------------------------------------------------------------
# 4. Pull CRSP monthly returns for momentum and volatility
# ------------------------------------------------------------------
print("\n[4/5] Pulling CRSP monthly returns...")

# Get CRSP permnos from CCM link
cur.execute(f"""
    SELECT DISTINCT gvkey, lpermno
    FROM    crsp.ccmxpf_lnkhist
    WHERE   gvkey IN ({ph})
        AND linktype IN ('LU', 'LC', 'LS')
        AND linkprim IN ('P', 'C', 'J')
""", tuple(gvkey_list))
ccm_rows = cur.fetchall()
ccm = pd.DataFrame(ccm_rows, columns=['gvkey', 'permno'])
ccm['gvkey'] = ccm['gvkey'].astype(str).str.zfill(6)
ccm['permno'] = ccm['permno'].astype(int)
ccm = ccm.drop_duplicates(subset=['gvkey'], keep='first')
print(f"        CCM links: {len(ccm)}")

permno_list = ccm['permno'].unique().tolist()
print(f"        Permnos: {len(permno_list)}")

if permno_list:
    permno_ph = ",".join(["%s"] * len(permno_list))
    # Pull monthly returns
    cur.execute(f"""
        SELECT  permno, date, ret
        FROM    crsp.msf
        WHERE   permno IN ({permno_ph})
            AND date >= '2016-01-01'
            AND date <= '2026-01-31'
            AND ret IS NOT NULL
    """, tuple(permno_list))
    crsp_rows = cur.fetchall()
    crsp_df = pd.DataFrame(crsp_rows, columns=['permno', 'date', 'ret'])
    crsp_df['date'] = pd.to_datetime(crsp_df['date'])
    crsp_df['ret'] = pd.to_numeric(crsp_df['ret'], errors='coerce')
    crsp_df = crsp_df.dropna(subset=['ret'])
    crsp_df['year'] = crsp_df['date'].dt.year
    print(f"        Total CRSP rows: {len(crsp_df):,}")
    
    # Compute 12-month momentum and volatility
    crsp_df = crsp_df.sort_values(['permno', 'date'])
    crsp_df['log_ret'] = np.log1p(crsp_df['ret'])
    crsp_df['momentum_12m'] = (
        crsp_df.groupby('permno')['log_ret']
        .transform(lambda s: s.rolling(12, min_periods=10).sum().shift(1))
    )
    crsp_df['momentum_12m'] = np.expm1(crsp_df['momentum_12m'])
    crsp_df['volatility_12m'] = (
        crsp_df.groupby('permno')['ret']
        .transform(lambda s: s.rolling(12, min_periods=10).std().shift(1))
    )
    
    # Keep only December observations
    crsp_ye = crsp_df[crsp_df['date'].dt.month == 12].copy()
    crsp_ye = crsp_ye[['permno', 'year', 'momentum_12m', 'volatility_12m']].copy()
    crsp_ye = crsp_ye.drop_duplicates(subset=['permno', 'year'], keep='last')
    
    # Merge CRSP to panel via gvkey-permno mapping
    gvkey_permno = dict(zip(ccm['gvkey'].astype(str).str.zfill(6), ccm['permno']))
    panel['permno'] = panel['gvkey_str'].map(gvkey_permno)
    
    # Create merge key
    crsp_ye['permno'] = crsp_ye['permno'].astype(int)
    panel['permno'] = panel['permno'].astype('Int64')
    
    panel = panel.merge(
        crsp_ye[['permno', 'year', 'momentum_12m', 'volatility_12m']],
        left_on=['permno', 'fiscal_year'], right_on=['permno', 'year'], how='left'
    )
    panel = panel.drop(columns=['year'], errors='ignore')
    print(f"        CRSP merge: momentum non-null {panel['momentum_12m'].notna().sum()}, volatility non-null {panel['volatility_12m'].notna().sum()}")
else:
    print("        No CRSP permnos found, skipping momentum/volatility")

cur.close()
conn.close()

# ------------------------------------------------------------------
# 5. Merge Compustat additional variables
# ------------------------------------------------------------------
print("\n[5/5] Merging Compustat variables into panel...")

merge_cols = ['gvkey', 'datadate']
comp_merge = comp_df[merge_cols + [
    'mkt_cap', 'book_to_market', 'dividend_payer', 'dividend_yield',
    'advertising_intensity', 'sga_intensity', 'gross_margin', 'operating_margin',
    'ebitda_margin', 'net_margin', 'interest_coverage', 'current_ratio', 'ROE',
    'ppe_intensity', 'goodwill_intensity', 'cash_holdings', 'wc_to_assets',
    'debt_issuance', 'equity_issuance', 'acquisition', 'stock_repurchases',
    'rd_dummy', 'loss_indicator', 'ocf_to_assets', 'fcf_to_assets', 'investment',
    'inventory_to_assets', 'receivables_to_assets', 'log_emp2',
    'depreciation_to_assets', 'tax_rate', 'prcc_c', 'ceq',
    'quick_ratio', 'debt_to_assets', 'asset_turnover', 'price_to_earnings'
]].copy()
comp_merge['datadate'] = pd.to_datetime(comp_merge['datadate'])
comp_merge['gvkey'] = comp_merge['gvkey'].astype(str).str.zfill(6)

panel['datadate'] = pd.to_datetime(panel['datadate'], errors='coerce')

panel = panel.merge(comp_merge, left_on=['gvkey_str', 'datadate'], right_on=['gvkey', 'datadate'], how='left')

# Drop helper columns
panel = panel.drop(columns=['gvkey_x', 'gvkey_y', 'gvkey_str', 'permno'], errors='ignore')

# ------------------------------------------------------------------
# 6. Save
# ------------------------------------------------------------------
print(f"\nSaving to {OUT_PATH} ...")
panel.to_csv(OUT_PATH, index=False)
print(f"Done. Final panel: {len(panel):,} rows, {len(panel.columns)} columns")

# Summary of new columns
new_cols = [
    'mkt_cap', 'book_to_market', 'dividend_payer', 'dividend_yield',
    'advertising_intensity', 'sga_intensity', 'gross_margin', 'operating_margin',
    'ebitda_margin', 'net_margin', 'interest_coverage', 'current_ratio', 'ROE',
    'ppe_intensity', 'goodwill_intensity', 'cash_holdings', 'wc_to_assets',
    'debt_issuance', 'equity_issuance', 'acquisition', 'stock_repurchases',
    'rd_dummy', 'loss_indicator', 'ocf_to_assets', 'fcf_to_assets', 'investment',
    'inventory_to_assets', 'receivables_to_assets', 'log_emp2',
    'depreciation_to_assets', 'tax_rate', 'prcc_c', 'ceq',
    'quick_ratio', 'debt_to_assets', 'asset_turnover', 'price_to_earnings',
    'momentum_12m', 'volatility_12m'
]
print("\nNew variable coverage:")
for col in new_cols:
    if col in panel.columns:
        non_null = panel[col].notna().sum()
        print(f"  {col:<35s} {non_null:>4}/{len(panel)} ({non_null/len(panel)*100:.1f}%)")
