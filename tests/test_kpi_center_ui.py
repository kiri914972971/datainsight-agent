import ast
from pathlib import Path

from src.exploration import calculate_dataframe_height


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
APP_SOURCE = APP_PATH.read_text(encoding="utf-8")


def _function_source(function_name):
    tree = ast.parse(APP_SOURCE)
    node = next(
        item
        for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == function_name
    )
    return ast.get_source_segment(APP_SOURCE, node)


KPI_TAB_SOURCE = _function_source("render_kpi_center_tab")
METRIC_TAB_SOURCE = _function_source("render_metric_dictionary_tab")
METRIC_CENTER_SOURCE = _function_source("render_metric_center_tab")


def test_kpi_summary_has_five_unambiguous_cards():
    for label in ("自动推荐", "已保存", "已启用", "可供下游使用", "校验异常"):
        assert f'.metric("{label}"' in KPI_TAB_SOURCE
    assert 'metric("计算规则"' not in KPI_TAB_SOURCE


def test_candidate_and_saved_sections_use_independent_sources():
    assert "generate_project_kpi_candidates(" in KPI_TAB_SOURCE
    assert "filter_unsaved_kpi_candidates(" in KPI_TAB_SOURCE
    assert "saved_kpis = load_kpi_definitions(project_id)" in KPI_TAB_SOURCE
    assert "merged_project_kpis" not in KPI_TAB_SOURCE


def test_candidate_table_defaults_unselected_and_has_no_enabled_control():
    candidate_block = KPI_TAB_SOURCE.split('st.subheader("自动推荐候选")', 1)[1].split(
        'st.subheader("已保存指标")', 1
    )[0]
    assert '"选择": False' in candidate_block
    assert 'CheckboxColumn("选择", default=False)' in candidate_block
    assert "启用状态" not in candidate_block
    assert '"当前状态": "待确认"' in candidate_block


def test_candidate_save_processes_only_selected_rows():
    assert 'if not row.get("选择")' in KPI_TAB_SOURCE
    assert "save_selected_kpi_candidates(" in KPI_TAB_SOURCE
    assert "请至少选择一个候选指标。" in KPI_TAB_SOURCE
    assert "保存选中指标" in KPI_TAB_SOURCE


def test_saved_table_shows_validation_and_disables_status_metadata():
    assert "校验状态" in KPI_TAB_SOURCE
    assert "校验说明" in KPI_TAB_SOURCE
    assert "校验通过" in KPI_TAB_SOURCE
    assert "校验异常" in KPI_TAB_SOURCE
    assert "待完善" in KPI_TAB_SOURCE
    assert 'disabled=["校验状态", "校验说明", "创建方式"]' in KPI_TAB_SOURCE
    assert "保存指标修改" in KPI_TAB_SOURCE


def test_candidate_and_saved_editors_reuse_dynamic_height():
    assert KPI_TAB_SOURCE.count("height=calculate_dataframe_height(") == 2
    assert calculate_dataframe_height(2) < calculate_dataframe_height(9)
    assert calculate_dataframe_height(24) == calculate_dataframe_height(12)


def test_editor_and_delete_keys_bind_project_and_current_signature():
    assert 'kpi_candidate_editor_{project_id}_{candidate_signature}' in KPI_TAB_SOURCE
    assert 'kpi_saved_editor_{project_id}_{saved_signature}' in KPI_TAB_SOURCE
    assert 'delete_kpi_select_{project_id}_{saved_signature}' in KPI_TAB_SOURCE


def test_metric_dictionary_page_uses_only_saved_kpis():
    assert "project_kpis = load_kpi_definitions(project_id)" in METRIC_TAB_SOURCE
    assert "merged_project_kpis" not in METRIC_TAB_SOURCE
    assert "当前尚未保存指标计算规则" in METRIC_TAB_SOURCE


def test_metric_center_copy_does_not_claim_dashboard_integration_is_complete():
    assert "已保存、已启用且校验通过" in METRIC_CENTER_SOURCE
    assert "将逐步接入" in METRIC_CENTER_SOURCE
    assert "都会优先使用" not in METRIC_CENTER_SOURCE


