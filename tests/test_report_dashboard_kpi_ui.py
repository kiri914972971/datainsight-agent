import copy
import unittest
from pathlib import Path

from src.report_dashboard_kpi_ui import (
    build_dashboard_kpi_card_rows,
    format_dashboard_kpi_definition,
    format_dashboard_kpi_value,
    prepare_report_dashboard_kpi_view,
)


APP_SOURCE = (Path(__file__).resolve().parents[1] / "app.py").read_text(
    encoding="utf-8"
)


def _item(name="销售额", value=100, **overrides):
    item = {
        "kpi_id": name,
        "kpi_name": name,
        "category": "核心指标",
        "aggregation": "sum",
        "field_type": "amount",
        "value": value,
        "calculation_status": "ok",
        "calculation_message": "",
        "semantic_status": "linked",
        "business_definition": f"{name}业务定义",
    }
    item.update(overrides)
    return item


class ReportDashboardKpiUiHelperTests(unittest.TestCase):
    def test_one_to_four_cards_use_one_exact_width_row(self):
        for count in range(1, 5):
            items = [_item(f"KPI {index}") for index in range(count)]

            rows = build_dashboard_kpi_card_rows(items)

            self.assertEqual([len(row) for row in rows], [count])
            self.assertEqual(sum(map(len, rows)), count)

    def test_five_and_six_cards_wrap_to_at_most_three_columns(self):
        five = [_item(f"KPI {index}") for index in range(5)]
        six = [_item(f"KPI {index}") for index in range(6)]

        self.assertEqual(
            [len(row) for row in build_dashboard_kpi_card_rows(five)],
            [3, 2],
        )
        self.assertEqual(
            [len(row) for row in build_dashboard_kpi_card_rows(six)],
            [3, 3],
        )

    def test_empty_items_do_not_create_placeholder_rows(self):
        self.assertEqual(build_dashboard_kpi_card_rows([]), [])

    def test_view_preserves_context_order_and_limits_to_six(self):
        items = [_item(f"KPI {index}") for index in range(8)]

        view = prepare_report_dashboard_kpi_view({"items": items})

        self.assertEqual(
            [item["kpi_name"] for item in view["cards"]],
            [f"KPI {index}" for index in range(6)],
        )
        self.assertEqual(view["available_core_count"], 8)
        self.assertTrue(view["is_truncated"])

    def test_view_only_displays_successful_formal_core_kpis(self):
        items = [
            _item("核心成功"),
            _item("时间指标", category="时间指标"),
            _item("维度指标", category="维度指标"),
            _item("预留", aggregation="reserved"),
            _item("候选", lifecycle_status="candidate"),
            _item("禁用", enabled=False),
            _item("无效", validation_status="invalid"),
            _item(
                "计算失败",
                value=None,
                calculation_status="calculation_error",
                calculation_message="计算失败",
            ),
        ]

        view = prepare_report_dashboard_kpi_view({"items": items})

        self.assertEqual(
            [item["kpi_name"] for item in view["cards"]],
            ["核心成功"],
        )
        self.assertEqual(
            [row["指标名称"] for row in view["failed_rows"]],
            ["计算失败"],
        )

    def test_none_never_enters_normal_cards_or_becomes_zero(self):
        item = _item("空结果", value=None)

        view = prepare_report_dashboard_kpi_view({"items": [item]})

        self.assertEqual(view["cards"], [])
        self.assertEqual(view["failed_rows"][0]["计算状态"], "计算结果不可用")
        self.assertEqual(format_dashboard_kpi_value(item), "暂无数据")

    def test_amount_numeric_and_count_formatting(self):
        self.assertEqual(
            format_dashboard_kpi_value(_item(value=395108.35)),
            "395,108.35",
        )
        self.assertEqual(
            format_dashboard_kpi_value(
                _item(value=44, field_type="numeric")
            ),
            "44",
        )
        self.assertEqual(
            format_dashboard_kpi_value(
                _item(value=9137.268, field_type="numeric")
            ),
            "9,137.27",
        )
        for aggregation in ("count", "count_rows", "count_distinct"):
            self.assertEqual(
                format_dashboard_kpi_value(
                    _item(
                        value=3988,
                        aggregation=aggregation,
                        field_type="numeric",
                    )
                ),
                "3,988",
            )

    def test_ratio_amount_uses_amount_format(self):
        item = _item(value=1234.5, aggregation="ratio", field_type="amount")
        self.assertEqual(format_dashboard_kpi_value(item), "1,234.5")

    def test_missing_semantics_produces_one_view_level_flag(self):
        view = prepare_report_dashboard_kpi_view(
            {
                "items": [
                    _item("销售额", semantic_status="missing"),
                    _item("记录数", semantic_status="missing"),
                ]
            }
        )
        self.assertTrue(view["has_missing_semantics"])

    def test_failure_rows_use_safe_status_and_first_message_line(self):
        view = prepare_report_dashboard_kpi_view(
            {
                "items": [
                    _item(
                        "客单价",
                        value=None,
                        calculation_status="zero_denominator",
                        calculation_message="分母指标当前值为 0，无法计算比率\nTraceback...",
                    ),
                    _item(
                        "销售额",
                        value=None,
                        calculation_status="calculation_error",
                        calculation_message="计算失败",
                    ),
                ]
            }
        )

        self.assertEqual(view["failed_rows"][0]["计算状态"], "分母为 0")
        self.assertEqual(
            view["failed_rows"][0]["说明"],
            "分母指标当前值为 0，无法计算比率",
        )
        self.assertEqual(view["failed_rows"][1]["计算状态"], "计算失败")

    def test_no_failure_means_no_failure_rows(self):
        view = prepare_report_dashboard_kpi_view({"items": [_item()]})
        self.assertEqual(view["failed_rows"], [])

    def test_business_definition_is_compact_and_bounded(self):
        definition = "  销售额   按当前筛选范围统计  " + "说明" * 50
        formatted = format_dashboard_kpi_definition(definition)
        self.assertLessEqual(len(formatted), 80)
        self.assertNotIn("  ", formatted)
        self.assertTrue(formatted.endswith("…"))

    def test_helpers_do_not_modify_context(self):
        context = {"items": [_item("销售额"), _item("记录数")]}
        original = copy.deepcopy(context)

        prepare_report_dashboard_kpi_view(context)

        self.assertEqual(context, original)


