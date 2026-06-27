import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src import project_workspace
from src.engines.business_question_engine import parse_business_question
from src.services.business_question_service import (
    load_question_parse_history,
    parse_question_for_project,
)
from src.services.field_mapping_service import save_field_mappings
from src.services.kpi_service import save_kpi_definitions
from src.services.metric_dictionary_service import save_metric_dictionary


class BusinessQuestionEngineTests(unittest.TestCase):
    def setUp(self):
        self.context = {
            "metric_dictionary": [
                {
                    "metric_name": "销售额",
                    "aliases": ["GMV", "Revenue", "成交金额"],
                    "linked_kpi_name": "销售额",
                    "enabled": True,
                },
                {
                    "metric_name": "订单数",
                    "aliases": ["订单量", "Orders"],
                    "linked_kpi_name": "订单数",
                    "enabled": True,
                },
            ],
            "kpis": [
                {"kpi_name": "销售额", "aggregation": "sum", "source_field": "成交金额"},
                {"kpi_name": "订单数", "aggregation": "count", "source_field": "订单ID"},
            ],
            "field_mappings": [
                {"column_name": "区域", "confirmed_type": "区域字段"},
                {"column_name": "产品", "confirmed_type": "产品字段"},
                {"column_name": "销售员", "confirmed_type": "人员字段"},
                {"column_name": "成交日期", "confirmed_type": "日期字段"},
            ],
            "dataset_columns": ["区域", "产品", "销售员", "成交日期", "成交金额", "订单ID"],
            "dataset_preview": pd.DataFrame(
                {
                    "区域": ["华东", "华南"],
                    "产品": ["借呗6期", "借呗12期"],
                    "销售员": ["Kiri", "Ada"],
                    "成交金额": [100, 200],
                    "订单ID": [1, 2],
                }
            ),
        }

    def test_gmv_matches_sales_metric(self):
        result = parse_business_question("GMV 本月是多少？", self.context)
        self.assertEqual(result["metric"], "销售额")
        self.assertEqual(result["metric_alias_matched"], "GMV")

    def test_revenue_matches_sales_metric(self):
        result = parse_business_question("Revenue 最近趋势如何？", self.context)
        self.assertEqual(result["metric"], "销售额")
        self.assertEqual(result["metric_alias_matched"], "Revenue")
        self.assertEqual(result["intent_type"], "trend")

    def test_ranking_metric_dimension_and_topn(self):
        result = parse_business_question("销售额最高的5个区域是什么？", self.context)
        self.assertEqual(result["intent_type"], "ranking")
        self.assertEqual(result["metric"], "销售额")
        self.assertEqual(result["dimension"], "区域")
        self.assertEqual(result["top_n"], 5)
        self.assertEqual(result["sort"], "desc")
        self.assertEqual(result["aggregation"], "sum")

    def test_filter_metric_and_comparison(self):
        result = parse_business_question("华东区订单数环比增长多少？", self.context)
        self.assertEqual(result["intent_type"], "comparison")
        self.assertEqual(result["metric"], "订单数")
        self.assertEqual(result["comparison"], "环比")
        self.assertEqual(result["dimension"], "区域")
        self.assertEqual(result["filters"], [{"field": "区域", "operator": "==", "value": "华东"}])

    def test_time_range_and_product_dimension(self):
        result = parse_business_question("最近30天哪个产品销售额最高？", self.context)
        self.assertEqual(result["time_range"], "最近30天")
        self.assertEqual(result["dimension"], "产品")
        self.assertEqual(result["metric"], "销售额")
        self.assertEqual(result["top_n"], 1)

    def test_missing_metric_warning(self):
        result = parse_business_question("哪个区域最高？", self.context)
        self.assertIn("未识别到明确业务指标。", result["warnings"])

    def test_missing_dimension_warning(self):
        result = parse_business_question("销售额最高的是多少？", self.context)
        self.assertIn("未识别到明确分析维度。", result["warnings"])


class BusinessQuestionServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "projects"
        self.root_patch = patch.object(
            project_workspace,
            "PROJECT_ROOT",
            self.project_root,
        )
        self.root_patch.start()
        self.project = project_workspace.create_project("Business Question Project")
        project_id = self.project["project_id"]
        save_kpi_definitions(
            project_id,
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
            ],
        )
        save_metric_dictionary(
            project_id,
            [
                {
                    "metric_name": "销售额",
                    "aliases": ["GMV", "Revenue", "成交金额"],
                    "metric_type": "核心指标",
                    "business_definition": "统计订单成交金额总和",
                    "linked_kpi_name": "销售额",
                    "enabled": True,
                },
                {
                    "metric_name": "订单数",
                    "aliases": ["订单量", "Orders"],
                    "metric_type": "核心指标",
                    "business_definition": "统计订单数量",
                    "linked_kpi_name": "订单数",
                    "enabled": True,
                },
            ],
        )
        save_field_mappings(
            project_id,
            [
                {"column_name": "区域", "confirmed_type": "区域字段"},
                {"column_name": "产品", "confirmed_type": "产品字段"},
                {"column_name": "成交日期", "confirmed_type": "日期字段"},
            ],
        )
        analysis_path = self.project_root / project_id / "analysis"
        analysis_path.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            {
                "区域": ["华东", "华南"],
                "产品": ["借呗6期", "借呗12期"],
                "成交金额": [100, 200],
                "订单ID": [1, 2],
            }
        ).to_csv(analysis_path / "analysis_dataset.csv", index=False, encoding="utf-8-sig")

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def test_save_and_reload_question_parse_history(self):
        project_id = self.project["project_id"]
        result = parse_question_for_project(project_id, "华东区订单数环比增长多少？")
        history = load_question_parse_history(project_id)
        project = project_workspace.get_project(project_id)

        self.assertEqual(result["metric"], "订单数")
        self.assertEqual(result["filters"][0]["value"], "华东")
        self.assertEqual(len(history), 1)
        self.assertEqual(project["question_parse_history"], history)
        self.assertTrue(
            (
                self.project_root
                / project_id
                / "config"
                / "question_parse_history.json"
            ).is_file()
        )


if __name__ == "__main__":
    unittest.main()
