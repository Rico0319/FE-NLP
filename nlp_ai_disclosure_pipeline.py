# -*- coding: utf-8 -*-
"""
Pure NLP pipeline for AI disclosure classification in 10-K MD&A sentences.

Method:
1. Read sentence-level MD&A JSONL.
2. Use NLTK for tokenization and lemmatization.
3. Use Gensim Phrase Detection to identify bigrams.
4. Use Gensim Word2Vec to learn AI-related vocabulary from the corpus.
5. Build an expanded AI dictionary from seed terms.
6. Classify AI-related sentences into:
   - generic_ai_disclosure
   - substantive_ai_implementation
   - substantive_ai_risk_governance
7. Aggregate sentence-level results into firm-year disclosure intensity.

No LLM.
No OpenAI API.
No prompt-based classification.
"""

import os
import re
import ast
import json
import warnings
import multiprocessing
from collections import Counter

import numpy as np
import pandas as pd
from tqdm import tqdm

import nltk
from nltk.tokenize import RegexpTokenizer
from nltk.stem import WordNetLemmatizer

from gensim.models import Word2Vec
from gensim.models.phrases import Phrases, Phraser


# ============================================================
# 0. Configuration
# ============================================================

INPUT_PATH = "/Users/jiazuo/Desktop/nlp/nlppp/mdna_sentence_master.jsonl"
OUTPUT_DIR = "/Users/jiazuo/Desktop/nlp/nlppp/nlp_outputs"

TEXT_COL = "sentence_clean"

# For testing, you can set NROWS = 20000.
# For the full run, use NROWS = None.
NROWS = None

# Word2Vec parameters, following the spirit of the reference paper.
W2V_VECTOR_SIZE = 100
W2V_WINDOW = 5
W2V_MIN_COUNT = 5
W2V_EPOCHS = 10
W2V_SEED = 42

# Phrase detection parameters.
PHRASE_MIN_COUNT = 5
PHRASE_THRESHOLD = 10

# AI dictionary expansion.
AI_TOPN_PER_SEED = 50
AI_MIN_SIMILARITY = 0.35

# Category dictionary expansion.
# This is conservative because category labels are more context-sensitive.
EXPAND_CATEGORY_DICTIONARIES = True
CATEGORY_TOPN_PER_SEED = 10
CATEGORY_MIN_SIMILARITY = 0.60

# Classification thresholds.
IMPLEMENTATION_THRESHOLD = 2.5
RISK_THRESHOLD = 2.5

os.makedirs(OUTPUT_DIR, exist_ok=True)

warnings.filterwarnings("ignore")
tqdm.pandas()


# ============================================================
# 1. NLTK setup
# ============================================================

def download_nltk_resource(resource_name, resource_path):
    try:
        nltk.data.find(resource_path)
    except LookupError:
        nltk.download(resource_name)


download_nltk_resource("wordnet", "corpora/wordnet")
download_nltk_resource("omw-1.4", "corpora/omw-1.4")

tokenizer = RegexpTokenizer(r"[A-Za-z][A-Za-z0-9_'-]*")
lemmatizer = WordNetLemmatizer()


# ============================================================
# 2. Helper functions
# ============================================================

def safe_text(x):
    """Convert missing values to empty strings."""
    if pd.isna(x):
        return ""
    return str(x)


def normalize_bool(x, default=True):
    """Safely parse boolean-like columns."""
    if pd.isna(x):
        return default
    if isinstance(x, bool):
        return x
    s = str(x).strip().lower()
    if s in ["true", "1", "yes", "y"]:
        return True
    if s in ["false", "0", "no", "n"]:
        return False
    return default


def preprocess_text(text):
    """
    NLTK-style preprocessing:
    - lowercasing
    - tokenization
    - remove one-letter tokens except "ai"
    - lemmatization

    We do NOT remove stop words because Word2Vec needs context.
    """
    text = safe_text(text).lower()

    # Normalize common written forms.
    text = text.replace("artificial-intelligence", "artificial intelligence")
    text = text.replace("machine-learning", "machine learning")
    text = text.replace("deep-learning", "deep learning")
    text = text.replace("ai-powered", "ai powered")
    text = text.replace("ai-enabled", "ai enabled")
    text = text.replace("ai-driven", "ai driven")
    text = text.replace("third-party", "third party")
    text = text.replace("supply-chain", "supply chain")

    raw_tokens = tokenizer.tokenize(text)

    tokens = []
    for tok in raw_tokens:
        tok = tok.strip("'").strip("-")
        if not tok:
            continue

        # Keep "ai", remove other one-letter tokens.
        if len(tok) == 1 and tok != "ai":
            continue

        # Lemmatize verbs first, then nouns.
        tok = lemmatizer.lemmatize(tok, pos="v")
        tok = lemmatizer.lemmatize(tok, pos="n")

        tokens.append(tok)

    return tokens


