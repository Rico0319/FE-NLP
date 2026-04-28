"""
CRITICAL FIX: Correct fiscal year alignment for non-December FYE companies.

The previous fix_fiscal_year_and_winsorize.py had the WRONG direction:
- It ADDED 1 to fiscal_year for Jan-May FYE companies
- It should SUBTRACT 1

Why:
- NLP fiscal_year = filing year (from accession number)
  e.g., BF-B 2019: accession 19 = filed in 2019 = FY2019 10-K (ended April 2019)
  
- Compustat fyear = fiscal year START year (for Jan-May FYE companies)
  e.g., BF.B fyear=2018 -> datadate=2019-04-30 (FY May 2018 - April 2019)
        BF.B fyear=2019 -> datadate=2020-04-30 (FY May 2019 - April 2020)

- Correct relationship: controls fyear = NLP fiscal_year - 1
  e.g., NLP 2019 -> controls fyear=2018 -> FY2019 data (ended April 2019)

The previous script did: compustat_fyear = fiscal_year + 1
This matched NLP 2019 to controls fyear=2020 -> FY2021 data (2 years ahead!)

This script:
1. Rebuilds from the original panel_final.csv (which had correct 1-year-ahead match)
2. Applies the correct -1 adjustment
3. Re-adds winsorized variables, sample flags, post_ai, dummies
"""

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# 1. Load original panel (before any fix scripts)
# ---------------------------------------------------------------------------
# Use firm_year_panel_final.csv which was the last known good state
# Actually, panel_final also had the 1-year-ahead problem. 
# We need to rebuild from scratch using the correct alignment.

controls = pd.read_csv("/home/ricoz/econ_lab/FE-NLP/Data_Cleaning_NEW/data/final/control_variables.csv")
nlp = pd.read_csv("/home/ricoz/econ_lab/FE-NLP/20260426/希望是真的nlp/nlp_outputs/firm_year_ai_disclosure_summary.csv")

# Use the original panel_final as the base (it has all the extra columns)
# But we need to fix the fiscal year alignment
panel_orig = pd.read_csv("/home/ricoz/econ_lab/FE-NLP/20260426/firm_year_panel_final.csv")

print(f"Original panel: {len(panel_orig)} rows, {len(panel_orig.columns)} columns")
print(f"Controls: {len(controls)} rows")
print(f"NLP summary: {len(nlp)} rows")

# The controls CSV only has 30 columns. The original panel had 116 columns.
# The extra columns were added by fetch_additional_controls.py and fetch_ibes_forecasts.py.
# We need to re-run those scripts or merge from the original panel with corrected alignment.

# Best approach: Take the original panel, identify which rows have wrong alignment,
# and swap the controls data with the correct year's data.

# For Jan-May FYE companies, the original panel matched NLP fiscal_year=N to controls fyear=N.
# But it should have matched to controls fyear=N-1.
# So we need to: for each (ticker, fiscal_year) in Jan-May FYE companies,
# replace controls data with controls data from fyear=fiscal_year-1.

# Let's implement this:
print("\n=== CORRECTION STRATEGY ===")
print("For Jan-May FYE companies: shift controls back by 1 year")

# Identify Jan-May FYE companies from datadate
panel_orig['datadate'] = pd.to_datetime(panel_orig['datadate'])
panel_orig['fye_month'] = panel_orig['datadate'].dt.month
mask_early = panel_orig['fye_month'].isin([1, 2, 3, 4, 5])

print(f"Rows with Jan-May FYE: {mask_early.sum()}")
print(f"Tickers: {sorted(panel_orig[mask_early]['ticker'].unique())}")

# For these rows, we need to replace controls with data from fyear-1
# The controls columns are everything except NLP columns
nlp_cols = [
    'cik', 'ticker', 'company_name', 'fiscal_year', 'accession_number',
    'mdna_total_sentence_count', 'mdna_total_word_count', 'n_kept_sentences',
    'n_ai_candidate_sentences', 'n_generic_ai_disclosure_sentences',
    'n_substantive_ai_implementation_sentences', 'n_substantive_ai_risk_governance_sentences',
    'n_substantive_ai_disclosure_sentences', 'ai_candidate_sentence_intensity',
    'generic_ai_disclosure_sentence_intensity', 'substantive_ai_disclosure_sentence_intensity',
    'substantive_ai_implementation_sentence_intensity', 'substantive_ai_risk_governance_sentence_intensity',
    'ai_candidate_per_10000_words', 'generic_ai_disclosure_per_10000_words',
    'substantive_ai_disclosure_per_10000_words', 'substantive_ai_implementation_per_10000_words',
    'substantive_ai_risk_governance_per_10000_words'
]

# All other columns are controls (including the extra ones from additional scripts)
control_cols = [c for c in panel_orig.columns if c not in nlp_cols]
print(f"\nControl columns to correct: {len(control_cols)}")

# Check if extra columns exist in controls
extra_in_controls = [c for c in control_cols if c in controls.columns]
extra_not_in_controls = [c for c in control_cols if c not in controls.columns]
print(f"Extra columns that ARE in controls: {len(extra_in_controls)}")
print(f"Extra columns NOT in controls: {len(extra_not_in_controls)}")
print("Not in controls:", extra_not_in_controls[:20])

# Given the complexity, let's use the following approach:
# 1. Start with original panel (has all 116 columns)
# 2. For Jan-May FYE rows, replace control columns with data from the PREVIOUS fiscal year
#    (which is the correct alignment)

