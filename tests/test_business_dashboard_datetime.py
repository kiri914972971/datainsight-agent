import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.business_analysis import filter_time_slice, generate_dashboard
from src.datetime_utils import parse_datetime_series
from src.exploration import (
    build_exploration_field_roles,
    get_time_distribution_datetime_columns,
    parse_exploration_datetime_series,
)
from src.services import report_dashboard_kpi_service


DATE_COLUMN = "成交日期"


def _mixed_dashboard_dataframe() -> pd.DataFrame:
    april_and_may = pd.date_range("2020-04-01", "2020-05-31", freq="D")
    june = pd.date_range("2020-06-01", "2020-06-30", freq="D")
    first_source_dates = [
        april_and_may[index % len(april_and_may)].strftime("%Y-%m-%d %H:%M:%S")
        for index in range(1657)
    ]
    second_source_dates = [
        june[index % len(june)].strftime("%Y-%m-%d")
        for index in range(2331)
    ]
    row_count = len(first_source_dates) + len(second_source_dates)
    return pd.DataFrame(
        {
            DATE_COLUMN: first_source_dates + second_source_dates,
            "成交金额": [100.0] * row_count,
            "成交客户数": [1] * row_count,
        }
    )


def _dashboard_fields() -> dict:
    return {
        "date_column": DATE_COLUMN,
        "amount_column": "成交金额",
        "order_id_column": None,
        "customer_id_column": None,
        "customer_count_column": "成交客户数",
        "unit_price_column": None,
        "dimensions": [],
        "numeric_metrics": ["成交金额", "成交客户数"],
    }


def _formal_kpis() -> list[dict]:
    common = {
        "category": "核心指标",
        "enabled": True,
        "created_by": "user",
        "lifecycle_status": "saved",
        "validation_status": "valid",
        "validation_messages": [],
    }
    return [
        {
            **common,
            "kpi_id": "rows",
            "kpi_name": "记录数",
            "aggregation": "count_rows",
            "source_field": "",
            "field_type": "row",
        },
        {
            **common,
            "kpi_id": "customers",
            "kpi_name": "成交客户数",
            "aggregation": "sum",
            "source_field": "成交客户数",
            "field_type": "numeric",
        },
        {
            **common,
            "kpi_id": "sales",
            "kpi_name": "销售额",
            "aggregation": "sum",
            "source_field": "成交金额",
            "field_type": "amount",
        },
        {
            **common,
            "kpi_id": "aov",
            "kpi_name": "客单价",
            "aggregation": "ratio",
            "source_field": "",
            "field_type": "amount",
            "numerator_kpi_id": "sales",
            "denominator_kpi_id": "customers",
        },
    ]


def _build_test_kpi_context(
    dataframe: pd.DataFrame,
    project_id: str = "test-project",
) -> dict:
    kpis = _formal_kpis()
    with (
        patch.object(
            report_dashboard_kpi_service,
            "load_kpi_definitions",
            return_value=kpis,
        ),
        patch.object(
            report_dashboard_kpi_service,
            "list_usable_kpis",
            return_value=kpis,
        ),
        patch.object(
            report_dashboard_kpi_service,
            "load_metric_dictionary",
            return_value=[],
        ),
    ):
        return report_dashboard_kpi_service.build_report_dashboard_kpi_context(
            project_id,
            dataframe,
        )


