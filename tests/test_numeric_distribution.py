import json

import numpy as np
import pandas as pd

from src.exploration import (
    build_discrete_numeric_frequency_table,
    build_numeric_distribution_analysis,
    calculate_histogram_bin_count,
    classify_numeric_distribution,
    generate_numeric_distribution_interpretation,
)


def test_numeric_field_builds_statistics():
    series = pd.Series([10, 20, 30, 40, 50], name="成交金额")

    result = build_numeric_distribution_analysis(series, "成交金额")

    assert result["status"] == "ok"
    assert result["summary"]["mean"] == 30.0
    assert result["summary"]["median"] == 30.0
    assert result["summary"]["std"] == series.std()


def test_nan_is_excluded_from_statistics():
    series = pd.Series([1.0, 2.0, np.nan, 3.0, 4.0, 5.0])

    result = build_numeric_distribution_analysis(series, "客单价")

    assert result["valid_count"] == 5
    assert result["summary"]["mean"] == 3.0


def test_positive_and_negative_infinity_are_excluded():
    series = pd.Series([1.0, 2.0, np.inf, -np.inf, 3.0])

    result = build_numeric_distribution_analysis(series, "客单价")

    assert result["valid_count"] == 3
    assert result["excluded_count"] == 2
    assert result["values"] == [1.0, 2.0, 3.0]


def test_input_series_is_not_modified():
    series = pd.Series([1.0, np.nan, np.inf, 4.0])
    original = series.copy(deep=True)

    build_numeric_distribution_analysis(series, "客单价")

    pd.testing.assert_series_equal(series, original)


def test_valid_and_excluded_counts_are_correct():
    series = pd.Series([1, "2", "无法转换", None, np.inf, 3])

    result = build_numeric_distribution_analysis(series, "数量")

    assert result["total_count"] == 6
    assert result["valid_count"] == 3
    assert result["excluded_count"] == 3


def test_integer_with_at_most_30_unique_values_is_discrete():
    series = pd.Series([1, 2, 3, 1, 2, 3])

    assert classify_numeric_distribution(series) == "discrete"


def test_non_integer_values_are_continuous():
    series = pd.Series([1.1, 2.2, 3.3, 4.4, 5.5])

    assert classify_numeric_distribution(series) == "continuous"


def test_integer_with_more_than_30_unique_values_is_continuous():
    series = pd.Series(range(31))

    assert classify_numeric_distribution(series) == "continuous"


def test_discrete_frequency_table_is_sorted_by_value():
    series = pd.Series([3, 1, 2, 3, 1, 3])

    table = build_discrete_numeric_frequency_table(series)

    assert table == [
        {"value": 1, "count": 2},
        {"value": 2, "count": 1},
        {"value": 3, "count": 3},
    ]


def test_continuous_default_bin_count_is_within_limits():
    series = pd.Series(np.linspace(0.1, 100.9, 500))

    bin_count = calculate_histogram_bin_count(series)

    assert 10 <= bin_count <= 50


def test_histogram_bin_count_is_stable():
    series = pd.Series(np.linspace(0.1, 100.9, 500))

    first = calculate_histogram_bin_count(series)
    second = calculate_histogram_bin_count(series)

    assert first == second


def test_summary_contains_all_core_statistics():
    result = build_numeric_distribution_analysis(
        pd.Series([1, 2, 3, 4, 5]),
        "数量",
    )

    assert set(result["summary"]) == {
        "mean",
        "median",
        "std",
        "min",
        "q1",
        "q3",
        "max",
    }


def test_advanced_statistics_contains_required_fields():
    result = build_numeric_distribution_analysis(
        pd.Series(range(1, 21)),
        "数量",
    )

    assert set(result["advanced"]) == {
        "p10",
        "p25",
        "p50",
        "p75",
        "p90",
        "skew",
        "kurtosis",
    }


def test_fewer_than_five_valid_values_is_insufficient():
    result = build_numeric_distribution_analysis(
        pd.Series([1, 2, 3, 4, np.nan]),
        "数量",
    )

    assert result["status"] == "insufficient_data"


def test_constant_input_returns_constant():
    result = build_numeric_distribution_analysis(
        pd.Series([5] * 10),
        "固定数量",
    )

    assert result["status"] == "constant"


def test_small_sample_does_not_make_skewness_claim():
    interpretation = generate_numeric_distribution_interpretation(
        pd.Series([1.0, 1.1, 1.2, 10.0]),
        "客单价",
    )

    assert interpretation == "当前有效样本较少，分布特征可能不稳定。"
    assert "右偏" not in interpretation
    assert "左偏" not in interpretation


def test_clearly_right_skewed_data_has_right_skew_description():
    series = pd.Series(
        [1.0 + index / 100 for index in range(30)] + [100.0]
    )

    interpretation = generate_numeric_distribution_interpretation(
        series,
        "成交金额",
    )

    assert "右偏" in interpretation
    assert "少数较高取值可能拉高均值" in interpretation


def test_clearly_left_skewed_data_has_left_skew_description():
    series = pd.Series(
        [-100.0] + [1.0 + index / 100 for index in range(30)]
    )

    interpretation = generate_numeric_distribution_interpretation(
        series,
        "成交金额",
    )

    assert "左偏" in interpretation
    assert "少数较低取值可能拉低均值" in interpretation


def test_statistics_remain_numeric_not_scientific_notation_strings():
    result = build_numeric_distribution_analysis(
        pd.Series([1_000_000_000, 2_000_000_000, 3_000_000_000, 4_000_000_000, 5_000_000_000]),
        "成交金额",
    )

    values = list(result["summary"].values()) + list(result["advanced"].values())

    assert all(value is None or isinstance(value, (int, float)) for value in values)
    assert not any(isinstance(value, str) and "e" in value.lower() for value in values)


def test_result_is_json_serializable_for_streamlit():
    result = build_numeric_distribution_analysis(
        pd.Series([1.1, 2.2, 3.3, 4.4, 5.5]),
        "客单价",
    )

    assert json.loads(json.dumps(result, ensure_ascii=False)) == result
