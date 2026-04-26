# FE-NLP: AI Disclosure in S&P 500 10-K Filings

Columbia University — Financial Economics Research Project

## Overview

This repository contains the full research pipeline for analyzing AI-related disclosures in S&P 500 10-K filings (2018–2025). The project distinguishes **substantive AI disclosure** from **generic AI talk** ("AI washing") and examines the relationship between AI disclosure quality and firm performance, valuation, and future outcomes.

### Research Questions

- **RQ1**: Can NLP distinguish substantive vs. generic AI disclosure in 10-K MD&A sections?
- **RQ2**: Is substantive AI disclosure associated with firm characteristics of technological transformation?
- **RQ3**: Does substantive AI disclosure provide incremental explanatory power for firm value, future profitability, and operating performance?

---

## Repository Structure

```
FE-NLP/
├── 20260426/                           # Current working session (control variables & final panel)
│   ├── firm_year_panel_final.csv       # ⭐ MASTER DATASET: firm-year panel with all controls & forecasts
│   ├── scripts/
│   │   ├── merge_controls.py           # Merge WRDS Compustat + CRSP + IBES controls into panel
│   │   ├── fetch_additional_controls.py # Pull supplemental ratios from WRDS (margin, momentum, etc.)
│   │   └── fetch_ibes_forecasts.py     # Pull analyst forecasts from IBES via WRDS
│   └── 希望是真的nlp/                    # Group B NLP pipeline (sentiment analysis code)
│
├── Data_Cleaning_NEW/                  # MD&A extraction pipeline (completed)
│   ├── scripts/
│   │   ├── extract_mda_sentences.py    # Main extraction script
│   │   ├── build_control_variables.py  # Core control variable builder
│   │   ├── fetch_wrds_supplemental.py  # Supplemental WRDS data pull
│   │   └── fetch_crsp_prices.py        # CRSP price fetching for Tobin's Q
│   └── README.md
│
├── NLP/                                # Classification & regression pipeline (active development)
│   ├── a_group_scripts/                # LLM-based classification scripts
│   ├── b_group_outputs/                # Classification outputs & caches
│   └── ...
│
├── NLP_test_deprecated/                # Legacy pipeline (deprecated, reference only)
│   ├── DEPRECATED.md                   # Migration guide
│   └── ...
│
├── resources(raw_data&definitions)/    # Raw data, definitions, and professor's papers
│   ├── Definition.pdf
│   ├── ma_pipeline/                    # Group A's NLP pipeline code
│   └── sp500_selected_industries_mdna_2018_2026.csv
│
├── Literature/                         # Literature review and reference papers
├── Meeting_Notes/                      # Meeting notes and proposal documents
└── README.md                           # This file
```

---

## Master Dataset

**File**: `20260426/firm_year_panel_final.csv`

A firm-year panel (3,362 observations, 116 columns) covering 486 S&P 500 firms with fiscal years 2019–2025.

### Key Variables

| Category | Variables |
|----------|-----------|
| **AI Disclosure** | `ai_sentiment_score`, `ai_sentiment_label` (from groupmates' NLP pipeline) |
| **Firm Fundamentals** | `log_assets`, `ROA`, `ROE`, `leverage`, `sales_growth`, `rd_to_assets`, `capex_to_assets`, `intangibles_to_assets`, `book_to_market`, `tobin_q` |
| **Profitability & Margins** | `gross_margin`, `operating_margin`, `ebitda_margin`, `net_margin`, `interest_coverage` |
| **Market & Returns** | `mkt_cap`, `momentum_12m`, `volatility_12m`, `price_to_earnings` |
| **Balance Sheet** | `current_ratio`, `quick_ratio`, `debt_to_assets`, `cash_holdings`, `ppe_intensity`, `goodwill_intensity`, `wc_to_assets`, `inventory_to_assets`, `receivables_to_assets` |
| **Investment & Financing** | `debt_issuance`, `equity_issuance`, `acquisition`, `stock_repurchases`, `investment`, `ocf_to_assets`, `fcf_to_assets` |
| **Analyst Forecasts** | `fy1_eps_est`, `fy1_sales_est`, `fy1_numest`, `fy2_eps_est`, `fy2_sales_est` (IBES consensus for t+1 and t+2) |
| **Future Realizations** | `future_roa`, `future_sales_growth`, `future_earnings_growth` (realized values from t+1) |
| **Industry** | `sic`, `naics`, `gsubind`, `sector` |
| **Quality Flags** | `rd_dummy`, `loss_indicator`, `dividend_payer` |

---

## Pipeline Status

| Step | Status | Location |
|------|--------|----------|
| 1. MD&A Extraction | ✅ Complete | `Data_Cleaning_NEW/scripts/extract_mda_sentences.py` |
| 2. AI Classification | 🔄 In Progress | `NLP/` — groupmates' pipeline + LLM classification |
| 3. Control Variables | ✅ Complete | `20260426/scripts/` |
| 4. Master Panel | ✅ Complete | `20260426/firm_year_panel_final.csv` |
| 5. Regressions | ⏳ Pending | To be done by regression team |

---

## How to Use the Control Variable Scripts

All scripts connect to WRDS (Wharton Research Data Services) via PostgreSQL. Ensure your WRDS credentials are set:

```bash
export WRDS_PASS="your_wrds_password"
```

### Pull core controls (Compustat + CRSP + IBES)

```bash
cd 20260426
python scripts/merge_controls.py
```

### Pull IBES analyst forecasts

```bash
python scripts/fetch_ibes_forecasts.py
```

### Pull supplemental ratios (margins, momentum, volatility, etc.)

```bash
python scripts/fetch_additional_controls.py
```

---

## Key Design Decisions

- **Fiscal Year Alignment**: All WRDS variables are matched to the firm's fiscal year end (`datadate`). IBES forecasts use `FISCALP="ANN"` for annual consensus.
- **Future Variables**: "Future" operating performance refers to **analyst forecasts** (FY1 = t+1, FY2 = t+2 from IBES) and **realized values** (t+1 Compustat data where available). We do not use Yahoo Finance predictions because they lack coverage for our sample period and firms.
- **CRSP Momentum**: 12-month cumulative return (months t-12 to t-1), computed from CRSP monthly returns file (`msf`).
- **Industry Fixed Effects**: `sic` (4-digit), `naics` (6-digit), `gsubind` (GICS sub-industry), and `sector` (11 GICS sectors) are all available for industry FE specifications.

---

## Contributors

- **Rico Zhu** — Control variables, WRDS data integration, repo maintenance
- **Group A** — LLM-based AI classification pipeline
- **Group B** — Sentiment analysis & NLP metrics (`希望是真的nlp/`)
- **Regression Team** — Regression design & estimation (pending)

---

## Citation

If using this dataset or code, please cite the authors and acknowledge WRDS data access.
