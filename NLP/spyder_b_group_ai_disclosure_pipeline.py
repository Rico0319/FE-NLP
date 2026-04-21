import os
import json
import math
import time
import hashlib
import re
from typing import List, Literal, Optional

import numpy as np
import pandas as pd
from tqdm import tqdm
from pydantic import BaseModel
from openai import OpenAI

# ============================================================
# B组：MD&A sentence-level AI disclosure classification pipeline
#
# 适配文件：mdna_sentence_master.jsonl
# 运行环境：Spyder / Python 3.10+
#
# 安装建议：
# pip install openai pandas numpy tqdm pydantic python-dotenv pyarrow
#
# 说明：
# 1) 先做 keyword screening（高召回）
# 2) 再用 OpenAI API + definition-based prompt 做 sentence-level 分类
# 3) 输出 sentence-level 审计文件 + firm-year regression-ready measures
#
# 最终研究类目只有三类：
#   - generic_ai_disclosure
#   - substantive_ai_implementation
#   - substantive_ai_risk_governance
#
# “not_ai_related” 只是流水线内部状态，用来过滤误筛 candidate，
# 不是最终研究输出类目。
# ============================================================

# -----------------------------
# 0. PATHS / SETTINGS
# -----------------------------
INPUT_PATH = r"/Users/jiazuo/Desktop/nlppp/mdna_sentence_master.jsonl"   # 改成你的实际路径
OUTPUT_DIR = r"b_group_outputs"
CACHE_PATH = os.path.join(OUTPUT_DIR, "sentence_classification_cache.jsonl")
SENTENCE_OUTPUT_CSV = os.path.join(OUTPUT_DIR, "sentence_level_with_ai_labels.csv")
SENTENCE_OUTPUT_PARQUET = os.path.join(OUTPUT_DIR, "sentence_level_with_ai_labels.parquet")
FIRMYEAR_OUTPUT_CSV = os.path.join(OUTPUT_DIR, "firm_year_ai_disclosure_measures.csv")
SUMMARY_OUTPUT_CSV = os.path.join(OUTPUT_DIR, "run_summary.csv")

# OpenAI model: 这里默认用 gpt-4o-mini 控制成本；你也可以改成账户里支持 structured output 的更强模型
MODEL_NAME = os.getenv("gpt-5.2")
SLEEP_SEC = 0.0              # 若担心 rate limit，可设成 0.1~0.5
MAX_CONTEXT_WORDS = 800      # 参考 SSRN 论文：around keyword, ~800-word window
MAX_TEST_ROWS = None         # 调试时可改成 2000；正式跑设为 None
RETRY_TIMES = 3
ONLY_CLASSIFY_CANDIDATES = True

# share 口径：这里统一用“某类句子数 / 全部 AI 披露句子数（generic + substantive）”
# 这样：generic_ai_share + substantive_ai_share = 1
# 且 substantive_impl_share + substantive_risk_share = substantive_ai_share
SHARE_DENOMINATOR = "all_ai_sentences"

os.makedirs(OUTPUT_DIR, exist_ok=True)


# -----------------------------
# 1. AI seed keyword screen
# -----------------------------
# 说明：
# - 你的 definition 文件明确说：不能只靠关键词直接判 generic/substantive。
# - 所以这里的 keyword list 只用于“candidate screening”，高召回即可。
# - 最终 generic / implementation / risk_governance 仍由 API + prompt 决定。
HIGH_PRECISION_KEYWORDS = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "computer vision",
    "natural language processing",
    "large language model",
    "large language models",
    "llm",
    "llms",
    "generative ai",
    "genai",
    "a.i."
]

EXPANDED_KEYWORDS = [
    "business intelligence",
    "big data",
    "data science",
    "ai/ml",
    "data mining",
    "data scientist",
    "chatbot",
    "image recognition",
    "object recognition",
    "machine translation",
    "support vector machine",
    "classification algorithm",
    "classification algorithms",
    "supervised learning",
    "computational linguistics",
    "clustering algorithm",
    "clustering algorithms",
    "recommender system",
    "recommender systems",
    "dimensionality reduction",
    "information extraction",
    "kernel method",
    "kernel methods",
    "unsupervised learning",
    "predictive model",
    "predictive models",
    "algorithmic pricing",
    "autonomous system",
    "autonomous systems"
]

SEED_KEYWORDS = HIGH_PRECISION_KEYWORDS + EXPANDED_KEYWORDS


SEED_REGEX = re.compile("|".join(SEED_KEYWORDS), flags=re.IGNORECASE)


