# Module Documentation: ingestion

## 1. Module Overview: ingestion

The `ingestion` module serves as the production-grade "front door" for all survey data entering the estimation pipeline. It enforces a strict, type-safe contract between the raw data files and the downstream statistical modules using **Pydantic** for schema definition and **Polars** for high-performance lazy evaluation. The module automatically performs integrity checks (duplicate IDs, negative weights), generates audit-compliant SHA-256 file hashes, and produces an automated **A-F Quality Certification** based on missingness and sparsity metrics.

---

## 2. Core Classes & Initialization

### SurveyDataContract
> A Pydantic model that defines the metadata and schema requirements for a specific survey dataset.

**Initialization:** `SurveyDataContract(...)`
- **dataset_name**: Unique identifier for the survey.
- **unit_id_col**: Column name for unique identifiers.
- **continuous_targets**: List of columns expected to be continuous numeric variables.
- **domain_cols**: List of columns used for domain-level estimation.

### IngestionEngine
> Orchestrates the reading, validation, and auditing of survey files.

**Initialization:** `IngestionEngine(contract: SurveyDataContract, db_path: str = "ingestion_audit.db")`
- **contract**: The `SurveyDataContract` to enforce.
- **db_path**: Path to the SQLite database where ingestion audit records are persisted.

---

## 3. Core Methods & Functions

### IngestionEngine.ingest_file(file_path)
The main orchestration method for data ingestion.
- **Returns**: `IngestionResult` containing the collected `polars.DataFrame`, a `quality` summary (A-F grade), and any fatal errors or warnings.

### IngestionEngine._enforce_schema(lf)
Applies strict type casting to the incoming data stream.
- **Returns**: `polars.LazyFrame` with columns cast to `Utf8` for IDs/Domains and `Float64` for targets/weights.

### IngestionQualityAssurer.certify(df)
Performs statistical profiling of the ingested data.
- **Returns**: `IngestionQualitySummary` including the final quality score (0-100), grade (A-F), and specific reasons for score deductions.

### IngestionAuditStore.save_run(record)
Persists the ingestion metadata to the audit database.
- **Fields**: `run_id`, `file_hash`, `row_count`, `quality_grade`, etc.

---

## 4. Details (Methodology & Mathematics)

### Quality Scoring Matrix
The automated quality score $S \in [0, 100]$ is calculated using a weighted penalty system:
$$S = 100 - (1.5 \cdot \bar{M}) - (0.5 \cdot \max(0, \bar{Z} - 20)) - \min(10, 0.1 \cdot C_{out})$$
Where:
- $\bar{M}$: Average percentage of missing values across all target variables.
- $\bar{Z}$: Average percentage of zero values (sparsity) across target variables.
- $C_{out}$: Count of detected univariate outliers (using a $4\sigma$ threshold).

**Grading Scale:**
- **A**: $S \geq 90$
- **B**: $S \geq 80$
- **C**: $S \geq 70$
- **D**: $S \geq 60$
- **F**: $S < 60$ (Uncertified)

### Audit Hash Generation
To ensure end-to-end reproducibility, the engine calculates a SHA-256 hash of every ingested file. This hash is stored in the `ingestion_audit.db` and used to verify that the data has not been modified between processing steps or across different pipeline runs.

---

## 5. References

International Organization for Standardization. (2014). *ISO 8000: Data Quality*.

Polars Development Team. (2024). *Lazy API and Schema Enforcement*. [https://docs.pola.rs/user-guide/concepts/lazy-vs-eager/](https://docs.pola.rs/user-guide/concepts/lazy-vs-eager/)

Pydantic Contributors. (2024). *Data Validation and Settings Management*. [https://docs.pydantic.dev/](https://docs.pydantic.dev/)

---

## 6. Runnable Examples

### Example 1: Defining a Survey Data Contract
```python
from ingestion.models import SurveyDataContract

contract = SurveyDataContract(
    dataset_name="MonthlyBusinessSurvey",
    unit_id_col="tax_id",
    stratum_col="industry_code",
    continuous_targets=["revenue", "inventory"],
    domain_cols=["region", "size_class"],
    design_weight_col="base_weight"
)

print(f"Contract for {contract.dataset_name} initialized.")
```

### Example 2: Ingesting a Clean CSV with Quality Certification
```python
import polars as pl
from ingestion.engine import IngestionEngine
from ingestion.models import SurveyDataContract

# Setup a mock CSV
df_raw = pl.DataFrame({
    "tax_id": ["ID1", "ID2", "ID3"],
    "revenue": [100.0, 150.0, 120.0],
    "region": ["North", "South", "North"],
    "base_weight": [10.0, 10.0, 10.0]
})
df_raw.write_csv("test_data.csv")

contract = SurveyDataContract(
    dataset_name="TestSurvey",
    unit_id_col="tax_id",
    continuous_targets=["revenue"],
    domain_cols=["region"],
    design_weight_col="base_weight"
)

engine = IngestionEngine(contract, db_path="test_audit.db")
result = engine.ingest_file("test_data.csv")

print(f"Status: {result.status}")
print(f"Quality Grade: {result.quality.grade} (Score: {result.quality.score:.1f})")
print(result.data)
```

### Example 3: Handling Contract Violations (Missing Columns)
```python
import polars as pl
from ingestion.engine import IngestionEngine
from ingestion.models import SurveyDataContract

# CSV missing the required 'revenue' column
df_bad = pl.DataFrame({"tax_id": ["ID1"], "region": ["North"]})
df_bad.write_csv("missing_cols.csv")

contract = SurveyDataContract(
    dataset_name="MissingColTest",
    unit_id_col="tax_id",
    continuous_targets=["revenue"],
    domain_cols=["region"]
)

engine = IngestionEngine(contract)
try:
    result = engine.ingest_file("missing_cols.csv")
except ValueError as e:
    print(f"Caught expected violation: {e}")
```

### Example 4: Handling Integrity Errors (Duplicate IDs)
```python
import polars as pl
from ingestion.engine import IngestionEngine
from ingestion.models import SurveyDataContract

df_dupes = pl.DataFrame({
    "tax_id": ["ID1", "ID1"], # Duplicate!
    "revenue": [100.0, 200.0]
})
df_dupes.write_csv("dupes.csv")

contract = SurveyDataContract(
    dataset_name="DupeTest",
    unit_id_col="tax_id",
    continuous_targets=["revenue"],
    domain_cols=[]
)

engine = IngestionEngine(contract)
result = engine.ingest_file("dupes.csv")

print(f"Overall Success: {result.overall_success}")
print(f"Fatal Errors: {result.fatal_errors}")
```
