import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import project_workspace
from src.engines.metric_dictionary_engine import generate_metric_candidates_from_kpis
from src.services.kpi_service import save_kpi_definitions
from src.services.metric_dictionary_service import (
    add_metric_definition,
    delete_metric_definition,
    find_metric_by_alias,
    generate_project_metric_candidates,
    get_metric_by_name,
    get_metric_dictionary,
    list_enabled_metrics,
    load_metric_dictionary,
    save_metric_dictionary,
    update_metric_definition,
)


class MetricDictionaryEngineTests(unittest.TestCase):
    def setUp(self):
        self.kpis = [
            {
                "kpi_id": "kpi_sales",
                "kpi_name": "销售额",
                "aggregation": "sum",
                "source_field": "成交金额",
                "field_type": "amount",
                "category": "核心指标",
                "description": "统计销售总金额",
                "enabled": True,
            },
            {
                "kpi_id": "kpi_orders",
                "kpi_name": "订单数",
                "aggregation": "count",
                "source_field": "订单ID",
                "field_type": "id",
                "category": "核心指标",
                "description": "统计订单数量",
                "enabled": True,
            },
            {
                "kpi_id": "kpi_yoy",
                "kpi_name": "同比",
                "aggregation": "reserved",
                "source_field": "成交日期",
                "field_type": "date",
                "category": "时间指标",
                "description": "预留时间指标",
                "enabled": False,
            },
        ]

    def test_generates_metric_candidates_from_kpis(self):
        candidates = generate_metric_candidates_from_kpis(self.kpis)
        by_name = {item["metric_name"]: item for item in candidates}

        self.assertEqual(by_name["销售额"]["metric_type"], "核心指标")
        self.assertEqual(by_name["销售额"]["linked_kpi_id"], "kpi_sales")
        self.assertIn("GMV", by_name["销售额"]["aliases"])
        self.assertIn("成交金额", by_name["销售额"]["aliases"])
        self.assertEqual(by_name["同比"]["metric_type"], "时间指标")
        self.assertFalse(by_name["同比"]["enabled"])


class MetricDictionaryServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "projects"
        self.root_patch = patch.object(
            project_workspace,
            "PROJECT_ROOT",
            self.project_root,
        )
        self.root_patch.start()
        self.project = project_workspace.create_project("Metric Project")
        save_kpi_definitions(
            self.project["project_id"],
            [
                {
                    "kpi_id": "kpi_sales",
                    "kpi_name": "销售额",
                    "aggregation": "sum",
                    "source_field": "成交金额",
                    "field_type": "amount",
                    "category": "核心指标",
                    "description": "统计销售总金额",
                    "enabled": True,
                },
                {
                    "kpi_id": "kpi_orders",
                    "kpi_name": "订单数",
                    "aggregation": "count",
                    "source_field": "订单ID",
                    "field_type": "id",
                    "category": "核心指标",
                    "description": "统计订单数量",
                    "enabled": True,
                },
            ],
        )

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def test_project_candidate_generation_and_save_restore(self):
        candidates = generate_project_metric_candidates(self.project["project_id"])
        saved = save_metric_dictionary(self.project["project_id"], candidates)
        loaded = load_metric_dictionary(self.project["project_id"])
        project = project_workspace.get_project(self.project["project_id"])

        self.assertEqual(saved, loaded)
        self.assertEqual(project["metric_dictionary"], loaded)
        self.assertIsNotNone(find_metric_by_alias(self.project["project_id"], "GMV"))
        self.assertIsNotNone(find_metric_by_alias(self.project["project_id"], "成交金额"))
        self.assertTrue(
            (
                self.project_root
                / self.project["project_id"]
                / "config"
                / "metric_dictionary.json"
            ).is_file()
        )

    def test_add_edit_delete_alias_lookup_and_kpi_link(self):
        add_metric_definition(
            self.project["project_id"],
            {
                "metric_name": "客单价",
                "metric_type": "核心指标",
                "business_definition": "平均每单成交金额",
                "aliases": "AOV，平均订单金额",
                "linked_kpi_id": "kpi_sales",
                "linked_kpi_name": "销售额",
                "enabled": True,
            },
        )
        metric = get_metric_by_name(self.project["project_id"], "客单价")
        self.assertIsNotNone(metric)
        self.assertEqual(metric["linked_kpi_name"], "销售额")
        self.assertEqual(find_metric_by_alias(self.project["project_id"], "aov")["metric_name"], "客单价")

        update_metric_definition(
            self.project["project_id"],
            metric["metric_id"],
            {"enabled": False, "business_definition": "已禁用测试"},
        )
        self.assertEqual(list_enabled_metrics(self.project["project_id"]), [])
        self.assertEqual(
            get_metric_by_name(self.project["project_id"], "客单价")["business_definition"],
            "已禁用测试",
        )

        delete_metric_definition(self.project["project_id"], metric["metric_id"])
        self.assertEqual(get_metric_dictionary(self.project["project_id"]), [])


if __name__ == "__main__":
    unittest.main()
