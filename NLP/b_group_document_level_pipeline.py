#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B组：MD&A document-level AI disclosure classification pipeline

这个版本不按句子拆分，而是将同一份 MD&A 的所有句子拼回原始文本，
以"文档"为单位进行 AI 披露分类。

相比句子级版本：
- API 调用次数从 ~2000​+ 次降到 ~1000 次（按文档数）
- 保留了并发（ThreadPoolExecutor）
- 输出为 document-level 指标，适合快速 pilot / 初步分析

输入：mdna_sentence_master.jsonl（句子级，含 sentence_order）
输出：
  - document_level_ai_disclosure.csv   （每份 filing 一行）
  - run_summary.csv                     （运行统计）

适配：任何 OpenAI-compatible API（OpenAI, OpenRouter, 等）
环境变量：
  OPENAI_API_KEY      — API key
  OPENAI_BASE_URL     — 可选，自定义 base URL（如 OpenRouter）
  MODEL_NAME          — 模型名称，必填（如 gpt-4o, gpt-4o-mini, kimi-k2.5 等）
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from openai import OpenAI
from pydantic import BaseModel
from tqdm import tqdm

# ============================================================
# 0. CONFIGURATION
# ============================================================
INPUT_PATH = os.getenv(
    "INPUT_PATH",
    r"/Users/jiazuo/Desktop/nlppp/mdna_sentence_master.jsonl",
)
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "b_group_outputs")
CHECKPOINT_PATH = os.path.join(OUTPUT_DIR, "document_checkpoint.jsonl")
DOC_OUTPUT_CSV = os.path.join(OUTPUT_DIR, "document_level_ai_disclosure.csv")
SUMMARY_OUTPUT_CSV = os.path.join(OUTPUT_DIR, "run_summary.csv")

MODEL_NAME = os.getenv("MODEL_NAME", "")
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "8"))
SLEEP_SEC = float(os.getenv("SLEEP_SEC", "0.05"))
RETRY_TIMES = int(os.getenv("RETRY_TIMES", "3"))
MAX_DOC_WORDS = int(os.getenv("MAX_DOC_WORDS", "12000"))  # 单篇 MD&A 最大词数，超限则截断
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1"))  # 每批并发文档数

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
# 1. PROMPT
# ============================================================
SYSTEM_PROMPT = r"""You are a careful financial-disclosure research assistant.

Your task: Analyze an MD&A text from a firm's 10-K filing and count how many sentences mention AI/ML and what type of disclosure each represents.

Classification criteria:

1. generic_ai_disclosure:
   Mentions AI but remains vague, aspirational, strategic, or promotional.
   No concrete business function or risk mechanism is specified.
   Examples: "we are investing in AI", "AI is transforming our industry",
   "we embrace artificial intelligence and digitalization".

2. substantive_ai_implementation:
   Clearly describes a concrete AI use case in business operations.
   The text answers WHERE AI is applied, WHAT it does, or HOW it affects operations.
   Categories include: product development, AI product/provider, pricing optimization,
   inventory management, operational efficiency.
   Examples: "we use machine learning to forecast demand",
   "our AI-powered platform automates customer service",
   "deep learning models optimize our pricing in real time".

3. substantive_ai_risk_governance:
   Explicitly describes an AI-related risk or governance mechanism with
   identifiable source and/or consequence.
   Risk channels: regulatory, operational, competitive, cybersecurity, ethical,
   third-party dependence.
   Examples: "new AI regulation may increase compliance costs",
   "reliance on third-party AI models creates operational risk".

IMPORTANT:
- Count EACH sentence that mentions AI/ML separately.
- A sentence like "AI may create risks" is GENERIC unless it specifies the risk source/mechanism.
- Be conservative. Do not infer applications or risks not explicitly stated.
- Return exact integer counts.
"""


