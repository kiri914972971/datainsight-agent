import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from src import project_workspace


class UploadedFileStub(BytesIO):
    def __init__(self, name: str, content: bytes):
        super().__init__(content)
        self.name = name

    def getvalue(self) -> bytes:
        return super().getvalue()


class ProjectWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "projects"
        self.root_patch = patch.object(
            project_workspace, "PROJECT_ROOT", self.project_root
        )
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def test_project_lifecycle_and_file_persistence(self):
        project = project_workspace.create_project("Sales June")
        project_path = self.project_root / project["project_id"]

        self.assertTrue((project_path / "project.json").is_file())
        for directory in project_workspace.PROJECT_DIRECTORIES:
            self.assertTrue((project_path / directory).is_dir())

        project_workspace.save_project_files(
            project["project_id"],
            [
                UploadedFileStub("orders.csv", b"order_id,amount\n1,100\n"),
                UploadedFileStub("customers.xlsx", b"placeholder"),
            ],
        )

        files = project_workspace.list_project_files(project["project_id"])
        self.assertEqual([item["name"] for item in files], ["customers.xlsx", "orders.csv"])
        loaded = project_workspace.load_project_file(project["project_id"], "orders.csv")
        self.assertEqual(loaded.name, "orders.csv")
        self.assertEqual(loaded.read(), b"order_id,amount\n1,100\n")

        project_workspace.delete_project(project["project_id"])
        self.assertFalse(project_path.exists())

    def test_update_project_merges_fields_without_overwriting_existing_data(self):
        project = project_workspace.create_project("Project Update")
        original_created_at = project["created_at"]
        data_files = [{"file_id": "orders", "file_name": "orders.csv"}]
        current_analysis_file = {
            "file_id": "orders",
            "file_name": "orders.csv",
            "sheet_name": "CSV",
        }

        updated = project_workspace.update_project(
            project["project_id"],
            {
                "data_files": data_files,
                "current_analysis_file": current_analysis_file,
            },
        )
        reloaded = project_workspace.get_project(project["project_id"])

        self.assertEqual(updated, reloaded)
        self.assertEqual(reloaded["project_id"], project["project_id"])
        self.assertEqual(reloaded["project_name"], "Project Update")
        self.assertEqual(reloaded["created_at"], original_created_at)
        self.assertEqual(reloaded["data_files"], data_files)
        self.assertEqual(reloaded["current_analysis_file"], current_analysis_file)
        self.assertTrue(reloaded["updated_at"])

    def test_update_project_reports_missing_and_corrupted_projects(self):
        with self.assertRaisesRegex(
            FileNotFoundError,
            "Project not found: missing-project",
        ):
            project_workspace.update_project("missing-project", {"data_files": []})

        project = project_workspace.create_project("Corrupted Project")
        project_path = self.project_root / project["project_id"]
        (project_path / "project.json").write_text("{invalid", encoding="utf-8")

        with self.assertRaisesRegex(
            ValueError,
            "project.json is corrupted",
        ):
            project_workspace.update_project(project["project_id"], {"data_files": []})


if __name__ == "__main__":
    unittest.main()
