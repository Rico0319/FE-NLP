"""
Fix fiscal year alignment and add winsorized versions of control variables.

Problem: NLP's fiscal_year is filing year (from accession number), but Compustat's
fyear is the actual fiscal year. For companies with non-December fiscal year-ends,
these differ. E.g., WMT filed 10-K in March 2019 for FY ending Jan 2020:
- NLP fiscal_year = 2019 (filing year)
- Compustat fyear = 2020, datadate = 2020-01-31

Current merge matched NLP 2019 → Compustat fyear=2019 (datadate=2019-01-31),
which is the PREVIOUS fiscal year's data. This creates look-ahead bias for
future variables and misaligned controls.

Solution: Derive correct fiscal year from datadate month. If datadate is in
months 1-5, the fiscal year ended in the previous calendar year, so we need
to match NLP fiscal_year + 1 to Compustat fyear.
"""

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------------------------
panel_path = "/home/ricoz/econ_lab/FE-NLP/20260426/firm_year_panel_regression_ready.csv"
controls_path = "/home/ricoz/econ_lab/FE-NLP/Data_Cleaning_NEW/data/final/control_variables.csv"
out_path = "/home/ricoz/econ_lab/FE-NLP/20260426/firm_year_panel_regression_ready.csv"

panel = pd.read_csv(panel_path)
controls = pd.read_csv(controls_path)

print(f"Panel rows: {len(panel)}")
print(f"Controls rows: {len(controls)}")

# ---------------------------------------------------------------------------
# 2. Fix fiscal year alignment
# ---------------------------------------------------------------------------
# Parse datadate to determine the actual fiscal year
panel['datadate'] = pd.to_datetime(panel['datadate'])
panel['datadate_month'] = panel['datadate'].dt.month

# For companies with datadate in months 1-5, the fiscal year ended in the
# previous calendar year. So NLP filing year needs +1 to match Compustat fyear.
# For months 6-12, fiscal year ended in the same calendar year.
# This is a simplification; the exact rule depends on when the 10-K was filed.
# But for S&P 500 companies, FY ending Jan-May typically means the fiscal
# year is "named" by the year it started, not ended.
# E.g., WMT FY2020 ends Jan 31, 2020. Compustat calls it fyear=2020.
# NLP calls it fiscal_year=2019 (filing year). So we add 1.

panel['compustat_fyear'] = panel['fiscal_year'].copy()
# For datadate months 1-5: fiscal year ended early in the calendar year,
# so the "fiscal year label" in Compustat is the calendar year of the end date.
# NLP used filing year which is typically the previous calendar year.
mask_early = panel['datadate_month'].isin([1, 2, 3, 4, 5])
panel.loc[mask_early, 'compustat_fyear'] = panel.loc[mask_early, 'fiscal_year'] + 1

print(f"\n=== Fiscal Year Alignment Fix ===")
print(f"Companies with datadate in months 1-5 (fyear adjusted +1): {mask_early.sum()}")
print("Examples:")
examples = panel[panel['ticker'].isin(['WMT', 'NKE', 'BF-B', 'TGT'])][
    ['ticker', 'fiscal_year', 'compustat_fyear', 'datadate', 'accession_number']
].head(20)
print(examples.to_string())

# ---------------------------------------------------------------------------
# 3. Re-merge with corrected fiscal year
# ---------------------------------------------------------------------------
# Ticker normalization
ticker_map = {
    'BRK-B': 'BRK.B',
    'GOOG': 'GOOGL',
    'BF-B': 'BF.B',
    'NWS': 'NWSA',
    'FOX': 'FOXA',
}

# For the merge, we need to use the original NLP summary's ticker
# But panel already has the merged data. We need to re-extract NLP columns
# and re-merge with controls using the corrected fyear.

# Actually, let me take a different approach: the panel already has controls merged.
# I need to identify which rows have misaligned controls and fix them.
# The key issue is that for non-Dec FYE companies, the controls are from the wrong year.

# Let me rebuild from scratch: separate NLP data and controls, then re-merge.

# First, identify which columns are from NLP vs controls
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

# These are the control columns that were merged from Compustat
control_cols = [c for c in panel.columns if c not in nlp_cols + ['datadate_month', 'compustat_fyear']]
print(f"\nControl columns to re-merge: {len(control_cols)}")

# Extract just the NLP data
nlp_data = panel[nlp_cols + ['datadate_month', 'compustat_fyear']].copy()

# Add merge ticker
nlp_data['tic_merge'] = nlp_data['ticker'].replace(ticker_map).str.upper()
controls['tic_merge'] = controls['tic'].str.upper()