# -----------------------------
# 2. Definition-based prompt
# -----------------------------
# 这里把你 Definition 文件中的核心判别标准完整揉进 prompt：
# - substantive: 明确回答 AI 在哪里被用、做什么、影响什么结果/风险
# - generic: 只提 AI，但空泛、愿景化、宣传化、没有可验证 business mechanism
# - risk: 只有当风险来源/机制/后果被明确映射出来，才算 substantive risk/governance
# - implementation: 你要求把 Product Development / AI Product Provider /
#   Pricing Optimization / Inventory Management / Operational Efficiency 合并成一类

SYSTEM_PROMPT = r'''
You are a careful financial-disclosure research assistant.
You are classifying ONE focal sentence from a firm's MD&A using the focal sentence plus its surrounding MD&A context.

Research objective:
Classify AI disclosure into the following research labels:
1) generic_ai_disclosure
2) substantive_ai_implementation
3) substantive_ai_risk_governance
4) not_ai_related   (internal pipeline state only; not a research disclosure class)

Important:
- The final label must be assigned to the focal sentence, not to neighboring sentences.
- You may use surrounding context only to interpret the focal sentence.
- Be conservative.
- Do NOT infer applications, governance, or risks that are not explicitly stated.
- A sentence mentioning technology trends, strategy, innovation image, or aspirations is NOT substantive unless the text explicitly maps AI to a concrete business function or risk mechanism.

Full classification standard:

A. Definition of substantive AI disclosure
Substantive AI disclosure contains clear, specific, and identifiable business content regarding the firm's use of artificial intelligence.
It should allow an outside reader to understand how AI is being used in the firm and how it relates to products, services, operating processes, risk management, or expected future performance.
The defining feature is not merely the appearance of the term AI. The key question is whether the disclosure answers at least one of these:
- where AI is being applied;
- what objective the firm seeks to achieve through AI;
- how AI is expected to affect revenue, cost, efficiency, innovation, or risk;
- through which channel AI-related risks may arise.
Substantive disclosure is operationally grounded and has identifiable economic meaning.

B. Definition of generic AI disclosure
Generic AI disclosure mentions AI but remains broad, vague, symbolic, aspirational, strategic, or promotional.
It does NOT specify a concrete use case, business mechanism, risk source, or otherwise verifiable content.
A reader may learn that the firm referenced AI, but cannot reliably infer whether the firm is actually using AI, in which business function AI is applied, whether AI is intended to increase revenue or reduce costs, or whether the text reflects real deployment rather than rhetoric.

C. Fundamental distinction
Substantive AI disclosure explains what AI actually does within the firm.
Generic AI disclosure merely indicates that the firm mentions AI.

D. Four practical distinction rules
1) Specificity:
   - substantive = concrete application or risk mechanism
   - generic = investing in / exploring / embracing AI with no concrete mapping
2) Business relevance:
   - substantive = directly linked to production, sales, service delivery, workflow, cost structure, or firm risk
   - generic = broad vision, industry trends, strategic positioning
3) Verifiability:
   - substantive = clear object, action, intended effect
   - generic = lacks enough detail to verify economic meaning
4) Information content:
   - substantive = likely reflects real implementation capability or risk exposure
   - generic = weak informational value

E. Substantive implementation category (collapsed category in this project)
Any of the following should be mapped to substantive_ai_implementation:
- Product Development: AI used in design, testing, improvement, or development of products/services
- AI Product Provider: firm offers AI-based products/services/platforms to customers
- Pricing Optimization: AI used in pricing, dynamic pricing, promotional pricing, revenue management
- Inventory Management: AI used in demand forecasting, replenishment planning, inventory optimization, supply chain coordination
- Operational Efficiency: AI used to automate tasks, improve internal efficiency, reduce labor costs, streamline workflows, enhance daily operations

Implementation requires explicit operational/business mapping.
Examples of implementation-type evidence:
- AI used to improve drug screening or product performance simulation
- AI embedded in a platform sold to clients
- AI models used to adjust prices based on real-time data
- AI used to forecast demand and optimize inventory turnover
- AI used to automate customer service or internal approval workflows

F. Substantive risk/governance category
Map to substantive_ai_risk_governance only when the sentence explicitly describes the source and/or consequences of AI-related risk, governance burden, or control issue.
Common risk channels include:
- regulatory risk
- operational risk
- competitive risk
- cybersecurity risk
- ethical risk
- third-party dependence risk
Examples:
- new AI regulation may increase compliance cost or require product modification
- failures in third-party AI models may hurt platform stability or reputation

Important risk rule:
A sentence like "AI may create risks and uncertainties" is still GENERIC unless the text clearly specifies the risk source/mechanism/consequence.

G. Generic disclosure examples
These are generic_ai_disclosure when they mention AI but do not map AI to a concrete function or risk mechanism:
- purely conceptual statements
- strategic or visionary rhetoric
- vague bundling with other buzzwords (AI, big data, digitalization, intelligent analytics)
- generic risk references without business mapping

H. Sentence-level labeling rule
Because this is sentence-level classification, do not label the focal sentence as substantive just because nearby sentences are substantive.
However, you may use nearby text to resolve pronouns or omitted objects.
Only classify as substantive when the focal sentence itself, interpreted with nearby context, clearly communicates a concrete AI business function or risk/governance mechanism.

I. Output rules
Return exactly one final_label from:
- not_ai_related
- generic_ai_disclosure
- substantive_ai_implementation
- substantive_ai_risk_governance

Also return probabilities for the three research classes:
- generic_probability
- substantive_implementation_probability
- substantive_risk_governance_probability
Each probability must be between 0 and 1.
They do not need to sum to 1 exactly, but they should reflect relative confidence.

Return implementation_subtypes only when final_label is substantive_ai_implementation.
Allowed implementation subtypes:
- product_development
- ai_product_provider
- pricing_optimization
- inventory_management
- operational_efficiency

Return risk_subtypes only when final_label is substantive_ai_risk_governance.
Allowed risk subtypes:
- regulatory_risk
- operational_risk
- competitive_risk
- cybersecurity_risk
- ethical_risk
- third_party_dependence_risk

Return a short rationale grounded only in the provided text.
'''


