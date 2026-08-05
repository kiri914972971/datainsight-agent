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
    assert "list_unsaved_kpi_candidates(project_id)" in KPI_TAB_SOURCE
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
