#!/usr/bin/env python3
"""
Full Qwen Classification: Substantive vs Generic AI Disclosure
===============================================================
Based on group classification guidelines (定义.pdf).
Classifies all ~15,639 AI sentences extracted from S&P 500 10-K MD&A sections.
Uses Qwen-plus via DashScope API with concurrent workers.
"""

import os
import json
import time
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from openai import OpenAI

sys.stdout.reconfigure(line_buffering=True)

# ============================================================
# Config
# ============================================================
load_dotenv(Path(__file__).parent / ".env")

API_KEY  = os.environ["QWEN_API_KEY"]
BASE_URL = os.environ["QWEN_BASE_URL"]
MODEL    = "qwen-plus"
MAX_WORKERS = 10

EXTRACTS_FILE = Path(__file__).parent / "sp500_mda_ai_extracts.jsonl"
OUTPUT_FILE   = Path(__file__).parent / "sp500_ai_classified.jsonl"
CHECKPOINT_FILE = Path(__file__).parent / ".classification_checkpoint"

# ============================================================
# Classification Prompt — based on 定义.pdf
# ============================================================
SYSTEM_PROMPT = """You are a financial analyst specializing in corporate AI disclosure analysis.
Classify each sentence from a 10-K MD&A section as either SUBSTANTIVE or GENERIC AI disclosure.

## DEFINITIONS

### SUBSTANTIVE AI Disclosure
The disclosure has clear, specific, identifiable business content about AI usage. 
It answers at least ONE of:
- WHERE the company uses AI (specific business area)
- WHAT the company aims to achieve with AI
- HOW AI affects revenue, cost, efficiency, innovation, or risk
- WHAT specific AI risks the company faces and their sources

The core question is NOT "does AI appear" but "does it tell the reader what AI actually does?"

**Six types of substantive disclosure:**

1. **Product Development**: AI used for new product design, performance improvement, R&D testing, or innovation processes.
   Example: "The company uses machine learning models to improve drug screening."

2. **AI Product Provider**: The company itself provides AI products, services, or platforms to customers.
   Example: "The company provides AI-driven data analytics platforms to clients."

3. **Pricing Optimization**: AI used for dynamic pricing, demand-responsive pricing, or market price adjustment.
   Example: "The company uses AI models to automatically adjust prices based on real-time market data."

4. **Inventory Management**: AI used for demand forecasting, replenishment, inventory optimization, or supply chain coordination.
   Example: "The company uses AI to predict demand and optimize inventory turnover."

5. **Operational Efficiency**: AI used for process automation, improving internal efficiency, reducing labor costs, optimizing workflows, or improving daily operations.
   Example: "The company uses AI to automatically handle customer service requests to reduce response time."

6. **AI Risk Disclosure**: The company specifically identifies sources and consequences of AI-related risks (regulatory, operational, competitive, cybersecurity, ethical, third-party dependency).
   Example: "New regulations around AI may require the company to modify products and business processes, increasing compliance costs."

### GENERIC AI Disclosure
The company mentions AI but the expression stays at a general, broad, or promotional level. It lacks specific application scenarios, business mechanisms, risk sources, or verifiable business content.

**Common patterns:**
- Pure conceptual statements: "AI is profoundly changing the industry, and the company will actively seize AI opportunities."
- Strategic vision rhetoric: "We are committed to being at the forefront of AI innovation."
- Vague technology stacking: "The company combines AI, big data, digitalization, and smart analytics to drive transformation." (lists buzzwords without specifying what AI actually does)
- Non-specific risk statements: "AI may bring certain risks and uncertainties." (no specific risk source identified)

## KEY PRINCIPLES

1. **Context matters**: Read the full sentence and its meaning, not just keywords.
2. **First verify AI relevance**: Some sentences contain AI keywords but are not actually disclosing AI activities (e.g., listing AI as part of general industry background). If the sentence is NOT truly about the company's own AI activities, classify as "generic".
3. **Do NOT infer or supplement logic**: Do not assume AI purposes based on common sense. If a sentence says "the company is building AI capabilities," you CANNOT classify it as Operational Efficiency just because "capability building" sounds like it. ONLY classify as substantive when the text EXPLICITLY states what AI is used for.
4. **Map to categories**: If the text can be mapped to one of the 6 substantive types above → substantive. If it only shows "the company mentioned AI" without specific business function or risk mechanism → generic.

## SUMMARY RULE
If the sentence can answer "What does AI specifically do, where does it apply, what result does it affect?" → SUBSTANTIVE.
If the sentence only shows "the company mentioned AI" without identifiable business function or risk mechanism → GENERIC.

## RESPONSE FORMAT
Respond ONLY with valid JSON:
{"classification": "substantive" | "generic", "confidence": 0.0-1.0, "reason": "one sentence explanation in English"}"""


# ============================================================
# Build sentence queue
# ============================================================

