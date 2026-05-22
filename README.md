# NovaSurvey Documentation

Welcome to the official documentation repository for the **NovaSurvey Statistical Engine**. This repository is the central hub for all methodology, architecture, and user guides related to NovaSurvey.

## Repository Structure

The documentation is organized into the following sections:

### 1. [Methodology Guides](./methodology_guides/)
This folder contains the theoretical foundations and official reference methodology PDFs upon which NovaSurvey is built (e.g., G-Est, Banff, G-Sam, G-Confid). These documents provide the mathematical proofs and established frameworks for official statistics.

### 2. [Module Manuals](./module_manuals/)
Markdown manuals specific to each of the 8 core NovaSurvey modules. These explain how the theoretical methodology is specifically implemented within the engine's Python/Polars backend.
- Sampling
- Editing
- Imputation
- Calibration & Weighting
- Variance Estimation
- Seasonal Adjustment
- Small Area Estimation (SAE)
- Statistical Disclosure Control (SDC)

### 3. [User Guides](./user_guides/)
Help documentation, integration guides, and tutorials for interacting with both the NovaSurvey Command Center (GUI) and the Headless Engine (CLI/API).

### 4. [Architecture](./architecture/)
High-level system design documents, certification reports, development roadmaps, and frontend structure overviews. 

---

*For the mathematical source code, please refer to the private `NovaSurvey/core` repository. For the API and Desktop Application code, please refer to the `NovaSurvey/engine` repository.*
