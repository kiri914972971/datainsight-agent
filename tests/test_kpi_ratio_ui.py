import ast
from pathlib import Path


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


def test_new_ratio_form_uses_saved_valid_basic_dependency_helper():
    ratio_branch = KPI_TAB_SOURCE.split('if new_aggregation == "ratio":', 1)[1]
    assert "get_ratio_dependency_options(saved_kpis)" in ratio_branch
    assert '"分子 KPI"' in ratio_branch
    assert '"分母 KPI"' in ratio_branch
    assert "ratio_dependency_ids" in ratio_branch


def test_ratio_form_hides_normal_source_and_shows_read_only_result_metadata():
    assert 'value=NO_SOURCE_FIELD_LABEL' in KPI_TAB_SOURCE
    assert '"结果字段类型"' in KPI_TAB_SOURCE
    assert "infer_ratio_field_type(" in KPI_TAB_SOURCE
    assert "公式预览：" in KPI_TAB_SOURCE


def test_ratio_form_rejects_same_dependency_and_fewer_than_two_options():
    assert "比率 KPI 的分子和分母不能选择同一个指标。" in KPI_TAB_SOURCE
    assert "至少需要两个已保存且校验通过的基础 KPI" in KPI_TAB_SOURCE
    assert "disabled=not has_compatible_fields" in KPI_TAB_SOURCE


def test_ratio_submission_persists_ids_and_empty_source():
    assert 'new_aggregation in {"count_rows", "ratio"}' in KPI_TAB_SOURCE
    assert '"numerator_kpi_id": new_numerator_kpi_id' in KPI_TAB_SOURCE
    assert '"denominator_kpi_id": new_denominator_kpi_id' in KPI_TAB_SOURCE


def test_ratio_state_keys_are_project_scoped():
    for key in (
        "add_ratio_numerator_{project_id}",
        "add_ratio_denominator_{project_id}",
        "edit_ratio_select_{project_id}_{saved_signature}",
        "edit_ratio_numerator_{project_id}_{edit_ratio_id}",
        "edit_ratio_denominator_{project_id}_{edit_ratio_id}",
    ):
        assert key in KPI_TAB_SOURCE


def test_saved_ratio_has_independent_edit_area():
    assert 'st.subheader("编辑比率指标")' in KPI_TAB_SOURCE
    assert '"保存比率指标修改"' in KPI_TAB_SOURCE
    assert '"aggregation": "ratio"' in KPI_TAB_SOURCE
    assert '"source_field": ""' in KPI_TAB_SOURCE


def test_candidate_and_saved_tables_use_readable_formula_column():
    assert KPI_TAB_SOURCE.count('"来源字段／公式"') >= 4
    assert KPI_TAB_SOURCE.count("format_kpi_source_or_formula(") >= 3
    assert "numerator_kpi_id" not in KPI_TAB_SOURCE.split(
        'st.subheader("自动推荐候选")', 1
    )[1].split('st.subheader("已保存指标")', 1)[0].split("candidate_rows", 1)[0]


def test_legacy_single_field_aov_warning_does_not_migrate_it():
    assert "is_legacy_single_field_aov_kpi" in KPI_TAB_SOURCE
    assert "会继续保留且不会自动迁移" in KPI_TAB_SOURCE
    assert "改用比率 KPI" in KPI_TAB_SOURCE


def test_aov_ambiguity_notice_is_displayed_without_auto_selection():
    assert "generate_aov_ratio_recommendation(saved_kpis)" in KPI_TAB_SOURCE
    assert 'aov_recommendation["status"] == "ambiguous"' in KPI_TAB_SOURCE


def test_delete_dependency_requires_confirmation_without_cascade_delete():
    assert "get_ratio_dependents(saved_kpis, delete_kpi_id)" in KPI_TAB_SOURCE
    assert "删除后这些比率指标会保留" in KPI_TAB_SOURCE
    assert "我已了解依赖影响" in KPI_TAB_SOURCE
    assert "disabled=not deletion_confirmed" in KPI_TAB_SOURCE
    assert "delete_metric_definition" not in KPI_TAB_SOURCE


def test_metric_dictionary_displays_readable_formula_as_read_only():
    assert '"计算公式"' in METRIC_TAB_SOURCE
    assert "build_metric_formula_summary(" in METRIC_TAB_SOURCE
    assert 'disabled=["计算公式", "关联指标计算规则", "关联状态"]' in METRIC_TAB_SOURCE


def test_ratio_ui_does_not_write_dashboard_or_report_context():
    for forbidden in (
        "render_business_dashboard",
        "render_dashboard",
        "report_context",
        "export_",
    ):
        assert forbidden not in KPI_TAB_SOURCE
