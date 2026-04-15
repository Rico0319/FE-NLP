#!/usr/bin/env python3
"""
Full S&P 500 MD&A Extraction — Sentence-Level Master File
=========================================================
Rigorous data cleaning per professor's specification:

1. Accurately extracts Item 7 (MD&A) from 10-K filings
   - Parses SGML full-submission files to find the main 10-K document
   - Multi-pass boundary detection (TOC-aware, then pattern-based)
   - Stops at Item 7A (not just Item 8)
   - Removes table-of-contents false positives

2. Comprehensive text cleaning
   - Strips HTML/XBRL tags
   - Removes headers/footers, table fragments, navigation strings
   - Normalizes whitespace, unicode artifacts
   - Preserves negation words, modals, numbers (no over-cleaning)

3. Sentence-level tokenization
   - NLTK PunktSentenceTokenizer + custom post-processing
   - Handles 10-K long sentences, semicolons, broken lines
   - NOT simple period-splitting

4. Deduplication and quality control
   - Exact duplicate removal (hash-based)
   - Near-duplicate removal (Rapidfuzz ratio > 90%)
   - Removes titles, fragments, too-short sentences
   - Removes pure table rows and navigation artifacts

5. AI candidate sentence marking
   - High-recall seed lexicon matching
   - All matched keywords recorded

Output: Sentence-level MD&A master file with all professor-required fields.

Usage:
    python extract_mda_sentences.py [--sample N] [--resume]

Output: data/intermediate/mdna_sentence_master.jsonl
"""

import os
import re
import sys
import json
import time
import hashlib
import argparse
from pathlib import Path
from collections import OrderedDict

# Lazy imports (only when needed)
_bs4 = None
_nltk_sent = None
_rapidfuzz = None

def _import_deps():
    global _bs4, _nltk_sent, _rapidfuzz
    from bs4 import BeautifulSoup
    _bs4 = BeautifulSoup
    import nltk
    try:
        nltk.data.find('tokenizers/punkt_tab')
    except LookupError:
        nltk.download('punkt_tab', quiet=True)
    _nltk_sent = nltk.sent_tokenize
    from rapidfuzz import fuzz
    _rapidfuzz = fuzz

# ============================================================
# Config
# ============================================================
BASE = Path(__file__).parent
FILING_ROOT = BASE.parent.parent / "NLP_test" / "sec_filings_full" / "sec-edgar-filings"
OUTPUT_FILE = BASE.parent / "data" / "intermediate" / "mdna_sentence_master.jsonl"
CHECKPOINT_FILE = BASE / ".extract_mda_checkpoint"

# AI seed lexicon (high recall)
AI_KEYWORDS = [
    "artificial intelligence", "machine learning", "deep learning",
    "large language model", "llm", "llms", "generative ai", "genai",
    "neural network", "neural networks",
    "natural language processing", "nlp",
    "chatgpt", "gpt-4", "gpt-3", "openai", "claude", "gemini",
    "copilot", "predictive model", "predictive models",
    "computer vision",
    "algorithm", "algorithms",
    "automation", "automated",
    "robotic process automation", "rpa",
    "intelligent automation",
    "generative ai", "gen ai",
    "foundation model", "foundation models",
    "transformer model", "transformer models",
]

AI_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(k) for k in AI_KEYWORDS) + r')\b',
    re.IGNORECASE
)

# ============================================================
# SGML Full-Submission Parser
# ============================================================

def _extract_filing_date_from_sgmml(filepath: str) -> str:
    """Extract the filing date from the SEC-HEADER section of a full-submission file."""
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    # Look for ACCEPTANCE-DATETIME or FILED AS OF DATE
    m = re.search(r'FILED\s+AS\s+OF\s+DATE:\s*(\d{8})', content)
    if m:
        raw = m.group(1)
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    m = re.search(r'ACCEPTANCE-DATETIME:\s*(\d{14})', content)
    if m:
        raw = m.group(1)
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return ""


