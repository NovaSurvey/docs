# Module Documentation: Variance Estimation

## 1. Module Overview
The `variance_estimation` module is a high-performance statistical engine designed to calculate point estimates and their associated sampling variances for complex survey designs. It supports both **Analytical Variance Estimation** (via Taylor Linearization) and **Empirical Variance Estimation** (via Bootstrap). The module is specifically hardened for official statistics production, supporting calibration adjustments (GREG estimation), multi-phase sampling, and domain-level reporting for totals, means, and ratios.

## 2. Table of Contents
- [3. Core Orchestration](#3-core-orchestration)
  - [VarianceEngine](#varianceengine)
  - [calculate_variance](#calculate_variance)
  - [_calculate_bootstrap_variance](#_calculate_bootstrap_variance)
- [4. Precision Analytics](#4-precision-analytics)
  - [calculate_precision_metrics](#calculate_precision_metrics)

---

## 3. Core Orchestration

### VarianceEngine

#### Description
The primary execution engine for variance and point estimation.

#### Usage
`VarianceEngine(metadata)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `metadata` | `VarianceMetadata` | REQUIRED | A configuration object defining variables, design parameters, and estimation requests. |

#### Details
Initializes the estimation context. `VarianceMetadata` specifies `final_weight_var`, `design_weight_var`, `domain_vars`, `parameters` (Size, Total, Mean, Ratio), and the `design_config` (SRSWOR, Poisson).

#### Value
Initialized `VarianceEngine`.

#### References
N/A

#### Examples
```python
# See calculate_variance() examples below.
```

---

### calculate_variance (VarianceEngine)

#### Description
Dispatches the estimation request to the analytical or bootstrap handler based on the configuration.

#### Usage
`engine.calculate_variance(df)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | The input sampling frame with weights and response variables. |

#### Details
**Taylor Linearization ($u_k$)**
For non-linear parameters, the module computes linearized variables ($u_k$) such that the variance of the non-linear estimator $\hat{\theta}$ is approximately the variance of the total of $u_k$.
- **Total**: $u_k = y_k$
- **Mean**: $u_k = \frac{1}{\hat{N}} (y_k - \hat{\bar{Y}})$
- **Ratio**: $u_k = \frac{1}{\hat{Y}_2} (y_{1k} - \hat{R} y_{2k})$

**Calibration Residual Engine ($e_k$)**
If the weights are calibrated, the variance is calculated using residuals to account for the reduction in variance provided by auxiliary information $x_k$:
$$e_k = u_k - x_k^T \beta$$
Where the regression vector $\beta$ is estimated using weighted least squares (or pseudo-inverse for robustness):
$$\beta = (X^T W X)^{-1} X^T W u, \quad W = \text{diag}(d_k / c_k)$$
The final variance is computed on the term $g_k e_k$, where $g_k = w_k / d_k$ is the calibration factor.

**Sampling Design Variances**
1.  **Stratified SRSWOR**:
    $$\hat{V}(\hat{Y}) = \sum_{h} N_h^2 \left(1 - \frac{n_h}{N_h}\right) \frac{s_h^2}{n_h}$$
    where $s_h^2$ is the sample variance of $g_k e_k$ within stratum $h$.
2.  **Poisson Sampling**:
    $$\hat{V}(\hat{Y}) = \sum_{k \in s} d_k (d_k - 1) (g_k e_k)^2$$

#### Value
Polars DataFrame containing Estimate, Variance, Standard Error, and CV% per domain.

#### References
- Särndal, C.-E., Swensson, B., & Wretman, J. (1992). *Model Assisted Survey Sampling*. Springer.
- Deville, J.-C., & Särndal, C.-E. (1992). Calibration Estimators in Survey Sampling. *Journal of the American Statistical Association*, 87(418), 376-382.
- Wolter, K. M. (2007). *Introduction to Variance Estimation*. Second Edition. Springer.

#### Examples
```python
# Example 1: Stratified SRSWOR Variance
import polars as pl
from variance_estimation.engine import VarianceEngine
from variance_estimation.models import VarianceMetadata, ParameterRequest, VarianceDesignConfig

df = pl.DataFrame({
    "stratum": ["H1", "H1", "H2", "H2", "H2"],
    "N_h": [100, 100, 200, 200, 200],
    "w_design": [50.0, 50.0, 66.6, 66.6, 66.6],
    "w_final": [50.0, 50.0, 66.6, 66.6, 66.6],
    "revenue": [10.0, 12.0, 15.0, 14.0, 16.0]
})

meta = VarianceMetadata(
    design_weight_var="w_design",
    final_weight_var="w_final",
    domain_vars=[],
    parameters=[ParameterRequest(param_type="Total", name="Total_Rev", y_var="revenue")],
    design_config=VarianceDesignConfig(
        design_type="SRSWOR",
        stratum_var="stratum",
        pop_size_var="N_h"
    )
)

engine = VarianceEngine(meta)
results = engine.calculate_variance(df)
print(results.select(["Parameter", "Estimate", "Standard_Error", "CV_Percent"]))
```

```python
# Example 2: Calibrated GREG Variance (Residuals)
import polars as pl
from variance_estimation.engine import VarianceEngine
from variance_estimation.models import VarianceMetadata, ParameterRequest, VarianceDesignConfig

# Units with different G-factors due to calibration on 'aux1'
df = pl.DataFrame({
    "stratum": ["S1"] * 5,
    "N_h": [1000] * 5,
    "w_design": [200.0] * 5,
    "w_final": [210.0, 190.0, 205.0, 195.0, 200.0],
    "revenue": [50, 45, 60, 55, 52],
    "aux1": [1.2, 0.8, 1.3, 0.9, 1.0]
})

meta = VarianceMetadata(
    design_weight_var="w_design",
    final_weight_var="w_final",
    domain_vars=[],
    is_calibrated=True,
    auxiliary_vars=["aux1"],
    parameters=[ParameterRequest(param_type="Total", name="Total_Rev", y_var="revenue")],
    design_config=VarianceDesignConfig(design_type="SRSWOR", stratum_var="stratum", pop_size_var="N_h")
)

engine = VarianceEngine(meta)
results = engine.calculate_variance(df)
print(results.select(["Parameter", "Estimate", "Standard_Error"]))
```

```python
# Example 3: Ratio Estimation (Analytical Taylor)
import polars as pl
from variance_estimation.engine import VarianceEngine
from variance_estimation.models import VarianceMetadata, ParameterRequest, VarianceDesignConfig

df = pl.DataFrame({
    "w_design": [10.0] * 10,
    "w_final": [10.0] * 10,
    "revenue": [100, 150, 120, 130, 140] * 2,
    "expenses": [80, 120, 100, 110, 115] * 2
})

meta = VarianceMetadata(
    design_weight_var="w_design",
    final_weight_var="w_final",
    domain_vars=[],
    parameters=[ParameterRequest(param_type="Ratio", name="Margin", y_var="revenue", y2_var="expenses")],
    design_config=VarianceDesignConfig(design_type="Poisson")
)

engine = VarianceEngine(meta)
results = engine.calculate_variance(df)
print(results.select(["Parameter", "Estimate", "CV_Percent"]))
```

---

### _calculate_bootstrap_variance (VarianceEngine)

#### Description
Calculates variance empirically by computing point estimates across multiple replicate weight columns.

#### Usage
`engine._calculate_bootstrap_variance(df)` (Internal, called by `calculate_variance`)

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | The input sampling frame with replicate weights. |

#### Details
Empirically computes variance across all provided bootstrap replicates.

#### Value
Polars DataFrame containing empirical Estimate, Variance, Standard Error, and CV%.

#### References
N/A

#### Examples
```python
# Example 4: Bootstrap Replicate Variance
import polars as pl
from variance_estimation.engine import VarianceEngine
from variance_estimation.models import VarianceMetadata, ParameterRequest, VarianceDesignConfig

df = pl.DataFrame({
    "w_final": [10.0, 10.0, 10.0],
    "rep_wt_1": [12.0, 8.0, 10.0],
    "rep_wt_2": [9.0, 11.0, 10.0],
    "revenue": [100, 200, 150]
})

meta = VarianceMetadata(
    design_weight_var="w_final",
    final_weight_var="w_final",
    domain_vars=[],
    variance_method="bootstrap",
    bootstrap_weight_prefix="rep_wt_",
    parameters=[ParameterRequest(param_type="Total", name="Total_Rev", y_var="revenue")],
    design_config=VarianceDesignConfig(design_type="Poisson") # Placeholder for bootstrap
)

engine = VarianceEngine(meta)
results = engine.calculate_variance(df)
print(results.select(["Parameter", "Estimate", "Variance"]))
```

---

## 4. Precision Analytics

### calculate_precision_metrics

#### Description
Evaluates the calculated variances across all domains and parameters to generate macro-level precision diagnostics.

#### Usage
`calculate_precision_metrics(df_output)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df_output` | `pl.DataFrame` | REQUIRED | The calculated variance DataFrame output from the engine. |

#### Details
Calculates the proportion of estimates meeting target CV thresholds and identifies domains with critically high variance.

#### Value
Dictionary containing precision metrics and threshold violation counts.

#### References
N/A

#### Examples
```python
# Example 5: Precision Analytics
import polars as pl
from variance_estimation.analytics import calculate_precision_metrics

# Simulated output from VarianceEngine.calculate_variance
df_output = pl.DataFrame({
    "Domain": ["Total", "Region A", "Region B"],
    "Parameter": ["Total_Rev", "Total_Rev", "Total_Rev"],
    "Estimate": [1000.0, 600.0, 400.0],
    "CV_Percent": [5.2, 12.5, 35.0] # Region B has high CV
})

metrics = calculate_precision_metrics(df_output)
print(f"Total Estimates Evaluated: {metrics['total_estimates']}")
print(f"Estimates with CV > 16.5%: {metrics['cv_above_16_5']}")
print(f"Estimates with CV > 33.3%: {metrics['cv_above_33_3']}")
```
