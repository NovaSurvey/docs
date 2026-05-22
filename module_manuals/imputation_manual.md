# Module Documentation: Imputation

## 1. Module Overview: Imputation

The `imputation` package provides a robust, production-grade framework for treating item non-response in national statistical survey pipelines. It implements a multi-tier strategy combining deterministic corrections, semi-parametric donor-based methods (Nearest Neighbor and Predictive Mean Matching), and parametric estimators (Ratio, Regression, and Machine Learning models). The package is designed for high-throughput processing while maintaining strict audit trails and providing automated quality certification (A-F grading) based on imputation rates and distributional divergence.

---

## 2. Core Classes & Initialization

### ImputationEngine
> The primary orchestrator for the imputation pipeline.

**Initialization:** `ImputationEngine(data, metadata)`
- **data** (Union[str, polars.DataFrame]): Input dataset or path to Parquet file.
- **metadata** (Union[dict, ImputationConfig]): Configuration defining the sequence, hierarchy, and tasks.

### ImputationEstimator
> A suite of parametric and non-parametric modeling tools for point estimation.

**Initialization:** `ImputationEstimator(df, min_training_samples=10)`
- **df** (polars.DataFrame): Training and prediction dataset.
- **min_training_samples** (int): Minimum valid observations required to fit a model.

### SurveyProrater
> Enforces additivity and balance constraints (e.g., components summing to a total).

**Initialization:** `SurveyProrater(total_col, part_cols, tolerance=1e-5)`
- **total_col** (str): The definitive control variable.
- **part_cols** (List[str]): Components that must be balanced.

### PMMImputer & DonorImputer
> Implementation of semi-parametric "hot-deck" donor methods.

**Initialization (DonorImputer):** `DonorImputer(donor_df, variables)`
**Initialization (PMMImputer):** `PMMImputer(donor_df, variables, aux_cols)`

### DeterministicImputer
> Implements linear programming to resolve missing values that are uniquely determined by edit constraints.

**Initialization:** `DeterministicImputer(A_eq, b_eq, A_le, b_le, variables)`

---

## 3. Core Methods & Functions

### ImputationEngine.run_imputation_module(df=None)
Executes the configured sequence (e.g., `deterministic` -> `donor` -> `estimators`).
- **Returns**: `ImputationResult` object with processed data and diagnostics.

### ImputationEstimator.cur_ratio(target_col, aux_col, weight_col=None)
Computes a ratio estimate using a single auxiliary variable.
- **Returns**: `polars.Series` of predicted values.

### ImputationEstimator.xgboost_regression(target_col, aux_cols, weight_col=None, stochastic=False, **kwargs)
Gradient Boosted Trees regression. Handles non-linearities and missing features natively.
- **Returns**: `polars.Series` of predicted values.

### ImputationEstimator.random_forest_regression(target_col, aux_cols, weight_col=None, stochastic=False, **kwargs)
Ensemble-based Random Forest regression. Robust to outliers and high-dimensional aux data.
- **Returns**: `polars.Series` of predicted values.

### SurveyProrater.proportional_prorate(df)
Distributes discrepancy proportionally across components.
- **Returns**: Balanced `polars.DataFrame`.

### run_deterministic_imputation(df, spec)
Top-level function that orchestrates deterministic imputation using a fast vectorized path and an LP-based slow path.
- **Returns**: `polars.DataFrame` with deterministic corrections.

### run_donor_imputation(df, variables, group_var=None, mass=False, pmm_aux=None, max_donor_usage=None)
High-level wrapper for nearest-neighbor or PMM donor imputation. Supports grouped execution.
- **Returns**: `polars.DataFrame` with donor-imputed values.

### run_prorating(df, config)
Helper function that orchestrates balance resolution using proportional or reliability-weighted methods.
- **Returns**: `polars.DataFrame` with balanced components.

### MultipleImputer.run()
Executes the imputation pipeline $M$ times with different random seeds.
- **Returns**: List of `polars.DataFrame` objects.

### apply_rubins_rules(combined_df, target_var, weight_col=None)
Aggregates multiple datasets to compute valid point estimates and total variance.
- **Returns**: Dictionary with `mi_estimate` and `total_variance`.

### run_iterative_imputation(df, targets, aux_cols, method='xgboost', iterations=3)
Executes a MICE-like (Multivariate Imputation by Chained Equations) iterative procedure across multiple variables.
- **Returns**: `polars.DataFrame` with iteratively imputed values.

---

## 4. Details (Methodology & Mathematics)

### Ratio Estimator ($\hat{\beta}$)
The module implements a weighted ratio estimator to preserve the linear relationship between a target $y$ and an auxiliary $x$:
$$\hat{y}_{i, \text{imp}} = \hat{\beta} x_i, \quad \text{where} \quad \hat{\beta} = \frac{\sum_{j \in S_r} w_j y_j}{\sum_{j \in S_r} w_j x_j}$$
If no weights are provided ($w_j=1$), the formula reduces to the classical population ratio.

