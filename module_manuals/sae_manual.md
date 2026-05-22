# Module Documentation: sae

## 1. Module Overview: sae

The `sae` (Small Area Estimation) module is a sophisticated statistical package designed to produce reliable estimates for geographic or demographic domains with small sample sizes. By "borrowing strength" from auxiliary data (e.g., administrative records) through a linking model, it mitigates the high variance associated with direct survey estimators. The module implements the classical **Fay-Herriot (EBLUP)** model, **Robust REBLUP (Sinha-Rao)** for outlier protection, and **Hierarchical Bayes (HB)**, all integrated into a unified orchestration pipeline with automated validation, variance smoothing, and hierarchical benchmarking.

---

## 2. Core Classes & Initialization

### SAEOrchestrator
> The primary entry point for multi-model SAE execution and validation.

**Initialization:** `SAEOrchestrator(df_direct, area_id_var, target_var, variance_var, aux_vars, n_var=None, db_path=None)`
- **df_direct**: Polars DataFrame containing area-level direct estimates.
- **area_id_var**: Unique identifier for small areas.
- **target_var**: Direct point estimates.
- **variance_var**: Direct variance estimates.
- **aux_vars**: List of auxiliary predictors.

### SAEEngine (EBLUP)
> Implements the Fay-Herriot model and REML solver.

**Initialization:** `SAEEngine(metadata: SAEMetadata)`
- **metadata**: An `SAEMetadata` object containing variable mappings and an `SAEConfig` for model parameters (e.g., `robust=True`, `huber_c=1.345`).

---

## 3. Core Methods & Functions

### SAEOrchestrator.run_all_and_validate(configs)
Master pipeline that executes configured models (EBLUP, HB, MERF) and returns a validation report for each.
- **Returns**: A dictionary of results keyed by model type, including bias diagnostics and shrinkage metrics.

### SAEEngine.process(df)
The primary execution method for the EBLUP Fay-Herriot model.
- **Returns**: `SAEResult` containing the EBLUP estimates, MSE, and model variance ($\sigma^2_v$).

### SAEEngine._process_robust(df)
Executes the Robust Fay-Herriot (REBLUP) logic using Sinha-Rao Huber-penalized estimating equations.
- **Returns**: `SAEResult` with outlier-robust estimates and an `outlier_flag` column.

### SAEBootstrapMSE.calculate_mse(df, target_col, var_col, aux_vars)
Calculates parametric bootstrap MSE for EBLUP estimates.
- **Returns**: DataFrame updated with a `robust_bootstrap_mse` column.

### SAEOrchestrator.reconcile_results(result, df_top, parent_keys, child_key)
Applies top-down hierarchical benchmarking to ensure small area estimates sum to known population totals.

---

## 4. Details (Methodology & Mathematics)

### Fay-Herriot Model (EBLUP)
The area-level model assumes:
1.  **Sampling Model**: $\hat{\theta}_i^{DIR} = \theta_i + e_i, \quad e_i \sim N(0, \psi_i)$
2.  **Linking Model**: $\theta_i = X_i\beta + v_i, \quad v_i \sim N(0, \sigma^2_v)$

The EBLUP is the weighted average of the direct estimate and the synthetic regression estimate:
$$\hat{\theta}_i^{EBLUP} = \hat{\gamma}_i \hat{\theta}_i^{DIR} + (1 - \hat{\gamma}_i)x_i^T\hat{\beta}$$
where the shrinkage factor $\hat{\gamma}_i$ is defined as:
$$\hat{\gamma}_i = \frac{\hat{\sigma}^2_v}{\hat{\sigma}^2_v + \psi_i}$$

### Robust EBLUP (REBLUP)
To protect against area-level outliers, the module implements the Sinha-Rao estimator. It uses a Huber $\psi_c$ function to limit the influence of standardized residuals:
$$\hat{\theta}_i^{REBLUP} = x_i^T\hat{\beta} + \hat{\gamma}_i \sqrt{V_i} \psi_c\left(\frac{\hat{\theta}_i^{DIR} - x_i^T\hat{\beta}}{\sqrt{V_i}}\right)$$
where $V_i = \sigma^2_v + \psi_i$. The model variance $\sigma^2_v$ is solved using robustified REML equations.

### Parametric Bootstrap MSE
The module estimates MSE by simulating $B$ bootstrap populations from the fitted model, calculating "true" values $\theta_i^{(b)}$ and "bootstrap" estimates $\hat{\theta}_i^{(b)}$, and computing the average squared error:
$$MSE_{boot} = \frac{1}{B} \sum_{b=1}^B (\hat{\theta}_i^{(b)} - \theta_i^{(b)})^2$$

---

## 5. References

Rao, J. N. K., & Molina, I. (2015). *Small Area Estimation*. Second Edition. John Wiley & Sons.

Sinha, S. K., & Rao, J. N. K. (2009). Robust small area estimation. *Canadian Journal of Statistics*, 37(3), 381-399.

Prasad, N. G. N., & Rao, J. N. K. (1990). The estimation of the mean squared error of small-area estimators. *Journal of the American Statistical Association*, 85(409), 163-171.