class SharedDatetimeParserTests(unittest.TestCase):
    def test_mixed_complete_date_formats_are_all_parsed(self):
        series = pd.Series(
            [
                "2020-04-01 00:00:00",
                "2020-05-31 00:00:00",
                "2020-06-01",
                "2020-06-30",
                "not-a-date",
            ],
            index=[10, 20, 30, 40, 50],
            name=DATE_COLUMN,
        )

        parsed = parse_datetime_series(series)

        self.assertEqual(parsed.notna().sum(), 4)
        self.assertTrue(pd.isna(parsed.loc[50]))
        self.assertEqual(parsed.loc[10], pd.Timestamp("2020-04-01"))
        self.assertEqual(parsed.loc[40], pd.Timestamp("2020-06-30"))
        self.assertEqual(parsed.index.tolist(), series.index.tolist())
        self.assertEqual(parsed.name, series.name)

    def test_numeric_values_are_not_parsed_as_unix_timestamps(self):
        for values in ([2020, 2021], [4, 5, 6], [2020.0, 2021.0]):
            parsed = parse_datetime_series(pd.Series(values))
            self.assertTrue(parsed.isna().all())
            self.assertNotIn(pd.Timestamp("1970-01-01"), parsed.tolist())

    def test_shared_parser_and_exploration_wrapper_match(self):
        series = pd.Series(
            ["2020-04-01 00:00:00", "2020-06-01", "bad-date"]
        )
        pd.testing.assert_series_equal(
            parse_datetime_series(series),
            parse_exploration_datetime_series(series),
        )

    def test_parser_does_not_modify_input(self):
        series = pd.Series(
            ["2020-04-01 00:00:00", "2020-06-01", "bad-date"],
            name=DATE_COLUMN,
        )
        original = series.copy(deep=True)

        parse_datetime_series(series)

        pd.testing.assert_series_equal(series, original)


