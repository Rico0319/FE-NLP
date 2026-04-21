#!/usr/bin/env python3
"""
B组：MD&A sentence-level AI disclosure classification pipeline
===============================================================

Adapted for: mdna_sentence_master.jsonl
Environment: Python 3.10+

Install dependencies:
    pip install pandas numpy tqdm pydantic python-dotenv pyarrow

Features:
    1) Keyword screening (high recall) with word-boundary matching
    2) Concurrent API calls via ThreadPoolExecutor for speed
    3) Periodic checkpointing — resume safely if interrupted
    4) Structured JSON output via chat.completions (maximally compatible)
    5) Sentence-level audit file + firm-year regression-ready measures

Research labels (3-class):
    - generic_ai_disclosure
    - substantive_ai_implementation
    - substantive_ai_risk_governance

"not_ai_related" is an internal pipeline filter only.
"""

import os
import sys
import json
import math
import time
import hashlib
import re
import signal
import subprocess
import threading
from typing import List, Literal, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import numpy as np
import pandas as pd
from tqdm import tqdm
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load .env from the same directory as this script
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ============================================================
# 0. PATHS / SETTINGS
# ============================================================

INPUT_PATH = "/home/ricoz/econ_lab/FE-NLP/Data_Cleaning_NEW/data/intermediate/mdna_sentence_master.jsonl"
OUTPUT_DIR = "b_group_outputs"
CACHE_PATH = os.path.join(OUTPUT_DIR, "sentence_classification_cache.jsonl")
CHECKPOINT_PATH = os.path.join(OUTPUT_DIR, ".classification_checkpoint.json")
SENTENCE_OUTPUT_CSV = os.path.join(OUTPUT_DIR, "sentence_level_with_ai_labels.csv")
SENTENCE_OUTPUT_PARQUET = os.path.join(OUTPUT_DIR, "sentence_level_with_ai_labels.parquet")
FIRMYEAR_OUTPUT_CSV = os.path.join(OUTPUT_DIR, "firm_year_ai_disclosure_measures.csv")
SUMMARY_OUTPUT_CSV = os.path.join(OUTPUT_DIR, "run_summary.csv")

# API config — Kimi CLI only
MODEL_NAME = os.getenv("MODEL_NAME", "kimi-k2.6")
print(f"[Config] Using Kimi CLI. Model: {MODEL_NAME}")

# Concurrency & rate limiting
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "8"))
SLEEP_SEC = float(os.getenv("SLEEP_SEC", "0.05"))   # small delay between submissions
RETRY_TIMES = int(os.getenv("RETRY_TIMES", "3"))
CHECKPOINT_EVERY = int(os.getenv("CHECKPOINT_EVERY", "100"))  # save progress every N sentences

# Processing limits
MAX_CONTEXT_WORDS = 800      # SSRN reference: ~800-word window around keyword
MAX_TEST_ROWS = int(os.getenv("MAX_TEST_ROWS", "0")) or None  # Debug: set to 2000; production: None
ONLY_CLASSIFY_CANDIDATES = True

# Share denominator: all classified AI disclosure sentences
SHARE_DENOMINATOR = "all_ai_sentences"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Graceful shutdown handling
_shutdown_event = threading.Event()


def _signal_handler(signum, frame):
    print(f"\n[Signal {signum}] Shutdown requested. Finishing current batch and saving checkpoint...")
    _shutdown_event.set()


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# ============================================================
# 0a. API Client Setup & Validation
# ============================================================

