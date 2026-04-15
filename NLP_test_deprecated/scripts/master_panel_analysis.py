#!/usr/bin/env python3
"""
Master Panel: Merge AI Disclosure Data with Compustat Fundamentals
====================================================================
1. Map SEC CIK → Compustat GVKEY
2. Merge AI disclosure metrics with financial data
3. Calculate derived variables (ROA, leverage, MtB, etc.)
4. Create sector dummies from GICS
5. Output: master_panel.csv (firm-year level)
6. Run panel regressions with full financial controls
"""

import sys
import json
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)

BASE = Path(__file__).parent
WRDS_DIR = BASE / "data" / "wrds"
RESULTS_DIR = BASE / "results"
RESULTS_DIR.mkdir(exist_ok=True)

print("=" * 60)
print("Master Panel: AI Disclosure + Compustat")
print("=" * 60)
print()

# ============================================================
# 1. Load data
# ============================================================
print("Loading data...")

# CIK ↔ GVKEY crosswalk
cik_map = pd.read_csv(WRDS_DIR / "cik_gvkey_crosswalk.csv", dtype={'cik': str})
# Clean CIK (pad to 10 digits)
cik_map['cik'] = cik_map['cik'].str.zfill(10)
print(f"  CIK crosswalk: {len(cik_map):,} records")

# Compustat fundamentals
comp = pd.read_csv(WRDS_DIR / "compustat_annual_2018_2025.csv", dtype={'cik': str})
comp['cik'] = comp['cik'].astype(str).str.zfill(10)
comp['year'] = comp['fyear']
print(f"  Compustat: {len(comp):,} firm-years, {comp['gvkey'].nunique():,} unique GVKEYs")

# AI classified sentences
ai_cls = pd.read_json(BASE / "data" / "final" / "sp500_ai_classified.jsonl", lines=True)
print(f"  AI classified: {len(ai_cls):,} sentences")

# AI extraction (for sentence counts per filing)
ai_extract = pd.read_json(BASE / "data" / "intermediate" / "sp500_mda_ai_extracts.jsonl", lines=True)
print(f"  AI extracts: {len(ai_extract):,} filings")

print()

# ============================================================
# 2. Map AI data to GVKEY
# ============================================================
print("Mapping AI data to GVKEY...")

# Aggregate AI classification to firm-year level
ai_filing = ai_extract.copy()
# Extract year from accession or use the year field
ai_filing['year'] = pd.to_numeric(ai_filing['year'], errors='coerce').astype('Int64')

# Aggregate AI sentences per filing
ai_filing['substantive_cnt'] = 0
ai_filing['generic_cnt'] = 0
for _, row in ai_cls.iterrows():
    # Find matching filing
    mask = (ai_filing['ticker'] == row['ticker']) & (ai_filing['year'] == row['year'])
    # This is approximate; better to use accession
    pass

# Better approach: aggregate from classified data directly
ai_yearly = ai_cls.groupby(['ticker', 'year']).agg(
    ai_sentence_count=('sentence_key', 'count'),
    substantive_cnt=('classification', lambda x: (x == 'substantive').sum()),
    generic_cnt=('classification', lambda x: (x == 'generic').sum()),
).reset_index()
ai_yearly['has_substantive'] = (ai_yearly['substantive_cnt'] > 0).astype(int)
ai_yearly['has_generic'] = (ai_yearly['generic_cnt'] > 0).astype(int)
ai_yearly['substantive_ratio'] = ai_yearly['substantive_cnt'] / ai_yearly['ai_sentence_count'].replace(0, np.nan)

print(f"  AI firm-years: {len(ai_yearly):,}")

# Map ticker → CIK via CIK crosswalk
# First get unique tickers from AI data
ai_tickers = ai_yearly['ticker'].unique()

# Map tickers to CIKs using the crosswalk (match by ticker)
ticker_to_cik = {}
for _, row in cik_map.iterrows():
    tic = row.get('tic', '')
    if tic and pd.notna(tic):
        ticker_to_cik[str(tic).strip()] = str(row['cik']).zfill(10)

# Also try company name matching as fallback
name_to_cik = {}
for _, row in cik_map.iterrows():
    name = row.get('conm', '')
    if name and pd.notna(name):
        name_to_cik[str(name).strip().upper()] = str(row['cik']).zfill(10)

