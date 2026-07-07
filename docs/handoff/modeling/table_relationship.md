# Related Documents

- `docs/specs/Table_Relationship_Engine.md`
- `docs/architecture/Architecture.md`
- `docs/harness/PRODUCT_RULES.md`
- `docs/harness/ACCEPTANCE_CRITERIA.md`

# Module

Table Relationship Engine / 数据建模 -> 表关系

# Module Lifecycle

Maintenance

# Current Status

The module is implemented and in Maintenance.
It supports relationship discovery, saved relationship management, manual relationship configuration, relationship validation, and analysis dataset generation.
The service layer uses the unified project dataset registry, so uploaded, appended, cleaned, and joined/analysis datasets can all participate in modeling.
The UI has been refactored into lightweight management flows for saved relationships, recommendations, and manual configuration.

# External Dependencies

- Streamlit UI state through `st.session_state` for transient interaction state only.
- Project workspace persistence through `project_workspace`.
- Project dataset registry in `current_dataset_service.py`.
- Field mapping metadata from `field_mapping_service.py` and `relationship_engine.py` inference helpers.
- Pandas dataframe loading/merging for recommendation, validation, and analysis dataset generation.
- Local project files under `workspace/projects/<project_id>/`, especially `project.json`, `config/table_relationships.json`, and `analysis/analysis_dataset.csv`.

# Key Files

- `app.py`
  - Relationship tab UI.
  - Owns saved relationship management UI, recommendation assistant UI, manual configuration UI, and transient Streamlit state wiring.

- `src/services/relationship_service.py`
  - Relationship service boundary.
  - Owns modelable table listing, dataframe loading, candidate discovery orchestration, column lookup, persistence, validation, normalization, deletion, clearing, and cycle protection.

- `src/engines/relationship_engine.py`
  - Relationship recommendation engine.
  - Scores candidate relationships from field name match, field mapping type match, dtype family match, and uniqueness-ratio proximity.

- `src/services/current_dataset_service.py`
  - DatasetManager-equivalent registry for project datasets.
  - Owns `project_datasets`, `current_analysis_dataset`, dataset sync, dataset loading, generated dataset registration, and legacy current-file compatibility.

- `src/services/analysis_dataset_service.py`
  - Analysis dataset builder.
  - Builds `analysis/analysis_dataset.csv` from confirmed relationships, writes metadata, and registers the result as a `joined` project dataset.

- `src/services/data_source_service.py`
  - Uploaded dataset registration and legacy data-file metadata sync.

- `src/services/append_service.py`
  - Appended dataset generation and registration.

- `src/services/data_quality_service.py`
  - Cleaned dataset generation and registration.

# Implemented Features

- Project table listing is dataset-based.
  - `relationship_service.list_project_tables(project_id)` uses `list_project_datasets(project_id)`.
  - Returned table objects keep legacy UI-compatible fields: `table_id`, `table_name`, `file_id`, `file_name`, `sheet_name`, `rows`, `columns`.
  - Returned table objects also include dataset metadata: `dataset_id`, `dataset_name`, `dataset_type`, `source`, `file_path`, `is_generated`, `source_files`.

- Unified relationship table loading.
  - `load_relationship_table_dataframe(project_id, table_id)` loads through `load_project_dataset_dataframe(project_id, table_id)`.
  - Relationship discovery, field selection, validation, join-plan generation, and analysis dataset building all use this path.

- Supported dataset types for modeling.
  - `uploaded`
  - `appended`
  - `cleaned`
  - `joined`, including `analysis_dataset`

- Automatic relationship discovery.
  - `discover_project_relationships(project_id)` loads all readable project datasets and passes them to `relationship_engine.discover_relationship_candidates`.
  - Recommendation threshold is currently `70`.
  - Recommendation score is a 100-point additive score:
    - exact normalized field name match: 50
    - field mapping type match: 20
    - dtype family match: 20
    - uniqueness ratio proximity: 10
  - Amount fields are excluded from connectable recommendation candidates.
  - Candidate relationship metadata includes dataset type/source/file path fields.

- Recommendation UI.
  - Default view shows only a summary: total possible relationships and high-confidence count.
  - High confidence: `confidence >= 90`.
  - Medium confidence: `75 <= confidence < 90`.
  - Low confidence: `70 <= confidence < 75`.
  - One-click accept saves only high-confidence candidates.
  - Recommendation details are hidden behind a user-controlled checkbox and grouped by confidence.
  - Detail tables show only selection index, relationship, confidence, and advice.
  - Candidate `reason` is shown through a per-group selectbox, not in the main table.
  - Existing `selected_candidate_id` flow remains, so selecting a recommendation still pre-fills manual configuration.

