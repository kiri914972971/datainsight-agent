import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src import project_workspace
from src.engines.eda_engine import generate_eda_report
from src.services.field_mapping_service import save_field_mappings


class EdaEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "projects"
        self.root_patch = patch.object(
            project_workspace,
            "PROJECT_ROOT",
            self.project_root,
        )
        self.root_patch.start()
        self.project = project_workspace.create_project("EDA Engine Project")
        self.project_id = self.project["project_id"]
        analysis_path = self.project_root / self.project_id / "analysis"
        analysis_path.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            {
                "order_date": pd.date_range("2026-06-01", periods=8, freq="D"),
                "sales_amount": [100, 200, 300, 400, 500, 600, 5000, None],
                "discount": [1, 2, 3, 4, 5, 6, 50, None],
                "region": ["华东", "华东", "华东", "华东", "华东", "华南", "华北", "华东"],
                "product": ["A", "A", "B", "B", "C", "C", "D", "D"],
                "comment": [None, None, None, None, "ok", None, None, None],
            }
        ).to_csv(analysis_path / "analysis_dataset.csv", index=False, encoding="utf-8-sig")
        save_field_mappings(
            self.project_id,
            [
                {"column_name": "order_date", "confirmed_type": "日期字段"},
                {"column_name": "sales_amount", "confirmed_type": "金额字段"},
                {"column_name": "region", "confirmed_type": "区域字段"},
                {"column_name": "product", "confirmed_type": "产品字段"},
            ],
        )

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def test_overview_counts(self):
        report = generate_eda_report(self.project_id)
        self.assertEqual(report["overview"]["row_count"], 8)
        self.assertEqual(report["overview"]["column_count"], 6)
        self.assertEqual(report["overview"]["numeric_column_count"], 2)
        self.assertEqual(report["overview"]["categorical_column_count"], 3)
        self.assertEqual(report["overview"]["date_column_count"], 1)

    def test_numeric_analysis(self):
        report = generate_eda_report(self.project_id)
        numeric = {item["column"]: item for item in report["numeric_analysis"]}
        self.assertIn("sales_amount", numeric)
        self.assertAlmostEqual(numeric["sales_amount"]["mean"], 1014.285714, places=5)
        self.assertEqual(numeric["sales_amount"]["median"], 400)
        self.assertEqual(numeric["sales_amount"]["min"], 100)
        self.assertEqual(numeric["sales_amount"]["max"], 5000)
        self.assertEqual(numeric["sales_amount"]["missing_rate"], 0.125)

    def test_categorical_analysis(self):
        report = generate_eda_report(self.project_id)
        categorical = {item["column"]: item for item in report["categorical_analysis"]}
        self.assertEqual(categorical["region"]["unique_count"], 3)
        self.assertEqual(categorical["region"]["top5_values"][0]["value"], "华东")
        self.assertEqual(categorical["region"]["top5_values"][0]["count"], 6)
        self.assertEqual(categorical["region"]["top5_values"][0]["ratio"], 0.75)
        self.assertEqual(categorical["region"]["top5_ratio"], 1.0)

    def test_correlation_analysis(self):
        report = generate_eda_report(self.project_id)
        pairs = {
            (item["column_a"], item["column_b"]): item["correlation"]
            for item in report["correlation_analysis"]
        }
        self.assertIn(("sales_amount", "discount"), pairs)
        self.assertGreater(pairs[("sales_amount", "discount")], 0.8)

    def test_outlier_analysis(self):
        report = generate_eda_report(self.project_id)
        outliers = {item["column"]: item for item in report["outlier_analysis"]}
        self.assertGreaterEqual(outliers["sales_amount"]["outlier_count"], 1)
        self.assertGreater(outliers["sales_amount"]["outlier_ratio"], 0.05)
        self.assertIn("q1", outliers["sales_amount"])
        self.assertIn("q3", outliers["sales_amount"])
        self.assertIn("iqr", outliers["sales_amount"])

    def test_insights_and_warnings_generation(self):
        report = generate_eda_report(self.project_id)
        insight_types = {item["type"] for item in report["insights"]}
        warning_types = {item["type"] for item in report["warnings"]}
        self.assertIn("high_concentration", insight_types)
        self.assertIn("strong_correlation", insight_types)
        self.assertIn("high_outlier_ratio", insight_types)
        self.assertIn("high_missing_rate", warning_types)
        self.assertIn("high_concentration", warning_types)
        self.assertIn("high_outlier_ratio", warning_types)
        self.assertIn("strong_correlation", warning_types)

    def test_report_save_and_project_memory(self):
        report = generate_eda_report(self.project_id)
        report_path = (
            self.project_root
            / self.project_id
            / "analysis"
            / "eda_report.json"
        )
        self.assertTrue(report_path.is_file())
        saved = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["overview"], report["overview"])
        project = project_workspace.get_project(self.project_id)
        self.assertIn("latest_eda_report", project)


if __name__ == "__main__":
    unittest.main()
