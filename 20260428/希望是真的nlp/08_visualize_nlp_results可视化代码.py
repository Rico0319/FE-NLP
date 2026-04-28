# -*- coding: utf-8 -*-
"""
Professional NLP visualizations for AI disclosure project.

This script reads outputs from the pure NLP pipeline:
1. sentence_level_nlp_ai_candidates_only.csv
2. firm_year_ai_disclosure_summary.csv
3. ai_dictionary_word2vec_expanded.csv
4. word2vec_mdna_ai.model

It generates:
1. Time-series intensity plot
2. Annual category counts
3. Annual category composition
4. Top matched AI terms
5. Top implementation / risk / generic terms
6. Word2Vec semantic map using t-SNE
7. Word cloud of AI dictionary / matched AI terms
8. Distribution of firm-year substantive AI intensity
"""

import os
from collections import Counter

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from gensim.models import Word2Vec


# ============================================================
# 0. Paths
# ============================================================

OUTPUT_DIR = "/Users/jiazuo/Desktop/nlp/nlppp/nlp_outputs"

SENTENCE_PATH = os.path.join(
    OUTPUT_DIR,
    "sentence_level_nlp_ai_candidates_only.csv"
)

SUMMARY_PATH = os.path.join(
    OUTPUT_DIR,
    "firm_year_ai_disclosure_summary.csv"
)

AI_DICT_PATH = os.path.join(
    OUTPUT_DIR,
    "dictionaries",
    "ai_dictionary_word2vec_expanded.csv"
)

W2V_MODEL_PATH = os.path.join(
    OUTPUT_DIR,
    "word2vec_mdna_ai.model"
)

FIGURE_DIR = os.path.join(OUTPUT_DIR, "figures")
os.makedirs(FIGURE_DIR, exist_ok=True)


# ============================================================
# 1. Plot settings
# ============================================================

plt.rcParams["figure.dpi"] = 120
plt.rcParams["savefig.dpi"] = 300
plt.rcParams["font.size"] = 11
plt.rcParams["axes.titlesize"] = 14
plt.rcParams["axes.labelsize"] = 12
plt.rcParams["legend.fontsize"] = 10
plt.rcParams["xtick.labelsize"] = 10
plt.rcParams["ytick.labelsize"] = 10


def save_figure(fig, filename):
    """
    Save each figure as PNG and PDF.
    """
    png_path = os.path.join(FIGURE_DIR, filename + ".png")
    pdf_path = os.path.join(FIGURE_DIR, filename + ".pdf")
    fig.tight_layout()
    fig.savefig(png_path, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)
    print("Saved:", png_path)
    print("Saved:", pdf_path)


def split_terms(x):
    """
    Split semicolon-separated matched terms.
    """
    if pd.isna(x):
        return []
    x = str(x).strip()
    if not x:
        return []
    return [term.strip() for term in x.split(";") if term.strip()]


def count_terms(series):
    """
    Count matched terms from a column.
    """
    counter = Counter()
    for value in series.dropna():
        counter.update(split_terms(value))
    return counter


# ============================================================
# 2. Load data
# ============================================================

print("\nLoading NLP outputs...")

sent = pd.read_csv(SENTENCE_PATH)
summary = pd.read_csv(SUMMARY_PATH)

if os.path.exists(AI_DICT_PATH):
    ai_dict = pd.read_csv(AI_DICT_PATH)
else:
    ai_dict = pd.DataFrame(columns=["term"])

print("AI candidate sentences:", len(sent))
print("Firm-year observations:", len(summary))


# ============================================================
# 3. Figure 1: Time-series disclosure intensity
# ============================================================

print("\nCreating Figure 1: Time-series intensity...")

year_col = "fiscal_year"

intensity_cols = [
    "generic_ai_disclosure_sentence_intensity",
    "substantive_ai_disclosure_sentence_intensity",
    "substantive_ai_implementation_sentence_intensity",
    "substantive_ai_risk_governance_sentence_intensity"
]

available_intensity_cols = [c for c in intensity_cols if c in summary.columns]

for c in available_intensity_cols:
    summary[c] = pd.to_numeric(summary[c], errors="coerce")

trend = (
    summary
    .groupby(year_col)[available_intensity_cols]
    .mean()
    .reset_index()
    .sort_values(year_col)
)

fig, ax = plt.subplots(figsize=(10, 6))

label_map = {
    "generic_ai_disclosure_sentence_intensity": "Generic AI disclosure",
    "substantive_ai_disclosure_sentence_intensity": "Substantive AI disclosure",
    "substantive_ai_implementation_sentence_intensity": "Substantive AI implementation",
    "substantive_ai_risk_governance_sentence_intensity": "Substantive AI risk/governance"
}

for col in available_intensity_cols:
    ax.plot(
        trend[year_col],
        trend[col],
        marker="o",
        linewidth=2,
        label=label_map.get(col, col)
    )

ax.set_title("Average AI Disclosure Intensity over Time")
ax.set_xlabel("Fiscal Year")
ax.set_ylabel("Average sentence-based intensity")
ax.legend(frameon=False)
ax.grid(True, alpha=0.3)

