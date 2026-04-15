# ============================================================
#  config.py  —  所有可调参数集中在这里
# ============================================================

# ---------- 路径 ----------
OUTPUT_DIR        = "./sec_filings"          # 下载目录
EXTRACTS_FILE     = "./ma_extracts.jsonl"    # 中间结果（断点续跑用）
CLASSIFIED_FILE   = "./ma_classified.jsonl"  # GPT分类结果
DENSITY_CSV       = "./density_results.csv"  # 最终密度表

# ---------- SEC下载 ----------
SEC_USER_AGENT    = "ResearchProject your@email.com"   # ← 改成你的邮箱
DOWNLOAD_AFTER    = "2017-12-31"
DOWNLOAD_BEFORE   = "2025-01-01"
REQUEST_DELAY     = 0.7          # 秒，SEC限速10 req/s，保守设

# 每个行业抽取的公司数（设 None = 全取）
SECTOR_SAMPLE = {
    "Information Technology":  30,
    "Financials":              25,
    "Health Care":             25,
    "Consumer Discretionary":  20,
    "Industrials":             20,
    "Communication Services":  15,
    "Energy":                  15,
    "Consumer Staples":        15,
    "Materials":               10,
    "Real Estate":             10,
    "Utilities":               10,
}

# ---------- AI关键词 ----------
AI_KEYWORDS = [
    "artificial intelligence", "machine learning", "deep learning",
    "large language model", "llm", "generative ai", "genai",
    "neural network", "natural language processing", "nlp",
    "chatgpt", "gpt-4", "gpt-3", "openai", "claude", "gemini",
    "copilot", "predictive model", "computer vision",
    "algorithm", "automation", "robotic process automation", "rpa",
    "intelligent automation",
]

# ---------- OpenAI ----------
OPENAI_MODEL      = "gpt-4o"
OPENAI_MINI_MODEL = "gpt-4o-mini"   # 用于初筛，降低成本
OPENAI_MAX_TOKENS = 200
OPENAI_DELAY      = 0.3             # 批量调用间隔（秒）
