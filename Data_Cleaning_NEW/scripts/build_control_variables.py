#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build control-variable panel from WRDS Compustat data.

Produces a firm-year CSV with standard corporate-finance controls:
  - log(Assets)
  - ROA
  - Leverage
  - Sales Growth
  - R&D / Assets
  - Capex / Assets
  - Intangibles / Assets
  - Tobin's Q
  - Industry & Year identifiers (for FE)

INPUT
-----
  ../../NLP_test_deprecated/data/wrds/compustat_annual_2018_2025.csv
  (optional) Additional WRDS pull with capx, intan, prcc_f

OUTPUT
------
  ../data/final/control_variables.csv

WRDS QUERY (run this first if capx/intan/prcc_f are missing)
------------------------------------------------------------
  SELECT a.gvkey, a.fyear, a.datadate,
         a.capx, a.intan, a.prcc_f
  FROM comp.funda a
  WHERE a.gvkey IN (SELECT DISTINCT gvkey FROM your_firm_list)
    AND a.fyear BETWEEN 2018 AND 2025
    AND a.indfmt = 'INDL'
    AND a.datafmt = 'STD'
    AND a.popsrc = 'D'
    AND a.consol = 'C'
  ORDER BY a.gvkey, a.fyear;

Save the WRDS output as:
  ../data/raw/compustat_supplemental_2018_2025.csv
and re-run this script.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMPUSTAT_PATH = PROJECT_ROOT / "NLP_test_deprecated" / "data" / "wrds" / "compustat_annual_2018_2025.csv"
SUPPLEMENTAL_PATH = PROJECT_ROOT / "Data_Cleaning_NEW" / "data" / "raw" / "compustat_supplemental_2018_2025.csv"
OUTPUT_DIR = PROJECT_ROOT / "Data_Cleaning_NEW" / "data" / "final"
OUTPUT_CSV = OUTPUT_DIR / "control_variables.csv"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ------------------------------------------------------------------
# 1. Load base Compustat
# ------------------------------------------------------------------
print("[1/5] Loading Compustat annual data...")
if not COMPUSTAT_PATH.exists():
    print(f"[ERROR] Compustat file not found: {COMPUSTAT_PATH}")
    sys.exit(1)

df = pd.read_csv(COMPUSTAT_PATH, low_memory=False)
print(f"        Rows: {len(df):,} | Columns: {len(df.columns)}")