class BusinessDashboardDatetimeTests(unittest.TestCase):
    def setUp(self):
        self.dataframe = _mixed_dashboard_dataframe()

    def test_default_dashboard_slice_keeps_all_3988_rows(self):
        original = self.dataframe.copy(deep=True)

        result = filter_time_slice(self.dataframe, DATE_COLUMN)
        dates = parse_datetime_series(result[DATE_COLUMN])

        self.assertEqual(len(result), 3988)
        self.assertEqual(dates.notna().sum(), 3988)
        self.assertEqual(dates.min(), pd.Timestamp("2020-04-01"))
        self.assertEqual(dates.max(), pd.Timestamp("2020-06-30"))
        self.assertEqual((dates.max() - dates.min()).days + 1, 91)
        pd.testing.assert_frame_equal(self.dataframe, original)

    def test_month_filters_keep_april_may_and_june(self):
        expected_dates = parse_datetime_series(self.dataframe[DATE_COLUMN])
        filtered_rows = 0
        for month in (4, 5, 6):
            result = filter_time_slice(
                self.dataframe,
                DATE_COLUMN,
                year=2020,
                month=month,
            )
            result_dates = parse_datetime_series(result[DATE_COLUMN])
            expected_count = int((expected_dates.dt.month == month).sum())

            self.assertEqual(len(result), expected_count)
            self.assertGreater(len(result), 0)
            self.assertEqual(result_dates.dt.month.unique().tolist(), [month])
            filtered_rows += len(result)

        self.assertEqual(filtered_rows, 3988)

    def test_year_and_quarter_filters_keep_full_q2_dataset(self):
        by_year = filter_time_slice(self.dataframe, DATE_COLUMN, year=2020)
        by_quarter = filter_time_slice(
            self.dataframe,
            DATE_COLUMN,
            year=2020,
            quarter=2,
        )

        self.assertEqual(len(by_year), 3988)
        self.assertEqual(len(by_quarter), 3988)

    def test_dashboard_date_options_use_final_datetime_role_only(self):
        dataframe = pd.DataFrame(
            {
                DATE_COLUMN: ["2020-04-01", "2020-06-30 00:00:00"],
                "成交年份": [2020, 2020],
                "成交月份": [4, 6],
            }
        )
        field_roles = build_exploration_field_roles(
            dataframe,
            datetime_columns=[DATE_COLUMN, "成交年份", "成交月份"],
            confirmed_type_by_column={
                DATE_COLUMN: "日期字段",
                "成交年份": "日期字段",
                "成交月份": "日期字段",
            },
        )

        options = get_time_distribution_datetime_columns(dataframe, field_roles)

        self.assertEqual(options, [DATE_COLUMN])
        self.assertEqual(field_roles["role_by_column"][DATE_COLUMN], "datetime")
        self.assertEqual(
            field_roles["role_by_column"]["成交年份"],
            "derived_time",
        )
        self.assertEqual(
            field_roles["role_by_column"]["成交月份"],
            "derived_time",
        )

    def test_dashboard_current_period_current_df_and_trend_use_mixed_parser(self):
        original = self.dataframe.copy(deep=True)
        dashboard_df = filter_time_slice(self.dataframe, DATE_COLUMN)

        dashboard = generate_dashboard(
            dashboard_df,
            DATE_COLUMN,
            "日报",
            _dashboard_fields(),
            comparison_df=self.dataframe,
        )

        self.assertEqual(dashboard["current_period"], "2020-06-30")
        self.assertFalse(dashboard["current_df"].empty)
        self.assertTrue(
            (
                dashboard["current_df"][DATE_COLUMN]
                == pd.Timestamp("2020-06-30")
            ).all()
        )
        self.assertEqual(len(dashboard["trend"]), 91)
        self.assertEqual(dashboard["trend"]["周期"].iloc[0], "2020-04-01")
        self.assertEqual(dashboard["trend"]["周期"].iloc[-1], "2020-06-30")
        pd.testing.assert_frame_equal(self.dataframe, original)

    def test_kpi_context_uses_daily_current_df_while_trend_keeps_full_range(self):
        dashboard_df = filter_time_slice(self.dataframe, DATE_COLUMN)
        dashboard = generate_dashboard(
            dashboard_df,
            DATE_COLUMN,
            "日报",
            _dashboard_fields(),
            comparison_df=self.dataframe,
        )

        context = _build_test_kpi_context(dashboard["current_df"])
        values = {item["kpi_name"]: item["value"] for item in context["items"]}

        self.assertEqual(context["dataset_row_count"], len(dashboard["current_df"]))
        self.assertEqual(values["记录数"], len(dashboard["current_df"]))
        self.assertEqual(values["成交客户数"], len(dashboard["current_df"]))
        self.assertEqual(values["销售额"], len(dashboard["current_df"]) * 100.0)
        self.assertEqual(values["客单价"], 100.0)
        self.assertEqual(len(dashboard_df), 3988)
        self.assertEqual(len(dashboard["trend"]), 91)

    def test_all_report_periods_build_kpis_from_matching_current_df(self):
        dashboard_df = filter_time_slice(self.dataframe, DATE_COLUMN)
        expected_periods = {
            "日报": "2020-06-30",
            "周报": "2020-06-29/2020-07-05",
            "月报": "2020-06",
            "季报": "2020Q2",
            "年报": "2020",
        }

        for period, expected_current_period in expected_periods.items():
            with self.subTest(period=period):
                dashboard = generate_dashboard(
                    dashboard_df,
                    DATE_COLUMN,
                    period,
                    _dashboard_fields(),
                    comparison_df=self.dataframe,
                )
                context = _build_test_kpi_context(dashboard["current_df"])
                record_item = next(
                    item for item in context["items"] if item["kpi_name"] == "记录数"
                )

                self.assertEqual(dashboard["current_period"], expected_current_period)
                self.assertFalse(dashboard["current_df"].empty)
                self.assertEqual(
                    context["dataset_row_count"],
                    len(dashboard["current_df"]),
                )
                self.assertEqual(
                    record_item["value"],
                    len(dashboard["current_df"]),
                )

    def test_latest_period_changes_with_month_filter_without_stale_kpis(self):
        may_df = filter_time_slice(
            self.dataframe,
            DATE_COLUMN,
            year=2020,
            month=5,
        )
        june_df = filter_time_slice(
            self.dataframe,
            DATE_COLUMN,
            year=2020,
            month=6,
        )

        may_dashboard = generate_dashboard(
            may_df,
            DATE_COLUMN,
            "日报",
            _dashboard_fields(),
            comparison_df=self.dataframe,
        )
        june_dashboard = generate_dashboard(
            june_df,
            DATE_COLUMN,
            "日报",
            _dashboard_fields(),
            comparison_df=self.dataframe,
        )
        may_context = _build_test_kpi_context(may_dashboard["current_df"])
        june_context = _build_test_kpi_context(june_dashboard["current_df"])

        self.assertEqual(may_dashboard["current_period"], "2020-05-31")
        self.assertEqual(june_dashboard["current_period"], "2020-06-30")
        self.assertEqual(
            may_context["dataset_row_count"],
            len(may_dashboard["current_df"]),
        )
        self.assertEqual(
            june_context["dataset_row_count"],
            len(june_dashboard["current_df"]),
        )

    def test_weekly_filter_switch_rebuilds_kpis_and_keeps_full_slice_trends(self):
        month_dashboards = {}
        month_contexts = {}
        for month in (5, 6):
            dashboard_df = filter_time_slice(
                self.dataframe,
                DATE_COLUMN,
                year=2020,
                month=month,
            )
            dashboard = generate_dashboard(
                dashboard_df,
                DATE_COLUMN,
                "周报",
                _dashboard_fields(),
                comparison_df=self.dataframe,
            )
            context = _build_test_kpi_context(dashboard["current_df"])
            record_item = next(
                item for item in context["items"] if item["kpi_name"] == "记录数"
            )

            self.assertEqual(
                context["dataset_row_count"],
                len(dashboard["current_df"]),
            )
            self.assertEqual(record_item["value"], len(dashboard["current_df"]))
            self.assertEqual(
                int(dashboard["trend"]["订单数"].sum()),
                len(dashboard_df),
            )
            self.assertTrue(
                dashboard["trend"]["周期"].astype(str).str.contains("/").all()
            )
            month_dashboards[month] = dashboard
            month_contexts[month] = context

        self.assertEqual(
            month_dashboards[5]["current_period"],
            "2020-05-25/2020-05-31",
        )
        self.assertEqual(
            month_dashboards[6]["current_period"],
            "2020-06-29/2020-07-05",
        )
        self.assertNotEqual(
            month_contexts[5]["dataset_row_count"],
            month_contexts[6]["dataset_row_count"],
        )

    def test_weekly_context_calls_keep_project_and_filter_results_isolated(self):
        may_df = filter_time_slice(
            self.dataframe,
            DATE_COLUMN,
            year=2020,
            month=5,
        )
        june_df = filter_time_slice(
            self.dataframe,
            DATE_COLUMN,
            year=2020,
            month=6,
        )
        may_dashboard = generate_dashboard(
            may_df,
            DATE_COLUMN,
            "周报",
            _dashboard_fields(),
            comparison_df=self.dataframe,
        )
        june_dashboard = generate_dashboard(
            june_df,
            DATE_COLUMN,
            "周报",
            _dashboard_fields(),
            comparison_df=self.dataframe,
        )

        project_a_context = _build_test_kpi_context(
            may_dashboard["current_df"],
            project_id="project-a",
        )
        project_b_context = _build_test_kpi_context(
            june_dashboard["current_df"],
            project_id="project-b",
        )

        self.assertEqual(project_a_context["project_id"], "project-a")
        self.assertEqual(project_b_context["project_id"], "project-b")
        self.assertEqual(
            project_a_context["dataset_row_count"],
            len(may_dashboard["current_df"]),
        )
        self.assertEqual(
            project_b_context["dataset_row_count"],
            len(june_dashboard["current_df"]),
        )

    def test_real_appended_dataset_matches_acceptance_baseline_when_available(self):
        dataset_path = Path(
            "workspace/projects/project-7120e1b2/analysis/appended_dataset.csv"
        )
        if not dataset_path.is_file():
            self.skipTest("当前工作区未提供验收用 appended_dataset.csv")

        dataframe = pd.read_csv(dataset_path)
        parsed = parse_datetime_series(dataframe[DATE_COLUMN])
        dashboard_df = filter_time_slice(dataframe, DATE_COLUMN)

        self.assertEqual(len(dataframe), 3988)
        self.assertEqual(parsed.notna().sum(), 3988)
        self.assertEqual(parsed.min(), pd.Timestamp("2020-04-01"))
        self.assertEqual(parsed.max(), pd.Timestamp("2020-06-30"))
        self.assertEqual((parsed.max() - parsed.min()).days + 1, 91)
        self.assertEqual(len(dashboard_df), 3988)

    def test_real_june_30_kpis_use_67_row_current_period_when_available(self):
        dataset_path = Path(
            "workspace/projects/project-7120e1b2/analysis/appended_dataset.csv"
        )
        if not dataset_path.is_file():
            self.skipTest("当前工作区未提供验收用 appended_dataset.csv")

        dataframe = pd.read_csv(dataset_path)
        dashboard_df = filter_time_slice(dataframe, DATE_COLUMN)
        dashboard = generate_dashboard(
            dashboard_df,
            DATE_COLUMN,
            "日报",
            _dashboard_fields(),
            comparison_df=dataframe,
        )
        context = _build_test_kpi_context(dashboard["current_df"])
        values = {item["kpi_name"]: item["value"] for item in context["items"]}

        expected_customers = pd.to_numeric(
            dashboard["current_df"]["成交客户数"], errors="coerce"
        ).sum()
        expected_sales = pd.to_numeric(
            dashboard["current_df"]["成交金额"], errors="coerce"
        ).sum()
        self.assertEqual(dashboard["current_period"], "2020-06-30")
        self.assertEqual(len(dashboard["current_df"]), 67)
        self.assertEqual(values["记录数"], 67)
        self.assertEqual(values["成交客户数"], expected_customers)
        self.assertEqual(values["销售额"], expected_sales)
        self.assertAlmostEqual(
            values["客单价"],
            expected_sales / expected_customers,
        )
        self.assertEqual(len(dashboard["trend"]), 91)


