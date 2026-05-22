# Module Documentation: Sampling (Generalized Sampling and Allocation Module)

## 1. Module Overview: Sampling

The `sampling` package is a comprehensive suite of tools for the design and execution of probability-based survey samples. It covers the entire sampling lifecycle, from identifying optimal strata boundaries and allocating sample sizes to meet precision targets, to drawing units using coordinated Permanent Random Numbers (PRNs) to manage respondent burden. The module is designed for production use in national statistical agencies, featuring SQLite-backed audit trails, multi-domain optimization, and machine-learning-assisted stratification.

---

## 2. Core Classes & Initialization

### StratificationEngine
> Orchestrates the division of a population into homogeneous subgroups (strata).

**Initialization:** `StratificationEngine(config: StratificationConfig)`
- **config**: Defines the target variable, method (`dalenius_hodges`, `geometric`, `lh`, `cart`, `model_based`), and number of strata.

### AllocationEngine
> Determines the sample size for each stratum to minimize cost or maximize precision.

**Initialization:** `AllocationEngine(config: AllocationConfig)`
- **config**: Defines the total budget, CV targets, and method (`proportional`, `optimal`, `power`, `multivariate`).

### SelectionEngine
> Executes the actual draw of units from a sampling frame.

**Initialization:** `SelectionEngine(config: SamplingConfig)`
- **config**: Defines the selection method (`srs`, `poisson`, `systematic`), stratum sizes, and PRN coordination settings.

---

## 3. Core Methods & Functions

### StratificationEngine.run(df)
Executes the stratification algorithm on the input frame.
- **Returns**: `StratificationResult` object containing the data appended with a `stratum` column, and diagnostic statistics for each stratum.

### AllocationEngine.run_allocation(strata_stats, stratum_col, N_col, S_col, rho_col=None)
Calculates sample sizes based on the specified allocation method.
- **Returns**: `AllocationResult` object containing the `n_h_dict` (stratum ID to sample size mapping) and projected CVs.

### SelectionEngine.run_selection(frame_df)
Executes the sample draw from the frame.
- **Returns**: `SamplingResult` object containing the sampled DataFrame (with `design_weight` and PRNs) and audit-compliant diagnostics.

### MultivariateAllocator.allocate(df_strata, cv_targets, total_budget=None)
Solves the Bethel optimization problem for multiple variables.
- **Returns**: `polars.DataFrame` with an added `n_allocated` column.

---

## 4. Details (Methodology & Mathematics)

### Stratification Methodologies
1. **Dalenius-Hodges (Cumulative $\sqrt{f}$)**: Splits the population such that the sum of the square roots of the frequencies in each stratum is constant.
2. **Lavallée-Hidiroglou (LH)**: An iterative algorithm that minimizes the total sample size $n$ for a given global coefficient of variation (CV) by identifying optimal boundaries for a skewed population, typically including a Take-All stratum.
   - **Sethis iteration proxy**: $b_h = \frac{\mu_h + \mu_{h+1}}{2} + \frac{\sigma_h^2 - \sigma_{h+1}^2}{2(\mu_h - \mu_{h+1})}$
3. **ML-Based (CART/XGBoost)**: Uses decision trees or gradient boosting to find boundaries that maximize the variance explained by the stratification.

### Allocation Methodologies
1. **Neyman Allocation**: Minimizes the variance of the estimator for a fixed total sample size: $n_h \propto N_h S_h$.
2. **Bankier Power Allocation**: A compromise for multi-domain surveys that balances national and domain-level precision:
   $$n_h \propto N_h^a S_h$$
   - $a=1$: Neyman; $a=0.5$: Square Root (Standard); $a=0$: Equal Allocation (weighted by $S_h$).
3. **Bethel's Multivariate Allocation**: Uses convex programming to minimize cost $\sum c_h n_h$ subject to multiple precision constraints (CVs) for different variables.

### Selection & Coordination
- **PRN Coordination**: Assigns a $U(0,1)$ random number to each unit. Selection is performed by taking units within a "window" $[S, S + f_h]$, where $S$ is the start point (rotation offset) and $f_h$ is the sampling fraction.
- **Poisson Sampling**: Each unit $k$ is selected independently with probability $\pi_k$. If $PRN_k < \pi_k$, the unit is in the sample.

---

