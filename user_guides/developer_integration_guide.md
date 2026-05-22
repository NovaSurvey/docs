# NovaSurvey Developer & Integration Guide
## Programmatic Backend Integration Manual

NovaSurvey’s advanced statistical engines are implemented as pure, modular Python packages built on top of high-performance **Polars** dataframes. While they are exposed via the interactive RGui Console and Tkinter interfaces, they can be imported and called programmatically inside any custom Python program, batch job, or pipeline.

This guide provides concrete code templates and explanations on how to integrate the backend engines into your own analytical programs.

---

## ⚙️ 1. Environment Setup

To import NovaSurvey packages programmatically, ensure that your Python script can resolve the project workspace directory. You can add it to the search path programmatically:

```python
import os
import sys
import polars as pl

# 1. Add the workspace directory to the Python path
workspace_dir = r"c:\Users\mjian\Projects\ai-survey-app"
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)
```

---

## 🔍 2. Statistical Module Integration Examples

### A. Outlier Detection (`editing.outlier`)
Performs robust statistical outlier detection (e.g., Hidiroglou-Berthelot, Sigma-Gap, Isolation Forest) and appends boolean flagging columns directly to your dataset.

```python
from editing.outlier import run_outlier_detection

# 1. Prepare your dataset
df = pl.DataFrame({
    "id": [1, 2, 3, 4, 5],
    "revenue": [450.0, 520.0, 490.0, 15000.0, 480.0]  # Row 4 is an extreme outlier
})

# 2. Define the outlier check task
task = {
    "variable": "revenue",
    "method": "hb",              # Hidiroglou-Berthelot
    "threshold": 3.0,            # Z-score outlier threshold
    "prev_column": None,         # Optional: previous wave column for ratio outliers
    "group_var": None,           # Optional: stratum/grouping column
    "weight_var": None,          # Optional: weight column
    "critical_threshold": None   # Optional: criticality limit
}

# 3. Execute outlier detection
flagged_df = run_outlier_detection(df, [task])

print("Output Columns:", flagged_df.columns)
# Added columns: 'revenue_FTE' (Flagged for Extreme), 'revenue_FTI' (Flagged for Imputation)
print(flagged_df.select(["id", "revenue", "revenue_FTE", "revenue_FTI"]))
```

---

### B. High-Performance Imputation Engine (`imputation.engine`)
Implements ratio, mean, donor (hot-deck), and machine learning estimators (XGBoost) to impute missing (`null`) survey values.

```python
from imputation.models import ImputationConfig, EstimatorTask
from imputation.engine import ImputationEngine

# 1. Prepare your dataset with missing values (None / null)
df = pl.DataFrame({
    "id": [1, 2, 3, 4, 5],
    "revenue": [400.0, None, 450.0, 600.0, None],
    "sales": [320.0, 390.0, 360.0, 480.0, 310.0]  # Auxiliary variable
})

# 2. Hardening check: Ensure FTI flag exists (True for rows needing imputation)
if "revenue_FTI" not in df.columns:
    df = df.with_columns(pl.col("revenue").is_null().alias("revenue_FTI"))

# 3. Configure the Imputation Task
task = EstimatorTask(
    target="revenue",
    method="ratio",         # Ratio imputation
    aux=["sales"],          # Auxiliary columns
    weight_var=None,
    group_var=None
)

# 4. Instantiate Configuration
config = ImputationConfig(
    estimator_config=[task],
    imputation_sequence=["estimators"],
    mi_diagnostic_iterations=0,
    run_quality_certification=False,
    persist_results=False
)

# 5. Run the Imputation Engine
engine = ImputationEngine(df, config)
result = engine.run_imputation_module(df)

imputed_df = result.data
print("Imputed Dataset:")
print(imputed_df.select(["id", "revenue", "sales", "revenue_FTI"]))
```

---

### C. Bounded Calibration Engine (`calibration.engine`)
Adjusts design weights to match auxiliary population totals (raking, chi-square) while maintaining rigorous lower/upper bounds.

```python
from calibration.models import CalibrationMetadata, CalibrationGroup, CalibrationConstraints, DatasetConfig
from calibration.engine import CalibrationEngine

# 1. Prepare survey data with initial weights and auxiliary regions
df = pl.DataFrame({
    "id": [1, 2, 3, 4],
    "base_weight": [10.0, 10.0, 10.0, 10.0],
    "region": ["North", "North", "South", "South"]
})

# 2. Setup Bounded Calibration Metadata
metadata = CalibrationMetadata(
    dataset_config=DatasetConfig(
        file_name="custom_pipeline",
        initial_weight_var="base_weight"
    ),
    calibration_groups=[
        CalibrationGroup(
            group_id="region_calibration",
            auxiliary_vars=["region"],
            population_totals=[1500.0, 1500.0]  # Targets for North and South
        )
    ],
    constraints=CalibrationConstraints(
        lower_bound_ratio=0.4,
        upper_bound_ratio=3.0
    ),
    method="chi-square",
    output_weight_col="calibrated_weight",
    persist_results=False
)

# 3. Calibrate Weights
engine = CalibrationEngine(metadata)
result = engine.calibrate(df)

calibrated_df = result.data
print("Calibrated Dataset:")
print(calibrated_df.select(["id", "base_weight", "region", "calibrated_weight"]))
```

