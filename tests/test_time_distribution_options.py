import copy
from pathlib import Path

import pandas as pd

from src.exploration import (
    build_exploration_field_roles,
    build_time_distribution_analysis,
    get_time_distribution_datetime_columns,
    resolve_time_distribution_datetime_selection,
)


APP_SOURCE = Path("app.py").read_text(encoding="utf-8")
TIME_TAB_SOURCE = APP_SOURCE.split(
    "with exploration_tabs[2]:",
    maxsplit=1,
)[1].split(
    "with exploration_tabs[3]:",
    maxsplit=1,
)[0]


def _all_datetime_roles(columns):
    return {
        "role_by_column": {
            column: "datetime"
            for column in columns
        },
        "columns_by_role": {
            "datetime": list(columns),
        },
    }


def test_correct_final_roles_return_only_complete_date():
    df = pd.DataFrame(
        {
            "成交日期": ["2020-04-01", "2020-06-30"],
            "成交年份": [2020, 2020],
            "成交月份": [4, 6],
        }
    )
    roles = build_exploration_field_roles(
        df,
        datetime_columns=list(df.columns),
    )

    assert get_time_distribution_datetime_columns(df, roles) == ["成交日期"]


def test_misclassified_year_in_datetime_role_is_defensively_excluded():
    df = pd.DataFrame(
        {
            "成交日期": ["2020-04-01", "2020-06-30"],
            "成交年份": [2020, 2020],
        }
    )
    incorrect_roles = _all_datetime_roles(df.columns)

    assert get_time_distribution_datetime_columns(
        df,
        incorrect_roles,
    ) == ["成交日期"]


def test_misclassified_month_in_datetime_role_is_defensively_excluded():
    df = pd.DataFrame(
        {
            "成交日期": ["2020-04-01", "2020-06-30"],
            "成交月份": [4, 6],
        }
    )
    incorrect_roles = _all_datetime_roles(df.columns)

    assert get_time_distribution_datetime_columns(
        df,
        incorrect_roles,
    ) == ["成交日期"]


def test_numeric_year_dtype_is_excluded_from_options():
    df = pd.DataFrame({"成交年份": [2020, 2021]})

    assert get_time_distribution_datetime_columns(
        df,
        _all_datetime_roles(df.columns),
    ) == []


def test_numeric_month_dtype_is_excluded_from_options():
    df = pd.DataFrame({"成交月份": [4.0, 5.0, 6.0]})

    assert get_time_distribution_datetime_columns(
        df,
        _all_datetime_roles(df.columns),
    ) == []


def test_generic_numeric_datetime_role_is_excluded_without_name_hint():
    df = pd.DataFrame({"period_value": [100, 200]})

    assert get_time_distribution_datetime_columns(
        df,
        _all_datetime_roles(df.columns),
    ) == []


def test_object_complete_date_field_is_retained():
    df = pd.DataFrame({"成交日期": ["2020-04-01", "2020-06-30"]})

    assert get_time_distribution_datetime_columns(
        df,
        _all_datetime_roles(df.columns),
    ) == ["成交日期"]


def test_datetime_dtype_field_is_retained():
    df = pd.DataFrame(
        {"成交日期": pd.to_datetime(["2020-04-01", "2020-06-30"])}
    )

    assert get_time_distribution_datetime_columns(
        df,
        _all_datetime_roles(df.columns),
    ) == ["成交日期"]


def test_derived_time_role_never_enters_options():
    df = pd.DataFrame(
        {
            "成交日期": ["2020-04-01", "2020-06-30"],
            "成交年份": [2020, 2020],
        }
    )
    roles = {
        "role_by_column": {
            "成交日期": "datetime",
            "成交年份": "derived_time",
        },
        "columns_by_role": {
            "datetime": ["成交日期", "成交年份"],
            "derived_time": ["成交年份"],
        },
    }

    assert get_time_distribution_datetime_columns(df, roles) == ["成交日期"]


