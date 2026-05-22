# Nova GUI Standalone Executable: Usage & Command Guide

This guide outlines exactly how to launch, operate, and execute high-stakes statistical commands inside the standalone **`nova_gui.exe`** desktop console application.

---

## 🚀 1. How to Launch and Operate Nova GUI

1. **Launch the Desktop Application**:
   Double-click the compiled binary at:
   ```powershell
   .\dist\nova_gui.exe
   ```
   *Note: Because it is packaged in `--noconsole` mode, it will open the clean "Nova Console" window directly without showing a background command prompt.*

2. **Load the Sample Dataset**:
   * Go to the top menu bar and select **File -> Load File/Data** (or *Load Workspace*).
   * Open the prepared pipeline sample dataset at `examples/data/input/prod_input.parquet` (or any other CSV/Parquet file in the workspace).
   * You will see a success confirmation print directly inside the monospace area:
     ```text
     [Success] Loaded workspace dataset: 'prod_input.parquet'
               Shape: 100 rows, 7 columns
     ```

3. **Explore Monospace Interface Controls**:
   * Type commands directly at the **`> `** prompt.
   * Feel free to test the built-in RGui keyboard bounds: try backspacing past the active line or clicking other cells to edit past outputs. The boundary lock will seamlessly snap the focus back to the input block.

4. **Verify Dynamic HTML Help**:
   * Navigate to **Packages -> Module Documentation** and click **Outliers** or **Imputation**.
   * It will instantly open a styled, responsive, R-like documentation page in your default browser containing mathematical formulas, options, and copy-pasteable execution examples!
   * Go to **Help -> Master User Guide** to open the global dashboard.

---

## 📊 2. Synthetic Dataset Reference Schema
To execute the statistical module commands below, make sure you have loaded a standard survey dataset like `examples/data/input/prod_input.parquet` (which has 100 rows). It contains the following columns:
* `id` : Unique integer key (e.g. `0` to `99`).
* `area` : Grouping/Stratum variable (e.g. `Area_0` to `Area_9`).
* `part1` : Auxiliary numeric column.
* `part2` : Secondary numeric column (contains some missing values `None`).
* `total` : Survey total column (contains some edit errors: `part1 + part2 != total`).
* `revenue` : Main numeric target column (contains some outliers).
* `initial_weight` : Design/initial sample weights.
* `psi` : Direct area variance estimate column.
* `pi_k` : Direct sampling probability column.

---

## 🛠️ 3. Natural Python/R Function Syntax & CLI Commands [NEW]

You can execute commands inside **`nova_gui.exe`** using either **natural programming function syntax** (exactly like R or Python) or standard CLI commands! Both positional arguments and keyword arguments are fully supported!

### Syntax Rules:
1. **Unquoted Column Names**: You can specify columns without quotes, e.g. `outliers(revenue)` instead of `outliers("revenue")`.
2. **Positional Arguments**: Maps parameters naturally by their order, e.g., `outliers(revenue, hb, 3.5)` maps to `--target revenue`, `--method hb`, and `--threshold 3.5`.
3. **Keyword Arguments**: Override or explicitly define parameters by name, e.g., `outliers(revenue, method="hb", threshold=3.5)`.

Below are the examples of **both** natural function calls and CLI commands for each module:

### 1. Outliers (`outliers`)
Detects anomalous survey entries in `revenue` using Huber's robust method.
* **Natural R/Python call**:
  ```text
  outliers(revenue, method="hb", threshold=3.0)
  ```
* **CLI syntax**:
  ```text
  run outliers --target revenue --method hb --threshold 3.0
  ```

### 2. Imputation (`imputation`)
Imputes missing values in `part2` using a ratio estimator assisted by auxiliary variable `part1`.
* **Natural R/Python call**:
  ```text
  imputation(part2, part1, method="ratio")
  ```
* **CLI syntax**:
  ```text
  run imputation --target part2 --aux part1 --method ratio
  ```

### 3. Editing & Recalculation (`editing`)
Validates that `total = part1 + part2` and automatically corrects errors using a balance/recalculation rule.
* **Natural R/Python call**:
  ```text
  editing(vars="part1,part2,total", edits="total = part1 + part2")
  ```
* **CLI syntax**:
  ```text
  run editing --vars part1,part2,total --edits "total = part1 + part2"
  ```

### 4. Nonresponse Weighting (`nonresponse`)
Adjusts initial survey weights based on response probabilities to counter nonresponse bias.
* **Natural R/Python call**:
  ```text
  nonresponse(revenue, initial_weight, response_var="id")
  ```
* **CLI syntax**:
  ```text
  run nonresponse --target revenue --weight_var initial_weight --response_var id
  ```

### 5. Calibration Weighting (`calibration`)
Calibrates sample weights so estimated sums align perfectly with known population benchmarks.
* **Natural R/Python call**:
  ```text
  calibration(revenue, initial_weight, pop_total=100000.0)
  ```
* **CLI syntax**:
  ```text
  run calibration --target revenue --weight_var initial_weight --pop_total 100000.0
  ```

### 6. Sampling Design Analysis (`sampling`)
Analyzes stratified sampling allocations, expansion estimators, and sample coverage across areas.
* **Natural R/Python call**:
  ```text
  sampling(revenue, initial_weight, stratum="area")
  ```
* **CLI syntax**:
  ```text
  run sampling --target revenue --weight_var initial_weight --stratum area
  ```