# ============================================================
# 2. JSON SCHEMA (for structured output)
# ============================================================
DOCUMENT_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "n_generic_ai_sentences": {
            "type": "integer",
            "description": "Number of sentences mentioning AI in a generic/vague way",
        },
        "n_substantive_implementation_sentences": {
            "type": "integer",
            "description": "Number of sentences describing concrete AI implementation",
        },
        "n_substantive_risk_governance_sentences": {
            "type": "integer",
            "description": "Number of sentences describing specific AI risks or governance",
        },
        "n_total_ai_sentences": {
            "type": "integer",
            "description": "Total number of sentences that mention AI/ML",
        },
        "has_ai_mention": {
            "type": "boolean",
            "description": "True if the document contains any AI/ML mention",
        },
        "rationale": {
            "type": "string",
            "description": "Brief summary of AI disclosure findings in this document",
        },
    },
    "required": [
        "n_generic_ai_sentences",
        "n_substantive_implementation_sentences",
        "n_substantive_risk_governance_sentences",
        "n_total_ai_sentences",
        "has_ai_mention",
        "rationale",
    ],
    "additionalProperties": False,
}


# ============================================================
# 3. PYDANTIC MODEL (for validation after parsing)
# ============================================================
class DocumentClassification(BaseModel):
    n_generic_ai_sentences: int
    n_substantive_implementation_sentences: int
    n_substantive_risk_governance_sentences: int
    n_total_ai_sentences: int
    has_ai_mention: bool
    rationale: str


# ============================================================
# 4. HELPERS
# ============================================================
def safe_text(x) -> str:
    return "" if pd.isna(x) else str(x)


def truncate_mdna(text: str, max_words: int = MAX_DOC_WORDS) -> str:
    """Truncate MD&A text to max_words, preserving sentence boundaries where possible."""
    words = text.split()
    if len(words) <= max_words:
        return text
    truncated = " ".join(words[:max_words])
    # Try to end at a sentence boundary
    last_period = truncated.rfind(".")
    if last_period > max_words * 0.8:
        return truncated[: last_period + 1]
    return truncated


def build_document_text(group_df: pd.DataFrame, text_col: str) -> str:
    """Reconstruct full MD&A text from sorted sentences."""
    g = group_df.sort_values("sentence_order_num")
    sentences = g[text_col].fillna("").astype(str).tolist()
    text = " ".join(sentences)
    return re.sub(r"\s+", " ", text).strip()


def make_user_prompt(doc_text: str, doc_id: str, doc_meta: str = "") -> str:
    return f"""Analyze the following MD&A text and count AI-related sentences.

Document ID: {doc_id}
{doc_meta}

MD&A TEXT:
{doc_text}

Return a JSON object with exact integer counts for each AI disclosure category.
""".strip()


# ============================================================
# 5. API CLIENT
# ============================================================
def make_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", None)
    if not api_key:
        print("[ERROR] OPENAI_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)
    kwargs: Dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


client = make_client()


def classify_one_document(doc_text: str, doc_id: str, doc_meta: str = "") -> dict:
    user_prompt = make_user_prompt(doc_text, doc_id, doc_meta)
    last_err = None
    for attempt in range(RETRY_TIMES):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "DocumentClassification",
                        "schema": DOCUMENT_JSON_SCHEMA,
                        "strict": True,
                    },
                },
                temperature=0.0,
            )
            content = response.choices[0].message.content
            parsed = json.loads(content)
            # Validate with Pydantic
            validated = DocumentClassification(**parsed)
            return {
                "n_generic_ai_sentences": validated.n_generic_ai_sentences,
                "n_substantive_implementation_sentences": validated.n_substantive_implementation_sentences,
                "n_substantive_risk_governance_sentences": validated.n_substantive_risk_governance_sentences,
                "n_total_ai_sentences": validated.n_total_ai_sentences,
                "has_ai_mention": validated.has_ai_mention,
                "rationale": validated.rationale,
                "api_model": MODEL_NAME,
                "api_status": "ok",
                "truncated": len(doc_text.split()) >= MAX_DOC_WORDS,
            }
        except Exception as e:
            last_err = str(e)
            wait_s = min(2 ** attempt, 8)
            time.sleep(wait_s)

    return {
        "n_generic_ai_sentences": 0,
        "n_substantive_implementation_sentences": 0,
        "n_substantive_risk_governance_sentences": 0,
        "n_total_ai_sentences": 0,
        "has_ai_mention": False,
        "rationale": f"API_ERROR: {last_err}",
        "api_model": MODEL_NAME,
        "api_status": "error",
        "truncated": len(doc_text.split()) >= MAX_DOC_WORDS,
    }


