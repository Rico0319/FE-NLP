# S&P 500 AI Disclosure Analysis — NLP Test

## Overview

This project analyzes AI-related disclosures in S&P 500 companies' 10-K MD&A (Management's Discussion & Analysis) sections from 2019–2025. We distinguish between **substantive** AI disclosure (concrete, business-specific AI information) and **generic** AI disclosure (vague, boilerplate mentions), testing the "AI washing" hypothesis.

## Pipeline Summary

```
SEC EDGAR → Download 10-Ks → Extract MD&A → Find AI Sentences
    → Qwen Classification → Merge with Compustat → Panel Regressions
```

| Step | Script | What it does |
|------|--------|-------------|
| 1. Download | `scripts/download_sp500_10k.py` | Downloads all S&P 500 10-Ks from SEC EDGAR (3,362 filings, 87GB) |
| 2. Extract | `scripts/extract_mda_ai.py` | Extracts Item 7 MD&A text, finds AI keyword sentences (15,639 sentences) |
| 3. Classify | `scripts/classify_ai_sentences.py` | Qwen-plus classifies each sentence as substantive vs generic (16,260 total) |
| 4. WRDS Pull | `scripts/pull_wrds_data.py` | Pulls Compustat fundamentals + CIK↔GVKEY crosswalk from WRDS |
| 5. Master Panel | `scripts/master_panel_analysis.py` | Merges AI data with Compustat, calculates controls, runs regressions |

## Key Results

### 1. Scale
- **489 S&P 500 companies** × 7 years = **3,362 filings** processed
- **2,145 filings** (63.8%) contain AI mentions in MD&A
- **16,260 AI sentences** extracted and classified
- **2,107 firm-years** merged with Compustat financial data (358 unique firms)

### 2. Substantive vs Generic Classification
| Category | Count | % |
|----------|-------|---|
| **Generic** | 13,814 | **85.0%** |
| **Substantive** | 2,446 | **15.0%** |

### 3. Time Trend — The Core Finding
Substantive disclosure rate grew **3.4× from 2019 to 2025**:

| Year | Filings | AI Sentences | Substantive % | Generic % |
|------|---------|-------------|---------------|-----------|
| 2019 | 472 | 1,371 | 6.7% | 93.3% |
| 2020 | 483 | 1,619 | 9.1% | 90.9% |
| 2021 | 490 | 1,906 | 10.9% | 89.1% |
| 2022 | 489 | 2,135 | 10.6% | 89.4% |
| 2023 | 490 | 2,276 | 11.9% | 88.1% |
| 2024 | 483 | 3,115 | 20.3% | 79.7% |
| 2025 | 472 | 3,838 | 22.7% | 77.3% |

**The ChatGPT inflection point (2024) is clear**: substantive disclosure nearly doubled from 11.9% to 20.3%, then rose to 22.7% in 2025. But even in 2025, 77% of AI mentions remain generic.

### 4. Top Substantive Firms (by % of AI mentions that are substantive)
| Firm | Industry | Substantive % | AI Sentences |
|------|----------|---------------|-------------|
| HOLX (Hologic) | Healthcare | 72.5% | 51 |
| ADBE (Adobe) | Technology | 71.0% | 162 |
| EFX (Equifax) | Financials | 57.3% | 75 |
| PANW (Palo Alto) | Technology | 56.3% | 71 |
| NVDA (NVIDIA) | Technology | 53.0% | 83 |
| FTNT (Fortinet) | Technology | 52.6% | 78 |
| CRWD (CrowdStrike) | Technology | 44.2% | 104 |
| WDAY (Workday) | Technology | 42.5% | 134 |

### 5. Bottom Firms (Most "AI Washing")
| Firm | Generic % | Total AI Sentences |
|------|-----------|-------------------|
| ROK (Rockwell Automation) | 96.3% | 897 |
| HON (Honeywell) | 95.1% | 753 |
| AIG | 93.4% | 244 |
| ADP | 88.4% | 328 |

### 6. Regression Results — WITHOUT Financial Controls
| Model | Key Result | p-value |
|-------|-----------|---------|
| AI Density ~ Year (pooled OLS) | β = 0.24 per 10k words/year | 0.014 ✅ |
| AI Density ~ Year + Firm FE | β = 0.25 | 0.014 ✅ |
| AI Disclosure (0/1) Logit ~ Year | OR = 1.35× per year | 0.035 ✅ |
| Generic Density ~ Year + Firm FE | β = 0.12 | 0.013 ✅ |
| LLM Effect (Has_LLM dummy) | R² jumps 0.42 → 0.72 | — |

### 7. Regression Results — WITH Financial Controls (Master Panel)

**Sample:** 2,107 firm-years, 358 unique firms with both AI and Compustat data.

| Model | Year β | p-value | R² |
|-------|--------|---------|----|
| AI Disclosure (0/1) Logit ~ Controls | 0.176 | **0.016** ✅ | 0.056 |
| Substantive Ratio ~ Controls (OLS) | 0.022 | **0.013** ✅ | 0.044 |
| log(AI_Count+1) ~ Controls (OLS) | 0.088 | **<0.001** ✅ | 0.096 |
| **log(AI_Count) ~ Controls + Firm FE** | **0.108** | **<0.001** ✅ | **0.268** |

**Controls:** log(Assets), ROA, Leverage, R&D Intensity, Cash Ratio.

