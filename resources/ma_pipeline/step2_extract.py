# ============================================================
#  step2_extract.py  —  提取M&A章节 → 过滤AI相关句子
# ============================================================

import os
import re
import json
from bs4 import BeautifulSoup
from config import OUTPUT_DIR, EXTRACTS_FILE, AI_KEYWORDS

# ------------------------------------------------------------------
# 章节边界 patterns（覆盖SEC 10-K的各种写法）
# ------------------------------------------------------------------
ITEM7_START = [
    r"item\s*7[\.\:–\-]?\s*management.{0,30}discussion",
    r"item\s*7[\.\:–\-]?\s*md&a",
    r"management.{0,10}discussion\s*and\s*analysis\s*of",
]
ITEM8_START = [
    r"item\s*8[\.\:–\-]?\s*financial\s*statements",
    r"item\s*8[\.\:–\-]?\s*consolidated\s*financial",
]

# M&A段落筛选关键词（段落级别，比AI关键词更宽）
MA_PARA_KEYWORDS = [
    r"merger[s]?", r"acquisition[s]?", r"acqui[rs]",
    r"business\s*combination", r"m\s*&\s*a",
    r"strategic\s*transaction", r"divestiture",
    r"divest", r"carve.?out", r"spin.?off",
    r"purchase\s*price", r"transaction\s*value",
    r"target\s*compan", r"acquired\s*compan",
]
MA_PARA_PATTERN = re.compile("|".join(MA_PARA_KEYWORDS), re.IGNORECASE)

# ------------------------------------------------------------------
# AI关键词句子级匹配
# ------------------------------------------------------------------
AI_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(k) for k in AI_KEYWORDS) + r')\b',
    re.IGNORECASE
)

# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------

def parse_htm(filepath: str) -> str:
    """HTM → 干净纯文本"""
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "lxml")
    for tag in soup(["script", "style", "ix:nonfraction", "ix:nonnumeric"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    # 压缩多余空白
    text = re.sub(r'\s{2,}', ' ', text)
    return text


def find_section(text: str, start_patterns: list, end_patterns: list) -> str:
    """截取两组pattern之间的文本"""
    start_pos = None
    for pat in start_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            start_pos = m.start()
            break
    if start_pos is None:
        return ""

    # 在start之后寻找end
    search_from = start_pos + 200
    end_pos = len(text)
    for pat in end_patterns:
        m = re.search(pat, text[search_from:], re.IGNORECASE)
        if m:
            end_pos = search_from + m.start()
            break

    return text[start_pos:end_pos]


def split_sentences(text: str) -> list[str]:
    """简单句子分割（处理财报常见的缩写/数字边界）"""
    # 先把换行转为空格
    text = text.replace('\n', ' ')
    # 按句号/问号/叹号分割，但不在缩写处断开
    sentences = re.split(r'(?<!\b[A-Z][a-z])(?<!\b[A-Z])(?<=[.!?])\s+(?=[A-Z])', text)
    return [s.strip() for s in sentences if len(s.strip()) > 30]


def find_primary_document(filing_dir: str) -> str | None:
    """在filing文件夹中找到主HTM文件"""
    files = os.listdir(filing_dir)
    # 优先：不是 R[0-9].htm 这种附件，不是 FilingSummary
    candidates = [
        f for f in files
        if f.lower().endswith((".htm", ".html"))
        and not re.match(r'^R\d+\.htm', f, re.IGNORECASE)
        and "fillingsummary" not in f.lower()
        and "filesummary" not in f.lower()
    ]
    if not candidates:
        return None
    # 取最大的文件（正文通常最大）
    candidates.sort(
        key=lambda f: os.path.getsize(os.path.join(filing_dir, f)),
        reverse=True
    )
    return os.path.join(filing_dir, candidates[0])


def extract_filing_year(accession_number: str) -> str:
    """从accession number或文件夹名推断filing年份"""
    # accession格式: 0000320193-23-000106 → 2023
    m = re.search(r'-(\d{2})-', accession_number)
    if m:
        yy = int(m.group(1))
        return str(2000 + yy if yy < 50 else 1900 + yy)
    return "unknown"

# ------------------------------------------------------------------
# 核心处理函数
# ------------------------------------------------------------------

def process_filing(ticker: str, accession: str, filing_dir: str) -> dict | None:
    """处理单个filing，返回结构化结果"""
    htm_path = find_primary_document(filing_dir)
    if not htm_path:
        return None

    try:
        full_text = parse_htm(htm_path)
    except Exception as e:
        return {"ticker": ticker, "accession": accession, "error": str(e)}

    # 提取 MD&A (Item 7)
    mda_text = find_section(full_text, ITEM7_START, ITEM8_START)
    if not mda_text:
        mda_text = full_text   # fallback：用全文

    # 所有句子（用于计算分母）
    all_sentences = split_sentences(mda_text)

    # M&A相关段落
    ma_paragraphs = [s for s in all_sentences if MA_PARA_PATTERN.search(s)]

    # 在M&A句子中再过滤含AI关键词的句子
    ai_sentences = []
    for sent in ma_paragraphs:
        matches = AI_PATTERN.findall(sent)
        if matches:
            ai_sentences.append({
                "sentence": sent,
                "matched_keywords": list(set(m.lower() for m in matches))
            })

    return {
        "ticker":           ticker,
        "accession":        accession,
        "year":             extract_filing_year(accession),
        "mda_sentence_count":   len(all_sentences),
        "ma_sentence_count":    len(ma_paragraphs),
        "ai_sentence_count":    len(ai_sentences),
        "ai_sentences":         ai_sentences,
        "htm_path":             htm_path,
    }


def run_extraction():
    filings_root = os.path.join(OUTPUT_DIR, "sec-edgar-filings")

    if not os.path.isdir(filings_root):
        print(f"ERROR: {filings_root} not found. Run step1_download.py first.")
        return

    # 已处理的记录（断点续跑）
    done = set()
    if os.path.exists(EXTRACTS_FILE):
        with open(EXTRACTS_FILE) as f:
            for line in f:
                rec = json.loads(line)
                done.add((rec.get("ticker"), rec.get("accession")))
        print(f"Resuming: {len(done)} filings already extracted")

    total_filings = 0
    tickers = sorted(os.listdir(filings_root))

    with open(EXTRACTS_FILE, "a") as out:
        for ticker in tickers:
            ticker_dir = os.path.join(filings_root, ticker, "10-K")
            if not os.path.isdir(ticker_dir):
                continue

            for accession in sorted(os.listdir(ticker_dir)):
                if (ticker, accession) in done:
                    continue

                filing_dir = os.path.join(ticker_dir, accession)
                if not os.path.isdir(filing_dir):
                    continue

                result = process_filing(ticker, accession, filing_dir)
                if result:
                    out.write(json.dumps(result) + "\n")
                    out.flush()
                    total_filings += 1
                    ai_count = result.get("ai_sentence_count", 0)
                    print(f"  {ticker} {result.get('year','')} | "
                          f"MDA:{result.get('mda_sentence_count',0)} sentences | "
                          f"MA:{result.get('ma_sentence_count',0)} | "
                          f"AI:{ai_count}")

    print(f"\n[Step 2 Done] Processed {total_filings} filings → {EXTRACTS_FILE}")


if __name__ == "__main__":
    run_extraction()