save_figure(fig, "figure_01_time_series_ai_disclosure_intensity")


# ============================================================
# 4. Figure 2: Annual counts by category
# ============================================================

print("\nCreating Figure 2: Annual category counts...")

count_cols = [
    "n_generic_ai_disclosure_sentences",
    "n_substantive_ai_implementation_sentences",
    "n_substantive_ai_risk_governance_sentences"
]

available_count_cols = [c for c in count_cols if c in summary.columns]

for c in available_count_cols:
    summary[c] = pd.to_numeric(summary[c], errors="coerce").fillna(0)

annual_counts = (
    summary
    .groupby(year_col)[available_count_cols]
    .sum()
    .reset_index()
    .sort_values(year_col)
)

fig, ax = plt.subplots(figsize=(10, 6))

bottom = np.zeros(len(annual_counts))

for col in available_count_cols:
    ax.bar(
        annual_counts[year_col],
        annual_counts[col],
        bottom=bottom,
        label=label_map.get(col.replace("n_", "").replace("_sentences", "_sentence_intensity"), col)
    )
    bottom += annual_counts[col].values

ax.set_title("Annual Counts of AI Disclosure Sentences")
ax.set_xlabel("Fiscal Year")
ax.set_ylabel("Number of AI disclosure sentences")
ax.legend(frameon=False)
ax.grid(True, axis="y", alpha=0.3)

save_figure(fig, "figure_02_annual_category_counts")


# ============================================================
# 5. Figure 3: Annual category composition
# ============================================================

print("\nCreating Figure 3: Annual category composition...")

composition = annual_counts.copy()
composition_total = composition[available_count_cols].sum(axis=1)
composition_total = composition_total.replace(0, np.nan)

for col in available_count_cols:
    composition[col] = composition[col] / composition_total

fig, ax = plt.subplots(figsize=(10, 6))

bottom = np.zeros(len(composition))

for col in available_count_cols:
    ax.bar(
        composition[year_col],
        composition[col],
        bottom=bottom,
        label=col
        .replace("n_", "")
        .replace("_sentences", "")
        .replace("_", " ")
        .title()
    )
    bottom += composition[col].fillna(0).values

ax.set_title("Composition of AI Disclosure Categories over Time")
ax.set_xlabel("Fiscal Year")
ax.set_ylabel("Share among classified AI sentences")
ax.set_ylim(0, 1)
ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(1.02, 1))
ax.grid(True, axis="y", alpha=0.3)

save_figure(fig, "figure_03_annual_category_composition")


# ============================================================
# 6. Figure 4: Top matched AI terms
# ============================================================

print("\nCreating Figure 4: Top matched AI terms...")

ai_counter = count_terms(sent["nlp_ai_matched_terms"])

top_n = 30
top_ai_terms = ai_counter.most_common(top_n)

if top_ai_terms:
    terms, counts = zip(*top_ai_terms)
    terms = list(terms)[::-1]
    counts = list(counts)[::-1]

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.barh(terms, counts)

    ax.set_title("Top Matched AI Dictionary Terms")
    ax.set_xlabel("Frequency in AI candidate sentences")
    ax.set_ylabel("AI terms")
    ax.grid(True, axis="x", alpha=0.3)

    save_figure(fig, "figure_04_top_matched_ai_terms")
else:
    print("No AI matched terms found. Skipping Figure 4.")


# ============================================================
# 7. Figure 5: Top matched terms by classification dimension
# ============================================================

print("\nCreating Figure 5: Top matched terms by category dictionaries...")

term_columns = [
    ("nlp_generic_matched_terms", "Generic disclosure terms"),
    ("nlp_implementation_matched_terms", "Implementation terms"),
    ("nlp_risk_matched_terms", "Risk / governance terms")
]

for col, title in term_columns:
    if col not in sent.columns:
        continue

    counter = count_terms(sent[col])
    top_terms = counter.most_common(25)

    if not top_terms:
        print(f"No matched terms for {col}. Skipping.")
        continue

    terms, counts = zip(*top_terms)
    terms = list(terms)[::-1]
    counts = list(counts)[::-1]

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(terms, counts)
    ax.set_title(title)
    ax.set_xlabel("Frequency")
    ax.set_ylabel("Matched terms")
    ax.grid(True, axis="x", alpha=0.3)

    clean_name = col.replace("nlp_", "").replace("_matched_terms", "")
    save_figure(fig, f"figure_05_top_{clean_name}_terms")


# ============================================================
# 8. Figure 6: Word2Vec semantic map of AI dictionary
# ============================================================

print("\nCreating Figure 6: Word2Vec semantic map...")

