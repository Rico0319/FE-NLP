# 20260427 Update

数据清洗已全部完成！以下是最终交付内容总结：

---

## 交付文件

| 文件 | 说明 |
|------|------|
| `20260426/firm_year_panel_regression_ready.csv` | **最终清洗后的面板数据**（3,315行 × 107列） |
| `20260426/README_PANEL.md` | 数据说明文档 |
| `20260426/sample_regressions.do` | Stata 回归示例代码 |
| `20260426/sample_regressions.py` | Python 回归示例代码 |

---

## 处理内容

### 1. 空行问题 ✅
- 原数据有23个FY2025行缺少control变量（BF-B、CAG、GIS、NKE等非12月财年公司）
- **原因**：这些公司的FY2025财年结束于2025年4-5月，Compustat数据尚未更新
- **处理**：已删除这23行，保留3,315个完整观测

### 2. ROE极端值 ✅
- 原始ROE范围：[-65.36, 388.70]，68个极端值
- **原因**：ceq（common equity）极小或负数（如股票回购导致），会计上合理
- **处理**：新增 `ROE_winsorized` 列（1%/99% winsorize），范围：[-3.10, 3.65]
- 原始ROE保留供参考

### 3. 去重 ✅
- **Dual-class shares**：FOX/FOXA、GOOG/GOOGL、NWS/NWSA → 保留有CIK的版本（FOXA、GOOGL、NWSA）
- **Multi-accession cases**：
  - CRM FY2022：保留 `0001108524-22-000013`（2022-03-11 filing）
  - SMCI FY2019：保留 `0001375365-19-000079`（2019-12-19 filing）
  - SMCI FY2025：保留 `0001375365-25-000027`（2025-08-28 filing）

### 4. 删除重复列 ✅
保留了优先版本，删除了：fyear、tic、conm、gvkey_ctrl、cik_ctrl、debt_to_assets、ppe_intensity、cash_holdings、future_operating_performance、log_emp2

### 5. 主键设置 ✅
- `gvkey` + `fiscal_year` 唯一
- 0 duplicates

---

## 数据概况

- **公司数**：486家
- **年份**：2019–2025
- **AI提及率**：89.1% 的公司至少提到AI
- **实质性AI披露率**：85.4%
- **面板平衡**：439家公司有完整7年数据

---

## 给组员的说明

这份数据现在可以直接用于regression：
- 主键：`gvkey` + `fiscal_year`
- 回归时用 `ROE_winsorized` 避免极端值影响
- 行业固定效应可用 `sector`、`sic`、`naics` 或 `gsubind`
- 年份固定效应用 `fiscal_year`

我还附了Stata和Python的sample regression code，可以直接参考。


# 20260426 Session — Firm-Year Panel Data Dictionary

This folder contains the final firm-year panel used for regression analysis, plus the scripts that built it.

## Master Dataset

**File:** `firm_year_panel_final.csv`  
**Dimensions:** 3,362 rows (firm-years) × 116 columns  
**Coverage:** 486 unique S&P 500 firms, fiscal years 2019–2025  
**Source:** NLP pipeline output merged with WRDS Compustat, CRSP, and IBES

---

## Column Descriptions (by Category)

### 1. Firm Identification

| Column | Description |
|--------|-------------|
| `cik` | SEC Central Index Key (10-digit identifier) |
| `ticker` | Exchange ticker symbol |
| `company_name` | Company legal name from SEC filings |
| `gvkey_ctrl` | Compustat GVKEY (6-digit firm identifier) — the control-variable merge key |
| `cik_ctrl` | CIK as stored in Compustat (may include leading zeros) |
| `tic` | Ticker as stored in Compustat |
| `conm` | Company name as stored in Compustat |
| `fiscal_year` / `fyear` | Fiscal year of the 10-K filing (e.g., 2023) |
| `datadate` | Fiscal year-end date (Compustat `datadate`) |
| `accession_number` | SEC EDGAR accession number for the 10-K filing |

### 2. AI Disclosure Variables (from NLP Pipeline)

These variables come from your groupmates' NLP analysis of the MD&A section.