def test_delete_warning_points_to_metric_dictionary_without_cascade_delete():
    assert "该指标可能存在关联的指标语义定义" in KPI_TAB_SOURCE
    assert "delete_metric_definition" not in KPI_TAB_SOURCE


def test_new_count_aggregations_are_available_with_chinese_labels():
    assert "AGGREGATION_LABELS" in KPI_TAB_SOURCE
    assert "SUPPORTED_AGGREGATIONS" in KPI_TAB_SOURCE
    assert "非空计数" in KPI_TAB_SOURCE
    assert "记录行数" in KPI_TAB_SOURCE
    assert "去重计数" in KPI_TAB_SOURCE


def test_count_rows_submission_clears_source_and_uses_row_type():
    assert 'new_aggregation == "count_rows"' in KPI_TAB_SOURCE
    assert '"" if new_aggregation == "count_rows"' in KPI_TAB_SOURCE
    assert '"field_type": new_field_type' in KPI_TAB_SOURCE
    assert "NO_SOURCE_FIELD_LABEL" in KPI_TAB_SOURCE


def test_new_form_uses_one_source_options_helper_instead_of_manual_lists():
    assert "resolve_kpi_source_selection(" in KPI_TAB_SOURCE
    assert "kpi_field_roles" in KPI_TAB_SOURCE
    assert "new_source_field_options" not in KPI_TAB_SOURCE
    assert "selected_field_type_options" not in KPI_TAB_SOURCE


def test_source_and_field_type_controls_rerun_before_form_submission():
    source_control = KPI_TAB_SOURCE.index('new_source_field = source_columns[0].selectbox(')
    field_type_control = KPI_TAB_SOURCE.index('source_columns[1].selectbox(')
    form_start = KPI_TAB_SOURCE.index('with st.form(f"add_kpi_form_')

    assert source_control < form_start
    assert field_type_control < form_start
    assert "get_kpi_source_field_type(" in KPI_TAB_SOURCE
    assert '"字段类型",\n            [new_field_type],\n            disabled=True' in KPI_TAB_SOURCE


def test_new_form_state_is_project_scoped_and_invalid_source_is_reset():
    assert 'source_state_key = f"add_kpi_source_field_{project_id}"' in KPI_TAB_SOURCE
    assert 'key=f"add_kpi_aggregation_{project_id}"' in KPI_TAB_SOURCE
    assert 'st.session_state.get(source_state_key)' in KPI_TAB_SOURCE
    assert 'st.session_state[source_state_key] = source_selection["selected_option"]' in KPI_TAB_SOURCE


def test_no_compatible_source_disables_add_button():
    assert "当前分析数据集中没有适用于该聚合方式的字段。" in KPI_TAB_SOURCE
    assert "disabled=not has_compatible_fields" in KPI_TAB_SOURCE


def test_count_explanation_is_selected_outside_form_for_dynamic_rerun():
    aggregation_control = KPI_TAB_SOURCE.index('new_aggregation = st.selectbox(')
    form_start = KPI_TAB_SOURCE.index('with st.form(f"add_kpi_form_')
    assert aggregation_control < form_start
    assert "AGGREGATION_HELP_TEXTS.get(new_aggregation)" in KPI_TAB_SOURCE
    assert "if aggregation_help:" in KPI_TAB_SOURCE


def test_missing_id_candidate_guidance_uses_complete_generated_candidates():
    assert "missing_entity_id_candidate_names(generated_kpis)" in KPI_TAB_SOURCE
    assert "当前字段映射中未识别到订单 ID 或客户 ID" in KPI_TAB_SOURCE
    assert "‘成交客户数’通常应按业务定义求和，而不是去重计数" in KPI_TAB_SOURCE


def test_legacy_count_has_non_migration_guidance():
    assert "已保存规则中存在非空计数指标" in KPI_TAB_SOURCE
    assert "请将聚合方式改为去重计数" in KPI_TAB_SOURCE
