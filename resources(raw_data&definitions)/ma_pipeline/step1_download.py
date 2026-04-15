# ============================================================
#  step1_download.py  —  从SEC EDGAR批量下载10-K
# ============================================================

import os
import time
import pandas as pd
from sec_edgar_downloader import Downloader
from config import (
    OUTPUT_DIR, SEC_USER_AGENT, DOWNLOAD_AFTER,
    DOWNLOAD_BEFORE, REQUEST_DELAY, SECTOR_SAMPLE
)


def get_sp500_tickers() -> pd.DataFrame:
    """从Wikipedia拉S&P500列表（含行业分类）"""
    print("Fetching S&P 500 company list from Wikipedia...")
    tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    sp500 = tables[0][["Symbol", "Security", "GICS Sector", "GICS Sub-Industry"]]
    sp500["Symbol"] = sp500["Symbol"].str.replace(".", "-", regex=False)  # BRK.B → BRK-B
    return sp500


def select_companies(sp500: pd.DataFrame) -> pd.DataFrame:
    """按SECTOR_SAMPLE配置，每个行业取前N家"""
    selected = []
    for sector, n in SECTOR_SAMPLE.items():
        subset = sp500[sp500["GICS Sector"] == sector]
        subset = subset.head(n) if n else subset
        selected.append(subset)
        print(f"  {sector}: {len(subset)} companies")
    result = pd.concat(selected, ignore_index=True)
    print(f"\nTotal selected: {len(result)} companies\n")
    return result


def download_filings(companies: pd.DataFrame):
    """批量下载10-K，已下载的自动跳过"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 保存公司列表，方便后续 join
    companies.to_csv(f"{OUTPUT_DIR}/company_list.csv", index=False)

    email = SEC_USER_AGENT.split()[-1]
    name  = " ".join(SEC_USER_AGENT.split()[:-1])
    dl = Downloader(name, email, OUTPUT_DIR)

    tickers = companies["Symbol"].tolist()
    failed  = []

    for i, ticker in enumerate(tickers):
        ticker_dir = os.path.join(
            OUTPUT_DIR, "sec-edgar-filings", ticker, "10-K"
        )
        # 如果已有文件则跳过（断点续跑）
        if os.path.isdir(ticker_dir) and os.listdir(ticker_dir):
            print(f"[{i+1}/{len(tickers)}] SKIP (already downloaded): {ticker}")
            continue

        try:
            dl.get("10-K", ticker,
                   after=DOWNLOAD_AFTER,
                   before=DOWNLOAD_BEFORE)
            print(f"[{i+1}/{len(tickers)}] ✓ {ticker}")
        except Exception as e:
            print(f"[{i+1}/{len(tickers)}] ✗ {ticker}: {e}")
            failed.append({"ticker": ticker, "error": str(e)})

        time.sleep(REQUEST_DELAY)

    if failed:
        pd.DataFrame(failed).to_csv(f"{OUTPUT_DIR}/download_failed.csv", index=False)
        print(f"\nFailed: {len(failed)} tickers → saved to {OUTPUT_DIR}/download_failed.csv")

    print(f"\n[Step 1 Done] Filings saved to: {OUTPUT_DIR}/sec-edgar-filings/")


if __name__ == "__main__":
    sp500     = get_sp500_tickers()
    companies = select_companies(sp500)
    download_filings(companies)
