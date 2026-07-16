from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from tests.helpers.fixture_loader import (
    copy_fixture_to_temp,
    fixture_path,
    load_csv_fixture,
)
from src import project_workspace
from src.services.data_quality_service import (
    apply_duplicate_group_preview,
    apply_duplicate_handling_plan_preview,
    apply_missing_value_plan_preview,
    detect_identifier_columns,
    get_final_id_columns,
    get_iqr_numeric_measure_columns,
    summarize_duplicate_handling_effect,
    summarize_duplicates_for_quality,
    summarize_iqr_outliers_for_quality,
    summarize_missing_value_plan_effect,
    update_id_override_state,
)
from src.services.data_source_service import save_project_data_files
from src.services.relationship_service import (
    discover_project_relationships,
    list_project_tables,
)


FIXTURE_CONTRACTS = {
    "sales_basic.csv": {
        "shape": (12, 6),
        "columns": ["成交日期", "销售工号", "产品", "区域", "成交金额", "成交客户数"],
    },
    "sales_missing.csv": {
        "shape": (10, 6),
        "columns": ["成交日期", "销售工号", "产品", "区域", "成交金额", "成交客户数"],
    },
    "sales_duplicates.csv": {
        "shape": (10, 6),
        "columns": ["成交日期", "销售工号", "产品", "区域", "成交金额", "成交客户数"],
    },
    "sales_outliers.csv": {
        "shape": (14, 5),
        "columns": ["成交日期", "销售工号", "产品", "成交金额", "成交客户数"],
    },
    "sales_id_fields.csv": {
        "shape": (10, 6),
        "columns": ["成交日期", "销售工号", "订单号", "成交金额", "客单价", "产品"],
    },
    "customers.csv": {
        "shape": (6, 3),
        "columns": ["customer_id", "customer_name", "region"],
    },
    "orders.csv": {
        "shape": (10, 5),
        "columns": ["order_id", "customer_id", "product_id", "order_date", "amount"],
    },
    "products.csv": {
        "shape": (5, 4),
        "columns": ["product_id", "product_name", "category", "unit_price"],
    },
}


class UploadedFileStub(BytesIO):
    def __init__(self, name: str, content: bytes):
        super().__init__(content)
        self.name = name
        self.size = len(content)

    def getvalue(self) -> bytes:
        return super().getvalue()


class FixtureIntegrityTests(unittest.TestCase):
    def test_required_fixtures_exist_load_and_match_documented_shapes(self):
        for filename, contract in FIXTURE_CONTRACTS.items():
            with self.subTest(filename=filename):
                path = fixture_path(filename)
                dataframe = load_csv_fixture(filename)

                self.assertTrue(path.is_absolute())
                self.assertEqual(dataframe.shape, contract["shape"])
                self.assertEqual(dataframe.columns.tolist(), contract["columns"])
                self.assertFalse(dataframe.empty)

    def test_readme_row_and_column_counts_match_actual_fixtures(self):
        documented_shapes = {}
        for line in fixture_path("README.md").read_text(encoding="utf-8").splitlines():
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) < 4 or not cells[0].startswith("`"):
                continue
            filename = cells[0].strip("`")
            if filename in FIXTURE_CONTRACTS:
                documented_shapes[filename] = (int(cells[2]), int(cells[3]))

        self.assertEqual(set(documented_shapes), set(FIXTURE_CONTRACTS))
        for filename, contract in FIXTURE_CONTRACTS.items():
            with self.subTest(filename=filename):
                self.assertEqual(documented_shapes[filename], contract["shape"])
                self.assertEqual(load_csv_fixture(filename).shape, documented_shapes[filename])

    def test_fixture_can_be_copied_to_an_isolated_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            copied_path = copy_fixture_to_temp("sales_basic.csv", temp_dir)

            self.assertEqual(copied_path.parent, Path(temp_dir))
            self.assertEqual(copied_path.read_bytes(), fixture_path("sales_basic.csv").read_bytes())
            self.assertEqual(pd.read_csv(copied_path, encoding="utf-8").shape, (12, 6))


class SalesBasicFixtureTests(unittest.TestCase):
    def test_clean_fixture_matches_quality_and_id_contract(self):
        dataframe = load_csv_fixture("sales_basic.csv")

        self.assertEqual(int(dataframe.isna().sum().sum()), 0)
        self.assertEqual(int(dataframe.duplicated().sum()), 0)
        self.assertTrue(pd.api.types.is_numeric_dtype(dataframe["成交金额"]))
        self.assertTrue(pd.api.types.is_numeric_dtype(dataframe["成交客户数"]))

        identifiers = detect_identifier_columns(dataframe)
        self.assertIn("销售工号", identifiers)
        self.assertNotIn("成交金额", identifiers)
        self.assertNotIn("成交客户数", identifiers)
        self.assertNotIn("成交日期", identifiers)


