# ============================================================
#  run_pipeline.py  —  一键运行完整pipeline
#
#  用法:
#    python run_pipeline.py                  # 运行全部4步
#    python run_pipeline.py --start 2        # 从第2步开始（已有下载）
#    python run_pipeline.py --only 3         # 只跑第3步
#    python run_pipeline.py --start 2 --end 3  # 跑第2、3步
# ============================================================

import argparse
import time

def run(start: int = 1, end: int = 4):
    if start <= 1 <= end:
        print("\n" + "="*60)
        print("STEP 1: Downloading 10-K filings from SEC EDGAR")
        print("="*60)
        from step1_download import get_sp500_tickers, select_companies, download_filings
        sp500 = get_sp500_tickers()
        companies = select_companies(sp500)
        download_filings(companies)

    if start <= 2 <= end:
        print("\n" + "="*60)
        print("STEP 2: Extracting M&A sections & filtering AI sentences")
        print("="*60)
        from step2_extract import run_extraction
        run_extraction()

    if start <= 3 <= end:
        print("\n" + "="*60)
        print("STEP 3: Classifying AI sentences with GPT")
        print("="*60)
        from step3_classify import run_classification
        run_classification(two_pass=True)

    if start <= 4 <= end:
        print("\n" + "="*60)
        print("STEP 4: Computing density metrics")
        print("="*60)
        from step4_density import run_density
        run_density()

    print("\n" + "="*60)
    print("ALL DONE")
    print("="*60)
    print("Output files:")
    print("  ./sec_filings/          — raw 10-K HTM files")
    print("  ./ma_extracts.jsonl     — extracted M&A + AI sentences")
    print("  ./ma_classified.jsonl   — GPT classification results")
    print("  ./density_results.csv   — final density table (load into Excel/R/Stata)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="M&A AI Disclosure Pipeline")
    parser.add_argument("--start", type=int, default=1, help="Start from step N (1-4)")
    parser.add_argument("--end",   type=int, default=4, help="End at step N (1-4)")
    parser.add_argument("--only",  type=int, default=None, help="Run only step N")
    args = parser.parse_args()

    if args.only:
        run(start=args.only, end=args.only)
    else:
        run(start=args.start, end=args.end)
