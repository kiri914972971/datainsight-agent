from pathlib import Path


APP_SOURCE = Path("app.py").read_text(encoding="utf-8")
CORRELATION_TAB_SOURCE = APP_SOURCE.split(
    "with exploration_tabs[3]:",
    maxsplit=1,
)[1].split(
    "with exploration_tabs[4]:",
    maxsplit=1,
)[0]
SCATTER_SOURCE = CORRELATION_TAB_SOURCE.split(
    'st.markdown("#### 查看字段对分布")',
    maxsplit=1,
)[1]


def test_scatter_section_is_after_relationship_interpretation():
    interpretation_position = CORRELATION_TAB_SOURCE.index(
        'st.markdown("#### 相关关系解读")'
    )
    scatter_position = CORRELATION_TAB_SOURCE.index(
        'st.markdown("#### 查看字段对分布")'
    )

    assert scatter_position > interpretation_position


def test_scatter_axis_fields_use_selected_columns():
    assert (
        '"横轴字段",\n'
        "                        selected_correlation_columns"
        in SCATTER_SOURCE
    )
    assert "for column in selected_correlation_columns" in SCATTER_SOURCE


def test_scatter_axes_do_not_use_all_numeric_fields():
    assert "correlation_numeric_columns" not in SCATTER_SOURCE


def test_scatter_y_axis_excludes_selected_x():
    assert "if column != selected_scatter_x" in SCATTER_SOURCE


def test_default_scatter_x_is_first_selected_field():
    assert (
        "selected_correlation_columns[0]"
        in SCATTER_SOURCE
    )


def test_default_scatter_y_is_second_selected_field():
    assert (
        "selected_correlation_columns[1]"
        in SCATTER_SOURCE
    )


def test_invalid_x_state_falls_back_safely():
    assert (
        "st.session_state.get(scatter_x_key)\n"
        "                        not in selected_correlation_columns"
        in SCATTER_SOURCE
    )


def test_invalid_y_state_falls_back_safely():
    assert (
        "st.session_state.get(scatter_y_key)\n"
        "                        not in scatter_y_options"
        in SCATTER_SOURCE
    )


def test_scatter_control_key_contains_field_set_signature():
    assert "scatter_field_set_signature" in SCATTER_SOURCE
    assert "selected_correlation_columns" in SCATTER_SOURCE


def test_scatter_control_keys_bind_project_and_dataset():
    assert "active_project_id" in SCATTER_SOURCE
    assert "correlation_dataset_key" in SCATTER_SOURCE
    assert "correlation_scatter_x_" in SCATTER_SOURCE
    assert "correlation_scatter_y_" in SCATTER_SOURCE


def test_scatter_uses_current_method_without_second_control():
    assert "method=selected_correlation_method" in SCATTER_SOURCE
    assert "st.radio(" not in SCATTER_SOURCE


def test_pearson_can_be_passed_to_scatter_helper():
    assert '("pearson", "spearman")' in CORRELATION_TAB_SOURCE
    assert "method=selected_correlation_method" in SCATTER_SOURCE


def test_spearman_can_be_passed_to_scatter_helper():
    assert '"spearman": "Spearman"' in CORRELATION_TAB_SOURCE
    assert "method=selected_correlation_method" in SCATTER_SOURCE


def test_scatter_helper_receives_required_arguments():
    assert "build_correlation_scatter_data(" in SCATTER_SOURCE
    assert "df=df" in SCATTER_SOURCE
    assert "field_x=selected_scatter_x" in SCATTER_SOURCE
    assert "field_y=selected_scatter_y" in SCATTER_SOURCE
    assert "max_points=5000" in SCATTER_SOURCE
    assert "random_state=42" in SCATTER_SOURCE


def test_scatter_chart_data_uses_helper_rows():
    assert 'correlation_scatter_result["rows"]' in SCATTER_SOURCE
    assert 'item["x"]' in SCATTER_SOURCE
    assert 'item["y"]' in SCATTER_SOURCE


def test_page_does_not_recalculate_scatter_correlation():
    assert ".corr(" not in SCATTER_SOURCE


def test_page_does_not_clean_or_sample_scatter_data():
    assert ".dropna(" not in SCATTER_SOURCE
    assert ".sample(" not in SCATTER_SOURCE
    assert "np.isfinite" not in SCATTER_SOURCE


def test_ok_status_builds_scatter_chart():
    assert 'scatter_status != "ok"' in SCATTER_SOURCE
    assert "scatter_figure = px.scatter(" in SCATTER_SOURCE


def test_insufficient_data_status_does_not_enter_chart_branch():
    insufficient_position = SCATTER_SOURCE.index(
        'elif scatter_status == "insufficient_data":'
    )
    ok_position = SCATTER_SOURCE.index('elif scatter_status != "ok":')
    chart_position = SCATTER_SOURCE.index("scatter_figure = px.scatter(")

    assert insufficient_position < ok_position < chart_position
    assert "当前字段对的共同有效记录少于 5 条" in SCATTER_SOURCE