panel_fixed = panel_orig.copy()

# For Jan-May FYE rows, get the correct controls
for idx in panel_fixed[mask_early].index:
    gvkey = panel_fixed.loc[idx, 'gvkey']
    curr_fyear = panel_fixed.loc[idx, 'fyear']
    target_fyear = curr_fyear - 1
    
    # Find the row with the target fyear for the same gvkey
    target_row = panel_orig[(panel_orig['gvkey'] == gvkey) & (panel_orig['fyear'] == target_fyear)]
    
    if len(target_row) == 1:
        # Replace control columns
        for col in control_cols:
            if col in target_row.columns and col in panel_fixed.columns:
                panel_fixed.loc[idx, col] = target_row[col].values[0]
    elif len(target_row) == 0:
        # No target row found - this is the first year (e.g., 2019 for BF-B)
        # We need to get data from controls directly
        t = panel_fixed.loc[idx, 'ticker']
        target_controls = controls[(controls['tic'] == t.replace('BF-B', 'BF.B').replace('BRK-B', 'BRK.B')) & (controls['fyear'] == target_fyear)]
        if len(target_controls) == 1:
            for col in control_cols:
                if col in target_controls.columns and col in panel_fixed.columns:
                    panel_fixed.loc[idx, col] = target_controls[col].values[0]

print(f"\nFixed {mask_early.sum()} rows")

# Verify
print("\n=== Post-fix verification ===")
for comp in ['BF-B', 'WMT', 'NKE']:
    subset = panel_fixed[panel_fixed['ticker'] == comp][['ticker', 'fiscal_year', 'fyear', 'datadate', 'at', 'sale', 'ni']].head(5)
    if len(subset) > 0:
        print(f"\n{comp}:")
        print(subset.to_string())

# Now recompute future variables with correct alignment
print("\n=== Recomputing future variables ===")
controls_sorted = controls.sort_values(['gvkey', 'fyear'])

lead_vars = ['ROA', 'sales_growth', 'capex_to_assets', 'rd_to_assets', 'ni', 'sale']
for var in lead_vars:
    controls_sorted[f'future_{var}'] = controls_sorted.groupby('gvkey')[var].shift(-1)

controls_sorted['future_earnings_growth'] = np.where(
    controls_sorted['ni'].abs() > 1e-9,
    (controls_sorted['future_ni'] - controls_sorted['ni']) / controls_sorted['ni'].abs(),
    np.nan
)
controls_sorted['future_operating_performance'] = controls_sorted['future_ROA']

# Merge future variables back
lead_merge = controls_sorted[['gvkey', 'fyear', 'future_ROA', 'future_sales_growth',
                               'future_earnings_growth', 'future_capex_to_assets',
                               'future_rd_to_assets', 'future_operating_performance']].copy()

panel_fixed = panel_fixed.merge(
    lead_merge,
    left_on=['gvkey', 'fyear'],
    right_on=['gvkey', 'fyear'],
    how='left',
    suffixes=('', '_lead')
)

# Drop old future columns and rename new ones
for col in ['future_ROA', 'future_sales_growth', 'future_earnings_growth', 
            'future_capex_to_assets', 'future_rd_to_assets', 'future_operating_performance']:
    if f'{col}_lead' in panel_fixed.columns:
        panel_fixed[col] = panel_fixed[f'{col}_lead']
        panel_fixed = panel_fixed.drop(columns=[f'{col}_lead'])

# Now add winsorized vars, post_ai, dummies, sample flags
print("\n=== Adding derived variables ===")

# Winsorization
vars_to_winsorize = [
    'tobin_q', 'sales_growth', 'future_sales_growth', 'future_earnings_growth',
    'price_to_earnings', 'leverage', 'book_to_market', 'momentum_12m', 'ROE'
]

for var in vars_to_winsorize:
    if var not in panel_fixed.columns:
        print(f"  SKIP: {var} not found")
        continue
    raw = panel_fixed[var].copy()
    valid_mask = raw.notna()
    if valid_mask.sum() == 0:
        continue
    lower = raw[valid_mask].quantile(0.01)
    upper = raw[valid_mask].quantile(0.99)
    panel_fixed[f'{var}_winsorized'] = raw.clip(lower=lower, upper=upper)
    print(f"  {var}: winsorized")

# Post-AI and dummies
panel_fixed['post_ai'] = (panel_fixed['fiscal_year'] >= 2023).astype(int)
panel_fixed['has_ai_candidate'] = (panel_fixed['n_ai_candidate_sentences'] > 0).astype(int)
panel_fixed['has_generic_ai'] = (panel_fixed['n_generic_ai_disclosure_sentences'] > 0).astype(int)
panel_fixed['has_substantive_ai'] = (panel_fixed['n_substantive_ai_disclosure_sentences'] > 0).astype(int)

# Sample flags
ai_main = ['n_ai_candidate_sentences', 'n_generic_ai_disclosure_sentences',
           'n_substantive_ai_disclosure_sentences']
baseline_controls = ['log_assets', 'leverage', 'sales_growth', 'rd_to_assets',
                     'capex_to_assets', 'ROA']

panel_fixed['sample_valuation'] = (
    panel_fixed['tobin_q_winsorized'].notna() &
    panel_fixed[ai_main].notna().all(axis=1) &
    panel_fixed[baseline_controls].notna().all(axis=1)
).astype(int)

