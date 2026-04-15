# M&A AI Disclosure Pipeline

从SEC EDGAR批量下载标普500财报 → 提取M&A章节 → 过滤AI相关语句
→ GPT分类（substantive / generic）→ 计算AI披露密度

---

## 文件结构

```
ma_ai_pipeline/
├── config.py            ← 所有参数在这里改
├── step1_download.py    ← 从SEC下载10-K
├── step2_extract.py     ← 提取M&A章节，过滤AI句子
├── step3_classify.py    ← GPT分类
├── step4_density.py     ← 计算密度，输出CSV
├── run_pipeline.py      ← 一键入口
└── requirements.txt
```

---

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 设置 OpenAI API Key
```bash
# Mac/Linux
export OPENAI_API_KEY="sk-..."

# Windows
set OPENAI_API_KEY=sk-...
```

### 3. 修改 config.py
```python
# 必改：填入你的邮箱（SEC要求User-Agent）
SEC_USER_AGENT = "ResearchProject your@email.com"

# 可选：调整每个行业抽取的公司数
SECTOR_SAMPLE = {
    "Information Technology": 30,
    ...
}
```

### 4. 运行

```bash
# 完整流程（首次运行）
python run_pipeline.py

# 已经下载好了，从提取步骤开始
python run_pipeline.py --start 2

# 只重跑GPT分类
python run_pipeline.py --only 3

# 只重新计算密度（不重跑GPT）
python run_pipeline.py --only 4
```

---

## 输出文件说明

### `density_results.csv` — 主结果表

每行 = 一家公司的一份年报

| 列名 | 含义 |
|------|------|
| ticker | 股票代码 |
| Security | 公司名 |
| GICS Sector | 行业 |
| year | 财报年份 |
| mda_sentence_count | MD&A总句数（分母） |
| ma_sentence_count | M&A相关句数 |
| ai_total | 含AI关键词的M&A句数 |
| substantive_cnt | 实质性AI披露句数 |
| generic_cnt | 泛化AI披露句数 |
| **ai_density_in_mda** | ai_total / mda句数 |
| **substantive_density** | substantive / mda句数 |
| **generic_density** | generic / mda句数 |
| ai_density_in_ma | ai_total / ma句数（另一视角）|
| **substantive_ratio** | substantive / ai_total（AI质量比）|

### `ma_extracts.jsonl` — 中间文件（可检查质量）

每行是一个filing的提取结果，包含所有原始AI句子，方便人工抽查。

### `ma_classified.jsonl` — GPT分类明细

每行是一条句子的分类结果，包含置信度和GPT的reason。

---

## 成本估算

约195家公司 × 7年 = ~1,365个filings  
假设平均每个filing提取5条AI句子 ≈ 6,825条句子

- `gpt-4o-mini` Pass 1: ~6,825 × $0.00015/1k tokens ≈ **$0.5**
- `gpt-4o` Pass 2（仅低置信度，约20%）: ~1,365 × $0.005/1k tokens ≈ **$3**
- 总计约 **$3-5**

---

## 断点续跑

所有步骤都支持中断后继续：
- `step1`: 已下载的ticker自动跳过
- `step2`: 已处理的 (ticker, accession) 自动跳过
- `step3`: 已分类的句子自动跳过
- `step4`: 每次重新计算（速度很快）

---

## 常见问题

**Q: M&A章节没提取到内容？**  
在 `step2_extract.py` 中打印 `mda_text[:500]` 检查，可能需要在 `ITEM7_START` 里加该公司的特殊标题写法。

**Q: SEC下载很慢/被限速？**  
`config.py` 中增大 `REQUEST_DELAY`（建议不低于0.5秒）。

**Q: 想只看某个行业？**  
在 `config.py` 的 `SECTOR_SAMPLE` 里把其他行业设为 `0` 或删除。
