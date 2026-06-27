import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src import project_workspace
from src.services import data_source_service


class UploadedFileStub(BytesIO):
    def __init__(self, name: str, content: bytes):
        super().__init__(content)
        self.name = name

    def getvalue(self) -> bytes:
        return super().getvalue()


def excel_bytes() -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame({"order_id": [1, 2], "amount": [100, 200]}).to_excel(
            writer,
            sheet_name="Orders",
            index=False,
        )
        pd.DataFrame({"customer_id": [10], "region": ["East"]}).to_excel(
            writer,
            sheet_name="Customers",
            index=False,
        )
    return buffer.getvalue()


class DataSourceServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "projects"
        self.root_patch = patch.object(
            project_workspace,
            "PROJECT_ROOT",
            self.project_root,
        )
        self.root_patch.start()
        self.project = project_workspace.create_project("Data Sources")

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def test_data_source_lifecycle_and_project_metadata(self):
        saved = data_source_service.save_project_data_files(
            self.project["project_id"],
            [
                UploadedFileStub(
                    "orders.csv",
                    b"order_id,amount\n1,100\n2,200\n",
                ),
                UploadedFileStub("model.xlsx", excel_bytes()),
            ],
        )
        self.assertEqual(len(saved), 2)

        files = data_source_service.list_project_data_files(
            self.project["project_id"]
        )
        self.assertEqual(len(files), 2)
        project_after_upload = project_workspace.get_project(self.project["project_id"])
        self.assertEqual(project_after_upload["project_name"], "Data Sources")
        self.assertEqual(len(project_after_upload["data_files"]), 2)
        self.assertEqual(len(project_after_upload["project_datasets"]), 3)
        dataset_names = {
            dataset["dataset_name"]
            for dataset in project_after_upload["project_datasets"]
        }
        self.assertIn("orders.csv", dataset_names)
        self.assertIn("model.xlsx / Orders", dataset_names)
        self.assertIn("model.xlsx / Customers", dataset_names)
        excel_file = next(item for item in files if item["file_type"] == "xlsx")
        self.assertEqual(
            [sheet["sheet_name"] for sheet in excel_file["sheets"]],
            ["Orders", "Customers"],
        )

        dataframe = data_source_service.load_project_data_file(
            self.project["project_id"],
            excel_file["file_id"],
            "Customers",
        )
        self.assertEqual(dataframe.columns.tolist(), ["customer_id", "region"])

        selection = data_source_service.set_current_analysis_file(
            self.project["project_id"],
            excel_file["file_id"],
            "Orders",
        )
        self.assertEqual(selection["sheet_name"], "Orders")
        project = project_workspace.get_project(self.project["project_id"])
        self.assertEqual(project["current_analysis_file"], selection)

        result = data_source_service.delete_project_data_file(
            self.project["project_id"],
            excel_file["file_id"],
        )
        self.assertTrue(result["cleared_current_analysis"])
        project = project_workspace.get_project(self.project["project_id"])
        self.assertIsNone(project["current_analysis_file"])


if __name__ == "__main__":
    unittest.main()
