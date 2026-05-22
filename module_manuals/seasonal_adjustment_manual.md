# Module Documentation: seasonal_adjustment

## 1. Module Overview: seasonal_adjustment

The `seasonal_adjustment` module provides a production-grade framework for isolating and removing predictable seasonal and calendar effects from time-series data. It is designed to reveal the underlying economic trend and cycle for official statistics production. The module implements a robust 3-phase pipeline:
1.  **Seasonal Adjustment**: Primary decomposition using classical (X-13ARIMA-SEATS), robust (STL), or modern (Machine Learning) methods.
2.  **Temporal Benchmarking**: Ensuring high-frequency estimates (e.g., monthly) sum to low-frequency benchmarks (e.g., annual totals).
3.  **Hierarchical Reconciliation**: Enforcing consistency across complex geographical or industrial hierarchies.

---

## 2. Core Classes & Initialization

### SeasonalAdjustmentEngine
> The high-level orchestrator for the 3-phase adjustment pipeline.

**Initialization:** `SeasonalAdjustmentEngine(config: SeasonalAdjustmentMetadata, db_path: str = "seasonal_factors.db")`
- **config**: A `SeasonalAdjustmentMetadata` object defining the parameters for all three phases.
- **db_path**: Path to the SQLite factor bank for audit persistence.

### SeasonalAdjuster
> The engine responsible for the primary time-series decomposition.

**Initialization:** `SeasonalAdjuster(config: Dict[str, Any])`
- **config**: A dictionary containing `method` (x13, ml, or stl), `target_vars`, and model-specific parameters.

---

## 3. Core Methods & Functions

### SeasonalAdjustmentEngine.process(df, benchmark_df=None)
Executes the full 3-phase pipeline.
- **Returns**: `SAResult` containing the adjusted data and exhaustive `DiagnosticsReport` objects for each phase.

### SeasonalAdjuster.adjust(df)
Dispatches the adjustment request to the appropriate decomposition engine.
- **Returns**: A tuple of `(DataFrame, List[DiagnosticsReport])`.

### SeasonalAdjuster._run_x13(df, target_vars, time_col)
Wraps the US Census Bureau's X-13ARIMA-SEATS algorithm. It captures M-statistics and Q-statistics for quality assessment.

### SeasonalAdjuster._run_stl(df, target_vars, time_col)
Implements Robust Seasonal-Trend decomposition using Loess. It is highly resistant to outliers and handles non-stationary seasonality.

### SeasonalAdjuster._run_ml_preprocessor(df, target_vars, time_col)
Modern deseasonalization using XGBoost. It models trend and seasonality simultaneously using Fourier terms and calendar dummies.

---

## 4. Details (Methodology & Mathematics)

### Time-Series Decomposition Models
The module supports both additive and multiplicative models:
- **Additive**: $Y_t = T_t + S_t + I_t$ (Standard for data with constant seasonal amplitude).
- **Multiplicative**: $Y_t = T_t \times S_t \times I_t$ (Standard for data where seasonal variation grows with the trend).

### STL (Loess) Decomposition
STL uses iterative local regression to separate the series into Trend ($T_t$), Seasonal ($S_t$), and Irregular ($I_t$) components. The Seasonal Adjustment is calculated as:
$$SA_t = Y_t - S_t$$
For robust estimation, the engine applies biweight weights to downweight residuals that are identified as outliers.

### ML Deseasonalization with Fourier Terms
For the `ml` method, the engine constructs a design matrix $X$ containing a trend feature $t$ and seasonal features derived from Fourier series:
$$f_k(t) = \left[ \cos\left(\frac{2\pi k t}{P}\right), \sin\left(\frac{2\pi k t}{P}\right) \right]$$
where $P$ is the period (e.g., 12 for monthly data). The model is fitted using a Gradient Boosted Regressor:
$$\hat{Y}_t = \text{XGBoost}(t, \text{calendar\_dummies}, f_k(t))$$
The seasonally adjusted series is obtained by predicting the value with seasonal features set to their neutral state (mean).

---

## 5. References

US Census Bureau. (2017). *X-13ARIMA-SEATS Reference Manual*. [https://www.census.gov/data/software/x13as.html](https://www.census.gov/data/software/x13as.html)

Cleveland, R. B., Cleveland, W. S., McRae, J. E., & Terpenning, I. (1990). STL: A seasonal-trend decomposition procedure based on loess. *Journal of Official Statistics*, 6(1), 3-73.

---

## 6. Runnable Examples

### Example 1: Robust STL Decomposition
```python
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

### Example 2: ML Deseasonalization (XGBoost + Fourier)
```python
import polars as pl
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

### Example 3: Full 3-Phase Orchestration
```python
import polars as pl
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

### Example 4: Handling Multiplicative Seasonality
```python
import polars as pl
import numpy as np
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
