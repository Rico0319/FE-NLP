# ============================================================
#  step4_density.py  —  计算AI披露密度，输出最终CSV
# ============================================================
#
#  密度定义（分母选MDA总句数，最合理）：
#
#  ai_density_in_mda       = ai句总数        / MDA总句数
#  substantive_density     = substantive句数  / MDA总句数
#  generic_density         = generic句数      / MDA总句数
#  ai_density_in_ma        = ai句总数        / MA相关句数   (另一个视角)
#  substantive_ratio       = substantive句数  / ai句总数    (AI质量比)
#
# ============================================================

import json
import os
import pandas as pd
from config import CLASSIFIED_FILE, EXTRACTS_FILE, DENSITY_CSV, OUTPUT_DIR


def load_extracts() -> dict:
    """加载extraction结果，建立 (ticker, accession) → 句子数量的映射"""
    meta = {}
    if not os.path.exists(EXTRACTS_FILE):
        return meta
    with open(EXTRACTS_FILE) as f:
        for line in f:
            rec = json.loads(line)
            key = (rec["ticker"], rec["accession"])
            meta[key] = {
                "mda_sentence_count": rec.get("mda_sentence_count", 0),
                "ma_sentence_count":  rec.get("ma_sentence_count", 0),
            }
    return meta


def load_classified() -> pd.DataFrame:
    """加载分类结果"""
    if not os.path.exists(CLASSIFIED_FILE):
        raise FileNotFoundError(f"{CLASSIFIED_FILE} not found. Run step3_classify.py first.")
    records = []
    with open(CLASSIFIED_FILE) as f:
        for line in f:
            records.append(json.loads(line))
    return pd.DataFrame(records)


def safe_div(a, b) -> float:
    return round(a / b, 6) if b > 0 else 0.0


def compute_density() -> pd.DataFrame:
    meta = load_extracts()
    df   = load_classified()

    # 过滤分类失败的行
    df = df[df["classification"].isin(["substantive", "generic"])].copy()

    # ---------- 每个 (ticker, accession, year) 汇总 ----------
    grouped = (
        df.groupby(["ticker", "accession", "year"])
        .agg(
            ai_total        = ("sentence", "count"),
            substantive_cnt = ("classification", lambda x: (x == "substantive").sum()),
            generic_cnt     = ("classification", lambda x: (x == "generic").sum()),
        )
        .reset_index()
    )

    # 补入句子总数（分母）
    grouped["mda_sentence_count"] = grouped.apply(
        lambda r: meta.get((r["ticker"], r["accession"]), {}).get("mda_sentence_count", 0),
        axis=1
    )
    grouped["ma_sentence_count"] = grouped.apply(
        lambda r: meta.get((r["ticker"], r["accession"]), {}).get("ma_sentence_count", 0),
        axis=1
    )

    # ---------- 计算各密度指标 ----------
    grouped["ai_density_in_mda"]   = grouped.apply(
        lambda r: safe_div(r["ai_total"], r["mda_sentence_count"]), axis=1)

    grouped["substantive_density"] = grouped.apply(
        lambda r: safe_div(r["substantive_cnt"], r["mda_sentence_count"]), axis=1)

    grouped["generic_density"]     = grouped.apply(
        lambda r: safe_div(r["generic_cnt"], r["mda_sentence_count"]), axis=1)

    grouped["ai_density_in_ma"]    = grouped.apply(
        lambda r: safe_div(r["ai_total"], r["ma_sentence_count"]), axis=1)

    grouped["substantive_ratio"]   = grouped.apply(
        lambda r: safe_div(r["substantive_cnt"], r["ai_total"]), axis=1)

    # ---------- 加入行业信息 ----------
    company_list_path = os.path.join(OUTPUT_DIR, "company_list.csv")
    if os.path.exists(company_list_path):
        companies = pd.read_csv(company_list_path)
        companies = companies.rename(columns={"Symbol": "ticker"})
        grouped = grouped.merge(
            companies[["ticker", "Security", "GICS Sector", "GICS Sub-Industry"]],
            on="ticker", how="left"
        )

    # ---------- 整理列顺序 ----------
    cols_order = [
        "ticker", "Security", "GICS Sector", "GICS Sub-Industry",
        "year", "accession",
        "mda_sentence_count", "ma_sentence_count",
        "ai_total", "substantive_cnt", "generic_cnt",
        "ai_density_in_mda", "substantive_density", "generic_density",
        "ai_density_in_ma", "substantive_ratio",
    ]
    cols_order = [c for c in cols_order if c in grouped.columns]
    grouped = grouped[cols_order].sort_values(["ticker", "year"])

    return grouped


def print_summary(df: pd.DataFrame):
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total filings with AI disclosure: {len(df)}")
    print(f"Companies:  {df['ticker'].nunique()}")
    print(f"Year range: {df['year'].min()} – {df['year'].max()}")
    print(f"\nMean densities (per filing):")
    for col in ["ai_density_in_mda", "substantive_density",
                "generic_density", "substantive_ratio"]:
        if col in df.columns:
            print(f"  {col:30s}: {df[col].mean():.4f}")

    if "GICS Sector" in df.columns:
        print("\nSubstantive density by sector (mean):")
        sector_stats = (
            df.groupby("GICS Sector")["substantive_density"]
            .mean()
            .sort_values(ascending=False)
        )
        for sector, val in sector_stats.items():
            print(f"  {sector:35s}: {val:.4f}")


def run_density():
    print("Computing density metrics...")
    df = compute_density()

    df.to_csv(DENSITY_CSV, index=False, encoding="utf-8-sig")
    print(f"\n[Step 4 Done] Density results saved to: {DENSITY_CSV}")
    print(f"  Shape: {df.shape[0]} rows × {df.shape[1]} columns")

    print_summary(df)
    return df


if __name__ == "__main__":
    run_density()