def test_invalid_fields_status_does_not_enter_chart_branch():
    invalid_position = SCATTER_SOURCE.index(
        'if scatter_status == "invalid_fields":'
    )
    chart_position = SCATTER_SOURCE.index("scatter_figure = px.scatter(")

    assert invalid_position < chart_position
    assert "请重新选择两个不同的数值字段。" in SCATTER_SOURCE


def test_unknown_scatter_status_has_safe_message():
    assert "当前散点分布状态无法识别，请重新选择字段。" in SCATTER_SOURCE


def test_small_sample_message_uses_five_to_nineteen_rule():
    assert (
        "5\n"
        '                                <= correlation_scatter_result["sample_size"]\n'
        "                                < 20"
        in SCATTER_SOURCE
    )
    assert "当前字段对的有效样本较少" in SCATTER_SOURCE


def test_sampled_result_shows_five_thousand_point_message():
    assert 'if correlation_scatter_result["is_sampled"]:' in SCATTER_SOURCE
    assert "散点图展示 5,000 个" in SCATTER_SOURCE
    assert "相关系数仍基于全部有效记录计算。" in SCATTER_SOURCE


def test_unsampled_result_has_no_unconditional_sampling_message():
    sampling_condition_position = SCATTER_SOURCE.index(
        'if correlation_scatter_result["is_sampled"]:'
    )
    sampling_message_position = SCATTER_SOURCE.index(
        "为保证图表可读性"
    )

    assert sampling_message_position > sampling_condition_position


def test_scatter_overview_shows_four_metrics():
    for label in (
        '"当前相关方法"',
        '"相关系数"',
        '"全部有效样本数"',
        '"图表展示点数"',
    ):
        assert label in SCATTER_SOURCE


def test_scatter_correlation_uses_three_decimal_numeric_format():
    assert (
        "correlation_scatter_result['correlation']:.3f"
        in SCATTER_SOURCE
    )
    correlation_metric_source = SCATTER_SOURCE.split(
        '"相关系数"',
        maxsplit=1,
    )[1].split(
        "scatter_overview_columns[2].metric",
        maxsplit=1,
    )[0]

    assert "%" not in correlation_metric_source


def test_near_complete_relationship_has_definition_notice():
    assert ">= 0.9999" in SCATTER_SOURCE
    assert "该字段对接近完全相关，可能存在重复字段、" in SCATTER_SOURCE


def test_scatter_has_no_trendline_or_regression_options():
    for term in ("trendline", "回归线", "回归方程", "R²"):
        assert term not in SCATTER_SOURCE


def test_scatter_uses_only_x_y_and_title_encodings():
    scatter_call = SCATTER_SOURCE.split(
        "scatter_figure = px.scatter(",
        maxsplit=1,
    )[1].split(
        "st.plotly_chart(",
        maxsplit=1,
    )[0]

    assert "x=scatter_field_x" in scatter_call
    assert "y=scatter_field_y" in scatter_call
    assert "size=" not in scatter_call
    assert "color=" not in scatter_call


def test_scatter_axes_remain_numeric():
    assert ".astype(str)" not in SCATTER_SOURCE
    assert 'type="category"' not in SCATTER_SOURCE


def test_scatter_pair_is_not_limited_by_threshold_pairs():
    assert "displayed_correlation_pairs" not in SCATTER_SOURCE
    assert "selected_correlation_threshold" not in SCATTER_SOURCE


def test_scatter_chart_key_contains_current_method_and_fields():
    chart_key_source = SCATTER_SOURCE.split(
        '"correlation_scatter_chart_"',
        maxsplit=1,
    )[1]

    assert "selected_scatter_x" in chart_key_source
    assert "selected_scatter_y" in chart_key_source
    assert "selected_correlation_method" in chart_key_source


def test_scatter_result_is_not_written_to_session_state():
    assert "correlation_scatter_result] =" not in SCATTER_SOURCE
    assert "scatter_result_key" not in SCATTER_SOURCE


def test_scatter_does_not_write_project_or_report_files():
    for term in (
        "save_",
        "write_text",
        "write_bytes",
        "report_context",
        "export_",
    ):
        assert term not in SCATTER_SOURCE


def test_scatter_fixed_non_causal_explanation_is_present():
    assert (
        "散点图只能帮助观察字段之间的分布形态，"
        in SCATTER_SOURCE
    )
    assert "不能证明一个字段导致另一个字段变化。" in SCATTER_SOURCE


def test_existing_relationship_sections_remain_before_scatter():
    scatter_position = CORRELATION_TAB_SOURCE.index(
        'st.markdown("#### 查看字段对分布")'
    )
    for heading in (
        'st.markdown("#### 数值字段相关矩阵")',
        'st.markdown("#### 达到当前阈值的字段对")',
        'st.markdown("#### 相关关系解读")',
    ):
        assert CORRELATION_TAB_SOURCE.index(heading) < scatter_position
