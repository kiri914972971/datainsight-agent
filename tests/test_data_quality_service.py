import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src import project_workspace
from src.services.current_dataset_service import (
    get_current_analysis_dataset,
    list_project_datasets,
    load_current_analysis_dataframe,
)
from src.services.append_service import (
    build_appended_dataset,
    list_append_sources,
    set_appended_dataset_as_current,
)
from src.services.data_quality_service import (
    apply_cleaning_plan_preview,
    apply_duplicate_group_preview,
    apply_duplicate_handling_plan_preview,
    apply_missing_value_plan_preview,
    apply_quality_operations,
    create_cleaned_dataset,
    detect_identifier_columns,
    detect_invalid_columns,
    duplicate_handling_plan_to_operations,
    format_duplicate_handling_plan,
    format_missing_value_plan,
    generate_data_repair_suggestions_for_quality,
    get_final_id_columns,
    get_iqr_numeric_measure_columns,
    reset_id_override_state,
    summarize_missing_value_plan_effect,
    set_cleaned_dataset_as_current,
    summarize_duplicates_for_quality,
    summarize_duplicate_handling_effect,
    summarize_identifier_columns,
    summarize_iqr_outliers_for_quality,
    summarize_missing_values_for_quality,
    summarize_quality_overview,
    update_id_override_state,
    upsert_duplicate_handling_plan,
    upsert_missing_value_plan_item,
)
from src.services.data_source_service import save_project_data_files, set_current_analysis_file


class UploadedFileStub(BytesIO):
    def __init__(self, name: str, content: bytes):
        super().__init__(content)
        self.name = name

    def getvalue(self) -> bytes:
        return super().getvalue()


class DataQualityServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "projects"
        self.root_patch = patch.object(
            project_workspace,
            "PROJECT_ROOT",
            self.project_root,
        )
        self.root_patch.start()
        self.project = project_workspace.create_project("Quality")

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def _set_csv_as_current(self, content: bytes = None):
        content = content or (
            b"id,amount,region,mostly_missing\n"
            b"1,10,East,\n"
            b"2,,East,\n"
            b"2,,East,\n"
            b"3,1000,West,\n"
        )
        saved = save_project_data_files(
            self.project["project_id"],
            [UploadedFileStub("quality.csv", content)],
        )
        set_current_analysis_file(self.project["project_id"], saved[0]["file_id"], "CSV")

    def test_missing_value_detection(self):
        self._set_csv_as_current()
        df = load_current_analysis_dataframe(self.project["project_id"])

        summary = summarize_missing_values_for_quality(df)
        amount_row = summary.loc[summary["字段名"] == "amount"].iloc[0]
        mostly_missing_row = summary.loc[summary["字段名"] == "mostly_missing"].iloc[0]

        self.assertEqual(int(amount_row["缺失值数量"]), 2)
        self.assertEqual(float(amount_row["缺失值比例"]), 50.0)
        self.assertEqual(amount_row["推荐处理方式"], "谨慎填充，建议结合业务判断")
        self.assertEqual(mostly_missing_row["推荐处理方式"], "删除字段或重新获取数据源")

    def test_missing_value_fill(self):
        self._set_csv_as_current()
        df = load_current_analysis_dataframe(self.project["project_id"])

        cleaned, steps = apply_quality_operations(
            df,
            [{"type": "fill_missing", "column": "amount", "method": "zero"}],
        )

        self.assertEqual(int(cleaned["amount"].isna().sum()), 0)
        self.assertEqual(float(cleaned.loc[1, "amount"]), 0)
        self.assertEqual(steps[0]["type"], "fill_missing")

    def test_missing_value_plan_applies_multiple_steps_to_copy(self):
        df = pd.DataFrame(
            {
                "amount": [10.0, None, 30.0],
                "region": ["East", None, "West"],
                "drop_me": [None, None, None],
            }
        )
        original = df.copy(deep=True)
        plan = [
            {"column": "amount", "method": "mean"},
            {"column": "region", "method": "custom", "fill_value": "Unknown"},
            {"column": "drop_me", "method": "drop_column"},
        ]

        preview = apply_missing_value_plan_preview(df, plan)
        effect = summarize_missing_value_plan_effect(df, plan)

        pd.testing.assert_frame_equal(df, original)
        self.assertNotIn("drop_me", preview.columns)
        self.assertEqual(int(preview["amount"].isna().sum()), 0)
        self.assertEqual(int(preview["region"].isna().sum()), 0)
        self.assertEqual(effect["before_missing_values"], 5)
        self.assertEqual(effect["after_missing_values"], 0)

    def test_missing_value_plan_replaces_same_column(self):
        plan = []
        plan = upsert_missing_value_plan_item(
            plan,
            {"column": "amount", "method": "mean"},
        )
        plan = upsert_missing_value_plan_item(
            plan,
            {"column": "amount", "method": "median"},
        )

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["column"], "amount")
        self.assertEqual(plan[0]["method"], "median")

    def test_missing_value_plan_format(self):
        df = pd.DataFrame({"amount": [1, None], "region": [None, "East"]})
        plan = [
            {"column": "amount", "method": "median"},
            {"column": "region", "method": "mode"},
        ]

        table = format_missing_value_plan(plan, df)

        self.assertEqual(len(table), 2)
        self.assertIn("字段", table.columns)
        self.assertIn("处理方式", table.columns)
        self.assertIn("预计影响", table.columns)

    def test_drop_high_missing_columns(self):
        self._set_csv_as_current()
        df = load_current_analysis_dataframe(self.project["project_id"])

        cleaned, steps = apply_quality_operations(
            df,
            [{"type": "drop_high_missing_columns", "threshold": 0.8}],
        )

        self.assertNotIn("mostly_missing", cleaned.columns)
        self.assertIn("mostly_missing", steps[0]["dropped_columns"])

    def test_duplicate_detection_and_drop(self):
        self._set_csv_as_current()
        df = load_current_analysis_dataframe(self.project["project_id"])

        duplicate_summary = summarize_duplicates_for_quality(df)
        cleaned, _ = apply_quality_operations(df, [{"type": "drop_duplicates"}])

        self.assertEqual(duplicate_summary["duplicate_count"], 1)
        self.assertEqual(len(cleaned), 3)

    def test_duplicate_plan_drop_all_duplicates_uses_copy(self):
        df = pd.DataFrame(
            {
                "order_id": [1, 1, 2, 3],
                "amount": [10, 10, 20, 30],
            },
            index=[100, 101, 102, 103],
        )
        original = df.copy(deep=True)
        plan = {"method": "drop_all_duplicates"}

        preview = apply_duplicate_handling_plan_preview(df, plan)
        effect = summarize_duplicate_handling_effect(df, plan)
        table = format_duplicate_handling_plan(plan, df)

        pd.testing.assert_frame_equal(df, original)
        self.assertEqual(len(preview), 3)
        self.assertIn(100, preview.index)
        self.assertNotIn(101, preview.index)
        self.assertEqual(effect["removed_rows"], 1)
        self.assertEqual(effect["duplicate_group_rows"], 2)
        self.assertEqual(effect["after_duplicate_group_rows"], 0)
        self.assertFalse(table.empty)

    def test_duplicate_plan_drop_all_keeps_one_row_per_duplicate_group(self):
        df = pd.DataFrame(
            {
                "order_id": [1, 1, 2, 2, 2, 3],
                "amount": [10, 10, 20, 20, 20, 30],
            },
            index=[10, 11, 20, 21, 22, 30],
        )
        plan = {"method": "drop_all_duplicates"}

        preview = apply_duplicate_handling_plan_preview(df, plan)
        group_preview = apply_duplicate_group_preview(df, plan)
        effect = summarize_duplicate_handling_effect(df, plan)

        self.assertEqual(len(preview), 3)
        self.assertEqual(preview.index.tolist(), [10, 20, 30])
        self.assertEqual(group_preview.index.tolist(), [10, 20])
        self.assertEqual(effect["duplicate_group_rows"], 5)
        self.assertEqual(effect["removed_rows"], 3)
        self.assertEqual(effect["after_duplicate_group_rows"], 0)

    def test_duplicate_plan_drop_selected_rows_by_stable_index(self):
        df = pd.DataFrame(
            {
                "order_id": [1, 1, 2, 3],
                "amount": [10, 10, 20, 30],
            },
            index=[100, 101, 102, 103],
        )
        plan = {"method": "drop_selected_rows", "row_indices": [101]}

        preview = apply_duplicate_handling_plan_preview(df, plan)
        group_preview = apply_duplicate_group_preview(df, plan)
        operations = duplicate_handling_plan_to_operations(plan)

        self.assertNotIn(101, preview.index)
        self.assertIn(100, preview.index)
        self.assertEqual(len(preview), 3)
        self.assertEqual(group_preview.index.tolist(), [100])
        self.assertEqual(operations[0]["type"], "drop_rows_by_index")
        self.assertEqual(operations[0]["row_indices"], [101])

    def test_duplicate_metrics_distinguish_group_rows_removed_and_remaining(self):
        df = pd.DataFrame(
            {
                "order_id": [1, 1, 2, 2, 2, 3],
                "amount": [10, 10, 20, 20, 20, 30],
            }
        )

        summary = summarize_duplicates_for_quality(df)
        effect = summarize_duplicate_handling_effect(
            df,
            {"method": "drop_selected_rows", "row_indices": [1]},
        )

        self.assertEqual(summary["duplicate_group_rows"], 5)
        self.assertEqual(summary["duplicate_count"], 3)
        self.assertEqual(effect["duplicate_group_rows"], 5)
        self.assertEqual(effect["removed_rows"], 1)
        self.assertEqual(effect["after_duplicate_group_rows"], 3)

    def test_cleaning_plan_preview_applies_missing_then_duplicate_plan(self):
        df = pd.DataFrame(
            {
                "order_id": [1, 1, 2],
                "amount": [None, None, 20],
            },
            index=[10, 11, 12],
        )
        missing_plan = [{"column": "amount", "method": "zero"}]
        duplicate_plan = {"method": "drop_all_duplicates"}

        preview, steps = apply_cleaning_plan_preview(df, missing_plan, duplicate_plan)

        self.assertEqual(len(preview), 2)
        self.assertEqual(int(preview["amount"].isna().sum()), 0)
        self.assertEqual([step["type"] for step in steps], ["fill_missing", "drop_duplicates"])

    def test_duplicate_plan_replaces_conflicting_plan(self):
        plan = upsert_duplicate_handling_plan(None, {"method": "drop_all_duplicates"})
        plan = upsert_duplicate_handling_plan(
            plan,
            {"method": "drop_selected_rows", "row_indices": [2, 2, 3]},
        )

        self.assertEqual(plan["method"], "drop_selected_rows")
        self.assertEqual(plan["row_indices"], [2, 3])
        self.assertNotIn("drop_all_duplicates", plan)

    def test_iqr_outlier_detection_and_drop(self):
        self._set_csv_as_current(
            b"id,amount,region\n1,10,East\n2,11,East\n3,12,West\n4,1000,West\n"
        )
        df = load_current_analysis_dataframe(self.project["project_id"])

        outliers = summarize_iqr_outliers_for_quality(df)
        self.assertIn("Q1", outliers.columns)
        self.assertIn("Q3", outliers.columns)
        self.assertIn("IQR", outliers.columns)
        amount_outliers = outliers.loc[outliers["字段名"] == "amount"].iloc[0]
        cleaned, _ = apply_quality_operations(
            df,
            [{"type": "outlier", "column": "amount", "method": "drop_rows"}],
        )

        self.assertEqual(int(amount_outliers["异常值数量"]), 1)
        self.assertEqual(len(cleaned), 3)
        self.assertNotIn(1000, cleaned["amount"].tolist())

    def test_iqr_numeric_measure_columns_exclude_identifier_like_fields(self):
        df = pd.DataFrame(
            {
                "销售工号": [1000000001, 1000000002, 1000000003, 1000000004],
                "订单号": [9001, 9002, 9003, 9004],
                "用户ID": [1, 2, 3, 4],
                "mobile": [13800000001, 13800000002, 13800000003, 13800000004],
                "销售额": [10, 11, 12, 1000],
                "数量": [1, 2, 3, 4],
                "amount": [20, 21, 22, 2000],
                "region": ["East", "East", "West", "West"],
            }
        )

        measure_columns = get_iqr_numeric_measure_columns(df)
        outliers = summarize_iqr_outliers_for_quality(df)

        self.assertNotIn("销售工号", measure_columns)
        self.assertNotIn("订单号", measure_columns)
        self.assertNotIn("用户ID", measure_columns)
        self.assertNotIn("mobile", measure_columns)
        self.assertIn("销售额", measure_columns)
        self.assertIn("数量", measure_columns)
        self.assertIn("amount", measure_columns)
        self.assertEqual(set(outliers["字段名"]), {"销售额", "数量", "amount"})

    def test_identifier_detection_excludes_dates_and_true_measures(self):
        df = pd.DataFrame(
            {
                "销售工号": [1001, 1002, 1003, 1004],
                "customer_id": ["C1", "C2", "C3", "C4"],
                "交易日期": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
                "销售额": [10, 20, 30, 40],
                "amount": [100, 200, 300, 400],
                "region": ["East", "West", "North", "South"],
            }
        )

        identifiers = detect_identifier_columns(df)
        identifier_summary = summarize_identifier_columns(df, identifiers)

        self.assertIn("销售工号", identifiers)
        self.assertIn("customer_id", identifiers)
        self.assertIn("region", identifiers)
        self.assertNotIn("交易日期", identifiers)
        self.assertNotIn("销售额", identifiers)
        self.assertNotIn("amount", identifiers)
        self.assertIn("识别原因", identifier_summary.columns)

    def test_final_id_columns_include_manual_ids(self):
        df = pd.DataFrame(
            {
                "销售工号": [1001, 1002, 1003],
                "订单号": [2001, 2002, 2003],
                "amount": [10, 20, 30],
            }
        )

        final_ids = get_final_id_columns(
            df,
            auto_id_columns=["销售工号"],
            manual_id_columns=["订单号"],
            manual_non_id_columns=[],
        )

        self.assertEqual(final_ids, ["销售工号", "订单号"])

    def test_final_id_columns_respect_manual_cancel(self):
        df = pd.DataFrame({"销售工号": [1001, 1002], "amount": [10, 20]})

        final_ids = get_final_id_columns(
            df,
            auto_id_columns=["销售工号"],
            manual_id_columns=[],
            manual_non_id_columns=["销售工号"],
        )

        self.assertNotIn("销售工号", final_ids)

    def test_manual_cancel_wins_if_override_state_conflicts(self):
        df = pd.DataFrame({"销售工号": [1001, 1002], "amount": [10, 20]})

        final_ids = get_final_id_columns(
            df,
            auto_id_columns=["销售工号"],
            manual_id_columns=["销售工号"],
            manual_non_id_columns=["销售工号"],
        )

        self.assertNotIn("销售工号", final_ids)

    def test_id_override_conflict_resolution(self):
        df = pd.DataFrame({"销售工号": [1001, 1002], "amount": [10, 20]})

        manual_ids, manual_non_ids = update_id_override_state(
            df,
            manual_id_columns=[],
            manual_non_id_columns=["销售工号"],
            column="销售工号",
            action="mark_id",
        )
        self.assertIn("销售工号", manual_ids)
        self.assertNotIn("销售工号", manual_non_ids)

        manual_ids, manual_non_ids = update_id_override_state(
            df,
            manual_id_columns=manual_ids,
            manual_non_id_columns=manual_non_ids,
            column="销售工号",
            action="mark_non_id",
        )
        self.assertNotIn("销售工号", manual_ids)
        self.assertIn("销售工号", manual_non_ids)

    def test_reset_id_override_state_clears_manual_lists(self):
        manual_ids, manual_non_ids = reset_id_override_state()

        self.assertEqual(manual_ids, [])
        self.assertEqual(manual_non_ids, [])

    def test_business_measures_and_dates_not_auto_id_by_uniqueness(self):
        df = pd.DataFrame(
            {
                "成交金额": [101.0, 202.0, 303.0, 404.0],
                "客单价": [11.0, 22.0, 33.0, 44.0],
                "amount": [100.0, 200.0, 300.0, 400.0],
                "price": [1.0, 2.0, 3.0, 4.0],
                "成交日期": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
                "employee_id": [1, 2, 3, 4],
            }
        )

        identifiers = detect_identifier_columns(df)

        self.assertIn("employee_id", identifiers)
        self.assertNotIn("成交金额", identifiers)
        self.assertNotIn("客单价", identifiers)
        self.assertNotIn("amount", identifiers)
        self.assertNotIn("price", identifiers)
        self.assertNotIn("成交日期", identifiers)

    def test_outlier_numeric_filter_excludes_final_id_columns(self):
        df = pd.DataFrame(
            {
                "销售工号": [1001, 1002, 1003, 1004],
                "amount": [10, 11, 12, 1000],
                "price": [1, 2, 3, 4],
            }
        )
        final_ids = get_final_id_columns(
            df,
            auto_id_columns=[],
            manual_id_columns=["price"],
            manual_non_id_columns=["销售工号"],
        )

        numeric_columns = get_iqr_numeric_measure_columns(df, final_ids)

        self.assertNotIn("price", numeric_columns)
        self.assertIn("amount", numeric_columns)

    def test_outlier_numeric_filter_uses_final_id_columns_after_manual_cancel(self):
        df = pd.DataFrame(
            {
                "amount": [10, 11, 12, 1000],
                "price": [1, 2, 3, 4],
            }
        )
        final_ids = get_final_id_columns(
            df,
            auto_id_columns=["amount"],
            manual_id_columns=[],
            manual_non_id_columns=["amount"],
        )

        numeric_columns = get_iqr_numeric_measure_columns(df, final_ids)

        self.assertNotIn("amount", final_ids)
        self.assertIn("amount", numeric_columns)

    def test_quality_overview_and_repair_suggestions(self):
        df = pd.DataFrame(
            {
                "订单号": [1, 2, 3, 3, 5],
                "amount": [10, 11, 12, 12, 1000],
                "region": ["East", "East", "West", "West", "North"],
                "mostly_missing": [None, None, None, None, "x"],
                "Unnamed: 0": [1, 2, 3, 3, 5],
            }
        )

        identifiers = detect_identifier_columns(df)
        invalid_columns = detect_invalid_columns(df)
        outliers = summarize_iqr_outliers_for_quality(df, identifiers)
        overview = summarize_quality_overview(df, identifiers, invalid_columns, outliers)
        suggestions = generate_data_repair_suggestions_for_quality(
            df,
            identifiers,
            invalid_columns,
            outliers,
        )

        self.assertGreaterEqual(overview["missing_values"], 4)
        self.assertGreaterEqual(overview["duplicate_rows"], 1)
        self.assertGreaterEqual(overview["identifier_column_count"], 1)
        self.assertGreaterEqual(overview["suspicious_column_count"], 1)
        self.assertGreaterEqual(overview["outlier_count"], 1)
        self.assertIn("缺失率过高", set(suggestions["问题类型"]))
        self.assertIn("重复行", set(suggestions["问题类型"]))
        self.assertIn("疑似 ID 字段", set(suggestions["问题类型"]))
        self.assertIn("检测到异常值", set(suggestions["问题类型"]))
        self.assertIn("疑似无效字段", set(suggestions["问题类型"]))

    def test_quality_detection_reads_appended_current_dataset(self):
        saved = save_project_data_files(
            self.project["project_id"],
            [
                UploadedFileStub(
                    "north.csv",
                    b"order_id,amount,region\n1,10,North\n2,11,North\n",
                ),
                UploadedFileStub(
                    "south.csv",
                    b"order_id,amount,region\n3,12,South\n4,1000,South\n",
                ),
            ],
        )
        sources = list_append_sources(self.project["project_id"])
        source_ids = [source["source_id"] for source in sources]
        build_appended_dataset(self.project["project_id"], source_ids)
        set_appended_dataset_as_current(self.project["project_id"])

        current = get_current_analysis_dataset(self.project["project_id"])
        df = load_current_analysis_dataframe(self.project["project_id"])
        identifiers = detect_identifier_columns(df)
        outliers = summarize_iqr_outliers_for_quality(df, identifiers)

        self.assertEqual(current["dataset_type"], "appended")
        self.assertEqual(len(df), 4)
        self.assertIn("order_id", identifiers)
        self.assertTrue(any(outliers["字段名"] == "amount"))

    def test_cleaned_dataset_registration_and_set_current(self):
        self._set_csv_as_current()

        metadata = create_cleaned_dataset(
            self.project["project_id"],
            [
                {"type": "fill_missing", "column": "amount", "method": "zero"},
                {"type": "drop_duplicates"},
            ],
        )
        datasets = list_project_datasets(self.project["project_id"])
        set_cleaned_dataset_as_current(self.project["project_id"])
        current = get_current_analysis_dataset(self.project["project_id"])
        current_df = load_current_analysis_dataframe(self.project["project_id"])

        self.assertEqual(metadata["dataset_name"], "cleaned_dataset.csv")
        self.assertEqual(metadata["source_dataset_name"], "quality.csv")
        self.assertEqual(len(metadata["missing_value_actions"]), 1)
        self.assertEqual(len(metadata["duplicate_actions"]), 1)
        self.assertEqual(metadata["outlier_actions"], [])
        self.assertTrue(
            (
                project_workspace.get_project_path(self.project["project_id"])
                / "analysis"
                / "cleaned_dataset.csv"
            ).is_file()
        )
        self.assertIn("cleaned_dataset", {item["dataset_id"] for item in datasets})
        self.assertEqual(current["dataset_type"], "cleaned")
        self.assertEqual(current["dataset_name"], "cleaned_dataset.csv")
        self.assertEqual(len(current_df), 3)


if __name__ == "__main__":
    unittest.main()