class SalesMissingFixtureTests(unittest.TestCase):
    def test_missing_counts_match_documented_contract(self):
        dataframe = load_csv_fixture("sales_missing.csv")

        self.assertEqual(int(dataframe.isna().sum().sum()), 4)
        self.assertEqual(
            dataframe.isna().sum().to_dict(),
            {
                "成交日期": 1,
                "销售工号": 0,
                "产品": 0,
                "区域": 1,
                "成交金额": 2,
                "成交客户数": 0,
            },
        )

    def test_multiple_missing_steps_use_a_copy_and_remove_expected_missing_values(self):
        dataframe = load_csv_fixture("sales_missing.csv")
        original = dataframe.copy(deep=True)
        plan = [
            {"column": "成交金额", "method": "mean"},
            {"column": "区域", "method": "mode"},
            {"column": "成交日期", "method": "drop_rows"},
        ]

        preview = apply_missing_value_plan_preview(dataframe, plan)
        effect = summarize_missing_value_plan_effect(dataframe, plan)

        pd.testing.assert_frame_equal(dataframe, original)
        self.assertEqual(float(preview["成交金额"].iloc[3]), 170.0)
        self.assertEqual(preview["区域"].iloc[2], "华东")
        self.assertEqual(int(preview.isna().sum().sum()), 0)
        self.assertEqual(len(preview), 9)
        self.assertEqual(effect["before_missing_values"], 4)
        self.assertEqual(effect["after_missing_values"], 0)
        self.assertEqual(effect["after_rows"], 9)


class SalesDuplicatesFixtureTests(unittest.TestCase):
    def test_keep_first_contract_retains_one_row_per_duplicate_group(self):
        dataframe = load_csv_fixture("sales_duplicates.csv")
        original = dataframe.copy(deep=True)
        summary = summarize_duplicates_for_quality(dataframe)
        plan = {"method": "drop_all_duplicates"}

        preview = apply_duplicate_handling_plan_preview(dataframe, plan)
        group_preview = apply_duplicate_group_preview(dataframe, plan)
        effect = summarize_duplicate_handling_effect(dataframe, plan)

        pd.testing.assert_frame_equal(dataframe, original)
        self.assertEqual(summary["duplicate_group_rows"], 4)
        self.assertEqual(summary["duplicate_count"], 2)
        self.assertEqual(effect["removed_rows"], 2)
        self.assertEqual(effect["after_duplicate_group_rows"], 0)
        self.assertEqual(len(preview), 8)
        self.assertEqual(group_preview.index.tolist(), [1, 6])
        self.assertEqual(preview.index.tolist(), [0, 1, 3, 4, 5, 6, 8, 9])

    def test_selected_duplicate_deletion_uses_stable_original_indexes(self):
        dataframe = load_csv_fixture("sales_duplicates.csv")
        original = dataframe.copy(deep=True)
        plan = {"method": "drop_selected_rows", "row_indices": [2, 7]}

        preview = apply_duplicate_handling_plan_preview(dataframe, plan)
        group_preview = apply_duplicate_group_preview(dataframe, plan)

        pd.testing.assert_frame_equal(dataframe, original)
        self.assertEqual(preview.index.tolist(), [0, 1, 3, 4, 5, 6, 8, 9])
        self.assertEqual(group_preview.index.tolist(), [1, 6])
        self.assertEqual(int(preview.duplicated().sum()), 0)


class SalesIdFixtureTests(unittest.TestCase):
    def test_identifier_detection_protects_business_measures_and_dates(self):
        dataframe = load_csv_fixture("sales_id_fields.csv")

        identifiers = detect_identifier_columns(dataframe)

        self.assertIn("销售工号", identifiers)
        self.assertIn("订单号", identifiers)
        self.assertNotIn("成交金额", identifiers)
        self.assertNotIn("客单价", identifiers)
        self.assertNotIn("成交日期", identifiers)

    def test_manual_id_cancellation_and_marking_update_the_final_set(self):
        dataframe = load_csv_fixture("sales_id_fields.csv")
        automatic = detect_identifier_columns(dataframe)

        manual_ids, manual_non_ids = update_id_override_state(
            dataframe,
            manual_id_columns=[],
            manual_non_id_columns=[],
            column="销售工号",
            action="mark_non_id",
        )
        manual_ids, manual_non_ids = update_id_override_state(
            dataframe,
            manual_id_columns=manual_ids,
            manual_non_id_columns=manual_non_ids,
            column="产品",
            action="mark_id",
        )
        final_ids = get_final_id_columns(
            dataframe,
            auto_id_columns=automatic,
            manual_id_columns=manual_ids,
            manual_non_id_columns=manual_non_ids,
        )

        self.assertEqual(final_ids, ["订单号", "产品"])


