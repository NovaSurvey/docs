# Module Documentation: publishing

## 1. Module Overview: publishing

The `publishing` module is the final stage of the survey estimation pipeline, responsible for transforming internal statistical results into official-grade public tables. It implements rigorous data quality grading (A-F scale), enforces automated suppression for both confidentiality ('S') and reliability ('F'), and handles mathematical rounding and metadata injection required by national statistical standards. The module ensures that all public-facing data is properly qualified, audit-compliant, and formatted for immediate institutional dissemination.

---

## 2. Core Classes & Initialization

### PublicationEngine
> The primary engine for official table generation and metadata management.

**Initialization:** `PublicationEngine(config: PublishingConfig)`
- **config**: A `PublishingConfig` object defining table metadata, rounding rules (`divide_by_thousands`), and output paths.

### PublishingConfig
> Pydantic model for publication parameters.

- **table_title**: The official title injected into the CSV header.
- **reference_period**: The temporal scope of the data (e.g., "2024-Q1").
- **unit_measure**: The units used for estimates (e.g., "Thousands of Dollars").
- **divide_by_thousands**: Boolean flag to scale estimates by 1,000 before rounding.

---

## 3. Core Methods & Functions

### PublicationEngine.run(df)
The main orchestrator for the publication pipeline.
- **Returns**: `PublishingResult` containing the formatted `polars.DataFrame` and audit-compliant `PublicationDiagnostics`.

### PublicationEngine.apply_quality_grades(df, cv_col, estimate_col)
Translates raw Coefficients of Variation (CVs) into qualitative grades and enforces reliability suppression.
- **Returns**: `polars.DataFrame` with a `Data_Quality_Indicator` column. Estimates and CVs are overwritten with 'F' where quality is too low.

### PublicationEngine.format_for_publication(df, domain_col, estimate_col, cv_col)
Applies rounding and renames columns to match official institutional headers.
- **Returns**: `polars.DataFrame` with human-readable headers (e.g., "Estimate (Thousands of Dollars)").

### PublicationEngine.export_to_csv(df, filepath)
Exports the result to a CSV file with an injected multi-line metadata header.
- **Output**: A UTF-8 encoded CSV file with institutional metadata at the top.

---

## 4. Details (Methodology & Mathematics)

### Quality Grading Matrix
The engine assigns alphabetical quality grades based on the Coefficient of Variation ($CV$) of the estimate. If the $CV$ exceeds the reliability threshold, the data is suppressed to prevent misuse.

| CV Range (%) | Quality Grade | Action |
| :--- | :--- | :--- |
| $CV < 5.0$ | **A** | Excellent |
| $5.0 \leq CV < 15.0$ | **B** | Very Good |
| $15.0 \leq CV < 25.0$ | **C** | Good |
| $25.0 \leq CV \leq 35.0$ | **E** | Use with caution |
| $CV > 35.0$ | **F** | Suppressed (Reliability) |
| *Manual Flag* | **S** | Suppressed (Confidentiality) |

### Suppression Propagation
If an estimate is flagged as **S** (Confidentiality) or **F** (Reliability), the suppression propagates across both the Estimate and CV columns to ensure no numerical values are leaked:
$$\text{Estimate}_{pub} = \begin{cases} \text{'S'} & \text{if Grade is 'S'} \\ \text{'F'} & \text{if Grade is 'F'} \\ \text{Round}(\text{Estimate}) & \text{otherwise} \end{cases}$$

### Rounding Mathematics
Rounding is applied after scaling. If `divide_by_thousands` is enabled:
- **Estimate**: $\text{Value}_{pub} = \text{Round}\left(\frac{\text{Value}_{raw}}{1000}, 0\right)$
- **CV**: $\text{CV}_{pub} = \text{Round}(\text{CV}_{raw}, 1)$

---

## 5. References

Statistics Canada. (2009). *Statistics Canada Quality Guidelines*. Fifth Edition. Catalogue no. 12-539-X.

US Census Bureau. (2024). *Statistical Quality Standards*. [https://www.census.gov/about/policies/quality/standards.html](https://www.census.gov/about/policies/quality/standards.html)

---

## 6. Runnable Examples

### Example 1: Quality Grading and S/F Suppression
```python
import polars as pl
from publishing.engine import PublicationEngine
from publishing.models import PublishingConfig

df = pl.DataFrame({
    "domain": ["Region A", "Region B", "Region C", "Region D"],
    "total": ["1000000", "2000000", "S", "500000"],
    "cv": ["4.2", "38.5", "S", "12.0"]
})

config = PublishingConfig(reference_period="2024-01")
engine = PublicationEngine(config)

# Apply grades (demonstrating F-suppression for Region B and S propagation for Region C)
df_graded = engine.apply_quality_grades(df, cv_col="cv", estimate_col="total")

print(df_graded.select(["domain", "total", "cv", "Data_Quality_Indicator"]))
```

### Example 2: Official Formatting and Rounding
```python
import polars as pl
from publishing.engine import PublicationEngine
from publishing.models import PublishingConfig

df = pl.DataFrame({
    "area": ["North", "South"],
    "val": [1234567.89, 987654.32],
    "cv_raw": [2.45, 14.99],
    "Data_Quality_Indicator": ["A", "B"]
})

config = PublishingConfig(
    reference_period="2024-M01",
    unit_measure="Thousands of Dollars",
    divide_by_thousands=True
)

engine = PublicationEngine(config)
df_pub = engine.format_for_publication(df, domain_col="area", estimate_col="val", cv_col="cv_raw")

print(df_pub)
```

### Example 3: Full Publication Run with Audit Log
```python
import polars as pl
import os
from publishing.engine import PublicationEngine
from publishing.models import PublishingConfig

df = pl.DataFrame({
    "domain": ["Total Sector"],
    "estimate": [5432100],
    "cv_percent": [3.1]
})

config = PublishingConfig(
    table_title="Monthly Revenue Report",
    reference_period="2024-05",
    output_csv_path="official_table.csv",
    persist_results=False
)

engine = PublicationEngine(config)
result = engine.run(df)

print(f"Publication Status: {result.diagnostics.status}")
print(f"Table Title: {result.diagnostics.table_title}")
print(result.data)

# Cleanup
if os.path.exists("official_table.csv"): os.remove("official_table.csv")
```