future_outcomes = ['future_ROA', 'future_sales_growth_winsorized',
                   'future_earnings_growth_winsorized']

panel_fixed['sample_future_performance'] = (
    panel_fixed[future_outcomes].notna().all(axis=1) &
    panel_fixed[ai_main].notna().all(axis=1) &
    panel_fixed[baseline_controls].notna().all(axis=1)
).astype(int)

# Deduplicate
panel_fixed = panel_fixed.sort_values('accession_number').drop_duplicates(subset=['ticker', 'fiscal_year'], keep='last')

# Save
out_path = "/home/ricoz/econ_lab/FE-NLP/20260426/firm_year_panel_regression_ready.csv"
panel_fixed.to_csv(out_path, index=False)

print(f"\n=== Saved to {out_path} ===")
print(f"Total rows: {len(panel_fixed)}")
print(f"Total columns: {len(panel_fixed.columns)}")

# Coverage report
print("\n=== COVERAGE ===")
print(f"sample_valuation: {panel_fixed['sample_valuation'].sum()}/{len(panel_fixed)}")
print(f"sample_future_performance: {panel_fixed['sample_future_performance'].sum()}/{len(panel_fixed)}")
print(f"post_ai=1: {panel_fixed['post_ai'].sum()}")

# Verify
pk_dup = panel_fixed.groupby(['ticker', 'fiscal_year']).size().reset_index(name='count')
print(f"Duplicates: {(pk_dup['count']>1).sum()}")

# Check BF-B 2019
bf = panel_fixed[(panel_fixed['ticker']=='BF-B') & (panel_fixed['fiscal_year']==2019)]
if len(bf) > 0:
    print("\nBF-B 2019:")
    print(bf[['ticker', 'fiscal_year', 'fyear', 'datadate', 'at', 'sale', 'ni', 'ROA']].to_string())

# The controls CSV only has 30 columns. The original panel had 116 columns.
# The extra columns were added by fetch_additional_controls.py and fetch_ibes_forecasts.py.
# We need to re-run those scripts or merge from the original panel with corrected alignment.

# Best approach: Take the original panel, identify which rows have wrong alignment,
# and swap the controls data with the correct year's data.

# For Jan-May FYE companies, the original panel matched NLP fiscal_year=N to controls fyear=N.
# But it should have matched to controls fyear=N-1.
# So we need to: for each (ticker, fiscal_year) in Jan-May FYE companies,
# replace controls data with controls data from fyear=fiscal_year-1.

# Let's implement this:
print("\n=== CORRECTION STRATEGY ===")
print("For Jan-May FYE companies: shift controls back by 1 year")

# Load original panel
panel_orig = pd.read_csv("/home/ricoz/econ_lab/FE-NLP/20260426/firm_year_panel_final.csv")

# Identify Jan-May FYE companies from datadate
panel_orig['datadate'] = pd.to_datetime(panel_orig['datadate'])
panel_orig['fye_month'] = panel_orig['datadate'].dt.month
mask_early = panel_orig['fye_month'].isin([1, 2, 3, 4, 5])

print(f"Rows with Jan-May FYE: {mask_early.sum()}")
print(f"Tickers: {sorted(panel_orig[mask_early]['ticker'].unique())}")

# For these rows, we need to replace controls with data from fyear-1
# The controls columns are everything except NLP columns
nlp_cols = [
    'cik', 'ticker', 'company_name', 'fiscal_year', 'accession_number',
    'mdna_total_sentence_count', 'mdna_total_word_count', 'n_kept_sentences',
    'n_ai_candidate_sentences', 'n_generic_ai_disclosure_sentences',
    'n_substantive_ai_implementation_sentences', 'n_substantive_ai_risk_governance_sentences',
    'n_substantive_ai_disclosure_sentences', 'ai_candidate_sentence_intensity',
    'generic_ai_disclosure_sentence_intensity', 'substantive_ai_disclosure_sentence_intensity',
    'substantive_ai_implementation_sentence_intensity', 'substantive_ai_risk_governance_sentence_intensity',
    'ai_candidate_per_10000_words', 'generic_ai_disclosure_per_10000_words',
    'substantive_ai_disclosure_per_10000_words', 'substantive_ai_implementation_per_10000_words',
    'substantive_ai_risk_governance_per_10000_words'
]

# All other columns are controls (including the extra ones from additional scripts)
control_cols = [c for c in panel_orig.columns if c not in nlp_cols]
print(f"\nControl columns to correct: {len(control_cols)}")

# For Jan-May FYE rows, get the correct year's data from controls
# We need to match on (gvkey, fyear_corrected)
# But some extra columns (like momentum_12m) come from different sources.
# For simplicity, let's re-merge ALL controls from the original panel using gvkey.

# Actually, the simplest approach:
# 1. For each row with Jan-May FYE, find the same ticker with fyear = current_fyear - 1
# 2. But the original panel already has the wrong fyear. We need to look up in controls.

# Let's re-merge controls with corrected fyear for ALL rows
# This will give us the correct base controls (log_assets, ROA, etc.)
# For extra columns, we need to check if they were also from controls or from other sources.

