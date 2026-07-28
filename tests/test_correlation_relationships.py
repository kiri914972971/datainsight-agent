import json

import numpy as np
import pandas as pd

from src.exploration import (
    build_correlation_relationship_analysis,
    build_correlation_scatter_data,
    calculate_correlation_pairs,
    describe_correlation_strength,
    generate_correlation_relationship_interpretation,
)


def _linear_frame(size=20):
    values = np.arange(1, size + 1, dtype=float)
    return pd.DataFrame(
        {
            "a": values,
            "b": values * 2,
            "c": values[::-1],
        }
    )


def _pair(result, field_a, field_b):
    return next(
        item
        for item in result["all_pairs"]
        if item["field_a"] == field_a and item["field_b"] == field_b
    )


def _assert_raises_value_error(callback):
    try:
        callback()
    except ValueError:
        return
    raise AssertionError("应抛出 ValueError")


def test_pearson_calculates_two_numeric_fields():
    result = build_correlation_relationship_analysis(
        _linear_frame(),
        ["a", "b"],
        method="pearson",
    )

    assert result["status"] == "ok"
    assert _pair(result, "a", "b")["correlation"] == 1.0


def test_spearman_calculates_two_numeric_fields():
    values = np.arange(1, 21, dtype=float)
    df = pd.DataFrame({"a": values, "b": values ** 2})

    result = build_correlation_relationship_analysis(
        df,
        ["a", "b"],
        method="SPEARMAN",
    )

    assert result["method"] == "spearman"
    assert _pair(result, "a", "b")["correlation"] == 1.0


def test_invalid_method_raises_value_error():
    _assert_raises_value_error(
        lambda: build_correlation_relationship_analysis(
            _linear_frame(),
            ["a", "b"],
            method="kendall",
        )
    )


def test_invalid_threshold_raises_value_error():
    for threshold in (-0.01, 1.01, float("nan")):
        _assert_raises_value_error(
            lambda threshold=threshold: (
                build_correlation_relationship_analysis(
                    _linear_frame(),
                    ["a", "b"],
                    threshold=threshold,
                )
            )
        )


def test_fewer_than_two_selected_fields_is_insufficient():
    result = build_correlation_relationship_analysis(
        _linear_frame(),
        ["a"],
    )

    assert result["status"] == "insufficient_columns"
    assert result["pairs"] == []


def test_missing_field_is_excluded_safely():
    result = build_correlation_relationship_analysis(
        _linear_frame(),
        ["a", "missing"],
    )

    assert result["status"] == "insufficient_columns"
    assert result["excluded_columns"] == ["missing"]


def test_non_numeric_field_is_excluded_safely():
    df = _linear_frame()
    df["label"] = [f"类别{index}" for index in range(len(df))]

    result = build_correlation_relationship_analysis(
        df,
        ["a", "label"],
    )

    assert result["excluded_columns"] == ["label"]


def test_constant_field_is_excluded_safely():
    df = _linear_frame()
    df["constant"] = 1

    result = build_correlation_relationship_analysis(
        df,
        ["a", "constant"],
    )

    assert result["excluded_columns"] == ["constant"]


def test_nan_is_handled_pairwise():
    df = pd.DataFrame(
        {
            "a": [1, 2, 3, 4, 5, 6],
            "b": [2, 4, None, 8, 10, 12],
        }
    )

    result = build_correlation_relationship_analysis(df, ["a", "b"])

    assert _pair(result, "a", "b")["sample_size"] == 5


def test_infinity_does_not_participate():
    df = pd.DataFrame(
        {
            "a": [1, 2, 3, 4, 5, 6, 7],
            "b": [2, 4, np.inf, 8, 10, -np.inf, 14],
        }
    )

    result = build_correlation_relationship_analysis(df, ["a", "b"])

    assert _pair(result, "a", "b")["sample_size"] == 5


def test_analysis_does_not_drop_rows_across_all_selected_fields():
    df = pd.DataFrame(
        {
            "a": [1, 2, 3, 4, 5, None, None, None],
            "b": [1, 2, 3, 4, 5, 6, 7, 8],
            "c": [None, None, None, 1, 2, 3, 4, 5],
        }
    )

    result = build_correlation_relationship_analysis(
        df,
        ["a", "b", "c"],
    )

    assert _pair(result, "a", "b")["sample_size"] == 5
    assert _pair(result, "b", "c")["sample_size"] == 5