def test_options_preserve_dataframe_column_order():
    df = pd.DataFrame(
        {
            "更新日期": ["2020-05-01", "2020-05-02"],
            "创建日期": ["2020-04-01", "2020-04-02"],
        }
    )
    roles = _all_datetime_roles(["创建日期", "更新日期"])

    assert get_time_distribution_datetime_columns(df, roles) == [
        "更新日期",
        "创建日期",
    ]


def test_options_helper_does_not_modify_inputs():
    df = pd.DataFrame(
        {
            "成交日期": ["2020-04-01", "2020-06-30"],
            "成交年份": [2020, 2020],
        }
    )
    roles = _all_datetime_roles(df.columns)
    original_df = df.copy(deep=True)
    original_roles = copy.deepcopy(roles)

    get_time_distribution_datetime_columns(df, roles)

    pd.testing.assert_frame_equal(df, original_df)
    assert roles == original_roles


def test_real_page_builds_options_with_unique_helper():
    assert (
        "time_distribution_columns = get_time_distribution_datetime_columns("
        in TIME_TAB_SOURCE
    )
    assert "df," in TIME_TAB_SOURCE
    assert "exploration_field_roles or {}" in TIME_TAB_SOURCE


def test_real_selectbox_uses_only_filtered_options():
    selectbox_source = TIME_TAB_SOURCE.split(
        'st.selectbox(\n                "选择日期字段"',
        maxsplit=1,
    )[1].split(
        ")",
        maxsplit=1,
    )[0]

    assert "time_distribution_columns" in selectbox_source
    assert "date_columns" not in selectbox_source
    assert "datetime_columns" not in selectbox_source


def test_time_page_has_no_old_date_options_fallback():
    assert "inferred_date_columns" not in TIME_TAB_SOURCE
    assert "+ date_columns" not in TIME_TAB_SOURCE
    assert "set(datetime_columns" not in TIME_TAB_SOURCE


def test_old_year_selection_falls_back_to_complete_date():
    assert resolve_time_distribution_datetime_selection(
        ["成交日期"],
        "成交年份",
    ) == "成交日期"


def test_old_month_selection_falls_back_to_complete_date():
    assert resolve_time_distribution_datetime_selection(
        ["成交日期"],
        "成交月份",
    ) == "成交日期"


def test_dataset_key_is_in_real_selectbox_state_key():
    assert (
        'f"{active_project_id}_{time_distribution_dataset_key}"'
        in TIME_TAB_SOURCE
    )


def test_real_page_guards_selection_before_time_analysis():
    guard_position = TIME_TAB_SOURCE.index(
        "if selected_time_field not in time_distribution_columns:"
    )
    analysis_position = TIME_TAB_SOURCE.index(
        "build_time_distribution_analysis("
    )

    assert guard_position < analysis_position
    assert "selected_time_field = time_distribution_columns[0]" in TIME_TAB_SOURCE


def test_mixed_date_reproduction_keeps_all_3988_records():
    april_and_may = pd.date_range("2020-04-01", "2020-05-31")
    june = pd.date_range("2020-06-01", "2020-06-30")
    values = [
        april_and_may[index % len(april_and_may)].strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        for index in range(1657)
    ]
    values.extend(
        june[index % len(june)].strftime("%Y-%m-%d")
        for index in range(2331)
    )

    result = build_time_distribution_analysis(
        pd.Series(values),
        "成交日期",
    )

    assert result["valid_count"] == 3988
    assert result["excluded_count"] == 0
    assert result["start_date"] == "2020-04-01"
    assert result["end_date"] == "2020-06-30"


def test_numeric_time_analysis_never_returns_1970_date():
    result = build_time_distribution_analysis(
        pd.Series([2020, 2020]),
        "成交年份",
    )

    assert result["status"] == "no_valid_dates"
    assert result["start_date"] is None
    assert result["end_date"] is None
    assert "1970-01-01" not in str(result)
