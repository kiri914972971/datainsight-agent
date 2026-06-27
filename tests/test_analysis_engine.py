import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src import project_workspace
from src.engines.analysis_engine import execute_analysis
from src.services.field_mapping_service import save_field_mappings
from src.services.kpi_service import save_kpi_definitions
from src.services.metric_dictionary_service import save_metric_dictionary


class AnalysisEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "projects"
        self.root_patch = patch.object(
            project_workspace,
            "PROJECT_ROOT",
            self.project_root,
        )
        self.root_patch.start()
        self.project = project_workspace.create_project("Analysis Engine Project")
        self.project_id = self.project["project_id"]
        self.today = pd.Timestamp.now().normalize()
        analysis_path = self.project_root / self.project_id / "analysis"
        analysis_path.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            {
                "产品": ["A", "B", "A", "C"],
                "区域": ["华东", "华东", "华南", "华东"],
                "成交日期": [
                    self.today - pd.Timedelta(days=1),
                    self.today - pd.Timedelta(days=2),
                    self.today - pd.Timedelta(days=40),
                    self.today - pd.Timedelta(days=5),
                ],
                "成交金额": [100, 200, 300, 50],
                "订单ID": [1, 2, 3, 4],
                "客单价": [100, 200, 300, 50],
            }
        ).to_csv(analysis_path / "analysis_dataset.csv", index=False, encoding="utf-8-sig")
        save_field_mappings(
            self.project_id,
            [
                {"column_name": "成交日期", "confirmed_type": "日期字段"},
                {"column_name": "成交金额", "confirmed_type": "金额字段"},
                {"column_name": "订单ID", "confirmed_type": "ID字段"},
                {"column_name": "产品", "confirmed_type": "产品字段"},
                {"column_name": "区域", "confirmed_type": "区域字段"},
                {"column_name": "客单价", "confirmed_type": "金额字段"},
            ],
        )
        save_kpi_definitions(
            self.project_id,
            [
                {
                    "kpi_name": "销售额",
                    "aggregation": "sum",
                    "source_field": "成交金额",
                    "field_type": "amount",
                    "category": "核心指标",
                    "enabled": True,
                },
                {
                    "kpi_name": "订单数",
                    "aggregation": "count",
                    "source_field": "订单ID",
                    "field_type": "id",
                    "category": "核心指标",
                    "enabled": True,
                },
                {
                    "kpi_name": "客单价",
                    "aggregation": "avg",
                    "source_field": "客单价",
                    "field_type": "amount",
                    "category": "核心指标",
                    "enabled": True,
                },
            ],
        )
        save_metric_dictionary(
            self.project_id,
            [
                {"metric_name": "销售额", "aliases": ["GMV", "成交金额"], "linked_kpi_name": "销售额"},
                {"metric_name": "订单数", "aliases": ["订单量"], "linked_kpi_name": "订单数"},
                {"metric_name": "客单价", "aliases": ["AOV"], "linked_kpi_name": "客单价"},
            ],
        )

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def test_sum_without_dimension(self):
        result = execute_analysis(
            self.project_id,
            {"metric": "销售额", "aggregation": "sum", "original_question": "销售额是多少？"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["rows"][0]["销售额"], 650)

    def test_count_groupby(self):
        result = execute_analysis(
            self.project_id,
            {"metric": "订单数", "dimension": "区域", "aggregation": "count"},
        )
        rows = {item["区域"]: item["订单数"] for item in result["rows"]}
        self.assertEqual(rows["华东"], 3)
        self.assertEqual(rows["华南"], 1)

    def test_avg_without_dimension(self):
        result = execute_analysis(
            self.project_id,
            {"metric": "客单价", "aggregation": "avg"},
        )
        self.assertEqual(result["rows"][0]["客单价"], 162.5)

    def test_groupby_sort_and_top_n(self):
        result = execute_analysis(
            self.project_id,
            {
                "metric": "销售额",
                "dimension": "产品",
                "aggregation": "sum",
                "sort": "desc",
                "top_n": 2,
            },
        )
        self.assertEqual(len(result["rows"]), 2)
        self.assertEqual(result["rows"][0]["产品"], "A")
        self.assertEqual(result["rows"][0]["销售额"], 400)

    def test_filters(self):
        result = execute_analysis(
            self.project_id,
            {
                "metric": "销售额",
                "dimension": "产品",
                "aggregation": "sum",
                "filters": [{"field": "区域", "operator": "==", "value": "华东"}],
                "sort": "desc",
            },
        )
        rows = {item["产品"]: item["销售额"] for item in result["rows"]}
        self.assertEqual(rows, {"B": 200, "A": 100, "C": 50})

    def test_recent_30_days(self):
        result = execute_analysis(
            self.project_id,
            {
                "metric": "销售额",
                "dimension": "产品",
                "aggregation": "sum",
                "time_range": "最近30天",
                "sort": "desc",
                "top_n": 1,
            },
        )
        self.assertEqual(result["summary"]["filtered_rows"], 3)
        self.assertEqual(result["rows"][0]["产品"], "B")
        self.assertEqual(result["rows"][0]["销售额"], 200)

    def test_empty_result(self):
        result = execute_analysis(
            self.project_id,
            {
                "metric": "销售额",
                "aggregation": "sum",
                "filters": [{"field": "区域", "operator": "==", "value": "不存在"}],
            },
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["rows"], [])
        self.assertIn("过滤后没有可分析的数据。", result["warnings"])

    def test_missing_metric_field(self):
        result = execute_analysis(
            self.project_id,
            {"metric": "利润", "aggregation": "sum"},
        )
        self.assertFalse(result["success"])
        self.assertIn("未能定位指标字段：利润", result["warnings"])

    def test_result_saved(self):
        execute_analysis(
            self.project_id,
            {"metric": "销售额", "aggregation": "sum", "original_question": "销售额是多少？"},
        )
        self.assertTrue(
            (
                self.project_root
                / self.project_id
                / "analysis"
                / "analysis_result.json"
            ).is_file()
        )
        project = project_workspace.get_project(self.project_id)
        self.assertIn("latest_analysis_result", project)


if __name__ == "__main__":
    unittest.main()