def normalize_term(term):
    """
    Convert a phrase into the same style as Gensim bigram tokens.
    Example:
        "artificial intelligence" -> "artificial_intelligence"
    """
    term = str(term).lower().strip()
    term = term.replace("-", " ")
    term = re.sub(r"\s+", " ", term)
    term = term.replace(" ", "_")
    return term


def raw_phrase_match(text, phrases):
    """Find raw phrase matches in the original lowercase text."""
    text = safe_text(text).lower()
    matches = []
    for phrase in phrases:
        phrase_raw = phrase.replace("_", " ")
        pattern = r"\b" + re.escape(phrase_raw) + r"\b"
        if re.search(pattern, text):
            matches.append(phrase)
    return sorted(set(matches))


def token_match(tokens, dictionary_terms):
    """Match dictionary terms against tokenized/bigrammed tokens."""
    token_set = set(tokens)
    return sorted(token_set.intersection(dictionary_terms))


def clean_for_expansion(term):
    """
    Filter noisy Word2Vec expansion terms.
    This does not need to be too strict because we save the dictionary
    for manual review.
    """
    if not isinstance(term, str):
        return False
    if len(term) < 3:
        return False
    if term.isdigit():
        return False
    if re.search(r"\d{4,}", term):
        return False

    blocklist = {
        "company", "business", "result", "operation", "include", "including",
        "financial", "statement", "annual", "report", "form", "item",
        "management", "discussion", "analysis", "could", "would", "may",
        "also", "other", "certain", "various", "related", "future"
    }
    if term in blocklist:
        return False

    return True


def expand_dictionary_with_word2vec(model, seed_terms, topn=20, min_similarity=0.50):
    """
    Expand a seed dictionary using Word2Vec semantic similarity.
    Returns:
        expanded_terms: set
        expansion_records: DataFrame-friendly list of dict records
    """
    expanded_terms = set()
    records = []

    for seed in seed_terms:
        seed_norm = normalize_term(seed)
        expanded_terms.add(seed_norm)

        if seed_norm in model.wv:
            records.append({
                "seed": seed_norm,
                "expanded_term": seed_norm,
                "similarity": 1.0,
                "source": "manual_seed_in_vocab"
            })

            for term, sim in model.wv.most_similar(seed_norm, topn=topn):
                if sim >= min_similarity and clean_for_expansion(term):
                    expanded_terms.add(term)
                    records.append({
                        "seed": seed_norm,
                        "expanded_term": term,
                        "similarity": float(sim),
                        "source": "word2vec_expansion"
                    })
        else:
            records.append({
                "seed": seed_norm,
                "expanded_term": seed_norm,
                "similarity": np.nan,
                "source": "manual_seed_not_in_vocab"
            })

    return expanded_terms, records


def join_unique(items):
    """Join a list of matched terms for CSV output."""
    if not items:
        return ""
    return "; ".join(sorted(set(items)))


# ============================================================
# 3. Seed dictionaries based on your definitions
# ============================================================

# AI seed terms: these are used to learn an AI-related dictionary via Word2Vec.
AI_SEED_TERMS = [
    "ai",
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "neural network",
    "natural language processing",
    "computer vision",
    "predictive analytics",
    "predictive model",
    "algorithm",
    "automation",
    "robotics",
    "data mining",
    "large language model",
    "generative ai",
    "chatbot",
    "intelligent system",
    "intelligent analytics",
    "model training",
    "speech recognition",
    "facial recognition",
    "recommendation engine"
]

AI_RAW_PHRASES = [normalize_term(x) for x in AI_SEED_TERMS if " " in x or "-" in x]
AI_RAW_PHRASES += [
    "ai_powered",
    "ai_enabled",
    "ai_driven",
    "algorithmic_tool",
    "algorithmic_model"
]
AI_RAW_PHRASES = sorted(set(AI_RAW_PHRASES))


# Generic AI disclosure:
# Broad, vague, promotional, aspirational, strategic, market-facing statements.
GENERIC_SEED_TERMS = [
    "explore",
    "embrace",
    "commit",
    "committed",
    "forefront",
    "innovation",
    "innovative",
    "opportunity",
    "potential",
    "future",
    "trend",
    "transform",
    "transformation",
    "digital",
    "digitalization",
    "technology",
    "technological",
    "strategy",
    "strategic",
    "initiative",
    "capability",
    "capabilities",
    "advance",
    "advancing",
    "evolving",
    "emerging",
    "revolution",
    "market positioning"
]