ai_yearly['cik'] = ai_yearly['ticker'].map(ticker_to_cik)
matched = ai_yearly['cik'].notna().sum()
print(f"  Ticker→CIK matched: {matched}/{len(ai_yearly)} ({matched/len(ai_yearly)*100:.0f}%)")

# For unmatched, try fuzzy company name matching
unmatched = ai_yearly[ai_yearly['cik'].isna()]['ticker'].unique()
print(f"  Unmatched tickers ({len(unmatched)}): {list(unmatched[:20])}")

# Map to GVKEY
ai_yearly = ai_yearly.merge(cik_map[['cik', 'gvkey']], on='cik', how='left')
gvkey_matched = ai_yearly['gvkey'].notna().sum()
print(f"  CIK→GVKEY matched: {gvkey_matched}/{len(ai_yearly)} ({gvkey_matched/len(ai_yearly)*100:.0f}%)")

print()

# ============================================================
# 3. Merge with Compustat
# ============================================================
print("Merging with Compustat fundamentals...")

master = ai_yearly.merge(
    comp[['gvkey', 'year', 'conm', 'tic', 'at', 'revt', 'sale', 'ni', 'ib',
           'epspx', 'csho', 'ceq', 'lt', 'dltt', 'dlc', 'seq', 'ppent',
           'xrd', 'che', 'emp', 'sic', 'naics', 'gsubind']],
    on=['gvkey', 'year'],
    how='outer',
    suffixes=('_ai', '_comp')
)

print(f"  Master panel: {len(master):,} firm-years")
print(f"  With AI data: {master['ai_sentence_count'].notna().sum():,}")
print(f"  With Compustat: {master['at'].notna().sum():,}")
print(f"  With both: {(master['ai_sentence_count'].notna() & master['at'].notna()).sum():,}")
print()

# ============================================================
# 4. Calculate derived variables
# ============================================================
print("Calculating derived financial variables...")

# ROA = Net Income / Total Assets
master['ROA'] = master['ni'] / master['at'].replace(0, np.nan)

# Leverage = Total Debt / Total Assets
master['debt'] = master['dltt'].fillna(0) + master['dlc'].fillna(0)
master['leverage'] = master['debt'] / master['at'].replace(0, np.nan)

# Log Assets
master['log_assets'] = np.log(master['at'].replace(0, np.nan))

# R&D intensity
master['rd_intensity'] = master['xrd'] / master['at'].replace(0, np.nan)

# Cash ratio
master['cash_ratio'] = master['che'] / master['at'].replace(0, np.nan)

# PPE ratio
master['ppe_ratio'] = master['ppent'] / master['at'].replace(0, np.nan)

# Revenue growth
master = master.sort_values(['gvkey', 'year'])
master['revenue_growth'] = master.groupby('gvkey')['revt'].pct_change()

# AI density per 10k words (from MD&A)
master['substantive_ratio'] = master['substantive_cnt'] / master['ai_sentence_count'].replace(0, np.nan)

# Log employees
master['log_emp'] = np.log(master['emp'].replace(0, np.nan))

print(f"  ROA: mean={master['ROA'].mean():.4f}, median={master['ROA'].median():.4f}")
print(f"  Leverage: mean={master['leverage'].mean():.4f}")
print(f"  Log Assets: mean={master['log_assets'].mean():.2f}")
print(f"  R&D Intensity: mean={master['rd_intensity'].mean():.4f}")
print()

# ============================================================
# 5. Sector dummies from GICS
# ============================================================
print("Creating sector dummies...")

# Use SIC-based sector mapping if GICS not available
def sic_to_sector(sic_code):
    """Map SIC code to broad sector"""
    try:
        sic = int(sic_code)
    except (ValueError, TypeError):
        return 'Unknown'
    if 100 <= sic <= 999: return 'Agriculture'
    elif 1000 <= sic <= 1499: return 'Mining'
    elif 1500 <= sic <= 1799: return 'Construction'
    elif 2000 <= sic <= 3999: return 'Manufacturing'
    elif 4000 <= sic <= 4999: return 'Utilities/Transport'
    elif 5000 <= sic <= 5199: return 'Wholesale'
    elif 5200 <= sic <= 5999: return 'Retail'
    elif 6000 <= sic <= 6999: return 'Finance'
    elif 7000 <= sic <= 8999: return 'Services'
    elif 9000 <= sic <= 9999: return 'Public'
    else: return 'Unknown'

