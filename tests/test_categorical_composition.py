import json

import pandas as pd

from src.exploration import (
    build_categorical_composition_analysis,
    build_categorical_top_n_chart_data,
    calculate_dataframe_height,
    categorical_composition_table_title,
    generate_categorical_composition_interpretation,
)


def test_regular_category_builds_complete_composition():
    result = build_categorical_composition_analysis(
        pd.Series(["华东", "华东", "华南", "华北"]),
        "区域",
    )

    assert result["status"] == "ok"
    assert len(result["rows"]) == 3
    assert result["rows"][0]["category"] == "华东"


def test_null_values_are_excluded():
    result = build_categorical_composition_analysis(
        pd.Series(["A", None, "B", pd.NA]),
        "产品",
    )

    assert [item["category"] for item in result["rows"]] == ["A", "B"]


def test_valid_and_excluded_counts_are_correct():
    result = build_categorical_composition_analysis(
        pd.Series(["A", None, "B", "A", None]),
        "产品",
    )

    assert result["total_count"] == 5
    assert result["valid_count"] == 3
    assert result["excluded_count"] == 2


def test_category_count_is_correct():
    result = build_categorical_composition_analysis(
        pd.Series(["A", "B", "C", "A"]),
        "产品",
    )

    assert result["category_count"] == 3


def test_rows_are_sorted_by_count_descending():
    result = build_categorical_composition_analysis(
        pd.Series(["A", "B", "B", "C", "C", "C"]),
        "产品",
    )

    assert [item["count"] for item in result["rows"]] == [3, 2, 1]
    assert [item["category"] for item in result["rows"]] == ["C", "B", "A"]


def test_equal_counts_are_stably_sorted_by_category_string():
    result = build_categorical_composition_analysis(
        pd.Series(["B", "A", "C"]),
        "产品",
    )

    assert [item["category"] for item in result["rows"]] == ["A", "B", "C"]


def test_rank_is_continuous_from_one():
    result = build_categorical_composition_analysis(
        pd.Series(["A", "B", "B", "C", "C", "C"]),
        "产品",
    )

    assert [item["rank"] for item in result["rows"]] == [1, 2, 3]


def test_ratio_uses_non_null_valid_count():
    result = build_categorical_composition_analysis(
        pd.Series(["A", "A", "B", None]),
        "产品",
    )

    assert result["rows"][0]["ratio"] == 2 / 3
    assert result["rows"][1]["ratio"] == 1 / 3


def test_cumulative_ratio_ends_at_one():
    result = build_categorical_composition_analysis(
        pd.Series(["A", "A", "B", "C"]),
        "产品",
    )

    assert result["rows"][-1]["cumulative_ratio"] == 1.0


def test_top1_category_and_ratio_are_correct():
    result = build_categorical_composition_analysis(
        pd.Series(["A", "A", "A", "B"]),
        "产品",
    )

    assert result["top1_category"] == "A"
    assert result["top1_count"] == 3
    assert result["top1_ratio"] == 0.75


def test_top5_ratio_uses_all_categories_when_fewer_than_five():
    result = build_categorical_composition_analysis(
        pd.Series(["A", "A", "B", "C"]),
        "产品",
    )

    assert result["category_count"] == 3
    assert result["top5_ratio"] == 1.0


def test_chart_data_adds_merged_other_when_categories_remain():
    analysis = build_categorical_composition_analysis(
        pd.Series(["A"] * 5 + ["B"] * 4 + ["C"] * 3 + ["D"] * 2),
        "产品",
    )

    chart_data = build_categorical_top_n_chart_data(analysis, 2)

    assert chart_data["has_other"] is True
    assert chart_data["chart_rows"][-1]["category"] == "其他（合并）"
    assert chart_data["chart_rows"][-1]["count"] == 5


def test_merged_other_is_always_last_chart_row():
    analysis = build_categorical_composition_analysis(
        pd.Series(["A"] * 5 + ["B"] * 4 + ["C"] * 100),
        "产品",
    )

    chart_data = build_categorical_top_n_chart_data(analysis, 1)

    assert chart_data["chart_rows"][-1]["is_merged_other"] is True


def test_real_other_category_is_not_confused_with_merged_other():
    analysis = build_categorical_composition_analysis(
        pd.Series(["其他"] * 5 + ["A"] * 4 + ["B"] * 3 + ["C"] * 2),
        "产品",
    )

    chart_data = build_categorical_top_n_chart_data(analysis, 2)
    chart_categories = [item["category"] for item in chart_data["chart_rows"]]

    assert "其他" in chart_categories
    assert "其他（合并）" in chart_categories