# Substantive AI implementation:
# Product development, AI product provider, pricing optimization,
# inventory management, operational efficiency.
IMPLEMENTATION_ACTION_SEEDS = [
    "use",
    "utilize",
    "apply",
    "employ",
    "deploy",
    "implement",
    "integrate",
    "embed",
    "leverage",
    "develop",
    "build",
    "provide",
    "offer",
    "sell",
    "deliver",
    "launch",
    "power",
    "automate",
    "optimize",
    "forecast",
    "predict",
    "recommend",
    "detect",
    "simulate",
    "streamline",
    "enhance",
    "improve",
    "reduce"
]

IMPLEMENTATION_DOMAIN_SEEDS = [
    # Product development
    "product",
    "service",
    "platform",
    "solution",
    "tool",
    "system",
    "software",
    "application",
    "research development",
    "r d",
    "design",
    "testing",
    "drug screening",
    "simulation",
    "product performance",
    "time to market",

    # AI product provider
    "customer analytics",
    "data analytics platform",
    "customer service system",
    "client",
    "external customer",
    "intelligent insight",

    # Pricing optimization
    "pricing",
    "dynamic pricing",
    "promotional pricing",
    "revenue management",
    "price optimization",

    # Inventory management
    "inventory",
    "inventory management",
    "demand forecasting",
    "replenishment",
    "stockout",
    "overstock",
    "supply chain",
    "supply chain coordination",
    "inventory turnover",

    # Operational efficiency
    "workflow",
    "internal process",
    "operating workflow",
    "approval workflow",
    "customer request",
    "response time",
    "labor cost",
    "operating cost",
    "cost reduction",
    "efficiency",
    "productivity",
    "automation"
]

IMPLEMENTATION_EFFECT_SEEDS = [
    "increase revenue",
    "reduce cost",
    "reduce operating cost",
    "improve efficiency",
    "improve productivity",
    "enhance customer service",
    "reduce response time",
    "optimize inventory",
    "forecast demand",
    "improve product",
    "accelerate development",
    "reduce time to market",
    "improve decision",
    "improve accuracy",
    "automate task",
    "streamline workflow"
]


# Substantive AI risk/governance:
# Risk must have a concrete source or mechanism, not just "AI may introduce risk."
RISK_SOURCE_SEEDS = [
    "regulation",
    "regulatory",
    "compliance",
    "privacy",
    "data privacy",
    "data protection",
    "cybersecurity",
    "security",
    "bias",
    "ethical",
    "ethics",
    "liability",
    "governance",
    "model risk",
    "model failure",
    "model performance",
    "third party",
    "third party dependence",
    "vendor",
    "platform stability",
    "algorithmic bias",
    "reputation",
    "operational risk",
    "competitive risk",
    "vulnerability"
]

RISK_IMPACT_SEEDS = [
    "increase compliance cost",
    "modify product",
    "modify business practice",
    "affect operation",
    "affect platform stability",
    "affect reputation",
    "damage reputation",
    "legal liability",
    "regulatory scrutiny",
    "business interruption",
    "security breach",
    "privacy breach",
    "data breach",
    "loss",
    "cost",
    "penalty"
]

GENERIC_RISK_TERMS = [
    "risk",
    "uncertainty",
    "challenge",
    "concern"
]


# ============================================================
# 4. Load sentence-level data
# ============================================================

print("\n[1/9] Reading JSONL data...")

if NROWS is None:
    df = pd.read_json(INPUT_PATH, lines=True)
else:
    df = pd.read_json(INPUT_PATH, lines=True, nrows=NROWS)

print(f"Loaded rows: {len(df):,}")

if TEXT_COL not in df.columns:
    raise ValueError(f"Cannot find text column: {TEXT_COL}. Available columns: {list(df.columns)}")

df["_row_id"] = np.arange(len(df))
df[TEXT_COL] = df[TEXT_COL].apply(safe_text)

# Keep only clean, non-duplicate sentences if these flags exist.
if "keep_sentence_flag" in df.columns:
    df = df[df["keep_sentence_flag"].apply(lambda x: normalize_bool(x, default=True))].copy()

if "is_exact_duplicate" in df.columns:
    df = df[~df["is_exact_duplicate"].apply(lambda x: normalize_bool(x, default=False))].copy()

if "is_near_duplicate" in df.columns:
    df = df[~df["is_near_duplicate"].apply(lambda x: normalize_bool(x, default=False))].copy()

df = df.reset_index(drop=True)
print(f"Rows after filtering: {len(df):,}")


# ============================================================
# 5. Build previous/current/next sentence context
# ============================================================

print("\n[2/9] Building local context...")

possible_group_cols = ["cik", "accession_number", "section_name"]
group_cols = [c for c in possible_group_cols if c in df.columns]

if "sentence_order" in df.columns:
    sort_cols = group_cols + ["sentence_order"]
else:
    sort_cols = group_cols + ["_row_id"]

