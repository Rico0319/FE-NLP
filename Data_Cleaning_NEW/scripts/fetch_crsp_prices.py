#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch missing prcc_f from CRSP monthly prices via CCM link table."""

import os
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np
import psycopg2

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CTRL_PATH = PROJECT_ROOT / "Data_Cleaning_NEW" / "data" / "final" / "control_variables.csv"
OUTPUT_PATH = PROJECT_ROOT / "Data_Cleaning_NEW" / "data" / "raw" / "crsp_prices_supplemental.csv"

# ------------------------------------------------------------------
# WRDS connection
# ------------------------------------------------------------------
WRDS_HOST = "wrds-pgdata.wharton.upenn.edu"
WRDS_PORT = 9737
WRDS_DB = "wrds"
WRDS_USER = "fedorico"
WRDS_PASS = "Yang@230379033"

# ------------------------------------------------------------------
# 1. Load control variables, find missing prcc_f
# ------------------------------------------------------------------
print("[1/5] Loading control variables...")
ctrl = pd.read_csv(CTRL_PATH, low_memory=False)
ctrl["gvkey"] = ctrl["gvkey"].astype(str).str.zfill(6)
ctrl["fyear"] = pd.to_numeric(ctrl["fyear"], errors="coerce").astype("Int64")
ctrl["prcc_f"] = pd.to_numeric(ctrl["prcc_f"], errors="coerce")
ctrl["datadate"] = pd.to_datetime(ctrl["datadate"], errors="coerce")
ctrl["csho"] = pd.to_numeric(ctrl["csho"], errors="coerce")

missing = ctrl[ctrl["prcc_f"].isna()].copy()
print(f"        Total rows: {len(ctrl):,}")
print(f"        Missing prcc_f: {len(missing):,}")

if len(missing) == 0:
    print("        No missing prcc_f. Exiting.")
    sys.exit(0)

# Get unique gvkeys + date ranges for CCM lookup
gvkeys = missing["gvkey"].unique().tolist()
date_min = missing["datadate"].min().strftime("%Y-%m-%d")
date_max = missing["datadate"].max().strftime("%Y-%m-%d")
print(f"        {len(gvkeys):,} unique gvkeys")
print(f"        Date range: {date_min} to {date_max}")

# ------------------------------------------------------------------
# 2. Query CCM link table: gvkey -> permno
# ------------------------------------------------------------------
print("[2/5] Querying CCM link table (gvkey -> permno)...")

conn = psycopg2.connect(
    host=WRDS_HOST, port=WRDS_PORT, database=WRDS_DB,
    user=WRDS_USER, password=WRDS_PASS, sslmode="require",
)

cursor = conn.cursor()

# CCM link: use gvkey -> permno mapping
# Use crsp.ccmxpf_lnkhist for historical links
CHUNK = 2000
all_links = []

for i in range(0, len(gvkeys), CHUNK):
    chunk = gvkeys[i : i + CHUNK]
    placeholders = ",".join(["%s"] * len(chunk))
    query = f"""
        SELECT  DISTINCT l.gvkey, l.lpermno AS permno,
                l.linkdt, l.linkenddt, l.linktype, l.linkprim
        FROM    crsp.ccmxpf_lnkhist l
        WHERE   l.gvkey IN ({placeholders})
          AND   l.linktype IN ('LU', 'LC', 'LS', 'LX')
          AND   l.linkprim IN ('P', 'C', 'J')
        ORDER BY l.gvkey, l.lpermno, l.linkdt;
    """
    cursor.execute(query, chunk)
    rows = cursor.fetchall()
    all_links.extend(rows)
    print(f"        Chunk {i//CHUNK + 1}: {len(rows):,} link rows")

links = pd.DataFrame(
    all_links,
    columns=["gvkey", "permno", "linkdt", "linkenddt", "linktype", "linkprim"]
)
links["linkdt"] = pd.to_datetime(links["linkdt"])
links["linkenddt"] = pd.to_datetime(links["linkenddt"], errors="coerce")
links["permno"] = links["permno"].astype(int)

print(f"        Total link rows: {len(links):,}")
print(f"        Unique gvkeys with link: {links['gvkey'].nunique():,}")
print(f"        Unique permnos: {links['permno'].nunique():,}")

# ------------------------------------------------------------------
# 3. For each missing row, find the valid permno on datadate
# ------------------------------------------------------------------
print("[3/5] Matching gvkey+datadate to permno...")

# Merge missing rows with links where datadate is within link validity period
missing["_row_id"] = range(len(missing))