# -----------------------------
# 3. Structured output schema
# -----------------------------
class SentenceClassification(BaseModel):
    final_label: Literal[
        "not_ai_related",
        "generic_ai_disclosure",
        "substantive_ai_implementation",
        "substantive_ai_risk_governance",
    ]
    generic_probability: float
    substantive_implementation_probability: float
    substantive_risk_governance_probability: float
    implementation_subtypes: List[
        Literal[
            "product_development",
            "ai_product_provider",
            "pricing_optimization",
            "inventory_management",
            "operational_efficiency",
        ]
    ] = []
    risk_subtypes: List[
        Literal[
            "regulatory_risk",
            "operational_risk",
            "competitive_risk",
            "cybersecurity_risk",
            "ethical_risk",
            "third_party_dependence_risk",
        ]
    ] = []
    rationale: str


# -----------------------------
# 4. Helpers
# -----------------------------
def safe_text(x) -> str:
    if pd.isna(x):
        return ""
    return str(x)


def normalize_bool(x) -> bool:
    if isinstance(x, bool):
        return x
    if pd.isna(x):
        return False
    s = str(x).strip().lower()
    return s in {"1", "true", "t", "yes", "y"}


def sentence_word_count_from_text(text: str) -> int:
    text = safe_text(text).strip()
    if not text:
        return 0
    return len(text.split())


def parse_ai_keyword_terms(x):
    if isinstance(x, list):
        return x
    if pd.isna(x):
        return []
    s = str(x).strip()
    if not s or s == "[]":
        return []
    try:
        obj = json.loads(s.replace("'", '"'))
        if isinstance(obj, list):
            return obj
        return [str(obj)]
    except Exception:
        return [s]


def safe_div(num, den):
    if isinstance(num, pd.Series) or isinstance(den, pd.Series):
        out = np.where(np.asarray(den) > 0, np.asarray(num) / np.asarray(den), 0.0)
        return out
    return num / den if den and den > 0 else 0.0


def clamp01(x):
    try:
        x = float(x)
    except Exception:
        return 0.0
    return min(1.0, max(0.0, x))


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def pick_text_column(df: pd.DataFrame) -> str:
    if "sentence_clean" in df.columns:
        return "sentence_clean"
    if "sentence_raw" in df.columns:
        return "sentence_raw"
    raise ValueError("Input file must contain sentence_clean or sentence_raw.")