# Check if extra columns exist in controls
extra_in_controls = [c for c in control_cols if c in controls.columns]
extra_not_in_controls = [c for c in control_cols if c not in controls.columns]
print(f"\nExtra columns that ARE in controls: {len(extra_in_controls)}")
print(f"Extra columns NOT in controls: {len(extra_not_in_controls)}")
print("Not in controls:", extra_not_in_controls[:20])

# For columns not in controls, they came from other scripts (fetch_additional_controls, fetch_ibes)
# We need to re-merge those or take them from the original panel.

# For now, let's do a complete rebuild:
# 1. Start with NLP data
# 2. Merge ALL controls (including extra columns) from the original panel with corrected alignment
# 3. The extra columns were merged on gvkey + fyear, so we can re-merge them.

# But wait - the original panel already has the extra columns merged with WRONG alignment.
# We need to re-fetch them or shift them.

# Given the complexity, let's use the following approach:
# 1. Start with original panel (has all 116 columns)
# 2. For Jan-May FYE rows, replace control columns with data from the PREVIOUS fiscal year
#    (which is the correct alignment)

# To do this, we'll create a mapping: for each (gvkey, fyear) in original panel,
# if it's Jan-May FYE, use controls from (gvkey, fyear-1) instead.

# Let's implement this shift
panel_fixed = panel_orig.copy()

# For Jan-May FYE rows, get the correct controls
for idx in panel_fixed[mask_early].index:
    gvkey = panel_fixed.loc[idx, 'gvkey']
    curr_fyear = panel_fixed.loc[idx, 'fyear']
    target_fyear = curr_fyear - 1
    
    # Find the row with the target fyear for the same gvkey
    target_row = panel_orig[(panel_orig['gvkey'] == gvkey) & (panel_orig['fyear'] == target_fyear)]
    
    if len(target_row) == 1:
        # Replace control columns
        for col in control_cols:
            if col in target_row.columns and col in panel_fixed.columns:
                panel_fixed.loc[idx, col] = target_row[col].values[0]
    elif len(target_row) == 0:
        # No target row found - this is the first year (e.g., 2019 for BF-B)
        # We need to get data from controls directly
        t = panel_fixed.loc[idx, 'ticker']
        target_controls = controls[(controls['tic'] == t.replace('BF-B', 'BF.B').replace('BRK-B', 'BRK.B')) & (controls['fyear'] == target_fyear)]
        if len(target_controls) == 1:
            for col in control_cols:
                if col in target_controls.columns and col in panel_fixed.columns:
                    panel_fixed.loc[idx, col] = target_controls[col].values[0]

print(f"\nFixed {mask_early.sum()} rows")

# Verify
print("\n=== Post-fix verification ===")
for comp in ['BF-B', 'WMT', 'NKE']:
    subset = panel_fixed[panel_fixed['ticker'] == comp][['ticker', 'fiscal_year', 'fyear', 'datadate', 'at', 'sale', 'ni']].head(5)
    if len(subset) > 0:
        print(f"\n{comp}:")
        print(subset.to_string())

# Now recompute future variables with correct alignment
print("\n=== Recomputing future variables ===")
controls_sorted = controls.sort_values(['gvkey', 'fyear'])

lead_vars = ['ROA', 'sales_growth', 'capex_to_assets', 'rd_to_assets', 'ni', 'sale']
for var in lead_vars:
    controls_sorted[f'future_{var}'] = controls_sorted.groupby('gvkey')[var].shift(-1)

controls_sorted['future_earnings_growth'] = np.where(
    controls_sorted['ni'].abs() > 1e-9,
    (controls_sorted['future_ni'] - controls_sorted['ni']) / controls_sorted['ni'].abs(),
    np.nan
)
controls_sorted['future_operating_performance'] = controls_sorted['future_ROA']

# Merge future variables back
lead_merge = controls_sorted[['gvkey', 'fyear', 'future_ROA', 'future_sales_growth',
                               'future_earnings_growth', 'future_capex_to_assets',
                               'future_rd_to_assets', 'future_operating_performance']].copy()

panel_fixed = panel_fixed.merge(
    lead_merge,
    left_on=['gvkey', 'fyear'],
    right_on=['gvkey', 'fyear'],
    how='left',
    suffixes=('', '_lead')
)

# Drop old future columns and rename new ones
for col in ['future_ROA', 'future_sales_growth', 'future_earnings_growth', 
            'future_capex_to_assets', 'future_rd_to_assets', 'future_operating_performance']:
    if f'{col}_lead' in panel_fixed.columns:
        panel_fixed[col] = panel_fixed[f'{col}_lead']
        panel_fixed = panel_fixed.drop(columns=[f'{col}_lead'])

# Now add winsorized vars, post_ai, dummies, sample flags
print("\n=== Adding derived variables ===")

# Winsorization
vars_to_winsorize = [
    'tobin_q', 'sales_growth', 'future_sales_growth', 'future_earnings_growth',
    'price_to_earnings', 'leverage', 'book_to_market', 'momentum_12m', 'ROE'
]

for var in vars_to_winsorize:
    if var not in panel_fixed.columns:
        print(f"  SKIP: {var} not found")
        continue
    raw = panel_fixed[var].copy()
    valid_mask = raw.notna()
    if valid_mask.sum() == 0:
        continue
    lower = raw[valid_mask].quantile(0.01)
    upper = raw[valid_mask].quantile(0.99)
    panel_fixed[f'{var}_winsorized'] = raw.clip(lower=lower, upper=upper)
    print(f"  {var}: winsorized")