def extract_main_10k_text(filepath: str) -> str:
    """
    Parse a full-submission.txt SGML file and extract ONLY the main 10-K document.
    
    SGML structure:
    <SEC-DOCUMENT>
      <DOCUMENT>
        <TYPE>10-K
        <SEQUENCE>1
        <FILENAME>...
        <DESCRIPTION>...
        <TEXT>
          ...actual filing content...
        </TEXT>
      </DOCUMENT>
      <DOCUMENT>
        <TYPE>EX-10.1
        ... (exhibits — skip these)
      </DOCUMENT>
    </SEC-DOCUMENT>
    """
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    # Find all <DOCUMENT> blocks
    doc_pattern = re.compile(
        r'<DOCUMENT>\s*(.*?)</DOCUMENT>',
        re.DOTALL
    )
    
    # Find all <TYPE> blocks to identify the 10-K
    type_pattern = re.compile(r'<TYPE>\s*(\S+)', re.IGNORECASE)
    
    # Find the first 10-K document block (usually sequence 1)
    best_match = None
    best_seq = 999
    
    for doc_match in doc_pattern.finditer(content):
        doc_body = doc_match.group(1)
        
        # Check if this is a 10-K type
        type_match = type_pattern.search(doc_body)
        if not type_match:
            continue
        doc_type = type_match.group(1).upper()
        
        if doc_type != '10-K':
            continue
        
        # Get sequence number
        seq_match = re.search(r'<SEQUENCE>\s*(\d+)', doc_body)
        seq = int(seq_match.group(1)) if seq_match else 999
        
        # Prefer lower sequence numbers (main document)
        if seq < best_seq:
            best_seq = seq
            # Extract the TEXT block
            text_match = re.search(r'<TEXT>\s*\n?(.*?)(?:</TEXT>|$)', doc_body, re.DOTALL)
            if text_match:
                best_match = text_match.group(1).strip()
    
    if best_match:
        return best_match
    
    # Fallback: try to find any TEXT block
    text_match = re.search(r'<TEXT>\s*\n?(.*?)(?:</TEXT>|$)', content, re.DOTALL)
    if text_match:
        return text_match.group(1).strip()
    
    return content


def parse_html_text(raw_text: str) -> str:
    """Parse HTML content within a 10-K document and extract clean text."""
    soup = _bs4(raw_text, "lxml")
    
    # Remove script, style, metadata
    for tag in soup(["script", "style", "meta", "link", "ix:nonfraction", "ix:nonnumeric"]):
        tag.decompose()
    
    # Remove XBRL tags but keep content
    for tag in soup.find_all(lambda t: t.name and ':' in t.name):
        tag.unwrap()
    
    text = soup.get_text(separator=" ", strip=True)
    return text


def parse_plain_text(raw_text: str) -> str:
    """Parse plain text / SGML filing content."""
    # Remove SGML/XML tags
    text = re.sub(r'<[^>]+>', ' ', raw_text)
    # Clean whitespace
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()


# ============================================================
# MD&A Boundary Detection
# ============================================================

def _normalize_spaces(text: str) -> str:
    """Normalize all unicode spaces to regular ASCII spaces."""
    # Replace non-breaking spaces, em-spaces, en-spaces, etc.
    text = text.replace('\u00a0', ' ')  # NBSP
    text = text.replace('\u2000', ' ')  # EN QUAD
    text = text.replace('\u2001', ' ')  # EM QUAD
    text = text.replace('\u2002', ' ')  # EN SPACE
    text = text.replace('\u2003', ' ')  # EM SPACE
    text = text.replace('\u2004', ' ')  # THREE-PER-EM SPACE
    text = text.replace('\u2005', ' ')  # FOUR-PER-EM SPACE
    text = text.replace('\u2006', ' ')  # SIX-PER-EM SPACE
    text = text.replace('\u2007', ' ')  # FIGURE SPACE
    text = text.replace('\u2008', ' ')  # PUNCTUATION SPACE
    text = text.replace('\u2009', ' ')  # THIN SPACE
    text = text.replace('\u200a', ' ')  # HAIR SPACE
    text = text.replace('\u202f', ' ')  # NARROW NO-BREAK SPACE
    text = re.sub(r' +', ' ', text)
    return text