try:
    from sklearn.manifold import TSNE

    if os.path.exists(W2V_MODEL_PATH):
        model = Word2Vec.load(W2V_MODEL_PATH)

        # Prefer frequently matched AI terms because they are actually used in classification.
        frequent_terms = [term for term, count in ai_counter.most_common(100)]

        # If too few matched terms, use AI dictionary terms.
        if len(frequent_terms) < 20 and "term" in ai_dict.columns:
            frequent_terms += ai_dict["term"].dropna().astype(str).tolist()

        # Keep terms available in Word2Vec vocabulary.
        terms_for_map = []
        seen = set()

        for term in frequent_terms:
            term = str(term).strip()
            if term in model.wv and term not in seen:
                terms_for_map.append(term)
                seen.add(term)

        terms_for_map = terms_for_map[:80]

        if len(terms_for_map) >= 5:
            X = np.array([model.wv[t] for t in terms_for_map])

            perplexity = min(30, max(5, (len(terms_for_map) - 1) // 3))

            tsne = TSNE(
                n_components=2,
                perplexity=perplexity,
                random_state=42,
                init="pca",
                learning_rate="auto"
            )

            X_2d = tsne.fit_transform(X)

            fig, ax = plt.subplots(figsize=(12, 9))
            ax.scatter(X_2d[:, 0], X_2d[:, 1], s=35)

            for i, term in enumerate(terms_for_map):
                ax.annotate(
                    term,
                    (X_2d[i, 0], X_2d[i, 1]),
                    fontsize=8,
                    alpha=0.85
                )

            ax.set_title("Word2Vec Semantic Map of AI Dictionary Terms")
            ax.set_xlabel("t-SNE dimension 1")
            ax.set_ylabel("t-SNE dimension 2")
            ax.grid(True, alpha=0.25)

            save_figure(fig, "figure_06_word2vec_tsne_ai_dictionary")
        else:
            print("Too few AI dictionary terms found in Word2Vec vocabulary. Skipping t-SNE map.")
    else:
        print("Word2Vec model not found. Skipping t-SNE map.")

except Exception as e:
    print("Skipping t-SNE visualization because of error:")
    print(e)


# ============================================================
# 9. Figure 7: Word cloud of AI matched terms
# ============================================================

print("\nCreating Figure 7: AI word cloud...")

try:
    from wordcloud import WordCloud

    if ai_counter:
        wordcloud = WordCloud(
            width=1600,
            height=900,
            max_words=120,
            background_color="white",
            collocations=False
        ).generate_from_frequencies(ai_counter)

        fig, ax = plt.subplots(figsize=(12, 7))
        ax.imshow(wordcloud, interpolation="bilinear")
        ax.axis("off")
        ax.set_title("Word Cloud of Matched AI Terms")

        save_figure(fig, "figure_07_ai_matched_terms_wordcloud")
    else:
        print("No AI matched terms found. Skipping word cloud.")

except Exception as e:
    print("Skipping word cloud because of error:")
    print(e)


# ============================================================
# 10. Figure 8: Firm-year distribution of substantive AI intensity
# ============================================================

print("\nCreating Figure 8: Distribution of substantive AI intensity...")

dist_col = "substantive_ai_disclosure_sentence_intensity"

if dist_col in summary.columns:
    values = pd.to_numeric(summary[dist_col], errors="coerce").dropna()

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.hist(values, bins=40)

    ax.set_title("Distribution of Firm-Year Substantive AI Disclosure Intensity")
    ax.set_xlabel("Substantive AI disclosure sentence intensity")
    ax.set_ylabel("Number of firm-year observations")
    ax.grid(True, axis="y", alpha=0.3)

    save_figure(fig, "figure_08_distribution_substantive_ai_intensity")
else:
    print(f"{dist_col} not found. Skipping distribution plot.")


# ============================================================
# 11. Figure 9: Category heatmap by fiscal year
# ============================================================

print("\nCreating Figure 9: Category intensity heatmap...")

heatmap_cols = [
    "generic_ai_disclosure_sentence_intensity",
    "substantive_ai_implementation_sentence_intensity",
    "substantive_ai_risk_governance_sentence_intensity"
]

available_heatmap_cols = [c for c in heatmap_cols if c in summary.columns]

if available_heatmap_cols:
    heatmap_data = (
        summary
        .groupby(year_col)[available_heatmap_cols]
        .mean()
        .sort_index()
    )

    fig, ax = plt.subplots(figsize=(10, 6))

    im = ax.imshow(
        heatmap_data.T.values,
        aspect="auto"
    )

    ax.set_title("Heatmap of Average AI Disclosure Intensity")
    ax.set_xlabel("Fiscal Year")
    ax.set_ylabel("Disclosure category")

    ax.set_xticks(np.arange(len(heatmap_data.index)))
    ax.set_xticklabels(heatmap_data.index.astype(str), rotation=45, ha="right")

    category_labels = [
        "Generic",
        "Implementation",
        "Risk/Governance"
    ]

    ax.set_yticks(np.arange(len(available_heatmap_cols)))
    ax.set_yticklabels(category_labels[:len(available_heatmap_cols)])

    fig.colorbar(im, ax=ax, label="Average sentence-based intensity")

    save_figure(fig, "figure_09_category_intensity_heatmap")
else:
    print("No heatmap columns found. Skipping heatmap.")


print("\nAll figures saved to:")
print(FIGURE_DIR)