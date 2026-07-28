import json

import pandas as pd

from src.exploration import build_time_distribution_analysis


def test_normal_date_field_builds_analysis():
    result = build_time_distribution_analysis(
        pd.Series(pd.to_datetime(["2026-01-01", "2026-01-02"])),
        "成交日期",
    )

    assert result["status"] == "ok"
    assert result["rows"]


def test_null_values_are_excluded():
    result = build_time_distribution_analysis(
        pd.Series(["2026-01-01", None, "2026-01-02"]),
        "成交日期",
    )

    assert result["valid_count"] == 2
    assert result["excluded_count"] == 1


def test_unparseable_strings_are_excluded():
    result = build_time_distribution_analysis(
        pd.Series(["2026-01-01", "无法解析", "2026-01-02"]),
        "成交日期",
    )

    assert result["valid_count"] == 2
    assert result["excluded_count"] == 1


def test_input_series_is_not_modified():
    series = pd.Series(["2026-01-01", None, "无法解析"])
    original = series.copy(deep=True)

    build_time_distribution_analysis(series, "成交日期")

    pd.testing.assert_series_equal(series, original)


def test_total_valid_and_excluded_counts_are_correct():
    result = build_time_distribution_analysis(
        pd.Series(["2026-01-01", "2026-01-02", None, "错误日期"]),
        "成交日期",
    )

    assert result["total_count"] == 4
    assert result["valid_count"] == 2
    assert result["excluded_count"] == 2


def test_start_and_end_dates_are_correct():
    result = build_time_distribution_analysis(
        pd.Series(["2026-04-03", "2026-04-01", "2026-04-02"]),
        "成交日期",
    )

    assert result["start_date"] == "2026-04-01"
    assert result["end_date"] == "2026-04-03"


def test_calendar_span_includes_both_endpoints():
    result = build_time_distribution_analysis(
        pd.Series(["2026-04-01", "2026-04-03"]),
        "成交日期",
    )

    assert result["calendar_span_days"] == 3


def test_active_date_count_uses_unique_natural_days():
    result = build_time_distribution_analysis(
        pd.Series(
            [
                "2026-04-01 08:00:00",
                "2026-04-01 18:00:00",
                "2026-04-02 09:00:00",
            ]
        ),
        "成交日期",
    )

    assert result["valid_count"] == 3
    assert result["active_date_count"] == 2


def test_ninety_day_span_recommends_day():
    start = pd.Timestamp("2026-01-01")
    result = build_time_distribution_analysis(
        pd.Series([start, start + pd.Timedelta(days=89)]),
        "成交日期",
    )

    assert result["calendar_span_days"] == 90
    assert result["recommended_granularity"] == "day"


def test_ninety_one_day_span_recommends_week():
    start = pd.Timestamp("2026-01-01")
    result = build_time_distribution_analysis(
        pd.Series([start, start + pd.Timedelta(days=90)]),
        "成交日期",
    )

    assert result["calendar_span_days"] == 91
    assert result["recommended_granularity"] == "week"


def test_exact_two_year_boundary_recommends_week():
    start = pd.Timestamp("2020-01-01")
    result = build_time_distribution_analysis(
        pd.Series([start, start + pd.DateOffset(years=2)]),
        "成交日期",
    )

    assert result["recommended_granularity"] == "week"


def test_more_than_two_years_recommends_month():
    start = pd.Timestamp("2020-01-01")
    result = build_time_distribution_analysis(
        pd.Series(
            [
                start,
                start + pd.DateOffset(years=2) + pd.Timedelta(days=1),
            ]
        ),
        "成交日期",
    )

    assert result["recommended_granularity"] == "month"


def test_exact_eight_year_boundary_recommends_month():
    start = pd.Timestamp("2020-01-01")
    result = build_time_distribution_analysis(
        pd.Series([start, start + pd.DateOffset(years=8)]),
        "成交日期",
    )

    assert result["recommended_granularity"] == "month"