def make_seed_candidate_flags(df: pd.DataFrame, text_col: str) -> pd.DataFrame:
    df = df.copy()
    text_series = df[text_col].fillna("").astype(str)
    df["seed_keyword_match"] = text_series.str.contains(SEED_REGEX, regex=True)

    if "ai_candidate_flag" in df.columns:
        api_flag = df["ai_candidate_flag"].apply(normalize_bool)
    else:
        api_flag = pd.Series(False, index=df.index)

    if "ai_keyword_matched_terms" in df.columns:
        matched_terms_nonempty = df["ai_keyword_matched_terms"].apply(lambda x: len(parse_ai_keyword_terms(x)) > 0)
    else:
        matched_terms_nonempty = pd.Series(False, index=df.index)

    if "keep_sentence_flag" in df.columns:
        keep_flag = df["keep_sentence_flag"].apply(normalize_bool)
    else:
        keep_flag = pd.Series(True, index=df.index)

    df["keep_sentence_flag_bool"] = keep_flag
    df["a_group_ai_candidate_flag_bool"] = api_flag
    df["matched_terms_nonempty"] = matched_terms_nonempty

    # 最终 candidate：优先保留 A 组结果，同时加上我们自己的 keyword screening
    df["ai_candidate_final"] = (
        df["keep_sentence_flag_bool"]
        & (
            df["a_group_ai_candidate_flag_bool"]
            | df["matched_terms_nonempty"]
            | df["seed_keyword_match"]
        )
    )
    return df