class SalesOutlierFixtureTests(unittest.TestCase):
    def test_iqr_contract_excludes_identifier_and_finds_deterministic_outliers(self):
        dataframe = load_csv_fixture("sales_outliers.csv")
        identifiers = detect_identifier_columns(dataframe)
        measure_columns = get_iqr_numeric_measure_columns(dataframe, identifiers)
        summary = summarize_iqr_outliers_for_quality(dataframe, identifiers)

        self.assertIn("销售工号", identifiers)
        self.assertNotIn("销售工号", measure_columns)
        self.assertIn("成交金额", measure_columns)
        self.assertIn("成交客户数", measure_columns)

        amount = summary.loc[summary["字段名"] == "成交金额"].iloc[0]
        customers = summary.loc[summary["字段名"] == "成交客户数"].iloc[0]
        self.assertEqual(float(amount["Q1"]), 106.5)
        self.assertEqual(float(amount["Q3"]), 119.5)
        self.assertEqual(float(amount["IQR"]), 13.0)
        self.assertEqual(float(amount["下界"]), 87.0)
        self.assertEqual(float(amount["上界"]), 139.0)
        self.assertEqual(int(amount["异常值数量"]), 2)
        self.assertEqual(int(customers["异常值数量"]), 0)

        outlier_mask = (dataframe["成交金额"] < amount["下界"]) | (
            dataframe["成交金额"] > amount["上界"]
        )
        self.assertEqual(dataframe.index[outlier_mask].tolist(), [12, 13])
        self.assertEqual(dataframe.loc[outlier_mask, "成交金额"].tolist(), [500, 600])


class RelationshipFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "projects"
        self.root_patch = patch.object(project_workspace, "PROJECT_ROOT", self.project_root)
        self.root_patch.start()
        self.project = project_workspace.create_project("Fixture Relationships")
        save_project_data_files(
            self.project["project_id"],
            [
                UploadedFileStub(filename, fixture_path(filename).read_bytes())
                for filename in ("customers.csv", "orders.csv", "products.csv")
            ],
        )

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def test_relationship_recommendations_and_display_names_match_contract(self):
        tables = list_project_tables(self.project["project_id"])
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

        self.assertEqual(
            {table["table_name"] for table in tables},
            {"customers.csv", "orders.csv", "products.csv"},
        )
        self.assertIn(
            ("orders.csv", "customer_id", "customers.csv", "customer_id"),
            pairs,
        )
        self.assertIn(
            ("orders.csv", "product_id", "products.csv", "product_id"),
            pairs,
        )

    def test_relationship_keys_and_join_counts_match_documented_contract(self):
        customers = load_csv_fixture("customers.csv")
        orders = load_csv_fixture("orders.csv")
        products = load_csv_fixture("products.csv")

        self.assertTrue(customers["customer_id"].is_unique)
        self.assertTrue(products["product_id"].is_unique)
        self.assertTrue(orders["order_id"].is_unique)
        self.assertLessEqual(set(orders["customer_id"]), set(customers["customer_id"]))
        self.assertLessEqual(set(orders["product_id"]), set(products["product_id"]))

        self.assertEqual(len(orders.merge(customers, on="customer_id", how="inner")), 10)
        self.assertEqual(len(orders.merge(customers, on="customer_id", how="left")), 10)
        self.assertEqual(len(orders.merge(products, on="product_id", how="inner")), 10)
        self.assertEqual(len(orders.merge(products, on="product_id", how="left")), 10)
        self.assertEqual(len(customers.merge(orders, on="customer_id", how="left")), 11)
        self.assertEqual(len(products.merge(orders, on="product_id", how="left")), 11)
        self.assertEqual(
            len(
                orders.merge(customers, on="customer_id", how="inner").merge(
                    products,
                    on="product_id",
                    how="inner",
                )
            ),
            10,
        )


if __name__ == "__main__":
    unittest.main()