### 7. Influential Units (`influential`)
Flags high-impact outlier units that excessively skew target estimators (e.g. using the AY method).
* **Natural R/Python call**:
  ```text
  influential(revenue, initial_weight, group_var="area")
  ```
* **CLI syntax**:
  ```text
  run influential --target revenue --weight_var initial_weight --group_var area
  ```

### 8. Small Area Estimation (`sae`)
Applies Fay-Herriot EBLUP modeling to stabilize area-level estimates with small sample sizes.
* **Natural R/Python call**:
  ```text
  sae(direct_est, variance_var="psi", area_var="area", aux_vars="part1")
  ```
* **CLI syntax**:
  ```text
  run sae --target direct_est --variance_var psi --area_var area --aux_vars part1
  ```
*(Note: requires loading a direct-estimator dataset like `pipeline_output.parquet` which contains `direct_est` and `psi`).*

### 9. Variance Estimation (`variance`)
Estimates precision metrics (standard errors and CVs) under complex sampling designs (e.g. Poisson).
* **Natural R/Python call**:
  ```text
  variance(revenue, initial_weight, stratum="area")
  ```
* **CLI syntax**:
  ```text
  run variance --target revenue --weight_var initial_weight --stratum area
  ```

### 10. Seasonal Adjustment (`seasonal`)
Decomposes target time series into seasonal, trend, and irregular components (STL/ARIMA-ready).
* **Natural R/Python call**:
  ```text
  seasonal(revenue)
  ```
* **CLI syntax**:
  ```text
  run seasonal --target revenue
  ```

### 11. Statistical Disclosure Control (`sdc`)
Protects respondent confidentiality by applying primary suppression and adding differential privacy noise.
* **Natural R/Python call**:
  ```text
  sdc(revenue, area_var="area", n_threshold=3)
  ```
* **CLI syntax**:
  ```text
  run sdc --target revenue --area_var area --n_threshold 3
  ```

### 12. Variance Imputation (`variance_imputation`)
Calculates the extra variance contribution introduced by imputing missing values.
* **Natural R/Python call**:
  ```text
  variance_imputation(revenue, initial_weight)
  ```
* **CLI syntax**:
  ```text
  run variance_imputation --target revenue --weight_var initial_weight
  ```

---

## 🔄 4. Running a Full Pipeline

You can run the entire 12-module high-performance statistical pipeline sequentially using the dedicated command line runner or Python test suite:

### Option A: Run via Python Integration Script (Recommended)
Launch the end-to-end integration test which generates synthetic production data, feeds it through all 12 modules via the `PipelineManager`, writes a combined output file `prod_output.parquet`, and creates a full QA report:
```powershell
python run_full_pipeline.py
```
Upon completion, the pipeline outputs:
* **Output Parquet**: `examples/data/output/prod_output.parquet`
* **Full QA Audit & Quality Report**: `examples/data/output/prod_output_qa_report.json`

### Option B: Run Batch CLI (Fast Verification)
To trigger the entire statistical pipeline inside the command shell directly:
```powershell
python run_banff_pipeline.py
```
This executes the core BANFF editing, outlier detection, and imputation pipeline, producing a certified, audited output Parquet frame in seconds!

---

## 🐍 5. Running Arbitrary Python Code (Interactive REPL)

Both the windowed **`nova_gui.exe`** console and **`nova_console.exe`** now act as a **fully functional, interactive Python REPL**! Any entered command that is not a pre-defined statistical command is compiled and executed dynamically inside a persistent, sandbox-safe local Python context.

### Features:
1. **Bidirectional Dataset Synchronization**: The active Polars DataFrame is automatically exposed inside your Python scope as the variable **`df`**. If you modify `df` in Python, the active workspace state updates instantly!
2. **Pre-imported Modules**: Common high-performance libraries are pre-imported for you:
   * **`pl`** : Polars
   * **`np`** : NumPy
   * **`pd`** : Pandas (if installed)
3. **Persistent Local Context**: Variables, custom functions, and classes you define remain in scope across inputs.

### Premium Examples to Try:

* **Basic Math Calculations**:
  ```text
  > 100 * 45 / 3.14
  1433.1210191082802
  ```

* **Inspect the Active Polars Dataset**:
  ```text
  > df.shape
  (100, 7)
  ```
  ```text
  > df.columns
  ['id', 'area', 'part1', 'part2', 'total', 'revenue', 'initial_weight']
  ```

* **Execute High-speed Polars Queries**:
  ```text
  > df.filter(pl.col("revenue") > 500)
  ```

* **Define Persistent Variables**:
  ```text
  > scale_factor = 2.5
  > scale_factor * df.height
  250.0
  ```

* **Run Standard Python Scripting**:
  ```text
  > import math
  > math.sqrt(64)
  8.0
  ```

* **Install and Import External Python Packages**:
  Since our application has a dedicated **workspace package extension injection system**, you can install any Python library locally into the workspace, and it will be immediately available inside the GUI!
  1. Open your terminal in the workspace directory.
  2. Run the pip installation targeting the local `packages/` folder:
     ```powershell
     pip install --target .\packages requests
     ```
  3. Inside the `nova_gui.exe` console, import it directly:
     ```text
     > import requests
     > r = requests.get("https://api.github.com")
     > r.status_code
     200
     ```
  Any third-party analytical, plotting, or utility library can be dynamically installed and loaded at runtime without needing to recompile the binary!
