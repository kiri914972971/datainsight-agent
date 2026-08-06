import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src import project_workspace
from src.engines.kpi_engine import (
    AGGREGATION_HELP_TEXTS,
    NO_SOURCE_FIELD_LABEL,
    SUPPORTED_AGGREGATIONS,
    calculate_basic_kpi,
    generate_kpi_candidates,
    get_kpi_source_field_options,
    get_kpi_source_field_type,
    missing_entity_id_candidate_names,
    normalize_kpi_definition,
    resolve_kpi_source_selection,
    validate_kpi_definition,
)
from src.exploration import build_exploration_field_roles
from src.services.field_mapping_service import save_field_mappings
from src.services.kpi_service import (
    add_saved_kpi_definition,
    list_usable_kpis,
    save_kpi_definitions,
)


def _definition(**overrides):
    result = {
        "kpi_name": "测试指标",
        "aggregation": "count_distinct",
        "source_field": "订单ID",
        "field_type": "id",
        "category": "核心指标",
        "enabled": True,
        "created_by": "user",
        "lifecycle_status": "saved",
    }
    result.update(overrides)
    return result


class KpiAggregationDefinitionTests(unittest.TestCase):
    def test_count_help_text_is_dynamic_and_exact(self):
        self.assertEqual(
            AGGREGATION_HELP_TEXTS.get("count"),
            "非空计数统计来源字段中的非空记录，不进行去重。",
        )
        self.assertNotIn("记录行数", AGGREGATION_HELP_TEXTS["count"])
        self.assertNotIn("去重计数", AGGREGATION_HELP_TEXTS["count"])

    def test_count_rows_help_text_is_dynamic_and_exact(self):
        self.assertEqual(
            AGGREGATION_HELP_TEXTS.get("count_rows"),
            "记录行数统计当前分析数据集的总行数，不等同于订单数；该规则无需来源字段。",
        )
        self.assertNotIn("非空计数", AGGREGATION_HELP_TEXTS["count_rows"])
        self.assertNotIn("去重计数", AGGREGATION_HELP_TEXTS["count_rows"])

    def test_count_distinct_help_text_is_dynamic_and_exact(self):
        self.assertEqual(
            AGGREGATION_HELP_TEXTS.get("count_distinct"),
            "去重计数统计来源字段中的非空唯一值数量，适合订单 ID、客户 ID、人员编号等字段。",
        )
        self.assertNotIn("非空计数", AGGREGATION_HELP_TEXTS["count_distinct"])
        self.assertNotIn("记录行数", AGGREGATION_HELP_TEXTS["count_distinct"])

    def test_non_count_aggregations_have_no_count_help_text(self):
        for aggregation in ("sum", "avg", "max", "min", "reserved"):
            self.assertIsNone(AGGREGATION_HELP_TEXTS.get(aggregation))

    def test_switching_aggregation_changes_help_lookup_immediately(self):
        sequence = [
            AGGREGATION_HELP_TEXTS.get(aggregation)
            for aggregation in ("count", "max", "count_rows", "count_distinct")
        ]

        self.assertIsNotNone(sequence[0])
        self.assertIsNone(sequence[1])
        self.assertNotEqual(sequence[0], sequence[2])
        self.assertNotEqual(sequence[2], sequence[3])

    def test_supported_aggregations_include_new_count_types(self):
        self.assertIn("count_rows", SUPPORTED_AGGREGATIONS)
        self.assertIn("count_distinct", SUPPORTED_AGGREGATIONS)

    def test_normalize_preserves_new_aggregations(self):
        rows = normalize_kpi_definition(
            _definition(
                aggregation="count_rows",
                source_field="",
                field_type="row",
            )
        )
        distinct = normalize_kpi_definition(_definition())

        self.assertEqual(rows["aggregation"], "count_rows")
        self.assertEqual(rows["validation_status"], "valid")
        self.assertEqual(distinct["aggregation"], "count_distinct")
        self.assertEqual(distinct["validation_status"], "valid")

    def test_count_rows_requires_no_source_and_accepts_supported_types(self):
        for field_type in ("row", "dataset", "custom"):
            result = validate_kpi_definition(
                _definition(
                    aggregation="count_rows",
                    source_field="",
                    field_type=field_type,
                )
            )
            self.assertEqual(result["validation_status"], "valid")

    def test_count_rows_rejects_incompatible_field_type(self):
        result = validate_kpi_definition(
            _definition(
                aggregation="count_rows",
                source_field="",
                field_type="amount",
            )
        )

        self.assertEqual(result["validation_status"], "invalid")

    def test_count_distinct_requires_existing_source_field(self):
        missing_source = validate_kpi_definition(
            _definition(source_field="")
        )
        missing_field = validate_kpi_definition(
            _definition(), available_fields=["其他字段"]
        )

        self.assertEqual(missing_source["validation_status"], "invalid")
        self.assertEqual(missing_field["validation_status"], "invalid")

    def test_count_distinct_accepts_entity_custom_and_numeric_types(self):
        for field_type in (
            "id",
            "date",
            "categorical",
            "person",
            "product",
            "region",
            "custom",
            "numeric",
            "amount",
        ):
            result = validate_kpi_definition(
                _definition(field_type=field_type)
            )
            self.assertEqual(result["validation_status"], "valid")

    def test_count_still_validates_as_non_distinct_field_count(self):
        result = validate_kpi_definition(
            _definition(aggregation="count")
        )

        self.assertEqual(result["validation_status"], "valid")

    def test_reserved_remains_pending(self):
        result = validate_kpi_definition(
            _definition(
                aggregation="reserved",
                source_field="",
                field_type="custom",
            )
        )

        self.assertEqual(result["validation_status"], "pending")


class KpiSourceFieldOptionTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame(
            {
                "成交客户数": [2, 3],
                "成交金额": [100.0, 200.0],
                "客单价": [50.0, 66.7],
                "成交日期": ["2020-04-01", "2020-06-30"],
                "成交年份": [2020, 2020],
                "成交月份": [4, 6],
                "销售工号": [10001, 10002],
                "产品": ["A", "B"],
                "区域": ["华东", "华南"],
            }
        )
        self.mappings = [
            {"column_name": "成交客户数", "confirmed_type": "数量字段"},
            {"column_name": "成交金额", "confirmed_type": "金额字段"},
            {"column_name": "客单价", "confirmed_type": "金额字段"},
            {"column_name": "成交日期", "confirmed_type": "日期字段"},
            {"column_name": "成交年份", "confirmed_type": "日期字段"},
            {"column_name": "成交月份", "confirmed_type": "日期字段"},
            {"column_name": "销售工号", "confirmed_type": "ID字段"},
            {"column_name": "产品", "confirmed_type": "产品字段"},
            {"column_name": "区域", "confirmed_type": "区域字段"},
        ]
        self.roles = build_exploration_field_roles(
            self.df,
            confirmed_type_by_column={
                item["column_name"]: item["confirmed_type"]
                for item in self.mappings
            },
        )
        self.fields = list(self.df.columns)

    def options(self, aggregation):
        return get_kpi_source_field_options(
            aggregation,
            self.fields,
            self.mappings,
            self.roles,
        )

    def test_sum_and_avg_only_return_amount_or_numeric_fields_in_source_order(self):
        expected = ["成交客户数", "成交金额", "客单价"]

        self.assertEqual(self.options("sum"), expected)
        self.assertEqual(self.options("avg"), expected)
        self.assertNotIn("成交年份", self.options("sum"))
        self.assertNotIn("成交月份", self.options("sum"))
        self.assertNotIn(NO_SOURCE_FIELD_LABEL, self.options("sum"))

    def test_max_and_min_include_complete_dates_but_exclude_derived_time(self):
        expected = ["成交客户数", "成交金额", "客单价", "成交日期"]

        self.assertEqual(self.options("max"), expected)
        self.assertEqual(self.options("min"), expected)
        self.assertNotIn("成交年份", self.options("max"))
        self.assertNotIn("成交月份", self.options("min"))

    def test_count_aggregations_return_every_real_field_without_placeholder(self):
        self.assertEqual(self.options("count"), self.fields)
        self.assertEqual(self.options("count_distinct"), self.fields)
        self.assertIn("销售工号", self.options("count_distinct"))
        self.assertIn("成交年份", self.options("count"))
        self.assertNotIn(NO_SOURCE_FIELD_LABEL, self.options("count"))
        self.assertNotIn(NO_SOURCE_FIELD_LABEL, self.options("count_distinct"))

    def test_count_rows_only_returns_placeholder_and_uses_row_type(self):
        self.assertEqual(self.options("count_rows"), [NO_SOURCE_FIELD_LABEL])
        self.assertEqual(
            get_kpi_source_field_type(
                "count_rows", "", self.mappings, self.roles
            ),
            "row",
        )

    def test_field_type_is_derived_from_mapping_and_final_role(self):
        expectations = {
            "成交金额": "amount",
            "成交客户数": "numeric",
            "销售工号": "id",
            "成交日期": "date",
            "产品": "product",
            "区域": "region",
            "成交年份": "custom",
        }

        for field, expected in expectations.items():
            self.assertEqual(
                get_kpi_source_field_type(
                    "count", field, self.mappings, self.roles
                ),
                expected,
            )

    def test_switching_aggregation_replaces_incompatible_old_source(self):
        to_sum = resolve_kpi_source_selection(
            "sum", "销售工号", self.fields, self.mappings, self.roles
        )
        to_rows = resolve_kpi_source_selection(
            "count_rows", "成交金额", self.fields, self.mappings, self.roles
        )
        back_to_sum = resolve_kpi_source_selection(
            "sum",
            to_rows["selected_option"],
            self.fields,
            self.mappings,
            self.roles,
        )

        self.assertEqual(to_sum["selected_option"], "成交客户数")
        self.assertEqual(to_sum["field_type"], "numeric")
        self.assertEqual(to_rows["selected_option"], NO_SOURCE_FIELD_LABEL)
        self.assertEqual(to_rows["source_field"], "")
        self.assertEqual(to_rows["field_type"], "row")
        self.assertEqual(back_to_sum["selected_option"], "成交客户数")

    def test_no_compatible_fields_returns_safe_disabled_state(self):
        category_df = pd.DataFrame({"产品": ["A", "B"]})
        mappings = [{"column_name": "产品", "confirmed_type": "产品字段"}]
        roles = build_exploration_field_roles(
            category_df,
            confirmed_type_by_column={"产品": "产品字段"},
        )

        result = resolve_kpi_source_selection(
            "sum", "产品", ["产品"], mappings, roles
        )

        self.assertEqual(result["options"], [])
        self.assertEqual(result["source_field"], "")
        self.assertFalse(result["has_compatible_fields"])

    def test_option_helpers_do_not_modify_inputs(self):
        original_df = self.df.copy(deep=True)
        original_mappings = copy.deepcopy(self.mappings)
        original_roles = copy.deepcopy(self.roles)

        self.options("sum")
        resolve_kpi_source_selection(
            "count_distinct",
            "销售工号",
            self.fields,
            self.mappings,
            self.roles,
        )

        pd.testing.assert_frame_equal(self.df, original_df)
        self.assertEqual(self.mappings, original_mappings)
        self.assertEqual(self.roles, original_roles)


class BasicKpiExecutionTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame(
            {
                "订单ID": ["A", "A", "B", None, ""],
                "金额": [10.0, 20.0, None, 40.0, 30.0],
            }
        )

    def test_count_rows_returns_total_rows_including_empty_fields(self):
        result = calculate_basic_kpi(
            self.df,
            _definition(
                aggregation="count_rows",
                source_field="",
                field_type="row",
            ),
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["value"], 5)

    def test_count_returns_non_null_count_without_deduplication(self):
        result = calculate_basic_kpi(
            self.df,
            _definition(aggregation="count"),
        )

        self.assertEqual(result["value"], 4)

    def test_count_distinct_excludes_null_but_keeps_blank_string(self):
        result = calculate_basic_kpi(self.df, _definition())

        self.assertEqual(result["value"], 3)

    def test_count_distinct_does_not_modify_dataframe(self):
        original = self.df.copy(deep=True)

        calculate_basic_kpi(self.df, _definition())

        pd.testing.assert_frame_equal(self.df, original)

    def test_sum_avg_max_and_min_use_valid_values(self):
        results = {
            aggregation: calculate_basic_kpi(
                self.df,
                _definition(
                    aggregation=aggregation,
                    source_field="金额",
                    field_type="amount",
                ),
            )["value"]
            for aggregation in ("sum", "avg", "max", "min")
        }

        self.assertEqual(results["sum"], 100.0)
        self.assertEqual(results["avg"], 25.0)
        self.assertEqual(results["max"], 40.0)
        self.assertEqual(results["min"], 10.0)

    def test_missing_field_and_reserved_return_safe_statuses(self):
        missing = calculate_basic_kpi(
            self.df,
            _definition(source_field="不存在字段"),
        )
        reserved = calculate_basic_kpi(
            self.df,
            _definition(aggregation="reserved"),
        )

        self.assertEqual(missing["status"], "missing_field")
        self.assertEqual(reserved["status"], "unsupported")

    def test_empty_dataframe_count_results_are_zero(self):
        empty = self.df.iloc[0:0].copy()

        rows = calculate_basic_kpi(
            empty,
            _definition(
                aggregation="count_rows",
                source_field="",
                field_type="row",
            ),
        )
        distinct = calculate_basic_kpi(empty, _definition())

        self.assertEqual(rows["value"], 0)
        self.assertEqual(distinct["value"], 0)

    def test_execution_result_is_json_serializable(self):
        result = calculate_basic_kpi(self.df, _definition())

        self.assertTrue(json.dumps(result, ensure_ascii=False))