master['sector'] = master['sic'].apply(sic_to_sector)
print(f"  Sector distribution:")
print(master['sector'].value_counts().head(10).to_string())
print()

# ============================================================
# 6. Save master panel
# ============================================================
master_file = BASE / "data" / "final" / "master_panel.csv"
save_cols = ['gvkey', 'ticker', 'cik', 'year', 'conm',
             'ai_sentence_count', 'substantive_cnt', 'generic_cnt',
             'has_substantive', 'has_generic', 'substantive_ratio',
             'at', 'revt', 'sale', 'ni', 'ib', 'epspx', 'csho',
             'ceq', 'lt', 'dltt', 'dlc', 'seq', 'ppent', 'xrd', 'che', 'emp',
             'ROA', 'leverage', 'log_assets', 'rd_intensity',
             'cash_ratio', 'ppe_ratio', 'revenue_growth', 'log_emp',
             'sic', 'naics', 'gsubind', 'sector']
master[[c for c in save_cols if c in master.columns]].to_csv(master_file, index=False)
print(f"✅ Master panel saved: {master_file}")
print(f"   {len(master):,} firm-years, {len(save_cols)} columns")
print()

# ============================================================
# 7. Regressions with full controls
# ============================================================
print("=" * 60)
print("REGRESSIONS WITH FINANCIAL CONTROLS")
print("=" * 60)

# Subset: firms with both AI and Compustat data
reg_data = master[
    master['ai_sentence_count'].notna() & 
    master['at'].notna() & 
    master['log_assets'].notna()
].copy()

print(f"Regression sample: {len(reg_data):,} firm-years")
print()

results_log = []

# --- Reg 1: AI Disclosure (0/1) on Year + Controls ---
print("--- Reg 1: AI_Disclosure ~ Year + Controls + Firm FE ---")
reg_data['AI_Disclosure'] = (reg_data['ai_sentence_count'] > 0).astype(int)

# Drop rows missing key controls
reg1 = reg_data.dropna(subset=['AI_Disclosure', 'year', 'log_assets', 'ROA', 'leverage'])
print(f"  Sample: {len(reg1):,}")

try:
    model1 = smf.logit('AI_Disclosure ~ year + log_assets + ROA + leverage + rd_intensity + cash_ratio',
                       data=reg1).fit(disp=False, maxiter=100)
    print(model1.summary())
    results_log.append({
        'model': 'AI_Disclosure ~ Year + Controls (Logit)',
        'n_obs': len(reg1),
        'year_coef': model1.params.get('year'),
        'year_pval': model1.pvalues.get('year'),
        'pseudo_r2': model1.prsquared,
    })
except Exception as e:
    print(f"  Error: {e}")

print()

# --- Reg 2: Substantive Ratio on Year + Controls ---
print("--- Reg 2: Substantive_Ratio ~ Year + Controls ---")
reg2 = reg_data.dropna(subset=['substantive_ratio', 'year', 'log_assets', 'ROA', 'leverage'])
reg2 = reg2[reg2['ai_sentence_count'] > 0]  # Only AI-disclosing firms
print(f"  Sample: {len(reg2):,}")

if len(reg2) > 10:
    try:
        model2 = smf.ols('substantive_ratio ~ year + log_assets + ROA + leverage + rd_intensity',
                         data=reg2).fit(cov_type='HC3')
        print(model2.summary())
        results_log.append({
            'model': 'Substantive_Ratio ~ Year + Controls (OLS)',
            'n_obs': len(reg2),
            'year_coef': model2.params.get('year'),
            'year_pval': model2.pvalues.get('year'),
            'r_squared': model2.rsquared,
        })
    except Exception as e:
        print(f"  Error: {e}")

print()

# --- Reg 3: AI Sentence Count on Year + Controls (Poisson-like) ---
print("--- Reg 3: AI_Sentence_Count ~ Year + Controls (OLS on log) ---")
reg3 = reg_data.dropna(subset=['ai_sentence_count', 'year', 'log_assets', 'ROA', 'leverage'])
reg3['log_ai_count'] = np.log1p(reg3['ai_sentence_count'])
print(f"  Sample: {len(reg3):,}")

try:
    model3 = smf.ols('log_ai_count ~ year + log_assets + ROA + leverage + rd_intensity + cash_ratio',
                     data=reg3).fit(cov_type='HC3')
    print(model3.summary())
    results_log.append({
        'model': 'log(AI_Count+1) ~ Year + Controls (OLS)',
        'n_obs': len(reg3),
        'year_coef': model3.params.get('year'),
        'year_pval': model3.pvalues.get('year'),
        'r_squared': model3.rsquared,
    })
