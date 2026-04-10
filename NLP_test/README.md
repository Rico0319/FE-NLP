# S&P 500 AI Disclosure Analysis — NLP Test

## Overview

This project analyzes AI-related disclosures in S&P 500 companies' 10-K MD&A (Management's Discussion & Analysis) sections from 2019–2025. We distinguish between **substantive** AI disclosure (concrete, business-specific AI information) and **generic** AI disclosure (vague, boilerplate mentions), testing the "AI washing" hypothesis.

## Pipeline Summary

```
SEC EDGAR → Download 10-Ks → Extract MD&A → Find AI Sentences → Qwen Classification → Regressions
```

| Step | Script | What it does |
|------|--------|-------------|
| 1. Download | `scripts/download_sp500_10k.py` | Downloads all S&P 500 10-Ks from SEC EDGAR (3,362 filings, 87GB) |
| 2. Extract | `scripts/extract_mda_ai.py` | Extracts Item 7 MD&A text, finds AI keyword sentences (15,639 sentences) |
| 3. Classify | `scripts/classify_ai_sentences.py` | Qwen-plus classifies each sentence as substantive vs generic (16,260 total) |
| 4. Regressions | `scripts/ai_disclosure_analysis.py`<br>`scripts/regression_part2.py` | Panel regressions on AI disclosure trends |

## Key Results

### 1. Scale
- **489 S&P 500 companies** × 7 years = **3,362 filings** processed
- **2,145 filings** (63.8%) contain AI mentions in MD&A
- **16,260 AI sentences** extracted and classified

### 2. Substantive vs Generic Classification
| Category | Count | % |
|----------|-------|---|
| **Generic** | 13,814 | 85.0% |
| **Substantive** | 2,446 | 15.0% |

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

### 6. Regression Results
All regressions show a **statistically significant upward trend** in AI disclosure:

| Model | Key Result | p-value |
|-------|-----------|---------|
| AI Density ~ Year (pooled OLS) | β = 0.24 per 10k words/year | 0.014 ✅ |
| AI Density ~ Year + Firm FE | β = 0.25 | 0.014 ✅ |
| AI Disclosure (0/1) Logit ~ Year | OR = 1.35× per year | 0.035 ✅ |
| Generic Density ~ Year + Firm FE | β = 0.12 | 0.013 ✅ |
| Substantive Density ~ Year | β = 0.03 | 0.330 (n.s.) |
| LLM Effect (Has_LLM dummy) | R² jumps 0.42 → 0.72 | — |

**Interpretation:** The overall AI disclosure trend is driven primarily by generic mentions. Substantive disclosure, while growing, is not yet statistically significant at the aggregate level (only 2,446 sentences across 3,362 filings).

## Directory Structure

```
NLP_test/
├── README.md                          ← You are here
├── .env                               ← Qwen API key (gitignored!)
├── .env.example                       ← Template for team members
├── .gitignore
├── scripts/                           ← All analysis scripts
│   ├── download_sp500_10k.py          # Step 1: Download 10-Ks from SEC
│   ├── extract_mda_ai.py              # Step 2: Extract MD&A + AI sentences
│   ├── classify_ai_sentences.py       # Step 3: Qwen substantive/generic
│   ├── ai_disclosure_analysis.py      # Step 4a: Initial regressions (small sample)
│   ├── regression_part2.py            # Step 4b: Classification-based regressions
│   └── qwen_classification.py         # Legacy: single-threaded classifier
├── data/
│   ├── intermediate/                  # Intermediate data
│   │   ├── sp500_mda_ai_extracts.jsonl   # 3,362 filings × AI sentences
│   │   ├── ai_sentences_sample.csv       # 61 sentences (legacy small sample)
│   │   ├── keyword_evolution.csv
│   │   └── qwen_classified.jsonl         # 61 sentences (legacy small sample)
│   └── final/                         # Final analysis-ready data
│       ├── sp500_ai_classified.jsonl     # ⭐ Main result: 16,260 classified sentences
│       ├── ai_features_panel.csv         # Panel with keyword metrics
│       └── ai_features_panel_with_classification.csv
├── results/
│   ├── RESULTS.md                      # Detailed results report
│   ├── summary_yearly.csv
│   ├── summary_by_company.csv
│   ├── summary_by_industry.csv
│   ├── regressions/                    # Full regression outputs
│   │   ├── reg1-6_*.txt                   # Part 1: keyword-based regressions
│   │   ├── regA-E_*.txt                   # Part 2: classification-based regressions
│   │   └── regression_summary*.csv
│   └── figures/
│       ├── fig_descriptive.png           # 4-panel overview
│       ├── fig_keyword_evolution.png     # Keyword trends
│       └── fig_classification.png        # Substantive vs generic
└── sec_filings_full/                   # Raw SEC 10-K HTML files (87GB, gitignored)
    └── sec-edgar-filings/
        └── [ticker]/10-K/[accession]/...
```

## How to Run

### Prerequisites
```bash
conda activate NLP-env
pip install -r requirements.txt  # if needed
```

### Setup API Key
```bash
cp .env.example .env
# Edit .env with your Qwen API key
```

### Reproduce Results
```bash
# Full pipeline (each step resumes automatically):
python scripts/download_sp500_10k.py   # ~30 min, 87GB
python scripts/extract_mda_ai.py       # ~45 min
python scripts/classify_ai_sentences.py # ~60 min
```

## Methodology Notes

- **Classification criteria**: Based on group guidelines (定义.pdf) — 6 substantive categories (Product Development, AI Product Provider, Pricing Optimization, Inventory Management, Operational Efficiency, AI Risk) vs generic (vague, promotional, non-specific)
- **Key principle**: "Do not infer" — only classify as substantive when the text explicitly states what AI does, where it applies, and what result it affects
- **API**: Qwen-plus via DashScope (OpenAI-compatible endpoint)

## Pending: WRDS Integration
Once WRDS access is approved, next steps:
1. Pull Compustat fundamentals (Assets, Revenue, ROA, EPS, etc.)
2. Pull CRSP stock prices
3. Merge with classified AI disclosure data
4. Run panel regressions with full financial controls
