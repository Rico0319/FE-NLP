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

## Missing Data

Three variables are currently **100% missing** because they require a
supplemental WRDS pull:

1. `capex_to_assets` → needs `capx`
2. `intangibles_to_assets` → needs `intan`
3. `tobin_q` → needs `prcc_f`

See `../raw/README_WRDS_query.md` for the exact SQL query to download
these from WRDS.

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