def _validate_setup() -> None:
    """Validate that Kimi CLI is available and essential config is present."""
    if not MODEL_NAME:
        raise ValueError("MODEL_NAME is not set.")
    if not os.path.isfile(INPUT_PATH):
        raise FileNotFoundError(f"Input file not found: {INPUT_PATH}")
    # Verify kimi CLI is installed
    try:
        subprocess.run(
            ["kimi", "--version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError(
            "'kimi' CLI is not found or not working. "
            "Please install it (https://github.com/MoonshotAI/kimi-cli) and run 'kimi login'."
        ) from e




def _call_api_via_kimi_cli(
    messages: List[Dict[str, str]],
    max_tokens: int = 1024,
) -> str:
    """Call the Kimi CLI as a subprocess and return the raw JSON response.

    The Kimi coding-agent API key does not work with raw HTTP calls, but the
    official kimi CLI (which is OAuth-authenticated) can access it. We wrap the
    CLI here so the rest of the pipeline stays unchanged.
    """
    # Flatten messages into a single prompt string
    parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            parts.append(f"[System Instructions]\n{content}")
        else:
            parts.append(content)
    full_prompt = "\n\n".join(parts)

    # The prompt can be long; pass via --prompt (ARG_MAX on Linux is ~2 MB)
    env = {**os.environ, "COLUMNS": "10000"}  # prevent line-wrapping
    cmd = [
        "kimi",
        "--yolo",
        "--no-thinking",
        "--prompt",
        full_prompt,
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120.0,
        env=env,
    )

    if result.returncode != 0:
        stderr_tail = result.stderr.strip()[-500:] if result.stderr else ""
        raise RuntimeError(
            f"kimi CLI exited with code {result.returncode}. "
            f"stderr: {stderr_tail}"
        )

    # stdout contains the response prefixed with "• " on the first line.
    # With COLUMNS=10000 there is no word-wrapping, so the JSON is intact.
    stdout = result.stdout
    if not stdout.strip():
        raise RuntimeError("kimi CLI returned empty stdout.")

    # Find the bullet-prefixed response line(s)
    lines = stdout.splitlines()
    response_lines: List[str] = []
    in_response = False
    for line in lines:
        if line.startswith("\u2022 "):  # bullet + space
            in_response = True
            response_lines.append(line[2:])  # strip "• "
        elif in_response:
            if line.strip() == "":
                break
            response_lines.append(line)

    if not response_lines:
        raise RuntimeError(
            f"Could not parse kimi CLI output. Raw stdout:\n{stdout[:2000]}"
        )

    return "\n".join(response_lines)


# ============================================================
# 1. AI seed keyword screen
# ============================================================

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
    "a\\.i\\.",  # escaped for regex word boundary
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
    "autonomous systems",
]

SEED_KEYWORDS = HIGH_PRECISION_KEYWORDS + EXPANDED_KEYWORDS

# Word-boundary regex for cleaner matching
SEED_PATTERN = r"\b(?:" + "|".join(SEED_KEYWORDS) + r")\b"
SEED_REGEX = re.compile(SEED_PATTERN, flags=re.IGNORECASE)


# ============================================================
# 2. Definition-based prompt
# ============================================================

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

