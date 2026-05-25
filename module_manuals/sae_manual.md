# Module Documentation: Small Area Estimation (sae)

## 1. Module Overview
The `sae` (Small Area Estimation) module is a sophisticated statistical package designed to produce reliable estimates for geographic or demographic domains with small sample sizes. By "borrowing strength" from auxiliary data (e.g., administrative records) through a linking model, it mitigates the high variance associated with direct survey estimators. The module implements the classical **Fay-Herriot (EBLUP)** model, **Robust REBLUP (Sinha-Rao)** for outlier protection, and **Hierarchical Bayes (HB)**, all integrated into a unified orchestration pipeline with automated validation, variance smoothing, and hierarchical benchmarking.

## 2. Table of Contents
- [3. Master Orchestration](#3-master-orchestration)
  - [SAEOrchestrator](#saeorchestrator)
  - [run_all_and_validate](#run_all_and_validate)
  - [get_best_model](#get_best_model)
  - [certify_quality](#certify_quality)
- [4. SAE Engines](#4-sae-engines)
  - [SAEEngine (EBLUP)](#saeengine-eblup)
  - [_process_robust (REBLUP)](#_process_robust-reblup)
  - [HBEngine (Hierarchical Bayes)](#hbengine-hierarchical-bayes)
  - [MERFEngine](#merfengine)
- [5. Variance & Error Estimation](#5-variance--error-estimation)
  - [calculate_mse (Bootstrap)](#calculate_mse-bootstrap)
  - [orchestrate_variance_smoothing](#orchestrate_variance_smoothing)
- [6. Benchmarking & Reconciliation](#6-benchmarking--reconciliation)
  - [SAEHierarchicalBenchmarker](#saehierarchicalbenchmarker)
  - [reconcile](#reconcile)
- [7. Analytics](#7-analytics)
  - [calculate_sae_efficiency](#calculate_sae_efficiency)

---

## 3. Master Orchestration

### SAEOrchestrator

#### Description
The primary entry point for multi-model SAE execution and validation.

#### Usage
`SAEOrchestrator(df_direct, area_id_var, target_var, variance_var, aux_vars, n_var=None, db_path=None)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df_direct` | `pl.DataFrame` | REQUIRED | DataFrame containing area-level direct estimates. |
| `area_id_var` | `str` | REQUIRED | Unique identifier for small areas. |
| `target_var` | `str` | REQUIRED | Direct point estimates. |
| `variance_var` | `str` | REQUIRED | Direct variance estimates. |
| `aux_vars` | `list` | REQUIRED | List of auxiliary predictors. |

#### Details
Initializes the master pipeline environment for model comparisons.

#### Value
Initialized `SAEOrchestrator`.

#### References
N/A

#### Examples
```python
# See run_all_and_validate() example below.
```

---

### run_all_and_validate

#### Description
Master pipeline that executes configured models (EBLUP, HB, MERF) and returns a validation report for each.

#### Usage
`orch.run_all_and_validate(configs)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `configs` | `dict` | REQUIRED | Dictionary defining which models to run and their parameters. |

#### Details
Executes all requested models sequentially, running goodness-of-fit and bias diagnostics on each.

#### Value
A dictionary of results keyed by model type, including bias diagnostics and shrinkage metrics.

#### References
N/A

#### Examples
```python
# Example 3: Master Orchestrator with Multi-Model Run
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

---

### get_best_model

#### Description
Compares the output of multiple executed models and automatically selects the one with the best validation metrics and highest efficiency.

#### Usage
`orch.get_best_model(results)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `results` | `dict` | REQUIRED | The output dictionary from `run_all_and_validate()`. |

#### Details
Evaluates bias, MSE reduction, and model diagnostics to choose the optimal estimator.

#### Value
`SAEResult` corresponding to the best model.

#### References
N/A

#### Examples
```python
# best_result = orch.get_best_model(results)
```

---

### certify_quality

#### Description
Assigns a formal A-F quality grade based on the reduction in MSE, model fit diagnostics, and potential bias introduced by the model.

#### Usage
`orch.certify_quality(result)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `result` | `SAEResult` | REQUIRED | The output of a specific model execution. |

#### Details
Creates an objective quality tier for the estimates.

#### Value
Quality grade string.

#### References
N/A

#### Examples
```python
# grade = orch.certify_quality(eblup_res)
```

---

## 4. SAE Engines

### SAEEngine (EBLUP)

#### Description
Implements the Fay-Herriot model and REML solver.

#### Usage
`SAEEngine(metadata)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `metadata` | `SAEMetadata` | REQUIRED | Contains variable mappings and an `SAEConfig` for model parameters. |

#### Details
**Fay-Herriot Model (EBLUP)**
The area-level model assumes:
1.  **Sampling Model**: $\hat{\theta}_i^{DIR} = \theta_i + e_i, \quad e_i \sim N(0, \psi_i)$
2.  **Linking Model**: $\theta_i = X_i\beta + v_i, \quad v_i \sim N(0, \sigma^2_v)$

The EBLUP is the weighted average of the direct estimate and the synthetic regression estimate:
$$\hat{\theta}_i^{EBLUP} = \hat{\gamma}_i \hat{\theta}_i^{DIR} + (1 - \hat{\gamma}_i)x_i^T\hat{\beta}$$
where the shrinkage factor $\hat{\gamma}_i$ is defined as:
$$\hat{\gamma}_i = \frac{\hat{\sigma}^2_v}{\hat{\sigma}^2_v + \psi_i}$$

#### Value
`SAEResult` containing the EBLUP estimates, MSE, and model variance ($\sigma^2_v$).

#### References
- Rao, J. N. K., & Molina, I. (2015). *Small Area Estimation*. Second Edition. John Wiley & Sons.

#### Examples
```python
# Example 1: Standard EBLUP (Fay-Herriot)
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

---

### _process_robust (REBLUP)

#### Description
Executes the Robust Fay-Herriot (REBLUP) logic using Sinha-Rao Huber-penalized estimating equations.

#### Usage
`engine._process_robust(df)` (Internal, called automatically via config)

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | DataFrame containing area-level direct estimates. |

#### Details
**Robust EBLUP (REBLUP)**
To protect against area-level outliers, the module implements the Sinha-Rao estimator. It uses a Huber $\psi_c$ function to limit the influence of standardized residuals:
$$\hat{\theta}_i^{REBLUP} = x_i^T\hat{\beta} + \hat{\gamma}_i \sqrt{V_i} \psi_c\left(\frac{\hat{\theta}_i^{DIR} - x_i^T\hat{\beta}}{\sqrt{V_i}}\right)$$
where $V_i = \sigma^2_v + \psi_i$. The model variance $\sigma^2_v$ is solved using robustified REML equations.

#### Value
`SAEResult` with outlier-robust estimates and an `outlier_flag` column.

#### References
- Sinha, S. K., & Rao, J. N. K. (2009). Robust small area estimation. *Canadian Journal of Statistics*, 37(3), 381-399.

#### Examples
```python
# Example 2: Robust EBLUP (REBLUP) for Outlier Protection
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

---

### HBEngine (Hierarchical Bayes)

#### Description
Executes Bayesian Small Area Estimation models (e.g., via MCMC).

#### Usage
`HBEngine(metadata)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `metadata` | `HBMetadata` | REQUIRED | Contains variable mappings and an `HBConfig` for model parameters. |

#### Details
This approach is useful when normality assumptions are questionable or for complex area-level models.

#### Value
`SAEResult` containing Bayesian estimates and posterior variance.

#### References
N/A

#### Examples
```python
# Example 5: Hierarchical Bayes (HB) for Small Area Estimation
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

---

### MERFEngine

#### Description
Machine learning engine that captures complex, non-linear relationships in auxiliary data while incorporating random area effects.

#### Usage
`MERFEngine(target_col, area_id_col, fixed_effect_cols)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `target_col` | `str` | REQUIRED | Target column. |
| `area_id_col` | `str` | REQUIRED | Area ID column. |
| `fixed_effect_cols` | `list` | REQUIRED | Auxiliary predictors. |

#### Details
Trains a Random Forest while extracting empirical Best Linear Unbiased Predictors (EBLUPs) for the area-level random effects.

#### Value
`SAEResult` with machine-learning-assisted small area estimates.

#### References
N/A

#### Examples
```python
# Example 7: MERF Engine (Machine Learning SAE)
import polars as pl
from sae.ai.engine import MERFEngine

df = pl.DataFrame({
    "area_id": ["A1", "A1", "A2", "A2", "A3"],
    "target": [10.5, 11.0, 15.0, 14.5, 12.0],
    "x1": [1.0, 1.1, 2.0, 2.1, 1.5],
    "x2": [5.0, 5.2, 10.0, 9.8, 7.5]
})

engine = MERFEngine(target_col="target", area_id_col="area_id", fixed_effect_cols=["x1", "x2"])
result = engine.process(df)

print(result.data.select(["area_id", "merf_est", "merf_mse"]))
```

---

## 5. Variance & Error Estimation

### calculate_mse (Bootstrap)

#### Description
Calculates parametric bootstrap MSE for EBLUP estimates.

#### Usage
`SAEBootstrapMSE.calculate_mse(df, target_col, var_col, aux_vars)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | Input frame. |
| `target_col` | `str` | REQUIRED | Target variable. |
| `var_col` | `str` | REQUIRED | Variance variable. |
| `aux_vars` | `list` | REQUIRED | Predictors. |

#### Details
**Parametric Bootstrap MSE**
The module estimates MSE by simulating $B$ bootstrap populations from the fitted model, calculating "true" values $\theta_i^{(b)}$ and "bootstrap" estimates $\hat{\theta}_i^{(b)}$, and computing the average squared error:
$$MSE_{boot} = \frac{1}{B} \sum_{b=1}^B (\hat{\theta}_i^{(b)} - \theta_i^{(b)})^2$$

#### Value
DataFrame updated with a `robust_bootstrap_mse` column.

#### References
- Prasad, N. G. N., & Rao, J. N. K. (1990). The estimation of the mean squared error of small-area estimators. *Journal of the American Statistical Association*, 85(409), 163-171.

#### Examples
```python
# Example 4: Parametric Bootstrap MSE Estimation
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

---

### orchestrate_variance_smoothing

#### Description
Automatically selects and applies the best variance smoothing technique to stabilize noisy direct variances before SAE modeling.

#### Usage
`orchestrate_variance_smoothing(df, target_col, variance_col, n_col)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | Input frame. |
| `target_col` | `str` | REQUIRED | Direct estimate. |
| `variance_col` | `str` | REQUIRED | Direct variance. |
| `n_col` | `str` | REQUIRED | Sample size per area. |

#### Details
Classes include:
- **`ClassicalVarianceSmoother`**: Fits standard models ($log(V) = a + b \log(Y)$).
- **`MLVarianceSmoother`**: Uses non-parametric ML (XGBoost) for smoothing.

#### Value
Tuple of (smoothed DataFrame, diagnostics dictionary).

#### References
N/A

#### Examples
```python
# See Example 6 below.
```

---

## 6. Benchmarking & Reconciliation

### SAEHierarchicalBenchmarker

#### Description
Implements top-down hierarchical reconciliation (e.g., forcing state-level estimates to sum to a known national total).

#### Usage
`SAEHierarchicalBenchmarker(target_col, mse_col, method="mse_weighted")`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `target_col` | `str` | REQUIRED | The target variable. |
| `mse_col` | `str` | REQUIRED | The MSE column. |
| `method` | `str` | `"mse_weighted"` | Benchmarking method (`proportional`, `mse_weighted`, `mint`). |

#### Details
Initializes the benchmarker.

#### Value
Initialized `SAEHierarchicalBenchmarker`.

#### References
N/A

#### Examples
```python
# See Example 6 below.
```

---

### reconcile

#### Description
Adjusts bottom-level estimates to match top-level totals.

#### Usage
`benchmarker.reconcile(df_top, df_bot, parent_keys, child_key)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df_top` | `pl.DataFrame` | REQUIRED | Upper level frame. |
| `df_bot` | `pl.DataFrame` | REQUIRED | Lower level frame. |
| `parent_keys` | `list` | REQUIRED | Joining columns defining the hierarchy. |
| `child_key` | `str` | REQUIRED | Unique area ID for the child level. |

#### Details
Supports `proportional`, `mse_weighted`, and `mint` adjustment strategies.

#### Value
DataFrame with reconciled bottom-level estimates.

#### References
N/A

#### Examples
```python
# Example 6: Variance Smoothing and Hierarchical Benchmarking
import polars as pl
from sae.gvf import orchestrate_variance_smoothing
from sae.benchmarker import SAEHierarchicalBenchmarker

# 1. Smooth noisy direct variances
df_areas = pl.DataFrame({
    "area": ["A1", "A2", "A3", "A4", "A5"],
    "parent": ["Nat", "Nat", "Nat", "Nat", "Nat"],
    "est": [10.0, 15.0, 12.0, 8.0, 20.0],
    "var": [5.0, 15.0, 0.5, 20.0, 1.0], # Highly volatile direct variances
    "n": [5, 2, 15, 1, 20] # Sample sizes
})

df_smoothed, diag = orchestrate_variance_smoothing(df_areas, target_col="est", variance_col="var", n_col="n")
print(f"Used smoother: {diag['selected_method']}")

# 2. Benchmark area estimates to a known parent total
df_top = pl.DataFrame({"parent": ["Nat"], "est": [70.0]}) # Areas sum to 65.0, need to bump up to 70.0
benchmarker = SAEHierarchicalBenchmarker(target_col="est", method="proportional")

df_reconciled = benchmarker.reconcile(df_top, df_smoothed, parent_keys=["parent"], child_key="area")
print(df_reconciled.select(["area", "est", "est_benchmarked"]))
```

---

## 7. Analytics

### calculate_sae_efficiency

#### Description
Evaluates the reduction in variance achieved by the SAE model compared to the direct estimates.

#### Usage
`calculate_sae_efficiency(df_output)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df_output` | `pl.DataFrame` | REQUIRED | Resulting DataFrame containing both direct variances and modeled MSEs. |

#### Details
Summarizes metrics like average CV reduction.

#### Value
Dictionary of efficiency metrics.

#### References
N/A

#### Examples
```python
# metrics = calculate_sae_efficiency(result.data)
```
