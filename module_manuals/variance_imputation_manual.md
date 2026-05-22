# Module Documentation: variance_imputation

## 1. Module Overview: variance_imputation

The `variance_imputation` module provides a production-grade implementation of the Generalized Estimation System (G-Est 2.03) methodology for calculating the variance of imputed data. In the presence of non-response, standard variance estimators underestimate the true uncertainty. This module decomposes total variance into sampling, non-response, and mixed components, providing a statistically sound measure of quality for surveys with significant imputation rates. It supports classical regression and donor models as well as modern machine learning-based imputation (XGBoost, MissForest) with linearized variance approximations.

---

## 2. Core Classes & Initialization

### ImputationOrchestrator
> The master controller that manages imputation model fitting and variance calculation.

**Initialization:** `ImputationOrchestrator(metadata: NonresponseMetadata)`
- **metadata**: A `NonresponseMetadata` object defining target variables, imputation models, and variance methods (analytical or bootstrap).

### Imputation Engines
> Specific engines for fitting models and imputing values.

- **LinearRegressionImputation**: Standard weighted regression engine.
- **DonorImputation**: Donor-based engine with Thin Plate Spline (TPS) variance approximation.
- **XGBoostImputation**: Gradient boosting engine with linear-regression-based variance linearization.

---

## 3. Core Methods & Functions

### Orchestrator.run_pipeline(df, imputation_class_col, psi_variance_func)
The main entry point for calculating variance on imputed data.
- **psi_variance_func**: A function that calculates the sampling variance of a total for a given vector of values.
- **Returns**: `VarianceResult` with domain-level diagnostics and quality grades.

### calculate_total_domain_variance(...)
A lower-level mathematical function that implements the G-Est variance decomposition.
- **Returns**: A dictionary containing $V_{SAM}$, $V_{NR}$, $V_{MIX}$, and $V_{TOT}$.

---

## 4. Details (Methodology & Mathematics)

### Total Variance Decomposition
The total variance $V_{TOT}$ is estimated as the sum of three components:
$$V_{TOT} = V_{SAM} + V_{NR} + V_{MIX}$$

1.  **Sampling Variance ($V_{SAM}$)**:
    $$V_{SAM} = \hat{V}_{design}(\tilde{y}) + \sum_{l \in s_m} (1 - \pi_l) w_l^2 \sigma_l^2$$
    where $\tilde{y}$ is the vector of respondent and imputed values.
2.  **Non-response Variance ($V_{NR}$)**:
    $$V_{NR} = \sum_{k \in s_r} W_{dk}^2 \sigma_k^2 + \sum_{l \in s_m} w_l^2 \sigma_l^2 + \hat{B}_c^2$$
    where $W_{dk}$ are the compensation weights derived from canonical coefficients $\phi_{kl}$.
3.  **Mixed Variance ($V_{MIX}$)**:
    $$V_{MIX} = 2 \left[ \sum_{k \in s_r} (w_k - 1) W_{dk} \sigma_k^2 - \sum_{l \in s_m} w_l(w_l - 1) \sigma_l^2 \right]$$

### Canonical Coefficients ($\phi_{kl}$)
For linear regression imputation, $\phi_{kl}$ represents the influence of respondent $k$ on the imputed value of non-respondent $l$:
$$\phi_{kl} = x_{al} x_l^T (X_r^T W_r X_r)^{-1} x_k \frac{w_k}{x_{ak} v_k}$$

---

## 5. References

Statistics Canada. (2010). *Generalized Estimation System (G-Est) Methodology*.

Shao, J., & Steel, P. (1999). Variance estimation for survey data with composite imputation and nonnegligible sampling fractions. *Journal of the American Statistical Association*.

---

## 6. Runnable Examples

