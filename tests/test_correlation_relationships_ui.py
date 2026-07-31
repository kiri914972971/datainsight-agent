from pathlib import Path

import pandas as pd

from src.exploration import calculate_correlation_pairs


APP_SOURCE = Path("app.py").read_text(encoding="utf-8")
NORMALIZED_APP_SOURCE = " ".join(APP_SOURCE.split())
CORRELATION_TAB_SOURCE = APP_SOURCE.split(
    "with exploration_tabs[3]:",
    maxsplit=1,
)[1].split(
    "with workbench_tabs[1]:",
    maxsplit=1,
)[0]


def test_correlation_tab_is_renamed():
    assert 'st.subheader("相关关系")' in CORRELATION_TAB_SOURCE
    assert 'st.subheader("相关分析")' not in CORRELATION_TAB_SOURCE


def test_exploration_tab_order_is_correct():
    assert (
        '["数值分布", "类别构成", "时间分布", "相关关系"]'
        in NORMALIZED_APP_SOURCE
    )


def test_selectable_fields_come_from_numeric_role():
    assert (
        'exploration_field_roles.get("columns_by_role", {}).get('
        in CORRELATION_TAB_SOURCE
    )
    assert '"numeric"' in CORRELATION_TAB_SOURCE


def test_identifier_role_is_not_added_to_selectable_fields():
    selection_source = CORRELATION_TAB_SOURCE.split(
        "correlation_numeric_columns =",
        maxsplit=1,
    )[1].split(
        "if len(correlation_numeric_columns)",
        maxsplit=1,
    )[0]

    assert '"identifier"' not in selection_source


def test_datetime_and_derived_time_roles_are_not_added_to_fields():
    selection_source = CORRELATION_TAB_SOURCE.split(
        "correlation_numeric_columns =",
        maxsplit=1,
    )[1].split(
        "if len(correlation_numeric_columns)",
        maxsplit=1,
    )[0]

    assert '"datetime"' not in selection_source
    assert '"derived_time"' not in selection_source


def test_default_selection_is_limited_to_first_eight_fields():
    assert "default=correlation_numeric_columns[:8]" in CORRELATION_TAB_SOURCE


def test_fewer_than_two_available_numeric_fields_has_empty_state():
    assert "if len(correlation_numeric_columns) < 2:" in CORRELATION_TAB_SOURCE
    assert (
        "当前数据集没有足够的数值字段进行相关关系分析。"
        in CORRELATION_TAB_SOURCE
    )


def test_fewer_than_two_selected_fields_does_not_calculate():
    assert "if len(selected_correlation_columns) < 2:" in CORRELATION_TAB_SOURCE
    assert "请至少选择两个数值字段。" in CORRELATION_TAB_SOURCE
    assert "disabled=correlation_selection_error is not None" in CORRELATION_TAB_SOURCE


def test_more_than_twelve_selected_fields_does_not_calculate():
    assert "elif len(selected_correlation_columns) > 12:" in CORRELATION_TAB_SOURCE
    assert "最多同时选择 12 个字段，请缩小分析范围。" in CORRELATION_TAB_SOURCE


def test_pearson_option_maps_to_internal_value():
    assert '("pearson", "spearman")' in CORRELATION_TAB_SOURCE
    assert '"pearson": "Pearson"' in CORRELATION_TAB_SOURCE


def test_spearman_option_maps_to_internal_value():
    assert '"spearman": "Spearman"' in CORRELATION_TAB_SOURCE


def test_threshold_defaults_to_point_five():
    assert "value=0.5" in CORRELATION_TAB_SOURCE


def test_threshold_range_and_step_are_correct():
    assert "min_value=0.0" in CORRELATION_TAB_SOURCE
    assert "max_value=1.0" in CORRELATION_TAB_SOURCE
    assert "step=0.1" in CORRELATION_TAB_SOURCE


def test_calculate_button_calls_relationship_helper():
    button_position = CORRELATION_TAB_SOURCE.index('"计算相关关系"')
    helper_position = CORRELATION_TAB_SOURCE.index(
        "build_correlation_relationship_analysis("
    )

    assert helper_position > button_position


