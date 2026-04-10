#!/usr/bin/env python3
"""
AI Disclosure Exploratory Analysis
====================================
基于 MD&A 文本的 AI 披露初步实证分析
Methodology: 关键词匹配 (Wang & Yen 2023) + 文本特征 + 面板回归
"""

import csv, sys, re, os, json
from pathlib import Path
from collections import Counter

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

# ============================================================
# 0. 配置
# ============================================================
DATA_DIR = Path(__file__).resolve().parent
CSV_PATH = DATA_DIR.parent / "resources" / "sp500_selected_industries_mdna_2018_2026.csv"
OUTPUT_DIR = DATA_DIR
OUTPUT_DIR.mkdir(exist_ok=True)

# AI 关键词词典 — 与 ma_pipeline 保持一致
AI_KEYWORDS = [
    "artificial intelligence", "machine learning", "deep learning",
    "large language model", "llm", "generative ai", "genai",
    "neural network", "natural language processing", "nlp",
    "chatgpt", "gpt-4", "gpt-3", "openai", "claude", "gemini",
    "copilot", "predictive model", "computer vision",
    "algorithm", "automation", "robotic process automation", "rpa",
    "intelligent automation",
]

# 关键词分类（用于更细粒度的分析）
AI_KEYWORD_CATS = {
    "core_ai": [
        "artificial intelligence", "machine learning", "deep learning",
        "neural network", "computer vision",
    ],
    "nlp_llm": [
        "natural language processing", "nlp", "large language model",
        "llm", "generative ai", "genai", "chatgpt", "gpt-4", "gpt-3",
        "claude", "gemini", "openai",
    ],
    "automation": [
        "automation", "robotic process automation", "rpa",
        "intelligent automation",
    ],
    "generic": [
        "algorithm", "predictive model", "copilot",
    ],
}

# ============================================================
# 1. 数据加载与清洗
# ============================================================
def load_data():
    csv.field_size_limit(sys.maxsize)
    # Check if file has header
    with open(CSV_PATH) as f:
        first_line = f.readline().strip()
    has_header = first_line.startswith('cik') or first_line.startswith('date')

    if has_header:
        df = pd.read_csv(CSV_PATH)
    else:
        df = pd.read_csv(CSV_PATH, names=['cik', 'date', 'company', 'mdna'])

    # 清理 AIG 名称不一致
    df['company'] = df['company'].str.replace(
        'AMERICAN INTERNATIONAL GROUP, INC.', 'AMERICAN INTERNATIONAL GROUP INC')

    # 提取年份
    df['year'] = pd.to_datetime(df['date']).dt.year

    # 行业标签
    industry_map = {
        'AFLAC INC': 'Insurance',
        'AMERICAN INTERNATIONAL GROUP INC': 'Insurance',
        'BERKLEY W R CORP': 'Insurance',
        'Unum Group': 'Insurance',
        'AMERICAN ELECTRIC POWER CO INC': 'Utilities',
        'AMERICAN EXPRESS CO': 'Financial Services',
        'AUTOMATIC DATA PROCESSING INC': 'Business Services',
    }
    df['industry'] = df['company'].map(industry_map)

    # 唯一公司ID（短名）
    ticker_map = {
        'AFLAC INC': 'AFL',
        'AMERICAN INTERNATIONAL GROUP INC': 'AIG',
        'BERKLEY W R CORP': 'WRB',
        'Unum Group': 'UNM',
        'AMERICAN ELECTRIC POWER CO INC': 'AEP',
        'AMERICAN EXPRESS CO': 'AXP',
        'AUTOMATIC DATA PROCESSING INC': 'ADP',
    }
    df['ticker'] = df['company'].map(ticker_map)

    # 文本长度
    df['text_len'] = df['mdna'].str.len()

    return df