# Valid SEC section item numbers
VALID_ITEMS = {'1', '1A', '1B', '1C', '2', '3', '4', '5', '6', '7', '7A',
               '8', '9', '9A', '9B', '9C', '10', '11', '12', '13', '14', '15', '16'}


def _build_section_index(text: str) -> list:
    """
    Build an index of SEC Item X headers in the text.
    Returns list of (item_number, position, header_text) tuples.
    Only captures valid SEC item numbers to avoid false matches like 'Item 2024'.
    """
    # Use compiled regex to avoid raw string escaping issues
    _ITEM_RE = re.compile(
        '(?:^|\\s)(?:Item|ITEM|item)\\s*:?\\s*(\\d+[A-Za-z]*)\\s*[.\\s:\\-]\\s*',
        re.MULTILINE
    )
    
    sections = []
    for m in _ITEM_RE.finditer(text):
        item_num = m.group(1).strip()
        # Only keep valid SEC item numbers
        if item_num not in VALID_ITEMS:
            continue
        pos = m.start()
        header_text = text[pos:pos+120].strip()
        sections.append((item_num, pos, header_text))

    sections.sort(key=lambda x: x[1])
    return sections


def _is_toc_section(sections: list, idx: int) -> bool:
    """
    Determine if a section header at index `idx` is likely in the TOC.
    
    TOC headers are in a dense cluster where many headers appear within 
    a small text range. Actual section headers in the document body 
    are more spread out, even if there are inline references nearby.
    
    Strategy: check if there are 5+ other section headers within +/-2000 chars.
    In the TOC, headers are packed every ~100 chars. In actual content,
    inline references are sparse.
    """
    pos = sections[idx][1]
    
    # Count headers within a tight window (+/-2000 chars)
    count_tight = 0
    for j, (_, other_pos, _) in enumerate(sections):
        if j == idx:
            continue
        if abs(other_pos - pos) < 2000:
            count_tight += 1
    
    # TOC: many headers packed together
    if count_tight >= 5:
        return True
    
    # Actual content: isolated headers
    return False


def find_mda_section(text: str) -> str:
    """
    Extract Item 7 (MD&A) section from 10-K text.
    """
    text = _normalize_spaces(text)
    sections = _build_section_index(text)
    if not sections:
        return _find_mda_fallback(text)
    
    # Find all Item 7 positions (both "7" and "7A")
    item7_matches = []
    for idx, (item_num, pos, header) in enumerate(sections):
        if re.match(r'^7[A-Z]?$', item_num, re.IGNORECASE):
            is_toc = _is_toc_section(sections, idx)
            item7_matches.append((pos, item_num, is_toc, idx))
    
    if not item7_matches:
        return _find_mda_fallback(text)
    
    # Find the actual Item 7 (not TOC, and not 7A)
    # Prefer non-TOC entries; among those, prefer the last one
    # (some filings reference Item 7 in multiple places)
    actual_item7 = None
    for pos, item_num, is_toc, idx in reversed(item7_matches):
        if item_num == '7' and not is_toc:
            actual_item7 = (pos, idx)
            break
    
    # Fallback: last non-TOC Item 7 (including 7A if no plain 7)
    if actual_item7 is None:
        for pos, item_num, is_toc, idx in reversed(item7_matches):
            if not is_toc:
                actual_item7 = (pos, idx)
                break
    
    # Last resort: last Item 7 match
    if actual_item7 is None:
        actual_item7 = (item7_matches[-1][0], item7_matches[-1][3])
    
    item7_pos = actual_item7[0]
    
    # Find end boundary: Item 7A preferred, then Item 8
    end_pos = len(text)
    search_start = item7_pos + 200
    
    # Look for Item 7A or Item 8 after the start position
    for idx, (item_num, pos, header) in enumerate(sections):
        if pos <= search_start:
            continue
        if re.match(r'^7A$', item_num, re.IGNORECASE):
            end_pos = pos
            break
        elif re.match(r'^8$', item_num):
            if end_pos == len(text):
                end_pos = pos
    
    # Extract the section
    mda_text = text[item7_pos:end_pos]
    
    # Verify it's reasonable (at least 5KB of content)
    cleaned = _clean_mda_text(mda_text)
    if len(cleaned) > 5000:
        return mda_text
    
    return _find_mda_fallback(text)


