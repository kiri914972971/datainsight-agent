import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src import project_workspace
from src.engines.relationship_engine import discover_relationship_candidates
from src.services.data_source_service import save_project_data_files
from src.services.relationship_service import (
    clear_table_relationships,
    delete_table_relationship,
    discover_project_relationships,
    get_project_table_columns,
    list_project_tables,
    load_table_relationships,
    save_table_relationships,
)


class UploadedFileStub(BytesIO):
    def __init__(self, name: str, content: bytes):
        super().__init__(content)
        self.name = name

    def getvalue(self) -> bytes:
        return super().getvalue()


class RelationshipEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "projects"
        self.root_patch = patch.object(
            project_workspace,
            "PROJECT_ROOT",
            self.project_root,
        )
        self.root_patch.start()
        self.project = project_workspace.create_project("Relationships")
        save_project_data_files(
            self.project["project_id"],
            [
                UploadedFileStub(
                    "orders.csv",
                    b"order_id,product_id,sales_id,amount\n1,P1,S1,100\n2,P1,S2,200\n3,P2,S1,300\n",
                ),
                UploadedFileStub(
                    "products.csv",
                    b"product_id,product_name\nP1,Loan\nP2,Card\n",
                ),
                UploadedFileStub(
                    "employees.csv",
                    b"sales_id,employee_name\nS1,Alice\nS2,Bob\n",
                ),
            ],
        )

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def test_discovers_candidate_relationships(self):
        candidates = discover_project_relationships(self.project["project_id"])
        pairs = {
            (
                item["table_a_name"],
                item["field_a"],
                item["table_b_name"],
                item["field_b"],
            )
            for item in candidates
        }

        self.assertIn(("orders", "product_id", "products", "product_id"), pairs)
        self.assertIn(("orders", "sales_id", "employees", "sales_id"), pairs)
        product_candidate = next(
            item for item in candidates if item["field_a"] == "product_id"
        )
        self.assertEqual(product_candidate["confidence"], 90)
        self.assertEqual(product_candidate["score_breakdown"]["字段名完全一致"], 50)
        self.assertEqual(product_candidate["relationship_type"], "many_to_one")

    def test_does_not_recommend_same_named_amount_measures_as_keys(self):
        candidates = discover_relationship_candidates(
            [
                {
                    "table_id": "orders",
                    "table_name": "orders",
                    "file_id": "orders",
                    "file_name": "orders.csv",
                    "sheet_name": "CSV",
                    "dataframe": pd.DataFrame(
                        {"amount": [100, 200], "date": ["2026-01-01", "2026-01-02"]}
                    ),
                },
                {
                    "table_id": "backup",
                    "table_name": "backup",
                    "file_id": "backup",
                    "file_name": "backup.csv",
                    "sheet_name": "CSV",
                    "dataframe": pd.DataFrame(
                        {"amount": [100, 200], "date": ["2026-01-01", "2026-01-02"]}
                    ),
                },
            ]
        )

        candidate_fields = {(item["field_a"], item["field_b"]) for item in candidates}
        self.assertIn(("date", "date"), candidate_fields)
        self.assertNotIn(("amount", "amount"), candidate_fields)

    def test_recommends_dates_but_excludes_amount_from_connectable_fields(self):
        candidates = discover_relationship_candidates(
            [
                {
                    "table_id": "a",
                    "table_name": "a",
                    "file_id": "a",
                    "file_name": "a.csv",
                    "sheet_name": "CSV",
                    "dataframe": pd.DataFrame(
                        {"成交日期": ["2026-01-01", "2026-01-02"], "成交金额": [100, 200]}
                    ),
                },
                {
                    "table_id": "b",
                    "table_name": "b",
                    "file_id": "b",
                    "file_name": "b.csv",
                    "sheet_name": "CSV",
                    "dataframe": pd.DataFrame(
                        {"成交日期": ["2026-01-01", "2026-01-02"], "成交金额": [100, 200]}
                    ),
                },
            ]
        )
        candidate_fields = {(item["field_a"], item["field_b"]) for item in candidates}

        self.assertIn(("成交日期", "成交日期"), candidate_fields)
        self.assertNotIn(("成交金额", "成交金额"), candidate_fields)

        orders_table = next(
            table
            for table in list_project_tables(self.project["project_id"])
            if table["table_name"] == "orders"
        )
        connectable = get_project_table_columns(
            self.project["project_id"],
            orders_table["table_id"],
            connectable_only=True,
        )
        self.assertNotIn("amount", connectable)
        self.assertIn("product_id", connectable)

    def test_saves_loads_and_syncs_relationships_to_project(self):
        tables = {table["table_name"]: table for table in list_project_tables(self.project["project_id"])}
        relationship = {
            "table_a_id": tables["orders"]["table_id"],
            "table_a_name": "orders",
            "table_a_file_id": tables["orders"]["file_id"],
            "table_a_file_name": tables["orders"]["file_name"],
            "table_a_sheet_name": tables["orders"]["sheet_name"],
            "field_a": "product_id",
            "table_b_id": tables["products"]["table_id"],
            "table_b_name": "products",
            "table_b_file_id": tables["products"]["file_id"],
            "table_b_file_name": tables["products"]["file_name"],
            "table_b_sheet_name": tables["products"]["sheet_name"],
            "field_b": "product_id",
            "relationship_type": "many_to_one",
            "confidence": 95,
            "reason": "test",
            "source": "auto",
        }

        saved = save_table_relationships(self.project["project_id"], [relationship])
        loaded = load_table_relationships(self.project["project_id"])
        project = project_workspace.get_project(self.project["project_id"])

        self.assertEqual(saved, loaded)
        self.assertEqual(project["table_relationships"], loaded)
        self.assertEqual(loaded[0]["relationship_type"], "many_to_one")
        self.assertEqual(loaded[0]["confidence"], 95)
        self.assertTrue(
            (
                self.project_root
                / self.project["project_id"]
                / "config"
                / "table_relationships.json"
            ).is_file()
        )

    def test_loads_legacy_main_target_relationship_as_table_a_table_b(self):
        tables = {table["table_name"]: table for table in list_project_tables(self.project["project_id"])}
        legacy = {
            "main_table_id": tables["orders"]["table_id"],
            "main_table_name": "orders",
            "main_column": "sales_id",
            "target_table_id": tables["employees"]["table_id"],
            "target_table_name": "employees",
            "target_column": "sales_id",
            "confidence": 0.95,
        }

        saved = save_table_relationships(self.project["project_id"], [legacy])

        self.assertEqual(saved[0]["table_a_name"], "orders")
        self.assertEqual(saved[0]["field_a"], "sales_id")
        self.assertEqual(saved[0]["table_b_name"], "employees")
        self.assertEqual(saved[0]["field_b"], "sales_id")
        self.assertEqual(saved[0]["confidence"], 95)

    def test_deletes_single_relationship_and_syncs_project(self):
        tables = {table["table_name"]: table for table in list_project_tables(self.project["project_id"])}
        first = {
            "table_a_id": tables["orders"]["table_id"],
            "table_a_name": "orders",
            "field_a": "product_id",
            "table_b_id": tables["products"]["table_id"],
            "table_b_name": "products",
            "field_b": "product_id",
            "relationship_type": "many_to_one",
        }
        second = {
            "table_a_id": tables["orders"]["table_id"],
            "table_a_name": "orders",
            "field_a": "sales_id",
            "table_b_id": tables["employees"]["table_id"],
            "table_b_name": "employees",
            "field_b": "sales_id",
            "relationship_type": "many_to_one",
        }
        saved = save_table_relationships(self.project["project_id"], [first, second])
        deleted_id = saved[0]["relationship_id"]

        remaining = delete_table_relationship(self.project["project_id"], deleted_id)
        loaded = load_table_relationships(self.project["project_id"])
        project = project_workspace.get_project(self.project["project_id"])

        self.assertEqual(remaining, loaded)
        self.assertEqual(project["table_relationships"], loaded)
        self.assertEqual(len(loaded), 1)
        self.assertNotIn(deleted_id, {item["relationship_id"] for item in loaded})

    def test_clears_all_relationships_and_syncs_project(self):
        tables = {table["table_name"]: table for table in list_project_tables(self.project["project_id"])}
        relationship = {
            "table_a_id": tables["orders"]["table_id"],
            "table_a_name": "orders",
            "field_a": "product_id",
            "table_b_id": tables["products"]["table_id"],
            "table_b_name": "products",
            "field_b": "product_id",
            "relationship_type": "many_to_one",
        }
        save_table_relationships(self.project["project_id"], [relationship])

        cleared = clear_table_relationships(self.project["project_id"])
        loaded = load_table_relationships(self.project["project_id"])
        project = project_workspace.get_project(self.project["project_id"])

        self.assertEqual(cleared, [])
        self.assertEqual(loaded, [])
        self.assertEqual(project["table_relationships"], [])

    def test_deleted_relationship_does_not_reappear_after_project_reload(self):
        tables = {table["table_name"]: table for table in list_project_tables(self.project["project_id"])}
        relationship = {
            "table_a_id": tables["orders"]["table_id"],
            "table_a_name": "orders",
            "field_a": "product_id",
            "table_b_id": tables["products"]["table_id"],
            "table_b_name": "products",
            "field_b": "product_id",
            "relationship_type": "many_to_one",
        }
        saved = save_table_relationships(self.project["project_id"], [relationship])
        relationship_id = saved[0]["relationship_id"]

        delete_table_relationship(self.project["project_id"], relationship_id)
        reloaded_project = project_workspace.get_project(self.project["project_id"])

        self.assertEqual(reloaded_project["table_relationships"], [])
        self.assertEqual(load_table_relationships(self.project["project_id"]), [])


if __name__ == "__main__":
    unittest.main()