def test_more_than_eight_years_recommends_year():
    start = pd.Timestamp("2020-01-01")
    result = build_time_distribution_analysis(
        pd.Series(
            [
                start,
                start + pd.DateOffset(years=8) + pd.Timedelta(days=1),
            ]
        ),
        "成交日期",
    )

    assert result["recommended_granularity"] == "year"


def test_day_granularity_fills_zero_record_dates():
    result = build_time_distribution_analysis(
        pd.Series(["2026-01-01", "2026-01-03"]),
        "成交日期",
        granularity="day",
    )

    assert [item["count"] for item in result["rows"]] == [1, 0, 1]
    assert result["rows"][1]["period_label"] == "2026-01-02"


def test_week_granularity_uses_monday_through_sunday():
    result = build_time_distribution_analysis(
        pd.Series(["2026-07-20", "2026-08-03"]),
        "成交日期",
        granularity="week",
    )

    assert result["rows"][0]["period_start"] == "2026-07-20"
    assert result["rows"][0]["period_end"] == "2026-07-26"


def test_week_label_has_explicit_date_range():
    result = build_time_distribution_analysis(
        pd.Series(["2026-07-22", "2026-07-23"]),
        "成交日期",
        granularity="week",
    )

    assert result["rows"][0]["period_label"] == "2026-07-20 至 2026-07-26"


def test_month_granularity_fills_zero_record_months():
    result = build_time_distribution_analysis(
        pd.Series(["2026-01-15", "2026-03-02"]),
        "成交日期",
        granularity="month",
    )

    assert [item["period_label"] for item in result["rows"]] == [
        "2026-01",
        "2026-02",
        "2026-03",
    ]
    assert [item["count"] for item in result["rows"]] == [1, 0, 1]


def test_quarter_granularity_is_correct():
    result = build_time_distribution_analysis(
        pd.Series(["2026-01-15", "2026-10-02"]),
        "成交日期",
        granularity="quarter",
    )

    assert [item["period_label"] for item in result["rows"]] == [
        "2026 Q1",
        "2026 Q2",
        "2026 Q3",
        "2026 Q4",
    ]


def test_year_granularity_is_correct():
    result = build_time_distribution_analysis(
        pd.Series(["2020-01-15", "2022-10-02"]),
        "成交日期",
        granularity="year",
    )

    assert [item["period_label"] for item in result["rows"]] == [
        "2020",
        "2021",
        "2022",
    ]


def test_rows_are_sorted_chronologically():
    result = build_time_distribution_analysis(
        pd.Series(["2026-01-03", "2026-01-01"]),
        "成交日期",
        granularity="day",
    )

    starts = [item["period_start"] for item in result["rows"]]
    assert starts == sorted(starts)


def test_row_counts_sum_to_valid_count():
    result = build_time_distribution_analysis(
        pd.Series(["2026-01-01", "2026-01-01", "2026-01-03"]),
        "成交日期",
        granularity="day",
    )

    assert sum(item["count"] for item in result["rows"]) == result["valid_count"]


def test_row_ratios_sum_to_one():
    result = build_time_distribution_analysis(
        pd.Series(["2026-01-01", "2026-01-01", "2026-01-03"]),
        "成交日期",
        granularity="day",
    )

    assert abs(sum(item["ratio"] for item in result["rows"]) - 1.0) < 1e-12


def test_zero_period_ratio_is_zero():
    result = build_time_distribution_analysis(
        pd.Series(["2026-01-01", "2026-01-03"]),
        "成交日期",
        granularity="day",
    )

    assert result["rows"][1]["count"] == 0
    assert result["rows"][1]["ratio"] == 0.0


def test_consecutive_zero_periods_are_merged():
    result = build_time_distribution_analysis(
        pd.Series(["2026-01-01", "2026-01-04"]),
        "成交日期",
        granularity="day",
    )

    assert result["zero_ranges"] == [
        {
            "start_label": "2026-01-02",
            "end_label": "2026-01-03",
            "start_date": "2026-01-02",
            "end_date": "2026-01-03",
            "period_count": 2,
            "granularity": "day",
        }
    ]