### Example 1: Linear Regression Imputation (Analytical)
```python
import numpy as np
import polars as pl
from variance_imputation.engine import LinearRegressionImputation, calculate_total_domain_variance

# Synthetic data: 5 respondents, 2 non-respondents
x_resp = np.array([[1, 10], [1, 12], [1, 15], [1, 14], [1, 16]])
y_resp = np.array([100, 120, 150, 140, 160])
x_nonresp = np.array([[1, 11], [1, 13]])
w_resp = np.array([20.0, 20.0, 20.0, 20.0, 20.0])
w_nonresp = np.array([20.0, 20.0])

engine = LinearRegressionImputation()
# Simple adjustment factors (all 1.0)
v_all = np.ones(7)
xa_all = np.ones(7)

y_imp = engine.fit_impute(x_resp, y_resp, x_nonresp, w_resp, v_all[:5], xa_all[:5], xa_all[5:])
mu_hat, sigma2_hat = engine.estimate_model_parameters(np.vstack([x_resp, x_nonresp]), y_resp, x_resp, np.ones(7), v_all[:5], v_all, xa_all)
phi_kl = engine.calculate_canonical_coefficients(x_resp, x_nonresp, w_resp, v_all[:5], xa_all[:5], xa_all[5:])

# Dummy sampling variance func
psi = lambda y: np.var(y) * len(y)**2

res = calculate_total_domain_variance(
    y_resp, w_resp, sigma2_hat[:5], mu_hat[:5], 
    mu_hat[5:], w_nonresp, np.ones(2), sigma2_hat[5:], np.array([0.05, 0.05]),
    phi_kl, psi
)
print(f"Total Variance: {res['V_TOT']:.2f}, CV: {res['CV']*100:.2f}%")
```

### Example 2: Donor Imputation with TPS Approximation
```python
import numpy as np
from variance_imputation.engine import DonorImputation

x_resp = np.array([[10], [12], [15], [14], [16]])
y_resp = np.array([100, 120, 150, 140, 160])
x_nonresp = np.array([[11], [13]])

engine = DonorImputation()
# Use nearest neighbor indices as donors
donor_indices = [0, 1] 
y_imp, phi_kl = engine.fit_impute(x_resp, y_resp, x_nonresp, donor_indices)
mu_k, sigma2_k = engine.estimate_model_parameters_tps(x_resp, y_resp, np.vstack([x_resp, x_nonresp]))

print(f"Imputed values: {y_imp}")
print(f"TPS Sigma2 estimates for non-respondents: {sigma2_k[5:]}")
```

### Example 3: XGBoost Imputation
```python
import numpy as np
from variance_imputation.engine import XGBoostImputation

x_resp = np.random.rand(20, 2)
y_resp = 5 * x_resp[:, 0] + 3 * x_resp[:, 1] + np.random.normal(0, 0.1, 20)
x_nonresp = np.random.rand(5, 2)
w_imp = np.ones(20)

engine = XGBoostImputation(ml_params={"n_estimators": 10, "max_depth": 3})
y_imp = engine.fit_impute(x_resp, y_resp, x_nonresp, w_imp)

print(f"XGBoost Imputed Values: {y_imp[:3]}...")
```

### Example 4: Parallel Bootstrap Re-imputation
```python
import polars as pl
from variance_imputation.orchestrator import ImputationOrchestrator
from variance_imputation.models import NonresponseMetadata, ImputationModelConfig

df = pl.DataFrame({
    "domain": ["A", "A", "A", "B", "B", "B"],
    "class": ["C1", "C1", "C1", "C1", "C1", "C1"],
    "revenue": [100.0, None, 150.0, 200.0, None, 250.0],
    "aux": [1.0, 1.1, 1.5, 2.0, 2.1, 2.5],
    "weight": [10.0] * 6,
    "pi": [0.1] * 6,
    "rep_1": [12.0, 12.0, 12.0, 8.0, 8.0, 8.0],
    "rep_2": [8.0, 8.0, 8.0, 12.0, 12.0, 12.0]
})

meta = NonresponseMetadata(
    target_var="revenue",
    weight_var="weight",
    domain_var="domain",
    pi_var="pi",
    variance_method="bootstrap",
    bootstrap_weight_prefix="rep_",
    hierarchy={"sampling_unit_id": "u", "imputation_unit_id": "u", "estimation_unit_id": "u"},
    imputation_model=ImputationModelConfig(method="LinearRegression", aux_vars=["aux"]),
    persist_results=False
)

orch = ImputationOrchestrator(meta)
# psi function for bootstrap is not strictly needed for the bootstrap re-imputation process itself
result = orch.run_pipeline(df, imputation_class_col="class", psi_variance_func=None)

print(f"Overall Quality: {result.overall_quality_grade}")
for d, diag in result.diagnostics.items():
    print(f"Domain {d}: V_TOT={diag.v_tot:.2f}, CV={diag.cv_percent:.2f}%")
```