### Reliability-Weighted Prorating
To resolve balance edit violations ($Total \neq \sum Parts$), the `SurveyProrater` distributes the discrepancy $D = Y_{total} - \sum Y_{parts}$ using reliability weights $\omega_k$:
$$Y_{k, \text{new}} = Y_{k, \text{old}} + D \times \left( \frac{\omega_k}{\sum \omega_j} \right)$$
Variables with $\omega_k=0$ are held constant (treated as definitive admin data), while those with higher weights absorb more of the adjustment. This allows the system to protect high-quality "anchor" variables while adjusting lower-quality imputed estimates.

### Multiple Imputation (Rubin's Rules)
Multiple Imputation (MI) accounts for the uncertainty introduced by the imputation process. The `MultipleImputer` generates $m$ datasets with different stochastic residuals, and results are combined using Rubin's Rules to produce a total variance $T$:
1. **Average Estimate**: $\bar{Q} = \frac{1}{m} \sum_{i=1}^m \hat{q}_i$
2. **Within-Imputation Variance**: $\bar{W} = \frac{1}{m} \sum_{i=1}^m w_i$
3. **Between-Imputation Variance**: $B = \frac{1}{m-1} \sum_{i=1}^m (\hat{q}_i - \bar{Q})^2$
4. **Total Variance**: $T = \bar{W} + (1 + \frac{1}{m})B$
The term $(1 + \frac{1}{m})B$ represents the variance added by the missing data mechanism itself.

### Donor Imputation (Nearest Neighbor)
The `DonorImputer` identifies the "closest" respondent (donor) for each non-respondent (recipient) based on a set of common auxiliary variables $X$. 

#### Rank-Value Transformation
To standardize disparate variables (e.g., income in dollars vs. age in years), the engine employs a rank transformation into a $(0,1)$ range:
$$R(x_i) = \frac{\text{rank}(x_i)}{N+1}$$
This ensures that variables with larger absolute scales do not dominate the distance calculation.

#### Chebyshev ($L_\infty$) Metric
The distance between recipient $i$ and donor $j$ is calculated as the maximum absolute difference across all transformed auxiliary dimensions:
$$d(i, j) = \max_k |R(x_{ik}) - R(x_{jk})|$$
This metric ensures "local similarity" across all matching variables simultaneously.

#### Mass vs. Partial Imputation
- **Partial Imputation**: Only the specific fields marked with `FTI=True` are replaced by the donor's values.
- **Mass Imputation**: The entire block of variables is replaced from the donor, ensuring that internal correlations and relationships (e.g., $Total = \sum Components$) are preserved as they existed in the respondent record.

#### Donor Usage Constraints
To prevent "donor burnout" (where a single record is used to impute many others, artificially reducing variance), the engine supports a `max_donor_usage` cap. If a donor exceeds this limit, the KD-Tree selects the next best match.

### Distributional Integrity (KS-Test)
Diagnostics include the Kolmogorov-Smirnov test to detect significant shifts in the empirical distribution function $F(x)$ after imputation:
$$D_n = \sup_x |F_{\text{imputed}}(x) - F_{\text{respondent}}(x)|$$

### Deterministic Constraint Resolution
For a vector of missing values $x_{S}$, the engine solves the following linear program for each $k \in S$:
$$\min / \max x_k \quad \text{subject to} \quad A_{\text{eq}, S} x_S = b_{\text{eq}} - A_{\text{eq}, \bar{S}} x_{\bar{S}}, \quad A_{\text{le}, S} x_S \le b_{\text{le}} - A_{\text{le}, \bar{S}} x_{\bar{S}}$$
If $\min x_k = \max x_k$, the variable $x_k$ is uniquely determined and deterministically imputed.

### Stochastic Regression Imputation
The `cur_reg` method fits a linear model and optionally adds a random residual to preserve the variance:
$$\hat{y}_{i, \text{imp}} = X_i \hat{\beta} + e_{j}, \quad \text{where} \quad e_j \sim \text{Resid}(S_r)$$
This ensures that the imputed data does not collapse onto the regression line, maintaining the original error structure.

### Gradient Boosted Tree Imputation (XGBoost)
XGBoost is used for high-performance non-parametric imputation. It is particularly effective for survey data with complex, non-linear interactions between auxiliary variables:
$$\hat{y}_i = \sum_{k=1}^K f_k(X_i), \quad f_k \in \mathcal{F}$$
where $K$ is the number of trees and $f_k$ are regression trees. The implementation supports native handling of missing values in the auxiliary set and can optionally add random residuals (stochastic mode) to maintain distributional variance.

