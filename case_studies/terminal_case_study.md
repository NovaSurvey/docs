# Case Study: Processing Complex Data via the Terminal

> [!NOTE]
> This case study demonstrates how to use the `NovaSurveyApp.exe` terminal (REPL) interface to ingest, clean, and process the messy CPS ASEC dataset without needing the Graphical User Interface.

## Introduction
The NovaSurvey engine provides a powerful, interactive terminal interface for data scientists and engineers who prefer working via the command line. This guide walks through the exact commands needed to process our 1,000,000-row synthetic Current Population Survey (CPS) dataset containing non-response bias and multimillion-dollar outliers.

## Terminal Workflow

![Terminal Workflow Interface](./terminal_workflow.png)

### 1. Launching the App
Start the terminal interface by executing the application:
```bash
./NovaSurveyApp.exe --console
```

You will be greeted by the interactive `NovaSurvey>` prompt.

### 2. Loading the Data
Load the heavily compressed Parquet file directly into the engine's memory:

```shell
NovaSurvey> load cps_labor_messy.parquet
[Success] Loaded 1000000 rows and 5 columns into memory.
```

### 3. Inspecting the Messiness
You can immediately view the statistical distributions and identify the missing data (nulls) by running the summary command:

```shell
NovaSurvey> summary
[Success] DataFrame summary (1000000 rows, 5 columns):
...
Weekly_Earnings
  Min.   :           0.0000
  1st Qu.:         450.2300
  Median :         780.4500
  Mean   :       12540.3000   <-- (Skewed by massive outliers)
  3rd Qu.:        1150.1000
  Max.   :    49500000.0000   <-- (The $50M Anomaly)
  NA's   :           119884   <-- (The 20% Non-Response)
```

### 4. Mitigating Outliers
We will mathematically cap the 50 multimillion-dollar anomalies so they don't destroy our downstream aggregations:

```shell
NovaSurvey> run outliers --target Weekly_Earnings --method hb --threshold 3.0
[Info] Running outlier detection on column 'Weekly_Earnings' using method 'hb'...
[Success] Outlier detection completed.
  Flagged for Extreme (FTE) : 50
  Flagged for Impute (FTI)  : 0
```

### 5. Context-Aware Imputation
Next, we impute the 119,884 missing `Weekly_Earnings` values. Instead of a flat average, we tell the engine to calculate the ratio based on `Usual_Hours_Worked`, grouped automatically by the `Industry_Code`.

```shell
NovaSurvey> run imputation --target Weekly_Earnings --method ratio --aux Usual_Hours_Worked --group_var Industry_Code
[Info] Running 'ratio' imputation for column 'Weekly_Earnings'...
[Success] Imputation completed successfully.
  Imputed count: 119884
```

### 6. Exporting the Cleaned Output
Finally, we write the perfectly clean, imputed, and outlier-mitigated dataset back to disk as a highly compressed Parquet file:

```shell
NovaSurvey> export cps_labor_cleaned.parquet
[Success] Exported data to cps_labor_cleaned.parquet
```

## Conclusion
Using the `NovaSurveyApp.exe` terminal, we processed 1,000,000 rows, dynamically imputed over 100k missing values based on industry-specific ratios, and securely mitigated massive anomalies—all using simple, chained commands.