# Post-AI and dummies
panel_fixed['post_ai'] = (panel_fixed['fiscal_year'] >= 2023).astype(int)
panel_fixed['has_ai_candidate'] = (panel_fixed['n_ai_candidate_sentences'] > 0).astype(int)
panel_fixed['has_generic_ai'] = (panel_fixed['n_generic_ai_disclosure_sentences'] > 0).astype(int)
panel_fixed['has_substantive_ai'] = (panel_fixed['n_substantive_ai_disclosure_sentences'] > 0).astype(int)

# Sample flags
ai_main = ['n_ai_candidate_sentences', 'n_generic_ai_disclosure_sentences',
           'n_substantive_ai_disclosure_sentences']
baseline_controls = ['log_assets', 'leverage', 'sales_growth', 'rd_to_assets',
                     'capex_to_assets', 'ROA']

panel_fixed['sample_valuation'] = (
    panel_fixed['tobin_q_winsorized'].notna() &
    panel_fixed[ai_main].notna().all(axis=1) &
    panel_fixed[baseline_controls].notna().all(axis=1)
).astype(int)

future_outcomes = ['future_ROA', 'future_sales_growth_winsorized',
                   'future_earnings_growth_winsorized']

panel_fixed['sample_future_performance'] = (
    panel_fixed[future_outcomes].notna().all(axis=1) &
    panel_fixed[ai_main].notna().all(axis=1) &
    panel_fixed[baseline_controls].notna().all(axis=1)
).astype(int)

# Deduplicate
panel_fixed = panel_fixed.sort_values('accession_number').drop_duplicates(subset=['ticker', 'fiscal_year'], keep='last')

# Save
out_path = "/home/ricoz/econ_lab/FE-NLP/20260426/firm_year_panel_regression_ready.csv"
panel_fixed.to_csv(out_path, index=False)

print(f"\n=== Saved to {out_path} ===")
print(f"Total rows: {len(panel_fixed)}")
print(f"Total columns: {len(panel_fixed.columns)}")

# Coverage report
print("\n=== COVERAGE ===")
print(f"sample_valuation: {panel_fixed['sample_valuation'].sum()}/{len(panel_fixed)}")
print(f"sample_future_performance: {panel_fixed['sample_future_performance'].sum()}/{len(panel_fixed)}")
print(f"post_ai=1: {panel_fixed['post_ai'].sum()}")

# Verify
pk_dup = panel_fixed.groupby(['ticker', 'fiscal_year']).size().reset_index(name='count')
print(f"Duplicates: {(pk_dup['count']>1).sum()}")

# Check BF-B 2019
bf = panel_fixed[(panel_fixed['ticker']=='BF-B') & (panel_fixed['fiscal_year']==2019)]
if len(bf) > 0:
    print("\nBF-B 2019:")
    print(bf[['ticker', 'fiscal_year', 'fyear', 'datadate', 'at', 'sale', 'ni', 'ROA']].to_string())

# ---------------------------------------------------------------------------
# 2. Parse datadate to determine FYE month
# ---------------------------------------------------------------------------
controls['datadate'] = pd.to_datetime(controls['datadate'])
controls['fye_month'] = controls['datadate'].dt.month

# For Jan-May FYE companies, Compustat fyear = start year
# We need to map NLP fiscal_year to correct controls fyear

# ---------------------------------------------------------------------------
# 3. Build correct mapping
# ---------------------------------------------------------------------------
# NLP fiscal_year = filing year
# For Jan-May FYE: filing year = FYE year, controls fyear = start year = FYE year - 1
# For Jun-Dec FYE: filing year = FYE year, controls fyear = FYE year (same)

# But we don't have FYE info directly. We can infer from datadate month.
# However, we need to match NLP to controls FIRST to get datadate.

# Alternative approach: use the original panel's datadate to determine FYE month
# The original panel had the correct datadate (just wrong fyear alignment)

# Let's use a two-step approach:
# Step 1: Merge NLP with controls on (ticker, fiscal_year) to get initial datadate
# Step 2: Check if datadate month is Jan-May
# Step 3: If Jan-May, re-merge with controls on (ticker, fiscal_year-1)

# Ticker normalization
ticker_map = {'BRK-B': 'BRK.B', 'GOOG': 'GOOGL', 'BF-B': 'BF.B', 'NWS': 'NWSA', 'FOX': 'FOXA'}
nlp['tic_merge'] = nlp['ticker'].replace(ticker_map).str.upper()
controls['tic_merge'] = controls['tic'].str.upper().replace(ticker_map)

# Step 1: Initial merge on exact fiscal_year match
merged = nlp.merge(
    controls,
    left_on=['tic_merge', 'fiscal_year'],
    right_on=['tic_merge', 'fyear'],
    how='left',
    suffixes=('', '_ctrl')
)

# Step 2: Identify Jan-May FYE companies from initial merge
merged['datadate'] = pd.to_datetime(merged['datadate'])
merged['fye_month'] = merged['datadate'].dt.month

# Companies with datadate in Jan-May need adjustment
mask_early = merged['fye_month'].isin([1, 2, 3, 4, 5])
print(f"\nCompanies with Jan-May FYE (from initial merge): {mask_early.sum()} rows")

# For these, the correct controls fyear should be fiscal_year - 1, not fiscal_year
# But wait - the initial merge on fiscal_year=fyear already gave us the "wrong" alignment
# (1 year ahead). For Jan-May FYE, we need to go back 1 year.