# ============================================================
# 6. CHECKPOINT / RESUME
# ============================================================
def load_checkpoint(checkpoint_path: str) -> set:
    """Load set of already-processed document IDs."""
    if not os.path.exists(checkpoint_path):
        return set()
    done = set()
    with open(checkpoint_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                done.add(obj.get("doc_id", ""))
            except Exception:
                continue
    return done


def append_checkpoint(checkpoint_path: str, record: dict):
    with open(checkpoint_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ============================================================
# 7. MAIN PIPELINE
# ============================================================
def run_pipeline():
    print("=" * 60)
    print("Document-Level AI Disclosure Classification Pipeline")
    print("=" * 60)

    if not MODEL_NAME:
        print("[ERROR] MODEL_NAME env var is required. Example: export MODEL_NAME=gpt-4o-mini")
        sys.exit(1)

    print(f"[CONFIG] Model: {MODEL_NAME}")
    print(f"[CONFIG] Workers: {MAX_WORKERS}")
    print(f"[CONFIG] Max doc words: {MAX_DOC_WORDS}")
    print(f"[CONFIG] Input: {INPUT_PATH}")
    print()

    print("[1/6] Reading input file...")
    df = pd.read_json(INPUT_PATH, lines=True)
    print(f"        Total sentences: {len(df):,}")

    text_col = "sentence_clean" if "sentence_clean" in df.columns else "sentence_raw"
    if text_col not in df.columns:
        raise ValueError("Input must contain 'sentence_clean' or 'sentence_raw' column.")

    # Ensure sentence_order exists
    if "sentence_order" not in df.columns:
        df["sentence_order"] = np.arange(len(df))
    df["sentence_order_num"] = pd.to_numeric(df["sentence_order"], errors="coerce")
    nan_mask = df["sentence_order_num"].isna()
    if nan_mask.any():
        df.loc[nan_mask, "sentence_order_num"] = np.arange(nan_mask.sum()) + 10_000_000

    # Build document groups
    group_keys = [c for c in ["cik", "accession_number", "filing_date", "fiscal_year"] if c in df.columns]
    if not group_keys:
        raise ValueError("Need at least one document identifier column (cik, accession_number, etc.)")

    print("[2/6] Grouping sentences into documents...")
    grouped = {
        k: g.sort_values("sentence_order_num").copy()
        for k, g in df.groupby(group_keys, dropna=False, sort=False)
    }
    print(f"        Total documents: {len(grouped):,}")

    # Identify documents with AI candidates (quick keyword check)
    ai_keywords = [
        "artificial intelligence", "machine learning", "deep learning",
        "computer vision", "natural language processing",
        "large language model", "large language models", "llm", "llms",
        "generative ai", "genai", "a.i.",
        "business intelligence", "big data", "data science", "ai/ml",
        "data mining", "chatbot", "image recognition", "object recognition",
        "machine translation", "support vector machine",
        "classification algorithm", "classification algorithms",
        "supervised learning", "clustering algorithm", "clustering algorithms",
        "recommender system", "recommender systems",
        "dimensionality reduction", "information extraction",
        "kernel method", "kernel methods", "unsupervised learning",
        "predictive model", "predictive models",
        "algorithmic pricing", "autonomous system", "autonomous systems",
        "computational linguistics", "data scientist",
    ]
    ai_pattern = re.compile("|".join(ai_keywords), flags=re.IGNORECASE)

    docs_to_classify = []
    for doc_key, gdf in grouped.items():
        full_text = build_document_text(gdf, text_col)
        if ai_pattern.search(full_text):
            docs_to_classify.append((doc_key, gdf))

    print(f"        Documents with AI keywords: {len(docs_to_classify):,}")
    print()

    # Load checkpoint
    print("[3/6] Loading checkpoint...")
    done_ids = load_checkpoint(CHECKPOINT_PATH)
    print(f"        Already processed: {len(done_ids):,}")

    # Filter out already done
    remaining = [(k, g) for k, g in docs_to_classify if str(k) not in done_ids]
    print(f"        Remaining: {len(remaining):,}")
    print()

    if not remaining:
        print("[INFO] All documents already processed. Generating outputs...")
    else:
        print("[4/6] Classifying documents with API...")
        # Concurrent classification
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {}
            for doc_key, gdf in remaining:
                full_text = build_document_text(gdf, text_col)
                truncated_text = truncate_mdna(full_text, MAX_DOC_WORDS)
                doc_id = str(doc_key)

                # Build metadata string
                meta_parts = []
                for col in ["cik", "company_name", "filing_date", "fiscal_year"]:
                    if col in gdf.columns:
                        val = safe_text(gdf[col].iloc[0])
                        if val:
                            meta_parts.append(f"{col}: {val}")
                doc_meta = "\n".join(meta_parts)

                future = executor.submit(
                    classify_one_document, truncated_text, doc_id, doc_meta
                )
                futures[future] = (doc_key, gdf, doc_id)

            results = []
            pbar = tqdm(total=len(remaining), desc="Documents")
            for future in as_completed(futures):
                doc_key, gdf, doc_id = futures[future]
                try:
                    result = future.result()
                except Exception as e:
                    result = {
                        "n_generic_ai_sentences": 0,
                        "n_substantive_implementation_sentences": 0,
                        "n_substantive_risk_governance_sentences": 0,
                        "n_total_ai_sentences": 0,
                        "has_ai_mention": False,
                        "rationale": f"FUTURE_ERROR: {e}",
                        "api_model": MODEL_NAME,
                        "api_status": "error",
                        "truncated": False,
                    }

                # Add document metadata
                record = {
                    "doc_id": doc_id,
                    **result,
                }
                for col in ["cik", "company_name", "gvkey", "ticker", "filing_date", "fiscal_year"]:
                    if col in gdf.columns:
                        record[col] = safe_text(gdf[col].iloc[0])

                # Total sentences in document
                record["n_total_sentences"] = len(gdf)

                results.append(record)
                append_checkpoint(CHECKPOINT_PATH, record)

                if SLEEP_SEC > 0:
                    time.sleep(SLEEP_SEC)

                pbar.update(1)
            pbar.close()

        print(f"        Classified {len(results):,} documents in this run.")
        print()

    # ============================================================
    # 8. MERGE & OUTPUT
    # ============================================================
    print("[5/6] Building output DataFrame...")

    # Load all checkpoint records
    all_records = []
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    all_records.append(json.loads(line))
                except Exception:
                    continue

    if not all_records:
        print("[WARNING] No records found. Nothing to output.")
        return

    doc_df = pd.DataFrame(all_records)

    # Deduplicate by doc_id (keep last)
    doc_df = doc_df.drop_duplicates(subset=["doc_id"], keep="last")

    # Compute shares
    doc_df["substantive_ai_sentences"] = (
        doc_df["n_substantive_implementation_sentences"]
        + doc_df["n_substantive_risk_governance_sentences"]
    )
    doc_df["all_ai_sentences"] = (
        doc_df["n_generic_ai_sentences"] + doc_df["substantive_ai_sentences"]
    )

    # Shares (all_ai_sentences as denominator)
    doc_df["generic_ai_share"] = doc_df["n_generic_ai_sentences"] / doc_df["all_ai_sentences"].replace(0, np.nan)
    doc_df["substantive_ai_share"] = doc_df["substantive_ai_sentences"] / doc_df["all_ai_sentences"].replace(0, np.nan)
    doc_df["substantive_impl_share"] = doc_df["n_substantive_implementation_sentences"] / doc_df["all_ai_sentences"].replace(0, np.nan)
    doc_df["substantive_risk_share"] = doc_df["n_substantive_risk_governance_sentences"] / doc_df["all_ai_sentences"].replace(0, np.nan)

    # Fill NaN shares with 0
    for col in ["generic_ai_share", "substantive_ai_share", "substantive_impl_share", "substantive_risk_share"]:
        doc_df[col] = doc_df[col].fillna(0.0)

    # Dummies
    doc_df["has_generic_ai"] = (doc_df["n_generic_ai_sentences"] > 0).astype(int)
    doc_df["has_substantive_implementation"] = (doc_df["n_substantive_implementation_sentences"] > 0).astype(int)
    doc_df["has_substantive_risk"] = (doc_df["n_substantive_risk_governance_sentences"] > 0).astype(int)
    doc_df["has_any_ai_disclosure"] = (doc_df["all_ai_sentences"] > 0).astype(int)

    # API status
    doc_df["api_success"] = (doc_df["api_status"] == "ok").astype(int)

    # Select output columns
    out_cols = [
        "doc_id", "cik", "company_name", "gvkey", "ticker",
        "filing_date", "fiscal_year",
        "n_total_sentences",
        "n_total_ai_sentences",
        "n_generic_ai_sentences",
        "n_substantive_implementation_sentences",
        "n_substantive_risk_governance_sentences",
        "substantive_ai_sentences",
        "all_ai_sentences",
        "generic_ai_share",
        "substantive_ai_share",
        "substantive_impl_share",
        "substantive_risk_share",
        "has_generic_ai",
        "has_substantive_implementation",
        "has_substantive_risk",
        "has_any_ai_disclosure",
        "has_ai_mention",
        "truncated",
        "api_status",
        "api_success",
        "api_model",
        "rationale",
    ]
    out_cols = [c for c in out_cols if c in doc_df.columns]
    doc_df = doc_df[out_cols]

    doc_df.to_csv(DOC_OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"        Saved: {DOC_OUTPUT_CSV}")

    # ============================================================
    # 9. SUMMARY
    # ============================================================
    print("[6/6] Writing summary...")

    total_docs = len(doc_df)
    success_docs = doc_df["api_success"].sum()
    ai_docs = doc_df["has_any_ai_disclosure"].sum()
    generic_docs = doc_df["has_generic_ai"].sum()
    impl_docs = doc_df["has_substantive_implementation"].sum()
    risk_docs = doc_df["has_substantive_risk"].sum()

    total_ai_sentences = doc_df["all_ai_sentences"].sum()
    total_generic = doc_df["n_generic_ai_sentences"].sum()
    total_impl = doc_df["n_substantive_implementation_sentences"].sum()
    total_risk = doc_df["n_substantive_risk_governance_sentences"].sum()

    summary = {
        "total_documents": total_docs,
        "api_success": int(success_docs),
        "api_errors": int(total_docs - success_docs),
        "documents_with_any_ai_disclosure": int(ai_docs),
        "documents_with_generic_ai": int(generic_docs),
        "documents_with_substantive_implementation": int(impl_docs),
        "documents_with_substantive_risk": int(risk_docs),
        "total_ai_sentences_across_all_docs": int(total_ai_sentences),
        "total_generic_sentences": int(total_generic),
        "total_implementation_sentences": int(total_impl),
        "total_risk_sentences": int(total_risk),
        "mean_generic_share": round(doc_df["generic_ai_share"].mean(), 4),
        "mean_substantive_share": round(doc_df["substantive_ai_share"].mean(), 4),
        "mean_substantive_impl_share": round(doc_df["substantive_impl_share"].mean(), 4),
        "mean_substantive_risk_share": round(doc_df["substantive_risk_share"].mean(), 4),
        "model": MODEL_NAME,
    }

    pd.DataFrame([summary]).to_csv(SUMMARY_OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"        Saved: {SUMMARY_OUTPUT_CSV}")
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print("=" * 60)


if __name__ == "__main__":
    run_pipeline()
