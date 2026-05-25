# Module Documentation: Variance Imputation

## 1. Module Overview
The `variance_imputation` module provides a production-grade implementation of the Generalized Estimation System (G-Est 2.03) methodology for calculating the variance of imputed data. In the presence of non-response, standard variance estimators underestimate the true uncertainty. This module decomposes total variance into sampling, non-response, and mixed components, providing a statistically sound measure of quality for surveys with significant imputation rates. It supports classical regression and donor models as well as modern machine learning-based imputation (XGBoost, MissForest) with linearized variance approximations.

## 2. Table of Contents
- [3. Core Orchestration](#3-core-orchestration)
  - [ImputationOrchestrator](#imputationorchestrator)
  - [run_pipeline](#run_pipeline)
- [4. Variance Computation](#4-variance-computation)
  - [calculate_total_domain_variance](#calculate_total_domain_variance)
- [5. Imputation Engines](#5-imputation-engines)
  - [LinearRegressionImputation](#linearregressionimputation)
  - [DonorImputation](#donorimputation)
  - [XGBoostImputation](#xgboostimputation)
- [6. Quality Assurance & Analytics](#6-quality-assurance--analytics)
  - [VarianceQualityAssurer](#variancequalityassurer)
  - [assign_grade](#assign_grade)
  - [calculate_variance_decomposition](#calculate_variance_decomposition)
- [7. Persistence](#7-persistence)
  - [VariancePersistence](#variancepersistence)

---

## 3. Core Orchestration

### ImputationOrchestrator

#### Description
The master controller that manages imputation model fitting and variance calculation.

#### Usage
`ImputationOrchestrator(metadata)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `metadata` | `NonresponseMetadata` | REQUIRED | A `NonresponseMetadata` object defining target variables, imputation models, and variance methods (analytical or bootstrap). |

#### Details
Initializes the engine mappings and context based on the provided metadata.

#### Value
Initialized `ImputationOrchestrator`.

#### References
N/A

#### Examples
```python
# See run_pipeline() examples below.
```

---

### run_pipeline (ImputationOrchestrator)

#### Description
The main entry point for calculating variance on imputed data.

#### Usage
`orch.run_pipeline(df, imputation_class_col, psi_variance_func)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | The input sampling frame containing both respondents and non-respondents. |
| `imputation_class_col` | `str` | REQUIRED | Column identifying imputation classes. |
| `psi_variance_func` | `callable` | REQUIRED | A function that calculates the sampling variance of a total for a given vector of values. |

#### Details
If `variance_method` is set to analytical, it coordinates the fitting of models and the application of the G-Est variance decomposition. If `bootstrap` is selected, it parallelizes re-imputation across replicate weights.

#### Value
`VarianceResult` with domain-level diagnostics and quality grades.

#### References
- Shao, J., & Steel, P. (1999). Variance estimation for survey data with composite imputation and nonnegligible sampling fractions. *Journal of the American Statistical Association*.

#### Examples
```python
# Example 4: Parallel Bootstrap Re-imputation
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

---

## 4. Variance Computation

### calculate_total_domain_variance

#### Description
A lower-level mathematical function that implements the G-Est variance decomposition.

#### Usage
`calculate_total_domain_variance(y_resp, w_resp, sigma2_hat_resp, mu_hat_resp, mu_hat_nonresp, w_nonresp, v_nonresp, sigma2_hat_nonresp, pi_nonresp, phi_kl, psi_variance_func)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `y_resp` | `np.ndarray` | REQUIRED | Values for respondents. |
| `w_resp` | `np.ndarray` | REQUIRED | Weights for respondents. |
| `sigma2_hat_resp` | `np.ndarray` | REQUIRED | Estimated variances for respondents. |
| `phi_kl` | `np.ndarray` | REQUIRED | Canonical coefficients mapping respondents to non-respondents. |
| `psi_variance_func` | `callable` | REQUIRED | The specific variance functional $\Psi$. |

#### Details
**Total Variance Decomposition**
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

#### Value
A dictionary containing $V_{SAM}$, $V_{NR}$, $V_{MIX}$, and $V_{TOT}$.

#### References
- Statistics Canada. (2010). *Generalized Estimation System (G-Est) Methodology*.

#### Examples
```python
# See Example 1 in LinearRegressionImputation below.
```

---

## 5. Imputation Engines

### LinearRegressionImputation

#### Description
Standard weighted regression engine.

#### Usage
`LinearRegressionImputation()`

#### Arguments
None.

#### Details
**Canonical Coefficients ($\phi_{kl}$)**
For linear regression imputation, $\phi_{kl}$ represents the influence of respondent $k$ on the imputed value of non-respondent $l$:
$$\phi_{kl} = x_{al} x_l^T (X_r^T W_r X_r)^{-1} x_k \frac{w_k}{x_{ak} v_k}$$

#### Value
Initialized `LinearRegressionImputation`.

#### References
N/A

#### Examples
```python
# Example 1: Linear Regression Imputation (Analytical)
import numpy as np
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

---

### DonorImputation

#### Description
Donor-based engine with Thin Plate Spline (TPS) variance approximation.

#### Usage
`DonorImputation()`

#### Arguments
None.

#### Details
Approximates the non-parametric donor structure to fit within the analytical variance decomposition framework using nearest neighbors.

#### Value
Initialized `DonorImputation`.

#### References
N/A

#### Examples
```python
# Example 2: Donor Imputation with TPS Approximation
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

---

### XGBoostImputation

#### Description
Gradient boosting engine with linear-regression-based variance linearization.

#### Usage
`XGBoostImputation(ml_params=None)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `ml_params` | `dict` | `None` | Dictionary of XGBoost hyperparameters. |

#### Details
Uses XGBoost to produce highly accurate predictions, then approximates its complex variance structure linearly.

#### Value
Initialized `XGBoostImputation`.

#### References
N/A

#### Examples
```python
# Example 3: XGBoost Imputation
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

---

## 6. Quality Assurance & Analytics

### VarianceQualityAssurer

#### Description
Evaluates the variance decomposition and assigns an objective quality grade based on the magnitude of the non-response variance penalty.

#### Usage
`VarianceQualityAssurer(metadata)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `metadata` | `NonresponseMetadata` | REQUIRED | Metadata containing penalty definitions. |

#### Details
Prepares context for grading.

#### Value
Initialized `VarianceQualityAssurer`.

#### References
N/A

#### Examples
```python
# qa = VarianceQualityAssurer(metadata)
```

---

### assign_grade (VarianceQualityAssurer)

#### Description
Evaluates the ratio of non-response variance to total variance.

#### Usage
`qa.assign_grade(v_sam, v_nr, fail_rate)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `v_sam` | `float` | REQUIRED | Sampling variance component. |
| `v_nr` | `float` | REQUIRED | Non-response variance component. |
| `fail_rate` | `float` | REQUIRED | Proportion of missing values. |

#### Details
High non-response variance relative to sampling variance triggers a lower grade.

#### Value
A string grade ("A", "B", "C", "D", "F").

#### References
N/A

#### Examples
```python
# grade = qa.assign_grade(100.0, 25.0, 0.1)
```

---

### calculate_variance_decomposition

#### Description
Aggregates the components of variance (Sampling, Nonresponse, Mixed) across multiple domains to provide a macro-level view of the uncertainty introduced by the imputation process.

#### Usage
`calculate_variance_decomposition(df_output)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df_output` | `pl.DataFrame` | REQUIRED | The output DataFrame containing variance components. |

#### Details
Produces percent breakdowns.

#### Value
Dictionary with aggregated variance components and percentage breakdowns.

#### References
N/A

#### Examples
```python
# Example 5: Variance Decomposition Analytics
import polars as pl
from variance_imputation.analytics import calculate_variance_decomposition

df_output = pl.DataFrame({
    "Domain": ["A", "B", "C"],
    "V_SAM": [100.0, 150.0, 50.0],
    "V_NR": [20.0, 50.0, 80.0],
    "V_MIX": [5.0, -10.0, 10.0],
    "V_TOT": [125.0, 190.0, 140.0],
    "CV_Percent": [10.5, 12.0, 25.0]
})

decomp = calculate_variance_decomposition(df_output)
print(f"Total Sampling Variance: {decomp['total_v_sam']}")
print(f"Total Nonresponse Variance: {decomp['total_v_nr']}")
print(f"Percent of variance due to imputation: {decomp['v_nr_pct']:.1f}%")
```

---

## 7. Persistence

### VariancePersistence

#### Description
Manages the serialization of variance metrics and diagnostics to SQLite for auditing.

#### Usage
`VariancePersistence(db_path="variance_imputation_audit.db")`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `db_path` | `str` | `"variance_imputation_audit.db"` | Path to the SQLite DB. |

#### Details
Provides `save_result`.

#### Value
Initialized `VariancePersistence`.

#### References
N/A

#### Examples
```python
# db = VariancePersistence()
# db.save_result("run_01", "revenue", "analytical", result)
```