## 5. References

Lavallée, P., & Hidiroglou, M. A. (1988). On the stratification of skewed populations. *Survey Methodology*, 14(1), 33-43.

Bankier, M. D. (1988). Power Allocations: Determining Sample Sizes for Subnational Areas. *The American Statistician*, 42(3), 174-177.

Bethel, J. (1989). Sample allocation in multivariate surveys. *Survey Methodology*, 15(1), 47-57.

Ohlsson, E. (1995). Coordination of samples using permanent random numbers. In *Business Survey Methods* (pp. 153-169). Wiley.

---

## 6. Runnable Examples

### Example 1: Univariate Stratification (Lavallée-Hidiroglou)
```python
import polars as pl
import numpy as np
from sampling.engine import StratificationEngine
from sampling.models import StratificationConfig

# Create a skewed population (Lognormal)
data = np.random.lognormal(mean=2, sigma=1, size=1000)
df = pl.DataFrame({"id": range(1000), "revenue": data})

config = StratificationConfig(
    target_col="revenue",
    feature_cols=[], # Required even for univariate
    method="lh",
    n_strata=3,
    take_all_threshold=50.0 # Units above 50 are automatically "TAKE_ALL"
)

engine = StratificationEngine(config)
res = engine.run(df)
print(res.data.group_by("stratum").len())
```

### Example 2: Optimal Allocation with Non-Response Adjustment
```python
import polars as pl
from sampling.engine import AllocationEngine
from sampling.models import AllocationConfig

# Strata statistics: N_h, S_h, and expected response rate rho_h
stats = pl.DataFrame({
    "region": ["North", "South", "East", "West"],
    "N_h": [1000, 2000, 1500, 500],
    "S_h": [50.0, 80.0, 60.0, 40.0],
    "rho_h": [0.8, 0.7, 0.85, 0.6] # Response rates
})

config = AllocationConfig(
    method="optimal",
    CV_target=0.05,
    Y_total=500000.0, # Approximate population total
    total_budget=500 # Enforce a total sample size
)

engine = AllocationEngine(config)
res = engine.run_allocation(stats, stratum_col="region", N_col="N_h", S_col="S_h", rho_col="rho_h")
print(res.n_h_dict)
```

### Example 3: Multivariate (Bethel) Allocation
```python
import polars as pl
from sampling.multivariate_allocation import MultivariateAllocator

# Multiple variables with different totals and standard deviations
strata_stats = pl.DataFrame({
    "stratum": ["A", "B", "C"],
    "N_h": [1000, 1000, 1000],
    "S_var1": [10.0, 20.0, 30.0],
    "Total_var1": [5000, 5000, 5000],
    "S_var2": [40.0, 10.0, 5.0],
    "Total_var2": [8000, 8000, 8000]
})

cv_targets = {"var1": 0.1, "var2": 0.1}

allocator = MultivariateAllocator()
res = allocator.allocate(strata_stats, cv_targets)
print(res.select(["stratum", "n_allocated"]))
```

### Example 4: PRN-Coordinated Selection with Rotation
```python
import polars as pl
from sampling.engine import SelectionEngine
from sampling.models import SamplingConfig

df = pl.DataFrame({
    "id": range(100),
    "region": ["A"]*50 + ["B"]*50
})

config = SamplingConfig(
    stratum_col="region",
    n_h_dict={"A": 10, "B": 10},
    selection_method="stratified_srs",
    coordination_method="prn",
    survey_start_offset=0.2, # Rotate starting point to 0.2
    instance_index=1
)

engine = SelectionEngine(config)
res = engine.run_selection(df)
print(f"Sample size: {res.data.height}, Start point used: {res.diagnostics[0].prn_start}")
```

### Example 5: Response Burden Tracking
```python
import polars as pl
from sampling.burden_management import update_burden_scores, apply_exclusion_zone

# Frame for current wave
df = pl.DataFrame({"id": [1, 2, 3, 4, 5], "revenue": [100.0]*5})

# Record that units 1 and 2 were selected in previous waves
update_burden_scores([1, 2], db_path="burden.db")

# Apply exclusion zone (threshold=1)
df_eligible = apply_exclusion_zone(df, id_col="id", threshold=1, db_path="burden.db")
print(df_eligible) # Units 1 and 2 will be removed
```
