# Module Documentation: Nonresponse Weighting

## 1. Module Overview
The `nonresponse_weighting` package provides a robust framework for adjusting survey weights to mitigate nonresponse bias. It leverages machine learning (XGBoost) to model response propensities and offers two industry-standard adjustment methodologies: **Response Homogeneity Groups (RHG)** and **Inverse Probability Weighting (IPW)**. The module is designed for production use in official statistics, featuring automated group collapsing, weight capping, mass redistribution, and A-F quality certification based on weight stability and model performance.

## 2. Table of Contents
- [3. Core Orchestration](#3-core-orchestration)
  - [NonresponseWeightingEngine](#nonresponseweightingengine)
  - [run](#run)
- [4. Propensity Modeling](#4-propensity-modeling)
  - [ResponsePropensityModel](#responsepropensitymodel)
  - [train_and_diagnose](#train_and_diagnose)
- [5. Weight Adjustment](#5-weight-adjustment)
  - [WeightAdjustmentEngine](#weightadjustmentengine)
  - [process](#process)
- [6. Quality Assurance & Analytics](#6-quality-assurance--analytics)
  - [certify](#certify)
  - [generate_nonresponse_diagnostic_data](#generate_nonresponse_diagnostic_data)
  - [generate_nonresponse_scatter_data](#generate_nonresponse_scatter_data)
  - [calculate_weighting_impact](#calculate_weighting_impact)
- [7. Persistence](#7-persistence)
  - [AuditDatabase](#auditdatabase)

---

## 3. Core Orchestration

### NonresponseWeightingEngine

#### Description
The high-level orchestrator that coordinates the full weighting pipeline.

#### Usage
`NonresponseWeightingEngine(config)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `config` | `NRWeightingConfig` | REQUIRED | Global configuration for method selection (`rhg` or `ipw`), persistence, and quality thresholds. |

#### Details
Initializes the sub-engines (`ResponsePropensityModel` and `WeightAdjustmentEngine`) and prepares the processing context.

#### Value
Initialized `NonresponseWeightingEngine`.

#### References
N/A

#### Examples
```python
# See run() examples below.
```

---

### run (NonresponseWeightingEngine)

#### Description
The primary execution method for the weighting pipeline.

#### Usage
`engine.run(df)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | The input sampling frame with respondents and non-respondents. |

#### Details
Executes the full pipeline: predicting response propensities and adjusting weights. 

**Inverse Probability Weighting (IPW)**
If the IPW method is selected, adjusted weights are calculated directly as the product of the design weight and the inverse of the predicted response propensity $\hat{p}_k$:
$$w_{adj, k} = d_k \cdot \frac{1}{\hat{p}_k}$$
A safety floor $\hat{p}_{min}$ is applied to prevent extreme weights: $\hat{p}_k^* = \max(\hat{p}_k, \hat{p}_{min})$.

#### Value
`NRWeightingResult` containing the adjusted DataFrame (respondents only), propensity diagnostics, and an automated quality grade.

#### References
- Little, R. J. A., & Rubin, D. B. (2002). *Statistical Analysis with Missing Data*. Wiley.

#### Examples
```python
# Example 3: Full Pipeline Execution (RHG Method)
import polars as pl
from nonresponse_weighting.engine import NonresponseWeightingEngine
from nonresponse_weighting.models import NRWeightingConfig

df = pl.DataFrame({
    "is_respondent": [1, 1, 1, 0, 0, 1, 0, 1, 1, 1],
    "x1": [10, 20, 15, 5, 2, 18, 4, 22, 14, 19],
    "design_weight": [1.0] * 10
})

config = NRWeightingConfig(
    method="rhg",
    feature_cols=["x1"],
    target_col="is_respondent",
    n_groups=2,
    persist_results=False
)

engine = NonresponseWeightingEngine(config)
result = engine.run(df)

print(f"Quality Grade: {result.quality.grade}")
print(f"Initial Mass: {result.total_initial_weight}")
print(f"Final Mass: {result.total_adjusted_weight}")
```

```python
# Example 4: Full Pipeline Execution (IPW Method)
import polars as pl
from nonresponse_weighting.engine import NonresponseWeightingEngine
from nonresponse_weighting.models import NRWeightingConfig

df = pl.DataFrame({
    "is_respondent": [1, 1, 1, 0, 1],
    "x1": [1.2, 1.5, 0.8, 0.5, 1.3],
    "design_weight": [100.0] * 5
})

config = NRWeightingConfig(
    method="ipw",
    feature_cols=["x1"],
    min_propensity_score=0.1,
    persist_results=False
)

engine = NonresponseWeightingEngine(config)
result = engine.run(df)

print(f"Method: {result.metadata['method']}")
print(result.data.select(["x1", "p_hat", "adjusted_weight"]))
```

---

## 4. Propensity Modeling

### ResponsePropensityModel

#### Description
Trains a gradient-boosted decision tree to predict unit-level response probabilities.

#### Usage
`ResponsePropensityModel(config)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `config` | `NRWeightingConfig` | REQUIRED | Defines features, hyperparameters (`learning_rate`, `max_depth`), and random seed. |

#### Details
Initializes the XGBoost classifier.

#### Value
Initialized `ResponsePropensityModel`.

#### References
- Chen, T., & Guestrin, C. (2016). XGBoost: A Scalable Tree Boosting System. *Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining*.

#### Examples
```python
# See train_and_diagnose() example below.
```

---

### train_and_diagnose

#### Description
Trains the XGBoost classifier and computes model performance metrics.

#### Usage
`model.train_and_diagnose(df)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | The input sampling frame. |

#### Details
**Propensity Modeling**
The module models the probability of response $R_k$ for unit $k$ given auxiliary features $X_k$ using a logistic objective:
$$P(R_k=1 | X_k) = \frac{1}{1 + \exp(-F(X_k))}$$
where $F(X_k)$ is the ensemble output of the XGBoost model.

#### Value
A tuple of (DataFrame with `p_hat`, `PropensityDiagnostics`, List of warnings).

#### References
N/A

#### Examples
```python
# Example 1: Propensity Model Training and Diagnostics
import polars as pl
import numpy as np
from nonresponse_weighting.engine import ResponsePropensityModel
from nonresponse_weighting.models import NRWeightingConfig

# Create synthetic data with a response bias
df = pl.DataFrame({
    "is_respondent": [1, 0, 1, 1, 0, 1, 0, 1, 1, 0],
    "revenue": [100, 500, 120, 130, 450, 110, 600, 140, 150, 550],
    "size": [1, 5, 2, 2, 4, 1, 5, 2, 2, 4]
})

config = NRWeightingConfig(
    feature_cols=["revenue", "size"],
    target_col="is_respondent"
)

model = ResponsePropensityModel(config)
df_res, diag, warnings = model.train_and_diagnose(df)

print(f"AUC-ROC: {diag.auc_roc:.3f}")
print(f"Log Loss: {diag.log_loss:.3f}")
print(df_res.select(["is_respondent", "p_hat"]))
```

---

## 5. Weight Adjustment

### WeightAdjustmentEngine

#### Description
Implements the logic for grouping units, collapsing small strata, and calculating RHG adjustment factors.

#### Usage
`WeightAdjustmentEngine(config)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `config` | `NRWeightingConfig` | REQUIRED | Defines the number of groups, minimum respondent counts, and weight capping thresholds. |

#### Details
Sets up the adjustment logic framework.

#### Value
Initialized `WeightAdjustmentEngine`.

#### References
N/A

#### Examples
```python
# See process() example below.
```

---

### process (WeightAdjustmentEngine)

#### Description
Executes RHG bucketing, handles group collapsing, and calculates the final adjustment factors.

#### Usage
`engine.process(df_with_propensity)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df_with_propensity` | `pl.DataFrame` | REQUIRED | DataFrame containing `p_hat` column. |

#### Details
**Response Homogeneity Groups (RHG)**
Units are partitioned into $H$ groups based on their propensity scores. Within each group $h$, the adjustment factor $f_h$ is calculated as the ratio of the total design weight of the sample to the design weight of the respondents:
$$f_h = \frac{\sum_{k \in s_h} d_k}{\sum_{k \in r_h} d_k}$$
where $d_k$ is the design weight, $s_h$ is the set of all sampled units in group $h$, and $r_h$ is the set of respondents. If $f_h > \text{cap}$, it is truncated to the cap value, and the lost mass may be redistributed to preserve the population total.

#### Value
A tuple of (Respondent DataFrame with `adjusted_weight`, List of `NRWeightingDiagnostics`, metadata dictionary).

#### References
- Brick, J. M. (2013). Unit Nonresponse and Weighting Adjustments. *Handbook of Survey Methodology*.

#### Examples
```python
# Example 2: RHG Processing and Group Collapsing
import polars as pl
from nonresponse_weighting.engine import WeightAdjustmentEngine
from nonresponse_weighting.models import NRWeightingConfig

df = pl.DataFrame({
    "p_hat": [0.1, 0.15, 0.2, 0.8, 0.85, 0.9],
    "is_respondent": [0, 0, 1, 1, 1, 1],
    "design_weight": [10.0] * 6
})

# Require at least 2 respondents per group (will trigger collapse for small groups)
config = NRWeightingConfig(
    feature_cols=[], # Required field
    n_groups=3, 
    min_respondents_per_rhg=2,
    collapse_small_rhgs=True,
    design_weight_col="design_weight"
)

engine = WeightAdjustmentEngine(config)
df_final, diagnostics, meta = engine.process(df)

print(f"Number of RHGs after collapse: {len(diagnostics)}")
print(df_final.select(["RHG_ID", "adjusted_weight"]))
```

---

## 6. Quality Assurance & Analytics

### certify (NRQualityAssurance)

#### Description
Performs post-processing diagnostics on the weight distribution.

#### Usage
`qa.certify(result, df_input)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `result` | `NRWeightingResult` | REQUIRED | The result to certify. |
| `df_input` | `pl.DataFrame` | REQUIRED | The original input DataFrame. |

#### Details
Computes Variance Inflation Factor (VIF) and weight shift metrics to assign a quality grade.

#### Value
An updated `NRWeightingResult` with an A-F quality grade.

#### References
N/A

#### Examples
```python
# certified_result = qa.certify(result, df_input)
```

---

### calculate_weighting_impact

#### Description
Evaluates the macro-level impact of nonresponse weighting, calculating the shift in total mass and identifying extreme weight adjustments.

#### Usage
`calculate_weighting_impact(df_initial, df_final, design_weight_col, adjusted_weight_col="adjusted_weight", weight_cap=3.0)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df_initial` | `pl.DataFrame` | REQUIRED | Original frame. |
| `df_final` | `pl.DataFrame` | REQUIRED | Adjusted frame. |
| `design_weight_col` | `str` | REQUIRED | Original weight column. |
| `adjusted_weight_col` | `str` | `"adjusted_weight"` | New weight column. |
| `weight_cap` | `float` | `3.0` | Cap ratio. |

#### Details
Calculates variance inflation and the proportion of capped weights.

#### Value
Dictionary containing impact metrics.

#### References
N/A

#### Examples
```python
# Example 5: Nonresponse Analytics and Impact Evaluation
import polars as pl
from nonresponse_weighting.analytics import generate_nonresponse_scatter_data, calculate_weighting_impact
from nonresponse_weighting.engine import NonresponseWeightingEngine
from nonresponse_weighting.models import NRWeightingConfig

df = pl.DataFrame({
    "id": range(10),
    "is_respondent": [1, 1, 1, 0, 0, 1, 0, 1, 1, 1],
    "x1": [10, 20, 15, 5, 2, 18, 4, 22, 14, 19],
    "design_weight": [10.0] * 10
})

config = NRWeightingConfig(
    method="rhg", feature_cols=["x1"], target_col="is_respondent",
    n_groups=2, persist_results=False
)

engine = NonresponseWeightingEngine(config)
result = engine.run(df)
df_final = result.data

# Evaluate impact
impact = calculate_weighting_impact(
    df_initial=df, df_final=df_final, 
    design_weight_col="design_weight", adjusted_weight_col="adjusted_weight"
)
print(f"Variance Inflation Factor (VIF): {impact['variance_inflation']:.3f}")
print(f"Total Weight Shift: {impact['weight_shift_pct']:.2f}%")
```

---

### generate_nonresponse_diagnostic_data

#### Description
Calculates response rates and nonresponse diagnostics across different strata or groups.

#### Usage
`generate_nonresponse_diagnostic_data(df, target_col, strata_vars, max_groups=10)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | The sampling frame. |
| `target_col` | `str` | REQUIRED | The response indicator column. |
| `strata_vars` | `list` | REQUIRED | Stratification columns. |
| `max_groups` | `int` | `10` | Max groups to report. |

#### Details
Aggregates nonresponse counts and rates.

#### Value
Dictionary containing nonresponse counts and rates.

#### References
N/A

#### Examples
```python
# data = generate_nonresponse_diagnostic_data(df, "is_respondent", ["stratum"])
```

---

### generate_nonresponse_scatter_data

#### Description
Generates data points suitable for plotting the original design weight versus the adjusted weight to visualize the impact of the nonresponse adjustment.

#### Usage
`generate_nonresponse_scatter_data(df_orig, df_final, design_weight_col, adjusted_weight_col="adjusted_weight", id_col="id", max_points=1000)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df_orig` | `pl.DataFrame` | REQUIRED | Original frame. |
| `df_final` | `pl.DataFrame` | REQUIRED | Adjusted frame. |
| `design_weight_col` | `str` | REQUIRED | Original weight column. |
| `adjusted_weight_col` | `str` | `"adjusted_weight"` | New weight column. |
| `id_col` | `str` | `"id"` | Identifier column. |
| `max_points` | `int` | `1000` | Max points for performance. |

#### Details
Extracts aligned scatter coordinates.

#### Value
Dictionary with `scatter_points`.

#### References
N/A

#### Examples
```python
# scatter_data = generate_nonresponse_scatter_data(df, df_final, "design_weight")
# print(f"Generated {len(scatter_data['scatter_points'])} points for plotting.")
```

---

## 7. Persistence

### AuditDatabase

#### Description
Handles the persistence of operational flags and metrics to an SQLite database.

#### Usage
`AuditDatabase(db_path="nonresponse_weighting_audit.db")`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `db_path` | `str` | `"nonresponse_weighting_audit.db"` | Path to the SQLite DB. |

#### Details
Provides methods like `save_run` and `save_unit_weights`.

#### Value
Initialized `AuditDatabase`.

#### References
N/A

#### Examples
```python
# db = AuditDatabase()
# db.save_run(result, "run_123")
```