# Re-merge using corrected fyear
merged = nlp_data.merge(
    controls,
    left_on=['tic_merge', 'compustat_fyear'],
    right_on=['tic_merge', 'fyear'],
    how='left',
    suffixes=('', '_ctrl')
)

# Drop duplicate columns from controls
merged = merged.drop(columns=[c for c in merged.columns if c.endswith('_ctrl') and c.replace('_ctrl', '') in merged.columns])
merged = merged.drop(columns=['tic_merge'])

print(f"\nRe-merged rows: {len(merged)}")

# Check alignment for the example companies
print("\n=== Post-fix alignment check ===")
for comp in ['WMT', 'NKE', 'BF-B', 'TGT']:
    subset = merged[merged['ticker'] == comp][['ticker', 'fiscal_year', 'compustat_fyear', 'datadate', 'at', 'sale', 'ni']].head(5)
    print(f"\n{comp}:")
    print(subset.to_string())

# ---------------------------------------------------------------------------
# 4. Rebuild future (lead) variables with correct alignment
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

# Merge lead variables on gvkey + compustat_fyear
merged = merged.merge(
    lead_merge,
    left_on=['gvkey', 'compustat_fyear'],
    right_on=['gvkey', 'fyear'],
    how='left',
    suffixes=('', '_lead')
)

# Drop duplicate columns
merged = merged.drop(columns=[c for c in merged.columns if c.endswith('_lead')])

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

merged['sector'] = merged['sic'].apply(sic_to_sector)

# ---------------------------------------------------------------------------
# 6. Winsorization at 1% / 99%
# ---------------------------------------------------------------------------
print("\n=== Winsorization ===")

vars_to_winsorize = [
    'tobin_q', 'sales_growth', 'future_sales_growth', 'future_earnings_growth',
    'price_to_earnings', 'leverage', 'book_to_market', 'momentum_12m', 'ROE'
]

for var in vars_to_winsorize:
    if var not in merged.columns:
        print(f"  SKIP: {var} not found in columns")
        continue
    
    raw = merged[var].copy()
    # Only winsorize non-null values
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
    
    # Report extremes
    n_lower = (raw < lower).sum()
    n_upper = (raw > upper).sum()
    print(f"  {var}: clipped {n_lower} below {lower:.4f}, {n_upper} above {upper:.4f}")

# ---------------------------------------------------------------------------
# 7. Clean up and save
# ---------------------------------------------------------------------------
# Drop helper columns
merged = merged.drop(columns=['datadate_month', 'compustat_fyear'], errors='ignore')

# Reorder columns: NLP first, then controls
nlp_cols_final = [c for c in nlp_cols if c in merged.columns]
control_cols_final = [c for c in merged.columns if c not in nlp_cols_final]
merged = merged[nlp_cols_final + control_cols_final]

merged.to_csv(out_path, index=False)

print(f"\n=== Saved to {out_path} ===")
print(f"Total rows: {len(merged)}")
print(f"Total columns: {len(merged.columns)}")

# Coverage report
print("\n=== FUTURE (LEAD) VARIABLE COVERAGE ===")
future_cols = ['future_ROA', 'future_sales_growth', 'future_earnings_growth',
               'future_capex_to_assets', 'future_rd_to_assets', 'future_operating_performance']
for c in future_cols:
    if c in merged.columns:
        non_null = merged[c].notna().sum()
        print(f"  {c}: {non_null}/{len(merged)} ({non_null/len(merged)*100:.1f}%)")

print("\n=== WINSORIZED VARIABLE COVERAGE ===")
for c in merged.columns:
    if '_winsorized' in c:
        non_null = merged[c].notna().sum()
        print(f"  {c}: {non_null}/{len(merged)} ({non_null/len(merged)*100:.1f}%)")

print("\n=== KEY CONTROL VARIABLE COVERAGE ===")
key_controls = ['sic', 'naics', 'gsubind', 'sector', 'log_assets', 'ROA', 'ROE', 'ROE_winsorized',
                'leverage', 'debt_at', 'sales_growth', 'sales_growth_winsorized',
                'rd_to_assets', 'capex_to_assets', 'intangibles_to_assets', 'tobin_q', 'tobin_q_winsorized',
                'cash_ratio', 'ppe_ratio', 'log_emp', 'book_to_market', 'book_to_market_winsorized',
                'momentum_12m', 'momentum_12m_winsorized', 'price_to_earnings', 'price_to_earnings_winsorized']
for c in key_controls:
    if c in merged.columns:
        non_null = merged[c].notna().sum()
        print(f"  {c}: {non_null}/{len(merged)} ({non_null/len(merged)*100:.1f}%)")