### Random Forest Imputation
Based on the Breiman (2001) algorithm, this method fits multiple decision trees on bootstrap samples of the data and averages their predictions:
$$\hat{y}_{i, \text{imp}} = \frac{1}{B} \sum_{b=1}^B T_b(X_i)$$
This method is highly robust to noise and provides a non-parametric alternative to linear regression when the relationship between $y$ and $X$ is unknown.

---

## 5. References
1. Little, R. J., & Rubin, D. B. (2019). *Statistical Analysis with Missing Data*. Wiley.
2. Beaumont, J.-F., & Bissonnette, J. (2011). *Variance Estimation Under Composite Imputation*. Survey Methodology.
3. Statistics Canada (2010). *Quality Guidelines, Fifth Edition*.
4. Chen, T., & Guestrin, C. (2016). *XGBoost: A Scalable Tree Boosting System*. Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining.
5. Breiman, L. (2001). *Random Forests*. Machine Learning, 45(1), 5-32.
6. Stekhoven, D. J., & Bühlmann, P. (2012). *MissForest—non-parametric missing value imputation for mixed-type data*. Bioinformatics.
7. Andridge, R. R., & Little, R. J. (2010). *A Review of Hot Deck Imputation for Survey Non-response*. International Statistical Review.
8. Rubin, D. B. (1987). *Multiple Imputation for Nonresponse in Surveys*. Wiley.
9. Sigman, R. S., & Wagner, D. (1997). *Editing and Imputation of Business Survey Data*.

---

## 6. Runnable Examples

### Example 1: ImputationEngine (Full Orchestration)
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

### Example 2: SurveyProrater (Proportional Balancing)
```python
import polars as pl
from imputation.prorating import SurveyProrater

df = pl.DataFrame({
    "total": [1000.0],
    "part_a": [600.0],
    "part_b": [300.0]  # Sum = 900, Discrepancy = 100
})
prorater = SurveyProrater(total_col="total", part_cols=["part_a", "part_b"])
balanced = prorater.proportional_prorate(df)
print(balanced)
```

### Example 3: ImputationEstimator (XGBoost ML Imputation)
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

### Example 4: PMMImputer (Predictive Mean Matching)
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

### Example 5: ImputationQualityAssessor (Distributional Diagnostics)
```python
import polars as pl
import numpy as np
from imputation.evaluator import ImputationQualityAssessor

orig = pl.DataFrame({"v": [1, 2, 3, 4, None]})
imp = pl.DataFrame({"v": [1, 2, 3, 4, 100]}) # High outlier
qa = ImputationQualityAssessor(orig, imp, "v", {"run_distribution_test": True})
print(qa.run_all_evaluations()["distributional_preservation"])
```

### Example 6: ImputationQualityAssurance (A-F Grading)
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

### Example 7: ImputationStore (Persistence)
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

### Example 8: run_deterministic_imputation (LP Solver)
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

### Example 9: DonorImputer (K-Nearest Neighbor)
```python
import polars as pl
import numpy as np
from imputation.donor_imputation import DonorImputer

donor_df = pl.DataFrame({
    "v1": np.linspace(0, 100, 20),
    "v2": np.linspace(0, 50, 20)
})
recip_df = pl.DataFrame({
    "v1": [None], "v2": [24.5], "v1_FTI": [True]
})

imputer = DonorImputer(donor_df, variables=["v1", "v2"])
imputer.fit()
res = imputer.impute(recip_df)
print(res)
```

### Example 10: run_iterative_imputation (MICE)
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

### Example 11: ImputationEstimator (Random Forest Imputation)
```python
import polars as pl
from imputation.estimators import ImputationEstimator

df = pl.DataFrame({
    "y": [10.5, 20.1, 15.2, 30.4, 25.5, 40.6, 35.7, 50.8, 45.9, 60.0, None],
    "x1": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    "y_FTI": [False]*10 + [True]
})

est = ImputationEstimator(df, min_training_samples=5)
# Using random forest for non-linear estimation
preds = est.random_forest_regression("y", ["x1"], n_estimators=100)
print(f"RF Prediction: {preds[-1]}")
```

### Example 12: Reliability-Weighted Prorating
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

### Example 13: Multiple Imputation (MI)
```python
import polars as pl
from imputation.multiple_imputation import MultipleImputer, apply_rubins_rules

# config = {...}
mi = MultipleImputer(data_path="data.parquet", metadata=config, iterations=5)
datasets = mi.run()
combined = pl.concat(datasets)

# Calculate combined estimate for 'revenue' using Rubin's Rules
stats = apply_rubins_rules(combined, "revenue")
print(f"MI Point Estimate: {stats['mi_estimate']:.2f}")
print(f"Total Variance: {stats['total_variance']:.4f}")
```
```