# Standardise identifiers
df["gvkey"] = df["gvkey"].astype(str).str.zfill(6)
df["cik"] = df["cik"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(10)
df["fyear"] = pd.to_numeric(df["fyear"], errors="coerce").astype("Int64")

# Drop rows without key identifiers
df = df.dropna(subset=["gvkey", "fyear"]).copy()

# ------------------------------------------------------------------
# 2. Merge supplemental WRDS data (capx, intan, prcc_f) if present
# ------------------------------------------------------------------
has_supplemental = False
if SUPPLEMENTAL_PATH.exists():
    print("[2/5] Merging supplemental WRDS data (capx, intan, prcc_f)...")
    sup = pd.read_csv(SUPPLEMENTAL_PATH, low_memory=False)
    sup["gvkey"] = sup["gvkey"].astype(str).str.zfill(6)
    sup["fyear"] = pd.to_numeric(sup["fyear"], errors="coerce").astype("Int64")
    sup = sup.dropna(subset=["gvkey", "fyear"])

    # Keep only needed columns
    sup_cols = ["gvkey", "fyear"]
    for c in ["capx", "intan", "prcc_f"]:
        if c in sup.columns:
            sup_cols.append(c)
    sup = sup[sup_cols].drop_duplicates(subset=["gvkey", "fyear"], keep="first")

    df = df.merge(sup, on=["gvkey", "fyear"], how="left")
    has_supplemental = True
    print(f"        Supplemental merged. capx present: {'capx' in df.columns}")
else:
    print("[2/5] Supplemental WRDS data not found.")
    print(f"        Expected at: {SUPPLEMENTAL_PATH}")
    print("        Will create placeholder columns for capx, intan, prcc_f.")
    for c in ["capx", "intan", "prcc_f"]:
        df[c] = np.nan

# ------------------------------------------------------------------
# 2b. Merge CRSP prices for missing prcc_f (if available)
# ------------------------------------------------------------------
CRSP_PATH = PROJECT_ROOT / "Data_Cleaning_NEW" / "data" / "raw" / "crsp_prices_supplemental.csv"
if CRSP_PATH.exists():
    print("[2b/5] Merging CRSP supplemental prices for missing prcc_f...")
    crsp = pd.read_csv(CRSP_PATH, low_memory=False)
    crsp["gvkey"] = crsp["gvkey"].astype(str).str.zfill(6)
    crsp["fyear"] = pd.to_numeric(crsp["fyear"], errors="coerce").astype("Int64")
    crsp["crsp_prc"] = pd.to_numeric(crsp["crsp_prc"], errors="coerce")
    crsp["days_diff"] = pd.to_numeric(crsp["days_diff"], errors="coerce")

    # Only use reliable prices: non-null and within 90 days of fiscal year-end
    crsp = crsp[
        crsp["crsp_prc"].notna()
        & (crsp["days_diff"] <= 90)
    ].copy()

    if not crsp.empty:
        # For merge, keep only gvkey, fyear, crsp_prc
        crsp_merge = crsp[["gvkey", "fyear", "crsp_prc", "crsp_date", "days_diff"]].drop_duplicates(
            subset=["gvkey", "fyear"], keep="first"
        )
        n_before = df["prcc_f"].notna().sum()
        df = df.merge(crsp_merge, on=["gvkey", "fyear"], how="left")
        # Fill missing prcc_f with CRSP price
        mask = df["prcc_f"].isna() & df["crsp_prc"].notna()
        df.loc[mask, "prcc_f"] = df.loc[mask, "crsp_prc"]
        n_after = df["prcc_f"].notna().sum()
        print(f"        Filled {n_after - n_before:,} missing prcc_f from CRSP")
        print(f"        prcc_f coverage: {n_after:,} / {len(df):,} ({n_after/len(df)*100:.1f}%)")
    else:
        print("        No reliable CRSP prices to merge.")
else:
    print("[2b/5] CRSP supplemental prices not found.")

# ------------------------------------------------------------------
# 3. Compute control variables
# ------------------------------------------------------------------
print("[3/5] Computing control variables...")

# Helper: coerce numeric
num_cols = ["at", "ni", "ib", "lt", "dltt", "dlc", "sale", "revt",
            "xrd", "ppent", "ceq", "csho", "che", "emp",
            "capx", "intan", "prcc_f"]
for c in num_cols:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

# --- log(Assets) ---
df["log_assets"] = np.where(df["at"] > 0, np.log(df["at"]), np.nan)

# --- ROA (net income / total assets) ---
df["ROA"] = np.where(df["at"] > 0, df["ni"] / df["at"], np.nan)

# --- Leverage (total liabilities / total assets) ---
df["leverage"] = np.where(df["at"] > 0, df["lt"] / df["at"], np.nan)

# --- Alternative leverage: (dltt + dlc) / at ---
df["debt_at"] = np.where(
    df["at"] > 0,
    (df["dltt"].fillna(0) + df["dlc"].fillna(0)) / df["at"],
    np.nan
)

# --- R&D / Assets ---
df["rd_to_assets"] = np.where(df["at"] > 0, df["xrd"] / df["at"], np.nan)

# --- Capex / Assets ---
df["capex_to_assets"] = np.where(df["at"] > 0, df["capx"] / df["at"], np.nan)

# --- Intangibles / Assets ---
df["intangibles_to_assets"] = np.where(df["at"] > 0, df["intan"] / df["at"], np.nan)

# --- Tobin's Q ---
# Q = (Market Value of Equity + Book Liabilities) / Book Total Assets
# Market Value = prcc_f * csho
mv_equity = df["prcc_f"] * df["csho"]
book_liab = df["lt"]
df["tobin_q"] = np.where(
    df["at"] > 0,
    (mv_equity.fillna(0) + book_liab.fillna(0)) / df["at"],
    np.nan
)
# If prcc_f is missing, Tobin's Q is not valid
# Recode to NaN when prcc_f is missing
df.loc[df["prcc_f"].isna(), "tobin_q"] = np.nan

# --- Sales Growth (year-over-year within firm) ---
df = df.sort_values(["gvkey", "fyear"]).copy()
df["sale_lag"] = df.groupby("gvkey")["sale"].shift(1)
df["sales_growth"] = np.where(
    df["sale_lag"] > 0,
    (df["sale"] - df["sale_lag"]) / df["sale_lag"],
    np.nan
)

# --- Additional common controls (optional) ---
df["cash_ratio"] = np.where(df["at"] > 0, df["che"] / df["at"], np.nan)
df["ppe_ratio"] = np.where(df["at"] > 0, df["ppent"] / df["at"], np.nan)
df["log_emp"] = np.where(df["emp"] > 0, np.log(df["emp"]), np.nan)

# ------------------------------------------------------------------
# 4. Build clean output
# ------------------------------------------------------------------
print("[4/5] Building output panel...")

out_cols = [
    "gvkey", "cik", "tic", "conm",
    "fyear", "datadate",
    "sic", "naics", "gsubind",
    # Core controls
    "log_assets",
    "ROA",
    "leverage",
    "debt_at",
    "sales_growth",
    "rd_to_assets",
    "capex_to_assets",
    "intangibles_to_assets",
    "tobin_q",
    # Additional
    "cash_ratio",
    "ppe_ratio",
    "log_emp",
    # Raw values (for transparency / auditing)
    "at", "ni", "lt", "sale", "xrd", "capx", "intan", "prcc_f", "csho",
]

# Keep only columns that exist
out_cols = [c for c in out_cols if c in df.columns]
out = df[out_cols].copy()

# Drop rows where ALL core controls are missing (empty firm-years)
core_controls = ["log_assets", "ROA", "leverage", "sales_growth"]
core_controls = [c for c in core_controls if c in out.columns]
n_before = len(out)
out = out.dropna(subset=core_controls, how="all").copy()
n_after = len(out)
print(f"        Dropped {n_before - n_after:,} rows with no core control data.")
print(f"        Final panel: {len(out):,} firm-years, {out['gvkey'].nunique():,} unique firms.")

# ------------------------------------------------------------------
# 5. Save
# ------------------------------------------------------------------
print("[5/5] Saving control_variables.csv...")
out.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
print(f"        Saved: {OUTPUT_CSV}")

# ------------------------------------------------------------------
# 6. Summary statistics
# ------------------------------------------------------------------
print("\n" + "=" * 60)
print("SUMMARY STATISTICS")
print("=" * 60)

summary_vars = [
    "log_assets", "ROA", "leverage", "sales_growth",
    "rd_to_assets", "capex_to_assets", "intangibles_to_assets", "tobin_q"
]
summary_vars = [c for c in summary_vars if c in out.columns]

if summary_vars:
    desc = out[summary_vars].describe().T
    desc["missing"] = out[summary_vars].isna().sum()
    desc["missing_pct"] = (desc["missing"] / len(out) * 100).round(1)
    print(desc[["count", "mean", "std", "min", "50%", "max", "missing", "missing_pct"]].to_string())

print("=" * 60)

# ------------------------------------------------------------------
# 7. Missing-data flags
# ------------------------------------------------------------------
print("\nMISSING VARIABLES THAT NEED WRDS SUPPLEMENTAL PULL:")
missing_flags = []
for var, item in [("capex_to_assets", "capx"),
                   ("intangibles_to_assets", "intan"),
                   ("tobin_q", "prcc_f")]:
    if var in out.columns:
        n_miss = out[var].isna().sum()
        pct = n_miss / len(out) * 100
        missing_flags.append((var, item, n_miss, pct))
        print(f"  {var:30s} <- needs {item:10s} | missing: {n_miss:6,} ({pct:5.1f}%)")

if not has_supplemental and missing_flags:
    print("\nTo fill these, run the WRDS SQL query in the script header,")
    print(f"save as {SUPPLEMENTAL_PATH}, and re-run this script.")

print("\nDone.")
