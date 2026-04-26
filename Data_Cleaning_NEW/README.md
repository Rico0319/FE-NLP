# FE-NLP: AI Disclosure in S&P 500 10-K Filings

## Overview

Analyzes AI-related disclosures in S&P 500 10-K MD&A sections (2018–2025). Distinguishes **substantive AI disclosure** from **generic AI talk** ("AI washing").

### Research Questions

- **RQ1**: Can NLP distinguish substantive vs generic AI disclosure in 10-Ks?
- **RQ2**: Is substantive AI disclosure associated with firm characteristics of technological transformation?
- **RQ3**: Does substantive AI disclosure provide incremental explanatory power for firm value?

---

## Step 1: MD&A Extraction (Done)

**Script:** `scripts/extract_mda_sentences.py`

Complete rewrite of the original pipeline. Key improvements:

| Issue | Old (NLP_test) | New (Data_Cleaning_NEW) |
|-------|---------------|------------------------|
| MD&A size | 2.2 MB median (extracted entire filing) | 72 KB median (accurate Item 7 → 7A) |
| Boundaries | Regex fails on TOC entries | Density-based TOC detection |
| Sentence splitting | Regex on periods (breaks on abbreviations) | NLTK PunktSentenceTokenizer |
| Deduplication | None | Exact + near-duplicate (125K removed) |
| Quality filters | None | Removes titles, fragments, table rows |

### Usage

```bash
conda activate NLP-env
pip install -r requirements.txt

python scripts/extract_mda_sentences.py              # full dataset
python scripts/extract_mda_sentences.py --sample 5    # test 5 tickers
python scripts/extract_mda_sentences.py --resume      # resume if interrupted
```

### Results

| Metric | Value |
|--------|-------|
| Filings processed | 3,362 (489 unique tickers) |
| Sentences extracted | 1,962,336 |
| Sentences kept (after dedup) | 1,836,642 |
| AI candidate sentences | 3,497 |
| Duplicates removed | 125,694 |

### Output Format

Flat JSONL — **one line per sentence** with all 21 professor-required fields:

```
firm-year:     cik, gvkey, ticker, company_name, filing_date, fiscal_year, accession_number
metadata:      section_name, mdna_total_word_count, mdna_total_sentence_count, mdna_total_char_count
sentence:      sentence_id, sentence_order, sentence_raw, sentence_clean, sentence_word_count
quality:       is_exact_duplicate, is_near_duplicate, keep_sentence_flag
AI candidate:  ai_candidate_flag, ai_keyword_matched_terms
```

### Data Location

- **Output**: `data/intermediate/mdna_sentence_master.jsonl` (1.9 GB, tracked via Git LFS)
- **Raw filings**: `../NLP_test_deprecated/sec_filings_full/` (87 GB, not in git)
- **WRDS data**: `../NLP_test_deprecated/data/wrds/` (shared via symlinks)

Requires `git-lfs` installed to clone: `git lfs install`

### Dependencies

`beautifulsoup4` (lxml), `nltk`, `rapidfuzz`, `pandas`

---

## Step 2: AI Classification

**Status**: In progress — see `../NLP/` for active classification pipeline.

Groupmates' sentiment analysis pipeline is in `../20260426/希望是真的nlp/`.

---

## Step 3: Control Variables ✅ DONE

All control variables have been pulled from WRDS and merged into the master panel.

**Master dataset**: `../20260426/firm_year_panel_final.csv`

| Variable Source | Coverage | Description |
|----------------|----------|-------------|
| Compustat Fundamentals | 99%+ | `log_assets`, `ROA`, `ROE`, `leverage`, `sales_growth`, `rd_to_assets`, `capex_to_assets`, `intangibles_to_assets`, `book_to_market` |
| CRSP | 91% | `tobin_q` (market value / replacement cost) |
| IBES | 75–85% | Analyst forecasts `fy1_eps_est`, `fy1_sales_est`, `fy2_eps_est`, `fy2_sales_est` |
| Supplemental Ratios | 80–99% | Margins, momentum, volatility, liquidity, investment activity |
| Industry Codes | 100% | `sic`, `naics`, `gsubind`, `sector` |

**Scripts**: `../20260426/scripts/`

---

## Step 4: Regressions

**Status**: Pending — regression team will use `../20260426/firm_year_panel_final.csv`.

---

## Deprecated

`../NLP_test_deprecated/` is the legacy pipeline. See `../NLP_test_deprecated/DEPRECATED.md` for migration guide.
