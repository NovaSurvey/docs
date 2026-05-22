# Module Documentation: nonresponse_weighting

## 1. Module Overview: nonresponse_weighting

The `nonresponse_weighting` package provides a robust framework for adjusting survey weights to mitigate nonresponse bias. It leverages machine learning (XGBoost) to model response propensities and offers two industry-standard adjustment methodologies: **Response Homogeneity Groups (RHG)** and **Inverse Probability Weighting (IPW)**. The module is designed for production use in official statistics, featuring automated group collapsing, weight capping, mass redistribution, and A-F quality certification based on weight stability and model performance.

---

## 2. Core Classes & Initialization

### ResponsePropensityModel
> Trains a gradient-boosted decision tree to predict unit-level response probabilities.

**Initialization:** `ResponsePropensityModel(config: NRWeightingConfig)`
- **config**: Defines features, hyperparameters (`learning_rate`, `max_depth`), and random seed.

### WeightAdjustmentEngine
> Implements the logic for grouping units, collapsing small strata, and calculating RHG adjustment factors.

**Initialization:** `WeightAdjustmentEngine(config: NRWeightingConfig)`
- **config**: Defines the number of groups, minimum respondent counts, and weight capping thresholds.

### NonresponseWeightingEngine
> The high-level orchestrator that coordinates the full weighting pipeline.

**Initialization:** `NonresponseWeightingEngine(config: NRWeightingConfig)`
- **config**: Global configuration for method selection (`rhg` or `ipw`), persistence, and quality thresholds.

---

## 3. Core Methods & Functions

### NonresponseWeightingEngine.run(df)
The primary execution method for the weighting pipeline.
- **Returns**: `NRWeightingResult` containing the adjusted DataFrame (respondents only), propensity diagnostics, and an automated quality grade.

### ResponsePropensityModel.train_and_diagnose(df)
Trains the XGBoost classifier and computes model performance metrics.
- **Returns**: A tuple of (DataFrame with `p_hat`, `PropensityDiagnostics`, List of warnings).

### WeightAdjustmentEngine.process(df_with_propensity)
Executes RHG bucketing, handles group collapsing, and calculates the final adjustment factors.
- **Returns**: A tuple of (Respondent DataFrame with `adjusted_weight`, List of `NRWeightingDiagnostics`, metadata dictionary).

### NRQualityAssurance.certify(result, df_input)
Performs post-processing diagnostics on the weight distribution.
- **Returns**: An updated `NRWeightingResult` with an A-F quality grade based on weight CV inflation.

---

## 4. Details (Methodology & Mathematics)

### Propensity Modeling
The module models the probability of response $R_k$ for unit $k$ given auxiliary features $X_k$ using a logistic objective:
$$P(R_k=1 | X_k) = \frac{1}{1 + \exp(-F(X_k))}$$
where $F(X_k)$ is the ensemble output of the XGBoost model.

### Response Homogeneity Groups (RHG)
Units are partitioned into $H$ groups based on their propensity scores. Within each group $h$, the adjustment factor $f_h$ is calculated as the ratio of the total design weight of the sample to the design weight of the respondents:
$$f_h = \frac{\sum_{k \in s_h} d_k}{\sum_{k \in r_h} d_k}$$
where $d_k$ is the design weight, $s_h$ is the set of all sampled units in group $h$, and $r_h$ is the set of respondents. If $f_h > \text{cap}$, it is truncated to the cap value, and the lost mass may be redistributed to preserve the population total.

### Inverse Probability Weighting (IPW)
Adjusted weights are calculated directly as the product of the design weight and the inverse of the predicted response propensity $\hat{p}_k$:
$$w_{adj, k} = d_k \cdot \frac{1}{\hat{p}_k}$$
A safety floor $\hat{p}_{min}$ is applied to prevent extreme weights: $\hat{p}_k^* = \max(\hat{p}_k, \hat{p}_{min})$.

---

## 5. References

Little, R. J. A., & Rubin, D. B. (2002). *Statistical Analysis with Missing Data*. Wiley.

Brick, J. M. (2013). Unit Nonresponse and Weighting Adjustments. *Handbook of Survey Methodology*.

Chen, T., & Guestrin, C. (2016). XGBoost: A Scalable Tree Boosting System. *Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining*.

---

## 6. Runnable Examples

### Example 1: Propensity Model Training and Diagnostics
```python
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

### Example 2: RHG Processing and Group Collapsing
```python
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

### Example 3: Full Pipeline Execution (RHG Method)
```python
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

### Example 4: Full Pipeline Execution (IPW Method)
```python
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
