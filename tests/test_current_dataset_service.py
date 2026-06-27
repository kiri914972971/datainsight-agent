import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from src import project_workspace
from src.engines.eda_engine import generate_eda_report
from src.services.append_service import build_appended_dataset, list_append_sources, set_appended_dataset_as_current
from src.services.current_dataset_service import (
    NO_CURRENT_ANALYSIS_DATASET_MESSAGE,
    get_current_analysis_dataset,
    list_project_datasets,
    load_project_dataset_dataframe,
    load_current_analysis_dataframe,
)
from src.services.data_quality_service import (
    create_cleaned_dataset,
    set_cleaned_dataset_as_current,
)
from src.services.data_source_service import save_project_data_files, set_current_analysis_file


class UploadedFileStub(BytesIO):
    def __init__(self, name: str, content: bytes):
        super().__init__(content)
        self.name = name

    def getvalue(self) -> bytes:
        return super().getvalue()


class CurrentDatasetServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "projects"
        self.root_patch = patch.object(
            project_workspace,
            "PROJECT_ROOT",
            self.project_root,
        )
        self.root_patch.start()
        self.project = project_workspace.create_project("Current Dataset")

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def _save_csv_files(self, files: list[tuple[str, bytes]]) -> list[dict]:
        return save_project_data_files(
            self.project["project_id"],
            [UploadedFileStub(name, content) for name, content in files],
        )

    def test_sets_uploaded_file_as_current_analysis_dataset(self):
        saved = self._save_csv_files(
            [("orders.csv", b"date,region,amount\n2026-01-01,East,100\n")]
        )

        set_current_analysis_file(self.project["project_id"], saved[0]["file_id"], "CSV")
        current = get_current_analysis_dataset(self.project["project_id"])
        dataframe = load_current_analysis_dataframe(self.project["project_id"])
        project = project_workspace.get_project(self.project["project_id"])
        datasets = list_project_datasets(self.project["project_id"])

        self.assertEqual(current["dataset_type"], "uploaded")
        self.assertEqual(current["dataset_name"], "orders.csv")
        self.assertEqual(current["file_path"], "data/orders.csv")
        self.assertEqual(current["row_count"], 1)
        self.assertEqual(project["current_analysis_dataset"], current)
        self.assertEqual(len(dataframe), 1)
        self.assertEqual(len(datasets), 1)
        self.assertEqual(datasets[0]["dataset_type"], "uploaded")
        self.assertEqual(datasets[0]["dataset_name"], "orders.csv")

    def test_sets_appended_dataset_as_current_analysis_dataset(self):
        self._save_csv_files(
            [
                ("one.csv", b"date,region,amount\n2026-01-01,East,100\n"),
                ("two.csv", b"date,region,amount\n2026-02-01,West,200\n"),
            ]
        )
        source_ids = [source["source_id"] for source in list_append_sources(self.project["project_id"])]
        build_appended_dataset(self.project["project_id"], source_ids)

        set_appended_dataset_as_current(self.project["project_id"])
        current = get_current_analysis_dataset(self.project["project_id"])
        dataframe = load_current_analysis_dataframe(self.project["project_id"])
        datasets = list_project_datasets(self.project["project_id"])
        appended_dataset = next(item for item in datasets if item["dataset_id"] == "appended_dataset")
        appended_preview = load_project_dataset_dataframe(
            self.project["project_id"],
            "appended_dataset",
        )

        self.assertEqual(current["dataset_type"], "appended")
        self.assertEqual(current["dataset_name"], "appended_dataset.csv")
        self.assertEqual(current["file_path"], "analysis/appended_dataset.csv")
        self.assertEqual(current["row_count"], 2)
        self.assertEqual(len(dataframe), 2)
        self.assertEqual(appended_dataset["dataset_type"], "appended")
        self.assertEqual(appended_dataset["row_count"], 2)
        self.assertEqual(len(appended_preview), 2)

    def test_appended_dataset_is_registered_before_set_current(self):
        self._save_csv_files(
            [
                ("one.csv", b"date,region,amount\n2026-01-01,East,100\n"),
                ("two.csv", b"date,region,amount\n2026-02-01,West,200\n"),
            ]
        )
        source_ids = [source["source_id"] for source in list_append_sources(self.project["project_id"])]
        build_appended_dataset(self.project["project_id"], source_ids)

        datasets = list_project_datasets(self.project["project_id"])
        dataset_ids = {item["dataset_id"] for item in datasets}
        appended_preview = load_project_dataset_dataframe(
            self.project["project_id"],
            "appended_dataset",
        )

        self.assertIn("appended_dataset", dataset_ids)
        self.assertEqual(len(appended_preview), 2)

    def test_reloads_current_dataset_after_project_restart(self):
        saved = self._save_csv_files(
            [("orders.csv", b"date,region,amount\n2026-01-01,East,100\n")]
        )
        set_current_analysis_file(self.project["project_id"], saved[0]["file_id"], "CSV")

        reloaded_project = project_workspace.get_project(self.project["project_id"])
        dataframe = load_current_analysis_dataframe(reloaded_project["project_id"])

        self.assertEqual(reloaded_project["current_analysis_dataset"]["dataset_name"], "orders.csv")
        self.assertEqual(len(dataframe), 1)

    def test_no_current_dataset_uses_unified_message(self):
        with self.assertRaisesRegex(FileNotFoundError, NO_CURRENT_ANALYSIS_DATASET_MESSAGE):
            load_current_analysis_dataframe(self.project["project_id"])

    def test_downstream_eda_reads_uploaded_dataset(self):
        saved = self._save_csv_files(
            [("orders.csv", b"date,region,amount\n2026-01-01,East,100\n")]
        )
        set_current_analysis_file(self.project["project_id"], saved[0]["file_id"], "CSV")

        report = generate_eda_report(self.project["project_id"])

        self.assertEqual(report["overview"]["row_count"], 1)
        self.assertEqual(report["overview"]["column_count"], 3)

    def test_downstream_eda_reads_appended_dataset(self):
        self._save_csv_files(
            [
                ("one.csv", b"date,region,amount\n2026-01-01,East,100\n"),
                ("two.csv", b"date,region,amount\n2026-02-01,West,200\n"),
            ]
        )
        source_ids = [source["source_id"] for source in list_append_sources(self.project["project_id"])]
        build_appended_dataset(self.project["project_id"], source_ids)
        set_appended_dataset_as_current(self.project["project_id"])

        report = generate_eda_report(self.project["project_id"])

        self.assertEqual(report["overview"]["row_count"], 2)
        self.assertEqual(report["overview"]["column_count"], 3)

    def test_downstream_eda_reads_cleaned_dataset(self):
        saved = self._save_csv_files(
            [
                (
                    "quality.csv",
                    b"date,region,amount\n2026-01-01,East,100\n2026-01-02,West,\n",
                )
            ]
        )
        set_current_analysis_file(self.project["project_id"], saved[0]["file_id"], "CSV")
        create_cleaned_dataset(
            self.project["project_id"],
            [{"type": "fill_missing", "column": "amount", "method": "zero"}],
        )
        set_cleaned_dataset_as_current(self.project["project_id"])

        report = generate_eda_report(self.project["project_id"])
        dataframe = load_current_analysis_dataframe(self.project["project_id"])

        self.assertEqual(report["overview"]["row_count"], 2)
        self.assertEqual(report["overview"]["column_count"], 3)
        self.assertEqual(int(dataframe["amount"].isna().sum()), 0)


if __name__ == "__main__":
    unittest.main()
