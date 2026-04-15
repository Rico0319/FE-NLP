# FE-NLP: AI Disclosure in S&P 500 10-K Filings

## Project Overview

This project analyzes AI-related disclosures in S&P 500 companies' 10-K MD&A (Management's Discussion & Analysis) sections from 2018-2025. The central research question distinguishes between **substantive AI disclosure** (concrete, business-specific AI implementation) and **generic AI talk** (vague, boilerplate mentions, or "AI washing").

### Research Questions

- **RQ1**: Can a transparent NLP-based framework identify AI-related disclosure in firms' 10-K filings and distinguish substantive AI disclosure from generic AI statements?
- **RQ2**: Is substantive AI disclosure more closely associated with firm characteristics consistent with technological transformation and operational implementation than generic AI talk?
- **RQ3**: After controlling for conventional financial variables, does substantive AI disclosure provide incremental explanatory power for firm value and future fundamentals?

### Pipeline Architecture

```
SEC EDGAR (10-K HTML/TXT) 
    ↓
[Step 1] MD&A Extraction & Text Cleaning (extract_mda_sentences.py)
    ↓
Sentence-Level MD&A Master File (mdna_sentence_master.jsonl)
    ↓
[Step 2] AI Classification (classify_ai_sentences.py) -- TODO
    ↓
[Step 3] WRDS Data Merge (pull_wrds_data.py + master_panel.py) -- TODO
    ↓
[Step 4] Panel Regressions -- TODO
```

---

## Directory Structure

```
NLP_NEW/
├── README.md                          ← You are here
├── .env.example                       ← Qwen API key template (copy to .env)
├── requirements.txt                   ← Python dependencies
├── scripts/
│   └── extract_mda_sentences.py       ← Step 1: MD&A extraction (NEW, fully rewritten)
├── data/
│   ├── intermediate/
│   │   └── mdna_sentence_master.jsonl  ← ⭐ OUTPUT: 1.1GB, sentence-level master file
│   └── wrds/
│       ├── cik_gvkey_crosswalk.csv     ← SEC CIK ↔ Compustat GVKEY mapping
│       ├── compustat_annual_2018_2025.csv ← Compustat fundamentals (96K firm-years)
│       └── gics_mapping.csv            ← GICS sector mapping
└── deprecated/                        ← See NLP_test/ for legacy code
```

### Note on Data Location

The main output file `data/intermediate/mdna_sentence_master.jsonl` (1.1 GB) is tracked in this repository via **Git LFS**. Git LFS stores the actual file content on a remote server while keeping lightweight pointers in the git history.

**Requirements:**
- You need `git-lfs` installed to clone and work with this repo
- Install: `sudo dnf install git-lfs` or `brew install git-lfs`
- After installing, run: `git lfs install`
- The 1.1GB file will be downloaded automatically on `git clone` or `git pull`

The raw 10-K filings (~87 GB) remain at `../NLP_test/sec_filings_full/sec-edgar-filings/` and are **not** tracked in git.

WRDS data (Compustat, crosswalk) is also stored in `../NLP_test/data/wrds/` and shared via symlinks.

---

## Step 1: MD&A Extraction & Text Cleaning

**Script:** `scripts/extract_mda_sentences.py`

This is a **complete rewrite** of the original extraction pipeline. The old version (in `NLP_test/scripts/extract_mda_ai.py`) had critical issues:

| Issue | Old Version | New Version |
|-------|-------------|-------------|
| MD&A boundary detection | Regex fails on TOC, extracts entire filing (2-50MB) | Density-based TOC exclusion, accurate Item 7 start / Item 7A stop |
| Document parsing | Processes raw SGML files with all exhibits embedded | Extracts only the main 10-K `<TEXT>` block, skips exhibits |
| Text cleaning | Basic HTML stripping | Full XBRL/HTML parsing, removes navigation strings, table fragments, headers/footers |
| Sentence splitting | Regex split on periods (breaks on abbreviations) | NLTK PunktSentenceTokenizer with 10-K specific post-processing |
| Deduplication | None | Exact (hash-based) + near-duplicate (Rapidfuzz >90% similarity) |
| Quality filters | None | Removes titles, fragments (<10 words), table rows, non-semantic content |

### How It Works

**1. SGML Parsing**: Full-submission `.txt` files contain 100+ embedded documents. The script identifies and extracts only the `<TYPE>10-K` `<TEXT>` block, ignoring exhibits (EX-10.1, EX-21, etc.).

**2. HTML/XBRL Parsing**: Uses BeautifulSoup with custom handling for XBRL inline tags, namespace-prefixed elements, and financial markup.

**3. MD&A Boundary Detection**: 
   - Builds an index of all SEC Item headers (Item 1, 1A, 1B, ..., 7, 7A, 8, etc.)
   - Uses density-based analysis: TOC headers are packed within ~5KB windows, actual section headers are isolated
   - Finds the actual "Item 7. Management's Discussion and Analysis" (not the TOC entry)
   - Extracts everything between Item 7 and Item 7A (or Item 8 if no 7A exists)

**4. Text Cleaning**:
   - Strips all HTML/XBRL tags while preserving content
   - Removes navigation strings ("Back to Table of Contents", "Click here for...")
   - Removes page numbers, table fragments, header/footer artifacts
   - Normalizes whitespace and Unicode artifacts
   - Preserves negation words, modals, numbers (no over-cleaning)

**5. Sentence Tokenization**:
   - Uses NLTK's PunktSentenceTokenizer (handles abbreviations like "Inc.", "Mr.", "e.g.", "U.S.")
   - Custom post-processing for 10-K specific patterns
   - Joins broken lines before splitting
   - Filters out fragments, titles, table rows