| Column | Description |
|--------|-------------|
| `mdna_total_sentence_count` | Total number of sentences in the MD&A section |
| `mdna_total_word_count` | Total word count of the MD&A section |
| `n_kept_sentences` | Sentences retained after deduplication and quality filters |
| `n_ai_candidate_sentences` | Sentences flagged as mentioning AI-related keywords |
| `n_generic_ai_disclosure_sentences` | AI sentences classified as **generic** (boilerplate/vague) |
| `n_substantive_ai_implementation_sentences` | AI sentences classified as **substantive implementation** |
| `n_substantive_ai_risk_governance_sentences` | AI sentences classified as **substantive risk/governance** |
| `n_substantive_ai_disclosure_sentences` | Total substantive AI sentences (implementation + risk/governance) |
| `ai_candidate_sentence_intensity` | `n_ai_candidate_sentences / n_kept_sentences` |
| `generic_ai_disclosure_sentence_intensity` | `n_generic_ai_disclosure_sentences / n_kept_sentences` |
| `substantive_ai_disclosure_sentence_intensity` | `n_substantive_ai_disclosure_sentences / n_kept_sentences` |
| `substantive_ai_implementation_sentence_intensity` | `n_substantive_ai_implementation_sentences / n_kept_sentences` |
| `substantive_ai_risk_governance_sentence_intensity` | `n_substantive_ai_risk_governance_sentences / n_kept_sentences` |
| `ai_candidate_per_10000_words` | `n_ai_candidate_sentences / mdna_total_word_count × 10,000` |
| `generic_ai_disclosure_per_10000_words` | `n_generic_ai_disclosure_sentences / mdna_total_word_count × 10,000` |
| `substantive_ai_disclosure_per_10000_words` | `n_substantive_ai_disclosure_sentences / mdna_total_word_count × 10,000` |
| `substantive_ai_implementation_per_10000_words` | `n_substantive_ai_implementation_sentences / mdna_total_word_count × 10,000` |
| `substantive_ai_risk_governance_per_10000_words` | `n_substantive_ai_risk_governance_sentences / mdna_total_word_count × 10,000` |

**Key distinction:** The `intensity` measures use sentence counts (relative to kept sentences), while the `per_10000_words` measures normalize by total MD&A length to control for filing verbosity.

### 3. Industry Codes (for Fixed Effects)

| Column | Description |
|--------|-------------|
| `sic` | Standard Industrial Classification (4-digit) |
| `naics` | North American Industry Classification System (6-digit) |
| `gsubind` | GICS Sub-Industry code |
| `gsector` | GICS Sector code |
| `ggroup` | GICS Industry Group code |
| `gind` | GICS Industry code |
| `spcindcd` | S&P Industry Code |
| `sector` | Human-readable GICS sector name (11 sectors) |

### 4. Core Firm Fundamentals (Compustat)

| Column | Description | Formula / Notes |
|--------|-------------|-----------------|
| `log_assets` | Natural log of total assets (`at`) | In millions USD |
| `ROA` | Return on Assets | `ni / at` |
| `leverage` | Book leverage | `lt / at` |
| `debt_at` | Same as leverage | `lt / at` |
| `sales_growth` | Year-over-year sales growth | `(sale_t - sale_t-1) / sale_t-1` |
| `rd_to_assets` | R&D intensity | `xrd / at` |
| `capex_to_assets` | Capital expenditure intensity | `capx / at` |
| `intangibles_to_assets` | Intangible asset intensity | `intan / at` |
| `tobin_q` | Tobin's Q (market-to-book proxy) | `(at + mkt_cap - ceq) / at` |
| `prcc_f` | Fiscal year-end closing stock price | From Compustat |
| `csho` | Common shares outstanding | In millions |
| `cash_ratio` | Cash & short-term investments / total assets | `che / at` |
| `ppe_ratio` | Property, plant & equipment / total assets | `ppent / at` |
| `log_emp` / `log_emp2` | Natural log of employees (`emp`) | Two versions from different pulls; use one |
| `at` | Total assets | Raw Compustat variable (millions USD) |
| `ni` | Net income | Raw Compustat variable |
| `lt` | Total liabilities | Raw Compustat variable |
| `sale` | Net sales/revenue | Raw Compustat variable |
| `xrd` | R&D expense | Raw Compustat variable |
| `capx` | Capital expenditures | Raw Compustat variable |
| `intan` | Intangible assets | Raw Compustat variable |
| `ceq` | Common/ordinary equity | Raw Compustat variable |
| `prcc_c` | Calendar year-end closing price | From Compustat |

