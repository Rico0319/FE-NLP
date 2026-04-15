# ============================================================
#  step3_classify.py  —  GPT批量分类：substantive vs generic
# ============================================================

import os
import json
import time
from openai import OpenAI
from config import (
    EXTRACTS_FILE, CLASSIFIED_FILE,
    OPENAI_MODEL, OPENAI_MINI_MODEL,
    OPENAI_MAX_TOKENS, OPENAI_DELAY
)

client = OpenAI()   # 读取环境变量 OPENAI_API_KEY

# ------------------------------------------------------------------
# Prompt设计
# 加了few-shot示例，显著提升一致性
# ------------------------------------------------------------------
SYSTEM_PROMPT = """You are a financial analyst specializing in M&A disclosures.
Your task: classify whether a sentence from an M&A section of a 10-K annual report 
contains SUBSTANTIVE or GENERIC AI disclosure.

Definitions:
- "substantive": Specific, concrete AI information tied to M&A activity.
  Indicators: named AI technology/product acquired, quantified AI synergies,
  specific AI capability that drove deal rationale, integration of named AI systems.
  
- "generic": Vague, boilerplate, or marketing language about AI with no M&A specifics.
  Indicators: "leveraging AI", "AI-enabled solutions", "committed to AI innovation",
  "AI-driven value creation" — without concrete deal-specific details.

Examples:
[SUBSTANTIVE] "The acquisition of DeepMind-based startup XYZ provides proprietary 
 computer vision models that will replace our manual quality inspection processes, 
 targeting $50M in annual cost savings."
 → Reason: Names specific technology, quantifies synergy, links to deal rationale.

[GENERIC] "We continue to explore acquisitions that leverage artificial intelligence 
 to enhance our competitive position."
 → Reason: No specific deal, technology, or quantification.

[SUBSTANTIVE] "The acquired entity's LLM-powered contract analysis tool processes 
 over 10,000 legal documents daily, eliminating the need for three acquired 
 subsidiary legal teams."
 → Reason: Named technology (LLM), specific use case, quantified operational impact.

[GENERIC] "Post-merger integration will incorporate AI and machine learning 
 capabilities to drive operational efficiencies."
 → Reason: Vague, no specifics on which AI, which operations, or expected impact.

Respond ONLY with valid JSON (no markdown):
{"classification": "substantive" | "generic", "confidence": 0.0-1.0, "reason": "one sentence"}"""


def classify_one(sentence: str, use_mini: bool = False) -> dict:
    """调用GPT分类单条句子，带指数退避重试"""
    model = OPENAI_MINI_MODEL if use_mini else OPENAI_MODEL

    for attempt in range(4):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": f'Sentence: "{sentence}"'}
                ],
                temperature=0,
                max_tokens=OPENAI_MAX_TOKENS,
                response_format={"type": "json_object"}
            )
            raw = response.choices[0].message.content
            result = json.loads(raw)
            result["model_used"] = model
            return result
        except json.JSONDecodeError:
            return {"classification": "error", "confidence": 0,
                    "reason": "JSON parse error", "model_used": model}
        except Exception as e:
            wait = 2 ** attempt
            print(f"    API error (attempt {attempt+1}): {e}. Retrying in {wait}s...")
            time.sleep(wait)

    return {"classification": "error", "confidence": 0,
            "reason": "max retries exceeded", "model_used": model}


def run_classification(two_pass: bool = True):
    """
    two_pass=True:
      Pass 1 → gpt-4o-mini 快速分类所有句子（便宜）
      Pass 2 → gpt-4o 复核 confidence < 0.75 的结果（精准）
    two_pass=False:
      直接全用 gpt-4o
    """
    if not os.path.exists(EXTRACTS_FILE):
        print(f"ERROR: {EXTRACTS_FILE} not found. Run step2_extract.py first.")
        return

    # 读取已处理记录（断点续跑）
    done_keys = set()
    if os.path.exists(CLASSIFIED_FILE):
        with open(CLASSIFIED_FILE) as f:
            for line in f:
                rec = json.loads(line)
                done_keys.add((rec["ticker"], rec["accession"], rec["sentence_idx"]))
        print(f"Resuming: {len(done_keys)} sentences already classified")

    total = 0
    substantive = 0
    generic = 0

    with open(CLASSIFIED_FILE, "a") as out:
        with open(EXTRACTS_FILE) as f:
            for line in f:
                filing = json.loads(line)

                if "error" in filing or not filing.get("ai_sentences"):
                    continue

                ticker    = filing["ticker"]
                accession = filing["accession"]
                year      = filing.get("year", "unknown")

                for idx, item in enumerate(filing["ai_sentences"]):
                    key = (ticker, accession, idx)
                    if key in done_keys:
                        continue

                    sentence = item["sentence"]
                    keywords = item["matched_keywords"]

                    # Pass 1: mini model
                    if two_pass:
                        result = classify_one(sentence, use_mini=True)
                        # Pass 2: re-check low confidence with full model
                        if (result.get("confidence", 1) < 0.75
                                or result.get("classification") == "error"):
                            time.sleep(OPENAI_DELAY)
                            result = classify_one(sentence, use_mini=False)
                    else:
                        result = classify_one(sentence, use_mini=False)

                    record = {
                        "ticker":           ticker,
                        "accession":        accession,
                        "year":             year,
                        "sentence_idx":     idx,
                        "sentence":         sentence,
                        "matched_keywords": keywords,
                        "classification":   result.get("classification"),
                        "confidence":       result.get("confidence"),
                        "reason":           result.get("reason"),
                        "model_used":       result.get("model_used"),
                        # 传入分母，供后续密度计算
                        "mda_sentence_count": filing.get("mda_sentence_count", 0),
                        "ma_sentence_count":  filing.get("ma_sentence_count", 0),
                        "total_ai_count":     filing.get("ai_sentence_count", 0),
                    }

                    out.write(json.dumps(record) + "\n")
                    out.flush()

                    cls = result.get("classification", "error")
                    total += 1
                    if cls == "substantive": substantive += 1
                    elif cls == "generic":   generic += 1

                    print(f"  {ticker} {year} [{idx}] → {cls} "
                          f"(conf:{result.get('confidence','?')}) | {keywords}")

                    time.sleep(OPENAI_DELAY)

    print(f"\n[Step 3 Done] Classified {total} sentences")
    print(f"  Substantive: {substantive} | Generic: {generic} | "
          f"Error/Other: {total - substantive - generic}")
    print(f"  Results → {CLASSIFIED_FILE}")


if __name__ == "__main__":
    run_classification(two_pass=True)
