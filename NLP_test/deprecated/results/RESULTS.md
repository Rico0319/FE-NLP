# AI Disclosure Exploratory Analysis — Results Summary

---

## Dataset
- **7 firms** × **8 years** (2018–2025) = **50 observations**
- Covers: Insurance (AFL, AIG, UNM, WRB), Financial Services (AXP), Utilities (AEP), Business Services (ADP)
- AI sentences classified by **Qwen-plus** via DashScope API (61 sentences)

---

## Part 1: Keyword Analysis (Wang & Yen 2023 style)

### 1.1 AI Disclosure is Rising Sharply

| Regression | β (year coefficient) | p-value |
|---|---|---|
| AI Density vs Year (pooled OLS) | 0.244 per 10k words/yr | **0.014** ✅ |
| AI Density vs Year + Firm FE | 0.246 | **0.014** ✅ |
| AI Disclosure (0/1) Logit | 0.301 (OR=1.35×/yr) | **0.035** ✅ |

### 1.2 Disclosure Rate by Year

| Year | Filings | AI Disclosure Rate | Mean Density |
|------|---------|--------------------|--------------|
| 2018 | 7 | 14% | 0.02 |
| 2019 | 7 | 29% | 0.38 |
| 2020 | 6 | 17% | 0.08 |
| 2021 | 6 | 33% | 0.35 |
| 2022 | 6 | 33% | 0.29 |
| 2023 | 7 | 57% | 0.66 |
| 2024 | 6 | 50% | 2.23 |
| 2025 | 5 | 60% | 1.47 |

**Inflection point: 2023** → ChatGPT effect.

### 1.3 Keyword Evolution

| Keyword | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|---|
| artificial intelligence | 0 | 1 | 1 | 3 | 2 | 8 | 18 | 18 |
| machine learning | 0 | 0 | 0 | 1 | 1 | 1 | 6 | 6 |
| automation | 1 | 2 | 0 | 0 | 1 | 3 | 2 | 2 |
| genai | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 0 |
| generative ai | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 |

---

## Part 2: Qwen Classification (Substantive vs Generic)

### 2.1 Classification Results

| Category | Count | % |
|---|---|---|
| **Generic** | 59 | 96.7% |
| **Substantive** | 2 | 3.3% |
| Errors | 0 | 0% |

### 2.2 The 2 Substantive Sentences

Both from **ADP 2024**:

1. **"we took action to lead with best-in-class HCM technology by launching ADP Assist, our cross-platform solution powered by generative AI (GenAI) that empowers employees and HR professionals through smart..."**
   - Names a specific product (ADP Assist), AI technology (GenAI), users (employees/HR), and platform scope.

2. **"research and development expenses increased for fiscal 2024 due to increased investments and costs to develop, support, and maintain our new and existing products, and increased investments in GenAI..."**
   - Concrete R&D spending allocation to a specific AI technology category.

### 2.3 Classification by Year

| Year | Generic | Substantive | Total | Substantive % |
|------|---------|-------------|-------|---------------|
| 2018 | 1 | 0 | 1 | 0% |
| 2019 | 3 | 0 | 3 | 0% |
| 2020 | 1 | 0 | 1 | 0% |
| 2021 | 3 | 0 | 3 | 0% |
| 2022 | 3 | 0 | 3 | 0% |
| 2023 | 8 | 0 | 8 | 0% |
| 2024 | 21 | **2** | 23 | 8.7% |
| 2025 | 19 | 0 | 19 | 0% |

### 2.4 Classification by Company

| Company | Generic | Substantive | Total |
|---|---|---|---|
| AEP | 2 | 0 | 2 |
| AFL | 3 | 0 | 3 |
| **ADP** | 5 | **2** | 7 |
| AIG | 35 | 0 | 35 |
| AXP | 14 | 0 | 14 |

### 2.5 Substantive vs Generic Regressions

| Regression | β (year) | p-value | Interpretation |
|---|---|---|---|
| Generic_Density ~ Year | **0.123** ✅ | **0.013** | Generic AI disclosure is rising significantly |
| Substantive_Density ~ Year | 0.028 | 0.330 | Not significant (only 2 obs) |
| Has_Substantive (Logit) ~ Year | 0.769 | 0.336 | Not significant |
| Substantive_Ratio ~ Year | 0.011 | 0.356 | No significant quality improvement trend |

### 2.6 Key Insight

**The time trend in AI disclosure is driven entirely by generic mentions.** Generic AI density grows significantly (β=0.123, p=0.013), while substantive disclosure remains near-zero. Only ADP in 2024 broke through with GenAI-specific product announcements.

This suggests most companies are engaging in what the literature calls **"AI washing"** — mentioning AI in boilerplate risk factors and vague strategic statements without concrete implementation details.

---

## Part 3: Additional Findings

### 3.1 Verbosity is NOT a Confounder

Regression controlling for MD&A text length: text length coefficient p=0.724. AI mentions aren't just an artifact of longer reports.

### 3.2 LLM-Era Effect

Adding a "Has LLM terms" dummy boosted R² from 0.42 to **0.72**, suggesting LLM-related mentions capture most of the cross-firm variation in AI disclosure.

### 3.3 Industry Patterns

- **Financial Services (AXP):** Most frequent AI mentions (87.5% disclosure rate)
- **Insurance:** Driven entirely by AIG; UNM and WRB have zero AI mentions
- **Utilities (AEP):** Minimal AI discussion (12.5% rate)

---

## Limitations

1. **Small sample** — 7 firms, 50 obs, only 61 AI sentences. The ma_pipeline targets ~195 firms.
2. **No financial controls** — Need Compustat data for Assets, ROA, Leverage, MtB etc.
3. **Sentence extraction limitation** — We extracted AI sentences from the full MD&A, not specifically from M&A-related paragraphs (the ma_pipeline step2 does M&A filtering). The current extraction is broader (any AI mention in MD&A).
4. **AIG naming issue** — Resolved by merging "AMERICAN INTERNATIONAL GROUP INC" and "AMERICAN INTERNATIONAL GROUP, INC."

---

## Output Files (24 files)

| File | Description |
|---|---|
| `ai_features_panel.csv` | Panel with keyword-based AI metrics |
| `ai_features_panel_with_classification.csv` | Panel + Qwen classification aggregated |
| `ai_sentences_sample.csv` | 61 AI sentences extracted |
| `qwen_classified.jsonl` | Qwen classification of each sentence |
| `fig_descriptive.png` | 4-panel descriptive figure |
| `fig_keyword_evolution.png` | Keyword trends stacked bar |
| `fig_classification.png` | Substantive vs Generic by year |
| `reg1-6_*.txt` | Part 1 regression outputs (6 files) |
| `regA-E_*.txt` | Part 2 regression outputs (5 files) |
| `regression_summary.csv` | Part 1 coefficients |
| `regression_summary_part2.csv` | Part 2 coefficients |
| `summary_yearly.csv` | Yearly aggregates |
| `summary_by_company.csv` | Firm-level aggregates |
| `summary_by_industry.csv` | Industry aggregates |
| `keyword_evolution.csv` | Keyword counts by year |
