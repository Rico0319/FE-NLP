#!/usr/bin/env python3
"""
Part 2: Regressions with Qwen-classified substantive vs generic AI disclosure
===============================================================================
Uses the Qwen classification results from qwen_classified.jsonl
"""

import json, os
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUTPUT_DIR = "/home/ricoz/econ_lab/FE-NLP/NLP_test"

# ============================================================
# 1. Load panel + classification
# ============================================================
panel = pd.read_csv(f"{OUTPUT_DIR}/ai_features_panel.csv")

# Load Qwen classifications
cls_records = []
with open(f"{OUTPUT_DIR}/qwen_classified.jsonl") as f:
    for line in f:
        cls_records.append(json.loads(line))
cls_df = pd.DataFrame(cls_records)

# Aggregate classifications back to panel level
cls_agg = cls_df.groupby(['ticker', 'year']).agg(
    n_sentences_classified=('classification', 'count'),
    substantive_cnt=('classification', lambda x: (x == 'substantive').sum()),
    generic_cnt=('classification', lambda x: (x == 'generic').sum()),
    avg_confidence=('confidence', 'mean'),
).reset_index()

# Merge with panel
df = panel.merge(cls_agg, on=['ticker', 'year'], how='left')
df['substantive_cnt'] = df['substantive_cnt'].fillna(0).astype(int)
df['generic_cnt'] = df['generic_cnt'].fillna(0).astype(int)
df['has_substantive'] = (df['substantive_cnt'] > 0).astype(int)
df['has_generic'] = (df['generic_cnt'] > 0).astype(int)
df['substantive_ratio'] = df['substantive_cnt'] / df['n_sentences_classified'].replace(0, np.nan)
df['substantive_density'] = df['substantive_cnt'] / df['n_words'].replace(0, np.nan) * 10000
df['generic_density'] = df['generic_cnt'] / df['n_words'].replace(0, np.nan) * 10000

print(f"Panel: {len(df)} obs, {df['ticker'].nunique()} firms")
print(f"Firms with substantive AI disclosure: {df['has_substantive'].sum()}")
print(f"Substantive sentences: {df['substantive_cnt'].sum()}")
print(f"Generic sentences: {df['generic_cnt'].sum()}")

# ============================================================
# 2. New regressions
# ============================================================
results_log = []

# --- Reg A: Substantive vs Generic over time ---
print("\n--- Reg A: Substantive_Density vs Year ---")
mask = df['substantive_density'].notna()
regA = df[mask]
modelA = smf.ols('substantive_density ~ year', data=regA).fit(cov_type='HC3')
print(modelA.summary())
results_log.append({'model': 'Substantive_Density ~ Year',
                    'coef': modelA.params.get('year'), 'pval': modelA.pvalues.get('year')})

with open(f"{OUTPUT_DIR}/regA_substantive_density_year.txt", 'w') as f:
    f.write(modelA.summary().as_text())

# --- Reg B: Generic_Density vs Year ---
print("\n--- Reg B: Generic_Density vs Year ---")
mask = df['generic_density'].notna()
regB = df[mask]
modelB = smf.ols('generic_density ~ year', data=regB).fit(cov_type='HC3')
print(modelB.summary())
results_log.append({'model': 'Generic_Density ~ Year',
                    'coef': modelB.params.get('year'), 'pval': modelB.pvalues.get('year')})

with open(f"{OUTPUT_DIR}/regB_generic_density_year.txt", 'w') as f:
    f.write(modelB.summary().as_text())

# --- Reg C: Has_Substantive Logit on Year ---
print("\n--- Reg C: Has_Substantive (0/1) Logit on Year ---")
modelC = smf.logit('has_substantive ~ year', data=df).fit(disp=False)
print(modelC.summary())
results_log.append({'model': 'Has_Substantive ~ Year (Logit)',
                    'coef': modelC.params.get('year'), 'pval': modelC.pvalues.get('year'),
                    'pseudo_r2': modelC.prsquared})