def ensure_sentence_order(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "sentence_order" not in df.columns:
        df["sentence_order"] = np.arange(len(df))
    df["sentence_order_num"] = pd.to_numeric(df["sentence_order"], errors="coerce")
    nan_mask = df["sentence_order_num"].isna()
    if nan_mask.any():
        df.loc[nan_mask, "sentence_order_num"] = np.arange(nan_mask.sum()) + 10_000_000
    return df


def build_group_keys(df: pd.DataFrame) -> List[str]:
    preferred = [
        "cik",
        "gvkey",
        "ticker",
        "company_name",
        "filing_date",
        "fiscal_year",
        "accession_number",
        "section_name",
    ]
    keys = [c for c in preferred if c in df.columns]
    if not keys:
        raise ValueError("Could not find enough identifier columns to build document groups.")
    return keys


def get_sentence_word_count_row(row, text_col: str) -> int:
    if "sentence_word_count" in row and not pd.isna(row["sentence_word_count"]):
        try:
            return int(row["sentence_word_count"])
        except Exception:
            pass
    return sentence_word_count_from_text(row[text_col])


def build_context_window(group_df: pd.DataFrame, row_idx, text_col: str, max_words: int = 800) -> str:
    g = group_df.sort_values("sentence_order_num").copy()
    positions = list(g.index)
    try:
        focal_pos = positions.index(row_idx)
    except ValueError:
        focal_pos = 0

    selected_positions = [focal_pos]
    total_words = get_sentence_word_count_row(g.loc[positions[focal_pos]], text_col)

    left = focal_pos - 1
    right = focal_pos + 1

    # 左右交替扩展，直到接近 max_words
    while (left >= 0 or right < len(positions)) and total_words < max_words:
        added = False

        if left >= 0:
            row = g.loc[positions[left]]
            w = get_sentence_word_count_row(row, text_col)
            if total_words + w <= max_words or (right >= len(positions) and not added):
                selected_positions.insert(0, left)
                total_words += w
                added = True
            left -= 1

        if right < len(positions) and total_words < max_words:
            row = g.loc[positions[right]]
            w = get_sentence_word_count_row(row, text_col)
            if total_words + w <= max_words or (left < 0 and not added):
                selected_positions.append(right)
                total_words += w
                added = True
            right += 1

        if not added and left < 0 and right >= len(positions):
            break

    context_rows = g.iloc[selected_positions]
    context_text = " ".join(context_rows[text_col].fillna("").astype(str).tolist())
    return re.sub(r"\s+", " ", context_text).strip()


def make_user_prompt(focal_sentence: str, context_text: str, sentence_id: str, matched_terms: List[str]) -> str:
    matched_terms_display = ", ".join(matched_terms) if matched_terms else "None"
    return f"""
Classify the focal MD&A sentence below.

Sentence ID: {sentence_id}
Seed matched terms: {matched_terms_display}

FOCAL SENTENCE:
{focal_sentence}

SURROUNDING MD&A CONTEXT (use only for interpretation, not for labeling neighboring sentences):
{context_text}

Task reminder:
- Label the focal sentence only.
- Use only explicitly stated information.
- Do not infer missing applications or risk channels.
- Return one final label plus probabilities and short rationale.
""".strip()


def probability_for_final_label(result: SentenceClassification) -> float:
    if result.final_label == "generic_ai_disclosure":
        return clamp01(result.generic_probability)
    if result.final_label == "substantive_ai_implementation":
        return clamp01(result.substantive_implementation_probability)
    if result.final_label == "substantive_ai_risk_governance":
        return clamp01(result.substantive_risk_governance_probability)
    # internal not_ai_related state: 用 1 - max(research class probabilities)
    return clamp01(
        1.0 - max(
            clamp01(result.generic_probability),
            clamp01(result.substantive_implementation_probability),
            clamp01(result.substantive_risk_governance_probability),
        )
    )


# -----------------------------
# 5. OpenAI call
# -----------------------------
client = OpenAI()


def classify_one_sentence(focal_sentence: str, context_text: str, sentence_id: str, matched_terms: List[str]):
    user_prompt = make_user_prompt(
        focal_sentence=focal_sentence,
        context_text=context_text,
        sentence_id=sentence_id,
        matched_terms=matched_terms,
    )

    last_err = None
    for attempt in range(RETRY_TIMES):
        try:
            response = client.responses.parse(
                model=MODEL_NAME,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                text_format=SentenceClassification,
            )
            parsed = response.output_parsed
            return {
                "final_label": parsed.final_label,
                "generic_probability": clamp01(parsed.generic_probability),
                "substantive_implementation_probability": clamp01(parsed.substantive_implementation_probability),
                "substantive_risk_governance_probability": clamp01(parsed.substantive_risk_governance_probability),
                "implementation_subtypes": parsed.implementation_subtypes,
                "risk_subtypes": parsed.risk_subtypes,
                "rationale": parsed.rationale,
                "final_confidence": probability_for_final_label(parsed),
                "api_model": MODEL_NAME,
                "api_status": "ok",
            }
        except Exception as e:
            last_err = str(e)
            wait_s = min(2 ** attempt, 8)
            time.sleep(wait_s)

    return {
        "final_label": "not_ai_related",
        "generic_probability": 0.0,
        "substantive_implementation_probability": 0.0,
        "substantive_risk_governance_probability": 0.0,
        "implementation_subtypes": [],
        "risk_subtypes": [],
        "rationale": f"API_ERROR: {last_err}",
        "final_confidence": 0.0,
        "api_model": MODEL_NAME,
        "api_status": "error",
    }


# -----------------------------
# 6. Cache
# -----------------------------
def load_cache(cache_path: str) -> dict:
    if not os.path.exists(cache_path):
        return {}
    cache = {}
    with open(cache_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                cache[obj["cache_key"]] = obj
            except Exception:
                continue
    return cache


def append_cache_record(cache_path: str, record: dict):
    with open(cache_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# -----------------------------
# 7. Main pipeline
# -----------------------------
def run_pipeline():
    print("[1/7] Reading input file...")
    df = pd.read_json(INPUT_PATH, lines=True)

    if MAX_TEST_ROWS is not None:
        df = df.head(MAX_TEST_ROWS).copy()

    text_col = pick_text_column(df)
    df = ensure_sentence_order(df)
    df = make_seed_candidate_flags(df, text_col=text_col)

    # 补 sentence_word_count
    if "sentence_word_count" not in df.columns:
        df["sentence_word_count"] = df[text_col].fillna("").astype(str).map(sentence_word_count_from_text)
    else:
        swc = pd.to_numeric(df["sentence_word_count"], errors="coerce")
        missing = swc.isna()
        if missing.any():
            swc.loc[missing] = df.loc[missing, text_col].fillna("").astype(str).map(sentence_word_count_from_text)
        df["sentence_word_count"] = swc.astype(int)

    if "sentence_id" not in df.columns:
        df["sentence_id"] = [f"row_{i}" for i in range(len(df))]

    group_keys = build_group_keys(df)

    # QC variable later: 统计被 A 组去掉的 duplicate / bad sentence
    df["dropped_by_keep_flag"] = ~df["keep_sentence_flag_bool"]

    print("[2/7] Building document groups...")
    grouped = {
        k: g.sort_values("sentence_order_num").copy()
        for k, g in df.groupby(group_keys, dropna=False, sort=False)
    }

    if ONLY_CLASSIFY_CANDIDATES:
        target_mask = df["ai_candidate_final"]
    else:
        target_mask = df["keep_sentence_flag_bool"]

    target_df = df.loc[target_mask].copy()
    print(f"Total rows: {len(df):,}")
    print(f"Rows kept for classification: {len(target_df):,}")

    print("[3/7] Loading cache...")
    cache = load_cache(CACHE_PATH)

    results = []
    print("[4/7] Classifying candidate sentences with OpenAI API...")
    for idx, row in tqdm(target_df.iterrows(), total=len(target_df)):
        gkey = tuple(row[k] for k in group_keys)
        gdf = grouped[gkey]

        focal_sentence = safe_text(row[text_col]).strip()
        context_text = build_context_window(gdf, idx, text_col=text_col, max_words=MAX_CONTEXT_WORDS)
        matched_terms = parse_ai_keyword_terms(row.get("ai_keyword_matched_terms", []))

        cache_key_payload = {
            "sentence_id": safe_text(row["sentence_id"]),
            "focal_sentence": focal_sentence,
            "context_hash": stable_hash(context_text),
            "model": MODEL_NAME,
        }
        cache_key = stable_hash(json.dumps(cache_key_payload, ensure_ascii=False, sort_keys=True))

        if cache_key in cache:
            rec = cache[cache_key].copy()
            rec["from_cache"] = True
        else:
            rec = classify_one_sentence(
                focal_sentence=focal_sentence,
                context_text=context_text,
                sentence_id=safe_text(row["sentence_id"]),
                matched_terms=matched_terms,
            )
            rec["cache_key"] = cache_key
            rec["sentence_id"] = safe_text(row["sentence_id"])
            append_cache_record(CACHE_PATH, rec)
            cache[cache_key] = rec
            rec["from_cache"] = False
            if SLEEP_SEC > 0:
                time.sleep(SLEEP_SEC)

        rec["row_index"] = idx
        results.append(rec)

    print("[5/7] Merging sentence-level results...")
    res_df = pd.DataFrame(results)
    if len(res_df) == 0:
        # 没有 candidate，就建空表并直接输出 0 measures
        res_df = pd.DataFrame(columns=[
            "row_index",
            "sentence_id",
            "final_label",
            "generic_probability",
            "substantive_implementation_probability",
            "substantive_risk_governance_probability",
            "implementation_subtypes",
            "risk_subtypes",
            "rationale",
            "final_confidence",
            "api_model",
            "api_status",
            "from_cache",
        ])

    df = df.merge(res_df, left_index=True, right_on="row_index", how="left")

    # 对未进入 API 的句子：统一记为 not_ai_related（内部状态）
    df["final_label"] = df["final_label"].fillna("not_ai_related")
    df["generic_probability"] = df["generic_probability"].fillna(0.0)
    df["substantive_implementation_probability"] = df["substantive_implementation_probability"].fillna(0.0)
    df["substantive_risk_governance_probability"] = df["substantive_risk_governance_probability"].fillna(0.0)
    df["rationale"] = df["rationale"].fillna("")
    df["final_confidence"] = df["final_confidence"].fillna(0.0)
    df["api_status"] = df["api_status"].fillna("not_called")
    df["api_model"] = df["api_model"].fillna("")

    # 列表列统一成字符串，方便 csv 导出
    for col in ["implementation_subtypes", "risk_subtypes"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, list) else (x if pd.notna(x) else "[]"))
        else:
            df[col] = "[]"

    # sentence-level flags
    df["generic_ai_sentence_flag"] = (df["final_label"] == "generic_ai_disclosure").astype(int)
    df["substantive_ai_implementation_sentence_flag"] = (df["final_label"] == "substantive_ai_implementation").astype(int)
    df["substantive_ai_risk_governance_sentence_flag"] = (df["final_label"] == "substantive_ai_risk_governance").astype(int)
    df["substantive_ai_total_sentence_flag"] = (
        df["substantive_ai_implementation_sentence_flag"] + df["substantive_ai_risk_governance_sentence_flag"]
    )
    df["classified_ai_sentence_flag"] = (
        df["generic_ai_sentence_flag"] + df["substantive_ai_total_sentence_flag"]
    )

    # intensity numerators: 用 sentence_word_count，适配 sentence-level master file
    df["ai_candidate_word_count"] = np.where(df["ai_candidate_final"], df["sentence_word_count"], 0)
    df["generic_ai_word_count"] = df["generic_ai_sentence_flag"] * df["sentence_word_count"]
    df["substantive_ai_implementation_word_count"] = df["substantive_ai_implementation_sentence_flag"] * df["sentence_word_count"]
    df["substantive_ai_risk_governance_word_count"] = df["substantive_ai_risk_governance_sentence_flag"] * df["sentence_word_count"]
    df["substantive_ai_total_word_count"] = (
        df["substantive_ai_implementation_word_count"] + df["substantive_ai_risk_governance_word_count"]
    )

    # 导出 sentence-level 审计文件
    sentence_export_cols = [
        c for c in [
            "cik", "gvkey", "ticker", "company_name", "filing_date", "fiscal_year",
            "accession_number", "section_name", "sentence_id", "sentence_order",
            text_col, "sentence_raw", "sentence_clean", "sentence_word_count",
            "keep_sentence_flag", "is_exact_duplicate", "is_near_duplicate",
            "ai_candidate_flag", "ai_keyword_matched_terms",
            "seed_keyword_match", "a_group_ai_candidate_flag_bool", "matched_terms_nonempty",
            "ai_candidate_final", "final_label", "generic_probability",
            "substantive_implementation_probability", "substantive_risk_governance_probability",
            "implementation_subtypes", "risk_subtypes", "rationale", "final_confidence",
            "api_status", "api_model", "generic_ai_sentence_flag",
            "substantive_ai_implementation_sentence_flag",
            "substantive_ai_risk_governance_sentence_flag",
            "substantive_ai_total_sentence_flag", "classified_ai_sentence_flag",
        ] if c in df.columns
    ]

    df[sentence_export_cols].to_csv(SENTENCE_OUTPUT_CSV, index=False, encoding="utf-8-sig")
    try:
        df[sentence_export_cols].to_parquet(SENTENCE_OUTPUT_PARQUET, index=False)
    except Exception as e:
        print(f"[Warning] Could not save parquet: {e}")

    print("[6/7] Aggregating firm-year measures...")

    # firm-year 输出尽量对齐你截图里的字段
    firm_year_keys = [c for c in ["cik", "gvkey", "ticker", "company_name", "filing_date", "fiscal_year"] if c in df.columns]
    size_cols = [c for c in ["mdna_total_word_count", "mdna_total_sentence_count", "mdna_total_char_count"] if c in df.columns]
    group_cols = firm_year_keys + size_cols

    def agg_first_nonnull(series):
        s = series.dropna()
        return s.iloc[0] if len(s) > 0 else np.nan

    agg_dict = {
        **{c: "sum" for c in [
            "ai_candidate_final",
            "generic_ai_sentence_flag",
            "substantive_ai_implementation_sentence_flag",
            "substantive_ai_risk_governance_sentence_flag",
            "substantive_ai_total_sentence_flag",
            "ai_candidate_word_count",
            "generic_ai_word_count",
            "substantive_ai_implementation_word_count",
            "substantive_ai_risk_governance_word_count",
            "substantive_ai_total_word_count",
            "dropped_by_keep_flag",
        ]},
        "final_confidence": lambda x: float(pd.Series(x)[pd.Series(x) > 0].mean()) if (pd.Series(x) > 0).any() else 0.0,
    }

    firm = df.groupby(group_cols, dropna=False).agg(agg_dict).reset_index()

    # rename counts
    firm = firm.rename(columns={
        "ai_candidate_final": "n_ai_candidate_sentences",
        "generic_ai_sentence_flag": "n_generic_ai_sentences",
        "substantive_ai_implementation_sentence_flag": "n_substantive_ai_implementation_sentences",
        "substantive_ai_risk_governance_sentence_flag": "n_substantive_ai_risk_governance_sentences",
        "substantive_ai_total_sentence_flag": "n_substantive_ai_total_sentences",
        "dropped_by_keep_flag": "n_dropped_duplicate_sentences",
        "final_confidence": "avg_classification_confidence",
    })

    # intensity denominators: mdna_total_word_count
    # 论文口径是 AI-related words / total words in extracted corpus；
    # 这里 sentence-level 适配为：某类句子词数 / mdna_total_word_count
    if "mdna_total_word_count" not in firm.columns:
        raise ValueError("mdna_total_word_count is required to compute intensity variables.")

    firm["ai_candidate_intensity"] = safe_div(firm["ai_candidate_word_count"], firm["mdna_total_word_count"])
    firm["generic_ai_intensity"] = safe_div(firm["generic_ai_word_count"], firm["mdna_total_word_count"])
    firm["substantive_ai_implementation_intensity"] = safe_div(
        firm["substantive_ai_implementation_word_count"], firm["mdna_total_word_count"]
    )
    firm["substantive_ai_risk_governance_intensity"] = safe_div(
        firm["substantive_ai_risk_governance_word_count"], firm["mdna_total_word_count"]
    )
    firm["substantive_ai_total_intensity"] = safe_div(
        firm["substantive_ai_total_word_count"], firm["mdna_total_word_count"]
    )

    # shares: denominator = all classified AI disclosure sentences
    firm["n_all_ai_disclosure_sentences"] = (
        firm["n_generic_ai_sentences"] + firm["n_substantive_ai_total_sentences"]
    )

    firm["generic_ai_share"] = safe_div(firm["n_generic_ai_sentences"], firm["n_all_ai_disclosure_sentences"])
    firm["substantive_ai_share"] = safe_div(firm["n_substantive_ai_total_sentences"], firm["n_all_ai_disclosure_sentences"])
    firm["substantive_impl_share"] = safe_div(
        firm["n_substantive_ai_implementation_sentences"], firm["n_all_ai_disclosure_sentences"]
    )
    firm["substantive_risk_share"] = safe_div(
        firm["n_substantive_ai_risk_governance_sentences"], firm["n_all_ai_disclosure_sentences"]
    )

    # net measures: 用 intensity 差值，更适合回归
    firm["net_substantive_minus_generic"] = (
        firm["substantive_ai_total_intensity"] - firm["generic_ai_intensity"]
    )
    firm["impl_minus_generic"] = (
        firm["substantive_ai_implementation_intensity"] - firm["generic_ai_intensity"]
    )
    firm["risk_minus_generic"] = (
        firm["substantive_ai_risk_governance_intensity"] - firm["generic_ai_intensity"]
    )

    # dummies
    firm["any_generic_ai_dummy"] = (firm["n_generic_ai_sentences"] > 0).astype(int)
    firm["any_substantive_ai_dummy"] = (firm["n_substantive_ai_total_sentences"] > 0).astype(int)
    firm["any_substantive_ai_implementation_dummy"] = (
        firm["n_substantive_ai_implementation_sentences"] > 0
    ).astype(int)
    firm["any_substantive_ai_risk_governance_dummy"] = (
        firm["n_substantive_ai_risk_governance_sentences"] > 0
    ).astype(int)

    # 最终输出列，对齐截图 1-2
    final_cols = [
        c for c in [
            "cik", "gvkey", "ticker", "company_name", "filing_date", "fiscal_year",
            "mdna_total_word_count", "mdna_total_sentence_count", "mdna_total_char_count",
            "n_ai_candidate_sentences", "n_generic_ai_sentences",
            "n_substantive_ai_implementation_sentences",
            "n_substantive_ai_risk_governance_sentences",
            "n_substantive_ai_total_sentences",
            "ai_candidate_intensity", "generic_ai_intensity",
            "substantive_ai_implementation_intensity",
            "substantive_ai_risk_governance_intensity",
            "substantive_ai_total_intensity",
            "generic_ai_share", "substantive_ai_share",
            "substantive_impl_share", "substantive_risk_share",
            "net_substantive_minus_generic", "impl_minus_generic", "risk_minus_generic",
            "any_generic_ai_dummy", "any_substantive_ai_dummy",
            "any_substantive_ai_implementation_dummy",
            "any_substantive_ai_risk_governance_dummy",
            "n_dropped_duplicate_sentences", "avg_classification_confidence",
        ] if c in firm.columns
    ]

    firm[final_cols].to_csv(FIRMYEAR_OUTPUT_CSV, index=False, encoding="utf-8-sig")

    print("[7/7] Writing run summary...")
    summary = pd.DataFrame([
        {
            "input_path": INPUT_PATH,
            "model_name": MODEL_NAME,
            "n_total_rows": len(df),
            "n_candidate_rows": int(df["ai_candidate_final"].sum()),
            "n_classified_generic": int(df["generic_ai_sentence_flag"].sum()),
            "n_classified_impl": int(df["substantive_ai_implementation_sentence_flag"].sum()),
            "n_classified_risk": int(df["substantive_ai_risk_governance_sentence_flag"].sum()),
            "n_firm_year_rows": len(firm),
            "sentence_output_csv": SENTENCE_OUTPUT_CSV,
            "sentence_output_parquet": SENTENCE_OUTPUT_PARQUET,
            "firmyear_output_csv": FIRMYEAR_OUTPUT_CSV,
            "cache_path": CACHE_PATH,
            "share_denominator": SHARE_DENOMINATOR,
            "intensity_denominator": "mdna_total_word_count",
        }
    ])
    summary.to_csv(SUMMARY_OUTPUT_CSV, index=False, encoding="utf-8-sig")

    print("Done.")
    print(f"Sentence-level output: {SENTENCE_OUTPUT_CSV}")
    print(f"Firm-year output:      {FIRMYEAR_OUTPUT_CSV}")
    print(f"Run summary:           {SUMMARY_OUTPUT_CSV}")


if __name__ == "__main__":
    run_pipeline()