def test_different_pairs_can_have_different_sample_sizes():
    df = pd.DataFrame(
        {
            "a": [1, 2, 3, 4, 5, None, None, None],
            "b": [1, 2, 3, 4, 5, 6, 7, 8],
            "c": [None, None, None, 1, 2, 3, 4, 5],
        }
    )

    result = build_correlation_relationship_analysis(
        df,
        ["a", "b", "c"],
    )

    assert _pair(result, "a", "b")["sample_size"] == 5
    assert _pair(result, "b", "c")["sample_size"] == 5
    assert result["sample_size_matrix"]["rows"][0][2] == 2


def test_pair_with_fewer_than_five_common_rows_is_not_valid():
    df = pd.DataFrame(
        {
            "a": [1, 2, 3, 4, 5, 6, None, None],
            "b": [1, 2, 3, 4, None, None, 5, 6],
        }
    )

    result = build_correlation_relationship_analysis(df, ["a", "b"])

    assert result["status"] == "no_valid_pairs"
    assert result["all_pairs"] == []
    assert result["matrix"]["rows"][0][1] is None


def test_five_to_nineteen_rows_is_marked_as_small_sample():
    result = build_correlation_relationship_analysis(
        _linear_frame(10),
        ["a", "b"],
    )

    assert _pair(result, "a", "b")["sample_status"] == "样本较少"


def test_twenty_rows_is_marked_as_normal_sample():
    result = build_correlation_relationship_analysis(
        _linear_frame(20),
        ["a", "b"],
    )

    assert _pair(result, "a", "b")["sample_status"] == "正常"


def test_matrix_order_matches_valid_columns():
    result = build_correlation_relationship_analysis(
        _linear_frame(),
        ["c", "a", "b"],
    )

    assert result["valid_columns"] == ["c", "a", "b"]
    assert result["matrix"]["columns"] == ["c", "a", "b"]


def test_correlation_matrix_is_symmetric():
    result = build_correlation_relationship_analysis(
        _linear_frame(),
        ["a", "b", "c"],
    )
    rows = result["matrix"]["rows"]

    assert rows[0][1] == rows[1][0]
    assert rows[0][2] == rows[2][0]
    assert rows[1][2] == rows[2][1]


def test_correlation_matrix_diagonal_is_one():
    result = build_correlation_relationship_analysis(
        _linear_frame(),
        ["a", "b", "c"],
    )

    assert [row[index] for index, row in enumerate(result["matrix"]["rows"])] == [
        1.0,
        1.0,
        1.0,
    ]


def test_sample_size_matrix_is_symmetric():
    result = build_correlation_relationship_analysis(
        _linear_frame(),
        ["a", "b", "c"],
    )
    rows = result["sample_size_matrix"]["rows"]

    assert rows[0][1] == rows[1][0]
    assert rows[0][2] == rows[2][0]


def test_sample_size_matrix_diagonal_uses_finite_counts():
    df = _linear_frame()
    df.loc[0, "a"] = np.inf
    df.loc[1, "a"] = np.nan

    result = build_correlation_relationship_analysis(df, ["a", "b"])

    assert result["sample_size_matrix"]["rows"][0][0] == 18
    assert result["sample_size_matrix"]["rows"][1][1] == 20


def test_each_field_pair_appears_once():
    result = build_correlation_relationship_analysis(
        _linear_frame(),
        ["a", "b", "c"],
        threshold=0,
    )
    names = [
        (item["field_a"], item["field_b"])
        for item in result["all_pairs"]
    ]

    assert len(names) == 3
    assert len(set(names)) == 3


def test_field_is_not_paired_with_itself():
    result = build_correlation_relationship_analysis(
        _linear_frame(),
        ["a", "b", "c"],
        threshold=0,
    )

    assert all(
        item["field_a"] != item["field_b"]
        for item in result["all_pairs"]
    )


def test_threshold_only_filters_displayed_pairs():
    df = pd.DataFrame(
        {
            "a": np.arange(1, 21, dtype=float),
            "b": np.arange(1, 21, dtype=float),
            "c": [
                4, 8, 1, 7, 3, 12, 6, 2, 18, 9,
                5, 14, 10, 20, 11, 16, 13, 15, 17, 19,
            ],
        }
    )
    low = build_correlation_relationship_analysis(
        df,
        ["a", "b", "c"],
        threshold=0,
    )
    high = build_correlation_relationship_analysis(
        df,
        ["a", "b", "c"],
        threshold=0.9,
    )

    assert low["matrix"] == high["matrix"]
    assert low["all_pairs"] == high["all_pairs"]
    assert len(low["pairs"]) >= len(high["pairs"])


