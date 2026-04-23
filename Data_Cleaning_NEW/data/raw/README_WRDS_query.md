# WRDS Supplemental Data Query

The control-variables panel needs three additional Compustat items that are
not in the base annual extract:

| Variable | Compustat Item | Needed For |
|----------|---------------|------------|
| capx     | Capital Expenditures | Capex / Assets |
| intan    | Intangible Assets    | Intangibles / Assets |
| prcc_f   | Price Close (FY end) | Tobin's Q |

## WRDS SQL Query

Run this in WRDS (Compustat / CRSP) and download the result as CSV:

```sql
SELECT a.gvkey,
       a.fyear,
       a.datadate,
       a.capx,
       a.intan,
       a.prcc_f
FROM   comp.funda a
WHERE  a.gvkey IN (
           SELECT DISTINCT gvkey
           FROM   your_firm_list   /* zero-padded 6-char strings, e.g. '001004' */
       )
   AND a.fyear BETWEEN 2018 AND 2025
   AND a.indfmt = 'INDL'
   AND a.datafmt = 'STD'
   AND a.popsrc = 'D'
   AND a.consol = 'C'
ORDER BY a.gvkey, a.fyear;
```

> ⚠️ **CRITICAL:** `comp.funda.gvkey` is a `VARCHAR`. If you pass integers (e.g. `1004`)
> instead of zero-padded strings (`'001004'`), the query will silently return **zero rows**
> for most firms. Always `str.zfill(6)` before querying.

## After Download

1. Save the CSV as:
   ```
   Data_Cleaning_NEW/data/raw/compustat_supplemental_2018_2025.csv
   ```

2. Re-run the build script:
   ```bash
   python Data_Cleaning_NEW/scripts/build_control_variables.py
   ```

The script will automatically merge the supplemental data and fill in
`capex_to_assets`, `intangibles_to_assets`, and `tobin_q`.
