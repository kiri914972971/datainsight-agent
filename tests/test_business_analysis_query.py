import unittest
from unittest.mock import patch

import pandas as pd

from src.business_analysis import (
    detect_multiple_business_questions,
    execute_business_query,
    parse_business_question,
)


class BusinessAnalysisQueryTests(unittest.TestCase):
    def setUp(self):
        self.dataframe = pd.DataFrame(
            {
                "小组": ["甲组", "乙组", "丙组", "丁组"],
                "成交金额": [100, 400, 300, 200],
                "订单号": ["A-1", "B-1", "C-1", "D-1"],
                "成交日期": pd.to_datetime(
                    ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]
                ),
            }
        )
        self.fields = {
            "date_column": "成交日期",
            "amount_column": "成交金额",
            "order_id_column": "订单号",
            "customer_id_column": None,
            "customer_count_column": None,
            "unit_price_column": None,
            "dimensions": ["小组"],
            "numeric_metrics": ["成交金额"],
        }

    def _ranking_query(self, limit):
        return {
            "intent": "ranking",
            "dimension": "小组",
            "metric": "成交金额",
            "aggregation": "sum",
            "limit": limit,
            "filters": [],
        }

    def test_parse_numeric_top_n(self):
        query = parse_business_question(
            "成交金额最高的前5个小组",
            ["小组"],
            ["成交金额"],
        )

        self.assertEqual(query["limit"], 5)

    def test_parse_chinese_top_n(self):
        query = parse_business_question(
            "成交金额最高的前五个小组",
            ["小组"],
            ["成交金额"],
        )

        self.assertEqual(query["limit"], 5)

    def test_parse_ranking_without_explicit_limit(self):
        query = parse_business_question(
            "各小组成交金额排名",
            ["小组"],
            ["成交金额"],
        )

        self.assertIsNone(query["limit"])

    def test_ai_parse_preserves_null_limit(self):
        response = (
            '{"intent":"ranking","dimension":"小组","metric":"成交金额",'
            '"aggregation":"sum","limit":null,"filters":[]}'
        )
        with (
            patch("src.business_analysis._request_completion", return_value={}),
            patch("src.business_analysis._extract_text", return_value=response),
        ):
            query = parse_business_question(
                "各小组成交金额排名",
                ["小组"],
                ["成交金额"],
                api_key="test-key",
            )

        self.assertIsNone(query["limit"])

    def test_execute_with_limit_returns_only_requested_rows(self):
        result = execute_business_query(
            self.dataframe,
            self._ranking_query(2),
            self.fields,
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(result["小组"].tolist(), ["乙组", "丙组"])
        self.assertEqual(result["排名"].tolist(), [1, 2])

    def test_execute_without_limit_returns_all_groups(self):
        result = execute_business_query(
            self.dataframe,
            self._ranking_query(None),
            self.fields,
        )

        self.assertEqual(len(result), 4)

    def test_execute_without_limit_stays_sorted_and_ranked(self):
        result = execute_business_query(
            self.dataframe,
            self._ranking_query(None),
            self.fields,
        )

        self.assertEqual(result["成交金额"].tolist(), [400.0, 300.0, 200.0, 100.0])
        self.assertEqual(result["排名"].tolist(), [1, 2, 3, 4])

    def test_growth_ranking_without_limit_returns_all_groups(self):
        growth_dataframe = pd.DataFrame(
            {
                "小组": [
                    "甲组",
                    "甲组",
                    "乙组",
                    "乙组",
                    "丙组",
                    "丙组",
                    "丁组",
                    "丁组",
                    "戊组",
                    "戊组",
                    "己组",
                    "己组",
                ],
                "成交金额": [
                    100,
                    200,
                    100,
                    150,
                    100,
                    140,
                    100,
                    130,
                    100,
                    120,
                    100,
                    110,
                ],
                "订单号": [f"ORDER-{index}" for index in range(12)],
                "成交日期": pd.to_datetime(
                    ["2026-01-01", "2026-02-01"] * 6
                ),
            }
        )
        query = {
            **self._ranking_query(None),
            "intent": "growth_ranking",
        }

        result = execute_business_query(growth_dataframe, query, self.fields)

        self.assertEqual(len(result), 6)
        self.assertEqual(result["小组"].tolist(), ["甲组", "乙组", "丙组", "丁组", "戊组", "己组"])
        self.assertEqual(result["排名"].tolist(), [1, 2, 3, 4, 5, 6])


class MultipleBusinessQuestionDetectionTests(unittest.TestCase):
    def test_two_question_sentences_are_multiple(self):
        self.assertTrue(
            detect_multiple_business_questions(
                "哪个小组成交金额最高？哪个销售人员订单数最多？"
            )
        )

    def test_two_semicolon_rankings_are_multiple(self):
        self.assertTrue(
            detect_multiple_business_questions(
                "小组成交金额排名；销售人员订单数排名"
            )
        )

    def test_separate_analysis_targets_are_multiple(self):
        self.assertTrue(
            detect_multiple_business_questions(
                "请分别分析小组成交金额和销售人员订单数"
            )
        )

    def test_simultaneous_independent_targets_are_multiple(self):
        self.assertTrue(
            detect_multiple_business_questions(
                "成交金额最高的前五个小组是哪些，同时订单数最多的前五个销售人员是谁"
            )
        )

    def test_rankings_joined_by_as_well_as_are_multiple(self):
        self.assertTrue(
            detect_multiple_business_questions(
                "小组成交金额排名，以及销售人员订单数排名"
            )
        )

    def test_group_comparison_with_and_is_single(self):
        self.assertFalse(
            detect_multiple_business_questions("A组和B组的成交金额对比")
        )

    def test_two_metrics_with_and_are_single(self):
        self.assertFalse(
            detect_multiple_business_questions("各地区的订单数和成交金额是多少")
        )

    def test_two_years_with_and_are_single(self):
        self.assertFalse(
            detect_multiple_business_questions("2025年和2026年的销售趋势对比")
        )


if __name__ == "__main__":
    unittest.main()