- Saved relationships UI.
  - Saved relationships are displayed as a single dataframe, not per-row containers.
  - Summary includes total, manual count, and auto/recommended count.
  - User selects one relationship in a selectbox before editing or deleting.
  - Edit, delete, and clear-all are centralized buttons.
  - Delete and clear-all both require confirmation before mutation.
  - Empty state shows a lightweight prompt instead of an empty table.

- Manual configuration UI.
  - Table A/Table B selectboxes list all project datasets with Chinese dataset type labels:
    - `uploaded` -> 原始上传
    - `appended` -> 合并结果
    - `cleaned` -> 清洗结果
    - `joined` -> 关联结果
  - Joined datasets show a label indicating they came from relationship/analysis generation.
  - `显示全部字段` checkbox controls field scope.
  - Default field list uses connectable fields only.
  - If no connectable fields exist, UI falls back to all fields and shows a lightweight caption.
  - Joined datasets are allowed and show a warning: confirm the user is not repeatedly joining fields already included.
  - Editing an existing relationship reuses `editing_key` and preselects original table/field when still available.
  - If an old relationship references a missing table, the UI shows an error and allows reselection.

- Relationship persistence.
  - Saved to `config/table_relationships.json`.
  - Mirrored into `project.json` under `table_relationships`.
  - `_normalize_relationship()` keeps legacy relationship field compatibility.
  - New relationships are hydrated with dataset metadata for both sides.
  - Relationship IDs are preserved when editing; new manual relationships get generated IDs during normalization if missing.

- Relationship validation.
  - Prevents `table_a_id == table_b_id`.
  - Validates both tables exist in `list_project_tables`.
  - Validates both relationship fields exist in loaded table columns.
  - Performs basic directed cycle detection and raises `ValueError("该关系会造成循环依赖，请调整表关系。")` for direct or chain back-links.

- Analysis dataset generation.
  - `analysis_dataset_service._load_project_table_frames()` reads model inputs through `relationship_service.list_project_tables()` and `load_relationship_table_dataframe()`.
  - `build_analysis_dataset(project_id)` can use generated datasets as JOIN inputs.
  - Output is persisted to `analysis/analysis_dataset.csv`.
  - Metadata is persisted to `analysis/analysis_dataset_meta.json`.
  - Project metadata is updated under `analysis_dataset`.
  - The generated dataset is registered as current analysis dataset with:
    - `dataset_id`: `analysis_dataset`
    - `dataset_type`: `joined`
    - `source`: `join`
    - `file_path`: `analysis/analysis_dataset.csv`

# Important Design Decisions

- The service layer treats `current_dataset_service.py` as the DatasetManager source of truth. Relationship modeling must not go back to raw `data_files` only.

- `table_id` is intentionally equal to `dataset_id` for relationship modeling. This keeps app-level table selectors and service-level dataset loading aligned.

- Relationship services preserve legacy field names (`file_id`, `file_name`, `sheet_name`) because existing app UI and saved records still depend on them.

- Generated datasets are first-class model inputs. This is required by harness rules and is now implemented for appended, cleaned, joined, and analysis datasets.

- Manual saves use `source = "manual"` even if the user started from a recommended candidate in the manual configuration form. In that case, confidence and reason are preserved, but the final action is user-confirmed manual save.

- One-click high-confidence recommendation saves candidates as recommendation-derived records. Those candidates retain `source = "auto"` from the engine.

- Relationship saving validates against the current dataset registry at save time. If a dataset was deleted or regenerated under a different ID, old relationships may become invalid and should be reselected.

- Analysis dataset generation avoids repeated JOIN of tables already applied in a single build. This is a practical guard, not a full semantic lineage system.

- The current cycle guard is simple directed graph detection over saved relationships. It prevents obvious loops but is not a full graph database or semantic model compiler.

# Data Flow / State Flow

1. Dataset registration
   - Upload -> `data_source_service` -> `set_current_analysis_dataset` / `list_project_datasets`.
   - Append -> `append_service` -> generated `appended_dataset` -> registered as `appended`.
   - Clean -> `data_quality_service` -> generated `cleaned_dataset` -> registered as `cleaned`.
   - Join/build analysis dataset -> `analysis_dataset_service.build_analysis_dataset` -> `analysis_dataset.csv` -> registered as `joined`.

2. Project dataset registry
   - `current_dataset_service.list_project_datasets(project_id)` syncs:
     - uploaded sheets from `data_files`
     - `appended_dataset`
     - `analysis_dataset`
     - discovered generated files: `cleaned_dataset.csv`, `joined_dataset.csv`, `analysis_dataset.csv`
     - existing generated dataset records whose files still exist
   - `project.json` stores `project_datasets` and `current_analysis_dataset`.