### 5. Future / Realized Outcomes (t+1 Compustat)

These are **actual realized values** from fiscal year t+1, merged forward by gvkey. They are **not** predictions — they are what actually happened.

| Column | Description |
|--------|-------------|
| `future_ROA` | ROA in year t+1 |
| `future_sales_growth` | Sales growth in year t+1 |
| `future_earnings_growth` | Earnings growth in year t+1 |
| `future_capex_to_assets` | Capex intensity in year t+1 |
| `future_rd_to_assets` | R&D intensity in year t+1 |
| `future_operating_performance` | Operating performance metric in year t+1 |

**Note:** Coverage for future variables is lower because t+1 data does not yet exist for 2025 fiscal years.

### 6. Analyst Forecasts (IBES via WRDS)

These are **predicted future values** from sell-side analyst consensus (IBES). `FY1` = forecast for fiscal year t+1, `FY2` = forecast for fiscal year t+2.

| Column | Description |
|--------|-------------|
| `fy1_meanest` | Mean analyst EPS estimate for FY1 |
| `fy1_medest` | Median analyst EPS estimate for FY1 |
| `fy1_numest` | Number of analysts covering the firm for FY1 |
| `fy1_stdev` | Standard deviation of FY1 EPS estimates |
| `fy1_actual` | Actual realized EPS for FY1 (backfilled by IBES) |
| `fy1_statpers` | IBES statistical period date for FY1 |
| `fy2_meanest` | Mean analyst EPS estimate for FY2 |
| `fy2_medest` | Median analyst EPS estimate for FY2 |
| `fy2_numest` | Number of analysts covering the firm for FY2 |
| `fy2_stdev` | Standard deviation of FY2 EPS estimates |
| `fy2_actual` | Actual realized EPS for FY2 (backfilled by IBES) |
| `fy2_statpers` | IBES statistical period date for FY2 |

### 7. Market & Return Variables (CRSP)

| Column | Description | Notes |
|--------|-------------|-------|
| `momentum_12m` | 12-month cumulative stock return | Months t-12 to t-1 before fiscal year end. Log-return compounded, then converted back. |
| `volatility_12m` | 12-month return volatility | Standard deviation of monthly returns over t-12 to t-1. |

### 8. Profitability & Margin Ratios

| Column | Description | Formula |
|--------|-------------|---------|
| `gross_margin` | Gross profit margin | `gp / sale` |
| `operating_margin` | Operating profit margin | `oiadp / sale` |
| `ebitda_margin` | EBITDA margin | `ebitda / sale` |
| `net_margin` | Net profit margin | `ni / sale` |
| `interest_coverage` | Interest coverage ratio | `oiadp / xint` |
| `ROE` | Return on equity | `ni / seq` |
| `asset_turnover` | Sales / total assets | `sale / at` |

### 9. Market Value & Valuation Ratios

| Column | Description | Formula |
|--------|-------------|---------|
| `mkt_cap` | Market capitalization | `prcc_c × cshfd` (price × shares outstanding) |
| `book_to_market` | Book-to-market ratio | `seq / mkt_cap` |
| `price_to_earnings` | P/E ratio | `prcc_c / (ib / cshfd)` |

### 10. Liquidity & Working Capital

| Column | Description | Formula |
|--------|-------------|---------|
| `current_ratio` | Current ratio | `act / lct` |
| `quick_ratio` | Quick ratio | `(act - invt) / lct` |
| `cash_holdings` | Cash & equivalents / total assets | `che / at` |
| `wc_to_assets` | Working capital / total assets | `wcap / at` |
| `inventory_to_assets` | Inventory / total assets | `invt / at` |
| `receivables_to_assets` | Accounts receivable / total assets | `rect / at` |

