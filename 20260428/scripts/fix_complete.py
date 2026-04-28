"""
Complete fix script:
1. Fix fiscal year alignment (NLP filing year vs Compustat fiscal year)
2. Re-merge all control variables including additional ones from WRDS
3. Winsorize extreme variables at 1%/99%
4. Add sample flags for regression samples
"""

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# 1. Load all source data
# ---------------------------------------------------------------------------
print("=== Loading source data ===")

# Current panel (already has fiscal year fix from previous run, but missing some vars)
current_panel = pd.read_csv('/home/ricoz/econ_lab/FE-NLP/20260426/firm_year_panel_regression_ready.csv')
print(f"Current panel: {len(current_panel)} rows, {len(current_panel.columns)} cols")

# Old panel with additional variables (IBES forecasts, CRSP momentum, etc.)
old_panel = pd.read_csv('/home/ricoz/econ_lab/FE-NLP/20260426/archive/data/firm_year_ai_disclosure_summary_with_controls_and_forecasts.csv')
print(f"Old panel: {len(old_panel)} rows, {len(old_panel.columns)} cols")

# Base controls from Compustat
controls = pd.read_csv('/home/ricoz/econ_lab/FE-NLP/Data_Cleaning_NEW/data/final/control_variables.csv')
print(f"Controls: {len(controls)} rows, {len(controls.columns)} cols")

# ---------------------------------------------------------------------------
# 2. Identify variable sources
# ---------------------------------------------------------------------------
print("\n=== Identifying variable sources ===")

# NLP columns (from the original summary)
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

# Variables that come from Compustat base controls
base_control_vars = [
    'log_assets', 'ROA', 'leverage', 'debt_at', 'sales_growth', 'rd_to_assets',
    'capex_to_assets', 'intangibles_to_assets', 'tobin_q', 'prcc_f', 'csho',
    'cash_ratio', 'ppe_ratio', 'log_emp', 'at', 'ni', 'lt', 'sale', 'xrd', 'capx', 'intan'
]

# Variables that come from additional WRDS fetch (old panel has these)
additional_vars = [
    'gsector', 'ggroup', 'gind', 'spcindcd',  # GICS classifications
    'mkt_cap', 'book_to_market', 'dividend_payer', 'dividend_yield',
    'advertising_intensity', 'sga_intensity', 'gross_margin', 'operating_margin',
    'ebitda_margin', 'net_margin', 'interest_coverage', 'current_ratio',
    'ppe_intensity', 'goodwill_intensity', 'cash_holdings', 'wc_to_assets',
    'debt_issuance', 'equity_issuance', 'acquisition', 'stock_repurchases',
    'rd_dummy', 'loss_indicator', 'ocf_to_assets', 'fcf_to_assets', 'investment',
    'inventory_to_assets', 'receivables_to_assets', 'log_emp2',
    'depreciation_to_assets', 'tax_rate', 'ceq',
    'quick_ratio', 'debt_to_assets', 'asset_turnover',
    'momentum_12m', 'volatility_12m'
]

# IBES forecast variables
ibes_vars = [
    'fy1_meanest', 'fy1_medest', 'fy1_numest', 'fy1_stdev', 'fy1_actual', 'fy1_statpers',
    'fy2_meanest', 'fy2_medest', 'fy2_numest', 'fy2_stdev', 'fy2_actual', 'fy2_statpers'
]

# Variables that need to be computed or come from additional sources
computed_vars = ['price_to_earnings', 'ROE', 'sector']

# Check what's available in old panel
print("Additional vars in old panel:")
for v in additional_vars + ibes_vars + ['price_to_earnings', 'ROE']:
    if v in old_panel.columns:
        non_null = old_panel[v].notna().sum()
        print(f"  {v}: {non_null}/{len(old_panel)} ({non_null/len(old_panel)*100:.1f}%)")
    else:
        print(f"  {v}: NOT FOUND")

# ---------------------------------------------------------------------------
# 3. Build the corrected panel
# ---------------------------------------------------------------------------
print("\n=== Building corrected panel ===")

# Start with NLP data from current panel (already has correct fiscal year alignment)
nlp_data = current_panel[nlp_cols].copy()

# Parse datadate to determine the correct Compustat fyear for merging
# We need to re-derive this since we're rebuilding from scratch
nlp_data['datadate'] = pd.to_datetime(current_panel['datadate'])
nlp_data['datadate_month'] = nlp_data['datadate'].dt.month

# For datadate months 1-5: fiscal year ended early in calendar year
# NLP filing year needs +1 to match Compustat fyear
nlp_data['compustat_fyear'] = nlp_data['fiscal_year'].copy()
mask_early = nlp_data['datadate_month'].isin([1, 2, 3, 4, 5])
nlp_data.loc[mask_early, 'compustat_fyear'] = nlp_data.loc[mask_early, 'fiscal_year'] + 1

print(f"Fiscal year alignment: {mask_early.sum()} observations adjusted (+1)")