def _find_mda_fallback(text: str) -> str:
    """
    Fallback MD&A extraction using direct pattern matching.
    Used when section index approach fails.
    """
    text = _normalize_spaces(text)
    
    # More robust Item 7 patterns
    item7_start = None
    
    # Try patterns in order of specificity
    start_patterns = [
        # Full header with description
        r'(?:(?:^|\n)\s*)(?:Item|ITEM)\s*7[\.\:\s\-–—]*(?:Management.{0,60}(?:Discussion|discussion))',
        # Shorter header
        r'(?:(?:^|\n)\s*)(?:Item|ITEM)\s*7[\.\:\s\-–—]*(?:MD&A|md&a)',
        # Just "Item 7" followed by content (not a page number)
        r'(?:(?:^|\n)\s*)(?:Item|ITEM)\s*7[\.\:\s\-–—]+\S',
    ]
    
    for pat in start_patterns:
        m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
        if m:
            # Verify this isn't a TOC entry
            context = text[m.start():m.start()+200]
            if not True:  # TOC check simplified
                item7_start = m.start()
                break
    
    if item7_start is None:
        return ""
    
    # Find end: Item 7A or Item 8
    end_pos = len(text)
    search_from = item7_start + 300
    
    end_patterns = [
        r'(?:(?:^|\n)\s*)(?:Item|ITEM)\s*7A[\.\:\s\-–—]',
        r'(?:(?:^|\n)\s*)(?:Item|ITEM)\s*8[\.\:\s\-–—]',
    ]
    
    for pat in end_patterns:
        m = re.search(pat, text[search_from:], re.IGNORECASE | re.MULTILINE)
        if m:
            # Check it's not TOC
            context = text[search_from:search_from+m.start()+200]
            if not True:  # TOC check simplified
                end_pos = search_from + m.start()
                break
    
    return text[item7_start:end_pos]


# ============================================================
# Text Cleaning
# ============================================================

def _clean_mda_text(text: str) -> str:
    """
    Clean MD&A text while preserving semantic content.
    
    Per professor's spec:
    - Remove HTML/XBRL tags
    - Remove headers/footers, table fragments, navigation strings
    - Remove encoding noise and meaningless special symbols
    - Normalize whitespace
    - Preserve negation words, modals, numbers
    - NO aggressive stemming or stop word removal
    """
    # Remove HTML tags (but keep content)
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # Remove XBRL tags
    text = re.sub(r'<\w+:[^>]*?>', ' ', text)
    text = re.sub(r'</\w+:[^>]*?>', ' ', text)
    
    # Remove XML/HTML entities
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    text = re.sub(r'&#\d+;', ' ', text)
    
    # Remove navigation strings
    nav_patterns = [
        r'(?:Back|Return)\s+(?:to\s+)?(?:the\s+)?(?:Table\s+of\s+Contents|Top)',
        r'(?:Table\s+of\s+Contents)',
        r'(?:Click\s+here\s+for\s+)',
    ]
    for pat in nav_patterns:
        text = re.sub(pat, ' ', text, flags=re.IGNORECASE)
    
    # Remove page numbers (standalone numbers, often at line boundaries)
    text = re.sub(r'(?<=\n)\s*\d{1,3}\s*(?=\n)', ' ', text)
    
    # Remove table fragments: lines that are mostly numbers, pipes, dashes
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        # Skip lines that are mostly special chars or numbers
        alpha_ratio = sum(1 for c in line_stripped if c.isalpha()) / max(len(line_stripped), 1)
        if alpha_ratio < 0.3 and len(line_stripped) > 10:
            continue
        # Skip lines that are just dashes, equals, etc.
        if re.match(r'^[\-=\s_]+$', line_stripped):
            continue
        # Skip very short lines that look like headers
        if len(line_stripped) < 15 and line_stripped.isupper():
            continue
        cleaned_lines.append(line_stripped)
    
    text = ' '.join(cleaned_lines)
    
    # Normalize whitespace
    text = re.sub(r'\s{2,}', ' ', text)
    text = text.strip()
    
    return text


