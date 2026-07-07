# Module

Data Quality Center / 项目数据 -> 数据质量

# Related Documents

- `docs/specs/Data_Quality_Engine.md`
- `docs/architecture/Architecture.md`
- `docs/harness/PRODUCT_RULES.md`
- `docs/harness/ACCEPTANCE_CRITERIA.md`
- `src/services/data_quality_service.py`
- `src/services/current_dataset_service.py`
- `app.py`

# Module Lifecycle

Maintenance

# Current Status

The Data Quality Center is implemented inside the current Project Data workspace tab.
It runs against the project-level current analysis dataset, not against a standalone legacy preview dataframe.
The active read path is `load_current_analysis_dataframe(project_id)`, and dataset metadata comes from `get_current_analysis_dataset(project_id)`.

The current UI has six internal sub-tabs:

- 总览
- 缺失值
- 重复值
- ID识别
- 异常值
- 数据修复

The module supports rule-based diagnosis, user-controlled cleaning plans, preview-only simulation, and generation of a separate `cleaned_dataset.csv`.
It does not mutate uploaded, appended, joined, or current source datasets during preview.

# External Dependencies

- Streamlit UI and `st.session_state` for transient cleaning plan and ID override state.
- Pandas for dataframe profiling, preview, missing-value operations, duplicate handling, and cleaning operations.
- Plotly for outlier visualizations in the current app UI.
- `src.outlier.calculate_iqr_bounds` for IQR bounds.
- `src.services.current_dataset_service` for dataset registry and current dataset loading:
  - `get_current_analysis_dataset`
  - `load_current_analysis_dataframe`
  - `register_project_dataset`
  - `set_current_analysis_dataset`
- `src.project_workspace` for project metadata persistence.
- Local project files under `workspace/projects/<project_id>/`, especially:
  - `project.json`
  - `analysis/cleaned_dataset.csv`
  - `analysis/cleaned_dataset_meta.json`

# Key Files

- `app.py`
  - Owns the Data Quality Center UI.
  - Active implementation is the later `render_project_data_quality_tab(project_id)` definition.
  - Wires Streamlit session state for missing-value plans, duplicate handling plans, manual ID overrides, outlier handling selection, preview tables, cleaned dataset generation, download, and "set as current" action.

- `src/services/data_quality_service.py`
  - Service boundary for current Data Quality Center logic.
  - Owns diagnosis helpers, ID detection and override helpers, IQR numeric field filtering, missing-value plan helpers, duplicate handling helpers, cleaning operation execution, cleaned dataset creation, metadata loading, and current-dataset registration.
  - Also forwards several legacy `src.data_quality` helpers for compatibility.

- `src/services/current_dataset_service.py`
  - DatasetManager-equivalent registry.
  - Owns `project_datasets`, `current_analysis_dataset`, generated dataset registration, dataset loading, and legacy current-file compatibility.

- `src/outlier.py`
  - Provides IQR bound calculation used by outlier diagnosis and handling.

- `tests/test_data_quality_service.py`
  - Covers missing-value diagnosis/handling, duplicate handling, ID detection and override helpers, IQR filtering, outlier handling, cleaned dataset registration, and setting cleaned data as current.

- `tests/test_current_dataset_service.py`
  - Covers dataset registry/current dataset behavior used by cleaned dataset registration.

# Implemented Features

- Current dataset based quality analysis.
  - The module reads the selected current analysis dataset using `load_current_analysis_dataframe(project_id)`.
  - Dataset summary displays current dataset name, type, row count, column count, and saved path.
  - Supports uploaded, appended, cleaned, and joined datasets when registered through `project_datasets`.

- Data quality overview.
  - Shows score, missing value count, duplicate count, final excluded ID field count, invalid/suspicious field count, outlier field count, and outlier count.
  - Score is a rule-based deduction from missing values, duplicate rows, final ID exclusions, invalid columns, and IQR outlier count.
  - Generates rule-based repair suggestions without AI calls.

- Missing-value analysis.
  - `summarize_missing_values_for_quality(df)` emits field name, dtype, missing count, missing ratio, and recommended action.
  - Recommendation logic:
    - missing ratio >= 80%: delete field or reacquire source
    - 30% <= missing ratio < 80%: cautious fill with business judgment
    - lower nonzero missing ratio: numeric mean/median, category mode, date fields not casually filled
    - zero missing: no handling needed
  - Missing sample preview includes an original row index column.