# Ticker normalization for merge
ticker_map = {
    'BRK-B': 'BRK.B',
    'GOOG': 'GOOGL',
    'BF-B': 'BF.B',
    'NWS': 'NWSA',
    'FOX': 'FOXA',
}
nlp_data['tic_merge'] = nlp_data['ticker'].replace(ticker_map).str.upper()
controls['tic_merge'] = controls['tic'].str.upper()

# Merge base controls using corrected fyear
merged = nlp_data.merge(
    controls,
    left_on=['tic_merge', 'compustat_fyear'],
    right_on=['tic_merge', 'fyear'],
    how='left',
    suffixes=('', '_ctrl')
)
merged = merged.drop(columns=[c for c in merged.columns if c.endswith('_ctrl')])
merged = merged.drop(columns=['tic_merge'])

print(f"After base controls merge: {len(merged)} rows, {len(merged.columns)} cols")

# ---------------------------------------------------------------------------
# 4. Add additional variables from old panel
# ---------------------------------------------------------------------------
print("\n=== Adding additional variables from old panel ===")

# Create merge key: ticker + fiscal_year (NLP's original filing year)
old_panel['tic_merge'] = old_panel['ticker'].replace(ticker_map).str.upper()
merged['tic_merge'] = merged['ticker'].replace(ticker_map).str.upper()

# Variables to bring from old panel
vars_from_old = [v for v in (additional_vars + ibes_vars + ['price_to_earnings', 'ROE']) if v in old_panel.columns]
print(f"Variables to transfer from old panel: {len(vars_from_old)}")

old_subset = old_panel[['tic_merge', 'fiscal_year', 'accession_number'] + vars_from_old].copy()

# Merge on ticker + fiscal_year + accession_number to ensure exact match
merged = merged.merge(
    old_subset,
    left_on=['tic_merge', 'fiscal_year', 'accession_number'],
    right_on=['tic_merge', 'fiscal_year', 'accession_number'],
    how='left',
    suffixes=('', '_old')
)

# Drop duplicate columns that came from old panel (keep the new ones if they exist)
for col in merged.columns:
    if col.endswith('_old'):
        base_col = col[:-4]
        if base_col in merged.columns:
            # Keep old version where new version is null
            merged[base_col] = merged[base_col].fillna(merged[col])
        merged = merged.drop(columns=[col])

merged = merged.drop(columns=['tic_merge'])

print(f"After additional vars merge: {len(merged)} rows, {len(merged.columns)} cols")

# Check coverage of key additional vars
for v in ['price_to_earnings', 'ROE', 'momentum_12m', 'book_to_market']:
    if v in merged.columns:
        non_null = merged[v].notna().sum()
        print(f"  {v}: {non_null}/{len(merged)} ({non_null/len(merged)*100:.1f}%)")

# ---------------------------------------------------------------------------
# 5. Rebuild future (lead) variables with correct alignment
# ---------------------------------------------------------------------------
print("\n=== Rebuilding future (lead) variables ===")

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

merged = merged.merge(
    lead_merge,
    left_on=['gvkey', 'compustat_fyear'],
    right_on=['gvkey', 'fyear'],
    how='left',
    suffixes=('', '_lead')
)
merged = merged.drop(columns=[c for c in merged.columns if c.endswith('_lead')])

# Future variable coverage
for c in ['future_ROA', 'future_sales_growth', 'future_earnings_growth',
          'future_capex_to_assets', 'future_rd_to_assets', 'future_operating_performance']:
    if c in merged.columns:
        non_null = merged[c].notna().sum()
        print(f"  {c}: {non_null}/{len(merged)} ({non_null/len(merged)*100:.1f}%)")

# ---------------------------------------------------------------------------
# 6. Add sector mapping
# ---------------------------------------------------------------------------
print("\n=== Adding sector mapping ===")

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

merged['sector'] = merged['sic'].apply(sic_to_sector)

# ---------------------------------------------------------------------------
# 7. Winsorization at 1% / 99%
# ---------------------------------------------------------------------------
print("\n=== Winsorization (1% / 99%) ===")

vars_to_winsorize = [
    'tobin_q', 'sales_growth', 'future_sales_growth', 'future_earnings_growth',
    'price_to_earnings', 'leverage', 'book_to_market', 'momentum_12m', 'ROE'
]

for var in vars_to_winsorize:
    if var not in merged.columns:
        print(f"  SKIP: {var} not found")
        continue
    
    raw = merged[var].copy()
    valid_mask = raw.notna()
    if valid_mask.sum() == 0:
        print(f"  SKIP: {var} has no non-null values")
        continue
    
    valid_values = raw[valid_mask]
    lower = valid_values.quantile(0.01)
    upper = valid_values.quantile(0.99)
    
    winsorized = raw.copy()
    winsorized = winsorized.clip(lower=lower, upper=upper)
    
    merged[f'{var}_winsorized'] = winsorized
    
    n_lower = (raw < lower).sum()
    n_upper = (raw > upper).sum()
    print(f"  {var}: clipped {n_lower} below {lower:.4f}, {n_upper} above {upper:.4f}")

# ---------------------------------------------------------------------------
# 8. Add sample flags
# ---------------------------------------------------------------------------
print("\n=== Adding sample flags ===")

