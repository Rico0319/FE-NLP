Slide 1: 10-K MD&A Data Extraction & NLP Pipeline Preparation
Data Source: SEC EDGAR API

Downloaded S&P 500 10-K filings for fiscal years 2019-2025
Parsed HTML to extract Item 7 (MD&A) sections
Handled filing format variations (plain text vs HTML vs XBRL)

Python Implementation Details
Used requests library to call SEC EDGAR API
Located specific filings via accession number
Used BeautifulSoup to parse HTML structure
Split extracted text into sentences for NLP team input

Output Format
One sentence per row with metadata: ticker, fiscal_year, accession_number, cik, gvkey
Generated firm_year_ai_disclosure_summary.csv for NLP team
Included fields: mdna_total_sentence_count, mdna_total_word_count, n_kept_sentences

Key Challenges
SEC API rate limits (10 calls per second)
Different fiscal year end months across companies
Non-standard 10-K formats requiring special parsing logic

Slide 2: Control Variable Database Construction (WRDS Data Extraction)
Data Source: WRDS (Wharton Research Data Services)

Compustat: Company fundamentals (assets, liabilities, earnings, cash flows)
CRSP: Stock market data (prices, market cap, trading volume, returns)
IBES: Analyst forecast data (EPS consensus, revenue estimates)

Python Script: fetch_additional_controls.py
Connected to WRDS PostgreSQL database using psycopg2
Used parameterized queries to prevent SQL injection
Extracted 40+ raw fields including:
at (total assets), sale (revenue), ni (net income)
capx (capex), xrd (R&D), lt (total liabilities)
prcc_f (fiscal year-end price), csho (shares outstanding)
emp (employees), seq (shareholders equity)

Derived Variable Calculations
ROA = ni / at (Return on Assets)
leverage = lt / at (Leverage ratio)
sales_growth = (sale_t - sale_t-1) / sale_t-1 (Sales growth rate)
capex_to_assets = capx / at (Capital expenditure intensity)
rd_to_assets = xrd / at (R&D intensity)
tobin_q = (prcc_f * csho + lt) / at (Tobin's Q)
log_assets = log(at) (Log of total assets)
log_emp = log(emp) (Log of employees)

Future Variable Calculations (Forward-looking Controls)
future_ROA = groupby(gvkey).shift(-1): Next year's realized ROA
future_sales_growth: Next year's sales growth
future_earnings_growth = (ni_t+1 - ni_t) / abs(ni_t): Earnings growth
future_capex_to_assets: Next year's capex intensity
future_rd_to_assets: Next year's R&D intensity

Winsorization Treatment
Winsorized all ratio variables at 1% and 99% percentiles
Generated *_winsorized versions to prevent extreme values from affecting regression results

Slide 3: Critical Data Cleaning Challenges & Fixes
Challenge 1: Fiscal Year Alignment

Problem Discovery:

42 companies have fiscal year end in months 1-5 (e.g., BF-B in April, WMT in January, NKE in May)
NLP fiscal_year derived from accession number (filing year)
Compustat fyear uses start year for non-December fiscal year companies

Error Example:
BF-B 2019: NLP has fiscal_year=2019
In Compustat, fyear=2018 corresponds to datadate=2019-04-30 (FY2019 ending April 2019)
Previous incorrect fix added +1, matching to fyear=2020 (FY2021 data, 2 years ahead!)

Fix Method (fix_fiscal_year_correct.py):
For Jan-May FYE companies: compustat_fyear = fiscal_year - 1
For Dec FYE companies (447 firms): No adjustment needed, fyear = fiscal_year
Verification: BF-B 2019 now correctly matches datadate=2019-04-30

Challenge 2: Dual-Class Share Deduplication
Problem Discovery:

GOOG/GOOGL, FOX/FOXA, NWS/NWSA share same accession_number but different tickers
Caused duplicate rows for same fiscal year, leading to double-counting in regression

Fix Method (fix_dual_class_and_gvkey.py):
Defined dual-class pairs: (secondary, primary)
GOOG → GOOGL (keep GOOGL, drop GOOG)
FOX → FOXA (keep FOXA, drop FOX)
NWS → NWSA (keep NWSA, drop NWS)
Retention rule: Keep primary class with complete gvkey and cik
Result: Removed 21 rows (7 years × 3 pairs), reduced from 3359 to 3338 rows

Challenge 3: Missing gvkey/cik Fix
Problem Discovery:

BF-B and BRK-B used hyphens in NLP data
Compustat uses dots (BF.B, BRK.B)
Caused merge failure, resulting in null gvkey and cik

Fix Method:
Built ticker mapping dictionary: {'BF-B': 'BF.B', 'BRK-B': 'BRK.B'}
Looked up corresponding gvkey/cik from controls and backfilled
BF-B: gvkey=2435, cik=14693
BRK-B: gvkey=2176, cik=1067983
Result: 3338 rows 100% complete, zero missing gvkey/cik

Slide 4: CRSP Market Variables & Final Panel Construction
CRSP Data Extraction

Retrieved from WRDS CRSP database:

momentum_12m: 12-month cumulative log-return (t-12 to t-1), using expm1 transformation
volatility_12m: 12-month return standard deviation
Required CRSP-Compustat link table (crsp.ccmxpf_linktable) to map gvkey to permno

Coverage Issue
2681/3338 rows have CRSP data (80.3% coverage)
657 rows missing: These companies lack CRSP permno coverage (typically recent IPOs or delisted firms)
Attempted recovery through alternative WRDS tables but could not restore

Winsorization & Sample Flags
Generated winsorized versions:

momentum_12m_winsorized: Winsorized at 1%/99% percentiles
Preserved original values for regression team choice

Generated sample flag variables (for regression team):
post_ai: Dummy variable, 1 if fiscal_year >= 2023
has_ai_candidate: 1 if n_ai_candidate_sentences > 0
has_generic_ai: 1 if n_generic_ai_disclosure_sentences > 0
has_substantive_ai: 1 if n_substantive_ai_disclosure_sentences > 0
sample_valuation: 1 if tobin_q + AI variables + baseline controls are all non-null
sample_future_performance: 1 if future_ROA + future_sales + AI variables + controls are all non-null

Final Panel Statistics
3338 rows, 73 columns
489 unique companies, 7 years (2019-2025)
Core control variables: 98.9% coverage
Tobin's Q: 90.9% coverage
CRSP momentum/volatility: 80.3% coverage

Deliverables
firm_year_panel_regression_ready.csv: Main regression panel
control_variables_inventory.txt: Documentation for all control variables
All scripts saved in scripts/ directory, fully reproducible