- Missing-value handling plan.
  - Stored in `st.session_state["missing_value_plan"]`.
  - Reset per project through `missing_value_plan_project_id`.
  - Supports:
    - no handling
    - drop selected field
    - drop rows missing the selected field
    - mean fill
    - median fill
    - mode fill
    - custom fixed fill
  - Service helpers:
    - `upsert_missing_value_plan_item`
    - `remove_missing_value_plan_item`
    - `missing_value_plan_to_operations`
    - `apply_missing_value_plan_preview`
    - `summarize_missing_value_plan_effect`
    - `format_missing_value_plan`

- Duplicate analysis.
  - `summarize_duplicates_for_quality(df)` uses full-row duplicate detection.
  - It distinguishes:
    - `duplicate_group_rows`: all rows that belong to duplicate groups, using `df.duplicated(keep=False)`
    - `duplicate_count`: extra rows that would be removed by keep-first de-duplication, using `df.duplicated(keep="first")`
    - `duplicate_ratio`: duplicate-group rows divided by total rows
  - Duplicate preview shows records in duplicate groups and includes stable original row index.

- Duplicate handling plan.
  - Stored in `st.session_state["duplicate_handling_plan"]`.
  - Reset per project through `duplicate_handling_plan_project_id`.
  - Supported methods:
    - `none`
    - `drop_all_duplicates`
    - `drop_selected_rows`
  - "删除完全重复行（每组保留第一条）" maps to `df.drop_duplicates(keep="first")`.
  - Selected-row deletion uses stable original dataframe index through `drop_rows_by_index`; it does not use displayed table position.
  - Duplicate preview is split into:
    - duplicate row preview before handling
    - duplicate-group post-processing preview
    - full-table post-processing preview
  - Service helpers:
    - `upsert_duplicate_handling_plan`
    - `duplicate_handling_plan_to_operations`
    - `apply_duplicate_handling_plan_preview`
    - `apply_duplicate_group_preview`
    - `summarize_duplicate_handling_effect`
    - `format_duplicate_handling_plan`

- ID field detection.
  - Auto detection uses field-name hints such as `id`, 编号, 编码, 工号, 订单号, 单号, 流水号, 客户号, 用户号, 销售工号, `customer_id`, `user_id`, `employee_id`, `order_id`.
  - A field can also be detected as ID when unique ratio is greater than 90%, unless it looks like a business measure.
  - Date-like fields are excluded from ID detection.
  - Business measure names such as 金额, 销售额, 单价, 成本, 利润, 数量, `amount`, `price`, `quantity`, `revenue`, `cost`, and `profit` are protected from uniqueness-only ID classification.

- Manual ID override.
  - UI allows selecting any current dataframe column.
  - User can mark a field as ID or cancel an ID mark.
  - State is held in:
    - `st.session_state["manual_id_columns"]`
    - `st.session_state["manual_non_id_columns"]`
  - Final ID exclusions are calculated as:

    ```text
    final_id_columns = auto_detected_id_columns + manual_id_columns - manual_non_id_columns
    ```

  - `manual_non_id_columns` wins if a field appears in both manual lists.
  - Reset clears both manual lists and restores auto-detected ID exclusions.
  - Cancelled auto-ID fields appear in the "已人工取消 ID 标记字段" section.
  - Final ID exclusions feed overview counts, repair suggestions, IQR outlier field filtering, and excluded-ID notices.

- Outlier diagnosis.
  - IQR is the implemented outlier detection method.
  - Numeric candidates are filtered through `get_iqr_numeric_measure_columns(df, final_id_columns)`.
  - Final ID fields are excluded.
  - ID-like names are also excluded by `is_iqr_measure_column`, including ID, 工号, 编号, 编码, 代码, 单号, 订单号, 客户号, 用户ID, 手机号, phone, mobile, and tel.
  - Outlier summary includes Q1, Q3, IQR, lower bound, upper bound, outlier count, and outlier ratio.
  - The UI explains that IQR outliers are statistical signals and not necessarily erroneous data.

