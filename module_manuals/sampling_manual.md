# Module Documentation: Sampling (Generalized Sampling and Allocation Module)

## 1. Module Overview
The `sampling` package is a comprehensive suite of tools for the design and execution of probability-based survey samples. It covers the entire sampling lifecycle, from identifying optimal strata boundaries and allocating sample sizes to meet precision targets, to drawing units using coordinated Permanent Random Numbers (PRNs) to manage respondent burden. It also includes advanced techniques like balanced sampling, adaptive wave sampling, machine-learning-assisted stratification, and multivariate optimization.

The module is designed for production use in national statistical agencies, featuring SQLite-backed audit trails, multi-domain optimization, and sophisticated burden management tracking.

## 2. Table of Contents
- [3. Stratification](#3-stratification)
- [4. Allocation](#4-allocation)
- [5. Multivariate Allocation](#5-multivariate-allocation)
- [6. Smart Allocation](#6-smart-allocation)
- [7. Selection & Coordination](#7-selection--coordination)
- [8. Balanced Sampling](#8-balanced-sampling)
- [9. Adaptive Wave Sampling](#9-adaptive-wave-sampling)
- [10. Burden Management](#10-burden-management)
- [11. Analytics](#11-analytics)

---

## 3. Stratification

### StratificationEngine

#### Description
Orchestrates the division of a population into homogeneous subgroups (strata).

#### Usage
`StratificationEngine(config)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `config` | `StratificationConfig` | REQUIRED | Defines the target variable, method (`dalenius_hodges`, `geometric`, `lh`, `cart`, `model_based`), and number of strata. |

#### Details
Uses multiple methodologies to find optimal stratum boundaries:
1. **Dalenius-Hodges (Cumulative $\sqrt{f}$)**: Splits the population such that the sum of the square roots of the frequencies in each stratum is constant.
2. **Lavallée-Hidiroglou (LH)**: An iterative algorithm that minimizes the total sample size $n$ for a given global coefficient of variation (CV) by identifying optimal boundaries for a skewed population.
3. **ML-Based (CART/XGBoost)**: Uses decision trees to find boundaries that maximize the variance explained by the stratification.

#### Value
Initialized `StratificationEngine`.

#### References
- Lavallée, P., & Hidiroglou, M. A. (1988). On the stratification of skewed populations. *Survey Methodology*, 14(1), 33-43.

#### Examples
```python
# See run() example below
```

---

### run (StratificationEngine)

#### Description
Executes the stratification algorithm on the input frame.

#### Usage
`engine.run(df)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | The input sampling frame. |

#### Details
Applies the configured methodology to append strata labels to the frame.

#### Value
`StratificationResult`: Contains the data appended with a `stratum` column, and diagnostic statistics for each stratum.

#### References
N/A

#### Examples
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

---

## 4. Allocation

### AllocationEngine

#### Description
Calculates sample sizes based on the specified allocation method.

#### Usage
`AllocationEngine(config)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `config` | `AllocationConfig` | REQUIRED | Defines total budget, CV targets, and method (`proportional`, `optimal`, `power`, `multivariate`). |

#### Details
Delegates to the `Allocation` class methods based on configuration.

#### Value
Initialized `AllocationEngine`.

#### References
N/A

#### Examples
```python
# See run_allocation() example below
```

---

### run_allocation (AllocationEngine)

#### Description
Executes sample size calculation per stratum.

#### Usage
`engine.run_allocation(strata_stats, stratum_col, N_col, S_col, rho_col=None)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `strata_stats` | `pl.DataFrame` | REQUIRED | Frame containing N_h, S_h per stratum. |
| `stratum_col` | `str` | REQUIRED | Stratum identifier column. |
| `N_col` | `str` | REQUIRED | Population size column. |
| `S_col` | `str` | REQUIRED | Standard deviation column. |
| `rho_col` | `str` | `None` | Optional expected response rate. |

#### Details
Calculates $n_h$ to minimize cost or maximize precision based on input strata statistics and predicted non-response (`rho_h`).

#### Value
`AllocationResult` object containing `n_h_dict`.

#### References
N/A

#### Examples
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

---

### Allocation Base Methods

#### Description
Low-level base allocation formulas.

#### Usage
`Allocation.proportional(N_h)`
`Allocation.neyman(N_h, S_h)`
`Allocation.kish_compromise(N_h, k)`
`Allocation.bankier_power_allocation(N_h, S_h, a)`
`optimal_allocation(N_h, S_h, CV_target, Y_total, ...)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `N_h` | `np.ndarray` | REQUIRED | Stratum sizes. |
| `S_h` | `np.ndarray` | REQUIRED | Stratum standard deviations. |
| `a` | `float` | REQUIRED | Power parameter for Bankier. |
| `CV_target` | `float` | REQUIRED | Target Coefficient of Variation. |
| `Y_total` | `float` | REQUIRED | Target Population total. |

#### Details
- **Neyman Allocation**: Minimizes the variance of the estimator for a fixed total sample size: $n_h \propto N_h S_h$.
- **Bankier Power Allocation**: Balances national and domain-level precision: $n_h \propto N_h^a S_h$. 
  - $a=1$: Neyman; $a=0.5$: Square Root; $a=0$: Equal.

#### Value
`np.ndarray` of allocated sample sizes.

#### References
- Bankier, M. D. (1988). Power Allocations: Determining Sample Sizes for Subnational Areas. *The American Statistician*, 42(3), 174-177.

#### Examples
```python
from sampling.allocation import Allocation
alloc = Allocation.neyman(np.array([100, 200]), np.array([5, 10]))
```

---

## 5. Multivariate Allocation

### MultivariateAllocator

#### Description
Implements Bethel's algorithm for multivariate allocation.

#### Usage
`MultivariateAllocator(min_sample_per_stratum=3)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `min_sample_per_stratum` | `int` | `3` | Minimum sample size per stratum. |

#### Details
Uses convex programming to minimize cost $\sum c_h n_h$ subject to multiple precision constraints (CVs) for different variables.

#### Value
Initialized `MultivariateAllocator`.

#### References
- Bethel, J. (1989). Sample allocation in multivariate surveys. *Survey Methodology*, 15(1), 47-57.
- Chromy, J. R. (1987). Design optimization with multiple objectives. *Proceedings of the Section on Survey Research Methods*, 194-199.

#### Examples
```python
from sampling.multivariate_allocation import MultivariateAllocator
allocator = MultivariateAllocator()
```

---

### allocate (MultivariateAllocator)

#### Description
Solves the Bethel optimization problem to fulfill CV constraints.

#### Usage
`allocator.allocate(df_strata, cv_targets, total_budget=None)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df_strata` | `pl.DataFrame` | REQUIRED | Frame containing N_h, S_var, Total_var for multiple variables. |
| `cv_targets` | `dict` | REQUIRED | Target CVs for each variable (e.g. `{"var1": 0.05}`). |
| `total_budget` | `int` | `None` | Optional total sample size constraint. |

#### Details
Iteratively applies the `multivariate_optimal_allocation` gradient descent routine until all CV constraints are met.

#### Value
`pl.DataFrame` with `stratum` and `n_allocated` columns.

#### References
N/A

#### Examples
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

---

## 6. Smart Allocation

### SmartAllocator

#### Description
Uses predictive machine learning models to optimize sample sizes within strata dynamically.

#### Usage
`SmartAllocator(frame, target_cols, feature_cols, strata_col)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `frame` | `pl.DataFrame` | REQUIRED | Frame data. |
| `target_cols` | `list` | REQUIRED | Target columns. |
| `feature_cols` | `list` | REQUIRED | Feature columns for ML. |
| `strata_col` | `str` | REQUIRED | Stratum identifier. |

#### Details
Learns the prediction error distributions across strata using features available on the frame, prioritizing sample sizes in strata where model error is highest.

#### Value
Initialized `SmartAllocator`.

#### References
N/A

#### Examples
```python
# See train_and_predict() example below
```

---

### train_and_predict

#### Description
Trains ML models and predicts optimal sample shifts.

#### Usage
`allocator.train_and_predict(n_h_dict)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `n_h_dict` | `dict` | REQUIRED | Base allocation dictionary to adjust. |

#### Details
Adjusts base allocations proportionally to the predicted residual variance in each stratum.

#### Value
`dict`: Updated sample allocations per stratum.

#### References
N/A

#### Examples
```python
import polars as pl
import numpy as np
from sampling.smart_allocation import SmartAllocator

df = pl.DataFrame({
    "id": range(100),
    "stratum": ["A"] * 50 + ["B"] * 50,
    "feature_1": np.random.randn(100),
    "target": np.random.randn(100) * 10 + 50
})

allocator = SmartAllocator(df, target_cols=["target"], feature_cols=["feature_1"], strata_col="stratum")
base_allocation = {"A": 10, "B": 10}

# Optimizes the allocation based on predictive error
smart_n_h = allocator.train_and_predict(base_allocation)
print(f"Smart Allocation: {smart_n_h}")
```

---

## 7. Selection & Coordination

### SelectionEngine

#### Description
Executes the actual draw of units from a sampling frame.

#### Usage
`SelectionEngine(config)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `config` | `SamplingConfig` | REQUIRED | Defines selection method (`srs`, `poisson`, `systematic`), sample sizes, and PRN settings. |

#### Details
Supports standard random sampling, probability proportional to size (PPS), and permanent random number (PRN) coordination.

#### Value
Initialized `SelectionEngine`.

#### References
- Ohlsson, E. (1995). Coordination of samples using permanent random numbers. In *Business Survey Methods* (pp. 153-169). Wiley.

#### Examples
```python
from sampling.engine import SelectionEngine
# engine = SelectionEngine(config)
```

---

### run_selection

#### Description
Executes the sample draw across the frame.

#### Usage
`engine.run_selection(frame_df)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `frame_df` | `pl.DataFrame` | REQUIRED | The complete sampling frame. |

#### Details
Automatically handles stratified sampling if a stratum column is defined. Generates design weights.

#### Value
`pl.DataFrame` of selected units with an appended `weight` column.

#### References
N/A

#### Examples
```python
# sample = engine.run_selection(frame)
```

---

### PRN Coordination Methods

#### Description
Manages Permanent Random Numbers for longitudinal coordination.

#### Usage
`assign_prns(df, id_col, db_path)`
`execute_sequential_rotation(start_point, fraction)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | Sampling frame. |
| `id_col` | `str` | REQUIRED | Identifier column. |
| `db_path` | `str` | REQUIRED | SQLite db path for PRNs. |
| `start_point` | `float` | REQUIRED | Previous window start $S$. |
| `fraction` | `float` | REQUIRED | Rotation shift fraction. |

#### Details
Assigns a $U(0,1)$ random number to each unit. Selection is performed by taking units within a "window" $[S, S + f_h]$. The window is rotated sequentially to manage burden.

#### Value
`pl.DataFrame` with a `_PRN` column, or the new floating window boundaries.

#### References
N/A

#### Examples
```python
from sampling.selection import assign_prns
# df_prn = assign_prns(df, "id", "prns.db")
```

---

## 8. Balanced Sampling

### BalancedSampler

#### Description
Implements the Cube Method for balanced sampling.

#### Usage
`BalancedSampler(landing_tolerance=1e-6)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `landing_tolerance` | `float` | `1e-6` | Tolerance for landing phase resolution. |

#### Details
Developed by Deville and Tillé, the method ensures that the sample estimates for auxiliary variables exactly equal the known population totals.
- **Flight Phase**: Modifies inclusion probabilities randomly while keeping the balancing equations satisfied.
- **Landing Phase**: Resolves the fractional probabilities remaining at the end of the flight phase.

#### Value
Initialized `BalancedSampler`.

#### References
- Deville, J.-C., & Tillé, Y. (2004). Efficient balanced sampling: The cube method. *Biometrika*, 91(4), 893-912.

#### Examples
```python
# See draw_sample() example below
```

---

### draw_sample (BalancedSampler)

#### Description
Draws a balanced sample.

#### Usage
`sampler.draw_sample(df, n_h_dict, stratum_col, balancing_vars, id_col)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | The sampling frame. |
| `n_h_dict` | `dict` | REQUIRED | Target sample sizes per stratum. |
| `stratum_col` | `str` | REQUIRED | Stratum identifier. |
| `balancing_vars` | `list` | REQUIRED | Columns to balance on. |
| `id_col` | `str` | REQUIRED | Unique ID column. |

#### Details
Applies the Cube method sequentially per stratum to draw a sample that satisfies all specified balancing constraints.

#### Value
`pl.DataFrame` containing the selected units.

#### References
N/A

#### Examples
```python
import polars as pl
import numpy as np
from sampling.balanced import BalancedSampler

# Setup a frame with balancing variables
np.random.seed(42)
df = pl.DataFrame({
    "id": range(100),
    "stratum": ["A"] * 50 + ["B"] * 50,
    "revenue": np.random.uniform(10, 100, 100),
    "employees": np.random.uniform(1, 50, 100)
})

n_h_dict = {"A": 10, "B": 10}

sampler = BalancedSampler()
# The resulting sample will match population totals for revenue and employees
sample_df = sampler.draw_sample(df, n_h_dict, "stratum", ["revenue", "employees"], "id")
print(f"Balanced sample size: {sample_df.height}")
```

---

## 9. Adaptive Wave Sampling

### AdaptiveWaveSampler

#### Description
Manages responsive survey designs, adjusting wave 2 allocations based on wave 1 telemetry.

#### Usage
`AdaptiveWaveSampler(N_h, S_h_matrix, CV_targets, Y_totals, strata_names, costs_h=None, wave_1_fraction=0.40)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `N_h`, `S_h_matrix`, `CV_targets`, `Y_totals` | `np.ndarray` | REQUIRED | Core optimization parameters matching strata lengths. |
| `strata_names` | `list` | REQUIRED | List of strata identifiers. |
| `wave_1_fraction` | `float` | `0.40` | Fraction to allocate to Wave 1. |

#### Details
Facilitates multi-wave sampling optimizations to hit precision targets when field response rates are volatile.

#### Value
Initialized `AdaptiveWaveSampler`.

#### References
N/A

#### Examples
```python
# See Adaptive Wave Methods below
```

---

### Adaptive Wave Methods

#### Description
Methods to execute the multi-wave lifecycle.

#### Usage
`allocate_wave_1(initial_rho_h)`
`ingest_telemetry(actual_responses, actual_sample_sizes)`
`allocate_wave_2()`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `initial_rho_h` | `np.ndarray` | REQUIRED | Expected response rates. |
| `actual_responses` | `dict` | REQUIRED | Observed field response counts. |
| `actual_sample_sizes` | `dict` | REQUIRED | Observed field sample counts. |

#### Details
Tracks live field non-response data to re-optimize remaining sample budget into Wave 2, guaranteeing constraints are met.

#### Value
Returns `dict` of sample allocations for the respective wave.

#### References
N/A

#### Examples
```python
import numpy as np
from sampling.adaptive_wave import AdaptiveWaveSampler

N_h = np.array([1000, 1500])
S_h_matrix = np.array([[10, 20], [15, 25]]) # [strata, variables]
Y_totals = np.array([50000, 60000])
cv_targets = np.array([0.05, 0.05])

sampler = AdaptiveWaveSampler(N_h, S_h_matrix, cv_targets, Y_totals, ["A", "B"], wave_1_fraction=0.4)

# 1. Plan Wave 1
wave1_alloc = sampler.allocate_wave_1(initial_rho_h=np.array([0.8, 0.8]))
print(f"Wave 1 Allocation: {wave1_alloc}")

# 2. Ingest Field Data (e.g., stratum A responded poorly)
actual_responses = {"A": 50, "B": 80}
actual_samples = {"A": 100, "B": 100}
sampler.ingest_telemetry(actual_responses, actual_samples)

# 3. Plan Wave 2 based on updated response rates
wave2_alloc = sampler.allocate_wave_2()
print(f"Wave 2 Allocation: {wave2_alloc}")
```

---

## 10. Burden Management

### Burden Management Methods

#### Description
Updates, decays, and applies response burden exclusions.

#### Usage
`update_burden_scores(sampled_ids, db_path)`
`decay_burden_scores(eligible_ids, sampled_ids, db_path)`
`apply_exclusion_zone(df, id_col, threshold, db_path)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `sampled_ids` | `list` | REQUIRED | Selected IDs to increment. |
| `eligible_ids` | `list` | REQUIRED | All frame IDs for decay logic. |
| `db_path` | `str` | REQUIRED | SQLite DB path. |
| `df` | `pl.DataFrame` | REQUIRED | Current sampling frame. |
| `threshold` | `int` | REQUIRED | Max burden score allowed. |

#### Details
Increments burden when selected. Decays burden if unselected across waves. Excludes highly burdened units from the active frame prior to selection.

#### Value
`apply_exclusion_zone` returns a filtered `pl.DataFrame`.

#### References
N/A

#### Examples
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

---

## 11. Analytics

### calculate_sampling_impact

#### Description
Evaluates precision, CV, design effects, and weights post-sampling.

#### Usage
`calculate_sampling_impact(df_output)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df_output` | `pl.DataFrame` | REQUIRED | Selected sample with weights. |

#### Details
Produces quality metrics to validate the final sample draw against theoretical CV targets.

#### Value
`dict` or `pl.DataFrame` with diagnostic analytics.

#### References
N/A

#### Examples
```python
# from sampling.analytics import calculate_sampling_impact
# metrics = calculate_sampling_impact(sample_df)
```

---

## 12. Case Study: Interactive Diagnostics Dashboard

To see a complete visual and interactive demonstration of these sampling tools in a production-like environment, navigate to the `CaseStudy.jsx` page in the React frontend. It highlights:
- **Skewed Population Frame Simulation:** Modeling of heavy-tailed business datasets.
- **Optimal Sample Allocation Strategies:** Visual comparison of Neyman, Bankier Power, and Bethel's Multivariate Convex Programming.
- **Live Multi-Wave Adaptive Design:** Telemetry tracking to re-allocate samples across multiple waves following non-response shocks.
