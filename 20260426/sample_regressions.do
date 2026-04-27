/*===============================================================
   FE-NLP Project — Sample Stata Regression Code
   Dataset: firm_year_panel_regression_ready.csv
   3,315 firm-years, 486 firms, 2019-2025
   Updated: 2026-04-27 with post_ai, sample flags, winsorized vars
===============================================================*/

* Load data
import delimited using "firm_year_panel_regression_ready.csv", clear

* Set up panel
encode ticker, gen(firm_id)
xtset firm_id fiscal_year

* Encode sector for FE
encode sector, gen(sector_id)

* Create interaction term for post-AI analysis
gen has_substantive_ai_x_post_ai = has_substantive_ai * post_ai

*===============================================================
* Specification 1: AI disclosure ~ firm characteristics
* (Determinants of AI disclosure)
*===============================================================
reg substantive_ai_disclosure_sentence_intensity ///
    log_assets leverage ROA tobin_q_winsorized sales_growth_winsorized ///
    rd_to_assets capex_to_assets ///
    i.fiscal_year i.sector_id, ///
    cluster(ticker)

*===============================================================
* Specification 2: Tobin's Q ~ AI disclosure (contemporaneous valuation)
* Use sample_valuation flag for consistent sample
*===============================================================
reg tobin_q_winsorized substantive_ai_disclosure_sentence_intensity ///
    log_assets leverage ROA sales_growth_winsorized ///
    rd_to_assets capex_to_assets ///
    i.fiscal_year i.sector_id ///
    if sample_valuation == 1, ///
    cluster(ticker)

*===============================================================
* Specification 3: Future performance ~ AI disclosure
* Use sample_future_performance flag for consistent sample
*===============================================================
* Future ROA
reg future_ROA substantive_ai_disclosure_sentence_intensity ///
    log_assets leverage ROA tobin_q_winsorized ///
    i.fiscal_year i.sector_id ///
    if sample_future_performance == 1, ///
    cluster(ticker)

* Future sales growth (winsorized)
reg future_sales_growth_winsorized substantive_ai_disclosure_sentence_intensity ///
    log_assets leverage ROA sales_growth_winsorized ///
    i.fiscal_year i.sector_id ///
    if sample_future_performance == 1, ///
    cluster(ticker)

*===============================================================
* Specification 4: Post-AI interaction (GenAI boom effect)
*===============================================================
reg tobin_q_winsorized ///
    has_substantive_ai post_ai has_substantive_ai_x_post_ai ///
    log_assets leverage ROA sales_growth_winsorized ///
    rd_to_assets capex_to_assets ///
    i.fiscal_year i.sector_id ///
    if sample_valuation == 1, ///
    cluster(ticker)

* Same for future performance
reg future_ROA ///
    has_substantive_ai post_ai has_substantive_ai_x_post_ai ///
    log_assets leverage ROA tobin_q_winsorized ///
    i.fiscal_year i.sector_id ///
    if sample_future_performance == 1, ///
    cluster(ticker)

*===============================================================
* Specification 5: Firm fixed effects (within-firm variation)
*===============================================================
xtreg future_ROA substantive_ai_disclosure_sentence_intensity ///
    log_assets leverage ROA tobin_q_winsorized ///
    i.fiscal_year ///
    if sample_future_performance == 1, ///
    fe cluster(ticker)

*===============================================================
* Specification 6: AI subcategories
*===============================================================
reg future_ROA ///
    substantive_ai_implementation_sentence_intensity ///
    substantive_ai_risk_governance_sentence_intensity ///
    log_assets leverage ROA tobin_q_winsorized ///
    i.fiscal_year i.sector_id ///
    if sample_future_performance == 1, ///
    cluster(ticker)

* Use ROE_winsorized to handle extreme values
reg ROE_winsorized substantive_ai_disclosure_sentence_intensity ///
    log_assets leverage tobin_q_winsorized ///
    i.fiscal_year i.sector_id ///
    if sample_valuation == 1, ///
    cluster(ticker)
