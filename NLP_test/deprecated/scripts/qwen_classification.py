#!/usr/bin/env python3
"""
AI Sentence Classification using Qwen via DashScope
====================================================
Classifies extracted AI sentences as substantive vs generic M&A disclosure.
Uses OpenAI-compatible API (DashScope).
"""

import os, json, time
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
from openai import OpenAI

# ============================================================
# Config — loaded from .env
# ============================================================
load_dotenv(Path(__file__).parent / ".env")

API_KEY  = os.environ["QWEN_API_KEY"]
BASE_URL = os.environ["QWEN_BASE_URL"]
MODEL    = "qwen-plus"  # or qwen-max

SENTENCES_CSV = "/home/ricoz/econ_lab/FE-NLP/NLP_test/ai_sentences_sample.csv"
OUTPUT_JSONL = "/home/ricoz/econ_lab/FE-NLP/NLP_test/qwen_classified.jsonl"

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# ============================================================
# Prompt — same logic as ma_pipeline step3, adapted for AI disclosure
# ============================================================
SYSTEM_PROMPT = """You are a financial analyst specializing in corporate disclosures.
Your task: classify whether a sentence from a company's MD&A section contains SUBSTANTIVE or GENERIC AI disclosure.

Definitions:
- "substantive": Specific, concrete AI information.
  Indicators: named AI technology/product, specific AI use case, quantified AI impact,
  specific AI implementation details, concrete AI strategy tied to business operations.

- "generic": Vague, boilerplate, or marketing language about AI.
  Indicators: "leveraging AI", "AI-enabled solutions", "committed to AI innovation",
  "AI-driven value creation" — without concrete specifics.
  Also includes risk factor boilerplate that mentions AI only in passing.

Respond ONLY with valid JSON (no markdown code blocks):
{"classification": "substantive" | "generic", "confidence": 0.0-1.0, "reason": "one sentence explanation"}"""


def classify_sentence(sentence: str) -> dict:
    """Classify one sentence using Qwen."""
    for attempt in range(4):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f'Sentence: "{sentence}"'}
                ],
                temperature=0,
                max_tokens=200,
                response_format={"type": "json_object"}
            )
            raw = response.choices[0].message.content.strip()
            # Strip markdown code blocks if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            result = json.loads(raw)
            result["model"] = MODEL
            result["api_error"] = None
            return result
        except json.JSONDecodeError as e:
            return {"classification": "error", "confidence": 0,
                    "reason": f"JSON parse error: {raw[:100]}", "model": MODEL, "api_error": str(e)}
        except Exception as e:
            wait = 2 ** attempt
            print(f"    API error (attempt {attempt+1}): {e}")
            time.sleep(wait)
    return {"classification": "error", "confidence": 0,
            "reason": "max retries exceeded", "model": MODEL}


def main():
    df = pd.read_csv(SENTENCES_CSV)
    print(f"Loaded {len(df)} AI sentences for classification")
    print(f"Using model: {MODEL} at {BASE_URL}")

    # Quick connectivity test
    print("\nTesting API connection...")
    try:
        test = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "Say 'OK' in one word."}],
            temperature=0, max_tokens=10
        )
        print(f"  ✅ Connected! Response: {test.choices[0].message.content.strip()}")
    except Exception as e:
        print(f"  ❌ Connection failed: {e}")
        return

    # Classify
    done = set()
    if os.path.exists(OUTPUT_JSONL):
        with open(OUTPUT_JSONL) as f:
            for line in f:
                rec = json.loads(line)
                done.add(rec.get('_idx', -1))
        print(f"Resuming: {len(done)} sentences already classified")

    results = []
    substantive = 0
    generic = 0
    errors = 0

    with open(OUTPUT_JSONL, "a") as out:
        for i, row in df.iterrows():
            if i in done:
                continue

            sentence = str(row['sentence'])
            print(f"\n[{i}/{len(df)}] {row['ticker']} ({row['year']}) | kw: {row['keywords']}")

            result = classify_sentence(sentence)

            record = {
                '_idx': i,
                'ticker': row['ticker'],
                'company': row['company'],
                'year': int(row['year']),
                'industry': row['industry'],
                'keywords': row['keywords'],
                'sentence': sentence,
                'classification': result.get('classification'),
                'confidence': result.get('confidence'),
                'reason': result.get('reason'),
                'model': result.get('model'),
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()

            cls = result.get('classification')
            if cls == 'substantive':
                substantive += 1
                print(f"  → SUBSTANTIVE (conf={result.get('confidence')})")
            elif cls == 'generic':
                generic += 1
                print(f"  → GENERIC (conf={result.get('confidence')})")
            else:
                errors += 1
                print(f"  → ERROR: {result.get('reason')}")

            # Rate limit friendly
            time.sleep(0.5)

    print(f"\n{'='*50}")
    print(f"Classification complete!")
    print(f"  Substantive: {substantive}")
    print(f"  Generic:     {generic}")
    print(f"  Errors:      {errors}")
    print(f"  Output: {OUTPUT_JSONL}")

    # Summary table
    cls_df = pd.read_json(OUTPUT_JSONL, lines=True)
    print(f"\n--- By Company ---")
    print(cls_df.groupby('ticker')['classification'].value_counts().unstack(fill_value=0).to_string())
    print(f"\n--- By Year ---")
    print(cls_df.groupby('year')['classification'].value_counts().unstack(fill_value=0).to_string())
    print(f"\n--- By Keyword Type ---")
    print(cls_df.groupby('keywords')['classification'].value_counts().unstack(fill_value=0).to_string())


if __name__ == '__main__':
    main()
