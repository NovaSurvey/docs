# Module Documentation: variance_estimation

## 1. Module Overview: variance_estimation

The `variance_estimation` module is a high-performance statistical engine designed to calculate point estimates and their associated sampling variances for complex survey designs. It supports both **Analytical Variance Estimation** (via Taylor Linearization) and **Empirical Variance Estimation** (via Bootstrap). The module is specifically hardened for official statistics production, supporting calibration adjustments (GREG estimation), multi-phase sampling, and domain-level reporting for totals, means, and ratios.

---

## 2. Core Classes & Initialization

### VarianceEngine
> The primary execution engine for variance and point estimation.

**Initialization:** `VarianceEngine(metadata: VarianceMetadata)`
- **metadata**: A `VarianceMetadata` object defining variables, design parameters, and estimation requests.

### VarianceMetadata
> Configuration container for the estimation task.

**Parameters:**
- **final_weight_var**: The calibrated weight column ($w_k$).
- **design_weight_var**: The initial design weight column ($d_k$).
- **domain_vars**: List of columns defining population sub-domains.
- **parameters**: List of `ParameterRequest` objects (Size, Total, Mean, Ratio).
- **design_config**: A `VarianceDesignConfig` defining the survey design (SRSWOR, Poisson, or Two-Phase).

---

## 3. Core Methods & Functions

### VarianceEngine.calculate_variance(df)
Dispatches the estimation request to the analytical or bootstrap handler based on the `variance_method` configuration.
- **Returns**: Polars DataFrame containing Estimate, Variance, Standard Error, and CV% per domain.

### VarianceEngine._calculate_bootstrap_variance(df) (Internal)
Calculates variance by computing point estimates across multiple replicate weight columns and taking their empirical variance.

---

## 4. Details (Methodology & Mathematics)

### Taylor Linearization ($u_k$)
For non-linear parameters, the module computes linearized variables ($u_k$) such that the variance of the non-linear estimator $\hat{\theta}$ is approximately the variance of the total of $u_k$.
- **Total**: $u_k = y_k$
- **Mean**: $u_k = \frac{1}{\hat{N}} (y_k - \hat{\bar{Y}})$
- **Ratio**: $u_k = \frac{1}{\hat{Y}_2} (y_{1k} - \hat{R} y_{2k})$

### Calibration Residual Engine ($e_k$)
If the weights are calibrated, the variance is calculated using residuals to account for the reduction in variance provided by auxiliary information $x_k$:
$$e_k = u_k - x_k^T \beta$$
Where the regression vector $\beta$ is estimated using weighted least squares (or pseudo-inverse for robustness):
$$\beta = (X^T W X)^{-1} X^T W u, \quad W = \text{diag}(d_k / c_k)$$
The final variance is computed on the term $g_k e_k$, where $g_k = w_k / d_k$ is the calibration factor.

### Sampling Design Variances
1.  **Stratified SRSWOR**:
    $$\hat{V}(\hat{Y}) = \sum_{h} N_h^2 \left(1 - \frac{n_h}{N_h}\right) \frac{s_h^2}{n_h}$$
    where $s_h^2$ is the sample variance of $g_k e_k$ within stratum $h$.
2.  **Poisson Sampling**:
    $$\hat{V}(\hat{Y}) = \sum_{k \in s} d_k (d_k - 1) (g_k e_k)^2$$

---

## 5. References

Särndal, C.-E., Swensson, B., & Wretman, J. (1992). *Model Assisted Survey Sampling*. Springer.

Deville, J.-C., & Särndal, C.-E. (1992). Calibration Estimators in Survey Sampling. *Journal of the American Statistical Association*, 87(418), 376-382.

Wolter, K. M. (2007). *Introduction to Variance Estimation*. Second Edition. Springer.

---

## 6. Runnable Examples

### Example 1: Stratified SRSWOR Variance
```python
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

### Example 2: Calibrated GREG Variance (Residuals)
```python
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

### Example 3: Ratio Estimation (Analytical Taylor)
```python
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

### Example 4: Bootstrap Replicate Variance
```python
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
