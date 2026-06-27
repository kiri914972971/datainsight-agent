import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src import project_workspace
from src.engines.field_mapping_engine import infer_field_mappings
from src.services.field_mapping_service import (
    get_missing_historical_fields,
    get_new_fields,
    load_field_mappings,
    mapping_business_summary,
    merge_existing_mappings,
    prioritize_business_fields,
    prioritize_dashboard_fields,
    save_field_mappings,
)


class FieldMappingEngineTests(unittest.TestCase):
    def setUp(self):
        self.dataframe = pd.DataFrame(
            {
                "成交日期": ["2026-06-01", "2026-06-02"],
                "成交金额": [100.0, 200.0],
                "订单号": ["A-1", "A-2"],
                "产品": ["借呗", "花呗"],
                "区域": ["华东", "华南"],
                "销售人员": ["张三", "李四"],
                "销售工号": [1001, 1002],
            }
        )

    def test_rule_based_field_types(self):
        mapping = {
            item["column_name"]: item
            for item in infer_field_mappings(self.dataframe)
        }
        self.assertEqual(mapping["成交日期"]["inferred_type"], "日期字段")
        self.assertEqual(mapping["成交金额"]["inferred_type"], "金额字段")
        self.assertEqual(mapping["订单号"]["inferred_type"], "ID字段")
        self.assertEqual(mapping["产品"]["inferred_type"], "产品字段")
        self.assertEqual(mapping["区域"]["inferred_type"], "区域字段")
        self.assertEqual(mapping["销售人员"]["inferred_type"], "人员字段")
        self.assertEqual(mapping["销售工号"]["inferred_type"], "ID字段")

    def test_existing_mapping_new_and_missing_fields(self):
        existing = [
            {
                "column_name": "成交金额",
                "pandas_dtype": "float64",
                "inferred_type": "金额字段",
                "confidence": 0.95,
                "reason": "历史规则",
                "confirmed_type": "数量字段",
            },
            {
                "column_name": "历史字段",
                "pandas_dtype": "object",
                "inferred_type": "类别字段",
                "confidence": 0.75,
                "reason": "历史规则",
                "confirmed_type": "类别字段",
            },
        ]
        merged = {
            item["column_name"]: item
            for item in merge_existing_mappings(self.dataframe, existing)
        }
        self.assertEqual(merged["成交金额"]["confirmed_type"], "数量字段")
        self.assertEqual(merged["产品"]["confirmed_type"], "产品字段")
        self.assertIn("产品", get_new_fields(self.dataframe, existing))
        self.assertEqual(
            get_missing_historical_fields(self.dataframe, existing),
            ["历史字段"],
        )


class FieldMappingServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "projects"
        self.root_patch = patch.object(
            project_workspace,
            "PROJECT_ROOT",
            self.project_root,
        )
        self.root_patch.start()
        self.project = project_workspace.create_project("Field Mapping")

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def test_save_and_load_field_mappings(self):
        mappings = infer_field_mappings(
            pd.DataFrame({"成交金额": [100, 200], "区域": ["华东", "华南"]})
        )
        saved = save_field_mappings(self.project["project_id"], mappings)
        loaded = load_field_mappings(self.project["project_id"])
        project = project_workspace.get_project(self.project["project_id"])

        self.assertEqual(saved, loaded)
        self.assertEqual(project["field_mappings"], loaded)
        self.assertTrue(
            (
                self.project_root
                / self.project["project_id"]
                / "config"
                / "field_mappings.json"
            ).is_file()
        )

    def test_confirmed_mappings_prioritize_downstream_business_fields(self):
        dataframe = pd.DataFrame(
            {
                "when_x": ["2026-05-01", "2026-06-01"],
                "metric_x": [100.0, 150.0],
                "count_x": [1, 2],
                "dim_region": ["East", "West"],
                "dim_product": ["A", "B"],
                "dim_person": ["Alice", "Bob"],
                "record_x": [1001, 1002],
            }
        )
        mappings = [
            {"column_name": "when_x", "confirmed_type": "日期字段"},
            {"column_name": "metric_x", "confirmed_type": "金额字段"},
            {"column_name": "count_x", "confirmed_type": "数量字段"},
            {"column_name": "dim_region", "confirmed_type": "区域字段"},
            {"column_name": "dim_product", "confirmed_type": "产品字段"},
            {"column_name": "dim_person", "confirmed_type": "人员字段"},
            {"column_name": "record_x", "confirmed_type": "ID字段"},
        ]
        existing = {
            "date_column": None,
            "amount_column": None,
            "dimensions": [],
            "numeric_metrics": ["metric_x", "count_x", "record_x"],
        }

        fields = prioritize_business_fields(dataframe, mappings, existing)

        self.assertEqual(fields["date_column"], "when_x")
        self.assertEqual(fields["amount_column"], "metric_x")
        self.assertEqual(
            fields["dimensions"][:3],
            ["dim_region", "dim_product", "dim_person"],
        )
        self.assertEqual(fields["numeric_metrics"][:2], ["metric_x", "count_x"])
        self.assertNotIn("record_x", fields["numeric_metrics"])

    def test_confirmed_mappings_prioritize_dashboard_and_report_summary(self):
        dataframe = pd.DataFrame(
            {
                "when_x": ["2026-05-01"],
                "metric_x": [100.0],
                "dim_region": ["East"],
                "dim_product": ["A"],
                "dim_person": ["Alice"],
            }
        )
        mappings = [
            {"column_name": "when_x", "confirmed_type": "日期字段"},
            {"column_name": "metric_x", "confirmed_type": "金额字段"},
            {"column_name": "dim_region", "confirmed_type": "区域字段"},
            {"column_name": "dim_product", "confirmed_type": "产品字段"},
            {"column_name": "dim_person", "confirmed_type": "人员字段"},
        ]

        dashboard_fields = prioritize_dashboard_fields(
            dataframe,
            mappings,
            {
                "date_column": None,
                "amount_column": None,
                "product_column": None,
                "region_column": None,
            },
        )
        summary = mapping_business_summary(dataframe, mappings)

        self.assertEqual(dashboard_fields["date_column"], "when_x")
        self.assertEqual(dashboard_fields["amount_column"], "metric_x")
        self.assertEqual(dashboard_fields["product_column"], "dim_product")
        self.assertEqual(dashboard_fields["region_column"], "dim_region")
        self.assertEqual(summary["人员字段"], ["dim_person"])


if __name__ == "__main__":
    unittest.main()