---

## 🔄 3. Building an End-to-End Pipeline

Because every backend module consumes a **Polars DataFrame** and returns a modified **Polars DataFrame**, you can cleanly chain these operations into a unified analytical pipeline:

```python
import polars as pl
from editing.outlier import run_outlier_detection
from imputation.models import ImputationConfig, EstimatorTask
from imputation.engine import ImputationEngine

def process_survey_data(filepath: str) -> pl.DataFrame:
    # 1. Ingest
    df = pl.read_parquet(filepath) if filepath.endswith(".parquet") else pl.read_csv(filepath)
    
    # 2. Flag Outliers
    outlier_task = {
        "variable": "revenue",
        "method": "hb",
        "threshold": 3.0,
        "prev_column": None,
        "group_var": None,
        "weight_var": None,
        "critical_threshold": None
    }
    df = run_outlier_detection(df, [outlier_task])
    
    # 3. Impute Flagged Cells
    impute_task = EstimatorTask(
        target="revenue",
        method="ratio",
        aux=["sales"],
        weight_var=None,
        group_var=None
    )
    config = ImputationConfig(
        estimator_config=[impute_task],
        imputation_sequence=["estimators"],
        mi_diagnostic_iterations=0,
        run_quality_certification=False,
        persist_results=False
    )
    engine = ImputationEngine(df, config)
    result = engine.run_imputation_module(df)
    
    return result.data

if __name__ == "__main__":
    processed_df = process_survey_data("comprehensive_sample.parquet")
    print("Pipeline Processing Complete!")
    print(processed_df.head())
```

---

## 💻 4. Programmatic Automation via Compiled Binary (`nova_console.exe`)

If you are distributing your application as compiled executables and **your users do not have access to the raw Python source code or packages**, they can still completely automate and script the analytical pipelines!

Both the GUI and CLI configurations generate a standalone command-line executable: **`dist/nova_console.exe`**. This console binary supports fully headless standard input (`stdin`) piping and standard output (`stdout`) redirection. Developers can drive the compiled engines programmatically in any language of their choice!

### A. Terminal Batch Redirection (Standard Pipes)
You can write a simple text file (`commands.txt`) listing the console actions to take, and pipe it directly into `nova_console.exe` using standard shell redirection:

**`commands.txt`**:
```text
load my_dataset.parquet
run outliers --target revenue --method hb --threshold 2.5
run imputation --target revenue --method ratio --aux sales
export processed_dataset.parquet
exit
```

**Run in Terminal (Command Prompt / PowerShell / Bash)**:
```cmd
dist/nova_console.exe < commands.txt
```

---

### B. Programmatic Calling in Python (via Subprocesses)
You can spawn the compiled `nova_console.exe` binary as a child subprocess, write commands dynamically to its input stream, and capture the stdout response programmatically:

```python
import subprocess

def run_compiled_pipeline():
    # 1. Start the compiled CLI console as a subprocess
    process = subprocess.Popen(
        ["dist/nova_console.exe"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    # 2. Send commands to stdin line by line
    commands = [
        "load comprehensive_sample.parquet",
        "run outliers --target revenue --method hb --threshold 2.5",
        "run imputation --target revenue --method ratio --aux sales",
        "export processed_sample.parquet",
        "exit"
    ]
    
    for cmd in commands:
        process.stdin.write(cmd + "\n")
    
    process.stdin.flush()
    
    # 3. Capture and print console log outputs
    stdout, stderr = process.communicate()
    print("=== Subprocess Outputs ===")
    print(stdout)

if __name__ == "__main__":
    run_compiled_pipeline()
```

---

### C. Programmatic Calling in R (via `system2`)
If your data analysts or statistician users work exclusively in **R**, they can call the compiled console binary natively:

```R
run_compiled_pipeline <- function() {
  # 1. Define command sequence
  commands <- c(
    "load comprehensive_sample.parquet",
    "run outliers --target revenue --method hb --threshold 2.5",
    "run imputation --target revenue --method ratio --aux sales",
    "export processed_sample.parquet",
    "exit"
  )
  
  # 2. Execute compiled binary passing commands via input stream
  output <- system2(
    command = "dist/nova_console.exe",
    input = commands,
    stdout = TRUE,
    stderr = TRUE
  )
  
  # 3. Print output logs
  cat("=== R Subprocess Outputs ===\n")
  cat(paste(output, collapse = "\n"))
}

run_compiled_pipeline()
```

