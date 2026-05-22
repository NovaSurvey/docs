import os

case_studies_dir = r"c:\Users\mjian\Projects\docs\case_studies"

files_content = {
    "01_sampling.md": """# Case Study 1: Survey Sampling

![Sampling Dashboard](./01_sampling.png)

## Overview
This module demonstrates the engine's capability to execute complex stratified random sampling designs. The dashboard visualizes the strata allocation budget and the geographic distribution of selected survey units, ensuring a representative baseline.
""",
    "02_editing_outliers.md": """# Case Study 2: Editing & Outlier Mitigation

![Editing and Outliers](./02_editing_outliers.png)

## Overview
Real-world microdata contains extreme anomalies. This module intelligently identifies statistical outliers (shown in red) using algorithms like Hidiroglou-Berthelot, capping them to preserve data integrity rather than simply dropping the records.
""",
    "03_imputation.md": """# Case Study 3: Data Imputation

![Imputation](./03_imputation.png)

## Overview
Missing data is a reality in any survey. The imputation module utilizes advanced models (Ratio, Donor, XGBoost) to predict and fill missing values contextually. The chart illustrates how missing gaps are mathematically filled to maintain the overall distribution.
""",
    "04_influential_units.md": """# Case Study 4: Influential Units Winsorization

![Influential Units](./04_influential_units.png)

## Overview
Some units carry excessive survey weights combined with extreme values, heavily distorting estimates. This module detects these influential units using Conditional Bias and shrinks their impact (winsorization) to stabilize downstream aggregations.
""",
    "05_nonresponse_weighting.md": """# Case Study 5: Nonresponse Weighting

![Nonresponse Weighting](./05_nonresponse_weighting.png)

## Overview
To counteract systematic nonresponse bias, this module dynamically creates Response Homogeneity Groups (RHGs) and applies inverse probability weighting. The chart shows how the unweighted, skewed sample is adjusted to form a balanced representative curve.
""",
    "06_calibration.md": """# Case Study 6: Calibration & Raking

![Calibration](./06_calibration.png)

## Overview
Survey samples rarely match the true population benchmarks perfectly. The calibration module applies Iterative Proportional Fitting (Raking) to force the sample totals to align perfectly with known census constraints.
""",
    "07_variance_estimation.md": """# Case Study 7: Variance Estimation

![Variance Estimation](./07_variance_estimation.png)

## Overview
Providing a point estimate is useless without measuring its precision. The analytical variance module calculates standard errors and 95% confidence intervals, accounting for the complex survey design and prior weighting stages.
""",
    "08_variance_imputation.md": """# Case Study 8: Variance Due to Imputation

![Variance Imputation](./08_variance_imputation.png)

## Overview
Standard variance estimation assumes all data is observed. This specialized module calculates the extra variance injected by the imputation process itself, isolating it from the baseline sampling variance.
""",
    "09_sae.md": """# Case Study 9: Small Area Estimation (SAE)

![Small Area Estimation](./09_sae.png)

## Overview
Direct estimates for small geographic domains are often highly volatile due to small sample sizes. The SAE module borrows strength across regions using EBLUP or Hierarchical Bayes models to produce reliable, smoothed estimates.
""",
    "10_seasonal_adjustment.md": """# Case Study 10: Seasonal Adjustment

![Seasonal Adjustment](./10_seasonal_adjustment.png)

## Overview
Economic indicators fluctuate due to seasonal patterns. This module decomposes the raw signal into Trend, Seasonal, and Irregular components, allowing analysts to observe the true underlying movement of the data.
""",
    "11_disclosure_control.md": """# Case Study 11: Statistical Disclosure Control

![Statistical Disclosure Control](./11_disclosure_control.png)

## Overview
Before publishing microdata, the engine ensures total privacy. The Statistical Disclosure Control (SDC) module detects sensitive cells and applies tabular suppression or differential privacy, preventing the re-identification of any individual entity.
""",
    "frontend_ui_params.md": """# Setting Up the Pipeline: Frontend Configuration

![Frontend UI Parameters](./frontend_ui_params.png)

## Overview
The NovaSurvey engine is powered by a massive backend, but configuring it is incredibly intuitive. The frontend dashboard allows users to easily set up configuration groups, define imputation parameters, toggle specific models, and orchestrate the pipeline via a clean, glassmorphism interface.
""",
    "full_pipeline.md": """# Case Study: Full Pipeline Orchestration

![Full Pipeline Execution](./full_pipeline.png)

## Overview
The true power of the NovaSurvey engine lies in its unified orchestration. This dashboard displays the execution DAG (Directed Acyclic Graph) of the full pipeline running end-to-end. Data flows seamlessly from ingestion, through all 11 statistical modules, directly into secure publishing formats.
""",
    "README.md": """# NovaSurvey Documentation: Comprehensive Case Studies

Welcome to the visual documentation for the NovaSurvey processing engine. These case studies demonstrate the platform's UI and its capabilities across the entire survey lifecycle.

## The 11 Core Modules
1. [Survey Sampling](./01_sampling.md)
2. [Editing & Outliers](./02_editing_outliers.md)
3. [Data Imputation](./03_imputation.md)
4. [Influential Units](./04_influential_units.md)
5. [Nonresponse Weighting](./05_nonresponse_weighting.md)
6. [Calibration](./06_calibration.md)
7. [Variance Estimation](./07_variance_estimation.md)
8. [Variance Due to Imputation](./08_variance_imputation.md)
9. [Small Area Estimation](./09_sae.md)
10. [Seasonal Adjustment](./10_seasonal_adjustment.md)
11. [Statistical Disclosure Control](./11_disclosure_control.md)

## System Configuration & Orchestration
- [Frontend Parameter Setup](./frontend_ui_params.md)
- [Full End-to-End Pipeline Orchestration](./full_pipeline.md)
"""
}

for filename, content in files_content.items():
    with open(os.path.join(case_studies_dir, filename), "w", encoding="utf-8") as f:
        f.write(content)

print("Created 14 markdown files successfully.")