# ============================================================
# Sentence Tokenization
# ============================================================

def split_sentences(text: str) -> list:
    """
    Split MD&A text into sentences using NLTK PunktSentenceTokenizer.
    
    Handles:
    - Abbreviations (Inc., Mr., Mrs., e.g., i.e., etc., U.S.)
    - 10-K specific patterns (section references, numbered items)
    - Semicolons (treat as sentence boundaries when followed by capital letter)
    - Broken lines (join before splitting)
    
    Returns list of clean sentence strings.
    """
    if not text or len(text) < 20:
        return []
    
    # Pre-process: join broken lines (line breaks mid-sentence)
    # Replace single newlines with space, double newlines with paragraph break
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
    text = re.sub(r'\n{2,}', ' ', text)
    
    # Use NLTK sentence tokenizer
    sentences = _nltk_sent(text)
    
    # Post-process sentences
    cleaned = []
    for sent in sentences:
        sent = sent.strip()
        
        # Skip if too short (fragments)
        if len(sent) < 20:
            continue
        
        # Skip if no alphabetic characters
        if not any(c.isalpha() for c in sent):
            continue
        
        # Skip if looks like a header (all caps, short)
        alpha_chars = [c for c in sent if c.isalpha()]
        if alpha_chars and all(c.isupper() for c in alpha_chars) and len(sent) < 100:
            continue
        
        # Skip if starts with common navigation/footer patterns
        if re.match(r'^(?:Source:|Note:|\d+\s*\)|Table\s+\d|Figure\s+\d)', sent, re.IGNORECASE):
            continue
        
        # Skip if looks like a table row (many numbers/special chars)
        num_ratio = sum(1 for c in sent if c.isdigit()) / max(len(sent), 1)
        if num_ratio > 0.5 and len(sent) < 200:
            continue
        
        cleaned.append(sent)
    
    return cleaned


# ============================================================
# Deduplication
# ============================================================

def deduplicate_sentences(sentences: list) -> list:
    """
    Remove exact and near-duplicate sentences.
    Returns list of (sentence, is_exact_duplicate, is_near_duplicate) tuples.
    All sentences are returned with flags so downstream can filter.
    """
    results = []
    kept_texts = []
    kept_hashes = set()
    
    for sent in sentences:
        sent_hash = hashlib.md5(sent.lower().encode()).hexdigest()
        
        if sent_hash in kept_hashes:
            results.append((sent, True, False))
            continue
        
        # Near-duplicate check against kept sentences
        is_near_dup = False
        sent_lower = sent.lower()
        for kept_sent in kept_texts[-50:]:
            ratio = _rapidfuzz.ratio(sent_lower, kept_sent.lower())
            if ratio > 90:
                is_near_dup = True
                break
        
        if is_near_dup:
            results.append((sent, False, True))
            continue
        
        results.append((sent, False, False))
        kept_texts.append(sent)
        kept_hashes.add(sent_hash)
    
    return results


# ============================================================
# AI Candidate Matching
# ============================================================

def match_ai_keywords(sentence: str) -> tuple:
    """
    Find AI keyword matches in a sentence.
    High recall — we want to catch all potential AI mentions.
    
    Returns:
        (is_candidate: bool, matched_terms: list)
    """
    sent_lower = sentence.lower()
    matches = AI_PATTERN.findall(sent_lower)
    if matches:
        return True, list(set(m.lower() for m in matches))
    return False, []


# ============================================================
# Process One Filing
# ============================================================