class ReportDashboardKpiAppIntegrationTests(unittest.TestCase):
    def test_real_report_dashboard_uses_current_period_dataframe_for_context(self):
        filter_position = APP_SOURCE.index("dashboard_df = filter_time_slice(")
        dashboard_position = APP_SOURCE.index(
            "dashboard = generate_dashboard(", filter_position
        )
        current_period_position = APP_SOURCE.index(
            'current_period_df = dashboard.get("current_df")',
            dashboard_position,
        )
        context_position = APP_SOURCE.index(
            "dashboard_kpi_context = build_report_dashboard_kpi_context(",
            current_period_position,
        )
        render_position = APP_SOURCE.index(
            "render_report_dashboard_kpi_cards(dashboard_kpi_context)",
            context_position,
        )
        context_block = APP_SOURCE[context_position:render_position]

        self.assertLess(filter_position, dashboard_position)
        self.assertLess(dashboard_position, current_period_position)
        self.assertLess(current_period_position, context_position)
        self.assertIn("active_project_id", context_block)
        self.assertIn("current_period_df", context_block)
        self.assertNotIn("dashboard_df", context_block)

    def test_empty_current_period_does_not_build_misleading_kpi_context(self):
        current_period_position = APP_SOURCE.index(
            'current_period_df = dashboard.get("current_df")'
        )
        context_position = APP_SOURCE.index(
            "dashboard_kpi_context = build_report_dashboard_kpi_context(",
            current_period_position,
        )
        guard_block = APP_SOURCE[current_period_position:context_position]

        self.assertIn("current_period_df.empty", guard_block)
        self.assertIn("当前报表周期没有可计算数据。", guard_block)
        self.assertIn("else:", guard_block)

    def test_top_cards_render_only_from_formal_context_view(self):
        render_start = APP_SOURCE.index("def render_report_dashboard_kpi_cards(")
        render_end = APP_SOURCE.index(
            "\ndef render_appended_dataset_summary(", render_start
        )
        render_source = APP_SOURCE[render_start:render_end]

        self.assertIn("prepare_report_dashboard_kpi_view(kpi_context)", render_source)
        self.assertIn('str(item.get("kpi_name", ""))', render_source)
        self.assertNotIn('dashboard["kpi"]', render_source)
        self.assertNotIn('dashboard["mom"]', render_source)
        self.assertNotIn('dashboard["yoy"]', render_source)
        self.assertNotIn("本期", render_source)
        self.assertIn("以下指标统计当前报表周期的数据。", render_source)

    def test_legacy_fixed_card_loop_and_comparisons_are_removed(self):
        self.assertNotIn(
            'for index, metric in enumerate(["成交金额", "订单数", "客户数", "客单价"]):',
            APP_SOURCE,
        )
        self.assertNotIn('f"本期{metric}"', APP_SOURCE)
        self.assertNotIn('f"环比 {mom:+.1f}%"', APP_SOURCE)
        self.assertNotIn('f"同比 {yoy:+.1f}%"', APP_SOURCE)

    def test_period_trend_and_ai_report_paths_remain(self):
        self.assertIn('st.caption(f"当前报表周期：{dashboard[\'current_period\']}")', APP_SOURCE)
        self.assertIn('trend = dashboard["trend"]', APP_SOURCE)
        self.assertIn('title=f"{metric}{dashboard_period}趋势"', APP_SOURCE)
        self.assertIn('if st.button(f"生成AI{dashboard_period}"', APP_SOURCE)
        self.assertIn('"环比": dashboard["mom"]', APP_SOURCE)
        self.assertIn('"同比": dashboard["yoy"]', APP_SOURCE)
        self.assertIn("趋势图仍使用旧业务分析逻辑，将在后续任务迁移。", APP_SOURCE)


if __name__ == "__main__":
    unittest.main()
