# Module Documentation: Calibration

## 1. Module Overview
The `calibration` package implements a high-performance, bounded optimization framework for survey weight adjustment. Its primary objective is to align survey estimates with known population benchmarks (Census totals) while minimizing the distance between design weights and calibrated weights. The engine utilizes convex optimization (via CVXPY and CLARABEL) to enforce range constraints (e.g., preventing negative weights or extreme g-factors) and supports advanced features such as Take-All unit exclusions, AI-assisted pre-processing, and parallel bootstrap replicate calibration.

## 2. Table of Contents
- [3. High-Level Orchestration](#3-high-level-orchestration)
  - [SurveyCalibrator](#surveycalibrator)
  - [calibrate_main_weight](#calibrate_main_weight)
  - [calibrate_replicates](#calibrate_replicates)
- [4. Low-Level Optimization](#4-low-level-optimization)
  - [CalibrationEngine](#calibrationengine)
  - [calibrate](#calibrate)
- [5. Resampling Utilities](#5-resampling-utilities)
  - [generate_bootstrap_replicates](#generate_bootstrap_replicates)
  - [generate_rao_wu_bootstrap](#generate_rao_wu_bootstrap)
- [6. Quality Assurance & Analytics](#6-quality-assurance--analytics)
  - [calculate_calibration_impact](#calculate_calibration_impact)
  - [certify](#certify)
  - [generate_quality_declaration](#generate_quality_declaration)
- [7. Persistence](#7-persistence)
  - [AuditDatabase](#auditdatabase)

---

## 3. High-Level Orchestration

### SurveyCalibrator

#### Description
High-level API for production calibration pipelines.

#### Usage
`SurveyCalibrator(lower_bound_ratio=0.4, upper_bound_ratio=3.0, min_sample_size=5)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `lower_bound_ratio` | `float` | `0.4` | Minimum allowable g-factor ($w_k/a_k$). |
| `upper_bound_ratio` | `float` | `3.0` | Maximum allowable g-factor. |
| `min_sample_size` | `int` | `5` | Minimum required units in a stratum to attempt calibration. |

#### Details
Initializes the SurveyCalibrator context for managing multiple weighting passes.

#### Value
Initialized `SurveyCalibrator`.

#### References
N/A

#### Examples
```python
import polars as pl
from calibration.engine import SurveyCalibrator

calibrator = SurveyCalibrator()
```

---

### calibrate_main_weight (SurveyCalibrator)

#### Description
Orchestrates the calibration of the primary design weight against control totals.

#### Usage
`calibrator.calibrate_main_weight(df, base_weight_col, control_totals, exclusion_col=None)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | The input sampling frame. |
| `base_weight_col` | `str` | REQUIRED | The initial design weight column name. |
| `control_totals` | `dict` | REQUIRED | Dictionary mapping auxiliary variables to their target population totals. |
| `exclusion_col` | `str` | `None` | Identifies "Take-All" units whose weights are locked at 1.0. |

#### Details
Handles "Take-All" units whose weights are locked at 1.0 (or their design weight) and whose contributions are removed from the population targets before calibrating the remaining units.

#### Value
`pl.DataFrame` containing the calibrated main weights (`final_calibrated_weight`) and g-factors.

#### References
N/A

#### Examples
```python
# Example 1: Basic Linear Calibration (Main Weight)
import polars as pl
from calibration.engine import SurveyCalibrator

df = pl.DataFrame({
    "id": [1, 2, 3, 4, 5],
    "w": [10.0, 10.0, 10.0, 10.0, 10.0], # Total = 50
    "x1": [1, 0, 1, 0, 1], # Count = 3
    "x2": [0, 1, 0, 1, 0], # Count = 2
})
totals = {"x1": 40.0, "x2": 25.0} # Target Total = 65

calibrator = SurveyCalibrator()
res = calibrator.calibrate_main_weight(df, "w", totals)
print(res.select(["id", "w", "final_calibrated_weight", "g_factor"]))
```

---

### calibrate_replicates (SurveyCalibrator)

#### Description
Executes calibration for multiple bootstrap replicate weights in parallel using a thread pool.

#### Usage
`calibrator.calibrate_replicates(df, rep_cols, control_totals, exclusion_col=None, max_workers=8)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | The input sampling frame. |
| `rep_cols` | `list` | REQUIRED | List of replicate weight column names. |
| `control_totals` | `dict` | REQUIRED | Population totals. |
| `exclusion_col` | `str` | `None` | Optional exclusion column. |
| `max_workers` | `int` | `8` | Number of concurrent threads. |

#### Details
Ensures all variance estimates reflect the calibration constraints.

#### Value
`pl.DataFrame` containing the newly calibrated replicate weights (suffixed with `_cal`).

#### References
N/A

#### Examples
```python
# Example 5: Parallel Replicate Calibration
import polars as pl
from calibration.engine import SurveyCalibrator

df = pl.DataFrame({
    "w_rep1": [10.5, 9.8, 11.2, 10.1, 9.9],
    "w_rep2": [9.5, 11.0, 10.5, 10.2, 10.8],
    "x": [1, 0, 1, 1, 0]
})
totals = {"x": 35.0}

calibrator = SurveyCalibrator()
res = calibrator.calibrate_replicates(df, rep_cols=["w_rep1", "w_rep2"], control_totals=totals)
print(res.select(["w_rep1_cal", "w_rep2_cal"]))
```

---

## 4. Low-Level Optimization

### CalibrationEngine

#### Description
Low-level optimization engine implementing specific distance metrics.

#### Usage
`CalibrationEngine(metadata)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `metadata` | `CalibrationMetadata` | REQUIRED | Configuration defining the method, constraints, and calibration groups. |

#### Details
Available methods: `linear`, `raking`, `penalized`, `ai_model_calibrated`.

#### Value
Initialized `CalibrationEngine`.

#### References
N/A

#### Examples
```python
# See calibrate() examples below.
```

---

### calibrate (CalibrationEngine)

#### Description
Executes the optimization solver for the defined calibration groups.

#### Usage
`engine.calibrate(df, population_frame=None)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | The input sampling frame. |
| `population_frame` | `pl.DataFrame` | `None` | Optional frame for AI pre-processing. |

#### Details
**Linear Bounded Calibration (Chi-Square)**
The default method minimizes the Chi-Square distance between calibrated weights $w_k$ and initial weights $a_k$:
$$\min \sum_{k \in S} \frac{(w_k - a_k)^2}{a_k}$$
Subject to:
1. **Benchmark Constraints**: $\sum_{k \in S} w_k x_{kj} = T_j \quad \forall j$
2. **Range Constraints**: $L \le \frac{w_k}{a_k} \le U$

**Raking Ratio Calibration**
Uses the Kullback-Leibler (KL) divergence as the distance metric, which is mathematically equivalent to the classical raking ratio procedure but with added support for range constraints:
$$\min \sum_{k \in S} \left( w_k \log \frac{w_k}{a_k} - w_k + a_k \right)$$

**Penalized (Ridge) Calibration**
When exact benchmark matching is not possible, the engine can apply a Ridge penalty to the objective function, allowing for controlled deviations from targets:
$$\min \text{Dist}(w, a) + \lambda \sum_{j} \left( \frac{\sum w_k x_{kj} - T_j}{T_j} \right)^2$$

**AI Model Assisted Calibration**
A two-phase hybrid approach designed to handle highly nonlinear relationships:
1. **Phase 1 (AI Preprocessor)**: Trains an XGBoost model to predict a target variable $y$ using auxiliary predictors $x$. It computes the population total of these predictions $\hat{T}_y = \sum_{k \in U} \hat{y}_k$.
2. **Phase 2 (Calibration)**: Calibrates weights using the model predictions as the primary auxiliary variable, effectively enforcing $\sum w_k \hat{y}_k = \hat{T}_y$.

#### Value
`CalibrationResult` object containing the data, status, and diagnostics.

#### References
1. Deville, J. C., & Särndal, C. E. (1992). *Calibration Estimators in Survey Sampling*. Journal of the American Statistical Association, 87(418), 376-382.
2. Beaumont, J.-F. (2008). *A new approach to weighting and convergence issues in sample surveys*. Survey Methodology, 34(1), 29-40.
3. Beaumont, J.-F., & Bocci, C. (2008). *Another look at ridge calibration*. Metron, 66(1), 5-20.
4. Bardsley, P., & Chambers, R. L. (1984). *Multipurpose estimation from unbalanced samples*. Journal of the Royal Statistical Society: Series C (Applied Statistics), 33(3), 290-299.
5. Wu, C., & Sitter, R. R. (2001). *A model-calibration approach to using complete auxiliary information from survey data*. Journal of the American Statistical Association, 96(453), 185-193.
6. Breidt, F. J., & Opsomer, J. D. (2017). *Model-Assisted Survey Estimation with Modern Prediction Techniques*. Statistical Science, 32(2), 190-205.

#### Examples
```python
# Example 2: Raking Calibration with Range Bounds
import polars as pl
from calibration.engine import CalibrationEngine
from calibration.models import CalibrationMetadata, CalibrationGroup, CalibrationConstraints, DatasetConfig

df = pl.DataFrame({"w": [5.0]*10, "age_cat": [1, 2]*5})
meta = CalibrationMetadata(
    method="raking",
    dataset_config=DatasetConfig(file_name="test", initial_weight_var="w"),
    calibration_groups=[CalibrationGroup(group_id="g1", auxiliary_vars=["age_cat"], population_totals=[40.0])],
    constraints=CalibrationConstraints(lower_bound_ratio=0.5, upper_bound_ratio=2.0)
)
engine = CalibrationEngine(meta)
res = engine.calibrate(df)
print(f"Success: {res.overall_success}, Mean G: {res.data['g_factor'].mean()}")
```

```python
# Example 3: Penalized Calibration (Soft Constraints)
from calibration.engine import CalibrationEngine
from calibration.models import CalibrationMetadata, CalibrationGroup, CalibrationConstraints, DatasetConfig
import polars as pl

df = pl.DataFrame({"w": [10.0]*5, "x": [1, 1, 1, 1, 1]})
meta = CalibrationMetadata(
    method="penalized",
    calibration_groups=[CalibrationGroup(group_id="p1", auxiliary_vars=["x"], population_totals=[100.0])],
    constraints=CalibrationConstraints(lambda_penalty=1000.0), # High penalty
    dataset_config=DatasetConfig(file_name="test", initial_weight_var="w")
)
engine = CalibrationEngine(meta)
res = engine.calibrate(df)
print(f"Target: 100.0, Result: {res.data['final_calibrated_weight'].sum()}")
```

```python
# Example 4: AI-Assisted Calibration (XGBoost + Calibration)
import polars as pl
import numpy as np
from calibration.engine import CalibrationEngine
from calibration.models import CalibrationMetadata, CalibrationGroup, DatasetConfig

# Sample and Population Frame
df = pl.DataFrame({"w": [1.0]*20, "income": np.random.rand(20)*100, "age": np.random.rand(20)*80})
frame = pl.DataFrame({"income": np.random.rand(100)*100, "age": np.random.rand(100)*80})

meta = CalibrationMetadata(
    method="ai_model_calibrated",
    dataset_config=DatasetConfig(file_name="ai_test", initial_weight_var="w"),
    calibration_groups=[CalibrationGroup(group_id="ai1", auxiliary_vars=["age"], ai_target_var="income", population_total=0.0)],
    constraints=CalibrationConstraints(),
    ai_model_params={"n_estimators": 50}
)
engine = CalibrationEngine(meta)
res = engine.calibrate(df, population_frame=frame)
print(f"AI Calibrated Total: {res.data['final_calibrated_weight'].sum()}")
```

---

## 5. Resampling Utilities

### generate_bootstrap_replicates

#### Description
Generates simple random sample (SRS) bootstrap replicates for variance estimation.

#### Usage
`generate_bootstrap_replicates(df, base_weight_col, n_reps=500, seed=None)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | The input sampling frame. |
| `base_weight_col` | `str` | REQUIRED | Base weight column. |
| `n_reps` | `int` | `500` | Number of replicates to generate. |
| `seed` | `int` | `None` | Optional random seed. |

#### Details
Adjusts base weights for samples drawn with replacement.

#### Value
`polars.DataFrame` appended with `n_reps` new replicate weight columns.

#### References
N/A

#### Examples
```python
# df_reps = generate_bootstrap_replicates(df, "design_weight", n_reps=50)
```

---

### generate_rao_wu_bootstrap

#### Description
Generates complex survey bootstrap replicates using the Rao-Wu rescaling method.

#### Usage
`generate_rao_wu_bootstrap(df, base_weight_col, stratum_col, n_reps=500, seed=None)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | The input sampling frame. |
| `base_weight_col` | `str` | REQUIRED | Base weight column. |
| `stratum_col` | `str` | REQUIRED | Stratum identifier column. |
| `n_reps` | `int` | `500` | Number of replicates. |
| `seed` | `int` | `None` | Optional random seed. |

#### Details
Preserves the original sampling design variance properties by sampling $n_h - 1$ units per stratum.

#### Value
`polars.DataFrame` appended with `n_reps` new replicate weight columns.

#### References
N/A

#### Examples
```python
# Example 6: Generating Rao-Wu Bootstrap Replicates
import polars as pl
from calibration.utils import generate_rao_wu_bootstrap

df = pl.DataFrame({
    "id": range(10),
    "stratum": ["A"]*5 + ["B"]*5,
    "design_weight": [10.0] * 10
})

# Generate 50 replicate weights for variance estimation
df_reps = generate_rao_wu_bootstrap(df, base_weight_col="design_weight", stratum_col="stratum", n_reps=50)
print(df_reps.select(["id", "design_weight", "rep_1", "rep_2", "rep_3"]).head())
```

---

## 6. Quality Assurance & Analytics

### calculate_calibration_impact

#### Description
Evaluates the macro-level impact of calibration, computing variance inflation, maximum g-factors, and checking for bounds violations across the overall dataset and within specified calibration groups.

#### Usage
`calculate_calibration_impact(df_initial, df_final, initial_weight_col, final_weight_col, calibration_groups)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df_initial` | `pl.DataFrame` | REQUIRED | Initial frame. |
| `df_final` | `pl.DataFrame` | REQUIRED | Calibrated frame. |
| `initial_weight_col` | `str` | REQUIRED | Initial weight column. |
| `final_weight_col` | `str` | REQUIRED | Calibrated weight column. |
| `calibration_groups` | `list` | REQUIRED | List of group variables. |

#### Details
Calculates variance inflation factor (Deff) and identifies weight range issues.

#### Value
Dictionary containing detailed impact metrics.

#### References
N/A

#### Examples
```python
# Example 7: Analytics and Quality Certification
import polars as pl
from calibration.engine import SurveyCalibrator
from calibration.analytics import calculate_calibration_impact
from calibration.quality import QualityAssurance

df = pl.DataFrame({
    "id": [1, 2, 3, 4, 5],
    "w": [10.0, 10.0, 10.0, 10.0, 10.0],
    "x1": [1, 0, 1, 0, 1],
})
totals = {"x1": 40.0}

calibrator = SurveyCalibrator()
# Calibrate
res_df = calibrator.calibrate_main_weight(df, "w", totals)

# Run analytics impact assessment
impact = calculate_calibration_impact(df, res_df, "w", "final_calibrated_weight", [])
print(f"Variance Inflation: {impact['variance_inflation']:.3f}")
```

---

### certify

#### Description
Applies a strict set of rules to determine the overall success and quality grade (A-F) of the calibration run.

#### Usage
`qa.certify(result, df)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `result` | `CalibrationResult` | REQUIRED | Result object. |
| `df` | `pl.DataFrame` | REQUIRED | Initial DataFrame. |

#### Details
Evaluates based on objective convergence, extreme g-factors, and design effect (Deff) inflation.

#### Value
Updated `CalibrationResult` with a populated quality block.

#### References
N/A

#### Examples
```python
# qa = QualityAssurance()
# res_certified = qa.certify(res, df)
# print(f"Assigned Grade: {res_certified.quality.grade}")
```

---

### generate_quality_declaration

#### Description
Generates a comprehensive markdown-formatted quality declaration summarizing the calibration process, execution environment, and metrics.

#### Usage
`qa.generate_quality_declaration(result)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `result` | `CalibrationResult` | REQUIRED | Certified result object. |

#### Details
Creates a human-readable report.

#### Value
String containing the markdown report.

#### References
N/A

#### Examples
```python
# print(qa.generate_quality_declaration(res_certified))
```

---

## 7. Persistence

### AuditDatabase

#### Description
Handles the persistence of calibration factors, diagnostics, and metrics to an SQLite database.

#### Usage
`AuditDatabase(db_path="calibration_factors.db")`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `db_path` | `str` | `"calibration_factors.db"` | DB path. |

#### Details
Provides `save_run` and `save_weights`.

#### Value
Initialized `AuditDatabase`.

#### References
N/A

#### Examples
```python
# db = AuditDatabase()
# db.save_run(result, "run_01")
```