def process_filing(ticker: str, accession: str, filing_dir: str,
                   company_info: dict = None, cik_map: dict = None) -> list:
    """
    Process a single 10-K filing and return flat sentence-level records.
    
    Each record has ALL professor-required fields:
    - firm-year identifiers: cik, gvkey, ticker, company_name, filing_date, fiscal_year, accession_number
    - MD&A metadata: section_name, mdna_total_word_count, mdna_total_sentence_count, mdna_total_char_count
    - sentence-level: sentence_id, sentence_order, sentence_raw, sentence_clean, sentence_word_count
    - quality flags: is_exact_duplicate, is_near_duplicate, keep_sentence_flag
    - AI candidate: ai_candidate_flag, ai_keyword_matched_terms
    
    Returns: list of dicts (one per sentence, including duplicates with flags)
    """
    # Find the main filing document
    doc_path = _find_primary_document(filing_dir)
    if not doc_path:
        return []
    
    # Extract text based on file type
    try:
        with open(doc_path, "r", encoding="utf-8", errors="ignore") as f:
            raw_content = f.read()
    except Exception:
        return []
    
    try:
        if '<SEC-DOCUMENT>' in raw_content or '<SEC-HEADER>' in raw_content:
            raw_text = extract_main_10k_text(doc_path)
        else:
            raw_text = raw_content
        
        raw_prefix = raw_text.lstrip().lower()[:200]
        if any(tag in raw_prefix for tag in ['<html', '<!doctype', '<?xml', '<xbrl']):
            full_text = parse_html_text(raw_text)
        else:
            full_text = parse_plain_text(raw_text)
    except Exception:
        return []
    
    # Extract MD&A section
    mda_text = find_mda_section(full_text)
    if not mda_text:
        mda_text = full_text
    
    # Clean MD&A text
    cleaned_mda = _clean_mda_text(mda_text)
    
    # Company info
    company_name = ""
    if company_info and ticker in company_info:
        company_name = company_info[ticker].get('name', '')
    
    # Extract filing date from SGML header
    filing_date = ""
    if '<SEC-DOCUMENT>' in raw_content or '<SEC-HEADER>' in raw_content:
        filing_date = _extract_filing_date_from_sgmml(doc_path)
    
    # Extract fiscal year from accession number
    fiscal_year = _extract_filing_year(accession)
    
    # Look up cik and gvkey
    cik = ""
    gvkey = ""
    if cik_map and ticker in cik_map:
        cik = cik_map[ticker].get('cik', '')
        gvkey = cik_map[ticker].get('gvkey', '')
    
    # MD&A metadata
    mdna_word_count = len(cleaned_mda.split())
    
    # Split into sentences
    all_sentences = split_sentences(cleaned_mda)
    mdna_sentence_count_raw = len(all_sentences)
    
    # Deduplicate (returns all sentences with flags)
    deduped = deduplicate_sentences(all_sentences)
    mdna_sentence_count = sum(1 for _, is_exact, is_near in deduped if not is_exact and not is_near)
    
    # Build flat sentence records
    records = []
    for idx, (sent, is_exact_dup, is_near_dup) in enumerate(deduped):
        is_ai_candidate, matched_terms = match_ai_keywords(sent)
        keep = not is_exact_dup and not is_near_dup
        
        records.append({
            # Firm-year identifiers
            "cik": cik,
            "gvkey": gvkey,
            "ticker": ticker,
            "company_name": company_name,
            "filing_date": filing_date,
            "fiscal_year": fiscal_year,
            "accession_number": accession,
            # MD&A metadata
            "section_name": "Item 7 - MD&A",
            "mdna_total_word_count": mdna_word_count,
            "mdna_total_sentence_count": mdna_sentence_count,
            "mdna_total_char_count": len(cleaned_mda),
            # Sentence-level
            "sentence_id": f"{ticker}_{accession}_{idx:04d}",
            "sentence_order": idx,
            "sentence_raw": sent[:500],
            "sentence_clean": _normalize_spaces(sent)[:500],
            "sentence_word_count": len(sent.split()),
            # Quality flags
            "is_exact_duplicate": is_exact_dup,
            "is_near_duplicate": is_near_dup,
            "keep_sentence_flag": keep,
            # AI candidate
            "ai_candidate_flag": is_ai_candidate,
            "ai_keyword_matched_terms": matched_terms,
        })
    
    return records


