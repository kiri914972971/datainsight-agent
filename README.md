# DataInsight Agent

DataInsight Agent is a Streamlit-based data analysis assistant designed for business users, analysts, and data-oriented product teams. It helps users upload tabular data, inspect quality issues, explore trends, generate charts, define metrics, and export reusable analysis outputs without building a full BI pipeline first.

> Status: MVP / Work in Progress

## Project Overview

DataInsight Agent focuses on the early-stage analytics workflow: getting from a raw CSV or Excel file to a trustworthy business-facing insight. The project combines data profiling, quality checks, exploratory analysis, metric management, relationship modeling, and report/dashboard export into one local application.

The current version is a working MVP with multiple analysis engines and service-layer tests. It is still evolving toward a more polished, modular analytics workspace.

## Target Users

- Business analysts who need to inspect unfamiliar datasets quickly.
- Operations, sales, or product teams that work with spreadsheet-heavy reporting.
- Founders or small teams that need lightweight analytics before investing in a full BI stack.
- Job portfolio reviewers who want to see applied data product thinking, not only isolated scripts.

## Core Pain Points

- Raw spreadsheet data often contains missing values, inconsistent fields, duplicate records, and unclear business meaning.
- Non-technical users need analysis guidance, not just charts.
- Many small-team analytics workflows are scattered across Excel files, notebooks, screenshots, and manual reports.
- Metric definitions, field mappings, and table relationships are easy to lose when analysis is repeated.

## Core Features

- Data upload and preview for CSV, XLSX, and XLS files.
- Automatic field type detection and dataset profiling.
- Data quality checks for missing values, duplicates, outliers, ID-like fields, and suspicious columns.
- Exploratory data analysis with descriptive statistics and chart suggestions.
- Business question analysis for common metric and dimension breakdowns.
- Metric dictionary and KPI center for reusable business definitions.
- Field mapping and table relationship engines for multi-table analysis preparation.
- Dashboard and report export workflows, including Excel/PowerPoint/Word-oriented templates.
- Optional AI-assisted insight generation through user-provided API settings.

## Tech Stack

- Python
- Streamlit
- pandas
- Plotly
- openpyxl / xlrd
- python-docx / python-pptx
- pytest

## Project Structure

```text
DataInsightAgent/
├── app.py                    # Streamlit application entry point
├── requirements.txt          # Python dependencies
├── src/                      # Core services, engines, exporters, and utilities
├── tests/                    # Regression and service-layer tests
├── docs/                     # Product notes, architecture, specs, and screenshots
├── templates/                # Export templates
├── outputs/                  # Local generated outputs, ignored except .gitkeep
└── workspace/                # Local runtime workspace, ignored except .gitkeep
```

## Screenshots

Screenshots are stored under `docs/` and can be used in a portfolio case study.

![Analysis Dataset UI](docs/analysis-dataset-ui.png)
![Business Question UI](docs/business-question-ui.png)
![KPI Center UI](docs/kpi-center-ui.png)
![Dashboard Engine UI](docs/phase12-dashboard-engine-ui.png)

## Setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Python 3.11 or 3.12 is recommended. Python 3.13 may have compatibility issues with some data analysis packages.

## AI Usage

AI features are optional. The application accepts an API key, model name, and base URL from the UI when the user wants AI-assisted insight generation. Secrets should be provided at runtime or through local-only configuration files and should never be committed to the repository.

## Current Progress

- MVP application is implemented in Streamlit.
- Core engines and services are organized under `src/`.
- Regression tests exist for analysis datasets, append workflows, data quality, KPI logic, relationship modeling, dashboard generation, and business question analysis.
- Documentation includes product requirements, architecture notes, implementation specs, and handoff materials.

## Roadmap

- Improve onboarding and sample-data experience for first-time users.
- Add clearer project/session management around uploaded datasets.
- Expand data lineage and reproducibility for generated reports.
- Improve AI prompt governance, error handling, and provider configuration.
- Add more portfolio-ready screenshots and a short demo walkthrough.
- Continue refactoring large UI sections into smaller, testable modules.

## GitHub Publishing Notes

Before publishing publicly:

- Do not commit `.env`, `.streamlit/secrets.toml`, virtual environments, browser debug folders, logs, local outputs, or private workspace data.
- Review any sample spreadsheets or generated reports for private business data.
- Keep API keys and model provider settings outside Git history.

## License

No license has been selected yet. Add a license before encouraging external reuse.
