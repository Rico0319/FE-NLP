/*===============================================================
   FE-NLP Project — Sample Stata Regression Code
   Dataset: firm_year_panel_regression_ready.csv
   3,315 firm-years, 486 firms, 2019-2025
===============================================================*/

* Load data
import delimited using "20260426/firm_year_panel_regression_ready.csv", clear

* Set up panel
encode ticker, gen(firm_id)
xtset gvkey fiscal_year

* Encode sector for FE
encode sector, gen(sector_id)

*===============================================================
* Specification 1: AI disclosure ~ firm characteristics
* (Determinants of AI disclosure)
*===============================================================
reg substantive_ai_disclosure_sentence_intensity ///
    log_assets leverage roa tobin_q sales_growth ///
    rd_to_assets capex_to_assets ///
    i.fiscal_year i.sector_id, ///
    cluster(gvkey)

*===============================================================
* Specification 2: Future performance ~ AI disclosure
* (Does AI disclosure predict performance?)
*===============================================================
* Future ROA
reg future_roa substantive_ai_disclosure_sentence_intensity ///
    log_assets leverage roa tobin_q ///
    i.fiscal_year i.sector_id, ///
    cluster(gvkey)

* Future sales growth
reg future_sales_growth substantive_ai_disclosure_sentence_intensity ///
    log_assets leverage roa sales_growth ///
    i.fiscal_year i.sector_id, ///
    cluster(gvkey)

*===============================================================
* Specification 3: Firm fixed effects (within-firm variation)
*===============================================================
xtreg future_roa substantive_ai_disclosure_sentence_intensity ///
    log_assets leverage roa tobin_q ///
    i.fiscal_year, ///
    fe cluster(gvkey)

*===============================================================
* Specification 4: AI subcategories
*===============================================================
reg future_roa ///
    substantive_ai_implementation_sentence_intensity ///
    substantive_ai_risk_governance_sentence_intensity ///
    log_assets leverage roa tobin_q ///
    i.fiscal_year i.sector_id, ///
    cluster(gvkey)

* Use ROE_winsorized to handle extreme values
reg roe_winsorized substantive_ai_disclosure_sentence_intensity ///
    log_assets leverage tobin_q ///
    i.fiscal_year i.sector_id, ///
    cluster(gvkey)
