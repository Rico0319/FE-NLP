#!/usr/bin/env python3
"""
Full S&P 500 MD&A Extraction + AI Sentence Filtering
=====================================================
Processes all 3,362 downloaded 10-K filings:
1. Extracts Item 7 (MD&A) section
2. Finds AI keyword mentions
3. Extracts AI-containing sentences
4. Outputs structured JSONL for downstream GPT/Qwen classification

Output: sp500_mda_ai_extracts.jsonl
"""

import os
import re
import json
import sys
import time
from pathlib import Path
from bs4 import BeautifulSoup

sys.stdout.reconfigure(line_buffering=True)

# ============================================================
# Config
# ============================================================
FILING_ROOT = Path(__file__).parent / "sec_filings_full" / "sec-edgar-filings"
OUTPUT_FILE = Path(__file__).parent / "sp500_mda_ai_extracts.jsonl"

# AI Keywords (same as ma_pipeline)
AI_KEYWORDS = [
    "artificial intelligence", "machine learning", "deep learning",
    "large language model", "llm", "generative ai", "genai",
    "neural network", "natural language processing", "nlp",
    "chatgpt", "gpt-4", "gpt-3", "openai", "claude", "gemini",
    "copilot", "predictive model", "computer vision",
    "algorithm", "automation", "robotic process automation", "rpa",
    "intelligent automation",
]

# Pre-compile patterns for speed
AI_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(k) for k in AI_KEYWORDS) + r')\b',
    re.IGNORECASE
)

# MD&A section boundary patterns
ITEM7_START = [
    r"item\s*7[\.\:–\-]?\s*management.{0,30}discussion",
    r"item\s*7[\.\:–\-]?\s*md&a",
    r"management.{0,10}discussion\s*and\s*analysis\s*of",
]
ITEM8_START = [
    r"item\s*8[\.\:–\-]?\s*financial\s*statements",
    r"item\s*8[\.\:–\-]?\s*consolidated\s*financial",
]

# ============================================================
# Text Processing
# ============================================================

def parse_htm(filepath: str) -> str:
    """HTM/HTML → clean text"""
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    # Handle XML filings (.txt with XML structure)
    if '<XML>' in content:
        # For inline XML filings, extract text more carefully
        soup = BeautifulSoup(content, "lxml-xml")
    else:
        soup = BeautifulSoup(content, "lxml")
    
    for tag in soup(["script", "style", "ix:nonfraction", "ix:nonnumeric", "meta", "link"]):
        tag.decompose()
    
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r'\s{2,}', ' ', text)
    return text


def parse_txt(filepath: str) -> str:
    """Plain text / SGML filing → clean text"""
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    # Remove SGML tags
    content = re.sub(r'<[^>]+>', ' ', content)
    # Remove XBRL tags
    content = re.sub(r'<\w+:[^>]*?>', ' ', content)
    content = re.sub(r'</\w+:[^>]*?>', ' ', content)
    # Clean whitespace
    text = re.sub(r'\s{2,}', ' ', content)
    return text.strip()


def find_section(text: str, start_patterns: list, end_patterns: list) -> str:
    """Extract text between two pattern groups"""
    start_pos = None
    for pat in start_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            start_pos = m.start()
            break
    if start_pos is None:
        return ""
    
    search_from = start_pos + 200
    end_pos = len(text)
    for pat in end_patterns:
        m = re.search(pat, text[search_from:], re.IGNORECASE)
        if m:
            end_pos = search_from + m.start()
            break
    
    return text[start_pos:end_pos]


def split_sentences(text: str) -> list:
    """Split text into sentences (handles abbreviations)"""
    text = text.replace('\n', ' ').replace('\r', ' ')
    sentences = re.split(r'(?<!\b[A-Z][a-z])(?<!\b[A-Z])(?<=[.!?])\s+(?=[A-Z])', text)
    return [s.strip() for s in sentences if len(s.strip()) > 30]


def find_primary_document(filing_dir: str) -> str | None:
    """Find the main filing document (largest non-attachment file)"""
    files = os.listdir(filing_dir)
    
    # Try HTM/HTML first
    candidates = [
        f for f in files
        if f.lower().endswith((".htm", ".html"))
        and not re.match(r'^R\d+\.htm', f, re.IGNORECASE)
        and "fillingsummary" not in f.lower()
        and "filesummary" not in f.lower()
    ]
    if candidates:
        candidates.sort(
            key=lambda f: os.path.getsize(os.path.join(filing_dir, f)),
            reverse=True
        )
        return os.path.join(filing_dir, candidates[0])
    
    # Try TXT (full submission format)
    txt_files = [f for f in files if f.lower().endswith(".txt")]
    if txt_files:
        txt_files.sort(
            key=lambda f: os.path.getsize(os.path.join(filing_dir, f)),
            reverse=True
        )
        return os.path.join(filing_dir, txt_files[0])
    
    return None


