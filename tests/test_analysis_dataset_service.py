import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from src import project_workspace
from src.services.analysis_dataset_service import (
    build_analysis_dataset,
    generate_join_plan,
    get_dataset_metadata,
    load_analysis_dataset,
    preview_analysis_dataset,
)
from src.services.data_source_service import (
    save_project_data_files,
    set_current_analysis_file,
)
from src.services.relationship_service import save_table_relationships


class UploadFile(BytesIO):
    def __init__(self, name: str, content: str):
        data = content.encode("utf-8")
        super().__init__(data)
        self.name = name
        self.size = len(data)


class AnalysisDatasetServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "projects"
        self.root_patch = patch.object(
            project_workspace,
            "PROJECT_ROOT",
            self.project_root,
        )
        self.root_patch.start()
        self.project = project_workspace.create_project("Analysis Dataset Project")

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def test_join_plan_and_dataset_build_many_to_one(self):
        orders, products, employees = save_project_data_files(
            self.project["project_id"],
            [
                UploadFile(
                    "orders.csv",
                    "order_id,product_id,sales_id,amount\n"
                    "1,p1,s1,100\n"
                    "2,p2,s1,120\n"
                    "3,p3,s2,300\n",
                ),
                UploadFile(
                    "products.csv",
                    "product_id,product_name\n"
                    "p1,借呗6期\n"
                    "p2,借呗12期\n",
                ),
                UploadFile(
                    "employees.csv",
                    "sales_id,sales_name\n"
                    "s1,Kiri\n"
                    "s2,Ada\n",
                ),
            ],
        )
        set_current_analysis_file(self.project["project_id"], orders["file_id"], "CSV")
        save_table_relationships(
            self.project["project_id"],
            [
                self._relationship(orders, "product_id", products, "product_id", "many_to_one"),
                self._relationship(orders, "sales_id", employees, "sales_id", "many_to_one"),
            ],
        )

        plan = generate_join_plan(self.project["project_id"])
        product_plan = next(item for item in plan if item["表B"] == "products")

        self.assertEqual(len(plan), 2)
        self.assertEqual(product_plan["预计匹配率"], 66.67)
        self.assertEqual(product_plan["预计扩张倍数"], 1.0)
        self.assertEqual(product_plan["风险"], "中")

        metadata = build_analysis_dataset(self.project["project_id"])
        dataset = load_analysis_dataset(self.project["project_id"])
        preview = preview_analysis_dataset(self.project["project_id"])
        restored_metadata = get_dataset_metadata(self.project["project_id"])

        self.assertEqual(metadata["rows"], 3)
        self.assertEqual(metadata["join_count"], 2)
        self.assertEqual(restored_metadata["rows"], 3)
        self.assertIn("product_name", dataset.columns)
        self.assertIn("sales_name", dataset.columns)
        self.assertEqual(len(preview["preview"]), 3)
        self.assertTrue(
            (
                self.project_root
                / self.project["project_id"]
                / "analysis"
                / "analysis_dataset.csv"
            ).is_file()
        )
        self.assertTrue(
            (
                self.project_root
                / self.project["project_id"]
                / "analysis"
                / "analysis_dataset_meta.json"
            ).is_file()
        )

    def test_one_to_one_one_to_many_and_many_to_many_risk(self):
        customers, profiles, orders, tags = save_project_data_files(
            self.project["project_id"],
            [
                UploadFile(
                    "customers.csv",
                    "customer_id,customer_name\n"
                    "c1,客户A\n"
                    "c2,客户B\n",
                ),
                UploadFile(
                    "profiles.csv",
                    "customer_id,level\n"
                    "c1,VIP\n"
                    "c2,普通\n",
                ),
                UploadFile(
                    "orders.csv",
                    "order_id,customer_id,amount\n"
                    "1,c1,100\n"
                    "2,c1,200\n"
                    "3,c2,300\n",
                ),
                UploadFile(
                    "tags.csv",
                    "customer_id,tag\n"
                    "c1,高价值\n"
                    "c1,复购\n"
                    "c2,新客\n",
                ),
            ],
        )
        save_table_relationships(
            self.project["project_id"],
            [
                self._relationship(customers, "customer_id", profiles, "customer_id", "one_to_one"),
                self._relationship(customers, "customer_id", orders, "customer_id", "one_to_many"),
                self._relationship(orders, "customer_id", tags, "customer_id", "many_to_many"),
            ],
        )

        plan = generate_join_plan(self.project["project_id"])
        by_type = {item["关系类型"]: item for item in plan}

        self.assertEqual(by_type["one_to_one"]["风险"], "低")
        self.assertEqual(by_type["one_to_many"]["预计扩张倍数"], 1.5)
        self.assertEqual(by_type["one_to_many"]["风险"], "中")
        self.assertEqual(by_type["many_to_many"]["风险"], "高")

    def _relationship(self, table_a, field_a, table_b, field_b, relationship_type):
        return {
            "table_a_id": f"{table_a['file_id']}::CSV",
            "table_a_name": Path(table_a["file_name"]).stem,
            "table_a_file_id": table_a["file_id"],
            "table_a_file_name": table_a["file_name"],
            "table_a_sheet_name": "CSV",
            "field_a": field_a,
            "table_b_id": f"{table_b['file_id']}::CSV",
            "table_b_name": Path(table_b["file_name"]).stem,
            "table_b_file_id": table_b["file_id"],
            "table_b_file_name": table_b["file_name"],
            "table_b_sheet_name": "CSV",
            "field_b": field_b,
            "relationship_type": relationship_type,
            "confidence": 95,
        }


if __name__ == "__main__":
    unittest.main()