with open(f"{OUTPUT_DIR}/regC_has_substantive_logit.txt", 'w') as f:
    f.write(modelC.summary().as_text())

# --- Reg D: Substantive_Ratio vs Year (among firms that mention AI) ---
print("\n--- Reg D: Substantive_Ratio vs Year (AI-disclosing firms only) ---")
regD = df[df['n_sentences_classified'] > 0].copy()
modelD = smf.ols('substantive_ratio ~ year', data=regD).fit(cov_type='HC3')
print(modelD.summary())
results_log.append({'model': 'Substantive_Ratio ~ Year (AI-firms)',
                    'coef': modelD.params.get('year'), 'pval': modelD.pvalues.get('year')})

with open(f"{OUTPUT_DIR}/regD_substantive_ratio_year.txt", 'w') as f:
    f.write(modelD.summary().as_text())

# --- Reg E: AI_Density = Substantive + Generic + Year + Firm FE ---
print("\n--- Reg E: Decompose AI_Density = Substantive + Generic (Firm FE) ---")
regE = df[df['substantive_density'].notna() & df['generic_density'].notna()].copy()
# Long format: each obs has both sub + gen density
# Use multivariate-style: explain total density composition
modelE = smf.ols('substantive_density ~ generic_density + year + C(ticker)', data=regE).fit(cov_type='HC3')
print(modelE.summary())
results_log.append({'model': 'Substantive_Density ~ Generic_Density + Year + Firm FE',
                    'coef_sub': modelE.params.get('generic_density'),
                    'pval_sub': modelE.pvalues.get('generic_density')})

with open(f"{OUTPUT_DIR}/regE_decompose_density.txt", 'w') as f:
    f.write(modelE.summary().as_text())

# ============================================================
# 3. Save summary
# ============================================================
reg2_summary = pd.DataFrame(results_log)
reg2_summary.to_csv(f"{OUTPUT_DIR}/regression_summary_part2.csv", index=False)

# Updated panel with classification
df.to_csv(f"{OUTPUT_DIR}/ai_features_panel_with_classification.csv", index=False)

# ============================================================
# 4. Figures
# ============================================================
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Left: Substantive vs Generic counts by year
yearly_cls = df.groupby('year').agg(
    substantive=('substantive_cnt', 'sum'),
    generic=('generic_cnt', 'sum'),
).reset_index()

ax1 = axes[0]
ax1.bar(yearly_cls['year'] - 0.15, yearly_cls['generic'], 0.3, label='Generic', color='#FF9800', alpha=0.8)
ax1.bar(yearly_cls['year'] + 0.15, yearly_cls['substantive'], 0.3, label='Substantive', color='#4CAF50', alpha=0.8)
ax1.set_xlabel('Year')
ax1.set_ylabel('Sentence Count')
ax1.set_title('Substantive vs Generic AI Sentences by Year')
ax1.legend()
ax1.grid(True, alpha=0.3, axis='y')

# Right: Substantive ratio trend
ax2 = axes[1]
regD_plot = regD.dropna(subset=['substantive_ratio'])
ax2.scatter(regD_plot['year'], regD_plot['substantive_ratio'], s=60, c='#2196F3', alpha=0.6, edgecolors='white')
# Add trend line
if len(regD_plot) > 1:
    z = np.polyfit(regD_plot['year'], regD_plot['substantive_ratio'], 1)
    p = np.poly1d(z)
    ax2.plot(regD_plot['year'].sort_values(), p(regD_plot['year'].sort_values()), '--', color='#F44336', lw=2)
ax2.set_xlabel('Year')
ax2.set_ylabel('Substantive Ratio')
ax2.set_title('Substantive / Total AI Sentences Ratio\n(among AI-disclosing firms)')
ax2.set_ylim(-0.05, 0.5)
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(f"{OUTPUT_DIR}/fig_classification.png", dpi=150, bbox_inches='tight')
plt.close()
print(f"\n✅ Saved: {OUTPUT_DIR}/fig_classification.png")

print("\n" + "=" * 60)
print("PART 2 DONE. All output files updated.")
print("=" * 60)