if group_cols:
    df = df.sort_values(sort_cols).reset_index(drop=True)
    df["_prev_text"] = df.groupby(group_cols)[TEXT_COL].shift(1).fillna("")
    df["_next_text"] = df.groupby(group_cols)[TEXT_COL].shift(-1).fillna("")
else:
    df = df.sort_values("_row_id").reset_index(drop=True)
    df["_prev_text"] = df[TEXT_COL].shift(1).fillna("")
    df["_next_text"] = df[TEXT_COL].shift(-1).fillna("")

df["_context_text"] = (
    df["_prev_text"].fillna("") + " " +
    df[TEXT_COL].fillna("") + " " +
    df["_next_text"].fillna("")
)


# ============================================================
# 6. NLTK preprocessing and Gensim phrase detection
# ============================================================

print("\n[3/9] Tokenizing and lemmatizing with NLTK...")

df["_tokens_unigram"] = df[TEXT_COL].progress_apply(preprocess_text)

sentences_unigram = df["_tokens_unigram"].tolist()

print("\n[4/9] Detecting bigrams with Gensim Phrases...")

phrases = Phrases(
    sentences_unigram,
    min_count=PHRASE_MIN_COUNT,
    threshold=PHRASE_THRESHOLD
)
bigram_model = Phraser(phrases)

df["_tokens"] = df["_tokens_unigram"].progress_apply(lambda x: list(bigram_model[x]))

# Build context tokens.
df["_tokens_str"] = df["_tokens"].apply(lambda x: " ".join(x))

if group_cols:
    df["_prev_tokens_str"] = df.groupby(group_cols)["_tokens_str"].shift(1).fillna("")
    df["_next_tokens_str"] = df.groupby(group_cols)["_tokens_str"].shift(-1).fillna("")
else:
    df["_prev_tokens_str"] = df["_tokens_str"].shift(1).fillna("")
    df["_next_tokens_str"] = df["_tokens_str"].shift(-1).fillna("")

df["_context_tokens"] = (
    df["_prev_tokens_str"] + " " +
    df["_tokens_str"] + " " +
    df["_next_tokens_str"]
).str.split()


# Save phrase model.
phrases.save(os.path.join(OUTPUT_DIR, "gensim_bigram_phrases.model"))
bigram_model.save(os.path.join(OUTPUT_DIR, "gensim_bigram_phraser.model"))


# ============================================================
# 7. Train Word2Vec
# ============================================================

print("\n[5/9] Training Word2Vec model...")

workers = max(1, multiprocessing.cpu_count() - 1)

w2v_model = Word2Vec(
    sentences=df["_tokens"].tolist(),
    vector_size=W2V_VECTOR_SIZE,
    window=W2V_WINDOW,
    min_count=W2V_MIN_COUNT,
    workers=workers,
    sg=0,                 # CBOW. You can set sg=1 for Skip-gram.
    epochs=W2V_EPOCHS,
    seed=W2V_SEED
)

w2v_path = os.path.join(OUTPUT_DIR, "word2vec_mdna_ai.model")
w2v_model.save(w2v_path)

print(f"Word2Vec vocabulary size: {len(w2v_model.wv):,}")
print(f"Saved Word2Vec model to: {w2v_path}")


# ============================================================
# 8. Build AI and category dictionaries
# ============================================================

print("\n[6/9] Building Word2Vec-expanded dictionaries...")

all_expansion_records = []

# AI dictionary: this is the main Word2Vec-learned dictionary.
ai_dictionary, ai_records = expand_dictionary_with_word2vec(
    w2v_model,
    AI_SEED_TERMS,
    topn=AI_TOPN_PER_SEED,
    min_similarity=AI_MIN_SIMILARITY
)
for r in ai_records:
    r["dictionary"] = "ai_dictionary"
all_expansion_records.extend(ai_records)

# Category dictionaries.
generic_terms = set(normalize_term(x) for x in GENERIC_SEED_TERMS)

implementation_action_terms = set(normalize_term(x) for x in IMPLEMENTATION_ACTION_SEEDS)
implementation_domain_terms = set(normalize_term(x) for x in IMPLEMENTATION_DOMAIN_SEEDS)
implementation_effect_terms = set(normalize_term(x) for x in IMPLEMENTATION_EFFECT_SEEDS)

risk_source_terms = set(normalize_term(x) for x in RISK_SOURCE_SEEDS)
risk_impact_terms = set(normalize_term(x) for x in RISK_IMPACT_SEEDS)
generic_risk_terms = set(normalize_term(x) for x in GENERIC_RISK_TERMS)

