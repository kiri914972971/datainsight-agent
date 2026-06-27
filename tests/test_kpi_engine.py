import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import project_workspace
from src.engines.kpi_engine import generate_kpi_candidates
from src.services.field_mapping_service import save_field_mappings
from src.services.kpi_service import (
    add_kpi_definition,
    delete_kpi_definition,
    generate_project_kpi_candidates,
    get_kpi_by_name,
    get_project_kpis,
    list_enabled_kpis,
    load_kpi_definitions,
    save_kpi_definitions,
    update_kpi_definition,
)


class KpiEngineTests(unittest.TestCase):
    def setUp(self):
        self.mappings = [
            {"column_name": "成交金额", "confirmed_type": "金额字段"},
            {"column_name": "订单ID", "confirmed_type": "ID字段"},
            {"column_name": "客户ID", "confirmed_type": "ID字段"},
            {"column_name": "成交日期", "confirmed_type": "日期字段"},
            {"column_name": "区域", "confirmed_type": "区域字段"},
            {"column_name": "产品", "confirmed_type": "产品字段"},
            {"column_name": "销售员", "confirmed_type": "人员字段"},
        ]

    def test_generates_core_time_and_dimension_candidates(self):
        candidates = generate_kpi_candidates(self.mappings)
        by_name = {item["kpi_name"]: item for item in candidates}

        self.assertEqual(by_name["销售额"]["aggregation"], "sum")
        self.assertEqual(by_name["销售额"]["source_field"], "成交金额")
        self.assertEqual(by_name["订单数"]["aggregation"], "count")
        self.assertEqual(by_name["客户数"]["aggregation"], "count")
        self.assertEqual(by_name["同比"]["category"], "时间指标")
        self.assertFalse(by_name["同比"]["enabled"])
        self.assertEqual(by_name["区域销售额"]["category"], "维度指标")
        self.assertEqual(by_name["产品销售额"]["category"], "维度指标")
        self.assertEqual(by_name["销售员销售额"]["category"], "维度指标")


class KpiServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "projects"
        self.root_patch = patch.object(
            project_workspace,
            "PROJECT_ROOT",
            self.project_root,
        )
        self.root_patch.start()
        self.project = project_workspace.create_project("KPI Project")
        save_field_mappings(
            self.project["project_id"],
            [
                {"column_name": "成交金额", "confirmed_type": "金额字段"},
                {"column_name": "订单ID", "confirmed_type": "ID字段"},
                {"column_name": "成交日期", "confirmed_type": "日期字段"},
            ],
        )

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def test_project_candidate_generation_and_save_restore(self):
        candidates = generate_project_kpi_candidates(self.project["project_id"])
        sales = next(item for item in candidates if item["kpi_name"] == "销售额")
        saved = save_kpi_definitions(self.project["project_id"], candidates)
        loaded = load_kpi_definitions(self.project["project_id"])
        project = project_workspace.get_project(self.project["project_id"])

        self.assertEqual(saved, loaded)
        self.assertEqual(project["kpi_definitions"], loaded)
        self.assertEqual(sales["aggregation"], "sum")
        self.assertTrue(
            (
                self.project_root
                / self.project["project_id"]
                / "config"
                / "kpi_definitions.json"
            ).is_file()
        )

    def test_add_edit_delete_enable_disable_and_lookup(self):
        add_kpi_definition(
            self.project["project_id"],
            {
                "kpi_name": "客单价",
                "aggregation": "avg",
                "source_field": "成交金额",
                "field_type": "amount",
                "category": "核心指标",
                "description": "平均成交金额",
                "enabled": True,
            },
        )
        kpi = get_kpi_by_name(self.project["project_id"], "客单价")
        self.assertIsNotNone(kpi)
        self.assertEqual(kpi["aggregation"], "avg")

        update_kpi_definition(
            self.project["project_id"],
            kpi["kpi_id"],
            {"enabled": False, "description": "已禁用测试"},
        )
        self.assertEqual(list_enabled_kpis(self.project["project_id"]), [])
        self.assertEqual(
            get_kpi_by_name(self.project["project_id"], "客单价")["description"],
            "已禁用测试",
        )

        delete_kpi_definition(self.project["project_id"], kpi["kpi_id"])
        self.assertEqual(get_project_kpis(self.project["project_id"]), [])


if __name__ == "__main__":
    unittest.main()
