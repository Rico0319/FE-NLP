import pandas as pd
import numpy as np
import statsmodels.api as sm
from linearmodels.panel import PanelOLS

# Load data
df = pd.read_csv('20260426/firm_year_panel_regression_ready.csv')

# Set panel index
df = df.set_index(['gvkey', 'fiscal_year'])

# ============================================================
# SPECIFICATION 1: Determinants of AI disclosure
# ============================================================
print("=" * 60)
print("SPEC 1: Determinants of AI Disclosure")
print("=" * 60)

# OLS with year and sector FE
X = df[['log_assets', 'leverage', 'ROA', 'tobin_q', 'sales_growth', 
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
# SPECIFICATION 2: AI disclosure → Future performance
# ============================================================
print("\n" + "=" * 60)
print("SPEC 2: AI Disclosure → Future ROA")
print("=" * 60)

X2 = df[['substantive_ai_disclosure_sentence_intensity',
         'log_assets', 'leverage', 'ROA', 'tobin_q']].copy()
X2 = sm.add_constant(X2)
y2 = df['future_ROA']

valid2 = X2.notna().all(axis=1) & y2.notna()
model2 = sm.OLS(y2[valid2], X2[valid2]).fit(cov_type='cluster',
                                              cov_kwds={'groups': df.loc[valid2, 'ticker']})
print(model2.summary().tables[1])

# ============================================================
# SPECIFICATION 3: Firm FE (within-firm variation)
# ============================================================
print("\n" + "=" * 60)
print("SPEC 3: Firm Fixed Effects")
print("=" * 60)

# Need to prepare data for linearmodels
df_panel = df.reset_index()
df_panel = df_panel.set_index(['gvkey', 'fiscal_year'])

# Select variables
fe_vars = ['future_ROA', 'substantive_ai_disclosure_sentence_intensity',
           'log_assets', 'leverage', 'ROA', 'tobin_q']
df_fe = df_panel[fe_vars].dropna()

# Entity FE + Time FE
exog = sm.add_constant(df_fe[['substantive_ai_disclosure_sentence_intensity',
                            'log_assets', 'leverage', 'ROA', 'tobin_q']])

model3 = PanelOLS(df_fe['future_ROA'], exog, 
                  entity_effects=True, time_effects=True)
result3 = model3.fit(cov_type='clustered', cluster_entity=True)
print(result3.summary.tables[1])

# ============================================================
# SPECIFICATION 4: AI subcategories
# ============================================================
print("\n" + "=" * 60)
print("SPEC 4: AI Subcategories → Future ROA")
print("=" * 60)

X4 = df[['substantive_ai_implementation_sentence_intensity',
         'substantive_ai_risk_governance_sentence_intensity',
         'log_assets', 'leverage', 'ROA', 'tobin_q']].copy()
X4 = sm.add_constant(X4)
y4 = df['future_ROA']

valid4 = X4.notna().all(axis=1) & y4.notna()
model4 = sm.OLS(y4[valid4], X4[valid4]).fit(cov_type='cluster',
                                             cov_kwds={'groups': df.loc[valid4, 'ticker']})
print(model4.summary().tables[1])

print("\n" + "=" * 60)
print("Sample regressions complete!")
print("=" * 60)