if EXPAND_CATEGORY_DICTIONARIES:
    generic_expanded, records = expand_dictionary_with_word2vec(
        w2v_model,
        GENERIC_SEED_TERMS,
        topn=CATEGORY_TOPN_PER_SEED,
        min_similarity=CATEGORY_MIN_SIMILARITY
    )
    for r in records:
        r["dictionary"] = "generic_dictionary"
    all_expansion_records.extend(records)
    generic_terms = generic_terms.union(generic_expanded)

    impl_action_expanded, records = expand_dictionary_with_word2vec(
        w2v_model,
        IMPLEMENTATION_ACTION_SEEDS,
        topn=CATEGORY_TOPN_PER_SEED,
        min_similarity=CATEGORY_MIN_SIMILARITY
    )
    for r in records:
        r["dictionary"] = "implementation_action_dictionary"
    all_expansion_records.extend(records)
    implementation_action_terms = implementation_action_terms.union(impl_action_expanded)

    impl_domain_expanded, records = expand_dictionary_with_word2vec(
        w2v_model,
        IMPLEMENTATION_DOMAIN_SEEDS,
        topn=CATEGORY_TOPN_PER_SEED,
        min_similarity=CATEGORY_MIN_SIMILARITY
    )
    for r in records:
        r["dictionary"] = "implementation_domain_dictionary"
    all_expansion_records.extend(records)
    implementation_domain_terms = implementation_domain_terms.union(impl_domain_expanded)

    risk_source_expanded, records = expand_dictionary_with_word2vec(
        w2v_model,
        RISK_SOURCE_SEEDS,
        topn=CATEGORY_TOPN_PER_SEED,
        min_similarity=CATEGORY_MIN_SIMILARITY
    )
    for r in records:
        r["dictionary"] = "risk_source_dictionary"
    all_expansion_records.extend(records)
    risk_source_terms = risk_source_terms.union(risk_source_expanded)

# Save dictionaries for manual inspection.
dict_dir = os.path.join(OUTPUT_DIR, "dictionaries")
os.makedirs(dict_dir, exist_ok=True)

pd.DataFrame({"term": sorted(ai_dictionary)}).to_csv(
    os.path.join(dict_dir, "ai_dictionary_word2vec_expanded.csv"),
    index=False,
    encoding="utf-8-sig"
)

pd.DataFrame({"term": sorted(generic_terms)}).to_csv(
    os.path.join(dict_dir, "generic_terms.csv"),
    index=False,
    encoding="utf-8-sig"
)

pd.DataFrame({"term": sorted(implementation_action_terms)}).to_csv(
    os.path.join(dict_dir, "implementation_action_terms.csv"),
    index=False,
    encoding="utf-8-sig"
)

pd.DataFrame({"term": sorted(implementation_domain_terms)}).to_csv(
    os.path.join(dict_dir, "implementation_domain_terms.csv"),
    index=False,
    encoding="utf-8-sig"
)

pd.DataFrame({"term": sorted(implementation_effect_terms)}).to_csv(
    os.path.join(dict_dir, "implementation_effect_terms.csv"),
    index=False,
    encoding="utf-8-sig"
)

pd.DataFrame({"term": sorted(risk_source_terms)}).to_csv(
    os.path.join(dict_dir, "risk_source_terms.csv"),
    index=False,
    encoding="utf-8-sig"
)

pd.DataFrame({"term": sorted(risk_impact_terms)}).to_csv(
    os.path.join(dict_dir, "risk_impact_terms.csv"),
    index=False,
    encoding="utf-8-sig"
)

pd.DataFrame(all_expansion_records).to_csv(
    os.path.join(dict_dir, "word2vec_expansion_records.csv"),
    index=False,
    encoding="utf-8-sig"
)

print(f"AI dictionary size: {len(ai_dictionary):,}")
print(f"Dictionary files saved to: {dict_dir}")


# ============================================================
# 9. Rule-based NLP classification
# ============================================================

print("\n[7/9] Classifying AI disclosure sentences...")

