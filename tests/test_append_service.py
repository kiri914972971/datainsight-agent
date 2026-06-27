import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src import project_workspace
from src.services.append_service import (
    analyze_append_compatibility,
    build_appended_dataset,
    get_appended_dataset_metadata,
    list_append_sources,
    load_appended_dataset,
    set_appended_dataset_as_current,
)
from src.services.data_source_service import save_project_data_files


class UploadedFileStub(BytesIO):
    def __init__(self, name: str, content: bytes):
        super().__init__(content)
        self.name = name

    def getvalue(self) -> bytes:
        return super().getvalue()


class AppendServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "projects"
        self.root_patch = patch.object(
            project_workspace,
            "PROJECT_ROOT",
            self.project_root,
        )
        self.root_patch.start()
        self.project = project_workspace.create_project("Append")

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def _save_csv_files(self, files: list[tuple[str, bytes]]) -> list[str]:
        save_project_data_files(
            self.project["project_id"],
            [UploadedFileStub(name, content) for name, content in files],
        )
        sources = list_append_sources(self.project["project_id"])
        source_by_name = {source["file_name"]: source["source_id"] for source in sources}
        return [source_by_name[name] for name, _ in files]

    def test_appends_tables_with_identical_fields(self):
        source_ids = self._save_csv_files(
            [
                ("apr_may.csv", b"date,region,amount\n2026-04-01,East,100\n2026-05-01,West,200\n"),
                ("june.csv", b"date,region,amount\n2026-06-01,East,300\n"),
            ]
        )

        metadata = build_appended_dataset(self.project["project_id"], source_ids)
        appended = load_appended_dataset(self.project["project_id"])

        self.assertEqual(metadata["after_rows"], 3)
        self.assertEqual(metadata["before_total_rows"], 3)
        self.assertEqual(metadata["validation_summary"]["before_total_rows"], 3)
        self.assertEqual(metadata["validation_summary"]["after_rows"], 3)
        self.assertTrue(metadata["validation_summary"]["row_count_matches"])
        self.assertFalse(metadata["validation_summary"]["has_filled_null_fields"])
        self.assertEqual(metadata["file_path"], "analysis/appended_dataset.csv")
        self.assertEqual(
            metadata["saved_path"],
            f"workspace/projects/{self.project['project_id']}/analysis/appended_dataset.csv",
        )
        self.assertEqual(
            metadata["metadata_path"],
            f"workspace/projects/{self.project['project_id']}/analysis/appended_dataset_meta.json",
        )
        self.assertTrue(
            (
                project_workspace.get_project_path(self.project["project_id"])
                / "analysis"
                / "appended_dataset.csv"
            ).is_file()
        )
        self.assertTrue(
            (
                project_workspace.get_project_path(self.project["project_id"])
                / "analysis"
                / "appended_dataset_meta.json"
            ).is_file()
        )
        self.assertEqual(list(appended.columns), ["date", "region", "amount"])
        self.assertEqual(int(appended["amount"].sum()), 600)

    def test_appends_tables_with_different_column_order(self):
        source_ids = self._save_csv_files(
            [
                ("first.csv", b"date,region,amount\n2026-04-01,East,100\n"),
                ("second.csv", b"amount,date,region\n200,2026-05-01,West\n"),
            ]
        )

        compatibility = analyze_append_compatibility(self.project["project_id"], source_ids)
        metadata = build_appended_dataset(self.project["project_id"], source_ids)
        appended = load_appended_dataset(self.project["project_id"])

        self.assertTrue(compatibility["field_order_different"])
        self.assertEqual(metadata["after_rows"], 2)
        self.assertEqual(list(appended.columns), ["date", "region", "amount"])
        self.assertEqual(appended.loc[1, "region"], "West")

    def test_appends_tables_with_missing_field_and_fills_nulls(self):
        source_ids = self._save_csv_files(
            [
                ("full.csv", b"date,region,amount,channel\n2026-04-01,East,100,Online\n"),
                ("missing.csv", b"date,region,amount\n2026-05-01,West,200\n"),
            ]
        )

        compatibility = analyze_append_compatibility(self.project["project_id"], source_ids)
        metadata = build_appended_dataset(self.project["project_id"], source_ids)
        appended = load_appended_dataset(self.project["project_id"])

        missing_source_id = source_ids[1]
        self.assertIn("channel", compatibility["missing_fields_by_source"][missing_source_id])
        self.assertIn("channel", metadata["field_alignment"]["suggested_null_fields"][missing_source_id])
        self.assertTrue(metadata["validation_summary"]["row_count_matches"])
        self.assertTrue(metadata["validation_summary"]["has_filled_null_fields"])
        self.assertEqual(metadata["validation_summary"]["filled_null_fields"], ["channel"])
        self.assertEqual(metadata["auto_fill_strategy"], "NaN")
        self.assertEqual(metadata["missing_fields"][0]["fields"], ["channel"])
        self.assertTrue(pd.isna(appended.loc[1, "channel"]))
        self.assertEqual(metadata["after_rows"], 2)

    def test_missing_field_fill_zero_strategy(self):
        source_ids = self._save_csv_files(
            [
                ("full.csv", b"date,amount,discount\n2026-04-01,100,5\n"),
                ("missing.csv", b"date,amount\n2026-05-01,200\n"),
            ]
        )

        metadata = build_appended_dataset(
            self.project["project_id"],
            source_ids,
            [{"field": "discount", "strategy": "zero"}],
        )
        appended = load_appended_dataset(self.project["project_id"])

        self.assertEqual(float(appended.loc[1, "discount"]), 0)
        self.assertEqual(metadata["fill_strategies"][0]["strategy"], "zero")

    def test_missing_field_fill_unknown_strategy(self):
        source_ids = self._save_csv_files(
            [
                ("full.csv", b"date,amount,channel\n2026-04-01,100,Online\n"),
                ("missing.csv", b"date,amount\n2026-05-01,200\n"),
            ]
        )

        metadata = build_appended_dataset(
            self.project["project_id"],
            source_ids,
            [{"field": "channel", "strategy": "unknown"}],
        )
        appended = load_appended_dataset(self.project["project_id"])

        self.assertEqual(appended.loc[1, "channel"], "未知")
        self.assertEqual(metadata["fill_strategies"][0]["strategy"], "unknown")

    def test_missing_field_fill_mode_strategy(self):
        source_ids = self._save_csv_files(
            [
                (
                    "full.csv",
                    b"date,amount,channel\n2026-04-01,100,Online\n2026-04-02,120,Online\n2026-04-03,130,Retail\n",
                ),
                ("missing.csv", b"date,amount\n2026-05-01,200\n"),
            ]
        )

        metadata = build_appended_dataset(
            self.project["project_id"],
            source_ids,
            [{"field": "channel", "strategy": "mode"}],
        )
        appended = load_appended_dataset(self.project["project_id"])

        self.assertEqual(appended.loc[3, "channel"], "Online")
        self.assertEqual(metadata["fill_strategies"][0]["strategy"], "mode")

    def test_missing_field_fill_custom_strategy(self):
        source_ids = self._save_csv_files(
            [
                ("full.csv", b"date,amount,channel\n2026-04-01,100,Online\n"),
                ("missing.csv", b"date,amount\n2026-05-01,200\n"),
            ]
        )

        metadata = build_appended_dataset(
            self.project["project_id"],
            source_ids,
            [{"field": "channel", "strategy": "custom", "custom_value": "线下"}],
        )
        appended = load_appended_dataset(self.project["project_id"])

        self.assertEqual(appended.loc[1, "channel"], "线下")
        self.assertEqual(metadata["fill_strategies"][0]["strategy"], "custom")
        self.assertEqual(metadata["fill_strategies"][0]["custom_value"], "线下")

    def test_set_appended_dataset_as_current_analysis_dataset(self):
        source_ids = self._save_csv_files(
            [
                ("one.csv", b"date,region,amount\n2026-04-01,East,100\n"),
                ("two.csv", b"date,region,amount\n2026-05-01,West,200\n"),
            ]
        )
        build_appended_dataset(self.project["project_id"], source_ids)

        selection = set_appended_dataset_as_current(self.project["project_id"])
        project = project_workspace.get_project(self.project["project_id"])
        metadata = get_appended_dataset_metadata(self.project["project_id"])

        self.assertEqual(selection["source_type"], "appended_dataset")
        self.assertEqual(selection["file_id"], "appended_dataset")
        self.assertEqual(selection["display_name"], "合并数据集 appended_dataset.csv")
        self.assertEqual(project["current_analysis_file"]["source_type"], "appended_dataset")
        self.assertEqual(metadata["after_rows"], 2)

    def test_appended_dataset_loads_after_project_reload(self):
        source_ids = self._save_csv_files(
            [
                ("one.csv", b"date,region,amount\n2026-04-01,East,100\n"),
                ("two.csv", b"date,region,amount\n2026-05-01,West,200\n"),
            ]
        )
        build_appended_dataset(self.project["project_id"], source_ids)
        set_appended_dataset_as_current(self.project["project_id"])

        reloaded_project = project_workspace.get_project(self.project["project_id"])
        reloaded_df = load_appended_dataset(self.project["project_id"])

        self.assertEqual(
            reloaded_project["current_analysis_file"]["file_name"],
            "appended_dataset.csv",
        )
        self.assertEqual(len(reloaded_df), 2)
        self.assertEqual(int(reloaded_df["amount"].sum()), 300)


if __name__ == "__main__":
    unittest.main()
