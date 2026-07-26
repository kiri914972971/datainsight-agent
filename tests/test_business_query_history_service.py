import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from src import project_workspace
from src.business_query_history_service import (
    build_saved_business_query_report_context,
    dataframe_from_saved_query,
    delete_saved_query,
    get_saved_query,
    get_saved_queries_for_dataset,
    get_saved_queries_path,
    load_saved_queries,
    save_query,
)


class BusinessQueryHistoryServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "projects"
        self.root_patch = patch.object(
            project_workspace,
            "PROJECT_ROOT",
            self.project_root,
        )
        self.root_patch.start()
        self.project = project_workspace.create_project("Business Query History")
        self.project_id = self.project["project_id"]
        self.result = pd.DataFrame(
            {
                "排名": [1, 2],
                "小组": ["甲组", "乙组"],
                "成交金额": [300.0, 200.0],
            }
        )
        self.query_plan = {
            "intent": "ranking",
            "dimension": "小组",
            "metric": "成交金额",
            "limit": 2,
            "filters": [],
        }

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def _save(self, *, question="成交金额最高的前2个小组", dataset_key="dataset-a"):
        return save_query(
            self.project_id,
            question,
            self.query_plan,
            self.result,
            "甲组成交金额排名第一。",
            dataset_key,
            f"{dataset_key}.csv",
        )

    def test_missing_history_file_returns_empty_list(self):
        self.assertEqual(load_saved_queries(self.project_id), [])

    def test_save_creates_file_and_can_be_reloaded(self):
        saved = self._save()
        records = load_saved_queries(self.project_id)

        self.assertTrue(get_saved_queries_path(self.project_id).is_file())
        self.assertEqual(records[0]["id"], saved["id"])

    def test_saved_metadata_and_row_count_are_preserved(self):
        self._save(question="测试问题", dataset_key="stable-dataset-key")
        record = load_saved_queries(self.project_id)[0]

        self.assertEqual(record["question"], "测试问题")
        self.assertEqual(record["query_plan"], self.query_plan)
        self.assertEqual(record["dataset_key"], "stable-dataset-key")
        self.assertEqual(record["result_row_count"], 2)

    def test_identifier_strings_remain_strings_after_reload(self):
        identifier = "100000003000000001"
        result = pd.DataFrame({"排名": [1], "销售工号": [identifier], "订单数": [5]})
        plan = {**self.query_plan, "dimension": "销售工号", "metric": "订单数"}
        save_query(
            self.project_id,
            "前1个销售工号",
            plan,
            result,
            "测试解读",
            "dataset-a",
            "dataset-a.csv",
            is_identifier_dimension=True,
        )

        loaded = dataframe_from_saved_query(load_saved_queries(self.project_id)[0])

        self.assertEqual(loaded.loc[0, "销售工号"], identifier)
        self.assertIsInstance(loaded.loc[0, "销售工号"], str)

    def test_numpy_timestamp_nan_and_none_are_json_safe(self):
        result = pd.DataFrame(
            {
                "数值": pd.Series([np.int64(7), np.float64(np.nan)], dtype=object),
                "时间": [pd.Timestamp("2026-07-17 08:30:00"), pd.NaT],
                "备注": [None, "完成"],
            }
        )
        plan = {**self.query_plan, "limit": np.int64(2)}
        save_query(
            self.project_id,
            "序列化测试",
            plan,
            result,
            "测试解读",
            "dataset-a",
            "dataset-a.csv",
        )

        payload = json.loads(
            get_saved_queries_path(self.project_id).read_text(encoding="utf-8")
        )
        record = payload["records"][0]

        self.assertEqual(record["query_plan"]["limit"], 2)
        self.assertEqual(record["result_rows"][0]["数值"], 7)
        self.assertEqual(record["result_rows"][0]["时间"], "2026-07-17T08:30:00")
        self.assertIsNone(record["result_rows"][1]["数值"])
        self.assertIsNone(record["result_rows"][1]["时间"])
        self.assertIsNone(record["result_rows"][0]["备注"])

    def test_delete_removes_only_selected_record(self):
        first = self._save(question="第一个问题")
        second = self._save(question="第二个问题")

        self.assertTrue(delete_saved_query(self.project_id, first["id"]))

        records = load_saved_queries(self.project_id)
        self.assertEqual([record["id"] for record in records], [second["id"]])

    def test_delete_missing_id_is_safe(self):
        self._save()

        self.assertFalse(delete_saved_query(self.project_id, "missing-id"))
        self.assertEqual(len(load_saved_queries(self.project_id)), 1)

    def test_get_saved_query_returns_selected_record(self):
        first = self._save(question="第一个问题")
        self._save(question="第二个问题")

        selected = get_saved_query(self.project_id, first["id"])

        self.assertEqual(selected["question"], "第一个问题")

    def test_same_project_can_store_multiple_records(self):
        self._save(question="问题一")
        self._save(question="问题二")
        self._save(question="问题三")

        self.assertEqual(len(load_saved_queries(self.project_id)), 3)

    def test_records_from_different_datasets_coexist(self):
        self._save(dataset_key="dataset-a")
        self._save(dataset_key="dataset-b")

        dataset_keys = {
            record["dataset_key"] for record in load_saved_queries(self.project_id)
        }
        self.assertEqual(dataset_keys, {"dataset-a", "dataset-b"})

    def test_dataset_filter_returns_only_exact_dataset_key(self):
        first = self._save(question="A 数据集问题", dataset_key="dataset-a")
        self._save(question="B 数据集问题", dataset_key="dataset-b")

        records = get_saved_queries_for_dataset(self.project_id, "dataset-a")

        self.assertEqual([record["id"] for record in records], [first["id"]])

    def test_empty_dataset_key_returns_empty_list(self):
        self._save(dataset_key="dataset-a")

        self.assertEqual(get_saved_queries_for_dataset(self.project_id, ""), [])
        self.assertEqual(get_saved_queries_for_dataset(self.project_id, None), [])

    def test_dataset_records_are_sorted_by_saved_time_ascending(self):
        first = self._save(question="问题一", dataset_key="dataset-a")
        second = self._save(question="问题二", dataset_key="dataset-a")
        third = self._save(question="问题三", dataset_key="dataset-a")

        records = get_saved_queries_for_dataset(self.project_id, "dataset-a")

        self.assertEqual(
            [record["id"] for record in records],
            [first["id"], second["id"], third["id"]],
        )

    def test_deleted_record_is_not_returned_for_dataset(self):
        deleted = self._save(question="删除问题", dataset_key="dataset-a")
        kept = self._save(question="保留问题", dataset_key="dataset-a")
        delete_saved_query(self.project_id, deleted["id"])

        records = get_saved_queries_for_dataset(self.project_id, "dataset-a")

        self.assertEqual([record["id"] for record in records], [kept["id"]])

    def test_report_context_contains_all_saved_snapshots(self):
        self._save(question="问题一", dataset_key="dataset-a")
        self._save(question="问题二", dataset_key="dataset-a")

        records = get_saved_queries_for_dataset(self.project_id, "dataset-a")
        context = build_saved_business_query_report_context(records)

        self.assertEqual([item["question"] for item in context], ["问题一", "问题二"])
        self.assertTrue(all(isinstance(item["result_df"], pd.DataFrame) for item in context))
        self.assertEqual(context[0]["result_df"].to_dict("records"), self.result.to_dict("records"))

    def test_report_context_preserves_identifier_string(self):
        identifier = "100000003000000001"
        result = pd.DataFrame({"排名": [1], "销售工号": [identifier], "订单数": [5]})
        save_query(
            self.project_id,
            "销售工号排名",
            {"dimension": "销售工号", "metric": "订单数", "limit": 1},
            result,
            "测试解读",
            "dataset-a",
            "dataset-a.csv",
            is_identifier_dimension=True,
        )

        context = build_saved_business_query_report_context(
            get_saved_queries_for_dataset(self.project_id, "dataset-a")
        )

        self.assertEqual(context[0]["result_df"].loc[0, "销售工号"], identifier)

    def test_missing_history_returns_no_dataset_records(self):
        self.assertEqual(
            get_saved_queries_for_dataset(self.project_id, "dataset-a"),
            [],
        )

    def test_loading_without_save_does_not_create_history_file(self):
        load_saved_queries(self.project_id)

        self.assertFalse(get_saved_queries_path(self.project_id).exists())

    def test_malformed_history_file_returns_empty_list(self):
        history_path = get_saved_queries_path(self.project_id)
        history_path.write_text("not valid json", encoding="utf-8")

        self.assertEqual(load_saved_queries(self.project_id), [])


if __name__ == "__main__":
    unittest.main()