def test_relationship_helper_receives_current_inputs():
    assert "df=df" in CORRELATION_TAB_SOURCE
    assert "selected_columns=selected_correlation_columns" in CORRELATION_TAB_SOURCE
    assert "method=selected_correlation_method" in CORRELATION_TAB_SOURCE
    assert "threshold=selected_correlation_threshold" in CORRELATION_TAB_SOURCE


def test_no_calculation_occurs_before_button_block():
    source_before_button = CORRELATION_TAB_SOURCE.split(
        "if st.button(",
        maxsplit=1,
    )[0]

    assert "build_correlation_relationship_analysis(" not in source_before_button


def test_heatmap_uses_helper_matrix():
    assert (
        'correlation_analysis_result["matrix"]'
        in CORRELATION_TAB_SOURCE
    )
    assert "z=correlation_matrix_rows" in CORRELATION_TAB_SOURCE


def test_heatmap_does_not_recalculate_from_dataframe():
    assert ".corr(" not in CORRELATION_TAB_SOURCE
    assert "correlation_heatmap(" not in CORRELATION_TAB_SOURCE


def test_heatmap_is_built_before_threshold_pair_filter_display():
    matrix_position = CORRELATION_TAB_SOURCE.index(
        "correlation_matrix_figure = go.Figure("
    )
    pair_position = CORRELATION_TAB_SOURCE.index(
        'correlation_analysis_result["pairs"]'
    )

    assert matrix_position < pair_position


def test_heatmap_uses_full_fixed_color_range():
    assert "zmin=-1" in CORRELATION_TAB_SOURCE
    assert "zmax=1" in CORRELATION_TAB_SOURCE
    assert 'texttemplate="%{text}"' in CORRELATION_TAB_SOURCE


def test_heatmap_title_uses_calculated_method():
    assert 'title=f"{correlation_method_label} 相关矩阵"' in CORRELATION_TAB_SOURCE
    assert 'correlation_analysis_result["method"]' in CORRELATION_TAB_SOURCE


def test_pair_table_uses_helper_pairs():
    assert (
        'correlation_analysis_result["pairs"]'
        in CORRELATION_TAB_SOURCE
    )


def test_empty_pairs_message_is_present():
    assert (
        "当前没有字段对达到 "
        in CORRELATION_TAB_SOURCE
    )
    assert "可以调低阈值查看较弱关系。" in CORRELATION_TAB_SOURCE


def test_empty_pairs_check_occurs_after_heatmap_rendering():
    chart_position = CORRELATION_TAB_SOURCE.index("st.plotly_chart(")
    empty_pairs_position = CORRELATION_TAB_SOURCE.index(
        "if not displayed_correlation_pairs:"
    )

    assert chart_position < empty_pairs_position


def test_pair_table_has_required_columns():
    for column in (
        '"字段 A"',
        '"字段 B"',
        '"相关方向"',
        '"相关系数"',
        '"关系强度"',
        '"有效样本数"',
        '"样本状态"',
    ):
        assert column in CORRELATION_TAB_SOURCE


def test_pair_table_does_not_expose_internal_absolute_value():
    table_source = CORRELATION_TAB_SOURCE.split(
        "correlation_pair_table =",
        maxsplit=1,
    )[1].split(
        "st.dataframe(",
        maxsplit=1,
    )[0]

    assert "absolute_correlation" not in table_source


def test_pair_table_uses_dynamic_height():
    assert (
        "calculate_dataframe_height(\n"
        "                                len(correlation_pair_table)"
        in CORRELATION_TAB_SOURCE
    )


def test_no_valid_pairs_does_not_enter_ok_rendering_branch():
    no_pairs_position = CORRELATION_TAB_SOURCE.index(
        'elif correlation_status == "no_valid_pairs":'
    )
    ok_branch_position = CORRELATION_TAB_SOURCE.index(
        'elif correlation_status != "ok":'
    )
    heatmap_position = CORRELATION_TAB_SOURCE.index(
        "correlation_matrix_figure = go.Figure("
    )

    assert no_pairs_position < ok_branch_position < heatmap_position


def test_result_signature_contains_project_and_dataset():
    signature_source = CORRELATION_TAB_SOURCE.split(
        "correlation_result_signature =",
        maxsplit=1,
    )[1].split(
        "correlation_result_key =",
        maxsplit=1,
    )[0]

    assert "str(active_project_id)" in signature_source
    assert "correlation_dataset_key" in signature_source


