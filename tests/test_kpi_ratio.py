import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src import project_workspace
from src.engines.kpi_engine import (
    SUPPORTED_AGGREGATIONS,
    calculate_basic_kpi,
    calculate_ratio_kpi,
    normalize_kpi_definition,
    validate_kpi_definition,
)
from src.engines.metric_dictionary_engine import generate_metric_candidates_from_kpis
from src.services.field_mapping_service import save_field_mappings
from src.services.kpi_service import (
    delete_kpi_definition,
    list_usable_kpis,
    load_kpi_definitions,
    save_kpi_definitions,
)


def _base_kpi(
    kpi_id,
    aggregation="sum",
    source_field="成交金额",
    field_type="amount",
    enabled=False,
    **overrides,
):
    result = {
        "kpi_id": kpi_id,
        "kpi_name": kpi_id,
        "aggregation": aggregation,
        "source_field": source_field,
        "field_type": field_type,
        "category": "核心指标",
        "description": "基础 KPI",
        "enabled": enabled,
        "created_by": "user",
        "lifecycle_status": "saved",
        "validation_status": "valid",
        "validation_messages": [],
    }
    result.update(overrides)
    return result


def _ratio_kpi(**overrides):
    result = {
        "kpi_id": "ratio-aov",
        "kpi_name": "客单价比率",
        "aggregation": "ratio",
        "source_field": "不应保留",
        "field_type": "amount",
        "numerator_kpi_id": "sales",
        "denominator_kpi_id": "customers",
        "category": "核心指标",
        "description": "销售额除以成交客户数",
        "enabled": True,
        "created_by": "user",
        "lifecycle_status": "saved",
    }
    result.update(overrides)
    return result


class KpiRatioDefinitionTests(unittest.TestCase):
    def setUp(self):
        self.dependencies = {
            "sales": _base_kpi("sales"),
            "customers": _base_kpi(
                "customers",
                source_field="成交客户数",
                field_type="numeric",
            ),
        }

    def test_supported_and_normalized_ratio_structure_is_json_safe(self):
        original = _ratio_kpi()
        before = copy.deepcopy(original)

        normalized = normalize_kpi_definition(
            original,
            kpi_by_id=self.dependencies,
        )

        self.assertIn("ratio", SUPPORTED_AGGREGATIONS)
        self.assertEqual(normalized["aggregation"], "ratio")
        self.assertEqual(normalized["source_field"], "")
        self.assertEqual(normalized["numerator_kpi_id"], "sales")
        self.assertEqual(normalized["denominator_kpi_id"], "customers")
        self.assertEqual(normalized["validation_status"], "valid")
        self.assertTrue(json.dumps(normalized, ensure_ascii=False))
        self.assertEqual(original, before)

    def test_legacy_basic_kpi_gets_safe_empty_dependency_ids(self):
        normalized = normalize_kpi_definition(_base_kpi("sales"))

        self.assertEqual(normalized["numerator_kpi_id"], "")
        self.assertEqual(normalized["denominator_kpi_id"], "")
        self.assertEqual(normalized["source_field"], "成交金额")
        self.assertEqual(normalized["validation_status"], "valid")

    def test_candidate_ratio_is_pending_even_before_dependencies_are_selected(self):
        normalized = normalize_kpi_definition(
            _ratio_kpi(
                lifecycle_status="candidate",
                created_by="auto",
                numerator_kpi_id="",
                denominator_kpi_id="",
            )
        )

        self.assertEqual(normalized["validation_status"], "pending")
        self.assertFalse(normalized["enabled"])

    def test_saved_ratio_requires_both_dependency_ids(self):
        missing_numerator = validate_kpi_definition(
            _ratio_kpi(numerator_kpi_id="")
        )
        missing_denominator = validate_kpi_definition(
            _ratio_kpi(denominator_kpi_id="")
        )

        self.assertEqual(missing_numerator["validation_status"], "invalid")
        self.assertIn("分子", "".join(missing_numerator["validation_messages"]))
        self.assertEqual(missing_denominator["validation_status"], "invalid")
        self.assertIn("分母", "".join(missing_denominator["validation_messages"]))

    def test_missing_or_self_referencing_dependencies_are_invalid(self):
        missing_numerator = validate_kpi_definition(
            _ratio_kpi(numerator_kpi_id="missing"),
            kpi_by_id=self.dependencies,
        )
        missing_denominator = validate_kpi_definition(
            _ratio_kpi(denominator_kpi_id="missing"),
            kpi_by_id=self.dependencies,
        )
        same_dependency = validate_kpi_definition(
            _ratio_kpi(denominator_kpi_id="sales"),
            kpi_by_id=self.dependencies,
        )
        self_numerator = validate_kpi_definition(
            _ratio_kpi(numerator_kpi_id="ratio-aov"),
            kpi_by_id=self.dependencies,
        )
        self_denominator = validate_kpi_definition(
            _ratio_kpi(denominator_kpi_id="ratio-aov"),
            kpi_by_id=self.dependencies,
        )

        for result in (
            missing_numerator,
            missing_denominator,
            same_dependency,
            self_numerator,
            self_denominator,
        ):
            self.assertEqual(result["validation_status"], "invalid")

    def test_candidate_invalid_reserved_and_nested_dependencies_are_rejected(self):
        cases = {
            "candidate": _base_kpi("customers", lifecycle_status="candidate"),
            "invalid": _base_kpi("customers", validation_status="invalid"),
            "reserved": _base_kpi("customers", aggregation="reserved"),
            "ratio": _base_kpi("customers", aggregation="ratio"),
        }

        for dependency in cases.values():
            dependencies = {**self.dependencies, "customers": dependency}
            result = validate_kpi_definition(
                _ratio_kpi(),
                kpi_by_id=dependencies,
            )
            self.assertEqual(result["validation_status"], "invalid")

    def test_two_saved_valid_disabled_dependencies_are_allowed(self):
        result = validate_kpi_definition(
            _ratio_kpi(enabled=False),
            kpi_by_id=self.dependencies,
        )

        self.assertEqual(result["validation_status"], "valid")


class KpiRatioExecutionTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame(
            {
                "成交金额": [100.0, 200.0],
                "成交客户数": [2, 3],
                "订单ID": ["A", "A"],
                "零值": [0, 0],
            }
        )
        self.sales = _base_kpi("sales")

    def calculate(self, denominator):
        return calculate_ratio_kpi(
            self.df,
            _ratio_kpi(denominator_kpi_id=denominator["kpi_id"]),
            {"sales": self.sales, denominator["kpi_id"]: denominator},
        )

    def test_sum_divided_by_sum_count_distinct_and_count_rows(self):
        sum_result = self.calculate(
            _base_kpi(
                "customers",
                source_field="成交客户数",
                field_type="numeric",
            )
        )
        distinct_result = self.calculate(
            _base_kpi(
                "orders",
                aggregation="count_distinct",
                source_field="订单ID",
                field_type="id",
            )
        )
        rows_result = self.calculate(
            _base_kpi(
                "rows",
                aggregation="count_rows",
                source_field="",
                field_type="row",
            )
        )

        self.assertEqual(sum_result["value"], 60.0)
        self.assertEqual(distinct_result["value"], 300.0)
        self.assertEqual(rows_result["value"], 150.0)
        self.assertEqual(sum_result["numerator_value"], 300.0)
        self.assertEqual(sum_result["denominator_value"], 5)

    def test_zero_denominator_returns_none_without_infinity(self):
        result = self.calculate(
            _base_kpi(
                "zero",
                source_field="零值",
                field_type="numeric",
            )
        )

        self.assertEqual(result["status"], "zero_denominator")
        self.assertIsNone(result["value"])
        self.assertIn("分母指标当前值为 0", result["message"])
        self.assertNotIn("Infinity", json.dumps(result, ensure_ascii=False))

    def test_non_finite_dependency_value_is_not_returned_as_infinity(self):
        dataframe = self.df.copy(deep=True)
        dataframe["无限值"] = [float("inf"), 0.0]
        denominator = _base_kpi(
            "infinite",
            source_field="无限值",
            field_type="numeric",
        )

        result = calculate_ratio_kpi(
            dataframe,
            _ratio_kpi(denominator_kpi_id="infinite"),
            {"sales": self.sales, "infinite": denominator},
        )

        self.assertEqual(result["status"], "dependency_error")
        self.assertIsNone(result["denominator_value"])
        self.assertNotIn("Infinity", json.dumps(result, ensure_ascii=False))

    def test_dependency_failures_and_missing_dependencies_are_safe(self):
        numerator_error = calculate_ratio_kpi(
            self.df,
            _ratio_kpi(),
            {
                "sales": _base_kpi("sales", source_field="不存在"),
                "customers": _base_kpi(
                    "customers", source_field="成交客户数", field_type="numeric"
                ),
            },
        )
        denominator_error = self.calculate(
            _base_kpi("customers", source_field="不存在", field_type="numeric")
        )
        missing = calculate_ratio_kpi(
            self.df,
            _ratio_kpi(),
            {"sales": self.sales},
        )

        self.assertEqual(numerator_error["status"], "dependency_error")
        self.assertEqual(denominator_error["status"], "dependency_error")
        self.assertEqual(missing["status"], "missing_dependency")

    def test_empty_data_and_inputs_are_not_modified_and_result_is_json_safe(self):
        empty = self.df.iloc[0:0].copy()
        original_df = empty.copy(deep=True)
        ratio = _ratio_kpi()
        original_ratio = copy.deepcopy(ratio)
        dependencies = {
            "sales": self.sales,
            "customers": _base_kpi(
                "customers", source_field="成交客户数", field_type="numeric"
            ),
        }
        original_dependencies = copy.deepcopy(dependencies)

        result = calculate_ratio_kpi(empty, ratio, dependencies)

        self.assertEqual(result["status"], "zero_denominator")
        self.assertTrue(json.dumps(result, ensure_ascii=False))
        pd.testing.assert_frame_equal(empty, original_df)
        self.assertEqual(ratio, original_ratio)
        self.assertEqual(dependencies, original_dependencies)

    def test_basic_executor_keeps_non_ratio_behavior_and_rejects_ratio_directly(self):
        basic_with_formula_fields = {
            **self.sales,
            "numerator_kpi_id": "ignored-a",
            "denominator_kpi_id": "ignored-b",
        }
        basic_result = calculate_basic_kpi(self.df, basic_with_formula_fields)
        ratio_result = calculate_basic_kpi(self.df, _ratio_kpi())

        self.assertEqual(basic_result["status"], "ok")
        self.assertEqual(basic_result["value"], 300.0)
        self.assertEqual(ratio_result["status"], "unsupported")


class KpiRatioPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_patch = patch.object(
            project_workspace,
            "PROJECT_ROOT",
            Path(self.temp_dir.name) / "projects",
        )
        self.root_patch.start()
        self.project = project_workspace.create_project("Ratio Project")
        self.project_id = self.project["project_id"]
        save_field_mappings(
            self.project_id,
            [
                {"column_name": "成交金额", "confirmed_type": "金额字段"},
                {"column_name": "成交客户数", "confirmed_type": "数量字段"},
            ],
        )
        self.sales = _base_kpi("sales", enabled=False)
        self.customers = _base_kpi(
            "customers",
            source_field="成交客户数",
            field_type="numeric",
            enabled=False,
        )
        self.ratio = _ratio_kpi(enabled=True)

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def save_all(self, ratio=None):
        return save_kpi_definitions(
            self.project_id,
            [self.sales, self.customers, ratio or self.ratio],
            available_fields=["成交金额", "成交客户数"],
        )

    def test_save_load_and_project_mirror_preserve_ratio_dependencies(self):
        saved = self.save_all()
        loaded = load_kpi_definitions(self.project_id)
        project = project_workspace.get_project(self.project_id)
        ratio = next(item for item in saved if item["kpi_id"] == "ratio-aov")

        self.assertEqual(ratio["validation_status"], "valid")
        self.assertEqual(ratio["numerator_kpi_id"], "sales")
        self.assertEqual(ratio["denominator_kpi_id"], "customers")
        self.assertEqual(saved, loaded)
        self.assertEqual(project["kpi_definitions"], saved)

    def test_usable_ratio_ignores_disabled_dependencies_but_requires_itself_enabled(self):
        self.save_all()

        usable = list_usable_kpis(
            self.project_id,
            available_fields=["成交金额", "成交客户数"],
        )
        self.assertEqual([item["kpi_id"] for item in usable], ["ratio-aov"])

        self.save_all(_ratio_kpi(enabled=False))
        self.assertEqual(
            list_usable_kpis(
                self.project_id,
                available_fields=["成交金额", "成交客户数"],
            ),
            [],
        )

    def test_invalid_or_missing_field_dependency_makes_ratio_unusable(self):
        self.save_all()

        usable = list_usable_kpis(
            self.project_id,
            available_fields=["成交金额"],
        )

        self.assertEqual(usable, [])

    def test_deleted_dependency_keeps_ratio_but_marks_it_invalid(self):
        self.save_all()

        remaining = delete_kpi_definition(self.project_id, "customers")
        ratio = next(item for item in remaining if item["kpi_id"] == "ratio-aov")

        self.assertEqual(ratio["validation_status"], "invalid")
        self.assertIn("customers", "".join(ratio["validation_messages"]))
        self.assertEqual(list_usable_kpis(self.project_id), [])

    def test_legacy_config_and_project_isolation_remain_compatible(self):
        save_kpi_definitions(self.project_id, [self.sales])
        loaded = load_kpi_definitions(self.project_id)
        other_project = project_workspace.create_project("Other Ratio Project")

        self.assertEqual(loaded[0]["numerator_kpi_id"], "")
        self.assertEqual(loaded[0]["denominator_kpi_id"], "")
        self.assertEqual(load_kpi_definitions(other_project["project_id"]), [])

    def test_metric_dictionary_uses_ratio_description_without_source_field(self):
        candidate = generate_metric_candidates_from_kpis(
            [{**normalize_kpi_definition(self.ratio), "lifecycle_status": "saved"}]
        )[0]

        self.assertEqual(candidate["business_definition"], "销售额除以成交客户数")


if __name__ == "__main__":
    unittest.main()