# linkenddt may be NULL (meaning still active) — treat as far future
links["linkenddt_filled"] = links["linkenddt"].fillna(pd.Timestamp("2099-12-31"))

matched = []
for _, row in missing.iterrows():
    gv = row["gvkey"]
    dd = row["datadate"]
    rid = row["_row_id"]
    
    # Find links valid on datadate
    valid = links[
        (links["gvkey"] == gv)
        & (links["linkdt"] <= dd)
        & (links["linkenddt_filled"] >= dd)
    ]
    
    if len(valid) > 0:
        # Prefer primary link (linkprim='P'), then earliest link
        valid = valid.sort_values(["linkprim", "linkdt"])
        best = valid.iloc[0]
        matched.append({
            "_row_id": rid,
            "gvkey": gv,
            "fyear": row["fyear"],
            "datadate": dd,
            "permno": int(best["permno"]),
        })

matched_df = pd.DataFrame(matched)
print(f"        Matched {len(matched_df):,} / {len(missing):,} missing rows to permno")

if len(matched_df) == 0:
    print("        No matches found. Exiting.")
    cursor.close()
    conn.close()
    sys.exit(0)

# ------------------------------------------------------------------
# 4. Query CRSP monthly prices (msf)
# ------------------------------------------------------------------
print("[4/5] Querying CRSP monthly prices...")

permnos = matched_df["permno"].unique().tolist()
print(f"        Querying {len(permnos):,} unique permnos")

all_prices = []
for i in range(0, len(permnos), CHUNK):
    chunk = permnos[i : i + CHUNK]
    placeholders = ",".join(["%s"] * len(chunk))
    
    # For each permno, we want prices around the datadates
    # We pull all prices in the relevant date range
    query = f"""
        SELECT  m.permno, m.date, m.prc, m.shrout
        FROM    crsp.msf m
        WHERE   m.permno IN ({placeholders})
          AND   m.date BETWEEN '{date_min}'::date - INTERVAL '3 months'
                           AND '{date_max}'::date + INTERVAL '1 month'
        ORDER BY m.permno, m.date;
    """
    cursor.execute(query, chunk)
    rows = cursor.fetchall()
    all_prices.extend(rows)
    print(f"        Chunk {i//CHUNK + 1}: {len(rows):,} price rows")

cursor.close()
conn.close()

prices = pd.DataFrame(all_prices, columns=["permno", "date", "prc", "shrout"])
prices["date"] = pd.to_datetime(prices["date"])
# prc is negative when no trade (bid-ask average), take abs
prices["prc"] = pd.to_numeric(prices["prc"], errors="coerce").abs()
prices["shrout"] = pd.to_numeric(prices["shrout"], errors="coerce")
print(f"        Total price rows fetched: {len(prices):,}")

# ------------------------------------------------------------------
# 5. For each matched row, find the price on or before datadate
# ------------------------------------------------------------------
print("[5/5] Finding nearest price on or before fiscal year-end...")

results = []
for _, row in matched_df.iterrows():
    dd = row["datadate"]
    perm = row["permno"]
    
    # Prices for this permno on or before datadate
    candidate = prices[
        (prices["permno"] == perm)
        & (prices["date"] <= dd)
    ].sort_values("date")
    
    if len(candidate) > 0:
        best = candidate.iloc[-1]  # most recent
        results.append({
            "gvkey": row["gvkey"],
            "fyear": row["fyear"],
            "datadate": dd,
            "permno": perm,
            "crsp_date": best["date"],
            "crsp_prc": best["prc"],
            "crsp_shrout": best["shrout"],
            "days_diff": (dd - best["date"]).days,
        })

results_df = pd.DataFrame(results)
print(f"        Found CRSP prices for {len(results_df):,} / {len(matched_df):,} matched rows")

if len(results_df) > 0:
    print(f"        Days diff (datadate - price_date):")
    print(f"          mean: {results_df['days_diff'].mean():.1f}")
    print(f"          median: {results_df['days_diff'].median():.1f}")
    print(f"          max: {results_df['days_diff'].max()}")
    print(f"          <=30 days: {(results_df['days_diff'] <= 30).sum():,}")
    print(f"          <=90 days: {(results_df['days_diff'] <= 90).sum():,}")
    
    # Save
    results_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    print(f"        Saved: {OUTPUT_PATH}")
else:
    print("        No CRSP prices found.")

print("\nDone. Run build_control_variables.py to merge CRSP prices and recompute tobin_q.")