- Outlier visualization and handling.
  - Uses Plotly visualizations in the current UI, not the old default matplotlib boxplot.
  - Shows an interactive box plot and distribution view, and can show a time distribution if a date-like field is available.
  - Outlier sample preview includes original row index.
  - Supported handling choices:
    - no handling
    - delete outlier rows
    - Winsorize values to IQR lower/upper bounds
    - add `is_outlier_<column>` marker column
  - Outlier operation is appended to `operations` only when the user selects a handling method.

- Data repair tab.
  - Shows a cleaning plan summary grouped by:
    - missing-value handling
    - ID field adjustment
    - duplicate handling
    - outlier handling
  - Shows expected processing impact using `apply_quality_operations(quality_df, operations)`.
  - Shows final processed preview from a copy of the dataframe.
  - The generate section intentionally hides raw list/dict/JSON operation objects and only shows a user-facing step count and explanation.

- Cleaned dataset generation.
  - Button calls `create_cleaned_dataset(project_id, operations)`.
  - Writes:
    - `workspace/projects/<project_id>/analysis/cleaned_dataset.csv`
    - `workspace/projects/<project_id>/analysis/cleaned_dataset_meta.json`
  - Does not overwrite uploaded files, appended dataset files, or joined/analysis dataset files.
  - Stores source dataset metadata, processing steps, grouped actions, before/after row and column counts, created time, and file size.
  - Registers the cleaned dataset with `register_project_dataset` as:
    - `dataset_id`: `cleaned_dataset`
    - `dataset_name`: `cleaned_dataset.csv`
    - `dataset_type`: `cleaned`
    - `source`: `quality_cleaning`
    - `file_path`: `analysis/cleaned_dataset.csv`
  - UI can download the cleaned CSV, preview it, and set it as current analysis dataset through `set_cleaned_dataset_as_current(project_id)`.

# Important Design Decisions

- Current implementation is dataset-registry based. Data quality must continue reading through `load_current_analysis_dataframe(project_id)`.

- The service layer is the source for pure data-quality logic. The app layer owns Streamlit state and UI wiring.

- Preview operations operate on dataframe copies. Preview must not mutate source/current dataframe content.

- ID fields are analysis exclusions, not cleaning deletions. Manual ID overrides should affect statistical analysis and IQR candidate filtering, not remove columns from generated data.

- Duplicate "delete all duplicates" means keep the first row in each fully duplicated group. It must not use `df[~df.duplicated(keep=False)]`, because that would remove every row in a duplicate group.

- Selected duplicate deletion is index based. The UI adds an original row index column and the service uses `drop_rows_by_index` against the dataframe index.

- The cleaned dataset is a generated project dataset, not a mutation of the selected current dataset.

- The Data Repair tab is both a planning summary and the generation entry point. Raw internal `operations` objects are not user-facing UI.

- The module keeps several compatibility forwards to `src.data_quality` in `data_quality_service.py`; remove them only after confirming all app imports and tests no longer rely on them.

# Data Flow / State Flow

1. Dataset selection
   - Project Data / Data Source selects a current analysis dataset.
   - `current_dataset_service` persists it under `current_analysis_dataset`.
   - Data Quality reads it through `get_current_analysis_dataset(project_id)` and `load_current_analysis_dataframe(project_id)`.

2. Initial diagnosis
   - Auto ID detection runs first.
   - Manual ID override state is normalized against current dataframe columns.
   - Final ID exclusions are computed.
   - Missing, duplicate, invalid-field, repair suggestion, and IQR outlier summaries are computed from the current dataframe and final ID set.

3. Session state
   - `missing_value_plan`: list of per-column missing handling decisions.
   - `missing_value_plan_project_id`: resets the missing plan when project changes.
   - `duplicate_handling_plan`: one active duplicate handling plan.
   - `duplicate_handling_plan_project_id`: resets duplicate plan when project changes.
   - `manual_id_columns`: user-marked ID fields.
   - `manual_non_id_columns`: user-cancelled ID fields.
   - `manual_id_columns_project_id`: resets manual ID state when project changes.
   - `project_quality_message`: transient success message after generation or set-current action.

4. Operation assembly
   - Base `operations` are assembled from:
     - `missing_value_plan_to_operations(missing_value_plan)`
     - `duplicate_handling_plan_to_operations(duplicate_handling_plan)`
   - Outlier operation is appended only when the current outlier UI selection is not "不处理".
   - Manual ID overrides are not converted into cleaning operations.

