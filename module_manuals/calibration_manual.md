# Module Documentation: Calibration

## 1. Module Overview: Calibration

The `calibration` package implements a high-performance, bounded optimization framework for survey weight adjustment. Its primary objective is to align survey estimates with known population benchmarks (Census totals) while minimizing the distance between design weights and calibrated weights. The engine utilizes convex optimization (via CVXPY and CLARABEL) to enforce range constraints (e.g., preventing negative weights or extreme g-factors) and supports advanced features such as Take-All unit exclusions, AI-assisted pre-processing, and parallel bootstrap replicate calibration.

---

## 2. Core Classes & Initialization

### SurveyCalibrator
> High-level API for production calibration pipelines.

**Initialization:** `SurveyCalibrator(lower_bound_ratio=0.4, upper_bound_ratio=3.0, min_sample_size=5)`
- **lower_bound_ratio** (float): Minimum allowable g-factor ($w_k/a_k$).
- **upper_bound_ratio** (float): Maximum allowable g-factor.
- **min_sample_size** (int): Minimum required units in a stratum to attempt calibration.

### CalibrationEngine
> Low-level optimization engine implementing specific distance metrics.

**Initialization:** `CalibrationEngine(metadata)`
- **metadata** (CalibrationMetadata): Configuration defining the method (`linear`, `raking`, `penalized`, `ai_model_calibrated`), constraints, and calibration groups.

---

## 3. Core Methods & Functions

### SurveyCalibrator.calibrate_main_weight(df, base_weight_col, control_totals, exclusion_col=None)
Orchestrates the calibration of the primary design weight.
- **exclusion_col**: Identifies "Take-All" units whose weights are locked at 1.0 (or their design weight) and whose contributions are removed from the population targets before calibrating the remaining units.

### SurveyCalibrator.calibrate_replicates(df, rep_cols, control_totals, exclusion_col=None, max_workers=8)
Executes calibration for multiple bootstrap replicate weights in parallel using a thread pool.

### CalibrationEngine.calibrate(df, population_frame=None)
Executes the optimization solver for the defined calibration groups.

---

## 4. Details (Methodology & Mathematics)

### Linear Bounded Calibration (Chi-Square)
The default method minimizes the Chi-Square distance between calibrated weights $w_k$ and initial weights $a_k$:
$$\min \sum_{k \in S} \frac{(w_k - a_k)^2}{a_k}$$
Subject to:
1. **Benchmark Constraints**: $\sum_{k \in S} w_k x_{kj} = T_j \quad \forall j$
2. **Range Constraints**: $L \le \frac{w_k}{a_k} \le U$

### Raking Ratio Calibration
Uses the Kullback-Leibler (KL) divergence as the distance metric, which is mathematically equivalent to the classical raking ratio procedure but with added support for range constraints:
$$\min \sum_{k \in S} \left( w_k \log \frac{w_k}{a_k} - w_k + a_k \right)$$

### Penalized (Ridge) Calibration
When exact benchmark matching is not possible (e.g., small samples or inconsistent totals), the engine can apply a Ridge penalty to the objective function, allowing for controlled deviations from targets (Bardsley & Chambers, 1984; Beaumont & Bocci, 2008):
$$\min \text{Dist}(w, a) + \lambda \sum_{j} \left( \frac{\sum w_k x_{kj} - T_j}{T_j} \right)^2$$

### AI Model Assisted Calibration
A two-phase hybrid approach designed to handle highly nonlinear relationships and complex auxiliary variables by leveraging modern machine learning predictors (Wu & Sitter, 2001; Breidt & Opsomer, 2017):
1. **Phase 1 (AI Preprocessor)**: Trains an XGBoost model to predict a target variable $y$ using auxiliary predictors $x$. It then computes the population total of these predictions $\hat{T}_y = \sum_{k \in U} \hat{y}_k$.
2. **Phase 2 (Calibration)**: Calibrates weights using the model predictions as the primary auxiliary variable, effectively enforcing $\sum w_k \hat{y}_k = \hat{T}_y$.

---

## 5. References
1. Deville, J. C., & Särndal, C. E. (1992). *Calibration Estimators in Survey Sampling*. Journal of the American Statistical Association, 87(418), 376-382.
2. Beaumont, J.-F. (2008). *A new approach to weighting and convergence issues in sample surveys*. Survey Methodology, 34(1), 29-40.
3. Beaumont, J.-F., & Bocci, C. (2008). *Another look at ridge calibration*. Metron, 66(1), 5-20.
4. Bardsley, P., & Chambers, R. L. (1984). *Multipurpose estimation from unbalanced samples*. Journal of the Royal Statistical Society: Series C (Applied Statistics), 33(3), 290-299.
5. Wu, C., & Sitter, R. R. (2001). *A model-calibration approach to using complete auxiliary information from survey data*. Journal of the American Statistical Association, 96(453), 185-193.
6. Breidt, F. J., & Opsomer, J. D. (2017). *Model-Assisted Survey Estimation with Modern Prediction Techniques*. Statistical Science, 32(2), 190-205.


---

## 6. Runnable Examples

### Example 1: Basic Linear Calibration (Main Weight)
```python
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

### Example 2: Raking Calibration with Range Bounds
```python
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

### Example 3: Penalized Calibration (Soft Constraints)
```python
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

### Example 4: AI-Assisted Calibration (XGBoost + Calibration)
```python
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

### Example 5: Parallel Replicate Calibration
```python
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
