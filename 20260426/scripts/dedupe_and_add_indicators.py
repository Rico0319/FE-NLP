"""
Fix duplicate rows in regression-ready panel and add new variables:
1. Deduplicate exact duplicate rows (caused by re-running fix_fiscal_year_and_winsorize.py
   with input==output: each run merged from already-merged panel, doubling rows for
   dual-class share companies that share gvkey).
2. Add post_ai indicator: 1 if fiscal_year >= 2023, 0 if fiscal_year <= 2022.
3. Add disclosure dummies:
   - has_ai_candidate: 1 if n_ai_candidate_sentences > 0
   - has_generic_ai: 1 if n_generic_ai_disclosure_sentences > 0
   - has_substantive_ai: 1 if n_substantive_ai_disclosure_sentences > 0
"""

import pandas as pd
import numpy as np

PANEL_PATH = "/home/ricoz/econ_lab/FE-NLP/20260426/firm_year_panel_regression_ready.csv"

panel = pd.read_csv(PANEL_PATH)
print(f"Loaded panel: {len(panel)} rows, {len(panel.columns)} cols")

# ---------------------------------------------------------------------------
# 1. Deduplicate exact duplicate rows
# ---------------------------------------------------------------------------
before = len(panel)
panel = panel.drop_duplicates()
after = len(panel)
print(f"\n=== Deduplicated ===")
print(f"Removed {before - after} exact duplicate rows ({before} -> {after})")

# Verify primary key uniqueness
dup_check = panel.groupby(['ticker', 'fiscal_year']).size().reset_index(name='count')
remaining_dups = dup_check[dup_check['count'] > 1]
if len(remaining_dups) > 0:
    print(f"WARNING: {len(remaining_dups)} (ticker, fiscal_year) groups still have duplicates:")
    print(remaining_dups.to_string())
else:
    print("Primary key (ticker, fiscal_year) is unique.")

# ---------------------------------------------------------------------------
# 2. Add post_ai indicator
# ---------------------------------------------------------------------------
panel['post_ai'] = (panel['fiscal_year'] >= 2023).astype(int)
print(f"\n=== post_ai ===")
print(f"post_ai = 1 (fiscal_year >= 2023): {panel['post_ai'].sum()} rows")
print(f"post_ai = 0 (fiscal_year <= 2022): {(panel['post_ai'] == 0).sum()} rows")

# ---------------------------------------------------------------------------
# 3. Add disclosure dummies
# ---------------------------------------------------------------------------
panel['has_ai_candidate'] = (panel['n_ai_candidate_sentences'] > 0).astype(int)
panel['has_generic_ai'] = (panel['n_generic_ai_disclosure_sentences'] > 0).astype(int)
panel['has_substantive_ai'] = (panel['n_substantive_ai_disclosure_sentences'] > 0).astype(int)

print(f"\n=== Disclosure Dummies ===")
print(f"has_ai_candidate: {panel['has_ai_candidate'].sum()}/{len(panel)} ({panel['has_ai_candidate'].mean()*100:.1f}%)")
print(f"has_generic_ai: {panel['has_generic_ai'].sum()}/{len(panel)} ({panel['has_generic_ai'].mean()*100:.1f}%)")
print(f"has_substantive_ai: {panel['has_substantive_ai'].sum()}/{len(panel)} ({panel['has_substantive_ai'].mean()*100:.1f}%)")

# ---------------------------------------------------------------------------
# 4. Recompute sample flags (in case dedup changed coverage)
# ---------------------------------------------------------------------------
# sample_valuation: non-missing tobin_q, main AI disclosure, baseline controls
ai_main = ['n_ai_candidate_sentences', 'n_generic_ai_disclosure_sentences',
           'n_substantive_ai_disclosure_sentences']
baseline_controls = ['log_assets', 'leverage', 'sales_growth', 'rd_to_assets',
                     'capex_to_assets', 'ROA']

panel['sample_valuation'] = (
    panel['tobin_q_winsorized'].notna() &
    panel[ai_main].notna().all(axis=1) &
    panel[baseline_controls].notna().all(axis=1)
).astype(int)

future_outcomes = ['future_ROA', 'future_sales_growth_winsorized',
                   'future_earnings_growth_winsorized']

panel['sample_future_performance'] = (
    panel[future_outcomes].notna().all(axis=1) &
    panel[ai_main].notna().all(axis=1) &
    panel[baseline_controls].notna().all(axis=1)
).astype(int)

print(f"\n=== Sample Flags (recomputed) ===")
print(f"sample_valuation = 1: {panel['sample_valuation'].sum()}/{len(panel)} ({panel['sample_valuation'].mean()*100:.1f}%)")
print(f"sample_future_performance = 1: {panel['sample_future_performance'].sum()}/{len(panel)} ({panel['sample_future_performance'].mean()*100:.1f}%)")

# By year
print("\nsample_valuation by fiscal_year:")
print(panel.groupby('fiscal_year')['sample_valuation'].agg(['sum', 'count']).to_string())
print("\nsample_future_performance by fiscal_year:")
print(panel.groupby('fiscal_year')['sample_future_performance'].agg(['sum', 'count']).to_string())

# ---------------------------------------------------------------------------
# 5. Save
# ---------------------------------------------------------------------------
panel.to_csv(PANEL_PATH, index=False)
print(f"\n=== Saved {PANEL_PATH} ===")
print(f"Final rows: {len(panel)}, columns: {len(panel.columns)}")
print(f"\nNew columns added: post_ai, has_ai_candidate, has_generic_ai, has_substantive_ai")
