#!/usr/bin/env python3
import sys; sys.stdout.reconfigure(line_buffering=True)
"""
Full S&P 500 10-K Download from SEC EDGAR (v2 — local CIK mapping)
====================================================================
Downloads all 10-K filings for current S&P 500 constituents
from 2019 to 2025. Uses pre-downloaded SEC CIK mapping to avoid rate limits.
"""

import os
import time
import json
import pandas as pd
from pathlib import Path

# ============================================================
# Config
# ============================================================
SEC_USER_AGENT = "ResearchProject rico.zhu@columbia.edu"
DOWNLOAD_AFTER = "2018-12-31"
DOWNLOAD_BEFORE = "2026-01-01"
REQUEST_DELAY = 1.0  # Increased delay to avoid rate limiting
OUTPUT_DIR = Path(__file__).parent / "sec_filings_full"
CIK_MAP_PATH = "/tmp/ticker_to_cik.json"

# ============================================================
# S&P 500 companies (tickers with CIKs only)
# ============================================================
# 489 of 501 found in SEC mapping. Missing 12: ANSS, CTLT, DAY, DFS, FI, HES, IPG, JNPR, K, MMC, PARA, WBA
SP500_TICKERS = [
    "MMM","AOS","ABT","ABBV","ACN","ADBE","AMD","AES","AFL","A","APD","ABNB","AKAM","ALB","ARE",
    "ALGN","ALLE","LNT","ALL","GOOGL","GOOG","MO","AMZN","AMCR","AEE","AAL","AEP","AXP","AIG","AMT",
    "AWK","AMP","AME","AMGN","APH","ADI","AON","APA","AAPL","AMAT","APTV","ACGL","ADM","ANET",
    "AJG","AIZ","T","ATO","ADSK","ADP","AZO","AVB","AVY","AXON","BKR","BALL","BAC","BAX","BDX",
    "BRK-B","BBY","TECH","BIIB","BLK","BX","BK","BA","BKNG","BWA","BSX","BMY","AVGO","BR","BRO",
    "BF-B","BLDR","BG","CDNS","CZR","CPT","CPB","COF","CAH","KMX","CCL","CARR","CAT","CBOE",
    "CBRE","CDW","CE","COR","CNC","CNP","CF","CHRW","CRL","SCHW","CHTR","CVX","CMG","CB","CHD",
    "CI","CINF","CTAS","CSCO","C","CFG","CLX","CME","CMS","KO","CTSH","CL","CMCSA","CAG","COP",
    "ED","STZ","CEG","COO","CPRT","GLW","CPAY","CTVA","CSGP","COST","CTRA","CRWD","CCI","CSX","CMI",
    "CVS","DHR","DRI","DVA","DECK","DE","DELL","DAL","DVN","DXCM","FANG","DLR","DG","DLTR","D",
    "DPZ","DOV","DOW","DHI","DTE","DUK","DD","EMN","ETN","EBAY","ECL","EIX","EW","EA","ELV",
    "LLY","EMR","ENPH","ETR","EOG","EPAM","EQT","EFX","EQIX","EQR","ESS","EL","EG","EVRG",
    "ES","EXC","EXPE","EXPD","EXR","XOM","FFIV","FDS","FICO","FAST","FRT","FDX","FIS","FITB",
    "FSLR","FE","FMC","F","FTNT","FTV","FOXA","FOX","BEN","FCX","GRMN","IT","GE","GEHC",
    "GEV","GEN","GNRC","GD","GIS","GM","GPC","GILD","GPN","GL","GDDY","GS","HAL","HIG","HAS",
    "HCA","DOC","HSIC","HSY","HPE","HLT","HOLX","HD","HON","HRL","HST","HWM","HPQ","HUBB",
    "HUM","HBAN","HII","IBM","IEX","IDXX","ITW","INCY","IR","PODD","INTC","ICE","IFF","IP",
    "INTU","ISRG","IVZ","INVH","IQV","IRM","JBHT","JBL","JKHY","J","JNJ","JCI","JPM","K",
    "KVUE","KDP","KEY","KEYS","KMB","KIM","KMI","KKR","KLAC","KHC","KR","LHX","LH","LRCX","LW",
    "LVS","LDOS","LEN","LIN","LYV","LKQ","LMT","L","LOW","LULU","LYB","MTB","MPC","MKTX","MAR",
    "MLM","MAS","MA","MTCH","MKC","MCD","MCK","MDT","MRK","META","MET","MTD","MGM","MCHP",
    "MU","MSFT","MAA","MRNA","MHK","MOH","TAP","MDLZ","MPWR","MNST","MCO","MS","MOS","MSI","MSCI",
    "NDAQ","NTAP","NFLX","NEM","NWSA","NWS","NEE","NKE","NI","NDSN","NSC","NTRS","NOC","NCLH",
    "NRG","NUE","NVDA","NVR","NXPI","ORLY","OXY","ODFL","OMC","ON","OKE","ORCL","OTIS","PCAR",
    "PKG","PLTR","PANW","PH","PAYX","PAYC","PYPL","PNR","PEP","PFE","PCG","PM","PSX","PNW",
    "PNC","POOL","PPG","PPL","PFG","PG","PGR","PLD","PRU","PEG","PTC","PSA","PHM","QRVO","PWR",
    "QCOM","DGX","RL","RJF","RTX","O","REG","REGN","RF","RSG","RMD","RVTY","ROK","ROL","ROP",
    "ROST","RCL","SPGI","CRM","SBAC","SLB","STX","SRE","NOW","SHW","SPG","SWKS","SJM","SW","SNA",
    "SOLV","SO","LUV","SWK","SBUX","STT","STLD","STE","SYK","SMCI","SYF","SNPS","SYY","TMUS","TROW",
    "TTWO","TPR","TRGP","TGT","TEL","TDY","TFX","TER","TSLA","TXN","TPL","TXT","TMO","TJX","TSCO",
    "TT","TDG","TRV","TRMB","TFC","TYL","TSN","USB","UBER","UDR","ULTA","UNP","UAL","UPS","URI",
    "UNH","UHS","VLO","VTR","VRSN","VRSK","VZ","VRTX","VTRS","VICI","V","VST","VMC","WRB","GWW",
    "WAB","WMT","DIS","WBD","WM","WAT","WEC","WFC","WELL","WST","WDC","WY","WMB","WTW",
    "WDAY","WYNN","XEL","XYL","YUM","ZBRA","ZBH","ZTS"
]

