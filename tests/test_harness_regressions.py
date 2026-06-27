import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src import project_workspace
from src.services.analysis_dataset_service import build_analysis_dataset
from src.services.append_service import build_appended_dataset, list_append_sources
from src.services.current_dataset_service import (
    list_project_datasets,
    load_current_analysis_dataframe,
    set_current_analysis_dataset,
)
from src.services.data_quality_service import (
    create_cleaned_dataset,
    summarize_duplicates_for_quality,
    summarize_iqr_outliers_for_quality,
    summarize_missing_values_for_quality,
)
from src.services.data_source_service import (
    list_project_data_files,
    save_project_data_files,
    set_current_analysis_file,
)
from src.services.relationship_service import save_table_relationships


class UploadedFileStub(BytesIO):
    def __init__(self, name: str, content: bytes):
        super().__init__(content)
        self.name = name
        self.size = len(content)

    def getvalue(self) -> bytes:
        return super().getvalue()


class HarnessRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "projects"
        self.root_patch = patch.object(project_workspace, "PROJECT_ROOT", self.project_root)
        self.root_patch.start()
        self.project = project_workspace.create_project("Harness")

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def _seed_project_datasets(self):
        orders, products = save_project_data_files(
            self.project["project_id"],
            [
                UploadedFileStub(
                    "orders.csv",
                    b"order_id,product_id,amount,region\n"
                    b"1,p1,10,East\n"
                    b"2,p2,,West\n"
                    b"2,p2,,West\n"
                    b"3,p3,1000,North\n",
                ),
                UploadedFileStub(
                    "products.csv",
                    b"product_id,product_name\np1,A\np2,B\np3,C\n",
                ),
            ],
        )
        set_current_analysis_file(self.project["project_id"], orders["file_id"], "CSV")

        source_ids = [source["source_id"] for source in list_append_sources(self.project["project_id"])]
        build_appended_dataset(self.project["project_id"], source_ids)

        create_cleaned_dataset(
            self.project["project_id"],
            [{"type": "fill_missing", "column": "amount", "method": "zero"}],
        )

        save_table_relationships(
            self.project["project_id"],
            [
                {
                    "table_a_id": f"{orders['file_id']}::CSV",
                    "table_a_name": "orders",
                    "table_a_file_id": orders["file_id"],
                    "table_a_file_name": orders["file_name"],
                    "table_a_sheet_name": "CSV",
                    "field_a": "product_id",
                    "table_b_id": f"{products['file_id']}::CSV",
                    "table_b_name": "products",
                    "table_b_file_id": products["file_id"],
                    "table_b_file_name": products["file_name"],
                    "table_b_sheet_name": "CSV",
                    "field_b": "product_id",
                    "relationship_type": "many_to_one",
                    "confidence": 95,
                }
            ],
        )
        build_analysis_dataset(self.project["project_id"])

    def test_project_dataset_registry_selects_all_dataset_types(self):
        self._seed_project_datasets()

        datasets = list_project_datasets(self.project["project_id"])
        by_type = {dataset["dataset_type"]: dataset for dataset in datasets}

        for dataset_type in ("uploaded", "appended", "cleaned", "joined"):
            with self.subTest(dataset_type=dataset_type):
                self.assertIn(dataset_type, by_type)
                selected = set_current_analysis_dataset(
                    self.project["project_id"],
                    by_type[dataset_type],
                )
                dataframe = load_current_analysis_dataframe(self.project["project_id"])
                self.assertEqual(selected["dataset_type"], dataset_type)
                self.assertFalse(dataframe.empty)

    def test_data_source_metadata_keeps_preview_and_selection_fields(self):
        saved = save_project_data_files(
            self.project["project_id"],
            [UploadedFileStub("orders.csv", b"order_id,amount\n1,100\n2,200\n")],
        )

        file_metadata = list_project_data_files(self.project["project_id"])[0]
        project_dataset = list_project_datasets(self.project["project_id"])[0]

        for key in ("file_id", "file_name", "file_path", "file_type", "file_size", "uploaded_at", "sheets"):
            self.assertIn(key, file_metadata)
        self.assertEqual(file_metadata["file_id"], saved[0]["file_id"])
        self.assertEqual(file_metadata["sheets"][0]["sheet_name"], "CSV")
        self.assertEqual(file_metadata["sheets"][0]["rows"], 2)
        self.assertEqual(file_metadata["sheets"][0]["columns"], 2)

        for key in (
            "dataset_id",
            "dataset_name",
            "dataset_type",
            "file_path",
            "sheet_name",
            "row_count",
            "column_count",
            "source",
            "source_file_id",
        ):
            self.assertIn(key, project_dataset)
        self.assertEqual(project_dataset["dataset_type"], "uploaded")
        self.assertEqual(project_dataset["row_count"], 2)
        self.assertEqual(project_dataset["column_count"], 2)

    def test_data_quality_summaries_keep_missing_duplicate_and_iqr_outputs(self):
        dataframe = pd.DataFrame(
            {
                "id": [1, 2, 2, 3],
                "amount": [10, None, None, 1000],
                "region": ["East", "West", "West", "North"],
            }
        )

        missing = summarize_missing_values_for_quality(dataframe)
        duplicates = summarize_duplicates_for_quality(dataframe)
        outliers = summarize_iqr_outliers_for_quality(dataframe)

        self.assertGreaterEqual(int(missing.iloc[:, 2].sum()), 2)
        self.assertIn("duplicate_count", duplicates)
        self.assertIn("duplicate_ratio", duplicates)
        self.assertIn("preview", duplicates)
        self.assertIn("Q1", outliers.columns)
        self.assertIn("Q3", outliers.columns)
        self.assertIn("IQR", outliers.columns)
        self.assertTrue(any(outliers.iloc[:, 0] == "amount"))

    def test_app_contains_required_workspace_and_preview_labels(self):
        app_text = Path("app.py").read_text(encoding="utf-8")
        required_labels = [
            "项目数据",
            "数据建模",
            "指标配置",
            "分析工作台",
            "交付导出",
            "数据源",
            "数据合并",
            "数据质量",
            "前20行",
            "后20行",
            "随机20行",
            "字段信息",
            "业务问题",
            "探索性分析",
            "Dashboard",
            "业务分析",
            "报告导出",
        ]

        for label in required_labels:
            with self.subTest(label=label):
                self.assertIn(label, app_text)


if __name__ == "__main__":
    unittest.main()
