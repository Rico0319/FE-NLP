# FE-NLP Regression-Ready Panel Dataset

**File:** `firm_year_panel_regression_ready.csv`  
**Created:** April 27, 2026  
**Shape:** 3,315 rows × 107 columns

## Summary

This is a cleaned, deduplicated firm-year panel dataset ready for regression analysis. Each row represents one firm-year observation with AI disclosure measures from 10-K MD&A sections and financial control variables from Compustat.

## Key Features

### Primary Key
- `gvkey` + `fiscal_year` — unique identifier for each firm-year

### Coverage
- **Firms:** 486 unique companies (S&P 500 constituents)
- **Years:** 2019–2025
- **Total observations:** 3,315 firm-years

### Year Distribution
| Year | Count |
|------|-------|
| 2019 | 466 |
| 2020 | 470 |
| 2021 | 476 |
| 2022 | 479 |
| 2023 | 480 |
| 2024 | 481 |
| 2025 | 463 |

## Data Cleaning Applied

### 1. Deduplication
- **Dual-class shares:** Consolidated FOX/FOXA, GOOG/GOOGL, NWS/NWSA → kept the class with CIK (FOXA, GOOGL, NWSA)
- **Multi-accession cases:** For firms with multiple 10-K filings in same fiscal year, kept the latest filing:
  - CRM FY2022: kept `0001108524-22-000013` (filed 2022-03-11)
  - SMCI FY2019: kept `0001375365-19-000079` (filed 2019-12-19)
  - SMCI FY2025: kept `0001375365-25-000027` (filed 2025-08-28)

### 2. Duplicate Columns Removed
Dropped redundant columns, keeping the preferred version:
- `fiscal_year` (kept) vs `fyear` (dropped)
- `ticker` (kept) vs `tic` (dropped)
- `company_name` (kept) vs `conm` (dropped)
- `gvkey` from NLP (kept) vs `gvkey_ctrl` (dropped)
- `cik` from NLP (kept) vs `cik_ctrl` (dropped)
- `leverage` (kept) vs `debt_to_assets` (dropped)
- `ppe_ratio` (kept) vs `ppe_intensity` (dropped)
- `cash_ratio` (kept) vs `cash_holdings` (dropped)
- `future_ROA` (kept) vs `future_operating_performance` (dropped)
- `log_emp` (kept) vs `log_emp2` (dropped)

### 3. Missing Data Handling
- **FY2025 control data:** 23 firms with non-December fiscal year ends (BF-B, CAG, GIS, NKE, etc.) had missing control variables because their FY2025 data is not yet in Compustat. These rows were **dropped**.
- **ROE winsorization:** Original ROE had extreme values (min: -65.36, max: 388.70) due to small/negative equity. Applied 1%/99% winsorization:
  - `ROE_winsorized` bounds: [-3.10, 3.65]
  - 68 observations were winsorized

## Variable Categories

### NLP/AI Disclosure Variables (24 columns)
- `mdna_total_sentence_count`, `mdna_total_word_count`
- `n_kept_sentences`
- `n_ai_candidate_sentences`
- `n_generic_ai_disclosure_sentences`
- `n_substantive_ai_implementation_sentences`
- `n_substantive_ai_risk_governance_sentences`
- `n_substantive_ai_disclosure_sentences`
- Various intensity and per-10,000-words measures

### Financial Control Variables (from Compustat)
- **Size:** `at`, `log_assets`, `mkt_cap`
- **Profitability:** `ni`, `ROA`, `ROE`, `ROE_winsorized`, `sale`, `log_sales`
- **Leverage:** `leverage`, `lt`, `debt_at`
- **Investment:** `capx`, `capex_to_assets`, `xrd`, `rd_to_assets`
- **Growth:** `sales_growth`, `future_ROA`, `future_sales_growth`, `future_earnings_growth`
- **Valuation:** `tobin_q`, `prcc_f`, `prcc_c`, `book_to_market`
- **Labor:** `emp`, `log_emp`
- **Industry:** `sic`, `naics`, `gsubind`, `sector`, `gsector`, `ggroup`, `gind`

### I/B/E/S Forecast Variables
- `fy1_meanest`, `fy1_medest`, `fy1_numest`, `fy1_stdev`, `fy1_actual`, `fy1_statpers`
- `fy2_meanest`, `fy2_medest`, `fy2_numest`, `fy2_stdev`, `fy2_actual`, `fy2_statpers`

### Market Variables
- `momentum_12m`, `volatility_12m`

## Usage Notes

1. **Primary key:** Use `gvkey` + `fiscal_year` for panel structure
2. **ROE for regression:** Use `ROE_winsorized` to avoid extreme value influence
3. **Missing data:** Some variables have high missing rates (e.g., `advertising_intensity`: 57.5%, `xrd`: 40.8%)
4. **Industry fixed effects:** Use `sector`, `sic`, `naics`, or `gsubind` for industry controls

## Files Generated

1. `firm_year_panel_regression_ready.csv` — Final cleaned panel (this file)
2. `firm_year_panel_final.csv` — Intermediate version with all rows (for reference)

## Data Quality Checks Passed

- ✅ No duplicate gvkey + fiscal_year combinations
- ✅ No duplicate ticker + fiscal_year combinations
- ✅ All rows have control variables (no missing `at`)
- ✅ Dual-class shares consolidated
- ✅ Multi-accession cases resolved
- ✅ Column naming consistent