def classify_sentence(row):
    """
    Classify one sentence using:
    - AI dictionary matches
    - current sentence + previous/next sentence context
    - rule-based scores derived from the definitions

    Final labels:
        generic_ai_disclosure
        substantive_ai_implementation
        substantive_ai_risk_governance
        "" for non-AI candidate
    """

    current_text = safe_text(row[TEXT_COL]).lower()
    context_text = safe_text(row["_context_text"]).lower()

    current_tokens = row["_tokens"]
    context_tokens = row["_context_tokens"]

    # --------------------------------------------------------
    # AI candidate detection
    # --------------------------------------------------------

    current_ai_matches = token_match(current_tokens, ai_dictionary)
    context_ai_matches = token_match(context_tokens, ai_dictionary)

    current_raw_ai_matches = raw_phrase_match(current_text, AI_RAW_PHRASES)
    context_raw_ai_matches = raw_phrase_match(context_text, AI_RAW_PHRASES)

    ai_matches = sorted(set(
        current_ai_matches +
        context_ai_matches +
        current_raw_ai_matches +
        context_raw_ai_matches
    ))

    is_ai_candidate = len(ai_matches) > 0

    if not is_ai_candidate:
        return pd.Series({
            "nlp_is_ai_candidate": False,
            "nlp_top_level_category": "",
            "nlp_sub_category": "",
            "nlp_final_label": "",
            "nlp_ai_matched_terms": "",
            "nlp_generic_matched_terms": "",
            "nlp_implementation_matched_terms": "",
            "nlp_risk_matched_terms": "",
            "nlp_generic_score": 0.0,
            "nlp_implementation_score": 0.0,
            "nlp_risk_score": 0.0
        })

    # --------------------------------------------------------
    # Match category terms
    # --------------------------------------------------------

    generic_matches = token_match(context_tokens, generic_terms)

    impl_action_matches = token_match(context_tokens, implementation_action_terms)
    impl_domain_matches = token_match(context_tokens, implementation_domain_terms)
    impl_effect_matches = token_match(context_tokens, implementation_effect_terms)

    risk_source_matches = token_match(context_tokens, risk_source_terms)
    risk_impact_matches = token_match(context_tokens, risk_impact_terms)
    generic_risk_matches = token_match(context_tokens, generic_risk_terms)

    implementation_matches = sorted(set(
        impl_action_matches +
        impl_domain_matches +
        impl_effect_matches
    ))

    risk_matches = sorted(set(
        risk_source_matches +
        risk_impact_matches +
        generic_risk_matches
    ))

    # --------------------------------------------------------
    # Pattern signals: implementation
    # --------------------------------------------------------

    implementation_score = 0.0

    has_impl_action = len(impl_action_matches) > 0
    has_impl_domain = len(impl_domain_matches) > 0
    has_impl_effect = len(impl_effect_matches) > 0

    # AI-powered / AI-enabled / AI-driven products or services.
    product_provider_pattern = re.search(
        r"\b(ai|artificial intelligence|machine learning|deep learning)\s+"
        r"(powered|enabled|driven|based)\s+"
        r"(product|service|platform|solution|tool|system|software|application)\b",
        context_text
    )

    # The firm uses/applies/deploys AI to do something concrete.
    ai_use_pattern = re.search(
        r"\b(use|uses|used|using|utilize|utilizes|apply|applies|applied|employ|employs|"
        r"deploy|deploys|deployed|implement|implements|implemented|integrate|integrates|"
        r"integrated|embed|embeds|embedded|leverage|leverages|leveraged)\b"
        r".{0,80}"
        r"\b(ai|artificial intelligence|machine learning|deep learning|algorithm|predictive model)\b",
        context_text
    ) or re.search(
        r"\b(ai|artificial intelligence|machine learning|deep learning|algorithm|predictive model)\b"
        r".{0,80}"
        r"\b(optimize|automate|forecast|predict|recommend|detect|simulate|streamline|enhance|improve|reduce)\b",
        context_text
    )

    # Concrete business functions.
    business_function_pattern = re.search(
        r"\b(pricing|inventory|demand forecasting|replenishment|supply chain|customer service|"
        r"workflow|internal process|product development|r&d|research and development|"
        r"analytics platform|fraud detection|recommendation|revenue management)\b",
        context_text
    )

    if has_impl_action and (has_impl_domain or has_impl_effect):
        implementation_score += 2.0

    if product_provider_pattern:
        implementation_score += 2.5

    if ai_use_pattern and (has_impl_domain or has_impl_effect or business_function_pattern):
        implementation_score += 2.0

    if business_function_pattern:
        implementation_score += 1.0

    # Light dictionary score, capped to avoid excessive influence.
    implementation_score += min(len(implementation_matches) * 0.25, 1.5)

    # --------------------------------------------------------
    # Pattern signals: risk/governance
    # --------------------------------------------------------

    risk_score = 0.0

    has_specific_risk_source = len(risk_source_matches) > 0
    has_risk_impact = len(risk_impact_matches) > 0
    has_generic_risk_only = len(generic_risk_matches) > 0 and not has_specific_risk_source

    ai_risk_pattern = re.search(
        r"\b(ai|artificial intelligence|machine learning|algorithmic|automated)\b"
        r".{0,120}"
        r"\b(regulation|regulatory|compliance|privacy|cybersecurity|security|bias|ethical|"
        r"ethics|liability|governance|model failure|third party|vendor|reputation|"
        r"data breach|security breach)\b",
        context_text
    ) or re.search(
        r"\b(regulation|regulatory|compliance|privacy|cybersecurity|security|bias|ethical|"
        r"ethics|liability|governance|model failure|third party|vendor|reputation|"
        r"data breach|security breach)\b"
        r".{0,120}"
        r"\b(ai|artificial intelligence|machine learning|algorithmic|automated)\b",
        context_text
    )

    if has_specific_risk_source:
        risk_score += 2.0

    if has_specific_risk_source and has_risk_impact:
        risk_score += 1.5

    if ai_risk_pattern:
        risk_score += 2.0

    # Generic "AI may introduce risks" should not automatically become substantive.
    if has_generic_risk_only and not has_specific_risk_source:
        risk_score += 0.5

    risk_score += min(len(risk_source_matches) * 0.25, 1.0)

    # --------------------------------------------------------
    # Pattern signals: generic AI disclosure
    # --------------------------------------------------------

    generic_score = 0.0

    generic_pattern = re.search(
        r"\b(transform|reshape|revolutionize|future|potential|opportunit|forefront|"
        r"explore|embrace|committed|commitment|innovation|innovative|strategic|strategy)\b",
        context_text
    )

    vague_ai_pattern = re.search(
        r"\b(ai|artificial intelligence|machine learning)\b"
        r".{0,100}"
        r"\b(opportunit|potential|future|explore|embrace|forefront|innovation|strategy|"
        r"transformation|digitalization|capabilities)\b",
        context_text
    )

    if generic_pattern:
        generic_score += 1.0

    if vague_ai_pattern:
        generic_score += 1.5

    generic_score += min(len(generic_matches) * 0.25, 1.5)

    # Generic risk reference without concrete risk source is generic.
    if has_generic_risk_only and not has_specific_risk_source:
        generic_score += 1.5

    # If it is AI-related but no substantive mechanism is found,
    # classify as generic by default.
    if implementation_score < IMPLEMENTATION_THRESHOLD and risk_score < RISK_THRESHOLD:
        generic_score = max(generic_score, 1.0)

    # --------------------------------------------------------
    # Final label decision
    # --------------------------------------------------------

    if risk_score >= RISK_THRESHOLD and risk_score >= implementation_score:
        top_level = "Substantive AI disclosure"
        sub_category = "Substantive AI risk/governance"
        final_label = "substantive_ai_risk_governance"

    elif implementation_score >= IMPLEMENTATION_THRESHOLD:
        top_level = "Substantive AI disclosure"
        sub_category = "Substantive AI implementation"
        final_label = "substantive_ai_implementation"

    else:
        top_level = "Generic AI disclosure"
        sub_category = ""
        final_label = "generic_ai_disclosure"

    return pd.Series({
        "nlp_is_ai_candidate": True,
        "nlp_top_level_category": top_level,
        "nlp_sub_category": sub_category,
        "nlp_final_label": final_label,
        "nlp_ai_matched_terms": join_unique(ai_matches),
        "nlp_generic_matched_terms": join_unique(generic_matches),
        "nlp_implementation_matched_terms": join_unique(implementation_matches),
        "nlp_risk_matched_terms": join_unique(risk_matches),
        "nlp_generic_score": round(generic_score, 4),
        "nlp_implementation_score": round(implementation_score, 4),
        "nlp_risk_score": round(risk_score, 4)
    })


