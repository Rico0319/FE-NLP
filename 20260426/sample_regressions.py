import pandas as pd
import numpy as np
import statsmodels.api as sm
from linearmodels.panel import PanelOLS

# Load data
df = pd.read_csv('firm_year_panel_regression_ready.csv')

# Set panel index
df = df.set_index(['ticker', 'fiscal_year'])

# ============================================================
# SPECIFICATION 1: Determinants of AI disclosure
# ============================================================
print("=" * 60)
print("SPEC 1: Determinants of AI Disclosure")
print("=" * 60)

# OLS with year and sector FE
X = df[['log_assets', 'leverage', 'ROA', 'tobin_q_winsorized', 'sales_growth_winsorized',
        'rd_to_assets', 'capex_to_assets']].copy()
X = sm.add_constant(X)

y = df['substantive_ai_disclosure_sentence_intensity']

# Drop rows with missing values
valid = X.notna().all(axis=1) & y.notna()
X_valid = X[valid]
y_valid = y[valid]

model1 = sm.OLS(y_valid, X_valid).fit(cov_type='cluster',
                                        cov_kwds={'groups': df.loc[valid, 'ticker']})
print(model1.summary().tables[1])

# ============================================================
# SPECIFICATION 2: AI disclosure → Tobin's Q (contemporaneous valuation)
# ============================================================
print("\n" + "=" * 60)
print("SPEC 2: AI Disclosure → Tobin's Q")
print("=" * 60)

# Use sample_valuation flag for consistent sample
df_val = df[df['sample_valuation'] == 1].copy()

X2 = df_val[['substantive_ai_disclosure_sentence_intensity',
             'log_assets', 'leverage', 'ROA', 'sales_growth_winsorized',
             'rd_to_assets', 'capex_to_assets']].copy()
X2 = sm.add_constant(X2)
y2 = df_val['tobin_q_winsorized']

valid2 = X2.notna().all(axis=1) & y2.notna()
model2 = sm.OLS(y2[valid2], X2[valid2]).fit(cov_type='cluster',
                                              cov_kwds={'groups': df_val.loc[valid2, 'ticker']})
print(model2.summary().tables[1])

# ============================================================
# SPECIFICATION 3: AI disclosure → Future performance
# ============================================================
print("\n" + "=" * 60)
print("SPEC 3: AI Disclosure → Future ROA")
print("=" * 60)

# Use sample_future_performance flag for consistent sample
df_fut = df[df['sample_future_performance'] == 1].copy()

X3 = df_fut[['substantive_ai_disclosure_sentence_intensity',
             'log_assets', 'leverage', 'ROA', 'tobin_q_winsorized']].copy()
X3 = sm.add_constant(X3)
y3 = df_fut['future_ROA']

valid3 = X3.notna().all(axis=1) & y3.notna()
model3 = sm.OLS(y3[valid3], X3[valid3]).fit(cov_type='cluster',
                                              cov_kwds={'groups': df_fut.loc[valid3, 'ticker']})
print(model3.summary().tables[1])

# ============================================================
# SPECIFICATION 4: Post-AI interaction (GenAI boom effect)
# ============================================================
print("\n" + "=" * 60)
print("SPEC 4: Post-AI Interaction → Tobin's Q")
print("=" * 60)

X4 = df_val[['has_substantive_ai', 'post_ai',
             'has_substantive_ai_x_post_ai',
             'log_assets', 'leverage', 'ROA', 'sales_growth_winsorized',
             'rd_to_assets', 'capex_to_assets']].copy()
X4 = sm.add_constant(X4)
y4 = df_val['tobin_q_winsorized']

valid4 = X4.notna().all(axis=1) & y4.notna()
model4 = sm.OLS(y4[valid4], X4[valid4]).fit(cov_type='cluster',
                                              cov_kwds={'groups': df_val.loc[valid4, 'ticker']})
print(model4.summary().tables[1])

# ============================================================
# SPECIFICATION 5: Firm FE (within-firm variation)
# ============================================================
print("\n" + "=" * 60)
print("SPEC 5: Firm Fixed Effects")
print("=" * 60)

# Need to prepare data for linearmodels
df_panel = df_fut.reset_index()
df_panel = df_panel.set_index(['ticker', 'fiscal_year'])

# Select variables
fe_vars = ['future_ROA', 'substantive_ai_disclosure_sentence_intensity',
           'log_assets', 'leverage', 'ROA', 'tobin_q_winsorized']
df_fe = df_panel[fe_vars].dropna()

# Entity FE + Time FE
exog = sm.add_constant(df_fe[['substantive_ai_disclosure_sentence_intensity',
                                'log_assets', 'leverage', 'ROA', 'tobin_q_winsorized']])

model5 = PanelOLS(df_fe['future_ROA'], exog,
                  entity_effects=True, time_effects=True)
result5 = model5.fit(cov_type='clustered', cluster_entity=True)
print(result5.summary.tables[1])

# ============================================================
# SPECIFICATION 6: AI subcategories
# ============================================================
print("\n" + "=" * 60)
print("SPEC 6: AI Subcategories → Future ROA")
print("=" * 60)

X6 = df_fut[['substantive_ai_implementation_sentence_intensity',
             'substantive_ai_risk_governance_sentence_intensity',
             'log_assets', 'leverage', 'ROA', 'tobin_q_winsorized']].copy()
X6 = sm.add_constant(X6)
y6 = df_fut['future_ROA']

valid6 = X6.notna().all(axis=1) & y6.notna()
model6 = sm.OLS(y6[valid6], X6[valid6]).fit(cov_type='cluster',
                                             cov_kwds={'groups': df_fut.loc[valid6, 'ticker']})
print(model6.summary().tables[1])

print("\n" + "=" * 60)
print("Sample regressions complete!")
print("=" * 60)