def test_zero_ranges_are_limited_to_ten():
    active_dates = pd.date_range("2026-01-01", periods=12, freq="2D")
    result = build_time_distribution_analysis(
        pd.Series(active_dates),
        "成交日期",
        granularity="day",
    )

    assert len(result["zero_ranges"]) == 10


def test_zero_ranges_are_sorted_by_length_descending():
    result = build_time_distribution_analysis(
        pd.Series(
            [
                "2026-01-01",
                "2026-01-03",
                "2026-01-08",
                "2026-01-10",
            ]
        ),
        "成交日期",
        granularity="day",
    )

    lengths = [item["period_count"] for item in result["zero_ranges"]]
    assert lengths == sorted(lengths, reverse=True)
    assert lengths[0] == 4


def test_tied_peak_uses_earliest_period():
    result = build_time_distribution_analysis(
        pd.Series(["2026-01-01", "2026-01-03"]),
        "成交日期",
        granularity="day",
    )

    assert result["peak_period"] == "2026-01-01"
    assert result["peak_count"] == 1


def test_more_than_four_hundred_points_returns_too_dense():
    start = pd.Timestamp("2020-01-01")
    result = build_time_distribution_analysis(
        pd.Series([start, start + pd.Timedelta(days=400)]),
        "成交日期",
        granularity="day",
    )

    assert result["status"] == "too_dense"
    assert result["period_count"] == 401
    assert result["rows"] == []


def test_no_valid_dates_returns_safe_state():
    result = build_time_distribution_analysis(
        pd.Series([None, "无法解析"]),
        "成交日期",
    )

    assert result["status"] == "no_valid_dates"
    assert result["rows"] == []
    assert result["zero_ranges"] == []
    assert result["peak_period"] is None


def test_single_natural_date_returns_safe_state():
    result = build_time_distribution_analysis(
        pd.Series(["2026-01-01 08:00:00", "2026-01-01 18:00:00"]),
        "成交日期",
    )

    assert result["status"] == "single_date"
    assert result["active_date_count"] == 1
    assert result["valid_count"] == 2


def test_one_period_at_selected_granularity_returns_ok():
    result = build_time_distribution_analysis(
        pd.Series(["2026-07-20", "2026-07-21"]),
        "成交日期",
        granularity="week",
    )

    assert result["status"] == "ok"
    assert result["period_count"] == 1
    assert len(result["rows"]) == 1
    assert "当前粒度下只有一个时间段" in result["interpretation"]


def test_interpretation_has_no_out_of_scope_terms():
    result = build_time_distribution_analysis(
        pd.Series(["2026-01-01", "2026-01-03"]),
        "成交日期",
        granularity="day",
    )

    assert "业绩" not in result["interpretation"]
    assert "增长" not in result["interpretation"]
    assert "风险" not in result["interpretation"]


def test_result_is_json_serializable():
    result = build_time_distribution_analysis(
        pd.Series(["2026-01-01", "2026-01-03"]),
        "成交日期",
        granularity="day",
    )

    assert json.loads(json.dumps(result, ensure_ascii=False)) == result


def test_timezone_aware_dates_keep_local_calendar_dates():
    series = pd.Series(
        pd.to_datetime(
            ["2026-01-01 23:30:00", "2026-01-02 00:30:00"]
        ).tz_localize("Asia/Shanghai")
    )

    result = build_time_distribution_analysis(
        series,
        "成交日期",
        granularity="day",
    )

    assert result["start_date"] == "2026-01-01"
    assert result["end_date"] == "2026-01-02"
    assert result["active_date_count"] == 2


def test_invalid_granularity_raises_value_error():
    try:
        build_time_distribution_analysis(
            pd.Series(["2026-01-01"]),
            "成交日期",
            granularity="hour",
        )
    except ValueError as exc:
        assert "不支持的时间粒度" in str(exc)
    else:
        raise AssertionError("非法粒度应抛出 ValueError")