3. Relationship modeling table list
   - UI calls `list_project_tables(project_id)`.
   - Relationship service converts project datasets into table-shaped records for UI and engine compatibility.

4. Recommendation
   - Candidate discovery calls `discover_project_relationships(project_id)`.
   - Service loads each readable dataset dataframe.
   - Engine profiles fields and scores pairwise column candidates.
   - UI groups recommendations into high/medium/low confidence.

5. Saved relationship management
   - UI loads `load_table_relationships(project_id)`.
   - Saved relationships populate management dataframe and relationship action selectbox.
   - Edit stores the selected relationship ID in Streamlit session state.
   - Delete stores pending delete state, then confirmation calls `delete_table_relationship`.
   - Clear stores pending clear state, then confirmation calls `clear_table_relationships`.

6. Manual configuration
   - Selected candidate state controls optional recommendation prefill.
   - Editing state controls edit prefill.
   - Table selectboxes use `table_id` values from `list_project_tables`.
   - Field selectboxes call `get_project_table_columns`.
   - Save calls `save_table_relationships` with either merged new records or replacement record.

7. Analysis dataset generation
   - `build_analysis_dataset` loads confirmed relationships and project table frames.
   - Current analysis dataset is used as base when possible; otherwise first relationship/table fallback is used.
   - Joins are applied iteratively using confirmed relationship fields.
   - Metadata, join plan, applied relationships, and health checks are stored.
   - Result registers back into DatasetManager as joined, so it can later be selected in 表关系 and modelled further.

# Known Issues

- Graph visualization described in `docs/specs/Table_Relationship_Engine.md` is not currently implemented in the inspected code. Current UI uses tables/selectboxes.

- Spec mentions content/value matching and orphan-record checks as product goals. Current recommendation engine primarily uses field names, inferred/confirmed field mapping types, dtype family, and uniqueness ratio. Detailed value-overlap scoring is only used later for join-plan risk/match statistics, not as a recommendation score input.

- Saved relationship `source` semantics differ by path:
  - one-click accepted candidates usually remain `auto`
  - manual form saves `manual`, even when initialized from a candidate
  This is intentional currently, but future analytics on source counts should account for it.

- Generated joined datasets can be used for further modeling. This is supported but can create user-level semantic duplication if users model a joined output against tables already included in it. UI warns but does not block; service validation handles only structural validity and cycle detection.

- Cycle detection is basic directed detection. It prevents obvious loops but does not understand star schemas, bridge tables, semantic grain, or lineage beyond saved relationship edges.

- Relationship deletion or clearing does not delete generated `analysis_dataset.csv`. UI tells users to regenerate analysis dataset after relationship changes. Downstream stale dataset invalidation is message-based, not enforced.

- Some old saved relationships may lack dataset metadata. `_normalize_relationship()` tolerates missing metadata, and `_hydrate_relationship_metadata()` fills it when saving if tables still exist.

# Future Improvements

- Add a compact relationship graph or lineage preview if product requirements still require relationship visualization.

- Add explicit stale-analysis-dataset state after relationship mutations instead of only showing messages.

- Refine relationship `source` semantics for relationships initialized from recommendations but saved manually.

- Extend recommendation scoring with actual value-overlap evidence if content matching remains a product goal.

- Add stronger semantic modeling controls for joined datasets to reduce accidental duplicate JOINs across generated outputs.

# Do Not Break

- Do not make relationship modeling read only `data_source_service.list_project_data_files()` again. It must remain dataset-registry based.

- Do not remove legacy-compatible fields from `list_project_tables` or saved relationship records: `table_id`, `table_name`, `file_id`, `file_name`, `sheet_name`, `rows`, `columns`, `table_a_file_id`, `table_b_file_id`, etc.

- Do not prevent generated datasets from participating in modeling. `appended`, `cleaned`, and `joined` datasets must remain selectable and loadable.

- Do not bypass `load_relationship_table_dataframe`; it is the unified read path for relationship modeling.

- Do not remove relationship validation for same-table relationships, missing fields, missing tables, or cycles.

- Do not remove legacy relationship migration in `_migrate_legacy_relationship`.

- Do not change `project_datasets` / `current_analysis_dataset` semantics without updating all dataset-producing services.

- Do not rely on Streamlit `session_state` as durable storage. Relationship truth lives in `config/table_relationships.json` and `project.json`; session state is only for transient UI state.

- Do not auto-delete or mutate source datasets when saving/deleting/clearing relationships. Relationship operations should only mutate relationship metadata.

- Do not silently accept all recommendation candidates by default. Current UX intentionally accepts only high-confidence candidates with one click.

# Last Updated

2026-06-29
