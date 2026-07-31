import ast
from pathlib import Path

import pandas as pd

from src.exploration import (
    build_numeric_distribution_analysis,
    calculate_histogram_bin_count,
)


BIN_CAPTION = (
    "分箱是将连续数值范围划分为若干区间，并统计每个区间内的记录数。"
    "分箱越多，图表越细；分箱越少，图表越概括。"
    "该设置只影响图表展示，不影响统计结果。"
)
APP_SOURCE = Path("app.py").read_text(encoding="utf-8")
NUMERIC_TAB_SOURCE = APP_SOURCE.split(
    "with exploration_tabs[0]:",
    maxsplit=1,
)[1].split(
    "with exploration_tabs[1]:",
    maxsplit=1,
)[0]
CONTINUOUS_MARKER = (
    "                else:\n"
    '                    histogram_bin_count = numeric_distribution["default_bin_count"]'
)
DISCRETE_BRANCH_SOURCE = NUMERIC_TAB_SOURCE.split(
    'elif numeric_distribution["distribution_type"] == "discrete":',
    maxsplit=1,
)[1].split(
    CONTINUOUS_MARKER,
    maxsplit=1,
)[0]
CONTINUOUS_BRANCH_SOURCE = NUMERIC_TAB_SOURCE.split(
    CONTINUOUS_MARKER,
    maxsplit=1,
)[1].split(
    'st.markdown("#### 分布解读")',
    maxsplit=1,
)[0]
CONTINUOUS_BRANCH_SOURCE = CONTINUOUS_MARKER + CONTINUOUS_BRANCH_SOURCE


def test_continuous_histogram_shows_bin_control_and_caption():
    assert 'st.slider(\n                            "分箱数量"' in CONTINUOUS_BRANCH_SOURCE
    caption_values = [
        node.args[0].value
        for node in ast.walk(ast.parse(APP_SOURCE))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "caption"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    ]

    assert BIN_CAPTION in caption_values


def test_discrete_chart_does_not_show_bin_control_or_caption():
    assert "st.slider(" not in DISCRETE_BRANCH_SOURCE
    assert "分箱数量" not in DISCRETE_BRANCH_SOURCE
    assert "只影响图表展示，不影响统计结果" not in DISCRETE_BRANCH_SOURCE


def test_bin_control_name_and_range_are_unchanged():
    slider_source = CONTINUOUS_BRANCH_SOURCE.split("st.slider(", maxsplit=1)[1].split(
        ")\n", maxsplit=1
    )[0]

    assert '"分箱数量"' in slider_source
    assert "min_value=10" in slider_source
    assert "max_value=50" in slider_source


def test_bin_caption_is_immediately_after_slider_and_before_histogram_data():
    slider_position = CONTINUOUS_BRANCH_SOURCE.index("st.slider(")
    caption_position = CONTINUOUS_BRANCH_SOURCE.index("st.caption(", slider_position)
    histogram_position = CONTINUOUS_BRANCH_SOURCE.index("histogram_data =", caption_position)

    assert slider_position < caption_position < histogram_position


def test_bin_caption_is_limited_to_visible_slider_condition():
    control_source = CONTINUOUS_BRANCH_SOURCE.split(
        'if numeric_distribution["valid_count"] >= 20:',
        maxsplit=1,
    )[1].split(
        "histogram_data =",
        maxsplit=1,
    )[0]

    assert "st.slider(" in control_source
    assert "st.caption(" in control_source
    assert APP_SOURCE.count("只影响图表展示，不影响统计结果") == 1


def test_default_bin_count_and_histogram_binding_are_unchanged():
    assert 'numeric_distribution["default_bin_count"]' in CONTINUOUS_BRANCH_SOURCE
    assert "nbins=histogram_bin_count" in CONTINUOUS_BRANCH_SOURCE


def test_changing_histogram_bin_count_does_not_change_statistics_summary():
    series = pd.Series([float(value) / 3 for value in range(1, 101)])
    result_before = build_numeric_distribution_analysis(series, "成交金额")
    original_summary = dict(result_before["summary"])

    automatic_bin_count = calculate_histogram_bin_count(series)
    manually_selected_bin_count = 50 if automatic_bin_count != 50 else 10
    result_after = build_numeric_distribution_analysis(series, "成交金额")

    assert manually_selected_bin_count != automatic_bin_count
    assert result_before["summary"] == original_summary
    assert result_after["summary"] == original_summary