# ============================================================
# 2. AI 指标构建 (关键词法)
# ============================================================
def build_ai_features(df):
    """为每条 MD&A 构建 AI 披露指标"""
    results = []

    for idx, row in df.iterrows():
        text = row['mdna'].lower()
        words = re.findall(r'[a-z]+(?:\'[a-z]+)?', text)
        n_words = len(words)

        # 句子分割（近似）
        sentences = re.split(r'(?<=[.!?])\s+', text.replace('\n', ' '))
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        n_sentences = len(sentences)

        # 关键词匹配
        ai_hits = {}
        ai_total_count = 0
        ai_sentences = []

        for kw in AI_KEYWORDS:
            pattern = r'\b' + re.escape(kw) + r'\b'
            matches = re.findall(pattern, text)
            count = len(matches)
            if count > 0:
                ai_hits[kw] = count
                ai_total_count += count

        # AI 句子（包含至少一个 AI 关键词的句子）
        for sent in sentences:
            sent_lower = sent.lower()
            matched = [kw for kw in AI_KEYWORDS if re.search(r'\b' + re.escape(kw) + r'\b', sent_lower)]
            if matched:
                ai_sentences.append({
                    'sentence': sent[:200],  # 截断存储
                    'keywords': list(set(matched)),
                })

        # 按类别汇总
        cat_counts = {}
        for cat, kws in AI_KEYWORD_CATS.items():
            cat_counts[cat] = sum(ai_hits.get(kw, 0) for kw in kws)

        # 是否有特定时代的关键词
        has_llm = any(kw in ai_hits for kw in ['llm', 'generative ai', 'genai', 'chatgpt', 'gpt-4', 'claude', 'gemini'])

        results.append({
            'cik': row['cik'],
            'ticker': row['ticker'],
            'company': row['company'],
            'industry': row['industry'],
            'date': row['date'],
            'year': row['year'],

            # 文本特征
            'n_words': n_words,
            'n_sentences': n_sentences,
            'text_len': row['text_len'],

            # AI 指标
            'AI_Disclosure': 1 if ai_total_count > 0 else 0,
            'AI_Freq': ai_total_count,
            'AI_Freq_log': np.log1p(ai_total_count),
            'AI_Density': ai_total_count / max(n_words, 1),
            'AI_Density_per10k': (ai_total_count / max(n_words, 1)) * 10000,
            'n_ai_keywords_unique': len(ai_hits),
            'n_ai_sentences': len(ai_sentences),
            'AI_Sentence_Density': len(ai_sentences) / max(n_sentences, 1),

            # 类别计数
            'AI_core_ai': cat_counts.get('core_ai', 0),
            'AI_nlp_llm': cat_counts.get('nlp_llm', 0),
            'AI_automation': cat_counts.get('automation', 0),
            'AI_generic': cat_counts.get('generic', 0),

            # LLM 时代
            'Has_LLM': int(has_llm),

            # 原始 hits（用于检查）
            'ai_hits': json.dumps(ai_hits, ensure_ascii=False),
            'ai_sentence_details': json.dumps(ai_sentences, ensure_ascii=False),
        })

    return pd.DataFrame(results)


