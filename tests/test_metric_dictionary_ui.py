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


METRIC_TAB_SOURCE = _function_source("render_metric_dictionary_tab")
KPI_TAB_SOURCE = _function_source("render_kpi_center_tab")


def test_metric_dictionary_has_no_create_metric_entry_or_submission_path():
    assert 'st.subheader("新增指标")' not in METRIC_TAB_SOURCE
    assert "add_metric_form_" not in METRIC_TAB_SOURCE
    assert "form_submit_button" not in METRIC_TAB_SOURCE
    assert "add_metric_definition(" not in METRIC_TAB_SOURCE
    assert "不关联指标计算规则" not in METRIC_TAB_SOURCE


def test_page_copy_has_fixed_semantic_and_calculation_boundaries():
    assert "指标语义字典用于维护已保存指标的业务定义、别名和业务称呼" in METRIC_TAB_SOURCE
    assert "来源字段、聚合方式和计算公式请前往【指标计算规则】维护" in METRIC_TAB_SOURCE
    assert "语义定义不会创建新的计算指标" in METRIC_TAB_SOURCE


def test_final_table_has_required_columns_and_read_only_rule_columns():
    for column in (
        "指标名称",
        "指标类型",
        "业务定义",
        "计算公式",
        "别名",
        "关联指标计算规则",
        "关联状态",
        "启用状态",
    ):
        assert f'"{column}"' in METRIC_TAB_SOURCE
    assert 'disabled=["计算公式", "关联指标计算规则", "关联状态"]' in METRIC_TAB_SOURCE
    assert '"KPI ID"' not in METRIC_TAB_SOURCE


def test_formula_is_derived_from_kpi_and_never_edited_in_dictionary():
    assert "build_metric_formula_summary(" in METRIC_TAB_SOURCE
    save_block = METRIC_TAB_SOURCE.split('if st.button(\n            "保存指标语义字典"', 1)[1]
    assert '"linked_kpi_id":' not in save_block
    assert '"linked_kpi_name":' not in save_block


def test_semantic_table_uses_dynamic_height_without_empty_table():
    assert "if current_metrics:" in METRIC_TAB_SOURCE
    assert "height=calculate_dataframe_height(len(metric_rows))" in METRIC_TAB_SOURCE
    assert calculate_dataframe_height(2) < calculate_dataframe_height(9)
    assert calculate_dataframe_height(24) == calculate_dataframe_height(12)


def test_empty_and_historical_states_use_required_guidance():
    assert "当前尚未保存指标计算规则。请先前往【指标计算规则】确认并保存指标" in METRIC_TAB_SOURCE
    assert "当前项目没有可关联的已保存指标计算规则。以下历史语义定义已保留" in METRIC_TAB_SOURCE
    assert "检测到尚未维护业务语义的已保存指标" in METRIC_TAB_SOURCE


def test_editor_delete_and_messages_are_project_scoped():
    assert 'metric_dictionary_editor_{project_id}' in METRIC_TAB_SOURCE
    assert 'save_metric_dictionary_{project_id}' in METRIC_TAB_SOURCE
    assert 'metric_dictionary_message_{project_id}' in METRIC_TAB_SOURCE
    assert 'delete_metric_select_{project_id}' in METRIC_TAB_SOURCE
    assert 'delete_metric_{project_id}' in METRIC_TAB_SOURCE


def test_delete_area_only_deletes_semantic_definition():
    assert 'st.subheader("删除指标语义定义")' in METRIC_TAB_SOURCE
    assert "delete_metric_definition(project_id, delete_metric_id)" in METRIC_TAB_SOURCE
    assert "delete_kpi_definition" not in METRIC_TAB_SOURCE
    assert "kpi_definitions.json" not in METRIC_TAB_SOURCE


def test_kpi_creation_remains_in_calculation_rules_tab():
    assert 'st.subheader("新增指标计算规则")' in KPI_TAB_SOURCE
    assert "add_saved_kpi_definition(" in KPI_TAB_SOURCE


def test_metric_dictionary_does_not_connect_downstream_modules():
    for forbidden in (
        "render_business_dashboard",
        "render_dimension_comparison",
        "render_business_question",
        "export_",
    ):
        assert forbidden not in METRIC_TAB_SOURCE