class KpiCountCandidateTests(unittest.TestCase):
    def setUp(self):
        self.mappings = [
            {"column_name": "订单ID", "confirmed_type": "ID字段"},
            {"column_name": "客户ID", "confirmed_type": "ID字段"},
            {"column_name": "销售工号", "confirmed_type": "ID字段"},
        ]

    def test_id_candidates_use_distinct_count_and_clear_names(self):
        by_name = {
            item["kpi_name"]: item
            for item in generate_kpi_candidates(self.mappings)
        }

        self.assertEqual(by_name["订单数"]["aggregation"], "count_distinct")
        self.assertEqual(by_name["客户数"]["aggregation"], "count_distinct")
        self.assertEqual(by_name["销售人员数"]["aggregation"], "count_distinct")
        self.assertNotIn("销售工号数量", by_name)

    def test_exactly_one_record_count_candidate_needs_no_mapping(self):
        candidates = generate_kpi_candidates([])
        record_candidates = [
            item for item in candidates if item["kpi_name"] == "记录数"
        ]

        self.assertEqual(len(record_candidates), 1)
        record = record_candidates[0]
        self.assertEqual(record["aggregation"], "count_rows")
        self.assertEqual(record["source_field"], "")
        self.assertEqual(record["field_type"], "row")
        self.assertIn("不等同于订单数", record["description"])
        self.assertEqual(record["lifecycle_status"], "candidate")
        self.assertFalse(record["enabled"])
        self.assertEqual(record["validation_status"], "pending")

    def test_derived_year_and_month_are_excluded_from_time_candidates(self):
        dataframe = pd.DataFrame(
            {
                "成交日期": ["2020-04-01", "2020-06-30"],
                "成交年份": [2020, 2020],
                "成交月份": [4, 6],
            }
        )
        mappings = [
            {"column_name": column, "confirmed_type": "日期字段"}
            for column in dataframe.columns
        ]

        candidates = generate_kpi_candidates(mappings, dataframe=dataframe)
        time_sources = {
            item["source_field"]
            for item in candidates
            if item["aggregation"] == "reserved"
            and item["kpi_name"] in {"同比", "环比", "增长率"}
        }

        self.assertEqual(time_sources, {"成交日期"})

    def test_business_measure_names_are_not_treated_as_derived_time(self):
        dataframe = pd.DataFrame(
            {
                "年销售额": [100.5, 300.2],
                "月收入": [50.0, 80.0],
                "year_revenue": [1000.0, 1200.0],
                "monthly_sales": [200.0, 250.0],
            }
        )
        mappings = [
            {"column_name": column, "confirmed_type": "日期字段"}
            for column in dataframe.columns
        ]

        candidates = generate_kpi_candidates(mappings, dataframe=dataframe)
        time_sources = {
            item["source_field"]
            for item in candidates
            if item["aggregation"] == "reserved"
        }

        self.assertEqual(time_sources, set(dataframe.columns))

    def test_quantity_field_does_not_become_distinct_id_candidate(self):
        candidates = generate_kpi_candidates(
            [{"column_name": "成交客户数", "confirmed_type": "数量字段"}],
            dataframe=pd.DataFrame({"成交客户数": [2, 3]}),
        )

        self.assertFalse(
            any(
                item["aggregation"] == "count_distinct"
                and item["source_field"] == "成交客户数"
                for item in candidates
            )
        )

    def test_missing_order_or_customer_candidates_are_reported(self):
        without_ids = generate_kpi_candidates(
            [{"column_name": "成交客户数", "confirmed_type": "数量字段"}]
        )
        order_only = generate_kpi_candidates(
            [{"column_name": "订单ID", "confirmed_type": "ID字段"}]
        )
        both = generate_kpi_candidates(self.mappings[:2])

        self.assertEqual(
            missing_entity_id_candidate_names(without_ids),
            ["订单数", "客户数"],
        )
        self.assertEqual(
            missing_entity_id_candidate_names(order_only), ["客户数"]
        )
        self.assertEqual(missing_entity_id_candidate_names(both), [])


class KpiAggregationServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_patch = patch.object(
            project_workspace,
            "PROJECT_ROOT",
            Path(self.temp_dir.name) / "projects",
        )
        self.root_patch.start()
        self.project = project_workspace.create_project("KPI Aggregations")
        save_field_mappings(
            self.project["project_id"],
            [{"column_name": "订单ID", "confirmed_type": "ID字段"}],
        )

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def test_saved_new_count_types_are_valid_enabled_and_usable(self):
        rows = add_saved_kpi_definition(
            self.project["project_id"],
            _definition(
                kpi_name="记录数",
                aggregation="count_rows",
                source_field="",
                field_type="row",
            ),
            available_fields=["订单ID"],
        )
        distinct = add_saved_kpi_definition(
            self.project["project_id"],
            _definition(kpi_name="订单数"),
            available_fields=["订单ID"],
        )

        usable = list_usable_kpis(
            self.project["project_id"], available_fields=["订单ID"]
        )

        self.assertTrue(rows["enabled"])
        self.assertEqual(rows["validation_status"], "valid")
        self.assertTrue(distinct["enabled"])
        self.assertEqual(distinct["validation_status"], "valid")
        self.assertCountEqual(
            [item["kpi_name"] for item in usable], ["记录数", "订单数"]
        )

    def test_available_field_change_only_invalidates_distinct_count(self):
        save_kpi_definitions(
            self.project["project_id"],
            [
                _definition(
                    kpi_name="记录数",
                    aggregation="count_rows",
                    source_field="",
                    field_type="row",
                ),
                _definition(kpi_name="订单数"),
            ],
        )

        usable = list_usable_kpis(
            self.project["project_id"], available_fields=[]
        )

        self.assertEqual([item["kpi_name"] for item in usable], ["记录数"])

    def test_legacy_count_configuration_is_not_migrated(self):
        original = _definition(
            kpi_name="旧订单数",
            aggregation="count",
            enabled=True,
        )
        before = copy.deepcopy(original)

        saved = save_kpi_definitions(self.project["project_id"], [original])

        self.assertEqual(saved[0]["aggregation"], "count")
        self.assertEqual(original, before)


if __name__ == "__main__":
    unittest.main()