except Exception as e:
    print(f"  Error: {e}")

print()

# --- Reg 4: Substantive vs Generic density ---
print("--- Reg 4: Substantive_Density vs Generic_Density ~ Year + Controls ---")
reg4 = reg_data.dropna(subset=['year', 'log_assets', 'ROA', 'leverage']).copy()
reg4['sub_density'] = reg4['substantive_cnt'] / reg4['ai_sentence_count'].replace(0, np.nan)
reg4 = reg4.dropna(subset=['sub_density'])
print(f"  Sample: {len(reg4):,}")

if len(reg4) > 10:
    try:
        model4 = smf.ols('sub_density ~ year + log_assets + ROA + leverage + rd_intensity',
                         data=reg4).fit(cov_type='HC3')
        print(model4.summary())
        results_log.append({
            'model': 'Sub_Density ~ Year + Controls',
            'n_obs': len(reg4),
            'year_coef': model4.params.get('year'),
            'year_pval': model4.pvalues.get('year'),
            'r_squared': model4.rsquared,
        })
    except Exception as e:
        print(f"  Error: {e}")

print()

# --- Reg 5: Firm Fixed Effects ---
print("--- Reg 5: log(AI_Count) ~ Year + Controls + Firm FE ---")
reg5 = reg3.copy()
reg5['gvkey_str'] = reg5['gvkey'].astype(str)
# Only firms with multiple observations
firm_counts = reg5.groupby('gvkey_str')['year'].count()
multi_firms = firm_counts[firm_counts >= 2].index
reg5 = reg5[reg5['gvkey_str'].isin(multi_firms)]
print(f"  Sample: {len(reg5):,} firm-years, {reg5['gvkey_str'].nunique():,} firms")

if len(reg5) > 20:
    try:
        model5 = smf.ols('log_ai_count ~ year + log_assets + ROA + leverage + C(gvkey_str)',
                         data=reg5).fit(cov_type='HC3')
        print(model5.summary())
        results_log.append({
            'model': 'log(AI_Count) ~ Year + Controls + Firm FE',
            'n_obs': len(reg5),
            'year_coef': model5.params.get('year'),
            'year_pval': model5.pvalues.get('year'),
            'r_squared': model5.rsquared,
        })
    except Exception as e:
        print(f"  Error: {e}")

print()

# Save regression summary
reg_summary = pd.DataFrame(results_log)
reg_summary.to_csv(RESULTS_DIR / "regression_summary_master.csv", index=False)
print(f"✅ Regression summary saved")

# ============================================================
# 8. Descriptive stats
# ============================================================
print()
print("=" * 60)
print("DESCRIPTIVE STATISTICS")
print("=" * 60)

print("\n--- Financial Variables (AI-disclosing firms) ---")
ai_firms = reg_data[reg_data['ai_sentence_count'] > 0]
print(ai_firms[['at', 'revt', 'ni', 'ROA', 'leverage', 'rd_intensity', 'log_assets']].describe().round(2).to_string())

print("\n--- AI Variables by Year ---")
yearly_ai = reg_data.groupby('year').agg(
    n_firms=('gvkey', 'nunique'),
    ai_disclosure_rate=('AI_Disclosure', 'mean'),
    mean_ai_sentences=('ai_sentence_count', 'mean'),
    mean_substantive=('substantive_cnt', 'mean'),
    mean_substantive_ratio=('substantive_ratio', 'mean'),
).round(3)
print(yearly_ai.to_string())

print("\n--- Top 10 Firms by Substantive AI Disclosure ---")
top_sub = reg_data.groupby('gvkey').agg(
    conm=('conm', 'first'),
    ticker=('ticker', 'first'),
    total_ai=('ai_sentence_count', 'sum'),
    total_sub=('substantive_cnt', 'sum'),
    n_years=('year', 'nunique'),
).sort_values('total_sub', ascending=False).head(10)
top_sub['sub_pct'] = (top_sub['total_sub'] / top_sub['total_ai'] * 100).round(1)
print(top_sub[['conm', 'ticker', 'total_ai', 'total_sub', 'sub_pct', 'n_years']].to_string())

print()
print("=" * 60)
print("ALL DONE")
print("=" * 60)
