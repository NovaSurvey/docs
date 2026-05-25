# Module Documentation: Influential Units

## 1. Module Overview
The `influential_units` package provides a production-grade framework for detecting and treating outliers in survey data. It implements robust estimation techniques designed to reduce the impact of influential units (observations that significantly shift the total estimate) on the precision of the results. The module supports two primary methodologies: **Beaumont-Rivest Winsorization** (optimal exponent detection) and **Huber-style Conditional Bias** (robust weights and pseudo-values). It is fully integrated with the survey estimation pipeline, supporting audit persistence, quality certification, and re-robusted bootstrap variance estimation.

## 2. Table of Contents
- [3. Core Orchestration](#3-core-orchestration)
  - [RobustEstimator](#robustestimator)
  - [process](#process)
- [4. Conditional Bias Methods](#4-conditional-bias-methods)
  - [apply_conditional_bias_treatment](#apply_conditional_bias_treatment)
- [5. Impact & Quality](#5-impact--quality)
  - [compute_impact](#compute_impact)
  - [certify](#certify)
- [6. Analytics & Visualization](#6-analytics--visualization)
  - [generate_influential_scatter_data](#generate_influential_scatter_data)
  - [calculate_influential_treatment_impact](#calculate_influential_treatment_impact)
- [7. Persistence](#7-persistence)
  - [AuditDatabase](#auditdatabase)

---

## 3. Core Orchestration

### RobustEstimator

#### Description
The main engine for influential unit detection and treatment.

#### Usage
`RobustEstimator(metadata)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `metadata` | `InfluentialMetadata` | REQUIRED | Configuration object defining target variables, group levels, and treatment parameters. |

#### Details
Initializes the context for robust estimation, setting up configuration for either Winsorization or Conditional Bias.

#### Value
Initialized `RobustEstimator`.

#### References
N/A

#### Examples
```python
# See process() examples below.
```

---

### process (RobustEstimator)

#### Description
The primary entry point for the robust estimation pipeline. Applies the configured outlier detection and treatment to the frame.

#### Usage
`estimator.process(df, run_id=None, save_audit=True)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | The input sampling frame with weights. |
| `run_id` | `str` | `None` | Optional execution ID for auditing. |
| `save_audit` | `bool` | `True` | Flag to persist run metrics to the audit database. |

#### Details
Applies either **Beaumont-Rivest Winsorization** or **Huber-style Conditional Bias** based on the `treatment_type` in the metadata.

**Beaumont-Rivest Winsorization**
This method detects influential units by calculating $z$-scores and identifying an optimal exponent $e \in (0, 1]$ that minimizes the Mean Squared Error (MSE).
- **Transformation**: $w_k = a_k^e$ for influential units.
- **Weight Redistribution**: To preserve the total population mass, weights of ordinary units are adjusted by a constant $c$:
  $$c = \frac{\sum a_{infl} + \sum a_{ord} - \sum a_{infl}^e}{\sum a_{ord}}$$
- **Optimization**: The engine uses a binary bisection solver to find the smallest $e$ such that the bias ratio $\frac{|Bias|}{SE} \leq \delta_{bias}$ and MSE improvement is maximized.

**Re-Robusted Bootstrap**
When bootstrap weights are provided, the module applies the treatment independently to each replicate to ensure variance estimates account for the variability in outlier detection.
- **Transformation**: $w_{b,k}^{robust} = 1 + (w_{b,k} - 1) \psi_c(CB_{b,k})$

#### Value
`InfluentialResult` containing the processed `data` (with `influential_weight`), diagnostics per group, and quality summaries.

#### References
- Beaumont, J.-F., & Rivest, L.-P. (2009). Dealing with outliers in survey data. In *Handbook of Statistics* (Vol. 29, pp. 247-279). Elsevier.
- Favre, A. C., Matei, A., & Rivest, L. P. (2004). Outlier detection and treatment in business surveys. *Proceedings of the Survey Methods Section, Statistical Society of Canada*.

#### Examples
```python
# Example 1: Standard Winsorization with MSE Optimization
import polars as pl
from influential_units.engine import RobustEstimator
from influential_units.models import InfluentialMetadata, DetectionConfig

df = pl.DataFrame({
    "id": range(10),
    "w": [10.0] * 10,
    "revenue": [100.0, 120.0, 110.0, 105.0, 115.0, 130.0, 125.0, 110.0, 5000.0, 115.0],
    "stratum": ["A"] * 10
})

meta = InfluentialMetadata(
    initial_weight_var="w",
    analysis_vars=["revenue"],
    group_vars=["stratum"],
    detection_config=DetectionConfig(method="AY", threshold_type="QUARTILE"),
    treatment_type="WINSORIZATION",
    delta_bias=0.05
)

estimator = RobustEstimator(meta)
result = estimator.process(df)

print(result.data.select(["id", "revenue", "influential_weight", "is_influential"]))
print(f"Optimal Exponent: {result.diagnostics[0].optimal_e}")
```

```python
# Example 2: Re-Robusted Bootstrap Integration
import polars as pl
from influential_units.engine import RobustEstimator
from influential_units.models import InfluentialMetadata

df = pl.DataFrame({
    "w": [10.0] * 5,
    "y": [100, 200, 150, 180, 5000],
    "boot_1": [12.0, 8.0, 10.0, 11.0, 11.0],
    "boot_2": [9.0, 11.0, 10.0, 9.5, 10.5]
})

meta = InfluentialMetadata(
    initial_weight_var="w",
    analysis_vars=["y"],
    group_vars=[],
    treatment_type="CONDITIONAL_BIAS",
    bootstrap_weight_prefix="boot_",
    n_bootstraps=2
)

estimator = RobustEstimator(meta)
result = estimator.process(df)

# Re-robusted weights are prefixed with 'robust_'
print(result.data.select(["y", "robust_boot_1", "robust_boot_2"]))
```

---

## 4. Conditional Bias Methods

### apply_conditional_bias_treatment

#### Description
Generates robust weights and pseudo-values based on Conditional Bias scores.

#### Usage
`estimator.apply_conditional_bias_treatment(df, base_weight_col)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | The input sampling frame. |
| `base_weight_col` | `str` | REQUIRED | The column containing design weights. |

#### Details
**Huber-style Conditional Bias**
A modern approach that generates robust weights by bounding the influence of each unit's contribution to the total.
- **Influence Score**: $CB_k = (w_k - 1) \frac{y_k - \text{median}(y)}{\text{MAD}(y)}$
- **Huber Factor**: $\psi_c(CB_k) = \begin{cases} 1 & |CB_k| \leq c \\ \frac{c}{|CB_k|} & |CB_k| > c \end{cases}$
- **Robust Weight**: $w_{k}^{robust} = 1 + (w_k - 1) \psi_c(CB_k)$
- **Pseudo-Values**: $\tilde{y}_k = y_k \frac{w_{k}^{robust}}{w_k}$ (used for analytical variance estimation).

#### Value
`polars.DataFrame` with `_robust_weight` and `_pseudo_value` columns for each analysis variable.

#### References
- Beaumont, J.-F., & Rivest, L.-P. (2009). Dealing with outliers in survey data. In *Handbook of Statistics* (Vol. 29, pp. 247-279). Elsevier.

#### Examples
```python
# Example 3: Conditional Bias Robust Estimation (Analytical)
import polars as pl
from influential_units.engine import RobustEstimator
from influential_units.models import InfluentialMetadata

df = pl.DataFrame({
    "w": [50.0] * 5,
    "income": [1000, 1200, 1100, 50000, 1150]
})

meta = InfluentialMetadata(
    initial_weight_var="w",
    analysis_vars=["income"],
    group_vars=[],
    treatment_type="CONDITIONAL_BIAS",
    tuning_constant=10.0
)

estimator = RobustEstimator(meta)
result = estimator.process(df)

# Note the presence of pseudo-values for variance estimation
print(result.data.select(["income", "influential_weight", "income_pseudo_value"]))
```

---

## 5. Impact & Quality

### compute_impact

#### Description
Calculates the aggregate reduction in total estimates caused by the treatment.

#### Usage
`estimator.compute_impact(result)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `result` | `InfluentialResult` | REQUIRED | The processed result from `process()`. |

#### Details
Aggregates the total using the original design weight versus the newly generated influential weight.

#### Value
`Dict[str, Dict[str, float]]` containing original vs. winsorized totals and percentage reductions per variable.

#### References
N/A

#### Examples
```python
# impact = estimator.compute_impact(result)
```

---

### certify (InfluentialQualityCertifier)

#### Description
Evaluates the statistical impact of the treatment and assigns a quality grade.

#### Usage
`certifier.certify(result)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `result` | `InfluentialResult` | REQUIRED | The result to certify. |

#### Details
Scores the magnitude of the intervention. Extreme interventions (e.g., massive reduction in total aggregate) result in lower quality grades.

#### Value
`InfluentialResult` with an updated `quality` object containing an A-F grade and certification status.

#### References
N/A

#### Examples
```python
# Example 4: Quality Certification & Impact Metrics
from influential_units.engine import RobustEstimator
from influential_units.models import InfluentialMetadata
import polars as pl

df = pl.DataFrame({"w": [10.0]*10, "val": [10, 12, 11, 1000, 9, 11, 12, 10, 11, 10]})
meta = InfluentialMetadata(
    initial_weight_var="w", 
    analysis_vars=["val"], 
    group_vars=[], 
    delta_bias=0.1
)

estimator = RobustEstimator(meta)
result = estimator.process(df)

print(f"Quality Grade: {result.quality.grade}")
print(f"Impact: {result.impact['val']['reduction_pct']:.2f}%")
```

---

## 6. Analytics & Visualization

### generate_influential_scatter_data

#### Description
Generates data points suitable for scatter plotting (Original vs Treated Weights) to visualize the impact of influential unit treatment.

#### Usage
`generate_influential_scatter_data(df_orig, df_treated, target_var, weight_orig_var, weight_treated_var, threshold=15.0, max_points=500, id_col="id")`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df_orig` | `pl.DataFrame` | REQUIRED | Original frame. |
| `df_treated` | `pl.DataFrame` | REQUIRED | Treated frame. |
| `target_var` | `str` | REQUIRED | Analysis variable. |
| `weight_orig_var` | `str` | REQUIRED | Original weight column. |
| `weight_treated_var` | `str` | REQUIRED | New treated weight column. |
| `threshold` | `float` | `15.0` | Z-score threshold for outlier highlighting. |
| `max_points` | `int` | `500` | Max points to sample for performance. |
| `id_col` | `str` | `"id"` | ID column. |

#### Details
Aligns treated data against original for plotting.

#### Value
Dictionary with `scatter_points`, `threshold`, and `outliers`.

#### References
N/A

#### Examples
```python
# See Example 5 below.
```

---

### calculate_influential_treatment_impact

#### Description
Evaluates the macro-level impact of influential unit treatment on totals and standard errors for specified target variables.

#### Usage
`calculate_influential_treatment_impact(df_orig, df_treated, target_vars, weight_orig_var, weight_treated_var)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df_orig` | `pl.DataFrame` | REQUIRED | Original frame. |
| `df_treated` | `pl.DataFrame` | REQUIRED | Treated frame. |
| `target_vars` | `list` | REQUIRED | List of analysis variables. |
| `weight_orig_var` | `str` | REQUIRED | Original weight column. |
| `weight_treated_var` | `str` | REQUIRED | New treated weight column. |

#### Details
Provides comparison metrics for global aggregates.

#### Value
Dictionary containing impact metrics per variable.

#### References
N/A

#### Examples
```python
# Example 5: Visualizing Influential Units Impact
import polars as pl
from influential_units.engine import RobustEstimator
from influential_units.models import InfluentialMetadata
from influential_units.analytics import generate_influential_scatter_data, calculate_influential_treatment_impact

df = pl.DataFrame({
    "id": range(10),
    "w": [10.0] * 10,
    "revenue": [100.0, 120.0, 110.0, 105.0, 115.0, 130.0, 125.0, 110.0, 5000.0, 115.0],
})

meta = InfluentialMetadata(
    initial_weight_var="w",
    analysis_vars=["revenue"],
    group_vars=[],
    treatment_type="WINSORIZATION"
)

estimator = RobustEstimator(meta)
result = estimator.process(df)

# Generate scatter plot data
scatter_data = generate_influential_scatter_data(
    df_orig=df, 
    df_treated=result.data, 
    target_var="revenue", 
    weight_orig_var="w", 
    weight_treated_var="influential_weight"
)
print(f"Number of outliers detected: {len(scatter_data['outliers'])}")

# Calculate macro impact
impact = calculate_influential_treatment_impact(
    df_orig=df, 
    df_treated=result.data, 
    target_vars=["revenue"], 
    weight_orig_var="w", 
    weight_treated_var="influential_weight"
)
print(f"Total Original: {impact['revenue']['total_orig']}")
print(f"Total Treated: {impact['revenue']['total_treated']}")
```

---

## 7. Persistence

### AuditDatabase

#### Description
Handles the persistence of operational flags and metrics to an SQLite database.

#### Usage
`AuditDatabase(db_path="influential_units_audit.db")`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `db_path` | `str` | `"influential_units_audit.db"` | Path to the SQLite DB. |

#### Details
Responsible for the `save_run` operation.

#### Value
Initialized `AuditDatabase`.

#### References
N/A

#### Examples
```python
# db = AuditDatabase()
# db.save_run(result, "run_123")
```
