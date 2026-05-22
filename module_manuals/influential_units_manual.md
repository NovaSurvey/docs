# Module Documentation: influential_units

## 1. Module Overview: influential_units

The `influential_units` package provides a production-grade framework for detecting and treating outliers in survey data. It implements robust estimation techniques designed to reduce the impact of influential units (observations that significantly shift the total estimate) on the precision of the results. The module supports two primary methodologies: **Beaumont-Rivest Winsorization** (optimal exponent detection) and **Huber-style Conditional Bias** (robust weights and pseudo-values). It is fully integrated with the survey estimation pipeline, supporting audit persistence, quality certification, and re-robusted bootstrap variance estimation.

---

## 2. Core Classes & Initialization

### RobustEstimator
> The main engine for influential unit detection and treatment.

**Initialization:** `RobustEstimator(metadata: InfluentialMetadata)`
- **metadata**: Configuration object defining target variables (`analysis_vars`), group levels (`group_vars`), and treatment parameters.

### InfluentialMetadata
> Pydantic model for module configuration.

- **initial_weight_var**: The column name of the design weights.
- **detection_config**: Parameters for identification (e.g., method=`AY`, threshold=`QUARTILE`).
- **treatment_type**: Choice between `WINSORIZATION` or `CONDITIONAL_BIAS`.
- **tuning_constant**: The Huber $c$ parameter for Conditional Bias.

---

## 3. Core Methods & Functions

### RobustEstimator.process(df, run_id=None, save_audit=True)
The primary entry point for the robust estimation pipeline.
- **Returns**: `InfluentialResult` containing the processed `data` (with `influential_weight`), diagnostics per group, and quality summaries.

### RobustEstimator.apply_conditional_bias_treatment(df, base_weight_col)
Generates robust weights and pseudo-values based on Conditional Bias scores.
- **Returns**: `polars.DataFrame` with `_robust_weight` and `_pseudo_value` columns for each analysis variable.

### InfluentialQualityCertifier.certify(result)
Evaluates the statistical impact of the treatment.
- **Returns**: `InfluentialResult` with an updated `quality` object containing an A-F grade and certification status.

### RobustEstimator.compute_impact(result)
Calculates the aggregate reduction in total estimates caused by the treatment.
- **Returns**: `Dict[str, Dict[str, float]]` containing original vs. winsorized totals and percentage reductions.

---

## 4. Details (Methodology & Mathematics)

### Method 1: Beaumont-Rivest Winsorization
This method detects influential units by calculating $z$-scores and identifying an optimal exponent $e \in (0, 1]$ that minimizes the Mean Squared Error (MSE).
- **Transformation**: $w_k = a_k^e$ for influential units.
- **Weight Redistribution**: To preserve the total population mass, weights of ordinary units are adjusted by a constant $c$:
  $$c = \frac{\sum a_{infl} + \sum a_{ord} - \sum a_{infl}^e}{\sum a_{ord}}$$
- **Optimization**: The engine uses a binary bisection solver to find the smallest $e$ such that the bias ratio $\frac{|Bias|}{SE} \leq \delta_{bias}$ and MSE improvement is maximized.

### Method 2: Huber-style Conditional Bias
A modern approach that generates robust weights by bounding the influence of each unit's contribution to the total.
- **Influence Score**: $CB_k = (w_k - 1) \frac{y_k - \text{median}(y)}{\text{MAD}(y)}$
- **Huber Factor**: $\psi_c(CB_k) = \begin{cases} 1 & |CB_k| \leq c \\ \frac{c}{|CB_k|} & |CB_k| > c \end{cases}$
- **Robust Weight**: $w_{k}^{robust} = 1 + (w_k - 1) \psi_c(CB_k)$
- **Pseudo-Values**: $\tilde{y}_k = y_k \frac{w_{k}^{robust}}{w_k}$ (used for analytical variance estimation).

### Re-Robusted Bootstrap
When bootstrap weights are provided, the module applies the treatment independently to each replicate to ensure variance estimates account for the variability in outlier detection.
- **Transformation**: $w_{b,k}^{robust} = 1 + (w_{b,k} - 1) \psi_c(CB_{b,k})$

---

## 5. References

Beaumont, J.-F., & Rivest, L.-P. (2009). Dealing with outliers in survey data. In *Handbook of Statistics* (Vol. 29, pp. 247-279). Elsevier.

Favre, A. C., Matei, A., & Rivest, L. P. (2004). Outlier detection and treatment in business surveys. *Proceedings of the Survey Methods Section, Statistical Society of Canada*.

Hidiroglou, M. A., & Berthelot, J. M. (1986). Statistical editing and imputation for periodic business surveys. *Survey Methodology*, 12(1), 73-83.

---

## 6. Runnable Examples

### Example 1: Standard Winsorization with MSE Optimization
```python
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

### Example 2: Conditional Bias Robust Estimation (Analytical)
```python
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

### Example 3: Re-Robusted Bootstrap Integration
```python
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

### Example 4: Quality Certification & Impact Metrics
```python
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