def test_pairs_are_sorted_by_absolute_correlation_descending():
    df = pd.DataFrame(
        {
            "a": np.arange(1, 21, dtype=float),
            "b": np.arange(1, 21, dtype=float),
            "c": [
                4, 8, 1, 7, 3, 12, 6, 2, 18, 9,
                5, 14, 10, 20, 11, 16, 13, 15, 17, 19,
            ],
        }
    )

    result = build_correlation_relationship_analysis(
        df,
        ["a", "b", "c"],
        threshold=0,
    )
    strengths = [
        item["absolute_correlation"]
        for item in result["pairs"]
    ]

    assert strengths == sorted(strengths, reverse=True)


def test_positive_correlation_direction_is_correct():
    result = build_correlation_relationship_analysis(
        _linear_frame(),
        ["a", "b"],
    )

    assert _pair(result, "a", "b")["direction"] == "正向"


def test_negative_correlation_direction_is_correct():
    result = build_correlation_relationship_analysis(
        _linear_frame(),
        ["a", "c"],
    )

    assert _pair(result, "a", "c")["direction"] == "负向"


def test_strength_labels_follow_boundaries():
    assert describe_correlation_strength(0.29) == "关系较弱"
    assert describe_correlation_strength(0.3) == "存在一定关系"
    assert describe_correlation_strength(0.5) == "中等关系"
    assert describe_correlation_strength(0.7) == "较强关系"


def test_strength_labels_use_absolute_value():
    assert describe_correlation_strength(-0.8) == "较强关系"


def test_near_complete_pair_has_definition_warning():
    result = build_correlation_relationship_analysis(
        _linear_frame(),
        ["a", "b"],
    )

    assert (
        _pair(result, "a", "b")["warning"]
        == "字段对接近完全相关，可能存在重复字段、单位转换或直接计算关系，请检查字段定义。"
    )


def test_high_relationship_adds_general_warning():
    result = build_correlation_relationship_analysis(
        _linear_frame(),
        ["a", "b"],
    )

    assert any("不代表因果关系" in item for item in result["warnings"])


def test_no_pairs_at_threshold_has_clear_interpretation():
    result = build_correlation_relationship_analysis(
        _linear_frame(),
        ["a", "b"],
        threshold=1,
    )
    result["pairs"] = []

    interpretation = generate_correlation_relationship_interpretation(result)

    assert interpretation == (
        "当前没有字段对达到 |r| ≥ 1 的显示阈值。"
        "可以调低阈值查看较弱关系。"
    )


def test_interpretation_summarizes_at_most_three_pairs():
    values = np.arange(1, 21, dtype=float)
    df = pd.DataFrame(
        {
            "a": values,
            "b": values * 2,
            "c": values * 3,
            "d": values * 4,
        }
    )

    result = build_correlation_relationship_analysis(
        df,
        ["a", "b", "c", "d"],
    )
    interpretation = result["interpretation"]

    assert "a与b" in interpretation
    assert "a与c" in interpretation
    assert "a与d" in interpretation
    assert "b与c" not in interpretation


def test_interpretation_has_no_actionable_or_causal_claim():
    result = build_correlation_relationship_analysis(
        _linear_frame(),
        ["a", "b"],
    )
    interpretation = result["interpretation"]

    assert "导致" not in interpretation
    assert "驱动因素" not in interpretation
    assert "建议提升" not in interpretation
    assert "经营风险" not in interpretation
    assert "不代表因果" in interpretation


def test_scatter_uses_pairwise_valid_finite_rows():
    df = pd.DataFrame(
        {
            "a": [1, 2, 3, 4, 5, 6, np.inf],
            "b": [2, 4, None, 8, 10, 12, 14],
        }
    )

    result = build_correlation_scatter_data(df, "a", "b")

    assert result["status"] == "ok"
    assert result["sample_size"] == 5
    assert result["displayed_point_count"] == 5


