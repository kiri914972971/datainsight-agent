import pandas as pd

from src.exploration import (
    EXPLORATION_FIELD_ROLES,
    build_exploration_field_roles,
    is_derived_time_column,
)


def _role_for(df, column, **kwargs):
    result = build_exploration_field_roles(df, **kwargs)
    return result["role_by_column"][column]


def test_identifier_column_is_identifier():
    df = pd.DataFrame({"销售工号": [10001, 10002]})

    role = _role_for(df, "销售工号", identifier_columns=["销售工号"])

    assert role == "identifier"


def test_numeric_order_id_is_not_numeric_when_marked_as_identifier():
    df = pd.DataFrame({"订单号": [20260001, 20260002]})

    role = _role_for(df, "订单号", identifier_columns=["订单号"])

    assert role == "identifier"


def test_amount_column_is_numeric():
    df = pd.DataFrame({"成交金额": [100.5, 200.0, 350.25]})

    assert _role_for(df, "成交金额") == "numeric"


def test_low_cardinality_count_column_remains_numeric():
    df = pd.DataFrame({"成交客户数": [1, 1, 2, 2]})

    assert _role_for(df, "成交客户数") == "numeric"


def test_bool_column_is_boolean():
    df = pd.DataFrame({"是否续约": [True, False, True]})

    assert _role_for(df, "是否续约") == "boolean"


def test_object_product_column_is_categorical():
    df = pd.DataFrame({"产品": ["产品A", "产品B", "产品A"]})

    assert _role_for(df, "产品") == "categorical"


def test_high_cardinality_object_column_is_categorical():
    df = pd.DataFrame({"客户名称": [f"客户{i}" for i in range(100)]})

    assert _role_for(df, "客户名称") == "categorical"


def test_datetime_dtype_column_is_datetime():
    df = pd.DataFrame({"成交日期": pd.to_datetime(["2026-01-01", "2026-01-02"])})

    assert _role_for(df, "成交日期") == "datetime"


def test_explicit_datetime_column_is_datetime():
    df = pd.DataFrame({"签约日": ["2026/01/01", "2026/01/02"]})

    role = _role_for(df, "签约日", datetime_columns=["签约日"])

    assert role == "datetime"


def test_chinese_derived_time_columns_are_recognized():
    df = pd.DataFrame(
        {
            "成交年份": [2025, 2026],
            "成交月份": [1, 2],
            "签约年": [2025, 2026],
            "签约月": [1, 2],
        }
    )

    result = build_exploration_field_roles(df)

    assert result["role_by_column"]["成交年份"] == "derived_time"
    assert result["role_by_column"]["成交月份"] == "derived_time"
    assert result["role_by_column"]["签约年"] == "derived_time"
    assert result["role_by_column"]["签约月"] == "derived_time"


def test_derived_time_overrides_automatic_datetime_detection():
    df = pd.DataFrame(
        {
            "成交日期": ["2020-04-01", "2020-06-30"],
            "成交年份": [2020, 2020],
            "成交月份": [4, 6],
            "created_year": [2020, 2020],
            "order_month": [4, 6],
            "quarter": [2, 2],
            "weekday": [3, 2],
        }
    )

    result = build_exploration_field_roles(
        df,
        datetime_columns=list(df.columns),
    )

    assert result["role_by_column"]["成交日期"] == "datetime"
    for column in (
        "成交年份",
        "成交月份",
        "created_year",
        "order_month",
        "quarter",
        "weekday",
    ):
        assert result["role_by_column"][column] == "derived_time"


def test_confirmed_datetime_role_overrides_derived_time_name():
    df = pd.DataFrame({"成交年份": [2020, 2021]})

    role = _role_for(
        df,
        "成交年份",
        datetime_columns=["成交年份"],
        confirmed_type_by_column={"成交年份": "日期字段"},
    )

    assert role == "datetime"


def test_derived_time_helper_supports_common_english_names():
    series = pd.Series([1, 2])

    assert is_derived_time_column("year", series)
    assert is_derived_time_column("created_year", series)
    assert is_derived_time_column("order_month", series)
    assert is_derived_time_column("created_week_day", series)


def test_measure_names_are_not_misclassified_as_derived_time():
    df = pd.DataFrame(
        {
            "年销售额": [100, 200],
            "月收入": [10, 20],
            "季度目标": [30, 40],
            "month_revenue": [50, 60],
        }
    )

    result = build_exploration_field_roles(df)

    assert set(result["columns_by_role"]["numeric"]) == set(df.columns)
    assert not result["columns_by_role"]["derived_time"]


def test_constant_column_is_constant():
    df = pd.DataFrame({"固定状态": ["启用", "启用", None]})

    assert _role_for(df, "固定状态") == "constant"


def test_all_null_object_column_is_unsupported():
    df = pd.DataFrame({"备注": pd.Series([None, None], dtype="object")})

    assert _role_for(df, "备注") == "unsupported"


def test_invalid_column_is_unsupported():
    df = pd.DataFrame({"异常字段": [1, 2]})

    role = _role_for(df, "异常字段", invalid_columns=["异常字段"])

    assert role == "unsupported"


def test_each_column_appears_in_exactly_one_role_list():
    df = pd.DataFrame(
        {
            "销售工号": [10001, 10002],
            "成交金额": [100.0, 200.0],
            "产品": ["A", "B"],
            "是否续约": [True, False],
            "成交日期": pd.to_datetime(["2026-01-01", "2026-01-02"]),
            "成交月份": [1, 2],
            "固定状态": ["启用", "启用"],
            "备注": pd.Series([None, None], dtype="object"),
        }
    )

    result = build_exploration_field_roles(
        df,
        identifier_columns=["销售工号"],
    )
    listed_columns = [
        column
        for role in EXPLORATION_FIELD_ROLES
        for column in result["columns_by_role"][role]
    ]

    assert len(listed_columns) == len(df.columns)
    assert len(set(listed_columns)) == len(df.columns)
    assert set(listed_columns) == set(df.columns)


def test_excluded_reasons_are_provided_in_chinese():
    df = pd.DataFrame(
        {
            "销售工号": [10001, 10002],
            "成交月份": [1, 2],
            "固定状态": ["启用", "启用"],
            "备注": pd.Series([None, None], dtype="object"),
        }
    )

    reasons = build_exploration_field_roles(
        df,
        identifier_columns=["销售工号"],
    )["excluded_reasons"]

    assert reasons["销售工号"] == "标识符字段"
    assert reasons["成交月份"] == "时间派生字段"
    assert reasons["固定状态"] == "仅有一个有效值"
    assert reasons["备注"] == "全部为空"


def test_confirmed_type_takes_priority_over_automatic_role():
    df = pd.DataFrame({"人工确认字段": [10001, 10002]})

    role = _role_for(
        df,
        "人工确认字段",
        identifier_columns=["人工确认字段"],
        confirmed_type_by_column={"人工确认字段": "类别字段"},
    )

    assert role == "categorical"


def test_build_field_roles_does_not_modify_dataframe():
    df = pd.DataFrame(
        {
            "销售工号": [10001, 10002],
            "成交日期": ["2026-01-01", "2026-01-02"],
            "成交金额": [100.0, 200.0],
        }
    )
    original = df.copy(deep=True)

    build_exploration_field_roles(
        df,
        identifier_columns=["销售工号"],
        datetime_columns=["成交日期"],
    )

    pd.testing.assert_frame_equal(df, original)
