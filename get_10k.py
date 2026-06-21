# =========================================
# S&P 500 (Selected Industries) 10-K MD&A Extraction
# =========================================

import psycopg2
import pandas as pd
import requests
import re
import time
import getpass

# -----------------------------
# 1. CONNECT
# -----------------------------
conn = psycopg2.connect(
    host="wrds-pgdata.wharton.upenn.edu",
    database="wrds",
    user="username",
    password=getpass.getpass("WRDS password: "),
    port=9737
)
conn.autocommit = True

# -----------------------------
# 2. GET S&P 500 + NAICS FILTER
# -----------------------------
print("Fetching S&P 500 firms (filtered by NAICS)...")

sp500_query = """
SELECT DISTINCT c.cik, c.naics
FROM crsp.msp500list sp
JOIN crsp.ccmxpf_linktable link
    ON sp.permno = link.lpermno
JOIN comp.company c
    ON link.gvkey = c.gvkey
WHERE sp.start <= '2026-12-31'
AND (sp.ending IS NULL OR sp.ending >= '2018-01-01')
AND link.linktype IN ('LU','LC')
AND link.linkprim IN ('P','C')
AND c.naics IS NOT NULL
AND LEFT(c.naics, 2) IN ('22','51','52','53','61','62');
"""

sp500 = pd.read_sql(sp500_query, conn)

print(f"Filtered S&P 500 firms: {len(sp500)}")

# Optional: check distribution
print("\nIndustry distribution:")
print(sp500['naics'].str[:2].value_counts())

# -----------------------------
# 3. GET 10-K FILINGS
# -----------------------------
print("\nFetching 10-K filings...")

query = """
SELECT cik, accession, fdate, coname, fname
FROM wrdssec_secsa.bow_filingsummary
WHERE form = '10-K'
AND fdate BETWEEN '2018-01-01' AND '2026-12-31';
"""

df = pd.read_sql(query, conn)

# Keep only filtered firms
df = df[df['cik'].isin(sp500['cik'])]

print(f"Filtered filings: {len(df)}")

# Build SEC URLs
df['url'] = "https://www.sec.gov/Archives/" + df['fname']

# OPTIONAL: test first
# df = df.head(50)

# -----------------------------
# 4. MD&A EXTRACTION FUNCTION
# -----------------------------
def extract_mdna(text):
    try:
        # Remove SEC header
        text = re.sub(r'<SEC-HEADER>.*?</SEC-HEADER>', ' ', text, flags=re.S)

        # Remove HTML
        text = re.sub(r'<.*?>', ' ', text)

        # Remove non-ASCII junk
        text = re.sub(r'[^\x00-\x7F]+', ' ', text)

        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)

        # Extract MD&A (Item 7 → Item 8)
        matches = re.findall(
            r'item\s+7[^a-zA-Z]{0,10}.*?(?=item\s+8)',
            text,
            re.IGNORECASE | re.DOTALL
        )

        return max(matches, key=len) if matches else None

    except:
        return None

# -----------------------------
# 5. DOWNLOAD + PROCESS
# -----------------------------
headers = {"User-Agent": "your_email@example.com"}
results = []

print("\nStarting extraction...\n")

for i, row in df.iterrows():
    try:
        print(f"{i+1}/{len(df)}: {row['coname']} ({row['fdate']})")

        response = requests.get(row['url'], headers=headers, timeout=15)
        text = response.text

        mdna = extract_mdna(text)

        results.append({
            'cik': row['cik'],
            'date': row['fdate'],
            'company': row['coname'],
            'mdna': mdna
        })

        # Avoid SEC rate limits
        time.sleep(0.2)

    except Exception as e:
        print(f"Error: {e}")
        continue

# -----------------------------
# 6. SAVE RESULTS
# -----------------------------
print("\nSaving results...")

mdna_df = pd.DataFrame(results)
mdna_df.to_csv("sp500_selected_industries_mdna_2018_2026.csv", index=False)

print("Done!")