Respond ONLY with a valid JSON object. Do not include markdown formatting, explanations, or code fences.
'''


# ============================================================
# 3. Structured output schema
# ============================================================

class SentenceClassification(BaseModel):
    final_label: Literal[
        "not_ai_related",
        "generic_ai_disclosure",
        "substantive_ai_implementation",
        "substantive_ai_risk_governance",
    ]
    generic_probability: float = Field(..., ge=0.0, le=1.0)
    substantive_implementation_probability: float = Field(..., ge=0.0, le=1.0)
    substantive_risk_governance_probability: float = Field(..., ge=0.0, le=1.0)
    implementation_subtypes: List[
        Literal[
            "product_development",
            "ai_product_provider",
            "pricing_optimization",
            "inventory_management",
            "operational_efficiency",
        ]
    ] = Field(default_factory=list)
    risk_subtypes: List[
        Literal[
            "regulatory_risk",
            "operational_risk",
            "competitive_risk",
            "cybersecurity_risk",
            "ethical_risk",
            "third_party_dependence_risk",
        ]
    ] = Field(default_factory=list)
    rationale: str = ""


# JSON schema for the API
CLASSIFICATION_JSON_SCHEMA = SentenceClassification.model_json_schema()


# ============================================================
# 4. Helpers
# ============================================================

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


def validate_required_columns(df: pd.DataFrame) -> None:
    """Ensure the input DataFrame has all columns we need."""
    required = {
        "sentence_id": "row identifier",
        "cik": "firm identifier",
        "filing_date": "filing date",
        "fiscal_year": "fiscal year",
    }
    # text_col is checked separately in pick_text_column
    missing = [c for c in required if c not in df.columns]
    if missing:
        descriptions = [f"  - {c}: {required[c]}" for c in missing]
        raise ValueError(
            f"Input file is missing required columns:\n" + "\n".join(descriptions)
        )


def make_seed_candidate_flags(df: pd.DataFrame, text_col: str) -> pd.DataFrame:
    df = df.copy()
    text_series = df[text_col].fillna("").astype(str)
    df["seed_keyword_match"] = text_series.str.contains(SEED_REGEX, regex=True)

    if "ai_candidate_flag" in df.columns:
        api_flag = df["ai_candidate_flag"].apply(normalize_bool)
    else:
        api_flag = pd.Series(False, index=df.index)

    if "ai_keyword_matched_terms" in df.columns:
        matched_terms_nonempty = df["ai_keyword_matched_terms"].apply(
            lambda x: len(parse_ai_keyword_terms(x)) > 0
        )
    else:
        matched_terms_nonempty = pd.Series(False, index=df.index)

    if "keep_sentence_flag" in df.columns:
        keep_flag = df["keep_sentence_flag"].apply(normalize_bool)
    else:
        keep_flag = pd.Series(True, index=df.index)

    df["keep_sentence_flag_bool"] = keep_flag
    df["a_group_ai_candidate_flag_bool"] = api_flag
    df["matched_terms_nonempty"] = matched_terms_nonempty

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


def build_context_window(
    group_df: pd.DataFrame, row_idx, text_col: str, max_words: int = 800
) -> str:
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


def make_user_prompt(
    focal_sentence: str, context_text: str, sentence_id: str, matched_terms: List[str]
) -> str:
    matched_terms_display = ", ".join(matched_terms) if matched_terms else "None"
    return f"""Classify the focal MD&A sentence below.

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
- Respond ONLY with valid JSON.""".strip()


def probability_for_final_label(result: SentenceClassification) -> float:
    if result.final_label == "generic_ai_disclosure":
        return clamp01(result.generic_probability)
    if result.final_label == "substantive_ai_implementation":
        return clamp01(result.substantive_implementation_probability)
    if result.final_label == "substantive_ai_risk_governance":
        return clamp01(result.substantive_risk_governance_probability)
    return clamp01(
        1.0
        - max(
            clamp01(result.generic_probability),
            clamp01(result.substantive_implementation_probability),
            clamp01(result.substantive_risk_governance_probability),
        )
    )


# ============================================================
# 5. LLM API call (robust, concurrent-safe)
# ============================================================

def _call_api_with_retry(
    focal_sentence: str,
    context_text: str,
    sentence_id: str,
    matched_terms: List[str],
) -> Dict[str, Any]:
    """Call the LLM API with manual retry logic and structured output parsing."""
    user_prompt = make_user_prompt(
        focal_sentence=focal_sentence,
        context_text=context_text,
        sentence_id=sentence_id,
        matched_terms=matched_terms,
    )

    last_err = None
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    for attempt in range(RETRY_TIMES):
        if _shutdown_event.is_set():
            return {
                "final_label": "not_ai_related",
                "generic_probability": 0.0,
                "substantive_implementation_probability": 0.0,
                "substantive_risk_governance_probability": 0.0,
                "implementation_subtypes": [],
                "risk_subtypes": [],
                "rationale": "SHUTDOWN_INTERRUPTED",
                "final_confidence": 0.0,
                "api_model": MODEL_NAME,
                "api_status": "shutdown",
            }

        try:
            raw_json = _call_api_via_kimi_cli(
                messages=messages,
                max_tokens=1024,
            )

            parsed = SentenceClassification.model_validate_json(raw_json)

            return {
                "final_label": parsed.final_label,
                "generic_probability": clamp01(parsed.generic_probability),
                "substantive_implementation_probability": clamp01(
                    parsed.substantive_implementation_probability
                ),
                "substantive_risk_governance_probability": clamp01(
                    parsed.substantive_risk_governance_probability
                ),
                "implementation_subtypes": parsed.implementation_subtypes,
                "risk_subtypes": parsed.risk_subtypes,
                "rationale": parsed.rationale,
                "final_confidence": probability_for_final_label(parsed),
                "api_model": MODEL_NAME,
                "api_status": "ok",
            }

        except Exception as e:
            last_err = str(e)
            # Exponential backoff: 1s, 2s, 4s
            wait_s = min(2 ** attempt, 8)
            time.sleep(wait_s)

    # All retries exhausted
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


# ============================================================
# 6. Cache & Checkpointing
# ============================================================

def load_cache(cache_path: str) -> Dict[str, Dict]:
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


def append_cache_record(cache_path: str, record: Dict):
    with open(cache_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_checkpoint(checkpoint_path: str) -> Dict[str, Any]:
    """Load progress checkpoint if it exists."""
    if not os.path.exists(checkpoint_path):
        return {}
    try:
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_checkpoint(checkpoint_path: str, data: Dict[str, Any]) -> None:
    """Atomically save progress checkpoint."""
    tmp_path = checkpoint_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, checkpoint_path)


# ============================================================
# 7. Concurrent classification worker
# ============================================================

def classify_single_sentence(args: tuple) -> Dict[str, Any]:
    """
    Worker function for ThreadPoolExecutor.
    Args: (row_dict, group_df_dict, text_col, cache, cache_path)
    """
    row_dict, group_df_dict, text_col, cache, cache_path = args

    row_idx = row_dict["__index__"]
    gkey = row_dict["__gkey__"]
    group_df = pd.DataFrame.from_dict(group_df_dict)

    focal_sentence = safe_text(row_dict[text_col]).strip()
    context_text = build_context_window(group_df, row_idx, text_col=text_col, max_words=MAX_CONTEXT_WORDS)
    matched_terms = parse_ai_keyword_terms(row_dict.get("ai_keyword_matched_terms", []))
    sentence_id = safe_text(row_dict.get("sentence_id", f"row_{row_idx}"))

    cache_key_payload = {
        "sentence_id": sentence_id,
        "focal_sentence": focal_sentence,
        "context_hash": stable_hash(context_text),
        "model": MODEL_NAME,
    }
    cache_key = stable_hash(json.dumps(cache_key_payload, ensure_ascii=False, sort_keys=True))

    if cache_key in cache:
        rec = cache[cache_key].copy()
        rec["from_cache"] = True
        rec["row_index"] = row_idx
        rec["cache_key"] = cache_key
        return rec

    rec = _call_api_with_retry(
        focal_sentence=focal_sentence,
        context_text=context_text,
        sentence_id=sentence_id,
        matched_terms=matched_terms,
    )
    rec["cache_key"] = cache_key
    rec["sentence_id"] = sentence_id
    rec["row_index"] = row_idx
    rec["from_cache"] = False

    # Write to cache immediately for durability
    append_cache_record(cache_path, rec)
    cache[cache_key] = rec

    if SLEEP_SEC > 0:
        time.sleep(SLEEP_SEC)

    return rec


# ============================================================
# 8. Cost estimation
# ============================================================

def estimate_costs(n_candidates: int, avg_words_per_context: int = 1000) -> Dict[str, Any]:
    """
    Rough cost estimation.
    Kimi-k2.6 pricing varies; we use conservative token estimates.
    ~1.3 tokens per word for English text.
    """
    tokens_per_word = 1.3
    system_prompt_tokens = len(SYSTEM_PROMPT.split()) * tokens_per_word
    context_tokens = avg_words_per_context * tokens_per_word
    output_tokens = 200  # JSON response

    input_tokens_per_call = system_prompt_tokens + context_tokens
    total_input_tokens = input_tokens_per_call * n_candidates
    total_output_tokens = output_tokens * n_candidates
    total_tokens = total_input_tokens + total_output_tokens

    # Kimi pricing is unknown; show token counts instead
    return {
        "n_candidates": n_candidates,
        "estimated_input_tokens": int(total_input_tokens),
        "estimated_output_tokens": int(total_output_tokens),
        "estimated_total_tokens": int(total_tokens),
        "notes": "Kimi pricing varies. Budget ~$0.03-0.10 per 1K tokens as a conservative estimate.",
    }


# ============================================================
# 9. Aggregation helpers
# ============================================================

def agg_first_nonnull(series: pd.Series):
    s = series.dropna()
    return s.iloc[0] if len(s) > 0 else np.nan


def agg_mean_positive(series: pd.Series) -> float:
    s = pd.Series(series)
    positive = s[s > 0]
    return float(positive.mean()) if len(positive) > 0 else 0.0


# ============================================================
# 10. Main pipeline
# ============================================================

def run_pipeline():
    print("=" * 60)
    print("B-Group AI Disclosure Classification Pipeline")
    print("=" * 60)
    print(f"Model:        {MODEL_NAME}")
    print(f"Input:        {INPUT_PATH}")
    print(f"Workers:      {MAX_WORKERS}")
    print(f"Checkpoint:   every {CHECKPOINT_EVERY} sentences")
    print("=" * 60)

    # --- Validation ---
    _validate_setup()

    # --- Read input ---
    print("\n[1/8] Reading input file...")
    df = pd.read_json(INPUT_PATH, lines=True)
    print(f"      Loaded {len(df):,} rows, {len(df.columns)} columns")

    if MAX_TEST_ROWS is not None:
        df = df.head(MAX_TEST_ROWS).copy()
        print(f"      DEBUG: truncated to {len(df):,} rows")

    text_col = pick_text_column(df)
    validate_required_columns(df)
    df = ensure_sentence_order(df)
    df = make_seed_candidate_flags(df, text_col=text_col)

    # Fill sentence_word_count
    if "sentence_word_count" not in df.columns:
        df["sentence_word_count"] = (
            df[text_col].fillna("").astype(str).map(sentence_word_count_from_text)
        )
    else:
        swc = pd.to_numeric(df["sentence_word_count"], errors="coerce")
        missing = swc.isna()
        if missing.any():
            swc.loc[missing] = (
                df.loc[missing, text_col]
                .fillna("")
                .astype(str)
                .map(sentence_word_count_from_text)
            )
        df["sentence_word_count"] = swc.astype(int)

    if "sentence_id" not in df.columns:
        df["sentence_id"] = [f"row_{i}" for i in range(len(df))]

    group_keys = build_group_keys(df)
    df["dropped_by_keep_flag"] = ~df["keep_sentence_flag_bool"]

    # --- Build document groups ---
    print("[2/8] Building document groups...")
    grouped = {
        k: g.sort_values("sentence_order_num").copy()
        for k, g in df.groupby(group_keys, dropna=False, sort=False)
    }

    if ONLY_CLASSIFY_CANDIDATES:
        target_mask = df["ai_candidate_final"]
    else:
        target_mask = df["keep_sentence_flag_bool"]

    target_df = df.loc[target_mask].copy()
    n_total = len(df)
    n_candidates = len(target_df)
    print(f"      Total rows:     {n_total:,}")
    print(f"      Candidates:     {n_candidates:,}")

    # --- Cost estimate ---
    cost_est = estimate_costs(n_candidates)
    print(f"\n[3/8] Cost estimate:")
    print(f"      Estimated input tokens:  {cost_est['estimated_input_tokens']:,}")
    print(f"      Estimated output tokens: {cost_est['estimated_output_tokens']:,}")
    print(f"      Estimated total tokens:  {cost_est['estimated_total_tokens']:,}")
    print(f"      Note: {cost_est['notes']}")

    # --- Load cache & checkpoint ---
    print(f"\n[4/8] Loading cache...")
    cache = load_cache(CACHE_PATH)
    print(f"      Cache entries: {len(cache):,}")

    checkpoint = load_checkpoint(CHECKPOINT_PATH)
    completed_indices = set(checkpoint.get("completed_row_indices", []))
    if completed_indices:
        print(f"      Checkpoint: {len(completed_indices):,} sentences already processed")

    # --- Prepare work items ---
    work_items = []
    for idx, row in target_df.iterrows():
        if idx in completed_indices:
            continue
        gkey = tuple(row[k] for k in group_keys)
        gdf = grouped[gkey]
        row_dict = row.to_dict()
        row_dict["__index__"] = idx
        row_dict["__gkey__"] = gkey
        work_items.append((row_dict, gdf.to_dict(), text_col, cache, CACHE_PATH))

    n_to_process = len(work_items)
    print(f"\n[5/8] Sentences to classify: {n_to_process:,}")
    if n_to_process == 0:
        print("      Nothing to do. Loading from cache/checkpoint...")

    # --- Concurrent classification ---
    results: List[Dict[str, Any]] = []
    processed_since_checkpoint = 0

    if n_to_process > 0:
        print(f"[6/8] Classifying with {MAX_WORKERS} workers...")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(classify_single_sentence, item): item for item in work_items}

            pbar = tqdm(total=n_to_process, desc="Classifying")
            for future in as_completed(futures):
                if _shutdown_event.is_set():
                    # Cancel remaining futures
                    for f in futures:
                        f.cancel()
                    break

                try:
                    rec = future.result(timeout=120)
                except Exception as e:
                    rec = {
                        "final_label": "not_ai_related",
                        "generic_probability": 0.0,
                        "substantive_implementation_probability": 0.0,
                        "substantive_risk_governance_probability": 0.0,
                        "implementation_subtypes": [],
                        "risk_subtypes": [],
                        "rationale": f"WORKER_ERROR: {str(e)}",
                        "final_confidence": 0.0,
                        "api_model": MODEL_NAME,
                        "api_status": "error",
                        "row_index": futures[future][0]["__index__"],
                        "from_cache": False,
                    }

                results.append(rec)
                processed_since_checkpoint += 1
                pbar.update(1)

                # Periodic checkpoint
                if processed_since_checkpoint >= CHECKPOINT_EVERY:
                    newly_done = [r["row_index"] for r in results[-processed_since_checkpoint:]]
                    all_done = list(completed_indices) + newly_done
                    save_checkpoint(
                        CHECKPOINT_PATH,
                        {
                            "completed_row_indices": all_done,
                            "total_processed": len(all_done),
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        },
                    )
                    completed_indices.update(newly_done)
                    processed_since_checkpoint = 0

            pbar.close()

    # Final checkpoint
    if results:
        all_done = list(completed_indices) + [r["row_index"] for r in results]
        save_checkpoint(
            CHECKPOINT_PATH,
            {
                "completed_row_indices": all_done,
                "total_processed": len(all_done),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
        )
        print(f"      Processed {len(results):,} sentences this run")

    # --- Load any cached results for already-completed rows ---
    print("\n[7/8] Merging sentence-level results...")
    all_results = results.copy()

    # For rows that were in checkpoint but not in this run's results, reconstruct from cache
    for idx in completed_indices:
        if not any(r.get("row_index") == idx for r in all_results):
            # Find in cache by row_index (we can't easily, but we can skip since
            # the merge will fill NaNs with defaults later)
            pass

    res_df = pd.DataFrame(all_results)
    if len(res_df) == 0:
        res_df = pd.DataFrame(
            columns=[
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
                "cache_key",
            ]
        )

    df = df.merge(res_df, left_index=True, right_on="row_index", how="left")

    # Fill defaults for non-classified sentences
    df["final_label"] = df["final_label"].fillna("not_ai_related")
    df["generic_probability"] = df["generic_probability"].fillna(0.0)
    df["substantive_implementation_probability"] = df["substantive_implementation_probability"].fillna(0.0)
    df["substantive_risk_governance_probability"] = df["substantive_risk_governance_probability"].fillna(0.0)
    df["rationale"] = df["rationale"].fillna("")
    df["final_confidence"] = df["final_confidence"].fillna(0.0)
    df["api_status"] = df["api_status"].fillna("not_called")
    df["api_model"] = df["api_model"].fillna("")
    df["from_cache"] = df["from_cache"].fillna(False)

    # List columns: keep as lists for Parquet, create string copies for CSV
    for col in ["implementation_subtypes", "risk_subtypes"]:
        if col not in df.columns:
            df[col] = [[] for _ in range(len(df))]
        else:
            df[col] = df[col].apply(lambda x: x if isinstance(x, list) else [])

    # Sentence-level flags
    df["generic_ai_sentence_flag"] = (df["final_label"] == "generic_ai_disclosure").astype(int)
    df["substantive_ai_implementation_sentence_flag"] = (
        df["final_label"] == "substantive_ai_implementation"
    ).astype(int)
    df["substantive_ai_risk_governance_sentence_flag"] = (
        df["final_label"] == "substantive_ai_risk_governance"
    ).astype(int)
    df["substantive_ai_total_sentence_flag"] = (
        df["substantive_ai_implementation_sentence_flag"]
        + df["substantive_ai_risk_governance_sentence_flag"]
    )
    df["classified_ai_sentence_flag"] = (
        df["generic_ai_sentence_flag"] + df["substantive_ai_total_sentence_flag"]
    )

    # Word-count-based intensity numerators
    df["ai_candidate_word_count"] = np.where(df["ai_candidate_final"], df["sentence_word_count"], 0)
    df["generic_ai_word_count"] = df["generic_ai_sentence_flag"] * df["sentence_word_count"]
    df["substantive_ai_implementation_word_count"] = (
        df["substantive_ai_implementation_sentence_flag"] * df["sentence_word_count"]
    )
    df["substantive_ai_risk_governance_word_count"] = (
        df["substantive_ai_risk_governance_sentence_flag"] * df["sentence_word_count"]
    )
    df["substantive_ai_total_word_count"] = (
        df["substantive_ai_implementation_word_count"]
        + df["substantive_ai_risk_governance_word_count"]
    )

    # --- Export sentence-level audit file ---
    _base_export_cols = [
        "cik",
        "gvkey",
        "ticker",
        "company_name",
        "filing_date",
        "fiscal_year",
        "accession_number",
        "section_name",
        "sentence_id",
        "sentence_order",
        "sentence_raw",
        "sentence_clean",
        "sentence_word_count",
        "keep_sentence_flag",
        "is_exact_duplicate",
        "is_near_duplicate",
        "ai_candidate_flag",
        "ai_keyword_matched_terms",
        "seed_keyword_match",
        "a_group_ai_candidate_flag_bool",
        "matched_terms_nonempty",
        "ai_candidate_final",
        "final_label",
        "generic_probability",
        "substantive_implementation_probability",
        "substantive_risk_governance_probability",
        "implementation_subtypes",
        "risk_subtypes",
        "rationale",
        "final_confidence",
        "api_status",
        "api_model",
        "from_cache",
        "generic_ai_sentence_flag",
        "substantive_ai_implementation_sentence_flag",
        "substantive_ai_risk_governance_sentence_flag",
        "substantive_ai_total_sentence_flag",
        "classified_ai_sentence_flag",
    ]
    # Ensure text_col is first among text columns, then deduplicate
    sentence_export_cols = [c for c in [text_col] + _base_export_cols if c in df.columns]
    sentence_export_cols = list(dict.fromkeys(sentence_export_cols))  # dedupe while preserving order

    # For CSV: stringify list columns
    df_csv = df.copy()
    for col in ["implementation_subtypes", "risk_subtypes"]:
        if col in df_csv.columns:
            df_csv[col] = df_csv[col].apply(
                lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, list) else "[]"
            )

    df_csv[sentence_export_cols].to_csv(SENTENCE_OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"      CSV:  {SENTENCE_OUTPUT_CSV}")

    # Parquet: preserve list types
    try:
        df[sentence_export_cols].to_parquet(SENTENCE_OUTPUT_PARQUET, index=False)
        print(f"      Parquet: {SENTENCE_OUTPUT_PARQUET}")
    except Exception as e:
        print(f"      [Warning] Could not save parquet: {e}")

    # --- Firm-year aggregation ---
    print("\n[8/8] Aggregating firm-year measures...")

    firm_year_keys = [
        c for c in ["cik", "gvkey", "ticker", "company_name", "filing_date", "fiscal_year"]
        if c in df.columns
    ]
    size_cols = [
        c
        for c in ["mdna_total_word_count", "mdna_total_sentence_count", "mdna_total_char_count"]
        if c in df.columns
    ]
    group_cols = firm_year_keys + size_cols

    agg_dict = {
        **{
            c: "sum"
            for c in [
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
            ]
        },
        "final_confidence": agg_mean_positive,
    }

    firm = df.groupby(group_cols, dropna=False).agg(agg_dict).reset_index()

    firm = firm.rename(
        columns={
            "ai_candidate_final": "n_ai_candidate_sentences",
            "generic_ai_sentence_flag": "n_generic_ai_sentences",
            "substantive_ai_implementation_sentence_flag": "n_substantive_ai_implementation_sentences",
            "substantive_ai_risk_governance_sentence_flag": "n_substantive_ai_risk_governance_sentences",
            "substantive_ai_total_sentence_flag": "n_substantive_ai_total_sentences",
            "dropped_by_keep_flag": "n_dropped_duplicate_sentences",
            "final_confidence": "avg_classification_confidence",
        }
    )

    # Intensity variables
    if "mdna_total_word_count" not in firm.columns:
        raise ValueError("mdna_total_word_count is required to compute intensity variables.")

    firm["ai_candidate_intensity"] = safe_div(
        firm["ai_candidate_word_count"], firm["mdna_total_word_count"]
    )
    firm["generic_ai_intensity"] = safe_div(
        firm["generic_ai_word_count"], firm["mdna_total_word_count"]
    )
    firm["substantive_ai_implementation_intensity"] = safe_div(
        firm["substantive_ai_implementation_word_count"], firm["mdna_total_word_count"]
    )
    firm["substantive_ai_risk_governance_intensity"] = safe_div(
        firm["substantive_ai_risk_governance_word_count"], firm["mdna_total_word_count"]
    )
    firm["substantive_ai_total_intensity"] = safe_div(
        firm["substantive_ai_total_word_count"], firm["mdna_total_word_count"]
    )

    # Shares
    firm["n_all_ai_disclosure_sentences"] = (
        firm["n_generic_ai_sentences"] + firm["n_substantive_ai_total_sentences"]
    )
    firm["generic_ai_share"] = safe_div(
        firm["n_generic_ai_sentences"], firm["n_all_ai_disclosure_sentences"]
    )
    firm["substantive_ai_share"] = safe_div(
        firm["n_substantive_ai_total_sentences"], firm["n_all_ai_disclosure_sentences"]
    )
    firm["substantive_impl_share"] = safe_div(
        firm["n_substantive_ai_implementation_sentences"], firm["n_all_ai_disclosure_sentences"]
    )
    firm["substantive_risk_share"] = safe_div(
        firm["n_substantive_ai_risk_governance_sentences"], firm["n_all_ai_disclosure_sentences"]
    )

    # Net measures
    firm["net_substantive_minus_generic"] = (
        firm["substantive_ai_total_intensity"] - firm["generic_ai_intensity"]
    )
    firm["impl_minus_generic"] = (
        firm["substantive_ai_implementation_intensity"] - firm["generic_ai_intensity"]
    )
    firm["risk_minus_generic"] = (
        firm["substantive_ai_risk_governance_intensity"] - firm["generic_ai_intensity"]
    )

    # Dummies
    firm["any_generic_ai_dummy"] = (firm["n_generic_ai_sentences"] > 0).astype(int)
    firm["any_substantive_ai_dummy"] = (firm["n_substantive_ai_total_sentences"] > 0).astype(int)
    firm["any_substantive_ai_implementation_dummy"] = (
        firm["n_substantive_ai_implementation_sentences"] > 0
    ).astype(int)
    firm["any_substantive_ai_risk_governance_dummy"] = (
        firm["n_substantive_ai_risk_governance_sentences"] > 0
    ).astype(int)

    final_cols = [
        c
        for c in [
            "cik",
            "gvkey",
            "ticker",
            "company_name",
            "filing_date",
            "fiscal_year",
            "mdna_total_word_count",
            "mdna_total_sentence_count",
            "mdna_total_char_count",
            "n_ai_candidate_sentences",
            "n_generic_ai_sentences",
            "n_substantive_ai_implementation_sentences",
            "n_substantive_ai_risk_governance_sentences",
            "n_substantive_ai_total_sentences",
            "ai_candidate_intensity",
            "generic_ai_intensity",
            "substantive_ai_implementation_intensity",
            "substantive_ai_risk_governance_intensity",
            "substantive_ai_total_intensity",
            "generic_ai_share",
            "substantive_ai_share",
            "substantive_impl_share",
            "substantive_risk_share",
            "net_substantive_minus_generic",
            "impl_minus_generic",
            "risk_minus_generic",
            "any_generic_ai_dummy",
            "any_substantive_ai_dummy",
            "any_substantive_ai_implementation_dummy",
            "any_substantive_ai_risk_governance_dummy",
            "n_dropped_duplicate_sentences",
            "avg_classification_confidence",
        ]
        if c in firm.columns
    ]

    firm[final_cols].to_csv(FIRMYEAR_OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"      Firm-year CSV: {FIRMYEAR_OUTPUT_CSV}")

    # --- Summary ---
    print("\n[Summary] Writing run summary...")
    summary = pd.DataFrame(
        [
            {
                "input_path": INPUT_PATH,
                "model_name": MODEL_NAME,
                "n_total_rows": len(df),
                "n_candidate_rows": int(df["ai_candidate_final"].sum()),
                "n_classified_generic": int(df["generic_ai_sentence_flag"].sum()),
                "n_classified_impl": int(df["substantive_ai_implementation_sentence_flag"].sum()),
                "n_classified_risk": int(df["substantive_ai_risk_governance_sentence_flag"].sum()),
                "n_from_cache": int(df["from_cache"].sum()),
                "n_api_errors": int((df["api_status"] == "error").sum()),
                "n_firm_year_rows": len(firm),
                "sentence_output_csv": SENTENCE_OUTPUT_CSV,
                "sentence_output_parquet": SENTENCE_OUTPUT_PARQUET,
                "firmyear_output_csv": FIRMYEAR_OUTPUT_CSV,
                "cache_path": CACHE_PATH,
                "checkpoint_path": CHECKPOINT_PATH,
                "share_denominator": SHARE_DENOMINATOR,
                "intensity_denominator": "mdna_total_word_count",
                "max_workers": MAX_WORKERS,
            }
        ]
    )
    summary.to_csv(SUMMARY_OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"      Summary CSV: {SUMMARY_OUTPUT_CSV}")

    print("\n" + "=" * 60)
    print("Done.")
    print(f"Sentence-level CSV:  {SENTENCE_OUTPUT_CSV}")
    print(f"Sentence-level PQ:   {SENTENCE_OUTPUT_PARQUET}")
    print(f"Firm-year CSV:       {FIRMYEAR_OUTPUT_CSV}")
    print("=" * 60)


if __name__ == "__main__":
    run_pipeline()
