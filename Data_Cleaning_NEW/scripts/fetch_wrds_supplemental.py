#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch capx, intan, prcc_f from WRDS Compustat for missing control variables."""

import os
import sys
from pathlib import Path

import pandas as pd
import psycopg2

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
GVLIST_PATH = PROJECT_ROOT / "Data_Cleaning_NEW" / "data" / "raw" / "gvkey_list.csv"
OUTPUT_PATH = PROJECT_ROOT / "Data_Cleaning_NEW" / "data" / "raw" / "compustat_supplemental_2018_2025.csv"

# ------------------------------------------------------------------
# WRDS connection (from ~/.pgpass)
#   wrds-pgdata.wharton.upenn.edu:9737:wrds:fedorico:Yang@230379033
# ------------------------------------------------------------------
WRDS_HOST = "wrds-pgdata.wharton.upenn.edu"
WRDS_PORT = 9737
WRDS_DB = "wrds"
WRDS_USER = "fedorico"
WRDS_PASS = "Yang@230379033"

# ------------------------------------------------------------------
# 1. Load gvkey list
# ------------------------------------------------------------------
print("[1/3] Loading gvkey list...")
if not GVLIST_PATH.exists():
    print(f"[ERROR] {GVLIST_PATH} not found.")
    sys.exit(1)

gvkeys = pd.read_csv(GVLIST_PATH)["gvkey"].astype(str).tolist()
print(f"        {len(gvkeys):,} gvkeys to query.")

# ------------------------------------------------------------------
# 2. Build and run WRDS query
# ------------------------------------------------------------------
print("[2/3] Querying WRDS Compustat...")
print(f"        Host: {WRDS_HOST}:{WRDS_PORT}")

# Build WHERE clause with gvkey list (batch into chunks if needed)
# WRDS PostgreSQL can handle IN clauses with ~10k items, but let's chunk just to be safe.
CHUNK_SIZE = 2000
all_results = []

try:
    conn = psycopg2.connect(
        host=WRDS_HOST,
        port=WRDS_PORT,
        database=WRDS_DB,
        user=WRDS_USER,
        password=WRDS_PASS,
        sslmode="require",
    )
    cursor = conn.cursor()

    for i in range(0, len(gvkeys), CHUNK_SIZE):
        chunk = gvkeys[i : i + CHUNK_SIZE]
        placeholders = ",".join(["%s"] * len(chunk))

        query = f"""
            SELECT  a.gvkey,
                    a.fyear,
                    a.datadate,
                    a.capx,
                    a.intan,
                    a.prcc_f
            FROM    comp.funda a
            WHERE   a.gvkey IN ({placeholders})
                AND a.fyear BETWEEN 2018 AND 2025
                AND a.indfmt = 'INDL'
                AND a.datafmt = 'STD'
                AND a.popsrc = 'D'
                AND a.consol = 'C'
            ORDER BY a.gvkey, a.fyear;
        """

        cursor.execute(query, chunk)
        rows = cursor.fetchall()
        all_results.extend(rows)
        print(f"        Chunk {i//CHUNK_SIZE + 1}: {len(rows):,} rows fetched.")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"[ERROR] WRDS query failed: {e}")
    sys.exit(1)

print(f"        Total rows fetched: {len(all_results):,}")

# ------------------------------------------------------------------
# 3. Save
# ------------------------------------------------------------------
print("[3/3] Saving supplemental data...")
supp = pd.DataFrame(
    all_results,
    columns=["gvkey", "fyear", "datadate", "capx", "intan", "prcc_f"],
)
supp["gvkey"] = supp["gvkey"].astype(str).str.zfill(6)
supp["fyear"] = pd.to_numeric(supp["fyear"], errors="coerce").astype("Int64")

# Drop duplicates if any
supp = supp.drop_duplicates(subset=["gvkey", "fyear"], keep="first")

supp.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
print(f"        Saved: {OUTPUT_PATH}")
print(f"        Rows: {len(supp):,} | Unique gvkeys: {supp['gvkey'].nunique():,}")

# Quick stats
print("\nVariable coverage:")
for col in ["capx", "intan", "prcc_f"]:
    n = supp[col].notna().sum()
    print(f"  {col}: {n:,} non-missing ({n/len(supp)*100:.1f}%)")

print("\nDone. Now run build_control_variables.py to merge.")
