import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import project_workspace
from src.engines.dashboard_engine import generate_dashboard


class DashboardEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "projects"
        self.root_patch = patch.object(
            project_workspace,
            "PROJECT_ROOT",
            self.project_root,
        )
        self.root_patch.start()
        self.project = project_workspace.create_project("Dashboard Engine Project")
        self.project_id = self.project["project_id"]
        analysis_path = self.project_root / self.project_id / "analysis"
        analysis_path.mkdir(parents=True, exist_ok=True)
        self.eda_report = {
            "overview": {
                "row_count": 100,
                "column_count": 12,
                "kpi_count": 4,
                "time_span": {"start": "2026-06-01", "end": "2026-06-30"},
            },
            "trend_analysis": [
                {
                    "title": "销售额趋势",
                    "x": ["2026-06-01", "2026-06-02"],
                    "y": [1000, 1200],
                }
            ],
            "dimension_analysis": [
                {
                    "title": "Top5产品",
                    "labels": ["A", "B", "C"],
                    "values": [500, 300, 100],
                },
                {
                    "title": "Top5区域",
                    "labels": ["华东", "华南"],
                    "values": [700, 200],
                },
            ],
            "warnings": [
                {
                    "type": "high_missing_rate",
                    "severity": "high",
                    "message": "成交日期缺失率较高。",
                },
                {
                    "type": "strong_correlation",
                    "severity": "low",
                    "message": "折扣率与销售额存在强相关。",
                },
            ],
        }
        (analysis_path / "eda_report.json").write_text(
            json.dumps(self.eda_report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def test_kpi_overview_cards(self):
        dashboard = generate_dashboard(self.project_id)
        cards = {item["title"]: item["value"] for item in dashboard["overview_cards"]}
        self.assertEqual(cards["行数"], 100)
        self.assertEqual(cards["字段数"], 12)
        self.assertEqual(cards["KPI数"], 4)
        self.assertEqual(cards["时间跨度"], "2026-06-01 ~ 2026-06-30")

    def test_trend_charts(self):
        dashboard = generate_dashboard(self.project_id)
        self.assertEqual(len(dashboard["trend_charts"]), 1)
        chart = dashboard["trend_charts"][0]
        self.assertEqual(chart["title"], "销售额趋势")
        self.assertEqual(chart["x"], ["2026-06-01", "2026-06-02"])
        self.assertEqual(chart["y"], [1000, 1200])

    def test_topn_charts(self):
        dashboard = generate_dashboard(self.project_id)
        titles = [item["title"] for item in dashboard["topn_charts"]]
        self.assertIn("Top5产品", titles)
        self.assertIn("Top5区域", titles)
        product_chart = next(item for item in dashboard["topn_charts"] if item["title"] == "Top5产品")
        self.assertEqual(product_chart["labels"][0], "A")
        self.assertEqual(product_chart["values"][0], 500)

    def test_risk_cards(self):
        dashboard = generate_dashboard(self.project_id)
        risk_levels = [item["risk_level"] for item in dashboard["risk_cards"]]
        self.assertIn("high", risk_levels)
        self.assertIn("low", risk_levels)
        messages = [item["message"] for item in dashboard["risk_cards"]]
        self.assertIn("成交日期缺失率较高。", messages)

    def test_dashboard_saved(self):
        dashboard = generate_dashboard(self.project_id)
        dashboard_path = (
            self.project_root
            / self.project_id
            / "analysis"
            / "dashboard.json"
        )
        self.assertTrue(dashboard_path.is_file())
        saved = json.loads(dashboard_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["overview_cards"], dashboard["overview_cards"])
        project = project_workspace.get_project(self.project_id)
        self.assertIn("latest_dashboard", project)


if __name__ == "__main__":
    unittest.main()