# ============================================================
# Patch sec-edgar-downloader to use local CIK mapping
# ============================================================
def patch_sec_downloader():
    """Monkey-patch the library to use local CIK mapping instead of fetching from SEC."""
    import sec_edgar_downloader._orchestrator as orch
    
    with open(CIK_MAP_PATH) as f:
        local_mapping = json.load(f)
    
    # Override the function
    original = orch.get_ticker_to_cik_mapping
    def patched_mapping(user_agent):
        return local_mapping
    orch.get_ticker_to_cik_mapping = patched_mapping
    print(f"✅ Patched sec-edgar-downloader to use local CIK mapping ({len(local_mapping)} entries)")


# ============================================================
# Download
# ============================================================
def download_all():
    patch_sec_downloader()
    
    from sec_edgar_downloader import Downloader
    OUTPUT_DIR.mkdir(exist_ok=True)

    email = SEC_USER_AGENT.split()[-1]
    name = " ".join(SEC_USER_AGENT.split()[:-1])
    dl = Downloader(name, email, str(OUTPUT_DIR))

    tickers = SP500_TICKERS
    failed = []
    total = len(tickers)

    print(f"\nStarting download of {total} S&P 500 companies' 10-K filings...")
    print(f"Date range: {DOWNLOAD_AFTER} to {DOWNLOAD_BEFORE}")
    print(f"Delay: {REQUEST_DELAY}s per request")
    print(f"Output: {OUTPUT_DIR}\n")

    start_time = time.time()

    for i, ticker in enumerate(tickers):
        ticker_dir = OUTPUT_DIR / "sec-edgar-filings" / ticker / "10-K"

        # Skip if already downloaded
        if ticker_dir.exists() and any(ticker_dir.iterdir()):
            existing = len(list(ticker_dir.iterdir()))
            print(f"[{i+1}/{total}] SKIP ({existing} filings): {ticker}")
            continue

        try:
            dl.get("10-K", ticker, after=DOWNLOAD_AFTER, before=DOWNLOAD_BEFORE)
            filings = len(list(ticker_dir.iterdir())) if ticker_dir.exists() else 0
            print(f"[{i+1}/{total}] ✓ {ticker} ({filings} filings)")
        except Exception as e:
            error_msg = str(e)
            print(f"[{i+1}/{total}] ✗ {ticker}: {error_msg[:100]}")
            failed.append({"ticker": ticker, "error": error_msg})

        time.sleep(REQUEST_DELAY)

        # Progress every 50
        if (i + 1) % 50 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed * 60
            eta = elapsed / (i + 1) * (total - i - 1)
            print(f"\n  ... {i+1}/{total} done | {rate:.0f} filings/min | ETA: {eta/60:.0f}m\n")

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"Download complete!")
    print(f"  Time: {elapsed/60:.1f} minutes")
    print(f"  Failed: {len(failed)} / {total}")

    if failed:
        pd.DataFrame(failed).to_csv(OUTPUT_DIR / "download_failed.csv", index=False)
        print(f"  Failed tickers saved to: {OUTPUT_DIR / 'download_failed.csv'}")
    print(f"{'='*60}")


if __name__ == '__main__':
    download_all()
