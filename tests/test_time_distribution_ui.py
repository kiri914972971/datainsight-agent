from pathlib import Path

import pandas as pd

from src.exploration import (
    TIME_GRANULARITIES,
    TIME_GRANULARITY_LABELS,
    build_time_distribution_analysis,
    build_time_distribution_view_data,
    calculate_dataframe_height,
    get_time_distribution_datetime_columns,
)


APP_SOURCE = Path("app.py").read_text(encoding="utf-8")
NORMALIZED_APP_SOURCE = " ".join(APP_SOURCE.split())
TIME_TAB_SOURCE = APP_SOURCE.split(
    "with exploration_tabs[2]:",
    maxsplit=1,
)[1].split(
    "with exploration_tabs[3]:",
    maxsplit=1,
)[0]


def test_exploration_tab_order_contains_time_distribution():
    assert (
        '["数值分布", "类别构成", "时间分布", "相关关系", "AI 探索洞察"]'
        in NORMALIZED_APP_SOURCE
    )


def test_date_selector_uses_only_datetime_role():
    df = pd.DataFrame(
        {
            "成交日期": ["2026-01-01"],
            "成交金额": [100],
            "产品": ["A"],
        }
    )
    field_roles = {
        "role_by_column": {
            "成交日期": "datetime",
            "成交金额": "numeric",
            "产品": "categorical",
        }
    }

    assert get_time_distribution_datetime_columns(df, field_roles) == [
        "成交日期"
    ]


def test_derived_time_is_not_in_date_selector():
    df = pd.DataFrame(
        {
            "成交日期": ["2026-01-01"],
            "成交年份": [2026],
            "成交月份": [1],
        }
    )
    field_roles = {
        "role_by_column": {
            "成交日期": "datetime",
            "成交年份": "derived_time",
            "成交月份": "derived_time",
        }
    }

    assert get_time_distribution_datetime_columns(df, field_roles) == [
        "成交日期"
    ]


def test_no_datetime_fields_returns_empty_list_and_has_empty_message():
    df = pd.DataFrame({"成交金额": [100]})
    field_roles = {"role_by_column": {"成交金额": "numeric"}}

    assert get_time_distribution_datetime_columns(df, field_roles) == []
    assert "当前数据集没有可用于时间分布分析的完整日期字段。" in TIME_TAB_SOURCE


def test_selected_date_field_is_used_to_access_dataframe_series():
    assert "df[selected_time_field]" in TIME_TAB_SOURCE


def test_recommended_granularity_has_correct_chinese_mapping():
    assert TIME_GRANULARITY_LABELS == {
        "day": "日",
        "week": "周",
        "month": "月",
        "quarter": "季度",
        "year": "年",
    }


def test_granularity_control_supports_all_five_options():
    assert TIME_GRANULARITIES == (
        "day",
        "week",
        "month",
        "quarter",
        "year",
    )
    assert "list(TIME_GRANULARITIES)" in TIME_TAB_SOURCE


def test_selected_granularity_is_passed_to_analysis_helper():
    assert "granularity=selected_time_granularity" in TIME_TAB_SOURCE


def test_ok_status_exposes_chart_data():
    analysis = build_time_distribution_analysis(
        pd.Series(["2026-01-01", "2026-01-03"]),
        "成交日期",
        granularity="day",
    )

    view_data = build_time_distribution_view_data(analysis)

    assert view_data["show_chart"] is True
    assert len(view_data["chart_rows"]) == 3


def test_chart_data_uses_existing_rows_without_reaggregation():
    analysis = build_time_distribution_analysis(
        pd.Series(["2026-01-01", "2026-01-03"]),
        "成交日期",
        granularity="day",
    )

    view_data = build_time_distribution_view_data(analysis)

    assert view_data["chart_rows"] == analysis["rows"]
    assert ".groupby(" not in TIME_TAB_SOURCE


def test_time_detail_rows_keep_source_time_order():
    analysis = build_time_distribution_analysis(
        pd.Series(["2026-01-03", "2026-01-01"]),
        "成交日期",
        granularity="day",
    )

    detail_rows = build_time_distribution_view_data(analysis)["detail_rows"]

    starts = [item["period_start"] for item in detail_rows]
    assert starts == sorted(starts)


def test_time_detail_uses_bounded_dynamic_height():
    assert calculate_dataframe_height(2) < calculate_dataframe_height(12)
    assert calculate_dataframe_height(24) == calculate_dataframe_height(12)
    assert "calculate_dataframe_height(" in TIME_TAB_SOURCE


def test_empty_zero_ranges_message_is_present():
    assert "当前时间范围内没有无记录时间段。" in TIME_TAB_SOURCE


def test_too_dense_status_does_not_expose_chart():
    analysis = build_time_distribution_analysis(
        pd.Series(["2020-01-01", "2021-02-04"]),
        "成交日期",
        granularity="day",
    )

    view_data = build_time_distribution_view_data(analysis)

    assert analysis["status"] == "too_dense"
    assert view_data["show_chart"] is False
    assert view_data["show_details"] is False


def test_single_date_status_does_not_expose_chart():
    analysis = build_time_distribution_analysis(
        pd.Series(["2026-01-01 08:00", "2026-01-01 18:00"]),
        "成交日期",
    )

    view_data = build_time_distribution_view_data(analysis)

    assert analysis["status"] == "single_date"
    assert view_data["show_chart"] is False


def test_no_valid_dates_status_does_not_expose_chart():
    analysis = build_time_distribution_analysis(
        pd.Series([None, "无法解析"]),
        "成交日期",
    )

    view_data = build_time_distribution_view_data(analysis)

    assert analysis["status"] == "no_valid_dates"
    assert view_data["show_chart"] is False


def test_dataset_key_is_part_of_time_control_state_keys():
    assert (
        'f"{active_project_id}_{time_distribution_dataset_key}"'
        in TIME_TAB_SOURCE
    )
    assert "time_distribution_last_field_" in TIME_TAB_SOURCE


def test_numeric_and_category_tab_indexes_are_unchanged():
    assert "with exploration_tabs[0]:" in APP_SOURCE
    assert "with exploration_tabs[1]:" in APP_SOURCE


def test_correlation_and_ai_tabs_shift_to_valid_indexes():
    assert "with exploration_tabs[3]:" in APP_SOURCE
    assert "with exploration_tabs[4]:" in APP_SOURCE
    assert APP_SOURCE.count("with exploration_tabs[") == 5


def test_time_page_copy_has_no_out_of_scope_terms():
    assert "业绩" not in TIME_TAB_SOURCE
    assert "增长" not in TIME_TAB_SOURCE
    assert "业务风险" not in TIME_TAB_SOURCE


def test_time_chart_is_bar_not_line():
    assert "time_figure = px.bar(" in TIME_TAB_SOURCE
    assert "px.line(" not in TIME_TAB_SOURCE


def test_unknown_status_is_handled_without_traceback_copy():
    view_data = build_time_distribution_view_data(
        {
            "status": "unexpected",
            "period_count": 0,
            "rows": [],
            "zero_ranges": [],
        }
    )

    assert view_data["known_status"] is False
    assert "当前时间分布状态无法识别" in TIME_TAB_SOURCE
