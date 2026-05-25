# Module Documentation: Imputation

## 1. Module Overview
The `imputation` package provides a robust, production-grade framework for treating item non-response in national statistical survey pipelines. It implements a multi-tier strategy combining deterministic corrections, semi-parametric donor-based methods (Nearest Neighbor and Predictive Mean Matching), and parametric estimators (Ratio, Regression, and Machine Learning models). The package is designed for high-throughput processing while maintaining strict audit trails and providing automated quality certification (A-F grading) based on imputation rates and distributional divergence.

## 2. Table of Contents
- [3. Engine Orchestration](#3-engine-orchestration)
- [4. Parametric Estimators](#4-parametric-estimators)
- [5. Donor Methods (Hot-Deck)](#5-donor-methods-hot-deck)
- [6. Deterministic & Balancing](#6-deterministic--balancing)
- [7. Multiple & Iterative Imputation](#7-multiple--iterative-imputation)
- [8. Quality & Analytics](#8-quality--analytics)

---

## 3. Engine Orchestration

### ImputationEngine

#### Description
The primary orchestrator for the imputation pipeline.

#### Usage
`ImputationEngine(data, metadata)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `data` | `pl.DataFrame` \| `str` | REQUIRED | Input dataset or path to Parquet file. |
| `metadata` | `dict` \| `ImputationConfig` | REQUIRED | Configuration defining the sequence, hierarchy, and tasks. |

#### Details
Coordinates the sequential execution of imputation methodologies based on the provided configuration.

> [!IMPORTANT]
> **Data Requirement:** The imputation engine strictly relies on Flag-To-Impute (`_FTI`) boolean columns to identify which cells require imputation (e.g., `employment_FTI`, `revenue_FTI`). The engine will NOT automatically impute `null` values without these flags. If a corresponding `_FTI` column is missing, the engine assumes 0 records need imputation for that variable. These flags should typically be generated upstream by an Error Localization module.

#### Value
Initialized `ImputationEngine`.

#### References
- Sigman, R. S., & Wagner, D. (1997). *Editing and Imputation of Business Survey Data*.

#### Examples
```python
import polars as pl
from imputation.engine import ImputationEngine
from imputation.models import ImputationConfig

# The execution example is provided under run_imputation_module below.
```

---

### run_imputation_module

#### Description
Executes the configured imputation sequence.

#### Usage
`engine.run_imputation_module(df=None)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | `None` | Optional DataFrame to process. Uses instance data if None. |

#### Details
Runs tasks in order: e.g., deterministic -> donor -> estimators.

#### Value
Returns an `ImputationResult` object with processed data and diagnostics.

#### References
N/A

#### Examples
```python
import polars as pl
import numpy as np
from imputation.engine import ImputationEngine
from imputation.models import ImputationConfig, EstimatorTask

df = pl.DataFrame({
    "id": range(100),
    "rev": [100.0 + i if i < 80 else None for i in range(100)],
    "prev_rev": [100.0 + i for i in range(100)],
    "rev_FTI": [False]*80 + [True]*20
})
config = ImputationConfig(
    estimator_config=[EstimatorTask(target="rev", method="ratio", aux=["prev_rev"])],
    imputation_sequence=["estimators"],
    persist_results=False
)
res = ImputationEngine(df, config).run_imputation_module()
print(res.data.filter(pl.col("rev_FTI")).head())
```

---

## 4. Parametric Estimators

### ImputationEstimator

#### Description
A suite of parametric and non-parametric modeling tools for point estimation.

#### Usage
`ImputationEstimator(df, min_training_samples=10)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | Training and prediction dataset. |
| `min_training_samples` | `int` | `10` | Minimum valid observations required to fit a model. |

#### Details
Provides methods for various statistical and ML-based imputations.

#### Value
Initialized `ImputationEstimator`.

#### References
N/A

#### Examples
```python
import polars as pl
from imputation.estimators import ImputationEstimator

# Initialization example
df = pl.DataFrame({"y": [1.0, 2.0], "x": [3.0, 4.0]})
est = ImputationEstimator(df, min_training_samples=1)
```

---

### cur_ratio

#### Description
Computes a ratio estimate using a single auxiliary variable.

#### Usage
`est.cur_ratio(target_col, aux_col, weight_col=None)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `target_col` | `str` | REQUIRED | Target variable to impute. |
| `aux_col` | `str` | REQUIRED | Auxiliary variable. |
| `weight_col` | `str` | `None` | Optional survey weights. |

#### Details
**Ratio Estimator ($\hat{\beta}$)**
The module implements a weighted ratio estimator to preserve the linear relationship between a target $y$ and an auxiliary $x$:
$$\hat{y}_{i, \text{imp}} = \hat{\beta} x_i, \quad \text{where} \quad \hat{\beta} = \frac{\sum_{j \in S_r} w_j y_j}{\sum_{j \in S_r} w_j x_j}$$
If no weights are provided ($w_j=1$), the formula reduces to the classical population ratio.

#### Value
`pl.Series` of predicted values.

#### References
N/A

#### Examples
```python
import polars as pl
from imputation.estimators import ImputationEstimator

df = pl.DataFrame({
    "revenue": [10.0, 20.0, 30.0, None],
    "employees": [1.0, 2.0, 3.0, 4.0],
    "revenue_FTI": [False, False, False, True]
})
est = ImputationEstimator(df, min_training_samples=3)
preds = est.cur_ratio("revenue", "employees")
print(f"Ratio Prediction: {preds[-1]}")
```

---

### cur_reg

#### Description
Fits a linear regression model using auxiliary columns.

#### Usage
`est.cur_reg(target_col, aux_cols, stochastic=False, weight_col=None)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `target_col` | `str` | REQUIRED | Target variable. |
| `aux_cols` | `list` | REQUIRED | Independent variables. |
| `stochastic` | `bool` | `False` | Add random residual. |
| `weight_col` | `str` | `None` | Survey weights. |

#### Details
**Stochastic Regression Imputation**
The `cur_reg` method fits a linear model and optionally adds a random residual to preserve the variance:
$$\hat{y}_{i, \text{imp}} = X_i \hat{\beta} + e_{j}, \quad \text{where} \quad e_j \sim \text{Resid}(S_r)$$
This ensures that the imputed data does not collapse onto the regression line, maintaining the original error structure.

#### Value
`pl.Series` of predicted values.

#### References
N/A

#### Examples
```python
import polars as pl
from imputation.estimators import ImputationEstimator

df = pl.DataFrame({
    "revenue": [10.0, 20.0, 30.0, None],
    "employees": [1.0, 2.0, 3.0, 4.0],
    "assets": [5.0, 10.0, 15.0, 20.0],
    "revenue_FTI": [False, False, False, True]
})
est = ImputationEstimator(df, min_training_samples=3)
preds = est.cur_reg("revenue", ["employees", "assets"], stochastic=True)
print(f"Stochastic Regression Prediction: {preds[-1]}")
```

---

### xgboost_regression

#### Description
Gradient Boosted Trees regression.

#### Usage
`est.xgboost_regression(target_col, aux_cols, weight_col=None, stochastic=False, **kwargs)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `target_col` | `str` | REQUIRED | Target. |
| `aux_cols` | `list` | REQUIRED | Features. |
| `weight_col` | `str` | `None` | Weights. |
| `stochastic` | `bool` | `False` | Add random residual. |

#### Details
**Gradient Boosted Tree Imputation (XGBoost)**
XGBoost is used for high-performance non-parametric imputation. It is particularly effective for survey data with complex, non-linear interactions between auxiliary variables:
$$\hat{y}_i = \sum_{k=1}^K f_k(X_i), \quad f_k \in \mathcal{F}$$
where $K$ is the number of trees and $f_k$ are regression trees. The implementation supports native handling of missing values in the auxiliary set and can optionally add random residuals (stochastic mode) to maintain distributional variance.

#### Value
`pl.Series` of predicted values.

#### References
- Chen, T., & Guestrin, C. (2016). *XGBoost: A Scalable Tree Boosting System*.

#### Examples
```python
import polars as pl
import numpy as np
from imputation.estimators import ImputationEstimator

# Provide 10+ samples to satisfy default min_training_samples=10
df = pl.DataFrame({
    "y": [10.0, 12.0, 15.0, 18.0, 20.0, 22.0, 25.0, 28.0, 30.0, 32.0, None],
    "x1": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0],
    "x2": [5.0, 4.0, 3.0, 2.0, 1.0, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05],
    "y_FTI": [False]*10 + [True]
})
est = ImputationEstimator(df, min_training_samples=5) # Explicitly lower if needed
preds = est.xgboost_regression("y", ["x1", "x2"], n_estimators=50)
print(f"ML Prediction: {preds[-1]}")
```

---

### random_forest_regression

#### Description
Ensemble-based Random Forest regression.

#### Usage
`est.random_forest_regression(target_col, aux_cols, weight_col=None, stochastic=False, **kwargs)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `target_col` | `str` | REQUIRED | Target. |
| `aux_cols` | `list` | REQUIRED | Features. |

#### Details
**Random Forest Imputation**
Based on the Breiman (2001) algorithm, this method fits multiple decision trees on bootstrap samples of the data and averages their predictions:
$$\hat{y}_{i, \text{imp}} = \frac{1}{B} \sum_{b=1}^B T_b(X_i)$$
This method is highly robust to noise and provides a non-parametric alternative to linear regression when the relationship between $y$ and $X$ is unknown.

#### Value
`pl.Series` of predicted values.

#### References
- Breiman, L. (2001). *Random Forests*. Machine Learning.

#### Examples
```python
import polars as pl
from imputation.estimators import ImputationEstimator

df = pl.DataFrame({
    "y": [10.5, 20.1, 15.2, 30.4, 25.5, 40.6, 35.7, 50.8, 45.9, 60.0, None],
    "x1": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    "y_FTI": [False]*10 + [True]
})

est = ImputationEstimator(df, min_training_samples=5)
preds = est.random_forest_regression("y", ["x1"], n_estimators=100)
print(f"RF Prediction: {preds[-1]}")
```

---

### aux_trend, locf, time_series_interpolate

#### Description
Longitudinal methods for propagating historical values.

#### Usage
`est.aux_trend(target_col, aux_col, historical_target_col, historical_aux_col)`
`est.locf(target_col, sort_col, id_col)`
`est.time_series_interpolate(target_col, sort_col, id_col)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `target_col` | `str` | REQUIRED | Target. |
| `sort_col` | `str` | REQUIRED | Time sort column. |
| `id_col` | `str` | REQUIRED | Unit identifier. |

#### Details
- **Historical Auxiliary Trend Estimator**: Imputes current values using historical relationships: $\hat{y}_{i,t} = x_{i,t} \times \left( \frac{y_{i,t-1}}{x_{i,t-1}} \right)$.
- **LOCF (Last Observation Carried Forward)**: Sorts data by time ($t$) and propagates the last known valid value: $\hat{y}_{i,t} = y_{i, t-1}$.
- **Time Series Interpolation**: Linearly interpolates values for missing periods situated between two valid periods $t_1$ and $t_2$:
  $$\hat{y}_{i,t} = y_{i,t_1} + (t - t_1) \frac{y_{i,t_2} - y_{i,t_1}}{t_2 - t_1}$$

#### Value
`pl.Series` of predicted values.

#### References
N/A

#### Examples
```python
import polars as pl
from imputation.estimators import ImputationEstimator

df = pl.DataFrame({
    "id": [1, 1, 1, 2, 2, 2],
    "time": [1, 2, 3, 1, 2, 3],
    "y": [10.0, None, 14.0, 50.0, None, None],
    "x": [5.0, 6.0, 7.0, 25.0, 26.0, 27.0],
    "y_prev": [8.0, 10.0, 12.0, 48.0, 50.0, 52.0],
    "x_prev": [4.0, 5.0, 6.0, 24.0, 25.0, 26.0],
    "y_FTI": [False, True, False, False, True, True]
})

est = ImputationEstimator(df, min_training_samples=1)

# 1. Historical Auxiliary Trend for ID 1, time 2
trend_preds = est.aux_trend("y", "x", "y_prev", "x_prev")

# 2. Linear Interpolation for ID 1, time 2
interp_preds = est.time_series_interpolate("y", sort_col="time", id_col="id")

# 3. Last Observation Carried Forward (LOCF) for ID 2
locf_preds = est.locf("y", sort_col="time", id_col="id")

print(f"Trend Prediction (ID 1, t=2): {trend_preds[1]}")
print(f"Interpolation (ID 1, t=2): {interp_preds[1]}")
print(f"LOCF (ID 2, t=2): {locf_preds[4]}")
```

---

### mean

#### Description
Computes the mean of the target variable for imputation.

#### Usage
`est.mean(target_col, weight_col=None)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `target_col` | `str` | REQUIRED | Target. |
| `weight_col` | `str` | `None` | Weights. |

#### Details
**Mean Imputation**
A baseline method substituting missing values with the population (or stratum) mean:
$$\hat{y}_i = \frac{\sum_{j \in S_r} w_j y_j}{\sum_{j \in S_r} w_j}$$
While simple, this method artificially reduces the variance of the dataset and is typically reserved for non-critical variables or as a fallback.

#### Value
`pl.Series` of predicted values.

#### References
N/A

#### Examples
```python
import polars as pl
from imputation.estimators import ImputationEstimator

df = pl.DataFrame({"y": [1.0, 2.0, 3.0, None], "y_FTI": [False, False, False, True]})
est = ImputationEstimator(df, min_training_samples=3)
preds = est.mean("y")
print(f"Mean Prediction: {preds[-1]}")
```

---

## 5. Donor Methods (Hot-Deck)

### DonorImputer & PMMImputer

#### Description
Implementation of semi-parametric "hot-deck" donor methods.

#### Usage
`DonorImputer(donor_df, variables)`
`PMMImputer(donor_df, variables, aux_cols)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `donor_df` | `pl.DataFrame` | REQUIRED | Valid donor frame. |
| `variables` | `list` | REQUIRED | Variables to impute. |
| `aux_cols` | `list` | REQUIRED | (PMM Only) Auxiliary features for matching. |

#### Details
**Donor Imputation (Nearest Neighbor)**
The `DonorImputer` identifies the "closest" respondent (donor) for each non-respondent (recipient) based on a set of common auxiliary variables. 

- **Rank-Value Transformation**: To standardize disparate variables, the engine employs a rank transformation into a $(0,1)$ range:
  $$R(x_i) = \frac{\text{rank}(x_i)}{N+1}$$
- **Chebyshev ($L_\infty$) Metric**: Distance is calculated as the maximum absolute difference across all transformed auxiliary dimensions:
  $$d(i, j) = \max_k |R(x_{ik}) - R(x_{jk})|$$
- **Mass vs. Partial Imputation**: 
  - Partial: Only `FTI=True` fields are replaced.
  - Mass: Entire block of variables is replaced to preserve correlations.
- **Donor Usage Constraints**: To prevent "donor burnout", the engine supports a `max_donor_usage` cap.

#### Value
Initialized objects.

#### References
- Andridge, R. R., & Little, R. J. (2010). *A Review of Hot Deck Imputation for Survey Non-response*. International Statistical Review.

#### Examples
```python
import polars as pl
import numpy as np
from imputation.donor_imputation import PMMImputer

# Provide 10+ donors to satisfy default min_training_samples=10
donor_df = pl.DataFrame({
    "y": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100], 
    "x": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
})
recip_df = pl.DataFrame({"y": [None], "x": [2.1], "y_FTI": [True]})

imputer = PMMImputer(donor_df, variables=["y"], aux_cols=["x"], min_training_samples=5)
imputer.fit()
res = imputer.impute(recip_df)
print(res)
```

---

### run_donor_imputation

#### Description
High-level wrapper for nearest-neighbor or PMM donor imputation.

#### Usage
`run_donor_imputation(df, variables, group_var=None, mass=False, pmm_aux=None, max_donor_usage=None)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | Frame. |
| `variables` | `list` | REQUIRED | Target variables. |
| `group_var` | `str` | `None` | Strata column. |
| `mass` | `bool` | `False` | Entire block replacement. |
| `pmm_aux` | `list` | `None` | Auxiliary columns for PMM. |
| `max_donor_usage` | `int` | `None` | Donor usage limit. |

#### Details
Handles grouping, validation, and KD-Tree lookups sequentially.

#### Value
`pl.DataFrame` with donor-imputed values.

#### References
N/A

#### Examples
```python
import polars as pl
import numpy as np
from imputation.donor_imputation import run_donor_imputation

df = pl.DataFrame({
    "v1": list(np.linspace(0, 100, 20)) + [None],
    "v2": list(np.linspace(0, 50, 20)) + [24.5],
    "v1_FTI": [False]*20 + [True]
})

# Under the hood, this sets up the DonorImputer and KD-Tree
res = run_donor_imputation(df, variables=["v1"], pmm_aux=["v2"])
print(res.tail(1))
```

---

## 6. Deterministic & Balancing

### DeterministicImputer

#### Description
Implements linear programming to resolve missing values uniquely determined by edit constraints.

#### Usage
`DeterministicImputer(A_eq, b_eq, A_le, b_le, variables)`

#### Details
**Deterministic Constraint Resolution**
For a vector of missing values $x_{S}$, the engine solves the following linear program for each $k \in S$:
$$\min / \max x_k \quad \text{subject to} \quad A_{\text{eq}, S} x_S = b_{\text{eq}} - A_{\text{eq}, \bar{S}} x_{\bar{S}}, \quad A_{\text{le}, S} x_S \le b_{\text{le}} - A_{\text{le}, \bar{S}} x_{\bar{S}}$$
If $\min x_k = \max x_k$, the variable $x_k$ is uniquely determined and deterministically imputed.

---

### run_deterministic_imputation

#### Description
Top-level function that orchestrates deterministic imputation using a fast vectorized path and an LP-based slow path.

#### Usage
`run_deterministic_imputation(df, spec)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | Input frame. |
| `spec` | `EditSpecification` | REQUIRED | Rules from `verify_edits`. |

#### Value
`pl.DataFrame` with deterministic corrections.

#### Examples
```python
import polars as pl
from imputation.deterministic_imputation import run_deterministic_imputation
from editing.verify_edits import EditSpecification

# Data where total is missing but components are known
df = pl.DataFrame({
    "id": [1, 2],
    "comp1": [10.0, 20.0],
    "comp2": [5.0, 15.0],
    "total": [None, None],
    "total_FTI": [True, True]
})

# Define edit: comp1 + comp2 - total = 0
spec = EditSpecification(["comp1", "comp2", "total"])
spec.add_edit("comp1 + comp2 - total = 0")

res = run_deterministic_imputation(df, spec)
print(res.select(["id", "total", "total_IMPUTATION_METHOD"]))
```

---

### SurveyProrater

#### Description
Enforces additivity and balance constraints (e.g., components summing to a total).

#### Usage
`SurveyProrater(total_col, part_cols, tolerance=1e-5)`

#### Details
**Reliability-Weighted Prorating**
To resolve balance edit violations ($Total \neq \sum Parts$), the `SurveyProrater` distributes the discrepancy $D = Y_{total} - \sum Y_{parts}$ using reliability weights $\omega_k$:
$$Y_{k, \text{new}} = Y_{k, \text{old}} + D \times \left( \frac{\omega_k}{\sum \omega_j} \right)$$
Variables with $\omega_k=0$ are held constant (treated as definitive admin data), while those with higher weights absorb more of the adjustment.

#### Value
Balanced `pl.DataFrame`.

#### Examples
```python
import polars as pl
from imputation.prorating import SurveyProrater

df = pl.DataFrame({
    "total": [1000.0],
    "part_a": [600.0], # High reliability (e.g. Admin Data)
    "part_b": [300.0]  # Low reliability (e.g. Imputed)
})

# Fix part_a (weight=0), adjust part_b (weight=1)
weights = {"part_a": 0.0, "part_b": 1.0}
prorater = SurveyProrater(total_col="total", part_cols=["part_a", "part_b"])
balanced = prorater.reliability_weighted_prorate(df, weights)
print(balanced) # part_b should be 400.0
```

---

## 7. Multiple & Iterative Imputation

### MultipleImputer

#### Description
Executes the imputation pipeline $M$ times with different random seeds.

#### Usage
`MultipleImputer.run()`

#### Details
Generates multiple datasets representing the distribution of possible imputed values, accounting for the uncertainty of the imputation model.

---

### apply_rubins_rules

#### Description
Aggregates multiple datasets to compute valid point estimates and total variance.

#### Usage
`apply_rubins_rules(combined_df, target_var, weight_col=None)`

#### Details
**Multiple Imputation (Rubin's Rules)**
The `MultipleImputer` generates $m$ datasets, and results are combined using Rubin's Rules to produce a total variance $T$:
1. **Average Estimate**: $\bar{Q} = \frac{1}{m} \sum_{i=1}^m \hat{q}_i$
2. **Within-Imputation Variance**: $\bar{W} = \frac{1}{m} \sum_{i=1}^m w_i$
3. **Between-Imputation Variance**: $B = \frac{1}{m-1} \sum_{i=1}^m (\hat{q}_i - \bar{Q})^2$
4. **Total Variance**: $T = \bar{W} + (1 + \frac{1}{m})B$
The term $(1 + \frac{1}{m})B$ represents the variance added by the missing data mechanism itself.

#### Value
`dict` with `mi_estimate` and `total_variance`.

#### References
- Rubin, D. B. (1987). *Multiple Imputation for Nonresponse in Surveys*. Wiley.

#### Examples
```python
import polars as pl
from imputation.multiple_imputation import MultipleImputer, apply_rubins_rules

# mi = MultipleImputer(data_path="data.parquet", metadata=config, iterations=5)
# datasets = mi.run()
# combined = pl.concat(datasets)
# stats = apply_rubins_rules(combined, "revenue")
# print(f"MI Point Estimate: {stats['mi_estimate']:.2f}")
```

---

### run_iterative_imputation

#### Description
Executes a MICE-like (Multivariate Imputation by Chained Equations) iterative procedure across multiple variables.

#### Usage
`run_iterative_imputation(df, targets, aux_cols, method='xgboost', iterations=3)`

#### Details
Cycles through variables imputing each iteratively, using the latest imputations of other variables as predictors.

#### Value
`pl.DataFrame`.

#### References
- Stekhoven, D. J., & Bühlmann, P. (2012). *MissForest—non-parametric missing value imputation for mixed-type data*.

#### Examples
```python
import polars as pl
import numpy as np
from imputation.estimators import run_iterative_imputation

df = pl.DataFrame({
    "x": [1, 2, 3, 4, 5, 6, 7, 8, 9, None],
    "y": [2, 4, 6, 8, 10, 12, 14, 16, 18, None],
    "x_FTI": [False]*9 + [True],
    "y_FTI": [False]*9 + [True]
})

res = run_iterative_imputation(df, targets=["x", "y"], aux_cols=[], iterations=5, min_training_samples=5)
print(res.tail(1))
```

---

## 8. Quality & Analytics

### ImputationQualityAssessor

#### Description
Evaluates the statistical properties and logical consistency of the imputed dataset compared to the original.

#### Usage
`ImputationQualityAssessor(df_original, df_imputed, target_col, config)`

#### Details
**Distributional Integrity (KS-Test)**
Diagnostics include the Kolmogorov-Smirnov test to detect significant shifts in the empirical distribution function $F(x)$ after imputation:
$$D_n = \sup_x |F_{\text{imputed}}(x) - F_{\text{respondent}}(x)|$$

#### Value
`dict` of test results.

#### Examples
```python
import polars as pl
from imputation.evaluator import ImputationQualityAssessor

orig = pl.DataFrame({"v": [1, 2, 3, 4, None]})
imp = pl.DataFrame({"v": [1, 2, 3, 4, 100]}) # High outlier
qa = ImputationQualityAssessor(orig, imp, "v", {"run_distribution_test": True})
print(qa.run_all_evaluations()["distributional_preservation"])
```

---

### Analytics Methods

#### Description
Generates profiles and impacts.

#### Usage
`generate_missingness_profile(df, target_columns, max_bins=100)`
`calculate_imputation_impact(df_original, df_imputed, target_vars)`

#### Details
Calculates missingness rates and patterns across variables to help diagnose non-response mechanisms, and evaluates the macro-level impact of imputation on totals, variances, and standard errors.

#### Value
`dict` of metrics.

#### Examples
```python
import polars as pl
from imputation.analytics import generate_missingness_profile

df = pl.DataFrame({
    "revenue": [100.0, 200.0, None, 400.0, None],
    "employees": [10, 20, 30, None, 50]
})

profile = generate_missingness_profile(df, target_columns=["revenue", "employees"])
print(f"Revenue missing rate: {profile['revenue']['missing_rate']:.2f}")
```

---

### ImputationQualityAssurance

#### Description
Generates comprehensive quality grades based on error localization results and imputation rates.

#### Usage
`ImputationQualityAssurance(target_variables)`

#### Examples
```python
import polars as pl
from imputation.quality import ImputationQualityAssurance
from imputation.models import ImputationResult

res = ImputationResult(
    data=pl.DataFrame({"v": [1, 2], "v_FTI": [True, True]}), # 100% Imputation
    status="success", overall_success=True, diagnostics={}, execution_time_seconds=0.1
)
qa = ImputationQualityAssurance(target_variables=["v"])
certified = qa.certify(res)
print(f"Grade: {certified.data['v_quality_grade'][0]}")
```

---

### ImputationStore

#### Description
Handles the persistence of operational flags and metrics to an SQLite database.

#### Usage
`ImputationStore(db_path)`

#### Examples
```python
from imputation.persistence import ImputationStore
from imputation.models import ImputationResult
import polars as pl

store = ImputationStore("test_audit.db")
res = ImputationResult(
    data=pl.DataFrame({"id": [1]}), status="success",
    overall_success=True, diagnostics={}, execution_time_seconds=0.5
)
store.save_run(res, "run_001")
print("Audit Persisted to SQLite.")
```
