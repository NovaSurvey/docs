# Module Documentation: Editing & Outlier Detection

## 1. Module Overview: Editing & Outlier Detection
The `EditingEngine` is a production-grade system designed for national statistical agencies to maintain data quality through automated error localization, robust outlier detection, and impact-based triage. It serves as a defensive gatekeeper in the survey processing pipeline, ensuring that microdata adheres to logical constraints and that extreme values are systematically flagged for examination or imputation.

## 2. Class Initialization (`__init__`)
The `EditingEngine` is initialized with a dataset and a comprehensive metadata object that defines the editing rules and operational parameters.

| Argument | Data Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `data` | `pl.DataFrame` \| `str` | REQUIRED | The input microdata as a Polars DataFrame or a path to a Parquet file. |
| `metadata` | `EditingMetadata` \| `dict` | REQUIRED | Global configuration containing edit groups, outlier settings, and selective editing thresholds. |
| `persist_results` | `bool` | `True` | If true, all run metadata and results are persisted to a SQLite audit trail. |
| `db_path` | `str` | `"editing_audit.db"` | The file path for the SQLite audit database. |
| `edit_tolerance` | `float` | `0.01` | Numerical tolerance for satisfying equality constraints (e.g., balance edits). |

---

## 3. Core Methods & Functions

### Method Signature: `run_edit_localization(df=None)`
Phase 1 & 3: Identifies variables within each record that must be changed to satisfy all edit constraints.

*   **Arguments**:
    *   `df` (`Optional[pl.DataFrame]`): Data to process. Defaults to the data provided at initialization.
*   **Value/Returns**:
    *   `EditingResult`: A structured envelope containing the cleaned DataFrame, an A-E quality grade, and detailed group-level diagnostics.

### Method Signature: `run_outlier_detection_module(df)`
Phase 2: Detects anomalous values using robust statistical methods (HB, Sigma-Gap) or machine learning algorithms.

*   **Arguments**:
    *   `df` (`pl.DataFrame`): The DataFrame to analyze for outliers.
*   **Value/Returns**:
    *   `pl.DataFrame`: The input DataFrame appended with operational flags (`_FTE`, `_FTI`) and diagnostic scores.

### Ontology of Operational Flags
The engine generates several standardized flags to guide downstream processing:
- **`_FTI` (Flag To Impute)**: A boolean indicator that the value failed a "hard" edit or was identified as a critical outlier. This flag serves as the primary trigger for the Imputation Module.
- **`_FTE` (Flag To Examine)**: Indicates an extreme value or a "soft" edit failure. These records are typically staged for manual review by subject-matter experts.
- **`_STATUS`**: A categorical flag (`critical_review`, `auto_edit`, `clean`) generated during the Selective Editing phase to prioritize manual intervention based on impact.

---

## 4. Details (Methodology & Mathematics)

### Error Localization (Fellegi-Holt Principle)
The engine implements the **Fellegi-Holt Principle (1976)**, which minimizes the weighted number of changes required to make a record feasible. This is solved as a **Mixed-Integer Linear Programming (MILP)** problem:

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

### Selective Editing (Score Functions)
Selective Editing is an impact-based triage strategy used to prioritize manual review for the most influential errors. Instead of reviewing every flagged record, the engine calculates a **Global Score** that estimates the potential impact of a record's errors on published aggregates.

$$S_i = \sum_{j \in \text{Variables}} \frac{w_i \cdot |x_{ij} - \hat{x}_{ij}|}{\text{Total}_j}$$

Where:
- $w_i$ is the survey design weight.
- $x_{ij}$ is the reported value.
- $\hat{x}_{ij}$ is the expected value (e.g., historical median or predicted value).
- $\text{Total}_j$ is the estimated total for variable $j$.

**Triage Categories (Stored in `_STATUS`):**
1.  **`critical_review`**: Records that failed edits and have a high impact score. These are routed to human experts.
2.  **`auto_edit`**: Records that failed edits but have low statistical impact. These are processed automatically by the Imputation Module.
3.  **`clean`**: Records that passed all logical constraints.

### Hidiroglou-Berthelot (HB) Outlier Detection
For ratio-based outlier detection, the engine uses the **HB Method (1986)**, which is particularly effective for business surveys. It calculates an $E$-score that accounts for the size of the unit:

1.  **Ratio calculation**: $R_i = \frac{y_{t,i}}{y_{t-1,i}}$
2.  **Transformation**: $S_i = \begin{cases} 1 - \frac{\text{med}(R)}{R_i} & \text{if } 0 < R_i < \text{med}(R) \\ \frac{R_i}{\text{med}(R)} - 1 & \text{if } R_i \ge \text{med}(R) \end{cases}$
3.  **Influence Scoring**: $E_{i} = S_{i} \times \max(y_{i,t}, y_{i, t-1})^{\alpha}$

