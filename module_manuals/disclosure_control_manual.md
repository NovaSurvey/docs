# Module Documentation: Disclosure Control

## 1. Module Overview
The `disclosure_control` module provides a comprehensive suite of Statistical Disclosure Control (SDC) techniques designed to protect respondent confidentiality in tabular and microdata outputs. It implements the classical "Primary and Secondary Suppression" framework used by national statistical agencies, alongside modern privacy-preserving alternatives such as **Differential Privacy (DP)** and **Synthetic Data Generation (SDG)**. The core of the module is an optimization-based engine that identifies high-risk cells and calculates an optimal secondary suppression pattern to prevent mathematical reconstruction of sensitive values.

## 2. Table of Contents
- [3. Master Orchestration](#3-master-orchestration)
  - [DisclosureControlOrchestrator](#disclosurecontrolorchestrator)
  - [run](#run)
- [4. Classical Cell Suppression](#4-classical-cell-suppression)
  - [CellSuppressionEngine](#cellsuppressionengine)
  - [identify_risks](#identify_risks)
  - [suppress_exact](#suppress_exact)
  - [suppress_benders](#suppress_benders)
  - [run_rounding](#run_rounding)
  - [audit_table](#audit_table)
- [5. Modern Privacy Methods](#5-modern-privacy-methods)
  - [DifferentialPrivacyEngine](#differentialprivacyengine)
  - [apply_laplace_mechanism](#apply_laplace_mechanism)
  - [SyntheticDataGenerator](#syntheticdatagenerator)
  - [generate_synthetic_microdata](#generate_synthetic_microdata)
- [6. Hierarchical Processing](#6-hierarchical-processing)
  - [AutoHierarchyBuilder & HierarchicalSuppressor](#autohierarchybuilder--hierarchicalsuppressor)
- [7. Analytics & Quality Assurance](#7-analytics--quality-assurance)
  - [calculate_disclosure_impact](#calculate_disclosure_impact)
  - [SDCQualityAssurer](#sdcqualityassurer)
- [8. Persistence](#8-persistence)
  - [SDCPersistence](#sdcpersistence)

---

## 3. Master Orchestration

### DisclosureControlOrchestrator

#### Description
The master router that orchestrates SDC protocols and handles fallbacks.

#### Usage
`DisclosureControlOrchestrator(metadata)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `metadata` | `SDCMetadata` | REQUIRED | Configures the high-level method (`tabular_suppression`, `differential_privacy`, or `synthetic_data`) and persistence settings. |

#### Details
Initializes the orchestrator environment.

#### Value
Initialized `DisclosureControlOrchestrator`.

#### References
N/A

#### Examples
```python
# See run() example below.
```

---

### run (DisclosureControlOrchestrator)

#### Description
Executes the configured SDC method. 

#### Usage
`orch.run(df_microdata, df_aggregated)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df_microdata` | `pl.DataFrame` | REQUIRED | Unit-level microdata. |
| `df_aggregated` | `pl.DataFrame` | REQUIRED | Aggregate tabular data. |

#### Details
If DP or SDG is requested but fails, it can automatically fall back to tabular suppression to ensure zero-day protection.

#### Value
`SuppressionResult` containing protected data and quality certification grades.

#### References
N/A

#### Examples
```python
# Example 4: Orchestrator with Differential Privacy
import polars as pl
from disclosure_control.engine import DisclosureControlOrchestrator
from disclosure_control.models import SDCMetadata, DPConfig

df_agg = pl.DataFrame({"p": ["A", "B"], "revenue": [1000.0, 2000.0]})
df_micro = pl.DataFrame({"p": ["A", "A", "B", "B"], "revenue": [500.0, 500.0, 1000.0, 1000.0]})

meta = SDCMetadata(
    area_id_var="p", group_vars=["p"], value_var="revenue", contribution_vars=["revenue"],
    method="differential_privacy",
    dp_config=DPConfig(epsilon=1.0, sensitivity_bounds={"revenue": 1000.0}),
    allow_fallback=True
)

orch = DisclosureControlOrchestrator(meta)
result = orch.run(df_microdata=df_micro, df_aggregated=df_agg)

print(f"Method Used: {result.diagnostics.method}")
print(result.data)
```

---

## 4. Classical Cell Suppression

### CellSuppressionEngine

#### Description
The primary engine for classical tabular suppression and auditing.

#### Usage
`CellSuppressionEngine(metadata)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `metadata` | `SDCMetadata` | REQUIRED | An `SDCMetadata` object defining the value column, contributor columns, and risk thresholds (p%, dominance). |

#### Details
Initializes the cell suppression engine context.

#### Value
Initialized `CellSuppressionEngine`.

#### References
N/A

#### Examples
```python
# See identify_risks() and suppress_exact() below.
```

---

### identify_risks

#### Description
Identifies primary sensitive cells based on (n), (n, k)-dominance, and p-percent rules.

#### Usage
`engine.identify_risks(df, is_microdata=False)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | Data frame to scan. |
| `is_microdata` | `bool` | `False` | True if the frame contains unit-level data. |

#### Details
**Primary Risk Assessment Rules**
The engine identifies sensitive cells by analyzing the concentration of values:
1.  **(n, k) Dominance Rule**: A cell is sensitive if the sum of the $k$ largest contributors exceeds $K\%$ of the total:
    $$\sum_{i=1}^k x_{(i)} > \frac{K}{100} X_{total}$$
2.  **p-percent Rule**: A cell is sensitive if the total value minus the largest contributor provides an estimate of that contributor within $p\%$ accuracy:
    $$X_{total} - x_{(1)} < \frac{p}{100} x_{(1)}$$

#### Value
DataFrame with a boolean `is_primary_sensitive` column.

#### References
- Hundepool, A., et al. (2012). *Statistical Disclosure Control*. John Wiley & Sons.

#### Examples
```python
# Example 1: Primary Risk Identification (Microdata)
import polars as pl
from disclosure_control.engine import CellSuppressionEngine
from disclosure_control.models import SDCMetadata, SDCConfig

df_micro = pl.DataFrame({
    "province": ["ON", "ON", "ON", "BC", "BC"],
    "industry": ["Tech", "Tech", "Tech", "Agri", "Agri"],
    "revenue": [500000, 10000, 5000, 1000000, 100] # BC is highly dominated
})

meta = SDCMetadata(
    area_id_var="province",
    group_vars=["province", "industry"],
    value_var="revenue",
    contribution_vars=["revenue"],
    config=SDCConfig(n_threshold=3, n_k_dominance=(1, 0.5))
)

engine = CellSuppressionEngine(meta)
df_risks = engine.identify_risks(df_micro, is_microdata=True)

print(df_risks.select(["province", "industry", "revenue", "is_primary_sensitive"]))
```

---

### suppress_exact

#### Description
Solves the secondary cell suppression problem for a 2D table using an exact Mixed-Integer Linear Programming (MILP) simultaneous flow formulation.

#### Usage
`engine.suppress_exact(df, rows, cols)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | Aggregated table containing `is_primary_sensitive`. |
| `rows` | `str` | REQUIRED | Row variable. |
| `cols` | `str` | REQUIRED | Column variable. |

#### Details
**Secondary Suppression (MILP Flow)**
To prevent reconstruction of primary cells via row/column totals, the engine solves a cost-minimization problem:
$$\min \sum c_{ij} x_{ij}$$
Subject to:
- $x_{ij} = 1$ for all primary sensitive cells.
- Capacity constraints ensuring that the flow across suppressed cells meets the **Upper Protection Level (UPL)**:
    $$f_{ij}^{fwd} + f_{ij}^{rev} \leq X_{ij} \cdot x_{ij}$$
- Flow conservation at each node (row/column total) ensuring the "cycle" of suppression is closed and balanced.

#### Value
`SuppressionResult` with `is_suppressed` flags and information loss diagnostics.

#### References
- Castro, J. (2007). A minimum-cost flow formulation for the secondary cell suppression problem. *Operations Research*, 55(4), 786-799.

#### Examples
```python
# Example 2: Exact MILP Secondary Suppression (2D Table)
import polars as pl
from disclosure_control.engine import CellSuppressionEngine
from disclosure_control.models import SDCMetadata

# Table with one primary sensitive cell (BC-Agri)
df_agg = pl.DataFrame({
    "province": ["ON", "ON", "BC", "BC"],
    "industry": ["Tech", "Agri", "Tech", "Agri"],
    "revenue": [10000, 5000, 8000, 200],
    "is_primary_sensitive": [False, False, False, True]
})

meta = SDCMetadata(
    area_id_var="province",
    group_vars=["province", "industry"],
    value_var="revenue",
    contribution_vars=["revenue"]
)

engine = CellSuppressionEngine(meta)
result = engine.suppress_exact(df_agg, rows="province", cols="industry")

print("Secondary Suppression Pattern:")
print(result.data.select(["province", "industry", "revenue", "is_suppressed"]))
print(f"Information Loss: {result.diagnostics.information_loss_pct:.1f}%")
```

---

### suppress_benders

#### Description
Uses Benders Decomposition to solve large-scale secondary suppression problems that cannot be solved efficiently using the exact MILP approach.

#### Usage
`engine.suppress_benders(df, rows, cols)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | Aggregated table. |
| `rows` | `str` | REQUIRED | Row variable. |
| `cols` | `str` | REQUIRED | Column variable. |

#### Details
Employs an iterative cut-generation process to find near-optimal suppression patterns on very large tables.

#### Value
`SuppressionResult` object.

#### References
N/A

#### Examples
```python
# result = engine.suppress_benders(df, rows="province", cols="industry")
```

---

### run_rounding

#### Description
Implements controlled rounding as a lighter alternative to full cell suppression, perturbing cell values to a specified base while maintaining marginal totals.

#### Usage
`engine.run_rounding(df, rows, cols)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | Aggregated table. |
| `rows` | `str` | REQUIRED | Row variable. |
| `cols` | `str` | REQUIRED | Column variable. |

#### Details
Adjusts values up or down to the nearest rounding base (e.g., base 5 or 10).

#### Value
`SuppressionResult` with rounded values.

#### References
N/A

#### Examples
```python
# Example 7: Controlled Rounding
import polars as pl
from disclosure_control.engine import CellSuppressionEngine
from disclosure_control.models import SDCMetadata

df_agg = pl.DataFrame({
    "province": ["ON", "ON", "BC", "BC"],
    "industry": ["Tech", "Agri", "Tech", "Agri"],
    "revenue": [10003, 5012, 8045, 201],
    "is_primary_sensitive": [False, False, False, True]
})

meta = SDCMetadata(area_id_var="province", group_vars=["province", "industry"], value_var="revenue", contribution_vars=["revenue"])
engine = CellSuppressionEngine(meta)

# Round values to base 10
result = engine.run_rounding(df_agg, rows="province", cols="industry")
print(result.data.select(["province", "industry", "revenue", "rounded_revenue"]))
```

---

### audit_table

#### Description
Simulates an attacker's attempt to find the range $[min, max]$ for suppressed cells using Linear Programming.

#### Usage
`engine.audit_table(df, rows, cols)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | Table with `is_suppressed` column. |
| `rows` | `str` | REQUIRED | Row variable. |
| `cols` | `str` | REQUIRED | Column variable. |

#### Details
**Attacker Audit Simulation**
The safety of a suppression pattern is verified by solving two LPs for each primary cell $x_p$:
- **Minimize** $x_p$ subject to row/column totals.
- **Maximize** $x_p$ subject to row/column totals.
The suppression is considered safe if the resulting interval $[min, max]$ is wide enough to satisfy the UPL.

#### Value
A dictionary of audit results containing the empirical safety margins for each primary cell.

#### References
N/A

#### Examples
```python
# Example 3: Attacker Audit Simulation
import polars as pl
from disclosure_control.engine import CellSuppressionEngine
from disclosure_control.models import SDCMetadata

df_suppressed = pl.DataFrame({
    "province": ["ON", "ON", "BC", "BC"],
    "industry": ["T", "A", "T", "A"],
    "revenue": [100, 50, 80, 20],
    "is_primary_sensitive": [False, False, False, True],
    "is_suppressed": [True, True, True, True]
})

meta = SDCMetadata(area_id_var="p", group_vars=["p", "i"], value_var="revenue", contribution_vars=[])
engine = CellSuppressionEngine(meta)

audit = engine.audit_table(df_suppressed, rows="province", cols="industry")
p_key = ("BC", "A")
print(f"Audit Results for {p_key}:")
print(f"  Min possible: {audit[p_key]['min']}")
print(f"  Max possible: {audit[p_key]['max']}")
print(f"  Actual: {audit[p_key]['actual']}")
```

---

## 5. Modern Privacy Methods

### DifferentialPrivacyEngine

#### Description
Implements modern epsilon-differential privacy using the Laplace mechanism.

#### Usage
`DifferentialPrivacyEngine(config)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `config` | `DPConfig` | REQUIRED | Differential Privacy configuration containing epsilon and bounds. |

#### Details
Initializes DP parameters.

#### Value
Initialized `DifferentialPrivacyEngine`.

#### References
- Dwork, C. (2006). Differential Privacy. *International Colloquium on Automata, Languages, and Programming*.

#### Examples
```python
# See apply_laplace_mechanism() below.
```

---

### apply_laplace_mechanism

#### Description
Adds Laplace noise calibrated to the global sensitivity of the target columns and the privacy budget ($\epsilon$).

#### Usage
`dp_engine.apply_laplace_mechanism(df, target_cols)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df` | `pl.DataFrame` | REQUIRED | Aggregated table. |
| `target_cols` | `list` | REQUIRED | Columns to perturb. |

#### Details
Maintains strict theoretical privacy guarantees by adding noise drawn from $Laplace(\Delta f / \epsilon)$.

#### Value
DataFrame with perturbed, differentially private values.

#### References
N/A

#### Examples
```python
# Example 5: Differential Privacy (Laplace Mechanism)
import polars as pl
from disclosure_control.differential_privacy import DifferentialPrivacyEngine
from disclosure_control.models import DPConfig

df_agg = pl.DataFrame({"industry": ["Tech", "Agri"], "revenue": [150000.0, 50000.0]})

# Configure DP with epsilon=1.0 and a known global sensitivity bound for revenue
dp_config = DPConfig(epsilon=1.0, sensitivity_bounds={"revenue": 10000.0})
dp_engine = DifferentialPrivacyEngine(dp_config)

# Apply noise
df_dp = dp_engine.apply_laplace_mechanism(df_agg, target_cols=["revenue"])
print(df_dp)
```

---

### SyntheticDataGenerator

#### Description
Generates non-disclosive synthetic microdata that mimics the statistical properties of the original dataset.

#### Usage
`SyntheticDataGenerator(n_samples)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `n_samples` | `int` | REQUIRED | Number of synthetic records to generate. |

#### Details
Initializes generator context.

#### Value
Initialized `SyntheticDataGenerator`.

#### References
N/A

#### Examples
```python
# See generate_synthetic_microdata() below.
```

---

### generate_synthetic_microdata

#### Description
Uses sequential regression models (e.g., CART) to generate fully synthetic unit-level data based on the conditional distributions of the real data.

#### Usage
`generator.generate_synthetic_microdata(df_real, synthesis_sequence)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df_real` | `pl.DataFrame` | REQUIRED | Real microdata. |
| `synthesis_sequence` | `list` | REQUIRED | Order of variable synthesis with predictors. |

#### Details
Preserves covariances without releasing true individual records.

#### Value
DataFrame of synthetic microdata.

#### References
N/A

#### Examples
```python
# Example 6: Synthetic Data Generation
import polars as pl
from disclosure_control.synthetic_data import SyntheticDataGenerator

df_real = pl.DataFrame({
    "age": [25, 30, 45, 22, 50],
    "income": [50000, 60000, 120000, 45000, 110000],
    "region": ["East", "East", "West", "East", "West"]
})

generator = SyntheticDataGenerator(n_samples=5)

# Synthesize region first, then age conditional on region, then income conditional on age and region
sequence = [
    {"target": "region", "predictors": []},
    {"target": "age", "predictors": ["region"]},
    {"target": "income", "predictors": ["region", "age"]}
]

df_synthetic = generator.generate_synthetic_microdata(df_real, synthesis_sequence=sequence)
print(df_synthetic)
```

---

## 6. Hierarchical Processing

### AutoHierarchyBuilder & HierarchicalSuppressor

#### Description
Automatically extracts complex linear equations from multidimensional microdata and applies secondary suppression across hierarchical linked tables.

#### Usage
`AutoHierarchyBuilder(hierarchy_columns)`
`HierarchicalSuppressor(equations)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `hierarchy_columns` | `list` | REQUIRED | Columns defining the hierarchy. |
| `equations` | `dict` | REQUIRED | Equations dict from `AutoHierarchyBuilder`. |

#### Details
Ensures that tabular sub-totals cannot be used to circumvent cell suppression rules at a higher or lower level.

#### Value
Initialized builder or suppressor.

#### References
N/A

#### Examples
```python
# builder = AutoHierarchyBuilder(["region", "province", "city"])
# equations = builder.extract_equations(df)
# supp = HierarchicalSuppressor(equations)
```

---

## 7. Analytics & Quality Assurance

### calculate_disclosure_impact

#### Description
Evaluates the utility loss caused by disclosure control.

#### Usage
`calculate_disclosure_impact(df_output)`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `df_output` | `pl.DataFrame` | REQUIRED | Suppressed or protected DataFrame. |

#### Details
Summarizes metrics like the total value suppressed or the percentage of cells masked.

#### Value
Dictionary containing impact metrics.

#### References
N/A

#### Examples
```python
# metrics = calculate_disclosure_impact(df_output)
```

---

### SDCQualityAssurer

#### Description
Certifies the final output data, assigning an A-F grade based on information loss and safety margins.

#### Usage
`SDCQualityAssurer()`

#### Arguments
None.

#### Details
Ensures adherence to agency release policies.

#### Value
Initialized `SDCQualityAssurer`.

#### References
N/A

#### Examples
```python
# qa = SDCQualityAssurer()
```

---

## 8. Persistence

### SDCPersistence

#### Description
SQLite-backed storage for tracking suppression runs, suppressed cells, and audit simulation results.

#### Usage
`SDCPersistence(db_path="disclosure_audit.db")`

#### Arguments
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `db_path` | `str` | `"disclosure_audit.db"` | Path to the SQLite DB. |

#### Details
Records the exact configuration, suppressed cells, and attacker audit bounds to the database for legal/compliance tracking.
Available methods: `save_run`, `save_cells`, `save_audit`.

#### Value
Initialized `SDCPersistence`.

#### References
N/A

#### Examples
```python
# db = SDCPersistence()
# db.save_run("run_123", result.diagnostics)
```
