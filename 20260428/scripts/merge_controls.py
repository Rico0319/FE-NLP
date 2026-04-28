import pandas as pd
import numpy as np

summary_path = "/home/ricoz/econ_lab/FE-NLP/20260426/firm_year_ai_disclosure_summary.csv"
controls_path = "/home/ricoz/econ_lab/FE-NLP/Data_Cleaning_NEW/data/final/control_variables.csv"
out_path = "/home/ricoz/econ_lab/FE-NLP/20260426/firm_year_ai_disclosure_summary_with_controls.csv"

summary = pd.read_csv(summary_path)
controls = pd.read_csv(controls_path)

# --- Step 1: Ticker normalization and merge ---
ticker_map = {
    'BRK-B': 'BRK.B',
    'GOOG': 'GOOGL',
    'BF-B': 'BF.B',
    'NWS': 'NWSA',
    'FOX': 'FOXA',
}
summary['tic_merge'] = summary['ticker'].replace(ticker_map).str.upper()
controls['tic_merge'] = controls['tic'].str.upper()

merged = summary.merge(
    controls,
    left_on=['tic_merge', 'fiscal_year'],
    right_on=['tic_merge', 'fyear'],
    how='left',
    suffixes=('', '_ctrl')
)

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
merged = merged.drop(columns=['tic_merge'])

# --- Step 2: Create t+1 lead variables from controls ---
controls_sorted = controls.sort_values(['gvkey', 'fyear'])

lead_vars = ['ROA', 'sales_growth', 'capex_to_assets', 'rd_to_assets', 'ni', 'sale']
for var in lead_vars:
    controls_sorted[f'future_{var}'] = controls_sorted.groupby('gvkey')[var].shift(-1)

# Future earnings growth = (NI(t+1) - NI(t)) / |NI(t)|
controls_sorted['future_earnings_growth'] = np.where(
    controls_sorted['ni'].abs() > 1e-9,
    (controls_sorted['future_ni'] - controls_sorted['ni']) / controls_sorted['ni'].abs(),
    np.nan
)

# Future operating performance: use future ROA as primary proxy
controls_sorted['future_operating_performance'] = controls_sorted['future_ROA']

# Keep only the lead columns for merging
lead_merge = controls_sorted[['gvkey', 'fyear', 'future_ROA', 'future_sales_growth',
                               'future_earnings_growth', 'future_capex_to_assets',
                               'future_rd_to_assets', 'future_operating_performance']].copy()

# Merge lead variables back on gvkey + fyear
merged = merged.merge(
    lead_merge,
    left_on=['gvkey_ctrl', 'fyear'],
    right_on=['gvkey', 'fyear'],
    how='left',
    suffixes=('', '_lead')
)

# Drop duplicate gvkey column from lead merge
if 'gvkey_lead' in merged.columns:
    merged = merged.drop(columns=['gvkey_lead'])
if 'gvkey' in merged.columns and 'gvkey_ctrl' in merged.columns:
    merged = merged.drop(columns=['gvkey'])

# --- Step 3: Save ---
merged.to_csv(out_path, index=False)

print(f"Saved final merged file to: {out_path}")
print(f"Total rows: {len(merged)}")
print(f"Total columns: {len(merged.columns)}")

future_cols = ['future_ROA', 'future_sales_growth', 'future_earnings_growth',
               'future_capex_to_assets', 'future_rd_to_assets', 'future_operating_performance']
print("\n=== FUTURE (LEAD) VARIABLE COVERAGE ===")
for c in future_cols:
    non_null = merged[c].notna().sum()
    print(f"  {c}: {non_null}/{len(merged)} ({non_null/len(merged)*100:.1f}%)")

key_controls = ['sic', 'naics', 'gsubind', 'sector', 'log_assets', 'ROA', 'leverage',
                'debt_at', 'sales_growth', 'rd_to_assets', 'capex_to_assets',
                'intangibles_to_assets', 'tobin_q', 'cash_ratio', 'ppe_ratio', 'log_emp']
print("\n=== KEY CONTROL VARIABLE COVERAGE ===")
for c in key_controls:
    if c in merged.columns:
        non_null = merged[c].notna().sum()
        print(f"  {c}: {non_null}/{len(merged)} ({non_null/len(merged)*100:.1f}%)")
