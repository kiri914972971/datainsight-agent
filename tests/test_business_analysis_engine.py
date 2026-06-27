import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import project_workspace
from src.engines.business_analysis_engine import generate_business_analysis


class BusinessAnalysisEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "projects"
        self.root_patch = patch.object(
            project_workspace,
            "PROJECT_ROOT",
            self.project_root,
        )
        self.root_patch.start()
        self.project = project_workspace.create_project("Business Analysis Engine Project")
        self.project_id = self.project["project_id"]
        analysis_path = self.project_root / self.project_id / "analysis"
        analysis_path.mkdir(parents=True, exist_ok=True)
        self.analysis_result = {
            "success": True,
            "rows": [
                {"产品": "B", "销售额": 700},
                {"产品": "A", "销售额": 200},
                {"产品": "C", "销售额": 100},
            ],
            "summary": {
                "metric": "销售额",
                "metric_field": "成交金额",
                "dimension": "产品",
                "dimension_field": "产品",
                "aggregation": "sum",
            },
            "warnings": [],
        }
        self.eda_report = {
            "warnings": [
                {
                    "type": "high_missing_rate",
                    "severity": "medium",
                    "message": "成交日期缺失率为 35%，存在数据质量风险。",
                },
                {
                    "type": "high_outlier_ratio",
                    "severity": "medium",
                    "message": "销售额异常值比例超过 5%。",
                },
                {
                    "type": "strong_correlation",
                    "severity": "low",
                    "message": "折扣率与销售额存在强相关。",
                },
            ]
        }
        (analysis_path / "eda_report.json").write_text(
            json.dumps(self.eda_report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def test_top1_business_finding(self):
        result = generate_business_analysis(self.project_id, self.analysis_result)
        self.assertIn("产品B是当前销售额贡献最大的产品。", result["findings"])
        self.assertIn("产品B", result["summary"])

    def test_concentration_risk_and_recommendation(self):
        result = generate_business_analysis(self.project_id, self.analysis_result)
        self.assertIn("业务集中度较高。", result["risks"])
        self.assertTrue(
            any("扩大产品结构" in item for item in result["recommendations"])
        )

    def test_growth_positive_and_negative(self):
        positive = {
            **self.analysis_result,
            "summary": {**self.analysis_result["summary"], "growth_rate": 25},
        }
        positive_result = generate_business_analysis(self.project_id, positive)
        self.assertIn("业务增长明显。", positive_result["findings"])
        self.assertIn("当前结果较对比期变化 +25.00%。", positive_result["comparisons"])

        negative = {
            **self.analysis_result,
            "summary": {**self.analysis_result["summary"], "growth_rate": -25},
        }
        negative_result = generate_business_analysis(self.project_id, negative)
        self.assertIn("业务出现明显下滑。", negative_result["risks"])

    def test_eda_warning_risks_and_recommendations(self):
        result = generate_business_analysis(self.project_id, self.analysis_result)
        self.assertTrue(any("高缺失率风险" in item for item in result["risks"]))
        self.assertTrue(any("高异常率风险" in item for item in result["risks"]))
        self.assertTrue(any("强相关字段提示" in item for item in result["risks"]))
        self.assertTrue(any("完善数据采集" in item for item in result["recommendations"]))
        self.assertTrue(any("核查异常记录" in item for item in result["recommendations"]))

    def test_accepts_analysis_result_payload_and_saves(self):
        payload = {
            "question": "销售额最高的产品是什么？",
            "analysis_result": self.analysis_result,
            "created_at": "2026-06-19T00:00:00Z",
        }
        result = generate_business_analysis(self.project_id, payload)
        output_path = (
            self.project_root
            / self.project_id
            / "analysis"
            / "business_analysis.json"
        )
        self.assertTrue(output_path.is_file())
        saved = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["summary"], result["summary"])
        project = project_workspace.get_project(self.project_id)
        self.assertIn("latest_business_analysis", project)


if __name__ == "__main__":
    unittest.main()