def extract_filing_year(accession: str) -> str:
    """Extract year from accession number: 0000320193-24-000106 → 2024"""
    m = re.search(r'-(\d{2})-', accession)
    if m:
        yy = int(m.group(1))
        return str(2000 + yy if yy < 50 else 1900 + yy)
    return "unknown"


# ============================================================
# Process One Filing
# ============================================================

def process_filing(ticker: str, accession: str, filing_dir: str) -> dict | None:
    """Extract MD&A + AI sentences from one filing"""
    doc_path = find_primary_document(filing_dir)
    if not doc_path:
        return None
    
    try:
        if doc_path.endswith((".htm", ".html")):
            full_text = parse_htm(doc_path)
        else:
            full_text = parse_txt(doc_path)
    except Exception as e:
        return {"ticker": ticker, "accession": accession, "error": str(e)}
    
    # Extract MD&A
    mda_text = find_section(full_text, ITEM7_START, ITEM8_START)
    if not mda_text:
        mda_text = full_text  # fallback
    
    all_sentences = split_sentences(mda_text)
    
    # Find AI-containing sentences
    ai_sentences = []
    for sent in all_sentences:
        sent_lower = sent.lower()
        matches = AI_PATTERN.findall(sent_lower)
        if matches:
            ai_sentences.append({
                "sentence": sent[:500],
                "matched_keywords": list(set(m.lower() for m in matches)),
                "keyword_count": len(matches),
            })
    
    return {
        "ticker": ticker,
        "accession": accession,
        "year": extract_filing_year(accession),
        "mda_length": len(mda_text),
        "mda_sentence_count": len(all_sentences),
        "ai_sentence_count": len(ai_sentences),
        "ai_sentences": ai_sentences,
        "total_text_length": len(full_text),
    }


# ============================================================
# Main Loop
# ============================================================

def main():
    if not FILING_ROOT.is_dir():
        print(f"ERROR: {FILING_ROOT} not found!")
        return
    
    # Load company list if available
    company_list_path = FILING_ROOT.parent / "sp500_company_list.csv"
    company_info = {}
    if company_list_path.exists():
        import pandas as pd
        df = pd.read_csv(company_list_path)
        for _, row in df.iterrows():
            company_info[row['Symbol']] = {
                'name': row['Security'],
                'sector': row['GICS Sector'],
            }
    
    # Track already processed
    done = set()
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE) as f:
            for line in f:
                rec = json.loads(line)
                done.add((rec.get("ticker"), rec.get("accession")))
        print(f"Resuming: {len(done)} filings already processed")
    
    tickers = sorted(os.listdir(FILING_ROOT))
    total_filings = 0
    total_ai_filings = 0
    total_ai_sentences = 0
    errors = 0
    
    start_time = time.time()
    
    print(f"\nProcessing {len(tickers)} companies...\n")
    
    with open(OUTPUT_FILE, "a") as out:
        for i, ticker in enumerate(tickers):
            ticker_dir = FILING_ROOT / ticker / "10-K"
            if not ticker_dir.is_dir():
                continue
            
            for accession in sorted(os.listdir(ticker_dir)):
                if (ticker, accession) in done:
                    continue
                
                filing_dir = ticker_dir / accession
                if not filing_dir.is_dir():
                    continue
                
                result = process_filing(ticker, accession, str(filing_dir))
                if result is None:
                    errors += 1
                    continue
                
                out.write(json.dumps(result, ensure_ascii=False) + "\n")
                out.flush()
                
                total_filings += 1
                ai_count = result.get("ai_sentence_count", 0)
                if ai_count > 0:
                    total_ai_filings += 1
                    total_ai_sentences += ai_count
                
                if "error" in result:
                    errors += 1
                
                # Progress
                if total_filings % 100 == 0 or ai_count > 0:
                    elapsed = time.time() - start_time
                    rate = total_filings / max(elapsed, 1) * 60
                    print(f"  {ticker} {result.get('year',''):4s} | "
                          f"MDA:{result.get('mda_sentence_count',0):>5} sent | "
                          f"AI:{ai_count:>3} | "
                          f"[{total_filings} done | {rate:.0f}/min]")
            
            # Progress every 25 tickers
            if (i + 1) % 25 == 0:
                elapsed = time.time() - start_time
                eta_min = (len(tickers) - i - 1) / max(elapsed / max(i+1, 1), 0.001) / 60
                print(f"\n  ... {i+1}/{len(tickers)} tickers | "
                      f"{total_filings} filings | "
                      f"ETA: {eta_min:.0f}m\n")
    
    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"Extraction Complete!")
    print(f"  Total filings processed: {total_filings}")
    print(f"  Filings with AI mentions: {total_ai_filings}")
    print(f"  Total AI sentences: {total_ai_sentences}")
    print(f"  Errors: {errors}")
    print(f"  Time: {elapsed/60:.1f} minutes")
    print(f"  Output: {OUTPUT_FILE}")
    if OUTPUT_FILE.exists():
        size_mb = OUTPUT_FILE.stat().st_size / 1024 / 1024
        print(f"  File size: {size_mb:.1f} MB")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
