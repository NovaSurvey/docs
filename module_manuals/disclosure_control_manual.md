# Module Documentation: disclosure_control

## 1. Module Overview: disclosure_control

The `disclosure_control` module provides a comprehensive suite of Statistical Disclosure Control (SDC) techniques designed to protect respondent confidentiality in tabular and microdata outputs. It implements the classical "Primary and Secondary Suppression" framework used by national statistical agencies, alongside modern privacy-preserving alternatives such as **Differential Privacy (DP)** and **Synthetic Data Generation (SDG)**. The core of the module is an optimization-based engine that identifies high-risk cells and calculates an optimal secondary suppression pattern to prevent mathematical reconstruction of sensitive values.

---

## 2. Core Classes & Initialization

### CellSuppressionEngine
> The primary engine for classical tabular suppression and auditing.

**Initialization:** `CellSuppressionEngine(metadata: SDCMetadata)`
- **metadata**: An `SDCMetadata` object defining the value column, contributor columns, and risk thresholds (p%, dominance).

### DisclosureControlOrchestrator
> The master router that orchestrates SDC protocols and handles fallbacks.

**Initialization:** `DisclosureControlOrchestrator(metadata: SDCMetadata)`
- **metadata**: Configures the high-level method (`tabular_suppression`, `differential_privacy`, or `synthetic_data`) and persistence settings.

---

## 3. Core Methods & Functions

### CellSuppressionEngine.identify_risks(df, is_microdata=False)
Identifies primary sensitive cells based on (n), (n, k)-dominance, and p-percent rules.
- **Returns**: DataFrame with a boolean `is_primary_sensitive` column.

### CellSuppressionEngine.suppress_exact(df, rows, cols)
Solves the secondary cell suppression problem for a 2D table using an exact Mixed-Integer Linear Programming (MILP) simultaneous flow formulation.
- **Returns**: `SuppressionResult` with `is_suppressed` flags and information loss diagnostics.

### CellSuppressionEngine.audit_table(df, rows, cols)
Simulates an attacker's attempt to find the range $[min, max]$ for suppressed cells using Linear Programming.
- **Returns**: A dictionary of audit results containing the empirical safety margins for each primary cell.

### DisclosureControlOrchestrator.run(df_microdata, df_aggregated)
Executes the configured SDC method. If DP or SDG is requested but fails, it can automatically fall back to tabular suppression to ensure zero-day protection.
- **Returns**: `SuppressionResult` containing protected data and quality certification grades.

---

## 4. Details (Methodology & Mathematics)

### Primary Risk Assessment Rules
The engine identifies sensitive cells by analyzing the concentration of values:
1.  **(n, k) Dominance Rule**: A cell is sensitive if the sum of the $k$ largest contributors exceeds $K\%$ of the total:
    $$\sum_{i=1}^k x_{(i)} > \frac{K}{100} X_{total}$$
2.  **p-percent Rule**: A cell is sensitive if the total value minus the largest contributor provides an estimate of that contributor within $p\%$ accuracy:
    $$X_{total} - x_{(1)} < \frac{p}{100} x_{(1)}$$

### Secondary Suppression (MILP Flow)
To prevent reconstruction of primary cells via row/column totals, the engine solves a cost-minimization problem:
$$\min \sum c_{ij} x_{ij}$$
Subject to:
- $x_{ij} = 1$ for all primary sensitive cells.
- Capacity constraints ensuring that the flow across suppressed cells meets the **Upper Protection Level (UPL)**:
    $$f_{ij}^{fwd} + f_{ij}^{rev} \leq X_{ij} \cdot x_{ij}$$
- Flow conservation at each node (row/column total) ensuring the "cycle" of suppression is closed and balanced.

### Attacker Audit Simulation
The safety of a suppression pattern is verified by solving two LPs for each primary cell $x_p$:
- **Minimize** $x_p$ subject to row/column totals.
- **Maximize** $x_p$ subject to row/column totals.
The suppression is considered safe if the resulting interval $[min, max]$ is wide enough to satisfy the UPL.

---

## 5. References

Hundepool, A., et al. (2012). *Statistical Disclosure Control*. John Wiley & Sons.

Castro, J. (2007). A minimum-cost flow formulation for the secondary cell suppression problem. *Operations Research*, 55(4), 786-799.

Dwork, C. (2006). Differential Privacy. *International Colloquium on Automata, Languages, and Programming*.

---

## 6. Runnable Examples

### Example 1: Primary Risk Identification (Microdata)
```python
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

### Example 2: Exact MILP Secondary Suppression (2D Table)
```python
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

### Example 3: Attacker Audit Simulation
```python
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

### Example 4: Orchestrator with Differential Privacy
```python
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