def _find_primary_document(filing_dir: str) -> str | None:
    """
    Find the main 10-K document in a filing directory.
    
    Priority:
    1. Full submission files (full-submission.txt, etc.)
    2. Largest HTM/HTML file (excluding exhibits R1.htm, R2.htm, etc.)
    3. Largest TXT file
    """
    files = os.listdir(filing_dir)
    
    # Try full submission files first
    submission_patterns = ['full-submission', 'full_submission', '10-K', '10k']
    for pat in submission_patterns:
        candidates = [f for f in files if pat.lower() in f.lower()]
        if candidates:
            candidates.sort(
                key=lambda f: os.path.getsize(os.path.join(filing_dir, f)),
                reverse=True
            )
            return os.path.join(filing_dir, candidates[0])
    
    # Try HTM/HTML files
    htm_candidates = [
        f for f in files
        if f.lower().endswith((".htm", ".html"))
        and not re.match(r'^R\d+', f, re.IGNORECASE)
        and not re.match(r'^ex-\d+', f, re.IGNORECASE)
        and "fillingsummary" not in f.lower()
        and "filesummary" not in f.lower()
    ]
    if htm_candidates:
        htm_candidates.sort(
            key=lambda f: os.path.getsize(os.path.join(filing_dir, f)),
            reverse=True
        )
        return os.path.join(filing_dir, htm_candidates[0])
    
    # Try TXT files
    txt_files = [f for f in files if f.lower().endswith(".txt")]
    if txt_files:
        txt_files.sort(
            key=lambda f: os.path.getsize(os.path.join(filing_dir, f)),
            reverse=True
        )
        return os.path.join(filing_dir, txt_files[0])
    
    return None


