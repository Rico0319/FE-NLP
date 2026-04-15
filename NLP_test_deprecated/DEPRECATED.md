# DEPRECATED — Use NLP_NEW Instead

This directory contains the original/legacy version of the FE-NLP analysis pipeline.
It has been superseded by the complete rewrite in `../NLP_NEW/`.

## What's Here (Legacy)

- `scripts/extract_mda_ai.py` — Original extraction script. **DO NOT USE.**
  - Extracts entire filing instead of just MD&A (2-50MB vs 20-100KB)
  - No deduplication
  - No quality filtering
  - Crude regex sentence splitting
  - Output: `data/intermediate/sp500_mda_ai_extracts.jsonl` (3,362 flat records)

- `scripts/classify_ai_sentences.py` — Original classification script. **USE AS REFERENCE ONLY.**
  - Binary classification (substantive vs generic)
  - Needs to be updated to 4-class scheme
  - Reusable as template for Step 2 in NLP_NEW

- `scripts/master_panel_analysis.py` — Original regression script. **USE AS REFERENCE ONLY.**
  - Useful as starting point for Step 3/4
  - Needs significant updates for professor's regression specification

- `scripts/pull_wrds_data.py` — WRDS data pull script. **STILL USABLE.**
  - This script works fine and the data is shared via symlinks

## Shared Data (NOT deprecated)

The following data is shared between NLP_test and NLP_NEW (symlinked):
- `data/wrds/` — Compustat and crosswalk files
- `data/intermediate/mdna_sentence_master.jsonl` — NEW pipeline output (1.1GB)
- `sec_filings_full/` — Raw 10-K filings (~87GB)

## Migration Guide

| Old File | New File | Notes |
|----------|----------|-------|
| `extract_mda_ai.py` | `NLP_NEW/scripts/extract_mda_sentences.py` | Complete rewrite |
| `sp500_mda_ai_extracts.jsonl` | `NLP_NEW/data/intermediate/mdna_sentence_master.jsonl` | Sentence-level, 1.1GB |
| `classify_ai_sentences.py` | `NLP_NEW/scripts/classify_ai_sentences.py` | TODO: 4-class update |
| `master_panel_analysis.py` | `NLP_NEW/scripts/master_panel_analysis.py` | TODO: New regressions |
| `pull_wrds_data.py` | `NLP_NEW/data/wrds/` | Data shared via symlinks |

## Why It Was Replaced

The original extraction pipeline had critical issues:
1. **Wrong MD&A boundaries**: TOC entries matched as actual section headers
2. **Massive over-extraction**: Median "MD&A" was 2.2MB (should be 20-100KB)
3. **No deduplication**: Boilerplate counted multiple times, inflating AI counts
4. **Poor sentence splitting**: Regex broken on abbreviations and 10-K formatting
5. **Missing quality filters**: Table fragments, navigation strings, headers included

The new pipeline (`NLP_NEW/scripts/extract_mda_sentences.py`) fixes all of these.

---
**Date:** 2025-04-15
**Replaced by:** `../NLP_NEW/README.md`