**6. Deduplication**:
   - Exact duplicate removal via MD5 hash of normalized sentence text
   - Near-duplicate removal using Rapidfuzz token ratio (>90% similarity threshold)
   - Windowed comparison (checks against last 50 kept sentences for efficiency)

**7. AI Candidate Matching**:
   - High-recall seed lexicon with 28 terms (AI, ML, LLM, ChatGPT, generative AI, etc.)
   - Records all matched keywords per sentence
   - Designed for maximum recall; precision handled by downstream classification

### Output Format

The output file `data/intermediate/mdna_sentence_master.jsonl` contains one JSON line per filing:

```json
{
  "ticker": "AAPL",
  "accession": "0000320193-24-000119",
  "fiscal_year": "2024",
  "company_name": "Apple Inc.",
  "mdna_total_word_count": 2380,
  "mdna_total_sentence_count": 72,
  "mdna_total_char_count": 14312,
  "total_ai_sentences": 3,
  "total_ai_keywords_matched": ["machine learning", "artificial intelligence"],
  "n_dropped_exact_duplicates": 12,
  "n_dropped_near_duplicates": 8,
  "n_sentences_kept": 72,
  "n_sentences_raw": 92,
  "sentences": [
    {
      "sentence_id": "AAPL_0000320193-24-000119_0000",
      "sentence_order": 0,
      "sentence_raw": "Management's Discussion and Analysis of Financial Condition...",
      "sentence_clean": "Management's Discussion and Analysis of Financial Condition...",
      "sentence_word_count": 36,
      "ai_candidate_flag": false,
      "ai_keyword_matched_terms": []
    }
  ]
}
```

### Results

| Metric | Value |
|--------|-------|
| Filings processed | 3,403 (489 unique tickers) |
| Total sentences (kept) | 1,859,276 |
| AI candidate sentences | 3,529 |
| Exact duplicates removed | 16,918 |
| Near-duplicates removed | 20,257 |
| Median MD&A size | 72 KB |
| Mean MD&A size | 135 KB |
| Output file size | 1.1 GB |

### Usage

```bash
# Activate environment
conda activate NLP-env

# Install dependencies (if not already installed)
pip install -r requirements.txt

# Run on full dataset
python scripts/extract_mda_sentences.py

# Run on sample (for testing)
python scripts/extract_mda_sentences.py --sample 5

# Run on specific tickers
python scripts/extract_mda_sentences.py --tickers AAPL,MSFT,GOOGL

# Resume from checkpoint (if interrupted)
python scripts/extract_mda_sentences.py --resume
```

### Dependencies

- `beautifulsoup4` with `lxml` parser
- `nltk` (PunktSentenceTokenizer)
- `rapidfuzz` (near-duplicate detection)
- `pandas` (company list loading)
- Standard library: `re`, `json`, `hashlib`, `argparse`

---

## Next Steps (TODO)

### Step 2: AI Classification (4-Class Scheme)

The current classification (in `NLP_test/scripts/classify_ai_sentences.py`) uses a binary substantive/generic scheme. Per the professor's specification, this needs to be updated to a 4-class system:

| Class | Label | Description |
|-------|-------|-------------|
| 0 | `not_meaningful_ai_mention` | Mentions AI term but no disclosure (titles,法规 names, broad lists) |
| 1 | `generic_ai_disclosure` | Strategic direction, trends, opportunities — no specific use case |
| 2 | `substantive_ai_implementation` | Specific deployment/integration of AI in products, services, operations |
| 3 | `substantive_ai_risk_governance` | AI risk mechanisms, model review, testing, governance framework |

Key changes needed:
- Add "not_meaningful" category to avoid dirtying the denominator
- Split "substantive" into implementation vs. risk/governance
- Regulatory mention of specific functions ≠ substantive
- Sentence deduplication (already done in Step 1)

### Step 3: Master Panel Construction

Merge AI disclosure data with Compustat financials and calculate:
- **Intensity variables**: generic_ai_intensity, substantive_impl_intensity, substantive_risk_intensity
- **Share variables**: generic_ai_share, substantive_ai_share
- **Net measures**: net_substantive_minus_generic
- **Dummies**: any_generic, any_substantive, any_impl, any_risk, plus mechanism dummies
- **Financial controls**: log_assets, ROA, leverage, R&D intensity, capex intensity, intangibles, cash ratio, Tobin's Q

### Step 4: Regressions

Per the professor's specification:
- **Model Group A**: Valuation relevance (Tobin's Q ~ AI intensity + controls)
- **Model Group B**: Post-ChatGPT heterogeneity (interaction models)
- **Model Group C**: Future outcomes (future ROA, future sales growth)
- **Model D**: Return predictability (stock return reversals)

---

## Data Sources

- **SEC EDGAR**: 10-K filings for S&P 500 companies (2018-2025), ~87GB raw data
- **Compustat Annual Fundamentals**: via WRDS (indfmt=INDL, datafmt=STD, popsrc=D, consol=C)
- **CIK-GVKEY Crosswalk**: Compustat names table
- **GICS Sector Mapping**: Compustat company table

---


## Version History

| Date | Version | Notes |
|------|---------|-------|
| 2025-04-15 | v2.0 | Complete rewrite of MD&A extraction pipeline |
| 2025-04-09 | v1.0 | Initial NLP_test pipeline (deprecated) |

---

## Known Issues

1. **Large filings**: ~400 filings (11.5%) have MD&A sections >300KB. These are primarily utility companies (AEP, EXC, ETR, SO) and financial firms (JPM, AIG) with extensive regulatory disclosures. These are legitimate, not extraction errors.
2. **Very small filings**: ~4 filings have MD&A <5KB. These may be shell companies or filings with minimal MD&A sections. Worth reviewing individually.