5. Preview
   - Missing preview uses `apply_missing_value_plan_preview`.
   - Duplicate preview uses `apply_duplicate_handling_plan_preview` and `apply_duplicate_group_preview`.
   - Repair tab preview uses `apply_quality_operations(quality_df, operations)` and displays expected before/after effects.

6. Cleaned dataset generation
   - `create_cleaned_dataset(project_id, operations)` loads the current analysis dataframe again.
   - Applies operations through `apply_quality_operations`.
   - Writes cleaned CSV and metadata under `analysis/`.
   - Updates project metadata under `cleaned_dataset`.
   - Registers `cleaned_dataset` in `project_datasets`.

7. Set cleaned dataset as current
   - UI calls `set_cleaned_dataset_as_current(project_id)`.
   - Service calls `set_current_analysis_dataset`.
   - `current_analysis_dataset` and legacy current-file fields are kept in sync by `current_dataset_service`.

# Known Issues

- Current implementation differs from original specification. The spec mentions broader checks such as Z-score outliers, detailed data type checks, date anomaly checks, unique-value anomaly checks, and historical data-volume anomaly checks. The inspected implementation focuses on missing values, duplicates, ID detection/override, invalid columns, IQR outliers, rule-based suggestions, and cleaned dataset generation.

- Current implementation differs from original specification. "Data Quality Score" exists as a rule-based deduction score, but it is not a full quality model over completeness, consistency, accuracy, and validity dimensions.

- Current implementation differs from original specification. Data type repair and restore-original-data flows are not implemented as standalone repair actions in the current Data Quality Center.

- Manual ID cancellation can remove a field from final ID exclusions, but the outlier selector still applies separate ID-like name filtering through `is_iqr_measure_column`. For example, a cancelled `销售工号` numeric field may still be excluded from IQR because its name matches 工号-like exclusion rules. The UI preserves a clear explanatory caption for this case.

- Manual ID override state is transient Streamlit session state. It is not persisted into `project.json`; switching projects resets it, and browser/session reloads may lose it.

- There are two `render_project_data_quality_tab` definitions in `app.py`; the later one is the active runtime definition. Avoid editing the earlier legacy copy unless intentionally cleaning dead code.

- Some source files contain historical mojibake-looking Chinese text in terminal output because of encoding display. The app source itself should be treated carefully when editing Chinese strings.

# Future Improvements

- Persist manual ID override configuration in project metadata if users expect ID decisions to survive browser reloads or team handoff.

- Add a dedicated data type repair flow if the original Data Quality Engine spec remains in scope.

- Add date anomaly checks and date-specific repair suggestions.

- Add Z-score or configurable outlier methods if needed, while keeping IQR behavior stable.

- Add clearer lineage display for cleaned datasets, including which current dataset they were generated from and whether they are stale after source selection changes.

- Consider extracting the active Data Quality UI from `app.py` into a dedicated page/module once behavior stabilizes. Do not do this as a bug fix.

- Add UI-level tests for Streamlit duplicate selection and manual ID override if a lightweight Streamlit testing pattern is adopted.

# Do Not Break

- Do not move Data Quality Center out of Project Data / 数据质量.

- Do not remove internal sub-tabs: 总览, 缺失值, 重复值, ID识别, 异常值, 数据修复.

- Do not make the module read only uploaded/raw files. It must continue using `current_analysis_dataset` and `load_current_analysis_dataframe(project_id)`.

- Do not bypass `project_datasets` when creating or selecting cleaned datasets.

- Do not overwrite uploaded, appended, joined, or original current datasets during cleaning.

- Do not mutate source/current dataframe content during preview.

- Do not show raw `operations`, dicts, or JSON debug output in the generate-cleaned-dataset section.

- Do not change duplicate removal semantics away from keep-first full-row duplicate handling.

- Do not make selected duplicate deletion position based. It must remain stable-original-index based.

- Do not remove manual ID override or make manual cancellation subordinate to auto ID detection.

- Do not remove final ID exclusions from IQR numeric field filtering.

- Do not remove IQR metrics, outlier preview, outlier handling, before/after comparison, or Plotly outlier visualization.

- Do not treat ID field adjustment as a data deletion operation.

- Do not remove cleaned dataset download, preview, or "set as current analysis dataset" actions.

# Last Updated

2026-06-29