def build_sentence_queue():
    """Flatten all AI sentences into a list of work items."""
    sentences = []
    with open(EXTRACTS_FILE) as f:
        for line in f:
            filing = json.loads(line)
            if "error" in filing or not filing.get("ai_sentences"):
                continue
            ticker = filing["ticker"]
            accession = filing["accession"]
            year = filing.get("year", "unknown")
            for idx, item in enumerate(filing["ai_sentences"]):
                key = f"{ticker}_{accession}_{idx}"
                sentences.append({
                    "sentence_key": key,
                    "ticker": ticker,
                    "accession": accession,
                    "year": year,
                    "sentence_idx": idx,
                    "sentence": item["sentence"][:2000],
                    "matched_keywords": item.get("matched_keywords", []),
                })
    return sentences


# ============================================================
# Classification
# ============================================================

def make_client():
    return OpenAI(api_key=API_KEY, base_url=BASE_URL)

def classify_one(item):
    """Classify one sentence."""
    client = make_client()
    sentence = item["sentence"]
    
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f'Sentence: "{sentence}"'}
                ],
                temperature=0,
                max_tokens=200,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            result = json.loads(raw)
            return (item["sentence_key"], {
                "classification": result.get("classification", "error"),
                "confidence": result.get("confidence", 0),
                "reason": result.get("reason", ""),
            })
        except json.JSONDecodeError:
            return (item["sentence_key"], {
                "classification": "error", "confidence": 0,
                "reason": "JSON parse error",
            })
        except Exception as e:
            wait = 2 ** attempt
            time.sleep(wait)
    
    return (item["sentence_key"], {
        "classification": "error", "confidence": 0,
        "reason": "max retries exceeded",
    })


# ============================================================
# Main
# ============================================================

def main():
    # Load checkpoint
    done_keys = set()
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            done_keys = set(json.load(f))
        print(f"Resuming: {len(done_keys)} sentences already classified")
    
    # Build queue
    print("Building sentence queue...")
    all_sentences = build_sentence_queue()
    total = len(all_sentences)
    print(f"Total sentences: {total:,}")
    
    # Filter done
    work = [s for s in all_sentences if s["sentence_key"] not in done_keys]
    remaining = len(work)
    print(f"To classify: {remaining:,}")
    
    # Stats
    stats = {"substantive": 0, "generic": 0, "errors": 0}
    
    # Open output file
    mode = "a" if done_keys else "w"
    start_time = time.time()
    processed = len(done_keys)
    
    print(f"\nStarting classification with {MAX_WORKERS} workers...\n")
    
    with open(OUTPUT_FILE, mode) as out:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            batch_size = 200
            for batch_start in range(0, len(work), batch_size):
                batch = work[batch_start:batch_start + batch_size]
                futures = {executor.submit(classify_one, item): item for item in batch}
                
                for future in as_completed(futures):
                    key, result = future.result()
                    
                    # Find the original item
                    item = next((s for s in all_sentences if s["sentence_key"] == key), {})
                    
                    record = {
                        "sentence_key": key,
                        "ticker": item.get("ticker", ""),
                        "accession": item.get("accession", ""),
                        "year": item.get("year", ""),
                        "sentence_idx": item.get("sentence_idx", 0),
                        "sentence": item.get("sentence", "")[:1000],
                        "matched_keywords": item.get("matched_keywords", []),
                        "classification": result["classification"],
                        "confidence": result["confidence"],
                        "reason": result["reason"],
                        "model": MODEL,
                    }
                    out.write(json.dumps(record, ensure_ascii=False) + "\n")
                    out.flush()
                    
                    done_keys.add(key)
                    cls = result["classification"]
                    if cls == "substantive":
                        stats["substantive"] += 1
                    elif cls == "generic":
                        stats["generic"] += 1
                    else:
                        stats["errors"] += 1
                    
                    processed += 1
                    
                    # Progress every 500
                    if processed % 500 == 0:
                        elapsed = time.time() - start_time
                        rate = processed / elapsed * 60 if elapsed > 0 else 0
                        eta_min = (total - processed) / max(rate, 0.001)
                        pct = processed / total * 100
                        print(f"  [{processed:,}/{total:,}] ({pct:.1f}%) | "
                              f"S:{stats['substantive']} G:{stats['generic']} E:{stats['errors']} | "
                              f"{rate:.0f}/min | ETA: {eta_min:.0f}min")
                    
                    # Checkpoint every 500
                    if processed % 500 == 0:
                        with open(CHECKPOINT_FILE, 'w') as cf:
                            json.dump(list(done_keys), cf)
    
    elapsed = time.time() - start_time
    rate = processed / elapsed * 60 if elapsed > 0 else 0
    
    print(f"\n{'='*60}")
    print(f"Classification Complete!")
    print(f"  Total: {processed:,}")
    print(f"  Substantive: {stats['substantive']:,} ({stats['substantive']/processed*100:.1f}%)")
    print(f"  Generic:     {stats['generic']:,} ({stats['generic']/processed*100:.1f}%)")
    print(f"  Errors:      {stats['errors']:,}")
    print(f"  Speed: {rate:.0f} sentences/min")
    print(f"  Time: {elapsed/60:.1f} minutes")
    print(f"  Output: {OUTPUT_FILE}")
    print(f"{'='*60}")
    
    # Cleanup checkpoint
    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()


if __name__ == '__main__':
    main()