classification_results = df.progress_apply(classify_sentence, axis=1)
df = pd.concat([df, classification_results], axis=1)


# ============================================================
# 10. Save sentence-level results
# ============================================================

print("\n[8/9] Saving sentence-level outputs...")

# Output columns.
preferred_cols = [
    "cik", "gvkey", "ticker", "company_name", "filing_date",
    "fiscal_year", "accession_number", "section_name",
    "sentence_id", "sentence_order",
    "sentence_raw", "sentence_clean",
    "sentence_word_count",
    "mdna_total_word_count",
    "mdna_total_sentence_count",
    "nlp_is_ai_candidate",
    "nlp_top_level_category",
    "nlp_sub_category",
    "nlp_final_label",
    "nlp_ai_matched_terms",
    "nlp_generic_matched_terms",
    "nlp_implementation_matched_terms",
    "nlp_risk_matched_terms",
    "nlp_generic_score",
    "nlp_implementation_score",
    "nlp_risk_score"
]

output_cols = [c for c in preferred_cols if c in df.columns]

all_sentence_path = os.path.join(OUTPUT_DIR, "sentence_level_nlp_all_sentences.csv")
ai_sentence_path = os.path.join(OUTPUT_DIR, "sentence_level_nlp_ai_candidates_only.csv")

df[output_cols].to_csv(all_sentence_path, index=False, encoding="utf-8-sig")
df.loc[df["nlp_is_ai_candidate"], output_cols].to_csv(ai_sentence_path, index=False, encoding="utf-8-sig")

print(f"Saved all sentence-level results to: {all_sentence_path}")
print(f"Saved AI candidate sentence results to: {ai_sentence_path}")