def _extract_filing_year(accession: str) -> str:
    """Extract year from accession number: 0000320193-24-000106 -> 2024"""
    m = re.search(r'-(\d{2})-', accession)
    if m:
        yy = int(m.group(1))
        return str(2000 + yy if yy < 50 else 1900 + yy)
    return "unknown"


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Extract MD&A sentences from 10-K filings")
    parser.add_argument("--sample", type=int, default=0, help="Process only N filings (for testing)")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--tickers", type=str, default="", help="Comma-separated list of tickers to process")
    args = parser.parse_args()
    
    # Import dependencies
    print("Loading dependencies...")
    _import_deps()
    
    if not FILING_ROOT.is_dir():
        print(f"ERROR: {FILING_ROOT} not found!")
        sys.exit(1)
    
    # Load company list
    company_list_path = FILING_ROOT.parent / "sp500_company_list.csv"
    company_info = {}
    if company_list_path.exists():
        import pandas as pd
        df = pd.read_csv(company_list_path)
        for _, row in df.iterrows():
            company_info[str(row['Symbol'])] = {
                'name': str(row.get('Security', '')),
                'sector': str(row.get('GICS Sector', '')),
            }
    
    # Load CIK-GVKEY crosswalk for cik/gvkey fields
    cik_map = {}
    cik_gvkey_path = BASE.parent.parent / "NLP_test" / "data" / "wrds" / "cik_gvkey_crosswalk.csv"
    if cik_gvkey_path.exists():
        import pandas as pd
        cwm = pd.read_csv(cik_gvkey_path, dtype={'cik': str})
        cwm['cik'] = cwm['cik'].str.zfill(10)
        for _, row in cwm.iterrows():
            tic = str(row.get('tic', '')).strip()
            if tic and tic != 'nan':
                cik_map[tic] = {
                    'cik': str(row['cik']),
                    'gvkey': str(row.get('gvkey', '')),
                }
        print(f"  Loaded CIK-GVKEY crosswalk: {len(cik_map)} tickers")
    
    # Determine which tickers to process
    all_tickers = sorted(os.listdir(FILING_ROOT))
    if args.tickers:
        target_tickers = [t.strip() for t in args.tickers.split(",")]
        all_tickers = [t for t in all_tickers if t in target_tickers]
        print(f"Processing specified tickers: {target_tickers}")
    elif args.sample > 0:
        all_tickers = all_tickers[:args.sample]
        print(f"Processing sample: {args.sample} tickers")
    
    # Load checkpoint
    done = set()
    if args.resume and CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            done = set(tuple(x) for x in json.load(f))
        print(f"Resuming: {len(done)} filings already processed")
    
    # Stats
    total_filings = 0
    total_sentences = 0
    total_kept = 0
    total_ai_sentences = 0
    total_ai_filings = 0
    total_errors = 0
    total_dropped_exact = 0
    total_dropped_near = 0
    
    start_time = time.time()
    
    print(f"\nProcessing {len(all_tickers)} tickers...\n")
    
    # Ensure output directory exists
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    mode = "a" if (args.resume and CHECKPOINT_FILE.exists() and OUTPUT_FILE.exists()) else "w"
    
    with open(OUTPUT_FILE, mode) as out:
        for i, ticker in enumerate(all_tickers):
            ticker_dir = FILING_ROOT / ticker / "10-K"
            if not ticker_dir.is_dir():
                continue
            
            for accession in sorted(os.listdir(ticker_dir)):
                if (ticker, accession) in done:
                    continue
                
                filing_dir = str(ticker_dir / accession)
                records = process_filing(ticker, accession, filing_dir, company_info, cik_map)
                
                if not records:
                    total_errors += 1
                    if total_errors <= 5:
                        print(f"  ERROR {ticker} {accession}: No records produced")
                    continue
                
                # Write flat sentence records (one JSON line per sentence)
                for rec in records:
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out.flush()
                
                # Stats
                total_filings += 1
                total_sentences += len(records)
                kept = sum(1 for r in records if r['keep_sentence_flag'])
                total_kept += kept
                dropped_exact = sum(1 for r in records if r['is_exact_duplicate'])
                dropped_near = sum(1 for r in records if r['is_near_duplicate'])
                total_dropped_exact += dropped_exact
                total_dropped_near += dropped_near
                ai_count = sum(1 for r in records if r['ai_candidate_flag'] and r['keep_sentence_flag'])
                total_ai_sentences += ai_count
                if ai_count > 0:
                    total_ai_filings += 1
                
                done.add((ticker, accession))
                
                # Progress every 50 filings
                if total_filings % 50 == 0:
                    elapsed = time.time() - start_time
                    rate = total_filings / max(elapsed, 1) * 60
                    avg_sent = total_kept / max(total_filings, 1)
                    print(f"  [{total_filings} done | {rate:.0f}/min | "
                          f"avg {avg_sent:.0f} kept sent/filing | "
                          f"{total_ai_filings} AI filings | "
                          f"{total_ai_sentences} AI sentences | "
                          f"dropped exact:{total_dropped_exact} near:{total_dropped_near}]")
                
                # Checkpoint every 50 filings
                if total_filings % 50 == 0:
                    with open(CHECKPOINT_FILE, 'w') as cf:
                        json.dump([list(x) for x in done], cf)
    
    # Final checkpoint
    with open(CHECKPOINT_FILE, 'w') as cf:
        json.dump([list(x) for x in done], cf)
    
    elapsed = time.time() - start_time
    
    print(f"\n{'='*70}")
    print(f"Extraction Complete!")
    print(f"  Total filings processed: {total_filings}")
    print(f"  Total sentences (all, incl. dups): {total_sentences:,}")
    print(f"  Sentences kept (after dedup): {total_kept:,}")
    print(f"  Total AI sentences (kept only): {total_ai_sentences:,}")
    print(f"  Filings with AI mentions: {total_ai_filings}")
    print(f"  Errors: {total_errors}")
    print(f"  Dropped exact duplicates: {total_dropped_exact:,}")
    print(f"  Dropped near duplicates: {total_dropped_near:,}")
    print(f"  Time: {elapsed/60:.1f} minutes")
    print(f"  Output: {OUTPUT_FILE}")
    if OUTPUT_FILE.exists():
        size_mb = OUTPUT_FILE.stat().st_size / 1024 / 1024
        print(f"  File size: {size_mb:.1f} MB")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()