# Define main AI disclosure variables (must be non-null)
ai_vars = [
    'ai_candidate_sentence_intensity',
    'substantive_ai_disclosure_sentence_intensity',
    'substantive_ai_implementation_sentence_intensity',
    'substantive_ai_risk_governance_sentence_intensity'
]

# Baseline controls (must be non-null for both samples)
baseline_controls = [
    'log_assets', 'ROA', 'leverage', 'sales_growth',
    'rd_to_assets', 'capex_to_assets', 'intangibles_to_assets'
]

# Check which AI vars exist
ai_vars_exist = [v for v in ai_vars if v in merged.columns]
print(f"AI disclosure vars available: {ai_vars_exist}")

# Check which baseline controls exist
baseline_exist = [v for v in baseline_controls if v in merged.columns]
print(f"Baseline controls available: {baseline_exist}")

# Sample flag 1: Valuation regression (Tobin's Q)
# Requirements: non-missing Tobin's Q, AI disclosure vars, baseline controls
conditions_valuation = []
if 'tobin_q' in merged.columns:
    conditions_valuation.append(merged['tobin_q'].notna())
for v in ai_vars_exist:
    conditions_valuation.append(merged[v].notna())
for v in baseline_exist:
    conditions_valuation.append(merged[v].notna())

if conditions_valuation:
    merged['sample_valuation'] = pd.concat(conditions_valuation, axis=1).all(axis=1).astype(int)
else:
    merged['sample_valuation'] = 0

# Sample flag 2: Future performance regression
# Requirements: non-missing future_ROA OR future_sales_growth OR future_earnings_growth,
# plus AI disclosure vars and baseline controls
future_outcomes = ['future_ROA', 'future_sales_growth', 'future_earnings_growth']
future_exist = [v for v in future_outcomes if v in merged.columns]
print(f"Future outcome vars available: {future_exist}")

conditions_future = []
if future_exist:
    conditions_future.append(merged[future_exist].notna().any(axis=1))
for v in ai_vars_exist:
    conditions_future.append(merged[v].notna())
for v in baseline_exist:
    conditions_future.append(merged[v].notna())

if conditions_future:
    merged['sample_future_performance'] = pd.concat(conditions_future, axis=1).all(axis=1).astype(int)
else:
    merged['sample_future_performance'] = 0

print(f"\nsample_valuation: {merged['sample_valuation'].sum()}/{len(merged)} ({merged['sample_valuation'].mean()*100:.1f}%)")
print(f"sample_future_performance: {merged['sample_future_performance'].sum()}/{len(merged)} ({merged['sample_future_performance'].mean()*100:.1f}%)")

# ---------------------------------------------------------------------------
# 9. Clean up and save
# ---------------------------------------------------------------------------
print("\n=== Cleaning up and saving ===")

# Drop helper columns
merged = merged.drop(columns=['datadate_month', 'compustat_fyear'], errors='ignore')

# Reorder columns: NLP first, then controls, then sample flags
nlp_cols_final = [c for c in nlp_cols if c in merged.columns]
other_cols = [c for c in merged.columns if c not in nlp_cols_final + ['sample_valuation', 'sample_future_performance']]
flag_cols = ['sample_valuation', 'sample_future_performance']
final_cols = nlp_cols_final + other_cols + flag_cols
merged = merged[final_cols]

out_path = '/home/ricoz/econ_lab/FE-NLP/20260426/firm_year_panel_regression_ready.csv'
merged.to_csv(out_path, index=False)

print(f"\nSaved to {out_path}")
print(f"Total rows: {len(merged)}")
print(f"Total columns: {len(merged.columns)}")

# Final coverage report
print("\n=== FINAL COVERAGE REPORT ===")
key_vars = [
    'sic', 'naics', 'gsubind', 'sector', 'gsector', 'ggroup', 'gind',
    'log_assets', 'ROA', 'ROE', 'ROE_winsorized',
    'leverage', 'leverage_winsorized', 'debt_at', 'sales_growth', 'sales_growth_winsorized',
    'rd_to_assets', 'capex_to_assets', 'intangibles_to_assets',
    'tobin_q', 'tobin_q_winsorized', 'cash_ratio', 'ppe_ratio', 'log_emp',
    'book_to_market', 'book_to_market_winsorized',
    'momentum_12m', 'momentum_12m_winsorized',
    'price_to_earnings', 'price_to_earnings_winsorized',
    'future_ROA', 'future_sales_growth', 'future_sales_growth_winsorized',
    'future_earnings_growth', 'future_earnings_growth_winsorized',
    'future_capex_to_assets', 'future_rd_to_assets', 'future_operating_performance',
    'fy1_meanest', 'fy1_numest', 'fy2_meanest',
    'sample_valuation', 'sample_future_performance'
]
for c in key_vars:
    if c in merged.columns:
        non_null = merged[c].notna().sum()
        print(f"  {c:<40s} {non_null:>5}/{len(merged)} ({non_null/len(merged)*100:>5.1f}%)")
    else:
        print(f"  {c:<40s} NOT FOUND")
