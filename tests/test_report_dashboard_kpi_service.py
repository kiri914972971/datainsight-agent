import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src import project_workspace
from src.services import report_dashboard_kpi_service as service
from src.services.kpi_service import save_kpi_definitions
from src.services.metric_dictionary_service import save_metric_dictionary


def _kpi(
    kpi_id,
    kpi_name,
    aggregation="sum",
    source_field="成交金额",
    field_type="amount",
    enabled=True,
    **overrides,
):
    result = {
        "kpi_id": kpi_id,
        "kpi_name": kpi_name,
        "category": "核心指标",
        "aggregation": aggregation,
        "source_field": source_field,
        "field_type": field_type,
        "enabled": enabled,
        "created_by": "user",
        "lifecycle_status": "saved",
        "validation_status": "valid",
        "validation_messages": [],
    }
    result.update(overrides)
    return result


def _semantic(linked_kpi_id, linked_kpi_name, **overrides):
    result = {
        "metric_id": f"metric-{linked_kpi_id}",
        "metric_name": linked_kpi_name,
        "metric_type": "核心指标",
        "business_definition": f"{linked_kpi_name}的业务定义",
        "aliases": [f"{linked_kpi_name}别名"],
        "linked_kpi_id": linked_kpi_id,
        "linked_kpi_name": linked_kpi_name,
        "enabled": True,
        "created_by": "auto",
    }
    result.update(overrides)
    return result


class ReportDashboardKpiContextTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame(
            {
                "成交金额": [100.0, 200.0, None],
                "客户ID": ["A", "A", "B"],
                "成交客户数": [2, 1, 0],
                "零值": [0, 0, 0],
            }
        )

    def build(self, usable, saved=None, semantics=None, dataframe=None):
        with (
            patch.object(
                service,
                "load_kpi_definitions",
                return_value=copy.deepcopy(saved if saved is not None else usable),
            ),
            patch.object(
                service,
                "list_usable_kpis",
                return_value=copy.deepcopy(usable),
            ) as usable_loader,
            patch.object(
                service,
                "load_metric_dictionary",
                return_value=copy.deepcopy(semantics or []),
            ),
        ):
            result = service.build_report_dashboard_kpi_context(
                "project-a",
                self.df if dataframe is None else dataframe,
            )
        return result, usable_loader

    def test_only_list_usable_kpis_output_enters_context(self):
        formal = _kpi("sales", "销售额")
        excluded = [
            _kpi("candidate", "候选", lifecycle_status="candidate"),
            _kpi("pending", "待完善", validation_status="pending"),
            _kpi("invalid", "异常", validation_status="invalid"),
            _kpi("disabled", "禁用", enabled=False),
            _kpi("reserved", "预留", aggregation="reserved", field_type="date"),
        ]

        context, usable_loader = self.build([formal], [formal, *excluded])

        self.assertEqual([item["kpi_id"] for item in context["items"]], ["sales"])
        self.assertEqual(context["usable_kpi_count"], 1)
        usable_loader.assert_called_once_with(
            "project-a",
            available_fields=["成交金额", "客户ID", "成交客户数", "零值"],
        )

    def test_all_basic_aggregations_reuse_engine_results(self):
        kpis = [
            _kpi("sum", "销售额", "sum"),
            _kpi("count", "金额非空数", "count"),
            _kpi("rows", "记录数", "count_rows", "", "row"),
            _kpi("distinct", "客户数", "count_distinct", "客户ID", "id"),
            _kpi("avg", "平均金额", "avg"),
            _kpi("max", "最大金额", "max"),
            _kpi("min", "最小金额", "min"),
        ]

        context, _ = self.build(kpis)
        values = {item["kpi_id"]: item["value"] for item in context["items"]}

        self.assertEqual(values["sum"], 300.0)
        self.assertEqual(values["count"], 2)
        self.assertEqual(values["rows"], 3)
        self.assertEqual(values["distinct"], 2)
        self.assertEqual(values["avg"], 150.0)
        self.assertEqual(values["max"], 200.0)
        self.assertEqual(values["min"], 100.0)
        self.assertEqual(context["calculated_kpi_count"], 7)
        self.assertEqual(context["failed_kpi_count"], 0)

    def test_ratio_uses_disabled_valid_basic_dependencies(self):
        sales = _kpi("sales", "销售额", enabled=False)
        customers = _kpi(
            "customers",
            "成交客户数",
            "sum",
            "成交客户数",
            "numeric",
            enabled=False,
        )
        ratio = _kpi(
            "aov",
            "客单价",
            "ratio",
            "",
            "amount",
            numerator_kpi_id="sales",
            denominator_kpi_id="customers",
        )

        context, _ = self.build([ratio], [sales, customers, ratio])
        item = context["items"][0]

        self.assertEqual(item["value"], 100.0)
        self.assertEqual(item["calculation_status"], "ok")
        self.assertEqual(item["formula"], "销售额 ÷ 成交客户数")

    def test_zero_denominator_is_not_coerced_to_zero(self):
        sales = _kpi("sales", "销售额", enabled=False)
        zero = _kpi(
            "zero",
            "零分母",
            "sum",
            "零值",
            "numeric",
            enabled=False,
        )
        ratio = _kpi(
            "ratio",
            "零除测试",
            "ratio",
            "",
            "numeric",
            numerator_kpi_id="sales",
            denominator_kpi_id="zero",
        )

        context, _ = self.build([ratio], [sales, zero, ratio])
        item = context["items"][0]

        self.assertIsNone(item["value"])
        self.assertEqual(item["calculation_status"], "zero_denominator")
        self.assertEqual(item["numerator_value"], 300.0)
        self.assertEqual(item["denominator_value"], 0.0)
        self.assertEqual(context["failed_kpi_count"], 1)

    def test_missing_ratio_dependency_returns_safe_failure_and_readable_formula(self):
        ratio = _kpi(
            "ratio",
            "缺失依赖比率",
            "ratio",
            "",
            "numeric",
            numerator_kpi_id="missing-a",
            denominator_kpi_id="missing-b",
        )

        context, _ = self.build([ratio], [ratio])
        item = context["items"][0]

        self.assertIsNone(item["value"])
        self.assertEqual(item["calculation_status"], "missing_dependency")
        self.assertEqual(item["formula"], "分子指标不可用 ÷ 分母指标不可用")
        self.assertNotIn("missing-a", item["formula"])

    def test_enabled_active_semantic_is_merged_by_kpi_id(self):
        sales = _kpi("sales", "销售额")
        semantics = [
            _semantic("same-name-other-id", "销售额"),
            _semantic("sales", "销售额", aliases=["GMV", "Revenue"]),
        ]

        context, _ = self.build([sales], [sales], semantics)
        item = context["items"][0]

        self.assertEqual(item["semantic_status"], "linked")
        self.assertEqual(item["business_definition"], "销售额的业务定义")
        self.assertEqual(item["aliases"], ["GMV", "Revenue"])

    def test_disabled_invalid_and_unlinked_semantics_are_not_merged(self):
        sales = _kpi("sales", "销售额")
        semantic_cases = [
            [_semantic("sales", "销售额", enabled=False)],
            [_semantic("deleted", "销售额")],
            [_semantic("", "销售额")],
        ]

        for semantics in semantic_cases:
            context, _ = self.build([sales], [sales], semantics)
            item = context["items"][0]
            self.assertEqual(item["semantic_status"], "missing")
            self.assertEqual(item["business_definition"], "")
            self.assertEqual(item["aliases"], [])
            self.assertIn(
                "指标 销售额 尚未保存有效业务语义定义。",
                context["warnings"],
            )

    def test_output_is_json_safe_native_and_stable(self):
        kpis = [
            _kpi("rows", "记录数", "count_rows", "", "row"),
            _kpi("sales", "销售额"),
        ]

        first, _ = self.build(kpis)
        second, _ = self.build(kpis)

        self.assertEqual(first, second)
        self.assertEqual([item["kpi_id"] for item in first["items"]], ["rows", "sales"])
        self.assertIsInstance(first["items"][0]["value"], int)
        self.assertIsInstance(first["items"][1]["value"], float)
        self.assertTrue(json.dumps(first, ensure_ascii=False))
        self.assertFalse(
            any(
                isinstance(value, (pd.DataFrame, pd.Series))
                for item in first["items"]
                for value in item.values()
            )
        )

    def test_non_finite_and_engine_exception_become_calculation_error(self):
        sales = _kpi("sales", "销售额")
        with patch.object(
            service,
            "calculate_basic_kpi",
            return_value={"status": "ok", "value": float("inf"), "message": ""},
        ):
            non_finite, _ = self.build([sales])
        with patch.object(
            service,
            "calculate_basic_kpi",
            side_effect=RuntimeError("boom"),
        ):
            failed, _ = self.build([sales])

        self.assertEqual(
            non_finite["items"][0]["calculation_status"], "calculation_error"
        )
        self.assertIsNone(non_finite["items"][0]["value"])
        self.assertEqual(
            failed["items"][0]["calculation_status"], "calculation_error"
        )
        self.assertIn("boom", failed["items"][0]["calculation_message"])

    def test_existing_failure_statuses_are_preserved_and_never_use_zero(self):
        sales = _kpi("sales", "销售额")
        for status in ("dependency_error", "invalid_definition", "unsupported"):
            with patch.object(
                service,
                "calculate_basic_kpi",
                return_value={
                    "status": status,
                    "value": 99,
                    "message": f"{status} message",
                },
            ):
                context, _ = self.build([sales])
            item = context["items"][0]
            self.assertEqual(item["calculation_status"], status)
            self.assertIsNone(item["value"])
            self.assertEqual(item["calculation_message"], f"{status} message")

    def test_loaded_kpi_and_semantic_definitions_are_not_modified(self):
        sales = _kpi("sales", "销售额")
        semantic = _semantic("sales", "销售额")
        original_kpi = copy.deepcopy(sales)
        original_semantic = copy.deepcopy(semantic)
        with (
            patch.object(service, "load_kpi_definitions", return_value=[sales]),
            patch.object(service, "list_usable_kpis", return_value=[sales]),
            patch.object(
                service, "load_metric_dictionary", return_value=[semantic]
            ),
        ):
            context = service.build_report_dashboard_kpi_context(
                "project-a", self.df
            )

        self.assertEqual(context["project_id"], "project-a")
        self.assertEqual(context["dataset_row_count"], 3)
        self.assertEqual(sales, original_kpi)
        self.assertEqual(semantic, original_semantic)

    def test_empty_dataframe_and_inputs_are_not_modified(self):
        empty = self.df.iloc[0:0].copy()
        rows = _kpi("rows", "记录数", "count_rows", "", "row")
        semantics = [_semantic("rows", "记录数")]
        original_df = empty.copy(deep=True)
        original_kpi = copy.deepcopy(rows)
        original_semantics = copy.deepcopy(semantics)

        context, _ = self.build([rows], [rows], semantics, dataframe=empty)

        self.assertEqual(context["dataset_row_count"], 0)
        self.assertEqual(context["items"][0]["value"], 0)
        pd.testing.assert_frame_equal(empty, original_df)
        self.assertEqual(rows, original_kpi)
        self.assertEqual(semantics, original_semantics)

    def test_no_formal_kpi_means_no_hardcoded_fallback(self):
        context, _ = self.build([], [])

        self.assertEqual(context["items"], [])
        self.assertEqual(context["usable_kpi_count"], 0)
        self.assertEqual(context["calculated_kpi_count"], 0)
        serialized = json.dumps(context, ensure_ascii=False)
        for forbidden in ("订单数", "客户数", "客单价", "销售额"):
            self.assertNotIn(forbidden, serialized)


class ReportDashboardKpiProjectIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "projects"
        self.root_patch = patch.object(
            project_workspace,
            "PROJECT_ROOT",
            self.project_root,
        )
        self.root_patch.start()
        self.project_a = project_workspace.create_project("KPI Context A")
        self.project_b = project_workspace.create_project("KPI Context B")

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def _save_project(self, project_id, kpi_id, definition):
        kpi = _kpi(kpi_id, "销售额")
        save_kpi_definitions(
            project_id,
            [kpi],
            available_fields=["成交金额"],
        )
        save_metric_dictionary(
            project_id,
            [
                _semantic(
                    kpi_id,
                    "销售额",
                    business_definition=definition,
                )
            ],
        )

    def test_projects_are_isolated_and_adapter_does_not_write_configs(self):
        self._save_project(self.project_a["project_id"], "sales-a", "项目 A 口径")
        self._save_project(self.project_b["project_id"], "sales-b", "项目 B 口径")
        dataframe = pd.DataFrame({"成交金额": [10.0, 20.0]})
        original = dataframe.copy(deep=True)
        watched_paths = []
        for project in (self.project_a, self.project_b):
            project_path = self.project_root / project["project_id"]
            watched_paths.extend(
                [
                    project_path / "project.json",
                    project_path / "config" / "kpi_definitions.json",
                    project_path / "config" / "metric_dictionary.json",
                ]
            )
        before = {path: path.read_bytes() for path in watched_paths}

        context_a = service.build_report_dashboard_kpi_context(
            self.project_a["project_id"], dataframe
        )
        context_b = service.build_report_dashboard_kpi_context(
            self.project_b["project_id"], dataframe
        )

        self.assertEqual(context_a["items"][0]["kpi_id"], "sales-a")
        self.assertEqual(context_b["items"][0]["kpi_id"], "sales-b")
        self.assertEqual(context_a["items"][0]["business_definition"], "项目 A 口径")
        self.assertEqual(context_b["items"][0]["business_definition"], "项目 B 口径")
        self.assertEqual(before, {path: path.read_bytes() for path in watched_paths})
        pd.testing.assert_frame_equal(dataframe, original)

    def test_missing_current_field_excludes_kpi_instead_of_fallback(self):
        self._save_project(self.project_a["project_id"], "sales-a", "项目 A 口径")

        context = service.build_report_dashboard_kpi_context(
            self.project_a["project_id"],
            pd.DataFrame({"其他字段": [1, 2]}),
        )

        self.assertEqual(context["items"], [])
        self.assertEqual(context["usable_kpi_count"], 0)


if __name__ == "__main__":
    unittest.main()