def test_result_signature_contains_selected_fields():
    assert "tuple(selected_correlation_columns)" in CORRELATION_TAB_SOURCE


def test_result_signature_contains_method():
    signature_source = CORRELATION_TAB_SOURCE.split(
        "correlation_result_signature =",
        maxsplit=1,
    )[1].split(
        "correlation_result_key =",
        maxsplit=1,
    )[0]

    assert "selected_correlation_method" in signature_source


def test_result_signature_contains_threshold():
    assert "float(selected_correlation_threshold)" in CORRELATION_TAB_SOURCE


def test_cached_result_requires_exact_signature():
    assert (
        'cached_correlation_result.get("signature")'
        in CORRELATION_TAB_SOURCE
    )
    assert "== correlation_result_signature" in CORRELATION_TAB_SOURCE


def test_invalid_saved_fields_are_cleaned_for_current_dataset():
    assert "cleaned_correlation_fields" in CORRELATION_TAB_SOURCE
    assert "if column in correlation_numeric_columns" in CORRELATION_TAB_SOURCE


def test_control_keys_include_project_and_dataset():
    assert (
        'f"{active_project_id}_{correlation_dataset_key}"'
        in CORRELATION_TAB_SOURCE
    )
    assert "correlation_relationship_fields_" in CORRELATION_TAB_SOURCE
    assert "correlation_relationship_method_" in CORRELATION_TAB_SOURCE
    assert "correlation_relationship_threshold_" in CORRELATION_TAB_SOURCE


def test_sample_size_matrix_is_available_in_expander():
    assert '"查看字段对有效样本量"' in CORRELATION_TAB_SOURCE
    assert '"sample_size_matrix"' in CORRELATION_TAB_SOURCE


def test_sample_size_table_uses_dynamic_height():
    assert (
        "calculate_dataframe_height(\n"
        "                                len(sample_size_table)"
        in CORRELATION_TAB_SOURCE
    )


def test_complete_relationship_notice_is_present():
    assert (
        "部分字段对接近完全相关，可能存在重复字段、"
        in CORRELATION_TAB_SOURCE
    )


def test_interpretation_uses_helper_result():
    assert (
        'correlation_analysis_result["interpretation"]'
        in CORRELATION_TAB_SOURCE
    )


def test_page_copy_has_no_out_of_scope_terms():
    for term in ("显著相关", "驱动因素", "影响程度", "业务风险"):
        assert term not in CORRELATION_TAB_SOURCE


def test_page_has_no_p_value_or_regression_content():
    for term in ("p 值", "趋势线", "回归线"):
        assert term not in CORRELATION_TAB_SOURCE


def test_page_calls_scatter_helper():
    assert "build_correlation_scatter_data(" in CORRELATION_TAB_SOURCE


def test_old_page_helpers_are_not_rendered_in_new_tab():
    assert "calculate_correlation_pairs(" not in CORRELATION_TAB_SOURCE
    assert "correlation_heatmap(" not in CORRELATION_TAB_SOURCE


def test_legacy_calculate_correlation_pairs_still_behaves_the_same():
    df = pd.DataFrame(
        {
            "a": list(range(1, 21)),
            "b": [value * 2 for value in range(1, 21)],
        }
    )

    result = calculate_correlation_pairs(df, ["a", "b"])

    assert list(result.columns) == [
        "字段A",
        "字段B",
        "相关系数",
        "相关强度",
        "可能含义",
    ]
    assert len(result) == 1


def test_exploration_tab_indexes_remain_aligned():
    assert APP_SOURCE.count("with exploration_tabs[") == 4
    for index in range(4):
        assert f"with exploration_tabs[{index}]:" in APP_SOURCE


def test_numeric_category_and_time_tabs_remain_before_relationships():
    assert APP_SOURCE.index("with exploration_tabs[0]:") < APP_SOURCE.index(
        "with exploration_tabs[1]:"
    )
    assert APP_SOURCE.index("with exploration_tabs[1]:") < APP_SOURCE.index(
        "with exploration_tabs[2]:"
    )
    assert APP_SOURCE.index("with exploration_tabs[2]:") < APP_SOURCE.index(
        "with exploration_tabs[3]:"
    )


def test_removed_ai_exploration_tab_is_not_accessible():
    assert "with exploration_tabs[4]:" not in APP_SOURCE
    assert '"AI 探索洞察"' not in APP_SOURCE
