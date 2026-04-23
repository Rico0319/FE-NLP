# FE-NLP: AI Disclosure in S&P 500 10-K Filings

## Overview

Analyzes AI-related disclosures in S&P 500 10-K MD&A sections (2018-2025). Distinguishes **substantive AI disclosure** from **generic AI talk** ("AI washing").

### Research Questions

- **RQ1**: Can NLP distinguish substantive vs generic AI disclosure in 10-Ks?
- **RQ2**: Is substantive AI disclosure associated with firm characteristics of technological transformation?
- **RQ3**: Does substantive AI disclosure provide incremental explanatory power for firm value?

### Pipeline

```
SEC EDGAR → [1] MD&A Extraction → [2] AI Classification → [3] WRDS Merge → [4] Regressions
              (done ✅)              (TODO)                (TODO)          (TODO)
```

---

## Step 1: MD&A Extraction (Done)

**Script:** `scripts/extract_mda_sentences.py`

Complete rewrite of the original pipeline. Key improvements:

| Issue | Old (NLP_test) | New (NLP_NEW) |
|-------|---------------|---------------|
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
- **Raw filings**: `../NLP_test/sec_filings_full/` (87 GB, not in git)
- **WRDS data**: `../NLP_test/data/wrds/` (shared via symlinks)

Requires `git-lfs` installed to clone: `git lfs install`

### Dependencies

`beautifulsoup4` (lxml), `nltk`, `rapidfuzz`, `pandas`

---

## Next Steps

**Step 2: AI Classification** — Update from binary (substantive/generic) to 4-class:
- 0: not_meaningful_ai_mention
- 1: generic_ai_disclosure
- 2: substantive_ai_implementation
- 3: substantive_ai_risk_governance

**Step 3: Control Variables** ✅ **DONE**
- Compustat fundamentals pulled (`log_assets`, `ROA`, `leverage`, `sales_growth`, `rd_to_assets`)
- Supplemental WRDS pull for `capx`, `intan`, `prcc_f` completed and merged
- CRSP supplemental prices merged (67 prices within 90 days of fiscal year-end)
- `capex_to_assets`, `intangibles_to_assets` now 98–99% complete; `tobin_q` now 91.0% complete
- Full regression sample: ~20K firm-years with all core controls

**Step 4: Master Panel & Regressions** — Merge AI scores with controls, run valuation models.

---

## Deprecated

`../NLP_test/` is the legacy pipeline. See `../NLP_test/DEPRECATED.md` for migration guide.