# Actually, let's think about this more carefully:
# Original merge: NLP 2019 -> controls fyear=2019 -> datadate=2020-04-30 (FY2020)
# Correct: NLP 2019 -> controls fyear=2018 -> datadate=2019-04-30 (FY2019)
# So we need to subtract 1 from the matched fyear for Jan-May FYE companies

# But we can't just subtract 1 from fyear in the merged data - we need to re-merge
# with the correct fyear.

# Let's identify which companies have Jan-May FYE
early_fye_tickers = merged[mask_early]['ticker'].unique()
print(f"Tickers with Jan-May FYE: {sorted(early_fye_tickers)[:10]}... ({len(early_fye_tickers)} total)")

# Step 3: For Jan-May FYE companies, create adjusted fiscal_year
nlp_corrected = nlp.copy()
nlp_corrected['fiscal_year_adj'] = nlp_corrected['fiscal_year'].copy()

# Mark which tickers need adjustment
needs_adjustment = nlp_corrected['ticker'].isin(early_fye_tickers)
print(f"\nNLP rows needing adjustment: {needs_adjustment.sum()}")

# For these, we need to match to controls fyear = fiscal_year - 1
# But we need to verify this is correct for ALL Jan-May FYE companies

# Let's check a few examples manually
print("\n=== Manual verification ===")
for t in ['BF-B', 'WMT', 'NKE']:
    t_nlp = nlp_corrected[nlp_corrected['ticker'] == t]
    for _, row in t_nlp.iterrows():
        fy = row['fiscal_year']
        # Check controls for this ticker at fyear=fy and fyear=fy-1
        t_ctrl_fy = controls[(controls['tic_merge'] == t.replace('BF-B', 'BF.B').replace('BRK-B', 'BRK.B')) & (controls['fyear'] == fy)]
        t_ctrl_fy_minus1 = controls[(controls['tic_merge'] == t.replace('BF-B', 'BF.B').replace('BRK-B', 'BRK.B')) & (controls['fyear'] == fy - 1)]
        
        if len(t_ctrl_fy) > 0:
            dd_fy = t_ctrl_fy['datadate'].values[0]
            dd_str = str(dd_fy)[:10] if pd.notna(dd_fy) else 'N/A'
            print(f"{t} NLP {fy}: controls fyear={fy} -> datadate={dd_str}")
        if len(t_ctrl_fy_minus1) > 0:
            dd_fy1 = t_ctrl_fy_minus1['datadate'].values[0]
            dd_str1 = str(dd_fy1)[:10] if pd.notna(dd_fy1) else 'N/A'
            print(f"{t} NLP {fy}: controls fyear={fy-1} -> datadate={dd_str1}")
        print()

# Based on the verification, apply the correction
# For Jan-May FYE companies: use fiscal_year - 1 for controls merge
nlp_corrected.loc[needs_adjustment, 'fiscal_year_adj'] = nlp_corrected.loc[needs_adjustment, 'fiscal_year'] - 1

print("\n=== Applying correction ===")
print(f"NLP rows with adjusted fiscal_year: {(nlp_corrected['fiscal_year_adj'] != nlp_corrected['fiscal_year']).sum()}")

# Step 4: Re-merge with corrected fiscal_year
merged_corrected = nlp_corrected.merge(
    controls,
    left_on=['tic_merge', 'fiscal_year_adj'],
    right_on=['tic_merge', 'fyear'],
    how='left',
    suffixes=('', '_ctrl')
)

# Drop duplicate columns
merged_corrected = merged_corrected.drop(columns=[c for c in merged_corrected.columns if c.endswith('_ctrl')])
merged_corrected = merged_corrected.drop(columns=['tic_merge', 'fiscal_year_adj', 'fye_month'], errors='ignore')

print(f"\nRe-merged rows: {len(merged_corrected)}")

# Verify alignment
print("\n=== Post-fix alignment check ===")
for comp in ['BF-B', 'WMT', 'NKE']:
    subset = merged_corrected[merged_corrected['ticker'] == comp][['ticker', 'fiscal_year', 'fyear', 'datadate', 'at', 'sale', 'ni']].head(5)
    if len(subset) > 0:
        print(f"\n{comp}:")
        print(subset.to_string())

# ---------------------------------------------------------------------------
# 4. Add lead (future) variables with correct alignment
# ---------------------------------------------------------------------------
controls_sorted = controls.sort_values(['gvkey', 'fyear'])

lead_vars = ['ROA', 'sales_growth', 'capex_to_assets', 'rd_to_assets', 'ni', 'sale']
for var in lead_vars:
    controls_sorted[f'future_{var}'] = controls_sorted.groupby('gvkey')[var].shift(-1)

controls_sorted['future_earnings_growth'] = np.where(
    controls_sorted['ni'].abs() > 1e-9,
    (controls_sorted['future_ni'] - controls_sorted['ni']) / controls_sorted['ni'].abs(),
    np.nan
)
controls_sorted['future_operating_performance'] = controls_sorted['future_ROA']

lead_merge = controls_sorted[['gvkey', 'fyear', 'future_ROA', 'future_sales_growth',
                               'future_earnings_growth', 'future_capex_to_assets',
                               'future_rd_to_assets', 'future_operating_performance']].copy()