**Key interpretation:** Even after controlling for firm size, profitability, leverage, and firm fixed effects, the year coefficient remains **highly significant at p < 0.001**. The AI disclosure trend is NOT driven by larger firms, more profitable firms, or firm-specific factors — it's a genuine secular trend. The multiplicative effect is **e^0.108 = 1.11× per year**, meaning AI disclosure grows ~11% annually even within the same firm.

### 8. Financial Characteristics of AI-Disclosing Firms
| Variable | Mean | Median | Std |
|----------|------|--------|-----|
| Total Assets ($M) | 88,324 | 23,641 | 299,960 |
| Revenue ($M) | 31,476 | 11,761 | 63,731 |
| ROA | 0.07 | 0.06 | 0.08 |
| Leverage | 0.33 | 0.31 | 0.24 |
| R&D Intensity | 0.04 | 0.02 | 0.05 |

## Directory Structure

```
NLP_test/
├── README.md                          ← You are here
├── .env                               ← Qwen API key (gitignored!)
├── .env.example                       ← Template for team members
├── .gitignore
├── requirements.txt                   ← Python dependencies
├── scripts/                           ← All analysis scripts
│   ├── download_sp500_10k.py          # Step 1: Download 10-Ks from SEC
│   ├── extract_mda_ai.py              # Step 2: Extract MD&A + AI sentences
│   ├── classify_ai_sentences.py       # Step 3: Qwen substantive/generic
│   ├── pull_wrds_data.py              # Step 4: Pull Compustat from WRDS
│   ├── master_panel_analysis.py       # Step 5: Merge + regressions
│   ├── ai_disclosure_analysis.py      # Legacy: initial small-sample regressions
│   ├── regression_part2.py            # Legacy: classification-based regressions
│   └── qwen_classification.py         # Legacy: single-threaded classifier
├── data/
│   ├── intermediate/                  # Intermediate data
│   │   ├── sp500_mda_ai_extracts.jsonl   # 3,362 filings × AI sentences
│   │   ├── ai_sentences_sample.csv       # 61 sentences (legacy small sample)
│   │   ├── keyword_evolution.csv
│   │   └── qwen_classified.jsonl         # 61 sentences (legacy small sample)
│   ├── final/                         # Final analysis-ready data
│   │   ├── sp500_ai_classified.jsonl     # ⭐ Main result: 16,260 classified sentences
│   │   ├── ai_features_panel.csv         # Panel with keyword metrics
│   │   ├── ai_features_panel_with_classification.csv
│   │   └── master_panel.csv              # ⭐ Master panel with Compustat
│   └── wrds/                          # WRDS/Compustat raw data
│       ├── cik_gvkey_crosswalk.csv       # SEC CIK ↔ Compustat GVKEY
│       ├── compustat_annual_2018_2025.csv # 96,151 firm-years
│       └── gics_mapping.csv              # GICS sector mapping
├── results/
│   ├── RESULTS.md                      # Detailed results report
│   ├── summary_yearly.csv
│   ├── summary_by_company.csv
│   ├── summary_by_industry.csv
│   ├── regression_summary_master.csv   # Master panel regression summary
│   ├── regressions/                    # Full regression outputs
│   │   ├── reg1-6_*.txt                # Part 1: keyword-based regressions
│   │   ├── regA-E_*.txt                # Part 2: classification-based regressions
│   │   └── regression_summary*.csv     # Regression coefficient summaries
│   └── figures/
│       ├── fig_descriptive.png           # 4-panel overview (small sample)
│       ├── fig_keyword_evolution.png     # Keyword trends
│       ├── fig_classification.png        # Substantive vs generic (small sample)
│       └── fig_master_panel.png          # ⭐ 6-panel master panel summary
└── sec_filings_full/                   # Raw SEC 10-K HTML files (87GB, gitignored)
    └── sec-edgar-filings/
        └── [ticker]/10-K/[accession]/...
```

## How to Run

### Prerequisites
```bash
conda activate NLP-env
pip install -r requirements.txt
```

### Setup API Key
```bash
cp .env.example .env
# Edit .env with your Qwen API key
```

### Reproduce Full Pipeline
```bash
python scripts/download_sp500_10k.py    # ~30 min, 87GB raw files
python scripts/extract_mda_ai.py        # ~45 min
python scripts/classify_ai_sentences.py # ~60 min
python scripts/pull_wrds_data.py        # Interactive: enter WRDS credentials
python scripts/master_panel_analysis.py # ~1 min
```

## Methodology Notes

- **Classification criteria**: Based on group guidelines (定义.pdf) — 6 substantive categories (Product Development, AI Product Provider, Pricing Optimization, Inventory Management, Operational Efficiency, AI Risk) vs generic (vague, promotional, non-specific)
- **Key principle**: "Do not infer" — only classify as substantive when the text explicitly states what AI does, where it applies, and what result it affects
- **API**: Qwen-plus via DashScope (OpenAI-compatible endpoint)
- **Financial data**: Compustat Annual Fundamentals via WRDS (indfmt=INDL, datafmt=STD, popsrc=D, consol=C)
- **Standard errors**: Heteroscedasticity-robust (HC3) for all OLS regressions

## Cloud Storage for Group

The `sec_filings_full/` directory (87GB raw 10-K files) is gitignored. Groupmates should either:
1. Run `scripts/download_sp500_10k.py` themselves (free, ~30 min), or
2. Download from shared cloud storage

All other data files (classified sentences, master panel, Compustat) are committed to git.