An observation is flagged if $E_i > \text{med}(E) + C \times DQ$, where $DQ$ is a robust distance based on the quartiles of the $E$-scores.

### Sigma-Gap (MAD-based) Detection
For univariate detection without historical data, the engine employs the **Median Absolute Deviation (MAD)**:

$$\text{MAD} = \text{median}(|x_{i} - \text{median}(X)|)$$
$$\sigma^* = 1.4826 \times \text{MAD}$$

Records are flagged if $|x_i - \text{med}(x)| > K \sigma^*$, where $K$ is a user-defined sensitivity threshold (typically 3.0).

### Isolation Forest (ML)
Isolation Forest is an unsupervised machine learning algorithm that identifies anomalies by isolating observations. It builds an ensemble of random trees; anomalies are isolated closer to the root of the tree (shorter average path lengths) because they require fewer random partitions to be separated.

$$\text{score}(x, n) = 2^{-\frac{E(h(x))}{c(n)}}$$

Where $E(h(x))$ is the average path length of point $x$ and $c(n)$ is the average path length of an unsuccessful search in a Binary Search Tree.

### K-Nearest Neighbors (KNN)
The KNN method flags outliers based on their distance to neighboring points in a multi-dimensional feature space. Points in sparse regions will have significantly larger distances to their $k$-th nearest neighbor or a larger average distance to their $k$ neighbors.

The engine calculates the average distance to the $k$ neighbors for each point and flags those in the top `contamination` percentile.

### Local Outlier Factor (LOF)
LOF is a density-based outlier detection method that identifies anomalies by comparing the local density of a point with the local densities of its $k$ nearest neighbors.
- **Logic**: It identifies points that have a substantially lower density than their neighbors. This is particularly effective for datasets with non-uniform densities, where a "global" distance threshold (like in KNN) might fail to capture outliers in sparse regions.
- **Score**: The score is the average ratio of the local reachability density of the neighbors to the point's own local reachability density. A score significantly greater than 1.0 indicates a density-based outlier.



---

## 5. References
- **Fellegi, I. P., & Holt, D. (1976)**. *A systematic approach to automatic edit and imputation*. Journal of the American Statistical Association, 71(353), 17-35.
- **Hidiroglou, M. A., & Berthelot, J. M. (1986)**. *Statistical editing and imputation for periodic business surveys*. Survey Methodology, 12(1), 73-83.
- **Lawrence, D., & McDavitt, C. (1994)**. *Selective editing and joint imputation*. Australian Bureau of Statistics.
- **Latouche, M., & Berthelot, J. M. (1992)**. *Use of a score function to prioritize and limit re-contacts in editing business surveys*. Journal of Official Statistics, 8(3), 389-400.
- **Liu, F. T., Ting, K. M., & Zhou, Z. H. (2008)**. *Isolation forest*. In 2008 Eighth IEEE International Conference on Data Mining.
- **Ramaswamy, S., Rastogi, R., & Shim, K. (2000)**. *Efficient algorithms for mining outliers from large data sets*. SIGMOD Record, 29(2), 427-438.
- **Breunig, M. M., Kriegel, H. P., Ng, R. T., & Sander, J. (2000)**. *LOF: identifying density-based local outliers*. In Proceedings of the 2000 ACM SIGMOD international conference on Management of data.

---

## 6. Runnable Examples

### Example 1: Hardened Edit Localization
This snippet demonstrates the Fellegi-Holt localization for a balance edit ($Total = Wages + Other$).

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

### Example 2: Selective Editing Triage
This example demonstrates how to prioritize manual review based on the statistical impact of records. High-impact records are flagged for `critical_review`, while low-impact errors are slated for `auto_edit`.

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

### Example 3: Outlier Detection (HB Method)
This snippet demonstrates ratio-based outlier detection with influence scoring.

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

### Example 4: Multivariate Detection (Isolation Forest)
This example demonstrates identifying multivariate anomalies (e.g., unusual expense/income ratios) using machine learning.

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

### Example 5: Proximity-based Detection (KNN)
This example uses KNN to find points that are distant from their neighbors.

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

### Example 6: Density-based Detection (LOF)
This example uses LOF to find an outlier that sits between two dense clusters.

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

### Example 7: End-to-End Editing & Resolution Pipeline
This comprehensive example demonstrates a full data quality pipeline: verifying the consistency of edit rules, running the MILP-based error localization engine, and applying different resolution strategies (Recalculate and Prorate) to fix identified errors.

```python
import polars as pl
from editing.engine import EditingEngine
from editing.resolution import apply_recalculate, apply_prorate

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

### Example 8: Advanced Multi-Method Outlier Comparison
This example provides a comparative analysis of multiple outlier detection methods. It runs HB, Sigma-Gap, Isolation Forest, KNN, and LOF on a dataset, merging the results to allow for a side-by-side comparison of different anomaly detection logic across industry groups.

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