# ============================================================
# 3. 描述性统计 & 图表
# ============================================================
def descriptive_stats(aidf, output_dir):
    print("=" * 60)
    print("1. DESCRIPTIVE STATISTICS")
    print("=" * 60)

    # 总体面板描述
    print(f"\nPanel: {aidf['ticker'].nunique()} firms × {aidf['year'].nunique()} years = {len(aidf)} obs")
    print(f"AI Disclosure rate: {aidf['AI_Disclosure'].mean():.1%}")
    print(f"Mean AI Freq: {aidf['AI_Freq'].mean():.1f}")
    print(f"Mean AI Density (per 10k words): {aidf['AI_Density_per10k'].mean():.2f}")
    print(f"Firms with LLM mentions: {aidf[aidf['Has_LLM']==1]['ticker'].nunique()}")

    # 按年份
    print("\n--- By Year ---")
    yearly = aidf.groupby('year').agg(
        n_filings=('ticker', 'count'),
        ai_disclosure_rate=('AI_Disclosure', 'mean'),
        mean_ai_freq=('AI_Freq', 'mean'),
        mean_ai_density=('AI_Density_per10k', 'mean'),
        has_llm=('Has_LLM', 'sum'),
    )
    print(yearly.to_string())
    yearly.to_csv(output_dir / 'summary_yearly.csv')

    # 按公司
    print("\n--- By Company ---")
    byco = aidf.groupby('ticker').agg(
        industry=('industry', 'first'),
        n_filings=('year', 'count'),
        ai_disclosure_rate=('AI_Disclosure', 'mean'),
        mean_ai_freq=('AI_Freq', 'mean'),
        max_ai_freq=('AI_Freq', 'max'),
        mean_ai_density=('AI_Density_per10k', 'mean'),
        has_llm=('Has_LLM', 'max'),
    )
    print(byco.to_string())
    byco.to_csv(output_dir / 'summary_by_company.csv')

    # 按行业
    print("\n--- By Industry ---")
    byind = aidf.groupby('industry').agg(
        n_filings=('ticker', 'count'),
        ai_disclosure_rate=('AI_Disclosure', 'mean'),
        mean_ai_density=('AI_Density_per10k', 'mean'),
    )
    print(byind.to_string())
    byind.to_csv(output_dir / 'summary_by_industry.csv')

    # === 图表 ===
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 1) AI disclosure rate over time
    ax1 = axes[0, 0]
    ax1.plot(yearly.index, yearly['ai_disclosure_rate'], 'o-', lw=2, color='#2196F3')
    ax1.set_xlabel('Year')
    ax1.set_ylabel('AI Disclosure Rate')
    ax1.set_title('Share of Filings with AI Mentions')
    ax1.set_ylim(0, 1.05)
    ax1.grid(True, alpha=0.3)

    # 2) AI density over time
    ax2 = axes[0, 1]
    ax2.bar(yearly.index, yearly['mean_ai_density'], color='#FF9800', alpha=0.8)
    ax2.set_xlabel('Year')
    ax2.set_ylabel('AI Density (per 10k words)')
    ax2.set_title('Average AI Keyword Density in MD&A')
    ax2.grid(True, alpha=0.3, axis='y')

    # 3) Company comparison
    ax3 = axes[1, 0]
    byco_sorted = byco.sort_values('mean_ai_density')
    colors = ['#4CAF50' if x > 0 else '#ccc' for x in byco_sorted['has_llm']]
    ax3.barh(byco_sorted.index, byco_sorted['mean_ai_density'], color=colors, alpha=0.8)
    ax3.set_xlabel('AI Density (per 10k words)')
    ax3.set_title('Avg AI Density by Company\n(green = has LLM mentions)')
    ax3.grid(True, alpha=0.3, axis='x')

    # 4) Keyword category breakdown by year
    ax4 = axes[1, 1]
    cats = ['core_ai', 'nlp_llm', 'automation', 'generic']
    cat_labels = ['Core AI', 'NLP/LLM', 'Automation', 'Generic']
    yearly_cats = aidf.groupby('year')[['AI_' + c for c in cats]].sum()
    yearly_cats.columns = cat_labels
    yearly_cats.plot(kind='bar', stacked=True, ax=ax4, alpha=0.85)
    ax4.set_xlabel('Year')
    ax4.set_ylabel('Total Keyword Count')
    ax4.set_title('AI Keyword Counts by Category')
    ax4.legend(loc='upper left', fontsize=8)
    ax4.tick_params(axis='x', rotation=45)
    ax4.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(output_dir / 'fig_descriptive.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n✅ Saved: {output_dir / 'fig_descriptive.png'}")


# ============================================================
# 4. 关键词演变分析 (Cao et al. 风格)
# ============================================================
def keyword_evolution(aidf, output_dir):
    print("\n" + "=" * 60)
    print("2. KEYWORD EVOLUTION OVER TIME (Cao et al. style)")
    print("=" * 60)

    # 汇总所有关键词出现次数，按年份
    all_years_hits = {}
    for _, row in aidf.iterrows():
        y = row['year']
        if y not in all_years_hits:
            all_years_hits[y] = Counter()
        for kw, cnt in json.loads(row['ai_hits']).items():
            all_years_hits[y][kw] += cnt

    top_kws = sorted(set(k for year_hits in all_years_hits.values() for k in year_hits),
                     key=lambda k: sum(all_years_hits[y].get(k, 0) for y in all_years_hits),
                     reverse=True)[:15]

    ev_df = pd.DataFrame(index=sorted(all_years_hits.keys()))
    for kw in top_kws:
        ev_df[kw] = [all_years_hits[y].get(kw, 0) for y in ev_df.index]

    print("\nTop 15 AI Keywords by Year:")
    print(ev_df.to_string())
    ev_df.to_csv(output_dir / 'keyword_evolution.csv')

    # 图表
    fig, ax = plt.subplots(figsize=(14, 6))
    ev_df.plot(kind='bar', stacked=True, ax=ax, alpha=0.85, colormap='tab20')
    ax.set_xlabel('Year')
    ax.set_ylabel('Keyword Count')
    ax.set_title('AI Keyword Usage Trends (Top 15)')
    ax.legend(loc='center left', bbox_to_anchor=(1.0, 0.5), fontsize=7)
    ax.tick_params(axis='x', rotation=45)
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(output_dir / 'fig_keyword_evolution.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"✅ Saved: {output_dir / 'fig_keyword_evolution.png'}")


# ============================================================
# 5. 回归分析
# ============================================================
def run_regressions(aidf, output_dir):
    print("\n" + "=" * 60)
    print("3. REGRESSION ANALYSIS")
    print("=" * 60)

    results_log = []

    # --------------------------------------------------
    # Regression 1: Panel OLS — AI Density vs Year
    # 看 AI 披露密度是否随时间显著增加
    # --------------------------------------------------
    print("\n--- Regression 1: AI_Density_per10k on Year ---")
    print("    (Does AI disclosure density increase over time?)")

    reg1 = aidf.copy()
    model1 = smf.ols('AI_Density_per10k ~ year', data=reg1).fit(cov_type='HC3')
    print(model1.summary())
    results_log.append({
        'model': 'AI_Density ~ Year (pooled OLS)',
        'key_coef': model1.params.get('year', np.nan),
        'key_pval': model1.pvalues.get('year', np.nan),
        'n_obs': len(reg1),
        'r_squared': model1.rsquared,
    })

    # 保存完整结果
    with open(output_dir / 'reg1_ai_density_year.txt', 'w') as f:
        f.write(model1.summary().as_text())

    # --------------------------------------------------
    # Regression 2: Panel OLS with firm FE
    # AI Density = β*Year + α_i + ε
    # --------------------------------------------------
    print("\n--- Regression 2: AI_Density_per10k on Year + Firm FE ---")
    print("    (Controlling for firm fixed effects)")

    reg2 = aidf.copy()
    model2 = smf.ols('AI_Density_per10k ~ C(ticker) + year', data=reg2).fit(cov_type='HC3')
    print(model2.summary())
    results_log.append({
        'model': 'AI_Density ~ Year + Firm FE',
        'key_coef': model2.params.get('year', np.nan),
        'key_pval': model2.pvalues.get('year', np.nan),
        'n_obs': len(reg2),
        'r_squared': model2.rsquared,
    })

    with open(output_dir / 'reg2_ai_density_year_fe.txt', 'w') as f:
        f.write(model2.summary().as_text())

    # --------------------------------------------------
    # Regression 3: Logit — AI Disclosure (0/1) on Year
    # 公司某年是否在 MD&A 中提及 AI
    # --------------------------------------------------
    print("\n--- Regression 3: AI_Disclosure (0/1) Logit on Year ---")

    reg3 = aidf.copy()
    model3 = smf.logit('AI_Disclosure ~ year', data=reg3).fit(disp=False)
    print(model3.summary())
    results_log.append({
        'model': 'AI_Disclosure ~ Year (Logit)',
        'key_coef': model3.params.get('year', np.nan),
        'key_pval': model3.pvalues.get('year', np.nan),
        'n_obs': len(reg3),
        'pseudo_r_squared': model3.prsquared,
    })

    with open(output_dir / 'reg3_ai_disclosure_logit.txt', 'w') as f:
        f.write(model3.summary().as_text())

    # --------------------------------------------------
    # Regression 4: AI_Density on Industry + Year
    # --------------------------------------------------
    print("\n--- Regression 4: AI_Density ~ Industry + Year ---")

    reg4 = aidf.copy()
    model4 = smf.ols('AI_Density_per10k ~ C(industry) + year', data=reg4).fit(cov_type='HC3')
    print(model4.summary())
    results_log.append({
        'model': 'AI_Density ~ Industry + Year',
        'key_coef': model4.params.get('year', np.nan),
        'key_pval': model4.pvalues.get('year', np.nan),
        'n_obs': len(reg4),
        'r_squared': model4.rsquared,
    })

    with open(output_dir / 'reg4_ai_density_industry_year.txt', 'w') as f:
        f.write(model4.summary().as_text())

    # --------------------------------------------------
    # Regression 5: AI_Density on text_len (control for verbosity)
    # --------------------------------------------------
    print("\n--- Regression 5: AI_Density ~ text_len + Year + Firm FE ---")
    print("    (Controlling for document verbosity)")

    reg5 = aidf.copy()
    reg5['log_text_len'] = np.log(reg5['text_len'])
    model5 = smf.ols('AI_Density_per10k ~ log_text_len + year + C(ticker)', data=reg5).fit(cov_type='HC3')
    print(model5.summary())
    results_log.append({
        'model': 'AI_Density ~ log(text_len) + Year + Firm FE',
        'key_coef_year': model5.params.get('year', np.nan),
        'key_pval_year': model5.pvalues.get('year', np.nan),
        'key_coef_len': model5.params.get('log_text_len', np.nan),
        'key_pval_len': model5.pvalues.get('log_text_len', np.nan),
        'n_obs': len(reg5),
        'r_squared': model5.rsquared,
    })

    with open(output_dir / 'reg5_ai_density_verbosity_fe.txt', 'w') as f:
        f.write(model5.summary().as_text())

    # --------------------------------------------------
    # Regression 6: LLM-era effect
    # LLM关键词出现后，AI披露密度是否更高
    # --------------------------------------------------
    print("\n--- Regression 6: AI_Density ~ Has_LLM + Year + Firm FE ---")

    reg6 = aidf.copy()
    model6 = smf.ols('AI_Density_per10k ~ Has_LLM + year + C(ticker)', data=reg6).fit(cov_type='HC3')
    print(model6.summary())
    results_log.append({
        'model': 'AI_Density ~ Has_LLM + Year + Firm FE',
        'key_coef_llm': model6.params.get('Has_LLM', np.nan),
        'key_pval_llm': model6.pvalues.get('Has_LLM', np.nan),
        'n_obs': len(reg6),
        'r_squared': model6.rsquared,
    })

    with open(output_dir / 'reg6_ai_density_llm_effect.txt', 'w') as f:
        f.write(model6.summary().as_text())

    # --------------------------------------------------
    # 汇总回归结果
    # --------------------------------------------------
    reg_summary = pd.DataFrame(results_log)
    reg_summary.to_csv(output_dir / 'regression_summary.csv', index=False)
    print(f"\n✅ Regression summary saved: {output_dir / 'regression_summary.csv'}")

    return reg_summary


# ============================================================
# 6. 提取 AI 句子样本
# ============================================================
def extract_ai_sentences(aidf, output_dir):
    """导出所有 AI 相关句子，方便人工检查和后续 GPT 分类"""
    samples = []
    for _, row in aidf.iterrows():
        if row['n_ai_sentences'] == 0:
            continue
        sentences = json.loads(row['ai_sentence_details'])
        for s in sentences:
            samples.append({
                'ticker': row['ticker'],
                'company': row['company'],
                'year': row['year'],
                'industry': row['industry'],
                'keywords': ', '.join(s['keywords']),
                'sentence': s['sentence'],
            })

    sample_df = pd.DataFrame(samples)
    sample_df = sample_df.sort_values(['year', 'ticker'])
    sample_df.to_csv(output_dir / 'ai_sentences_sample.csv', index=False)
    print(f"\n✅ Extracted {len(sample_df)} AI sentences → {output_dir / 'ai_sentences_sample.csv'}")
    return sample_df


# ============================================================
# MAIN
# ============================================================
def main():
    print("Loading data...")
    df = load_data()

    print("Building AI features...")
    aidf = build_ai_features(df)

    # 保存完整特征表
    save_cols = [c for c in aidf.columns if c != 'ai_sentence_details']
    aidf[save_cols].to_csv(OUTPUT_DIR / 'ai_features_panel.csv', index=False)
    print(f"✅ Saved full panel: {OUTPUT_DIR / 'ai_features_panel.csv'}")

    # 描述性统计
    descriptive_stats(aidf, OUTPUT_DIR)

    # 关键词演变
    keyword_evolution(aidf, OUTPUT_DIR)

    # 回归分析
    run_regressions(aidf, OUTPUT_DIR)

    # 提取句子
    extract_ai_sentences(aidf, OUTPUT_DIR)

    print("\n" + "=" * 60)
    print("ALL DONE. Output files:")
    for f in sorted(OUTPUT_DIR.iterdir()):
        size = f.stat().st_size
        print(f"  {f.name:<40s} {size:>10,} bytes")
    print("=" * 60)


if __name__ == '__main__':
    main()