# ============================================================
# 11. Firm-year summary
# ============================================================

print("\n[9/9] Building firm-year summary...")

possible_summary_keys = [
    "cik", "gvkey", "ticker", "company_name", "fiscal_year", "accession_number"
]
summary_keys = [c for c in possible_summary_keys if c in df.columns]

if not summary_keys:
    raise ValueError("No firm-year grouping columns found. Please check your data columns.")

# Denominators.
if "mdna_total_sentence_count" not in df.columns:
    df["mdna_total_sentence_count"] = df.groupby(summary_keys)[TEXT_COL].transform("count")

if "mdna_total_word_count" not in df.columns:
    df["_calc_word_count"] = df[TEXT_COL].apply(lambda x: len(preprocess_text(x)))
    df["mdna_total_word_count"] = df.groupby(summary_keys)["_calc_word_count"].transform("sum")

base_summary = df.groupby(summary_keys).agg(
    mdna_total_sentence_count=("mdna_total_sentence_count", "first"),
    mdna_total_word_count=("mdna_total_word_count", "first"),
    n_kept_sentences=(TEXT_COL, "count"),
    n_ai_candidate_sentences=("nlp_is_ai_candidate", "sum")
).reset_index()

cat_counts = (
    df[df["nlp_is_ai_candidate"]]
    .groupby(summary_keys + ["nlp_final_label"])
    .size()
    .reset_index(name="n")
    .pivot_table(
        index=summary_keys,
        columns="nlp_final_label",
        values="n",
        fill_value=0
    )
    .reset_index()
)

summary = base_summary.merge(cat_counts, on=summary_keys, how="left")

for col in [
    "generic_ai_disclosure",
    "substantive_ai_implementation",
    "substantive_ai_risk_governance"
]:
    if col not in summary.columns:
        summary[col] = 0
    summary[col] = summary[col].fillna(0).astype(int)

summary["n_generic_ai_disclosure_sentences"] = summary["generic_ai_disclosure"]
summary["n_substantive_ai_implementation_sentences"] = summary["substantive_ai_implementation"]
summary["n_substantive_ai_risk_governance_sentences"] = summary["substantive_ai_risk_governance"]

summary["n_substantive_ai_disclosure_sentences"] = (
    summary["n_substantive_ai_implementation_sentences"] +
    summary["n_substantive_ai_risk_governance_sentences"]
)

# Sentence-based intensities.
summary["ai_candidate_sentence_intensity"] = (
    summary["n_ai_candidate_sentences"] / summary["mdna_total_sentence_count"]
)

summary["generic_ai_disclosure_sentence_intensity"] = (
    summary["n_generic_ai_disclosure_sentences"] / summary["mdna_total_sentence_count"]
)

summary["substantive_ai_disclosure_sentence_intensity"] = (
    summary["n_substantive_ai_disclosure_sentences"] / summary["mdna_total_sentence_count"]
)

summary["substantive_ai_implementation_sentence_intensity"] = (
    summary["n_substantive_ai_implementation_sentences"] / summary["mdna_total_sentence_count"]
)

summary["substantive_ai_risk_governance_sentence_intensity"] = (
    summary["n_substantive_ai_risk_governance_sentences"] / summary["mdna_total_sentence_count"]
)

# Word-count adjusted versions.
summary["ai_candidate_per_10000_words"] = (
    summary["n_ai_candidate_sentences"] / summary["mdna_total_word_count"] * 10000
)

summary["generic_ai_disclosure_per_10000_words"] = (
    summary["n_generic_ai_disclosure_sentences"] / summary["mdna_total_word_count"] * 10000
)

summary["substantive_ai_disclosure_per_10000_words"] = (
    summary["n_substantive_ai_disclosure_sentences"] / summary["mdna_total_word_count"] * 10000
)

summary["substantive_ai_implementation_per_10000_words"] = (
    summary["n_substantive_ai_implementation_sentences"] / summary["mdna_total_word_count"] * 10000
)

summary["substantive_ai_risk_governance_per_10000_words"] = (
    summary["n_substantive_ai_risk_governance_sentences"] / summary["mdna_total_word_count"] * 10000
)

# Drop intermediate pivot columns.
summary = summary.drop(
    columns=[
        "generic_ai_disclosure",
        "substantive_ai_implementation",
        "substantive_ai_risk_governance"
    ],
    errors="ignore"
)

summary_path = os.path.join(OUTPUT_DIR, "firm_year_ai_disclosure_summary.csv")
summary.to_csv(summary_path, index=False, encoding="utf-8-sig")

print(f"Saved firm-year summary to: {summary_path}")

print("\nDone.")
print("Main outputs:")
print("1.", all_sentence_path)
print("2.", ai_sentence_path)
print("3.", summary_path)
print("4.", dict_dir)
