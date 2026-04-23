# Control Variables Panel

File: `control_variables.csv`

## Variables Included

| Variable | Description | Source |
|----------|-------------|--------|
| `gvkey` | Compustat global company key | Compustat |
| `cik` | SEC Central Index Key | Compustat |
| `tic` | Ticker | Compustat |
| `conm` | Company name | Compustat |
| `fyear` | Fiscal year | Compustat |
| `datadate` | Fiscal year-end date | Compustat |
| `sic` / `naics` / `gsubind` | Industry codes (for FE) | Compustat |
| `log_assets` | ln(Total Assets) | at |
| `ROA` | Net Income / Total Assets | ni / at |
| `leverage` | Total Liabilities / Total Assets | lt / at |
| `debt_at` | (Long-term Debt + Debt in Current Liab) / Total Assets | (dltt+dlc) / at |
| `sales_growth` | (Sale_t - Sale_{t-1}) / Sale_{t-1} | sale |
| `rd_to_assets` | R&D Expense / Total Assets | xrd / at |
| `capex_to_assets` | Capital Expenditures / Total Assets | capx / at |
| `intangibles_to_assets` | Intangible Assets / Total Assets | intan / at |
| `tobin_q` | (Mkt Equity + Book Liabilities) / Book Assets | (prcc_f*csho + lt) / at |
| `cash_ratio` | Cash / Total Assets | che / at |
| `ppe_ratio` | PP&E / Total Assets | ppent / at |
| `log_emp` | ln(Employees) | emp |

## Data Coverage

- **Firm-years**: ~60,689
- **Unique firms**: ~10,497
- **Years**: 2018–2025

## Missing Data (Post-WRDS Supplemental Pull)

All three supplemental variables have now been downloaded from WRDS and merged:

| Variable | Coverage | Notes |
|----------|----------|-------|
| `capex_to_assets` | 98.9% | `capx` from `comp.funda` |
| `intangibles_to_assets` | 99.0% | `intan` from `comp.funda` |
| `tobin_q` | **91.0%** | `prcc_f` from `comp.funda` + **CRSP supplemental** (67 prices filled) |

The remaining ~9% missing `tobin_q` is due to some firms lacking a fiscal year-end stock price in both Compustat and CRSP (often non-US or delisted firms). CRSP prices were merged only when within 90 days of fiscal year-end. For regression, use `dropna()` on the variables you need.

**Regression-ready sample sizes** (all core vars non-null):
- All 8 core controls: ~20,087 firm-years (~4,274 unique firms)
- Minimum set (log_assets, ROA, leverage, tobin_q): ~55,019 firm-years (~9,964 unique firms)

**Critical fix:** WRDS `comp.funda.gvkey` is a `VARCHAR` — queries must use zero-padded 6-digit strings (e.g., `"001004"`, not `"1004"`). The first pull matched only 3,295 firms because of this.

## Pre-processing Recommendation

Some variables contain extreme outliers (e.g., ROA > 1000) due to very
small denominators (near-zero assets). For regression analysis, **winsorize
at the 1st and 99th percentiles** within each year:

```python
import pandas as pd

df = pd.read_csv("control_variables.csv")
vars_to_winsorize = ["ROA", "leverage", "sales_growth", "rd_to_assets",
                     "capex_to_assets", "intangibles_to_assets", "tobin_q"]
for var in vars_to_winsorize:
    if var in df.columns:
        df[var] = df.groupby("fyear")[var].transform(
            lambda x: x.clip(lower=x.quantile(0.01), upper=x.quantile(0.99))
        )
```

## Merging with NLP Output

Merge on `gvkey` + `fyear` (or `cik` + `fyear`):

```python
nlp_panel = pd.read_csv("firm_year_ai_disclosure_measures.csv")
controls = pd.read_csv("control_variables.csv")
merged = nlp_panel.merge(
    controls,
    left_on=["cik", "year"],
    right_on=["cik", "fyear"],
    how="left"
)
```
