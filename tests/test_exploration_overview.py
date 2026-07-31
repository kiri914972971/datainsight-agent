import json

import pandas as pd

from src.exploration import (
    build_exploration_field_roles,
    build_exploration_overview,
    get_time_distribution_datetime_columns,
)


def _build_overview(df, dataset_name="sales.csv", **role_kwargs):
    field_roles = build_exploration_field_roles(df, **role_kwargs)
    return build_exploration_overview(df, field_roles, dataset_name)


def test_overview_has_correct_row_and_column_counts():
    df = pd.DataFrame(
        {
            "产品": ["A", "B", "C"],
            "成交金额": [100.0, 200.0, 300.0],
        }
    )

    overview = _build_overview(df)

    assert overview["dataset_name"] == "sales.csv"
    assert overview["row_count"] == 3
    assert overview["column_count"] == 2


def test_overview_counts_analysis_roles():
    df = pd.DataFrame(
        {
            "销售工号": [10001, 10002],
            "成交金额": [100.0, 200.0],
            "产品": ["A", "B"],
            "成交日期": pd.to_datetime(["2026-01-01", "2026-01-02"]),
        }
    )

    overview = _build_overview(
        df,
        identifier_columns=["销售工号"],
    )

    assert overview["numeric_count"] == 1
    assert overview["categorical_count"] == 1
    assert overview["datetime_count"] == 1
    assert overview["identifier_count"] == 1


def test_boolean_is_counted_as_categorical():
    df = pd.DataFrame({"是否续约": [True, False, True]})

    overview = _build_overview(df)

    assert overview["categorical_count"] == 1
    assert overview["numeric_count"] == 0


def test_derived_time_is_not_counted_as_datetime():
    df = pd.DataFrame(
        {
            "成交年份": [2025, 2026],
            "成交月份": [1, 2],
        }
    )

    overview = _build_overview(df)

    assert overview["datetime_count"] == 0
    assert overview["numeric_count"] == 0


def test_automatic_datetime_candidates_use_final_derived_time_roles():
    df = pd.DataFrame(
        {
            "成交日期": ["2020-04-01", "2020-06-30"],
            "成交年份": [2020, 2020],
            "成交月份": [4, 6],
        }
    )
    field_roles = build_exploration_field_roles(
        df,
        datetime_columns=["成交日期", "成交年份", "成交月份"],
    )

    overview = build_exploration_overview(
        df,
        field_roles,
        "sales.csv",
    )
    excluded_by_column = {
        item["column"]: item
        for item in overview["excluded_fields"]
    }

    assert overview["datetime_count"] == 1
    assert overview["datetime_summary"]["mode"] == "single"
    assert overview["datetime_summary"]["column"] == "成交日期"
    assert overview["datetime_summary"]["start_date"] == "2020-04-01"
    assert overview["datetime_summary"]["end_date"] == "2020-06-30"
    assert get_time_distribution_datetime_columns(df, field_roles) == [
        "成交日期"
    ]
    assert excluded_by_column["成交年份"] == {
        "column": "成交年份",
        "role": "derived_time",
        "reason": "时间派生字段",
    }
    assert excluded_by_column["成交月份"] == {
        "column": "成交月份",
        "role": "derived_time",
        "reason": "时间派生字段",
    }


def test_identifier_is_not_counted_as_numeric():
    df = pd.DataFrame({"销售工号": [10001, 10002]})

    overview = _build_overview(
        df,
        identifier_columns=["销售工号"],
    )

    assert overview["identifier_count"] == 1
    assert overview["numeric_count"] == 0


def test_single_datetime_returns_date_range():
    df = pd.DataFrame(
        {
            "成交日期": ["2026-01-03", "2026-01-01", None, "2026-01-02"],
        }
    )

    overview = _build_overview(
        df,
        datetime_columns=["成交日期"],
    )
    datetime_summary = overview["datetime_summary"]

    assert datetime_summary["mode"] == "single"
    assert datetime_summary["column"] == "成交日期"
    assert datetime_summary["start_date"] == "2026-01-01"
    assert datetime_summary["end_date"] == "2026-01-03"
    assert datetime_summary["column_count"] == 1


def test_multiple_datetimes_do_not_select_primary_column():
    df = pd.DataFrame(
        {
            "下单日期": pd.to_datetime(["2026-01-01", "2026-01-02"]),
            "发货日期": pd.to_datetime(["2026-01-03", "2026-01-04"]),
        }
    )

    datetime_summary = _build_overview(df)["datetime_summary"]

    assert datetime_summary["mode"] == "multiple"
    assert datetime_summary["column"] is None
    assert datetime_summary["start_date"] is None
    assert datetime_summary["end_date"] is None
    assert datetime_summary["column_count"] == 2


def test_no_datetime_returns_none_mode():
    df = pd.DataFrame({"成交金额": [100.0, 200.0]})

    datetime_summary = _build_overview(df)["datetime_summary"]

    assert datetime_summary["mode"] == "none"
    assert datetime_summary["column_count"] == 0


def test_all_null_datetime_has_no_date_range():
    df = pd.DataFrame(
        {
            "成交日期": pd.Series([pd.NaT, pd.NaT], dtype="datetime64[ns]"),
        }
    )

    datetime_summary = _build_overview(df)["datetime_summary"]

    assert datetime_summary["mode"] == "single"
    assert datetime_summary["start_date"] is None
    assert datetime_summary["end_date"] is None


def test_unparseable_datetime_has_no_date_range():
    df = pd.DataFrame(
        {
            "成交日期": ["无法解析", "仍然无法解析"],
        }
    )

    datetime_summary = _build_overview(
        df,
        datetime_columns=["成交日期"],
    )["datetime_summary"]

    assert datetime_summary["mode"] == "single"
    assert datetime_summary["start_date"] is None
    assert datetime_summary["end_date"] is None


def test_excluded_fields_contain_only_excluded_roles():
    df = pd.DataFrame(
        {
            "销售工号": [10001, 10002],
            "成交月份": [1, 2],
            "固定状态": ["启用", "启用"],
            "备注": pd.Series([None, None], dtype="object"),
            "成交日期": pd.to_datetime(["2026-01-01", "2026-01-02"]),
            "成交金额": [100.0, 200.0],
        }
    )

    excluded_fields = _build_overview(
        df,
        identifier_columns=["销售工号"],
    )["excluded_fields"]
    role_by_column = {
        item["column"]: item["role"]
        for item in excluded_fields
    }

    assert role_by_column == {
        "销售工号": "identifier",
        "成交月份": "derived_time",
        "固定状态": "constant",
        "备注": "unsupported",
    }


def test_overview_does_not_modify_dataframe():
    df = pd.DataFrame(
        {
            "销售工号": [10001, 10002],
            "成交日期": ["2026-01-01", "2026-01-02"],
        }
    )
    original = df.copy(deep=True)
    field_roles = build_exploration_field_roles(
        df,
        identifier_columns=["销售工号"],
        datetime_columns=["成交日期"],
    )

    build_exploration_overview(df, field_roles, "sales.csv")

    pd.testing.assert_frame_equal(df, original)


def test_overview_result_is_safe_for_streamlit_display():
    df = pd.DataFrame(
        {
            "产品": ["A", "B"],
            "成交金额": [100.0, 200.0],
        }
    )

    overview = _build_overview(df)

    assert json.loads(json.dumps(overview, ensure_ascii=False)) == overview