def test_scatter_fewer_than_five_rows_is_insufficient():
    df = pd.DataFrame({"a": [1, 2, 3, 4], "b": [2, 4, 6, 8]})

    result = build_correlation_scatter_data(df, "a", "b")

    assert result["status"] == "insufficient_data"
    assert result["rows"] == []


def test_scatter_more_than_five_thousand_rows_displays_five_thousand():
    values = np.arange(6000, dtype=float)
    df = pd.DataFrame({"a": values, "b": values * 2})

    result = build_correlation_scatter_data(df, "a", "b")

    assert result["sample_size"] == 6000
    assert result["displayed_point_count"] == 5000
    assert result["is_sampled"] is True


def test_scatter_correlation_uses_all_valid_rows():
    rng = np.random.default_rng(7)
    values = np.arange(6000, dtype=float)
    target = values * 0.3 + rng.normal(0, 800, size=6000)
    df = pd.DataFrame({"a": values, "b": target})
    expected = df["a"].corr(df["b"], method="pearson")

    result = build_correlation_scatter_data(df, "a", "b")

    assert abs(result["correlation"] - expected) < 1e-12


def test_scatter_sampling_is_stable_with_fixed_seed():
    values = np.arange(6000, dtype=float)
    df = pd.DataFrame({"a": values, "b": values * 2})

    first = build_correlation_scatter_data(
        df,
        "a",
        "b",
        random_state=42,
    )
    second = build_correlation_scatter_data(
        df,
        "a",
        "b",
        random_state=42,
    )

    assert first["rows"] == second["rows"]


def test_scatter_result_has_no_trendline():
    result = build_correlation_scatter_data(
        _linear_frame(),
        "a",
        "b",
    )

    assert "trendline" not in result
    assert "regression" not in result


def test_scatter_same_field_is_invalid():
    result = build_correlation_scatter_data(
        _linear_frame(),
        "a",
        "a",
    )

    assert result["status"] == "invalid_fields"


def test_analysis_does_not_modify_input_dataframe():
    df = _linear_frame()
    original = df.copy(deep=True)

    build_correlation_relationship_analysis(df, ["a", "b", "c"])

    pd.testing.assert_frame_equal(df, original)


def test_scatter_does_not_modify_input_dataframe():
    df = _linear_frame()
    original = df.copy(deep=True)

    build_correlation_scatter_data(df, "a", "b")

    pd.testing.assert_frame_equal(df, original)


def test_analysis_result_is_json_serializable():
    result = build_correlation_relationship_analysis(
        _linear_frame(),
        ["a", "b", "c"],
    )

    assert json.loads(json.dumps(result, ensure_ascii=False)) == result


def test_scatter_result_is_json_serializable():
    result = build_correlation_scatter_data(
        _linear_frame(),
        "a",
        "b",
    )

    assert json.loads(json.dumps(result, ensure_ascii=False)) == result


def test_invalid_matrix_relationship_uses_none_not_nan():
    df = pd.DataFrame(
        {
            "a": [1, 2, 3, 4, 5, 6, None, None],
            "b": [1, 2, 3, 4, None, None, 5, 6],
        }
    )

    result = build_correlation_relationship_analysis(df, ["a", "b"])
    value = result["matrix"]["rows"][0][1]

    assert value is None


def test_pearson_and_spearman_have_same_output_structure():
    df = _linear_frame()
    pearson = build_correlation_relationship_analysis(
        df,
        ["a", "b", "c"],
        method="pearson",
    )
    spearman = build_correlation_relationship_analysis(
        df,
        ["a", "b", "c"],
        method="spearman",
    )

    assert pearson.keys() == spearman.keys()
    assert pearson["matrix"].keys() == spearman["matrix"].keys()
    assert pearson["all_pairs"][0].keys() == spearman["all_pairs"][0].keys()


def test_legacy_calculate_correlation_pairs_behavior_is_unchanged():
    result = calculate_correlation_pairs(
        _linear_frame(),
        ["a", "b"],
    )

    assert list(result.columns) == [
        "字段A",
        "字段B",
        "相关系数",
        "相关强度",
        "可能含义",
    ]
    assert result.to_dict("records") == [
        {
            "字段A": "a",
            "字段B": "b",
            "相关系数": 1.0,
            "相关强度": "强相关",
            "可能含义": "a 与 b 呈强正相关，两者通常共同变化。",
        }
    ]