### 11. Capital Structure & Debt

| Column | Description | Formula |
|--------|-------------|---------|
| `debt_to_assets` | Total debt / total assets | `lt / at` |
| `debt_issuance` | Debt issuance / total assets | `dltis / at` |
| `equity_issuance` | Equity issuance / total assets | `sstk / at` |
| `stock_repurchases` | Stock repurchases / total assets | `prstkc / at` |

### 12. Investment & Financing Activity

| Column | Description | Formula |
|--------|-------------|---------|
| `investment` | Net investment / total assets | `(Δppent + dp) / at` |
| `acquisition` | Acquisition dummy | `=1` if `aqc > 0` |
| `depreciation_to_assets` | Depreciation / total assets | `dp / at` |

### 13. Cost & Intensity Ratios

| Column | Description | Formula |
|--------|-------------|---------|
| `advertising_intensity` | Advertising expense / sales | `xad / sale` |
| `sga_intensity` | SG&A expense / sales | `xsga / sale` |
| `ppe_intensity` | Net PP&E / total assets | `ppent / at` |
| `goodwill_intensity` | Goodwill / total assets | `gdwl / at` |

### 14. Cash Flow Measures

| Column | Description | Formula |
|--------|-------------|---------|
| `ocf_to_assets` | Operating cash flow / total assets | `oancf / at` |
| `fcf_to_assets` | Free cash flow / total assets | `(oancf - capx) / at` |

### 15. Firm Quality Flags

| Column | Description |
|--------|-------------|
| `rd_dummy` | `=1` if firm reports positive R&D expense (`xrd > 0`) |
| `loss_indicator` | `=1` if firm reports negative net income (`ni < 0`) |
| `dividend_payer` | `=1` if firm pays dividends (`dvc > 0`) |
| `dividend_yield` | Dividends / market cap | `dvc / mkt_cap` |
| `tax_rate` | Effective tax rate | `txt / pi` (capped at 0 when pre-tax income < 0) |

---

## Coverage Summary

| Variable Group | Coverage | Source |
|----------------|----------|--------|
| Firm fundamentals (`log_assets`, `ROA`, `leverage`, etc.) | 99%+ | Compustat |
| Industry codes (`sic`, `naics`, `gsubind`, `sector`) | 100% | Compustat |
| AI disclosure variables | 100% | NLP pipeline |
| Future realized outcomes | ~60–80% | Compustat (t+1) |
| Analyst forecasts (`fy1_*`, `fy2_*`) | 75–85% | IBES |
| CRSP momentum / volatility | 80% | CRSP |
| Supplemental ratios (margins, liquidity, etc.) | 80–99% | Compustat |

---

## Scripts in This Folder

| Script | Purpose |
|--------|---------|
| `scripts/merge_controls.py` | Merges core Compustat controls into the NLP panel |
| `scripts/fetch_ibes_forecasts.py` | Pulls IBES analyst EPS forecasts from WRDS |
| `scripts/fetch_additional_controls.py` | Pulls supplemental ratios (margins, momentum, liquidity, etc.) |

All scripts connect to WRDS via PostgreSQL. Set your password before running:

```bash
export WRDS_PASS="your_wrds_password"
python scripts/fetch_additional_controls.py
```

---

## Quick Start for Regression Team

```python
import pandas as pd

df = pd.read_csv('firm_year_panel_final.csv')

# Example: run a regression with controls
import statsmodels.formula.api as smf

model = smf.ols(
    'ROA ~ substantive_ai_disclosure_sentence_intensity + log_assets + leverage + rd_to_assets + sales_growth + C(sector)',
    data=df
).fit(cov_type='HC3')
print(model.summary())
```

**Suggested fixed effects:**
- `C(sector)` — GICS sector fixed effects (11 sectors)
- `C(fiscal_year)` — Year fixed effects
- `C(gvkey_ctrl)` — Firm fixed effects (absorbs time-invariant firm heterogeneity)

**Clustering:** Standard errors should be clustered at the firm level (`cluster(df['gvkey_ctrl'])`).