# Merge lead variables on gvkey + corrected fyear
merged_corrected = merged_corrected.merge(
    lead_merge,
    left_on=['gvkey', 'fyear'],
    right_on=['gvkey', 'fyear'],
    how='left',
    suffixes=('', '_lead')
)

# Drop duplicate columns
merged_corrected = merged_corrected.drop(columns=[c for c in merged_corrected.columns if c.endswith('_lead')])

# ---------------------------------------------------------------------------
# 5. Add sector mapping
# ---------------------------------------------------------------------------
def sic_to_sector(sic):
    if pd.isna(sic):
        return None
    sic = int(sic)
    if 100 <= sic <= 999: return "Agriculture"
    if 1000 <= sic <= 1299: return "Mining"
    if 1300 <= sic <= 1399: return "Oil_Gas"
    if 1400 <= sic <= 1499: return "Mining"
    if 1500 <= sic <= 1799: return "Construction"
    if 2000 <= sic <= 2099: return "Food"
    if 2100 <= sic <= 2199: return "Tobacco"
    if 2200 <= sic <= 2299: return "Textiles"
    if 2300 <= sic <= 2399: return "Apparel"
    if 2400 <= sic <= 2499: return "Lumber"
    if 2500 <= sic <= 2599: return "Furniture"
    if 2600 <= sic <= 2661: return "Paper"
    if 2700 <= sic <= 2799: return "Printing"
    if 2800 <= sic <= 2824: return "Chemicals"
    if 2830 <= sic <= 2836: return "Pharma"
    if 2840 <= sic <= 2899: return "Chemicals"
    if 2900 <= sic <= 2999: return "Petroleum"
    if 3000 <= sic <= 3099: return "Rubber"
    if 3100 <= sic <= 3199: return "Leather"
    if 3200 <= sic <= 3299: return "Stone_Clay_Glass"
    if 3300 <= sic <= 3399: return "Steel"
    if 3400 <= sic <= 3499: return "Fabricated_Metal"
    if 3500 <= sic <= 3599: return "Machinery"
    if 3600 <= sic <= 3699: return "Electrical_Equipment"
    if 3700 <= sic <= 3799: return "Transportation_Equipment"
    if 3800 <= sic <= 3879: return "Instruments"
    if 3900 <= sic <= 3999: return "Misc_Manufacturing"
    if 4000 <= sic <= 4799: return "Transportation"
    if 4800 <= sic <= 4899: return "Utilities"
    if 4900 <= sic <= 4949: return "Utilities"
    if 5000 <= sic <= 5199: return "Wholesale"
    if 5200 <= sic <= 5999: return "Retail"
    if 6000 <= sic <= 6411: return "Finance"
    if 6500 <= sic <= 6999: return "Real_Estate"
    if 7000 <= sic <= 7369: return "Services"
    if 7370 <= sic <= 7379: return "Technology"
    if 7380 <= sic <= 7999: return "Services"
    if 8000 <= sic <= 8999: return "Healthcare_Services"
    if 9000 <= sic <= 9999: return "Public_Admin"
    return "Other"

merged_corrected['sector'] = merged_corrected['sic'].apply(sic_to_sector)

# ---------------------------------------------------------------------------
# 6. Winsorization at 1% / 99%
# ---------------------------------------------------------------------------
print("\n=== Winsorization ===")

vars_to_winsorize = [
    'tobin_q', 'sales_growth', 'future_sales_growth', 'future_earnings_growth',
    'price_to_earnings', 'leverage', 'book_to_market', 'momentum_12m', 'ROE'
]

for var in vars_to_winsorize:
    if var not in merged_corrected.columns:
        print(f"  SKIP: {var} not found in columns")
        continue
    
    raw = merged_corrected[var].copy()
    valid_mask = raw.notna()
    if valid_mask.sum() == 0:
        print(f"  SKIP: {var} has no non-null values")
        continue
    
    valid_values = raw[valid_mask]
    lower = valid_values.quantile(0.01)
    upper = valid_values.quantile(0.99)
    
    winsorized = raw.copy()
    winsorized = winsorized.clip(lower=lower, upper=upper)
    
    merged_corrected[f'{var}_winsorized'] = winsorized
    
    n_lower = (raw < lower).sum()
    n_upper = (raw > upper).sum()
    print(f"  {var}: clipped {n_lower} below {lower:.4f}, {n_upper} above {upper:.4f}")

# ---------------------------------------------------------------------------
# 7. Add post_ai and disclosure dummies
# ---------------------------------------------------------------------------
merged_corrected['post_ai'] = (merged_corrected['fiscal_year'] >= 2023).astype(int)
merged_corrected['has_ai_candidate'] = (merged_corrected['n_ai_candidate_sentences'] > 0).astype(int)
merged_corrected['has_generic_ai'] = (merged_corrected['n_generic_ai_disclosure_sentences'] > 0).astype(int)
merged_corrected['has_substantive_ai'] = (merged_corrected['n_substantive_ai_disclosure_sentences'] > 0).astype(int)

# ---------------------------------------------------------------------------
# 8. Add sample flags
# ---------------------------------------------------------------------------
ai_main = ['n_ai_candidate_sentences', 'n_generic_ai_disclosure_sentences',
           'n_substantive_ai_disclosure_sentences']
baseline_controls = ['log_assets', 'leverage', 'sales_growth', 'rd_to_assets',
                     'capex_to_assets', 'ROA']

