from pathlib import Path


APP_SOURCE = Path("app.py").read_text(encoding="utf-8")
NORMALIZED_APP_SOURCE = " ".join(APP_SOURCE.split())
EXPLORATION_SOURCE = APP_SOURCE.split(
    "with workbench_tabs[0]:",
    maxsplit=1,
)[1].split(
    "with workbench_tabs[1]:",
    maxsplit=1,
)[0]
SETUP_NAVIGATION_SOURCE = APP_SOURCE.split(
    "def render_project_setup_navigation(",
    maxsplit=1,
)[1].split(
    "@st.cache_data",
    maxsplit=1,
)[0]


def test_exploration_has_exactly_four_subtabs():
    assert APP_SOURCE.count("with exploration_tabs[") == 4


def test_final_exploration_tab_order_is_correct():
    assert (
        '["数值分布", "类别构成", "时间分布", "相关关系"]'
        in NORMALIZED_APP_SOURCE
    )


def test_ai_exploration_tab_title_is_removed():
    assert "AI 探索洞察" not in APP_SOURCE


def test_exploration_indexes_are_contiguous_and_bounded():
    for index in range(4):
        assert f"with exploration_tabs[{index}]:" in APP_SOURCE
    assert "with exploration_tabs[4]:" not in APP_SOURCE


def test_numeric_distribution_remains_first_tab():
    numeric_position = APP_SOURCE.index("with exploration_tabs[0]:")

    assert 'st.subheader("数值分布")' in APP_SOURCE[numeric_position:]


def test_categorical_composition_remains_second_tab():
    category_source = APP_SOURCE.split(
        "with exploration_tabs[1]:",
        maxsplit=1,
    )[1].split(
        "with exploration_tabs[2]:",
        maxsplit=1,
    )[0]

    assert 'st.subheader("类别构成")' in category_source


def test_time_distribution_remains_third_tab():
    time_source = APP_SOURCE.split(
        "with exploration_tabs[2]:",
        maxsplit=1,
    )[1].split(
        "with exploration_tabs[3]:",
        maxsplit=1,
    )[0]

    assert 'st.subheader("时间分布")' in time_source


def test_correlation_relationships_remains_fourth_tab():
    correlation_source = APP_SOURCE.split(
        "with exploration_tabs[3]:",
        maxsplit=1,
    )[1].split(
        "with workbench_tabs[1]:",
        maxsplit=1,
    )[0]

    assert 'st.subheader("相关关系")' in correlation_source


def test_correlation_scatter_remains_available():
    assert 'st.markdown("#### 查看字段对分布")' in EXPLORATION_SOURCE
    assert "build_correlation_scatter_data(" in EXPLORATION_SOURCE


def test_ai_exploration_helpers_are_not_called_by_app():
    assert "build_analysis_payload(" not in APP_SOURCE
    assert "request_ai_insights(" not in APP_SOURCE


def test_ai_exploration_helper_imports_are_removed_from_app():
    assert "from src.eda_ai_complete import" not in APP_SOURCE


def test_ai_exploration_session_state_is_kept_for_export_compatibility():
    assert "ai_exploration_result" in APP_SOURCE
    assert (
        'st.session_state.get("ai_exploration_result")'
        in APP_SOURCE
    )


def test_dashboard_ai_summary_entry_remains():
    assert "AI 正在生成管理层报表总结..." in APP_SOURCE
    assert "AI 报表总结生成失败" in APP_SOURCE


def test_report_export_ai_features_remain():
    assert '"AI周期报告"' in APP_SOURCE
    assert '"管理层汇报"' in APP_SOURCE
    assert "generate_ai_periodic_report(" in APP_SOURCE
    assert '"生成管理层摘要"' in APP_SOURCE


def test_legacy_eda_engine_generation_remains():
    assert "from src.engines.eda_engine import generate_eda_report" in APP_SOURCE
    assert "generate_eda_report(active_project_id)" in EXPLORATION_SOURCE


def test_no_dataset_setup_navigation_has_no_removed_ai_entry():
    assert "AI 探索洞察" not in SETUP_NAVIGATION_SOURCE


def test_no_dataset_main_analysis_navigation_is_unchanged():
    assert (
        'analysis_tabs = st.tabs(["探索性分析", "Dashboard", "业务分析"])'
        in SETUP_NAVIGATION_SOURCE
    )
    assert SETUP_NAVIGATION_SOURCE.count("with analysis_tabs[") == 3


def test_main_workbench_navigation_is_unchanged():
    assert (
        'workbench_tabs = st.tabs(["探索性分析", "Dashboard", "业务分析"])'
        in APP_SOURCE
    )
    assert APP_SOURCE.count("with workbench_tabs[") == 3


def test_removed_legacy_exploration_sections_do_not_return():
    for term in (
        "自动探索报告",
        "IQR 异常值分析",
        "自动洞察",
        "风险警告",
        "异常值分析",
    ):
        assert term not in EXPLORATION_SOURCE


def test_exploration_copy_has_no_disallowed_labels():
    for term in (
        "显著相关",
        "业务风险",
        "业务贡献",
        "订单量",
        "业务量",
        "驱动因素",
        "因果关系",
    ):
        assert term not in EXPLORATION_SOURCE


def test_allowed_non_causal_reminder_is_preserved():
    assert "相关关系不代表因果" in EXPLORATION_SOURCE


def test_other_exploration_control_state_keys_remain():
    for prefix in (
        "numeric_distribution_field_",
        "categorical_composition_field_",
        "time_distribution_field_",
        "correlation_relationship_fields_",
    ):
        assert prefix in EXPLORATION_SOURCE
