# Module Documentation: Editing & Outlier Detection

## 1. Module Overview
The `EditingEngine` is a production-grade system designed for national statistical agencies to maintain data quality through automated error localization, robust outlier detection, and impact-based triage. It serves as a defensive gatekeeper in the survey processing pipeline, ensuring that microdata adheres to logical constraints and that extreme values are systematically flagged for examination or imputation.

## 2. Table of Contents
- [3. Engine Orchestration](#3-engine-orchestration)
- [4. Error Localization](#4-error-localization)
- [5. Outlier Detection](#5-outlier-detection)
- [6. Selective Editing & Triage](#6-selective-editing--triage)
- [7. Edit Verification](#7-edit-verification)
- [8. Resolution Methods](#8-resolution-methods)
- [9. Persistence & Quality](#9-persistence--quality)

---

## 3. Engine Orchestration

### EditingEngine

#### Description
The main entry point and orchestrator for the editing and imputation process.

#### Usage
`EditingEngine(data, metadata, persist_results=True, db_path="editing_audit.db", edit_tolerance=0.01)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `data` | `pl.DataFrame` \| `str` | REQUIRED | The input microdata as a Polars DataFrame or a path to a Parquet file. |
| `metadata` | `EditingMetadata` \| `dict` | REQUIRED | Global configuration containing edit groups, outlier settings, and selective editing thresholds. |
| `persist_results` | `bool` | `True` | If true, all run metadata and results are persisted to a SQLite audit trail. |
| `db_path` | `str` | `"editing_audit.db"` | The file path for the SQLite audit database. |
| `edit_tolerance` | `float` | `0.01` | Numerical tolerance for satisfying equality constraints. |

#### Details
The `EditingEngine` coordinates calls to `ErrorLocalizer`, `OutlierDetector`, and `SelectiveEditing`.

#### Value
An initialized `EditingEngine` instance.

#### References
N/A

#### Examples
```python
import polars as pl
from editing.engine import EditingEngine

# Initialization Example
df = pl.DataFrame({"id": [1]})
metadata = {"edit_groups": {}}
engine = EditingEngine(df, metadata)
```

---

### run_edit_localization

#### Description
Phase 1 & 3: Identifies variables within each record that must be changed to satisfy all edit constraints.

#### Usage
`engine.run_edit_localization(df=None)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `Optional[pl.DataFrame]` | `None` | Data to process. Defaults to the data provided at initialization. |

#### Details
This method leverages the **Fellegi-Holt Principle (1976)**, which minimizes the weighted number of changes required to make a record feasible. This is solved as a **Mixed-Integer Linear Programming (MILP)** problem:

$$\min_{y} \sum_{i=1}^{n} w_i y_i$$

Subject to the feasibility constraints:
1.  **Edit Constraints**: $A_{eq} x' = b_{eq}$ and $A_{le} x' \le b_{le}$
2.  **Big-M Logical Link**: $|x_{i}^{new} - x_{i}^{orig}| \le M \cdot y_{i}$

Where:
- $x_i$ is the original value of variable $i$.
- $x'_i$ is the new, potentially changed value.
- $y_i \in \{0, 1\}$ is a binary variable indicating if variable $i$ is changed.
- $w_i$ is the reliability weight (higher weights make the variable less likely to be localized).
- $M$ is a sufficiently large constant (Big-M) used to linearize the relationship between $x'$ and $y$.

#### Value
Returns an `EditingResult` object.

#### References
- **Fellegi, I. P., & Holt, D. (1976)**. *A systematic approach to automatic edit and imputation*. Journal of the American Statistical Association, 71(353), 17-35.

#### Examples
```python
import polars as pl
import numpy as np
from editing.engine import EditingEngine

# Generate synthetic data with 1 failing record
df = pl.DataFrame({
    "id": [1, 2, 3],
    "total": [100, 200, 500], # ID 3 fails: 300+100 != 500
    "wages": [70, 150, 300],
    "other": [30, 50, 100]
})

metadata = {
    "edit_groups": {
        "main": {
            "variables": ["total", "wages", "other"],
            "edits": ["total == wages + other"],
            "reliability_weights": {"total": 2.0, "wages": 1.0, "other": 1.0}
        }
    },
    "persist_results": False
}

engine = EditingEngine(df, metadata)
result = engine.run_edit_localization()

print("--- Edit Localization Results ---")
print(result.data.select(["id", "total_FTI", "wages_FTI", "other_FTI"]))
```

---

### run_outlier_detection_module

#### Description
Phase 2: Detects anomalous values using robust statistical methods or machine learning algorithms based on the provided configuration.

#### Usage
`engine.run_outlier_detection_module(df)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | The DataFrame to analyze for outliers. |

#### Details
Coordinates `OutlierDetector` runs. It processes multiple configuration blocks in series (e.g., HB, Sigma-Gap, Isolation Forest). 

The engine generates several standardized flags:
- **`_FTI` (Flag To Impute)**: A boolean indicator that the value failed a "hard" edit or was a critical outlier.
- **`_FTE` (Flag To Examine)**: Indicates an extreme value or a "soft" edit failure to be staged for manual review.

#### Value
Returns a `pl.DataFrame`.

#### References
N/A

#### Examples
```python
# df_results = engine.run_outlier_detection_module(df)
```

---

## 4. Error Localization

### ErrorLocalizer

#### Description
Implements the Fellegi-Holt algorithm for finding the minimal set of fields to change.

#### Usage
`ErrorLocalizer(A_eq, b_eq, A_le, b_le, variables, tolerance=0.01)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `A_eq`, `b_eq` | `np.ndarray` | REQUIRED | Matrix representations for equality edits. |
| `A_le`, `b_le` | `np.ndarray` | REQUIRED | Matrix representations for less-than-or-equal-to edits. |
| `variables` | `list` | REQUIRED | List of variable names involved in edits. |
| `tolerance` | `float` | `0.01` | Numerical tolerance. |

#### Details
Constructs the Mixed-Integer Linear Programming state for the edits.

#### Value
Initialized `ErrorLocalizer` object.

#### References
N/A

#### Examples
```python
# localizer = ErrorLocalizer(A_eq, b_eq, A_le, b_le, ["a", "b"])
```

---

### is_feasible

#### Description
Checks if a single record passes all logic edits.

#### Usage
`localizer.is_feasible(record)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `record` | `list` \| `np.ndarray` | REQUIRED | The numeric values of the record matching the variables. |

#### Details
Checks equality and inequality matrices. None or NaN values immediately return False.

#### Value
`bool`: True if the record passes, False otherwise.

#### References
N/A

#### Examples
```python
# status = localizer.is_feasible([10, 20, 30])
```

---

### localize_errors

#### Description
Uses MILP optimization to find the minimum weighted number of variables to impute for a specific record.

#### Usage
`localizer.localize_errors(record, weights=None)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `record` | `list` \| `np.ndarray` | REQUIRED | The numeric values of the record. |
| `weights` | `np.ndarray` | `None` | The reliability weights for each variable. |

#### Details
Uses Scipy's MILP solver with Big-M formulations to identify variables.

#### Value
`list`: A list of variable names that should be imputed.

#### References
N/A

#### Examples
```python
# fields_to_impute = localizer.localize_errors([10, 20, 50], weights=[1, 1, 2])
```

---

### run_error_localization

#### Description
Vectorized wrapper for executing error localization across a full DataFrame.

#### Usage
`run_error_localization(df, spec, weights=None, tolerance=0.01)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | The DataFrame to process. |
| `spec` | `EditSpecification` | REQUIRED | The edit specification object containing matrices. |
| `weights` | `dict` \| `np.ndarray` | `None` | Reliability weights. |
| `tolerance` | `float` | `0.01` | Numerical tolerance. |

#### Details
Identifies failing records first via vectorized mask to save MILP computation time, then applies localization.

#### Value
`pl.DataFrame`: The DataFrame with appended `_FTI` flags.

#### References
N/A

#### Examples
```python
# df_flagged = run_error_localization(df, spec)
```

---

## 5. Outlier Detection

### OutlierDetector

#### Description
Provides robust statistical and ML-based anomaly detection methods.

#### Usage
`OutlierDetector(df)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | The input DataFrame. |

#### Details
Wrapper class holding the state DataFrame for sequential processing.

#### Value
Initialized `OutlierDetector` object.

#### References
N/A

#### Examples
```python
import polars as pl
from editing.outlier import OutlierDetector

# Generate synthetic data with clusters and anomalies
df = pl.DataFrame({
    "id": range(100),
    "industry_group": ["Tech"] * 50 + ["Retail"] * 50,
    "revenue": [100] * 98 + [1000, 5], # Two outliers
    "revenue_prev": [95] * 100,
    "w_design": [1.0] * 100
})

# Run Multiple Methods
detector = OutlierDetector(df)

# 1. HB Method (Ratio-based)
df_hb = detector.hb_method(column="revenue", prev_column="revenue_prev", group_var="industry_group")
df_hb = df_hb.select(["id", "revenue_FTI"]).rename({"revenue_FTI": "hb_flag"})

# 2. Sigma-Gap (Univariate)
df_sg = detector.sigma_gap_method(column="revenue", group_var="industry_group")
df_sg = df_sg.select(["id", "revenue_FTI"]).rename({"revenue_FTI": "sigma_flag"})

# 3. Isolation Forest (ML Multivariate)
df_if = detector.isolation_forest_method(columns=["revenue", "revenue_prev"], contamination=0.05)
df_if = df_if.select(["id", "revenue_FTI"]).rename({"revenue_FTI": "iforest_flag"})

# Merge for comparison
df_comparison = df.join(df_hb, on="id").join(df_sg, on="id").join(df_if, on="id")
print("\n--- Outlier Method Comparison (Anomalies) ---")
print(df_comparison.filter(pl.col("hb_flag") | pl.col("sigma_flag") | pl.col("iforest_flag")))
```

---

### hb_method

#### Description
Uses the Hidiroglou-Berthelot (HB) method for longitudinal ratio comparisons.

#### Usage
`detector.hb_method(column, prev_column, alpha=0.5, ci=3.0, ce=5.0, group_var=None, weight_var=None, critical_threshold=None, pct=0.25, A=0.05)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `column` | `str` | REQUIRED | The current period variable. |
| `prev_column` | `str` | REQUIRED | The previous period variable. |
| `alpha` | `float` | `0.5` | Size penalty parameter. |
| `ci` | `float` | `3.0` | Confidence interval multiplier (FTI). |
| `ce` | `float` | `5.0` | Confidence interval multiplier (FTE). |
| `group_var` | `str` | `None` | Optional grouping variable. |

#### Details
**Hidiroglou-Berthelot (HB) Outlier Detection**
For ratio-based outlier detection, the engine uses the HB Method (1986), which calculates an $E$-score that accounts for the size of the unit:

1.  **Ratio calculation**: $R_i = \frac{y_{t,i}}{y_{t-1,i}}$
2.  **Transformation**: $S_i = \begin{cases} 1 - \frac{\text{med}(R)}{R_i} & \text{if } 0 < R_i < \text{med}(R) \\ \frac{R_i}{\text{med}(R)} - 1 & \text{if } R_i \ge \text{med}(R) \end{cases}$
3.  **Influence Scoring**: $E_{i} = S_{i} \times \max(y_{i,t}, y_{i, t-1})^{\alpha}$

An observation is flagged if $E_i > \text{med}(E) + C \times DQ$, where $DQ$ is a robust distance based on the quartiles of the $E$-scores.

#### Value
Returns the updated DataFrame with `_FTE` and `_FTI` flags for the analyzed column.

#### References
- **Hidiroglou, M. A., & Berthelot, J. M. (1986)**. *Statistical editing and imputation for periodic business surveys*. Survey Methodology, 12(1), 73-83.

#### Examples
```python
import polars as pl
import numpy as np
from editing.engine import EditingEngine

# Generate synthetic longitudinal data
n = 100
prev_revenue = np.random.uniform(100, 200, n)
curr_revenue = prev_revenue * 1.05 # 5% growth
curr_revenue[0] *= 10 # Massive outlier

df = pl.DataFrame({
    "id": range(n),
    "rev_t": curr_revenue,
    "rev_t_minus_1": prev_revenue
})

metadata = {
    "edit_groups": {},
    "outlier_config": [{
        "variable": "rev_t",
        "method": "hb",
        "prev_column": "rev_t_minus_1",
        "alpha": 0.5,
        "ci": 3.0
    }]
}

engine = EditingEngine(df, metadata)
df_outliers = engine.run_outlier_detection_module(df)

print("\n--- Outlier Detection Results (First 5) ---")
print(df_outliers.select(["id", "rev_t", "rev_t_FTE", "rev_t_FTI"]).head(5))
```

---

### sigma_gap_method

#### Description
Uses MAD-based sigma gap for univariate distributions.

#### Usage
`detector.sigma_gap_method(column, threshold=3.0, group_var=None)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `column` | `str` | REQUIRED | The variable to check. |
| `threshold` | `float` | `3.0` | Sensitivity multiplier for sigma. |
| `group_var` | `str` | `None` | Optional grouping variable. |

#### Details
**Sigma-Gap (MAD-based) Detection**
For univariate detection without historical data, the engine employs the **Median Absolute Deviation (MAD)**:

$$\text{MAD} = \text{median}(|x_{i} - \text{median}(X)|)$$
$$\sigma^* = 1.4826 \times \text{MAD}$$

Records are flagged if $|x_i - \text{med}(x)| > K \sigma^*$, where $K$ is a user-defined sensitivity threshold (typically 3.0).

#### Value
Returns the updated DataFrame with `_FTE` and `_FTI` flags for the analyzed column.

#### References
N/A

#### Examples
```python
# df = detector.sigma_gap_method("revenue", threshold=3.0, group_var="industry")
```

---

### isolation_forest_method

#### Description
Unsupervised anomaly detection via Isolation Forests.

#### Usage
`detector.isolation_forest_method(columns, contamination=0.05, group_var=None, random_state=42)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `columns` | `list` | REQUIRED | List of columns to check multivariate anomalies. |
| `contamination` | `float` | `0.05` | Expected proportion of outliers. |
| `group_var` | `str` | `None` | Optional grouping variable. |
| `random_state` | `int` | `42` | Seed. |

#### Details
**Isolation Forest (ML)**
Isolation Forest builds an ensemble of random trees; anomalies are isolated closer to the root of the tree (shorter average path lengths) because they require fewer partitions.

$$\text{score}(x, n) = 2^{-\frac{E(h(x))}{c(n)}}$$

Where $E(h(x))$ is the average path length of point $x$ and $c(n)$ is the average path length of an unsuccessful search in a Binary Search Tree.

#### Value
Returns the updated DataFrame with `_FTE`, `_FTI`, and `_if_score` flags.

#### References
- **Liu, F. T., Ting, K. M., & Zhou, Z. H. (2008)**. *Isolation forest*. In 2008 Eighth IEEE International Conference on Data Mining.

#### Examples
```python
import polars as pl
from editing.engine import EditingEngine

# Data with multi-variate anomalies
df = pl.DataFrame({
    "id": range(100),
    "income": [50000] * 99 + [50000],
    "expense": [30000] * 99 + [800000] # High expense relative to income
})

metadata = {
    "edit_groups": {},
    "outlier_config": [{
        "variable": ["income", "expense"],
        "method": "iforest",
        "contamination": 0.05
    }]
}

engine = EditingEngine(df, metadata)
df_results = engine.run_outlier_detection_module(df)

print("\n--- Isolation Forest Results (Anomalies) ---")
print(df_results.filter(pl.col("expense_FTI")).select(["id", "income", "expense"]))
```

---

### knn_method

#### Description
Proximity-based detection using K-Nearest Neighbors.

#### Usage
`detector.knn_method(columns, k=5, contamination=0.05, group_var=None)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `columns` | `list` | REQUIRED | List of columns. |
| `k` | `int` | `5` | Number of nearest neighbors. |
| `contamination` | `float` | `0.05` | Expected proportion of outliers. |
| `group_var` | `str` | `None` | Optional grouping variable. |

#### Details
**K-Nearest Neighbors (KNN)**
The KNN method flags outliers based on their distance to neighboring points in a multi-dimensional feature space. Points in sparse regions will have significantly larger distances to their $k$-th nearest neighbor. The engine calculates the average distance to the $k$ neighbors for each point and flags those in the top `contamination` percentile.

#### Value
Returns the updated DataFrame with `_FTE`, `_FTI`, and `_knn_score` flags.

#### References
- **Ramaswamy, S., Rastogi, R., & Shim, K. (2000)**. *Efficient algorithms for mining outliers from large data sets*. SIGMOD Record, 29(2), 427-438.

#### Examples
```python
import polars as pl
from editing.engine import EditingEngine

df = pl.DataFrame({
    "id": range(50),
    "val": list(range(49)) + [1000] # 1000 is an outlier
})

metadata = {
    "edit_groups": {},
    "outlier_config": [{
        "variable": "val",
        "method": "knn",
        "k": 5,
        "contamination": 0.1
    }]
}

engine = EditingEngine(df, metadata)
df_results = engine.run_outlier_detection_module(df)

print("\n--- KNN Detection Results (Tail) ---")
print(df_results.tail(5).select(["id", "val", "val_FTI"]))
```

---

### lof_method

#### Description
Density-based Local Outlier Factor detection.

#### Usage
`detector.lof_method(columns, n_neighbors=20, contamination=0.05, group_var=None)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `columns` | `list` | REQUIRED | List of columns. |
| `n_neighbors` | `int` | `20` | Number of neighbors for local density calculation. |
| `contamination` | `float` | `0.05` | Expected proportion of outliers. |
| `group_var` | `str` | `None` | Optional grouping variable. |

#### Details
**Local Outlier Factor (LOF)**
LOF is a density-based outlier detection method that identifies anomalies by comparing the local density of a point with the local densities of its $k$ nearest neighbors.
- **Logic**: It identifies points that have a substantially lower density than their neighbors.
- **Score**: The score is the average ratio of the local reachability density of the neighbors to the point's own local reachability density. A score significantly greater than 1.0 indicates a density-based outlier.

#### Value
Returns the updated DataFrame with `_FTE`, `_FTI`, and `_lof_score` flags.

#### References
- **Breunig, M. M., Kriegel, H. P., Ng, R. T., & Sander, J. (2000)**. *LOF: identifying density-based local outliers*.

#### Examples
```python
import polars as pl
from editing.engine import EditingEngine

# Data with a density-based outlier (5.0 is between clusters at 1.0 and 10.0)
df = pl.DataFrame({
    "id": range(101),
    "x": [1.0] * 50 + [10.0] * 50 + [5.0],
    "y": [1.0] * 50 + [10.0] * 50 + [5.0]
})

metadata = {
    "edit_groups": {},
    "outlier_config": [{
        "variable": ["x", "y"],
        "method": "lof",
        "n_neighbors": 20,
        "contamination": 0.02
    }]
}

engine = EditingEngine(df, metadata)
df_results = engine.run_outlier_detection_module(df)

print("\n--- LOF Results (Identifying the Middle Point) ---")
print(df_results.filter(pl.col("x_FTI")).select(["id", "x", "y"]))
```

---

## 6. Selective Editing & Triage

### SelectiveEditing

#### Description
Calculates impact scores to triage records for manual review or automatic imputation.

#### Usage
`SelectiveEditing(df, variables, weight_col=None)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | Input DataFrame. |
| `variables` | `list` | REQUIRED | List of variables to monitor. |
| `weight_col` | `str` | `None` | Optional column name for survey weights. |

#### Details
Selective Editing is an impact-based triage strategy used to prioritize manual review for the most influential errors. Instead of reviewing every flagged record, the engine calculates a **Global Score** that estimates the potential impact of a record's errors on published aggregates.

$$S_i = \sum_{j \in \text{Variables}} \frac{w_i \cdot |x_{ij} - \hat{x}_{ij}|}{\text{Total}_j}$$

Where:
- $w_i$ is the survey design weight.
- $x_{ij}$ is the reported value.
- $\hat{x}_{ij}$ is the expected value (e.g., historical median or predicted value).
- $\text{Total}_j$ is the estimated total for variable $j$.

#### Value
`SelectiveEditing` object.

#### References
- **Lawrence, D., & McDavitt, C. (1994)**. *Selective editing and joint imputation*. Australian Bureau of Statistics.
- **Latouche, M., & Berthelot, J. M. (1992)**. *Use of a score function to prioritize and limit re-contacts in editing business surveys*. Journal of Official Statistics, 8(3), 389-400.

#### Examples
```python
import polars as pl
from editing.engine import EditingEngine

# Create data: ID 2 has a high weight and a large error
df = pl.DataFrame({
    "id": [1, 2, 3],
    "revenue": [100, 1000, 105], 
    "sales": [60, 600, 60],
    "other": [40, 400, 40],
    "weight": [1.0, 10.0, 1.0] 
})

# Induce errors in all records (revenue != sales + other)
df = df.with_columns(pl.col("revenue") + 5)

metadata = {
    "edit_groups": {
        "main": {
            "variables": ["revenue", "sales", "other"],
            "edits": ["revenue == sales + other"]
        }
    },
    "selective_config": {
        "threshold": 0.2, # Sensitivity for manual review
        "weight_col": "weight"
    }
}

engine = EditingEngine(df, metadata)
result = engine.run_edit_localization()

print("\n--- Selective Editing Triage Results ---")
print(result.data.select(["id", "revenue", "weight", "main_STATUS"]))
```

---

### calculate_scores

#### Description
Calculates the global and local impact scores for records.

#### Usage
`se.calculate_scores()`

#### Arguments
None.

#### Details
Applies the score functions to the variables.

#### Value
Updates internal structures with `_global_score`.

#### References
N/A

#### Examples
```python
# se.calculate_scores()
```

---

### classify

#### Description
Categorizes records into `critical_review`, `auto_edit`, or `clean` based on thresholds.

#### Usage
`se.classify(threshold, failed_edit_mask=None)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `threshold` | `float` | REQUIRED | The threshold above which records are critical. |
| `failed_edit_mask` | `pl.Series` | `None` | A boolean mask of records that failed edits. |

#### Details
**Triage Categories (Stored in `_STATUS`):**
1.  **`critical_review`**: Records that failed edits and have a high impact score. These are routed to human experts.
2.  **`auto_edit`**: Records that failed edits but have low statistical impact. These are processed automatically by the Imputation Module.
3.  **`clean`**: Records that passed all logical constraints.

#### Value
`pl.DataFrame` with appended `_STATUS` column.

#### References
N/A

#### Examples
```python
# df_triaged = se.classify(threshold=0.2, failed_edit_mask=failures)
```

---

## 7. Edit Verification

### EditVerifier

#### Description
Parses string-based logical edits into matrix representations and verifies systematic consistency.

#### Usage
`EditVerifier(variables)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `variables` | `list` | REQUIRED | List of variables expected in edits. |

#### Details
Methods include `add_edit(edit_str)`, `get_matrices()`, and `check_consistency()`.

#### Value
`EditVerifier` object.

#### References
N/A

#### Examples
```python
# verifier = EditVerifier(["sales", "expenses"])
```

---

## 8. Resolution Methods

### apply_recalculate

#### Description
Recalculates a total variable as the sum of its components.

#### Usage
`apply_recalculate(df, total_var, component_vars, id_col="id", target_ids=None)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | Input DataFrame. |
| `total_var` | `str` | REQUIRED | The aggregate variable to replace. |
| `component_vars` | `list` | REQUIRED | List of component variable names. |
| `id_col` | `str` | `"id"` | The ID column name. |
| `target_ids` | `list` | `None` | The specific IDs to apply the change to. |

#### Details
Forces `Total_Final = Sum(Component_Vars)`. Preserves raw data in `_RAW` columns.

#### Value
`pl.DataFrame` with resolved values and `resolution_status` = "Recalculated".

#### References
N/A

#### Examples
```python
import polars as pl
from editing.engine import EditingEngine
from editing.resolution import apply_recalculate

# 1. Load Data
df = pl.DataFrame({
    "id": [1, 2, 3],
    "sales": [100, 200, 300],
    "pay": [50, 60, 100],
    "revenue": [150, 260, 500] # ID 3 fails: 300 + 100 != 500
})

metadata = {
    "edit_groups": {
        "main": {
            "variables": ["sales", "pay", "revenue"],
            "edits": ["sales + pay == revenue"]
        }
    }
}

# 2. Run Localization
engine = EditingEngine(df, metadata)
result = engine.run_edit_localization()
failed_ids = result.data.filter(pl.any_horizontal(pl.col("^.*_FTI$")))["id"].to_list()

# 3. Apply Resolutions
# Apply 'Recalculate' to the first half of failures
recalc_ids = failed_ids[:len(failed_ids)//2 + 1]
resolved_df = apply_recalculate(result.data, "revenue", ["sales", "pay"], target_ids=recalc_ids)

print("\n--- Resolved Data ---")
print(resolved_df.select(["id", "sales", "pay", "revenue", "resolution_status"]))
```

---

### apply_prorate

#### Description
Proportionally distributes a known total across component variables to resolve discrepancies.

#### Usage
`apply_prorate(df, total_var, component_vars, id_col="id", target_ids=None)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | Input DataFrame. |
| `total_var` | `str` | REQUIRED | The assumed true aggregate variable. |
| `component_vars` | `list` | REQUIRED | List of component variables to scale. |
| `id_col` | `str` | `"id"` | The ID column name. |
| `target_ids` | `list` | `None` | The specific IDs to apply the change to. |

#### Details
Applies ratio: `Component_Final = Total_Reported * (Component / Sum(Components))`.

#### Value
`pl.DataFrame` with resolved values and `resolution_status` = "Prorated".

#### References
N/A

#### Examples
```python
# df_resolved = apply_prorate(df, "revenue", ["sales", "pay"], target_ids=[3])
```

---

### calculate_divergence

#### Description
Returns the numerical difference between a total and the sum of its components.

#### Usage
`calculate_divergence(df, total_var, component_vars)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | Input DataFrame. |
| `total_var` | `str` | REQUIRED | The aggregate variable. |
| `component_vars` | `list` | REQUIRED | List of component variables. |

#### Details
Calculates `calculated_total` and `divergence_pct`.

#### Value
`pl.DataFrame` with the divergence columns appended.

#### References
N/A

#### Examples
```python
# df_div = calculate_divergence(df, "revenue", ["sales", "pay"])
```

---

## 9. Persistence & Quality

### AuditDatabase

#### Description
Handles the persistence of operational flags and metrics to an SQLite database.

#### Usage
`AuditDatabase(db_path="editing_audit.db")`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `db_path` | `str` | `"editing_audit.db"` | Path to the SQLite db file. |

#### Details
Creates necessary tables if they do not exist and logs run metadata.

#### Value
`AuditDatabase` object.

#### References
N/A

#### Examples
```python
# db = AuditDatabase()
```

---

### QualityDeclaration

#### Description
Generates standardized quality reports based on editing results.

#### Usage
`QualityDeclaration.generate_markdown_report(result)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `result` | `EditingResult` | REQUIRED | The result object from the engine. |

#### Details
Calculates quality metrics, scores, and produces a human-readable markdown breakdown.

#### Value
`str`: A markdown string.

#### References
N/A

#### Examples
```python
# md_report = QualityDeclaration.generate_markdown_report(result)
```