class BusinessDashboardDatetimeIntegrationTests(unittest.TestCase):
    def test_report_dashboard_selectbox_uses_unified_datetime_options(self):
        root = Path(__file__).resolve().parents[1]
        app_source = (root / "app.py").read_text(encoding="utf-8")
        report_start = app_source.index('with business_tabs[0]:')
        report_end = app_source.index('with business_tabs[1]:', report_start)
        report_source = app_source[report_start:report_end]
        selectbox_start = report_source.index(
            'selected_date_column = dashboard_controls[1].selectbox('
        )
        selectbox_end = report_source.index(
            "business_dates = parse_datetime_series",
            selectbox_start,
        )
        selectbox_source = report_source[selectbox_start:selectbox_end]

        self.assertIn(
            "dashboard_date_options = get_time_distribution_datetime_columns(",
            report_source,
        )
        self.assertIn("dashboard_date_options,", selectbox_source)
        self.assertNotIn("date_columns,", selectbox_source)
        self.assertIn(
            "resolve_time_distribution_datetime_selection(",
            report_source,
        )
        self.assertIn("active_project_id", report_source)
        self.assertIn("dashboard_dataset_key", report_source)
        self.assertIn("business_dashboard_date_", report_source)
        self.assertIn(
            "st.session_state[dashboard_date_key] = resolved_dashboard_date",
            report_source,
        )

    def test_app_and_business_dashboard_use_shared_parser(self):
        root = Path(__file__).resolve().parents[1]
        app_source = (root / "app.py").read_text(encoding="utf-8")
        business_source = (root / "src/business_analysis.py").read_text(
            encoding="utf-8"
        )
        report_start = app_source.index('with business_tabs[0]:')
        report_end = app_source.index('with business_tabs[1]:', report_start)
        report_source = app_source[report_start:report_end]

        self.assertIn(
            "business_dates = parse_datetime_series(df[selected_date_column])",
            report_source,
        )
        self.assertNotIn(
            "business_dates = pd.to_datetime",
            report_source,
        )
        self.assertIn(
            "temp[date_column] = parse_datetime_series(temp[date_column])",
            business_source,
        )
        self.assertIn(
            "history[date_column] = parse_datetime_series(history[date_column])",
            business_source,
        )
        self.assertIn(
            "dates = parse_datetime_series(df[date_column])",
            business_source,
        )


if __name__ == "__main__":
    unittest.main()