merged_corrected['sample_valuation'] = (
    merged_corrected['tobin_q_winsorized'].notna() &
    merged_corrected[ai_main].notna().all(axis=1) &
    merged_corrected[baseline_controls].notna().all(axis=1)
).astype(int)

future_outcomes = ['future_ROA', 'future_sales_growth_winsorized',
                   'future_earnings_growth_winsorized']

merged_corrected['sample_future_performance'] = (
    merged_corrected[future_outcomes].notna().all(axis=1) &
    merged_corrected[ai_main].notna().all(axis=1) &
    merged_corrected[baseline_controls].notna().all(axis=1)
).astype(int)

# ---------------------------------------------------------------------------
# 9. Clean up and save
# ---------------------------------------------------------------------------
# Drop helper columns
merged_corrected = merged_corrected.drop(columns=['datadate_month', 'compustat_fyear'], errors='ignore')

# Reorder columns: NLP first, then controls
nlp_cols = [
    'gvkey', 'fiscal_year', 'ticker', 'company_name', 'cik', 'accession_number',
    'mdna_total_sentence_count', 'mdna_total_word_count', 'n_kept_sentences',
    'n_ai_candidate_sentences', 'n_generic_ai_disclosure_sentences',
    'n_substantive_ai_implementation_sentences', 'n_substantive_ai_risk_governance_sentences',
    'n_substantive_ai_disclosure_sentences', 'ai_candidate_sentence_intensity',
    'generic_ai_disclosure_sentence_intensity', 'substantive_ai_disclosure_sentence_intensity',
    'substantive_ai_implementation_sentence_intensity', 'substantive_ai_risk_governance_sentence_intensity',
    'ai_candidate_per_10000_words', 'generic_ai_disclosure_per_10000_words',
    'substantive_ai_disclosure_per_10000_words', 'substantive_ai_implementation_per_10000_words',
    'substantive_ai_risk_governance_per_10000_words'
]

nlp_cols_final = [c for c in nlp_cols if c in merged_corrected.columns]
control_cols_final = [c for c in merged_corrected.columns if c not in nlp_cols_final]
merged_corrected = merged_corrected[nlp_cols_final + control_cols_final]

# Save deduplicated data
out_path = "/home/ricoz/econ_lab/FE-NLP/20260426/firm_year_panel_regression_ready.csv"
merged_corrected.to_csv(out_path, index=False)

print(f"\n=== Saved to {out_path} ===")
print(f"Total rows: {len(merged_corrected)}")
print(f"Total columns: {len(merged_corrected.columns)}")

# Coverage report
print("\n=== FUTURE (LEAD) VARIABLE COVERAGE ===")
future_cols = ['future_ROA', 'future_sales_growth', 'future_earnings_growth',
               'future_capex_to_assets', 'future_rd_to_assets', 'future_operating_performance']
for c in future_cols:
    if c in merged_corrected.columns:
        non_null = merged_corrected[c].notna().sum()
        print(f"  {c}: {non_null}/{len(merged_corrected)} ({non_null/len(merged_corrected)*100:.1f}%)")

print("\n=== WINSORIZED VARIABLE COVERAGE ===")
for c in merged_corrected.columns:
    if '_winsorized' in c:
        non_null = merged_corrected[c].notna().sum()
        print(f"  {c}: {non_null}/{len(merged_corrected)} ({non_null/len(merged_corrected)*100:.1f}%)")

print("\n=== SAMPLE FLAGS ===")
print(f"  sample_valuation: {merged_corrected['sample_valuation'].sum()}/{len(merged_corrected)} ({merged_corrected['sample_valuation'].mean()*100:.1f}%)")
print(f"  sample_future_performance: {merged_corrected['sample_future_performance'].sum()}/{len(merged_corrected)} ({merged_corrected['sample_future_performance'].mean()*100:.1f}%)")

print("\n=== POST-AI & DUMMIES ===")
print(f"  post_ai=1: {merged_corrected['post_ai'].sum()}")
print(f"  has_ai_candidate: {merged_corrected['has_ai_candidate'].sum()}")
print(f"  has_generic_ai: {merged_corrected['has_generic_ai'].sum()}")
print(f"  has_substantive_ai: {merged_corrected['has_substantive_ai'].sum()}")

# CRM FY2022: keep the later filing (000008 is 2022-03-11, 000013 is 2022-03-11)
# Actually both are same date, keep one arbitrarily
# SMCI FY2019: keep 000079 (2019-12-19) over 000039 (2019-08-16) - later filing
# SMCI FY2025: keep 000027 (2025-08-28) over 000004 (2025-08-28) - same date

# For now, keep the last accession number (higher sequence number)
merged_corrected = merged_corrected.sort_values('accession_number').drop_duplicates(subset=['ticker', 'fiscal_year'], keep='last')

print(f"\nAfter dedup: {len(merged_corrected)} rows")

# Verify no duplicates
pk_dup = merged_corrected.groupby(['ticker', 'fiscal_year']).size().reset_index(name='count')
print(f"Remaining duplicates: {(pk_dup['count']>1).sum()}")

# Save
out_path = "/home/ricoz/econ_lab/FE-NLP/20260426/firm_year_panel_regression_ready.csv"
merged_corrected.to_csv(out_path, index=False)

print(f"\n=== Saved to {out_path} ===")
print(f"Total rows: {len(merged_corrected)}")
print(f"Total columns: {len(merged_corrected.columns)}")
