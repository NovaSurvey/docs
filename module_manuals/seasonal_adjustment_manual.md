# Module Documentation: Seasonal Adjustment

## 1. Module Overview
The `seasonal_adjustment` module provides a production-grade framework for isolating and removing predictable seasonal and calendar effects from time-series data. It is designed to reveal the underlying economic trend and cycle for official statistics production. The module implements a robust 3-phase pipeline:
1.  **Seasonal Adjustment**: Primary decomposition using classical (X-13ARIMA-SEATS), robust (STL), or modern (Machine Learning) methods.
2.  **Temporal Benchmarking**: Ensuring high-frequency estimates (e.g., monthly) sum to low-frequency benchmarks (e.g., annual totals).
3.  **Hierarchical Reconciliation**: Enforcing consistency across complex geographical or industrial hierarchies.

## 2. Table of Contents
- [3. Master Orchestration](#3-master-orchestration)
  - [SeasonalAdjustmentEngine](#seasonaladjustmentengine)
  - [process](#process)
- [4. Core Decomposition](#4-core-decomposition)
  - [SeasonalAdjuster](#seasonaladjuster)
  - [adjust](#adjust)
  - [_run_x13](#_run_x13)
  - [_run_stl](#_run_stl)
  - [_run_ml_preprocessor](#_run_ml_preprocessor)
- [5. Benchmarking & Reconciliation](#5-benchmarking--reconciliation)
  - [TemporalBenchmarker](#temporalbenchmarker)
  - [benchmark](#benchmark)
  - [HierarchicalReconciler](#hierarchicalreconciler)
  - [reconcile](#reconcile)
- [6. Diagnostics & Revisions](#6-diagnostics--revisions)
  - [RevisionsTracker](#revisionstracker)
  - [compute_revisions](#compute_revisions)
  - [calculate_seasonal_impact](#calculate_seasonal_impact)
- [7. Persistence](#7-persistence)
  - [FactorBank](#factorbank)

---

## 3. Master Orchestration

### SeasonalAdjustmentEngine

#### Description
The high-level orchestrator for the 3-phase adjustment pipeline.

#### Usage
`SeasonalAdjustmentEngine(config, db_path="seasonal_factors.db")`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `config` | `SeasonalAdjustmentMetadata` | REQUIRED | Defines the parameters for all three phases. |
| `db_path` | `str` | `"seasonal_factors.db"` | Path to the SQLite factor bank for audit persistence. |

#### Details
Initializes the engine that coordinates adjustment, benchmarking, and reconciliation.

#### Value
Initialized `SeasonalAdjustmentEngine`.

#### References
N/A

#### Examples
```python
# See process() example below.
```

---

### process (SeasonalAdjustmentEngine)

#### Description
Executes the full 3-phase pipeline.

#### Usage
`engine.process(df, benchmark_df=None)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | Raw high-frequency data. |
| `benchmark_df` | `pl.DataFrame` | `None` | Optional low-frequency benchmark data. |

#### Details
Coordinates `SeasonalAdjuster`, `TemporalBenchmarker`, and `HierarchicalReconciler`.

#### Value
`SAResult` containing the adjusted data and exhaustive `DiagnosticsReport` objects for each phase.

#### References
N/A

#### Examples
```python
# Example 3: Full 3-Phase Orchestration
import polars as pl
from datetime import datetime
from seasonal_adjustment.engine import SeasonalAdjustmentEngine
from seasonal_adjustment.models import SeasonalAdjustmentMetadata, SeasonalConfig

df = pl.DataFrame({
    "time": pl.date_range(datetime(2020, 1, 1), datetime(2023, 12, 1), interval="1mo", eager=True),
    "revenue": [500 + 50 * (i % 12) + 5 * i for i in range(48)]
})

config = SeasonalAdjustmentMetadata(
    seasonal=SeasonalConfig(
        method="stl",
        target_vars=["revenue"],
        time_col="time"
    )
)

engine = SeasonalAdjustmentEngine(config)
result = engine.process(df)

print(f"Run Status: {result.status}")
print(f"Execution Time: {result.metadata['execution_time_seconds']:.2f}s")
print(result.data.head())
```

---

## 4. Core Decomposition

### SeasonalAdjuster

#### Description
The engine responsible for the primary time-series decomposition.

#### Usage
`SeasonalAdjuster(config)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `config` | `dict` | REQUIRED | A dictionary containing `method` (x13, ml, or stl), `target_vars`, and model-specific parameters. |

#### Details
**Time-Series Decomposition Models**
The module supports both additive and multiplicative models:
- **Additive**: $Y_t = T_t + S_t + I_t$ (Standard for data with constant seasonal amplitude).
- **Multiplicative**: $Y_t = T_t \times S_t \times I_t$ (Standard for data where seasonal variation grows with the trend).

#### Value
Initialized `SeasonalAdjuster`.

#### References
N/A

#### Examples
```python
# Example 4: Handling Multiplicative Seasonality
import polars as pl
import numpy as np
from datetime import datetime
from seasonal_adjustment.seasonal_adjustment import SeasonalAdjuster

df = pl.DataFrame({
    "time": pl.date_range(datetime(2020, 1, 1), datetime(2023, 12, 1), interval="1mo", eager=True),
    "volume": [100 * (1.05**i) * (1 + 0.2 * np.sin(2 * np.pi * i / 12)) for i in range(48)]
})

config = {
    "method": "stl",
    "target_vars": ["volume"],
    "time_col": "time",
    "multiplicative": True # Note: STL in this module approximates this via trend+resid
}

adjuster = SeasonalAdjuster(config)
res_df, _ = adjuster.adjust(df)

print(res_df.select(["time", "volume", "volume_sa"]).head())
```

---

### adjust (SeasonalAdjuster)

#### Description
Dispatches the adjustment request to the appropriate decomposition engine.

#### Usage
`adjuster.adjust(df)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | Raw data to adjust. |

#### Details
Calls `_run_x13`, `_run_stl`, or `_run_ml_preprocessor` based on config.

#### Value
A tuple of `(DataFrame, List[DiagnosticsReport])`.

#### References
N/A

#### Examples
```python
# See engine-specific examples below.
```

---

### _run_x13

#### Description
Wraps the US Census Bureau's X-13ARIMA-SEATS algorithm.

#### Usage
`adjuster._run_x13(df, target_vars, time_col)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | Data. |
| `target_vars` | `list` | REQUIRED | Target variables. |
| `time_col` | `str` | REQUIRED | Time column. |

#### Details
It captures M-statistics and Q-statistics for quality assessment.

#### Value
Adjusted DataFrame.

#### References
- US Census Bureau. (2017). *X-13ARIMA-SEATS Reference Manual*.

#### Examples
```python
# Typically invoked via adjust() with method="x13".
```

---

### _run_stl

#### Description
Implements Robust Seasonal-Trend decomposition using Loess. It is highly resistant to outliers and handles non-stationary seasonality.

#### Usage
`adjuster._run_stl(df, target_vars, time_col)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | Data. |
| `target_vars` | `list` | REQUIRED | Target variables. |
| `time_col` | `str` | REQUIRED | Time column. |

#### Details
**STL (Loess) Decomposition**
STL uses iterative local regression to separate the series into Trend ($T_t$), Seasonal ($S_t$), and Irregular ($I_t$) components. The Seasonal Adjustment is calculated as:
$$SA_t = Y_t - S_t$$
For robust estimation, the engine applies biweight weights to downweight residuals that are identified as outliers.

#### Value
Adjusted DataFrame.

#### References
- Cleveland, R. B., Cleveland, W. S., McRae, J. E., & Terpenning, I. (1990). STL: A seasonal-trend decomposition procedure based on loess. *Journal of Official Statistics*, 6(1), 3-73.

#### Examples
```python
# Example 1: Robust STL Decomposition
import polars as pl
import numpy as np
from datetime import datetime, timedelta
from seasonal_adjustment.seasonal_adjustment import SeasonalAdjuster

# Generate synthetic monthly data with a trend and seasonal pattern
dates = [datetime(2020, 1, 1) + timedelta(days=31 * i) for i in range(48)]
trend = np.linspace(100, 200, 48)
seasonal = 20 * np.sin(2 * np.pi * np.arange(48) / 12)
noise = np.random.normal(0, 2, 48)
y = trend + seasonal + noise

df = pl.DataFrame({"time": dates, "revenue": y})

config = {
    "method": "stl",
    "target_vars": ["revenue"],
    "time_col": "time",
    "freq": "M",
    "params": {"robust": True}
}

adjuster = SeasonalAdjuster(config)
res_df, diagnostics = adjuster.adjust(df)

print(res_df.select(["time", "revenue", "revenue_sa"]).head())
print(f"Seasonal Strength: {diagnostics[0].metrics['seasonal_strength']:.4f}")
```

---

### _run_ml_preprocessor

#### Description
Modern deseasonalization using XGBoost.

#### Usage
`adjuster._run_ml_preprocessor(df, target_vars, time_col)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | Data. |
| `target_vars` | `list` | REQUIRED | Target variables. |
| `time_col` | `str` | REQUIRED | Time column. |

#### Details
**ML Deseasonalization with Fourier Terms**
For the `ml` method, the engine constructs a design matrix $X$ containing a trend feature $t$ and seasonal features derived from Fourier series:
$$f_k(t) = \left[ \cos\left(\frac{2\pi k t}{P}\right), \sin\left(\frac{2\pi k t}{P}\right) \right]$$
where $P$ is period (e.g., 12 for monthly data). The model is fitted using a Gradient Boosted Regressor:
$$\hat{Y}_t = \text{XGBoost}(t, \text{calendar\_dummies}, f_k(t))$$
The seasonally adjusted series is obtained by predicting the value with seasonal features set to their neutral state (mean).

#### Value
Adjusted DataFrame.

#### References
N/A

#### Examples
```python
# Example 2: ML Deseasonalization (XGBoost + Fourier)
import polars as pl
from datetime import datetime
from seasonal_adjustment.seasonal_adjustment import SeasonalAdjuster

# Use the same logic as Example 1 but with the 'ml' method
df = pl.DataFrame({
    "time": pl.date_range(datetime(2020, 1, 1), datetime(2023, 12, 1), interval="1mo", eager=True),
    "sales": [100 + 10 * (i % 12) + 2 * i for i in range(48)]
})

config = {
    "method": "ml",
    "target_vars": ["sales"],
    "time_col": "time",
    "fourier_order": 3,
    "params": {"n_estimators": 50, "max_depth": 3}
}

adjuster = SeasonalAdjuster(config)
res_df, _ = adjuster.adjust(df)

print(res_df.select(["time", "sales", "sales_sa"]).tail())
```

---

## 5. Benchmarking & Reconciliation

### TemporalBenchmarker

#### Description
Ensures that high-frequency adjusted data (e.g., monthly) sums up exactly to known low-frequency totals (e.g., annual).

#### Usage
`TemporalBenchmarker(config)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `config` | `dict` | REQUIRED | Contains `target_vars`, `time_col`, `agg_col`. |

#### Details
Initializes benchmarking tools.

#### Value
Initialized `TemporalBenchmarker`.

#### References
N/A

#### Examples
```python
# See benchmark() example below.
```

---

### benchmark (TemporalBenchmarker)

#### Description
Distributes the discrepancy between the sum of the high-frequency series and the low-frequency benchmark.

#### Usage
`benchmarker.benchmark(df, benchmark_df)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | High frequency data. |
| `benchmark_df` | `pl.DataFrame` | REQUIRED | Low frequency benchmark totals. |

#### Details
**Temporal Benchmarking (Cholette-Dagum)**
When constraining high-frequency series $y_t$ to low-frequency benchmarks $z_T$, the engine minimizes a quadratic loss function with an AR(1) error structure:
$$\min (y - x)^T \Omega^{-1} (y - x) \quad \text{subject to} \quad L y = z$$
where $L$ is the aggregation matrix and $\Omega$ represents the AR(1) covariance matrix $\rho^{|i-j|}$.

#### Value
Tuple of `(DataFrame, List[DiagnosticsReport])`.

#### References
N/A

#### Examples
```python
# Example 5: Temporal Benchmarking
import polars as pl
from seasonal_adjustment.temporal_benchmarking import TemporalBenchmarker

df_monthly = pl.DataFrame({
    "time": ["2022-01-01", "2022-02-01", "2022-03-01", "2022-04-01"], # Quarterly agg
    "sales_sa": [10.0, 15.0, 12.0, 14.0],
    "qtr": ["Q1", "Q1", "Q1", "Q2"]
})

df_bench = pl.DataFrame({
    "qtr": ["Q1", "Q2"],
    "sales_benchmark": [40.0, 14.0] # Q1 sum was 37, needs to be bumped to 40
})

benchmarker = TemporalBenchmarker({"target_vars": ["sales_sa"], "time_col": "time", "agg_col": "qtr"})
res_df, _ = benchmarker.benchmark(df_monthly, df_bench)

print(res_df.select(["time", "sales_sa", "sales_sa_benchmarked"]))
```

---

### HierarchicalReconciler

#### Description
Enforces additivity across geographical or industrial hierarchies.

#### Usage
`HierarchicalReconciler(config)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `config` | `dict` | REQUIRED | Configuration dictionary. |

#### Details
Initializes reconciliation tools.

#### Value
Initialized `HierarchicalReconciler`.

#### References
N/A

#### Examples
```python
# See reconcile() example below.
```

---

### reconcile

#### Description
Adjusts bottom-level nodes such that they correctly aggregate to top-level totals.

#### Usage
`reconciler.reconcile(df)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | Unreconciled DataFrame. |

#### Details
**Hierarchical Reconciliation (MinT)**
Given a hierarchy defined by a summing matrix $S$ and bottom-level estimates $\hat{b}$, the reconciled base forecasts $\tilde{y}$ are found by solving:
$$\tilde{y} = S (S^T W S)^{-1} S^T W \hat{y}$$
where $W$ is the inverse of the estimated error covariance matrix.

#### Value
Tuple of `(DataFrame, List[DiagnosticsReport])`.

#### References
N/A

#### Examples
```python
# res_df, diags = reconciler.reconcile(df)
```

---

## 6. Diagnostics & Revisions

### RevisionsTracker

#### Description
Tracks and analyzes the revisions between different vintages (publication dates) of seasonally adjusted data.

#### Usage
`RevisionsTracker()`

#### Arguments
None.

#### Details
Initializes revisions tracking tools.

#### Value
Initialized `RevisionsTracker`.

#### References
N/A

#### Examples
```python
# See compute_revisions() example below.
```

---

### compute_revisions (RevisionsTracker)

#### Description
Calculates mean absolute revisions (MAR) and creates a revision triangle to track estimate stability over time.

#### Usage
`tracker.compute_revisions(current_df, previous_df, target_cols)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `current_df` | `pl.DataFrame` | REQUIRED | Current vintage data. |
| `previous_df` | `pl.DataFrame` | REQUIRED | Previous vintage data. |
| `target_cols` | `list` | REQUIRED | Columns to track. |

#### Details
Extracts stability metrics.

#### Value
Dictionary of revision metrics.

#### References
N/A

#### Examples
```python
# Example 6: Revisions Tracking
import polars as pl
from seasonal_adjustment.revisions import RevisionsTracker

df_prev = pl.DataFrame({"time": ["2023-01-01", "2023-02-01"], "val_sa": [100.0, 110.0]})
df_curr = pl.DataFrame({"time": ["2023-01-01", "2023-02-01"], "val_sa": [102.0, 109.0]})

tracker = RevisionsTracker()
revs = tracker.compute_revisions(df_curr, df_prev, target_cols=["val_sa"])
print(f"Mean Absolute Revision: {revs['val_sa']['mar']:.2f}")
```

---

### calculate_seasonal_impact

#### Description
Evaluates the variance ratio between the raw and adjusted series.

#### Usage
`calculate_seasonal_impact(df_output)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df_output` | `pl.DataFrame` | REQUIRED | DataFrame containing raw and SA values. |

#### Details
Determines how much variance was removed by the seasonal filter.

#### Value
Dictionary containing impact and variance metrics.

#### References
N/A

#### Examples
```python
# impact = calculate_seasonal_impact(df)
```

---

## 7. Persistence

### FactorBank

#### Description
SQLite-backed persistence layer that stores executed models, extracted seasonal factors, and historical data vintages.

#### Usage
`FactorBank(db_path="seasonal_factors.db")`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `db_path` | `str` | `"seasonal_factors.db"` | Path to the database. |

#### Details
Provides methods like `save_vintage`.

#### Value
Initialized `FactorBank`.

#### References
N/A

#### Examples
```python
# db = FactorBank()
# db.save_vintage("2023-10", "revenue", df)
```