def test_chart_top_n_does_not_change_complete_rows():
    analysis = build_categorical_composition_analysis(
        pd.Series(["A"] * 5 + ["B"] * 4 + ["C"] * 3),
        "产品",
    )
    original_rows = [dict(item) for item in analysis["rows"]]

    build_categorical_top_n_chart_data(analysis, 1)

    assert analysis["rows"] == original_rows
    assert len(analysis["rows"]) == 3


def test_low_frequency_categories_are_counted():
    result = build_categorical_composition_analysis(
        pd.Series(["A"] * 100 + ["B", "C"]),
        "产品",
    )

    assert result["low_frequency_count"] == 2
    assert result["low_frequency_ratio"] == 2 / 102


def test_high_cardinality_field_keeps_complete_result():
    series = pd.Series([f"类别{index:04d}" for index in range(5001)])

    result = build_categorical_composition_analysis(series, "高基数字段")

    assert result["category_count"] == 5001
    assert len(result["rows"]) == 5001


def test_all_null_input_returns_no_valid_data():
    result = build_categorical_composition_analysis(
        pd.Series([None, pd.NA], dtype="object"),
        "产品",
    )

    assert result["status"] == "no_valid_data"
    assert result["rows"] == []


def test_single_category_returns_constant():
    result = build_categorical_composition_analysis(
        pd.Series(["A", "A", "A"]),
        "产品",
    )

    assert result["status"] == "constant"


def test_boolean_field_is_counted_without_translation():
    result = build_categorical_composition_analysis(
        pd.Series([True, False, True], dtype="bool"),
        "是否续约",
    )

    assert result["category_count"] == 2
    assert result["rows"][0]["category"] == "True"
    assert result["rows"][1]["category"] == "False"


def test_mixed_category_types_sort_without_error():
    result = build_categorical_composition_analysis(
        pd.Series([1, "1", 2, "A"], dtype="object"),
        "混合类别",
    )

    assert result["category_count"] == 4
    assert len(result["rows"]) == 4


def test_input_series_is_not_modified():
    series = pd.Series(["A", None, "B", "A"])
    original = series.copy(deep=True)

    build_categorical_composition_analysis(series, "产品")

    pd.testing.assert_series_equal(series, original)


def test_result_is_json_serializable():
    result = build_categorical_composition_analysis(
        pd.Series(["A", "A", "B"]),
        "产品",
    )
    chart_data = build_categorical_top_n_chart_data(result, 1)

    assert json.loads(json.dumps(result, ensure_ascii=False)) == result
    assert json.loads(json.dumps(chart_data, ensure_ascii=False)) == chart_data


def test_interpretation_has_no_out_of_scope_conclusions():
    result = build_categorical_composition_analysis(
        pd.Series(["A"] * 20 + ["B"] * 10 + ["C"] * 5),
        "产品",
    )
    chart_data = build_categorical_top_n_chart_data(result, 2)

    interpretation = generate_categorical_composition_interpretation(
        "产品",
        result,
        chart_data,
    )

    assert "贡献" not in interpretation
    assert "风险" not in interpretation
    assert "建议删除" not in interpretation


def test_dataframe_height_shrinks_for_two_rows():
    two_row_height = calculate_dataframe_height(2)
    maximum_height = calculate_dataframe_height(12)

    assert two_row_height < maximum_height


def test_dataframe_height_for_nine_rows_is_between_small_and_maximum():
    two_row_height = calculate_dataframe_height(2)
    nine_row_height = calculate_dataframe_height(9)
    maximum_height = calculate_dataframe_height(12)

    assert two_row_height < nine_row_height < maximum_height


def test_dataframe_height_reaches_maximum_at_twelve_rows():
    assert calculate_dataframe_height(12) == 38 + 12 * 35 + 6


def test_dataframe_height_does_not_grow_after_twelve_rows():
    assert calculate_dataframe_height(24) == calculate_dataframe_height(12)


def test_dataframe_height_is_safe_for_zero_rows():
    assert calculate_dataframe_height(0) == 38 + 35 + 6


def test_dataframe_height_calculation_does_not_modify_table_data():
    table = pd.DataFrame(
        {
            "排名": [1, 2],
            "类别": ["A", "B"],
        }
    )
    original = table.copy(deep=True)

    calculate_dataframe_height(len(table))

    pd.testing.assert_frame_equal(table, original)


def test_high_cardinality_table_uses_limited_title():
    assert (
        categorical_composition_table_title(5001)
        == "类别构成表（页面展示前 5,000 类）"
    )
    assert categorical_composition_table_title(5000) == "完整类别构成表"