---

## 6. Runnable Examples

### Example 1: Standard EBLUP (Fay-Herriot)
```python
import polars as pl
from sae.eblup.engine import SAEEngine
from sae.eblup.models import SAEMetadata, SAEConfig

df = pl.DataFrame({
    "area_id": ["A1", "A2", "A3", "A4", "A5"],
    "direct_est": [100.0, 150.0, 120.0, 90.0, 200.0],
    "direct_var": [20.0, 50.0, 10.0, 80.0, 15.0],
    "x1": [1.2, 1.5, 1.1, 0.9, 1.8]
})

meta = SAEMetadata(
    area_id_var="area_id",
    direct_est_var="direct_est",
    direct_var_var="direct_var",
    aux_vars=["x1"],
    config=SAEConfig(method="REML")
)

engine = SAEEngine(meta)
result = engine.process(df)

print(f"Model Variance (sigma2_v): {result.diagnostics.model_variance:.4f}")
print(result.data.select(["area_id", "eblup_est", "eblup_mse", "gamma"]))
```

### Example 2: Robust EBLUP (REBLUP) for Outlier Protection
```python
import polars as pl
from sae.eblup.engine import SAEEngine
from sae.eblup.models import SAEMetadata, SAEConfig

# Area A5 is an outlier (high estimate, but predictor suggests lower)
df = pl.DataFrame({
    "area_id": ["A1", "A2", "A3", "A4", "A5"],
    "direct_est": [100, 110, 105, 95, 500], # A5 is Outlier
    "direct_var": [10.0] * 5,
    "x1": [1.0, 1.1, 1.05, 0.95, 1.0]
})

meta = SAEMetadata(
    area_id_var="area_id",
    direct_est_var="direct_est",
    direct_var_var="direct_var",
    aux_vars=["x1"],
    config=SAEConfig(robust=True, huber_c=1.345)
)

engine = SAEEngine(meta)
result = engine.process(df)

print(f"Outliers Capped: {result.diagnostics.custom_metrics['outliers_capped']}")
print(result.data.select(["area_id", "eblup_est", "robust_outlier_flag"]))
```

### Example 3: Master Orchestrator with Multi-Model Run
```python
import polars as pl
from sae.orchestrator import SAEOrchestrator

df = pl.DataFrame({
    "area_id": ["A", "B", "C"],
    "direct_est": [10, 20, 15],
    "direct_var": [2, 5, 3],
    "x1": [1, 2, 1.5]
})

orch = SAEOrchestrator(
    df_direct=df,
    area_id_var="area_id",
    target_var="direct_est",
    variance_var="direct_var",
    aux_vars=["x1"]
)

configs = {
    "eblup": {"config": {"method": "REML"}}
}

results = orch.run_all_and_validate(configs)
eblup_res = results["eblup"]["result"]

print(f"EBLUP Validation (Bias Slope): {eblup_res.validation.bias_slope:.3f}")
```

### Example 4: Parametric Bootstrap MSE Estimation
```python
import polars as pl
from sae.orchestrator import SAEOrchestrator
from sae.eblup.engine import SAEEngine
from sae.eblup.models import SAEMetadata

df = pl.DataFrame({
    "area_id": ["A1", "A2", "A3"],
    "direct_est": [10.0, 12.0, 11.0],
    "direct_var": [1.0, 1.0, 1.0],
    "x1": [1.0, 1.1, 1.0]
})

orch = SAEOrchestrator(df, "area_id", "direct_est", "direct_var", ["x1"])
meta = SAEMetadata(area_id_var="area_id", direct_est_var="direct_est", direct_var_var="direct_var", aux_vars=["x1"])

# We need a processed result first
engine = SAEEngine(meta)
result = engine.process(df)
orch.eblup_meta = meta # Inject meta for bootstrap

# Run bootstrap with small iterations for example
result_boot = orch.run_bootstrap_mse(result, b_iterations=10)

print(result_boot.data.select(["area_id", "eblup_est", "robust_bootstrap_mse"]))
```

### Example 5: Hierarchical Bayes (HB) for Small Area Estimation
This snippet demonstrates the Bayesian approach to SAE, which is useful when normality assumptions are questionable or for complex area-level models.

```python
import polars as pl
from sae.hb.engine import HBEngine
from sae.hb.models import HBMetadata, HBConfig

df = pl.DataFrame({
    "area_id": ["A1", "A2", "A3"],
    "direct_est": [10.5, 14.2, 11.8],
    "direct_var": [0.8, 1.2, 0.9],
    "x1": [1.0, 1.3, 1.1]
})

meta = HBMetadata(
    area_id_var="area_id",
    target_var="direct_est",
    variance_var="direct_var",
    auxiliary_vars=["x1"],
    config=HBConfig(model_type="HB_MM_KV", n_iter=2000, n_burn=500)
)

engine = HBEngine(meta)
result = engine.process(df)

print(f"HB Mean Estimate: {result.data.select(['area_id', 'hb_est'])}")
print(f"HB Posterior Variance: {result.data.select(['area_id', 'hb_mse'])}")
```
