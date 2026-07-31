from pathlib import Path

import pandas as pd

from src.exploration import (
    build_categorical_composition_analysis,
    build_categorical_top_n_chart_data,
    calculate_dataframe_height,
)


APP_SOURCE = Path("app.py").read_text(encoding="utf-8")
CATEGORY_TAB_SOURCE = APP_SOURCE.split(
    "with exploration_tabs[1]:",
    maxsplit=1,
)[1].split(
    "with exploration_tabs[2]:",
    maxsplit=1,
)[0]
OTHER_TABLE_SOURCE = CATEGORY_TAB_SOURCE.split(
    '"查看‘其他’包含的类别"',
    maxsplit=1,
)[1].split(
    'st.markdown("#### 构成解读")',
    maxsplit=1,
)[0]


def _other_rows(category_count, top_n=5):
    analysis = build_categorical_composition_analysis(
        pd.Series([f"类别{index:02d}" for index in range(category_count)]),
        "产品",
    )
    return build_categorical_top_n_chart_data(
        analysis,
        top_n,
    )["other_rows"]


def test_three_other_categories_use_compact_height():
    rows = _other_rows(8)

    assert len(rows) == 3
    assert calculate_dataframe_height(len(rows)) < calculate_dataframe_height(12)


def test_nine_other_categories_are_fully_visible_and_taller():
    three_rows = _other_rows(8)
    nine_rows = _other_rows(14)

    assert len(nine_rows) == 9
    assert calculate_dataframe_height(len(nine_rows)) > calculate_dataframe_height(
        len(three_rows)
    )
    assert calculate_dataframe_height(len(nine_rows)) < calculate_dataframe_height(12)


def test_twelve_other_categories_reach_full_maximum_height():
    rows = _other_rows(17)

    assert len(rows) == 12
    assert calculate_dataframe_height(len(rows)) == calculate_dataframe_height(12)


def test_twenty_four_other_categories_keep_all_rows_at_bounded_height():
    rows = _other_rows(29)

    assert len(rows) == 24
    assert calculate_dataframe_height(len(rows)) == calculate_dataframe_height(12)


def test_zero_other_rows_do_not_create_other_expander_condition():
    analysis = build_categorical_composition_analysis(
        pd.Series(["A", "B", "C", "D", "E"]),
        "产品",
    )
    chart_data = build_categorical_top_n_chart_data(analysis, 5)

    assert chart_data["has_other"] is False
    assert chart_data["other_rows"] == []
    assert 'and categorical_chart_data["other_rows"]' in CATEGORY_TAB_SOURCE


def test_other_table_reuses_existing_dataframe_height_helper():
    assert "height=calculate_dataframe_height(" in OTHER_TABLE_SOURCE
    assert "len(other_category_table)" in OTHER_TABLE_SOURCE
    assert "height=400" not in OTHER_TABLE_SOURCE


def test_other_table_receives_complete_other_dataframe():
    assert "other_category_table = pd.DataFrame(" in CATEGORY_TAB_SOURCE
    assert 'categorical_chart_data[\n                                        "other_rows"' in CATEGORY_TAB_SOURCE
    assert "st.dataframe(\n                                    other_category_table" in OTHER_TABLE_SOURCE
    assert ".head(" not in OTHER_TABLE_SOURCE
    assert ".tail(" not in OTHER_TABLE_SOURCE


def test_other_table_columns_remain_unchanged():
    for column in ('"类别"', '"记录数"', '"记录数占比"'):
        assert column in CATEGORY_TAB_SOURCE


def test_complete_composition_table_keeps_dynamic_height_behavior():
    complete_table_source = CATEGORY_TAB_SOURCE.split(
        "st.dataframe(\n                        displayed_composition_table",
        maxsplit=1,
    )[1].split(
        "if category_count > 5000:",
        maxsplit=1,
    )[0]

    assert "height=calculate_dataframe_height(" in complete_table_source
    assert "len(displayed_composition_table)" in complete_table_source


def test_top_n_and_merged_other_statistics_are_unchanged():
    analysis = build_categorical_composition_analysis(
        pd.Series(["A"] * 5 + ["B"] * 4 + ["C"] * 3 + ["D"] * 2),
        "产品",
    )
    chart_data = build_categorical_top_n_chart_data(analysis, 2)

    assert [item["category"] for item in chart_data["top_rows"]] == ["A", "B"]
    assert [item["category"] for item in chart_data["other_rows"]] == ["C", "D"]
    assert chart_data["chart_rows"][-1]["category"] == "其他（合并）"
    assert chart_data["chart_rows"][-1]["count"] == 5
