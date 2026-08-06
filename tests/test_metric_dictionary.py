import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import project_workspace
from src.engines.metric_dictionary_engine import (
    METRIC_ASSOCIATION_ACTIVE,
    METRIC_ASSOCIATION_CANDIDATE,
    METRIC_ASSOCIATION_INVALID,
    METRIC_ASSOCIATION_LEGACY,
    build_metric_association_view,
    build_metric_formula_summary,
    generate_metric_candidates_from_kpis,
    merge_metric_candidates,
)
from src.services.kpi_service import (
    delete_kpi_definition,
    load_kpi_definitions,
    save_kpi_definitions,
)
from src.services.field_mapping_service import save_field_mappings
from src.services.metric_dictionary_service import (
    add_metric_definition,
    delete_metric_definition,
    find_metric_by_alias,
    generate_project_metric_candidates,
    get_metric_by_name,
    get_metric_dictionary,
    get_metric_dictionary_view,
    list_enabled_metrics,
    list_usable_metrics,
    load_metric_dictionary,
    save_metric_dictionary,
    update_metric_definition,
)


class MetricDictionaryEngineTests(unittest.TestCase):
    def setUp(self):
        self.kpis = [
            {
                "kpi_id": "kpi_sales",
                "kpi_name": "销售额",
                "aggregation": "sum",
                "source_field": "成交金额",
                "field_type": "amount",
                "category": "核心指标",
                "description": "统计销售总金额",
                "enabled": True,
                "lifecycle_status": "saved",
                "validation_status": "valid",
            },
            {
                "kpi_id": "kpi_orders",
                "kpi_name": "订单数",
                "aggregation": "count",
                "source_field": "订单ID",
                "field_type": "id",
                "category": "核心指标",
                "description": "统计订单数量",
                "enabled": True,
                "lifecycle_status": "saved",
                "validation_status": "valid",
            },
            {
                "kpi_id": "kpi_yoy",
                "kpi_name": "同比",
                "aggregation": "reserved",
                "source_field": "成交日期",
                "field_type": "date",
                "category": "时间指标",
                "description": "预留时间指标",
                "enabled": False,
                "lifecycle_status": "saved",
                "validation_status": "pending",
            },
        ]

    def test_generates_metric_candidates_from_kpis(self):
        candidates = generate_metric_candidates_from_kpis(self.kpis)
        by_name = {item["metric_name"]: item for item in candidates}

        self.assertEqual(by_name["销售额"]["metric_type"], "核心指标")
        self.assertEqual(by_name["销售额"]["linked_kpi_id"], "kpi_sales")
        self.assertIn("GMV", by_name["销售额"]["aliases"])
        self.assertIn("成交金额", by_name["销售额"]["aliases"])
        self.assertEqual(by_name["同比"]["metric_type"], "时间指标")
        self.assertFalse(by_name["同比"]["enabled"])

    def test_explicit_unsaved_candidate_is_not_a_metric_candidate_source(self):
        candidate = {
            **self.kpis[0],
            "lifecycle_status": "candidate",
            "enabled": False,
        }

        self.assertEqual(generate_metric_candidates_from_kpis([candidate]), [])

    def test_pending_and_ratio_candidates_do_not_generate_semantics(self):
        pending = {
            **self.kpis[0],
            "kpi_id": "pending",
            "lifecycle_status": "candidate",
            "validation_status": "pending",
        }
        ratio_candidate = {
            **pending,
            "kpi_id": "ratio-candidate",
            "aggregation": "ratio",
            "source_field": "",
        }

        self.assertEqual(
            generate_metric_candidates_from_kpis([pending, ratio_candidate]),
            [],
        )

    def test_count_aggregations_generate_distinct_business_definitions(self):
        kpis = [
            {
                "kpi_id": "rows",
                "kpi_name": "记录数",
                "aggregation": "count_rows",
                "source_field": "",
                "field_type": "row",
                "category": "核心指标",
                "lifecycle_status": "saved",
            },
            {
                "kpi_id": "non-null",
                "kpi_name": "非空订单ID数",
                "aggregation": "count",
                "source_field": "订单ID",
                "field_type": "id",
                "category": "核心指标",
                "lifecycle_status": "saved",
            },
            {
                "kpi_id": "distinct",
                "kpi_name": "订单数",
                "aggregation": "count_distinct",
                "source_field": "订单ID",
                "field_type": "id",
                "category": "核心指标",
                "lifecycle_status": "saved",
            },
        ]

        by_name = {
            item["metric_name"]: item
            for item in generate_metric_candidates_from_kpis(kpis)
        }

        self.assertEqual(
            by_name["记录数"]["business_definition"],
            "统计当前分析数据集的记录行数。",
        )
        self.assertIn("非空记录", by_name["非空订单ID数"]["business_definition"])
        self.assertIn("不进行去重", by_name["非空订单ID数"]["business_definition"])
        self.assertIn("非空唯一值", by_name["订单数"]["business_definition"])

    def test_quantity_sum_uses_grain_aware_non_distinct_definition(self):
        candidate = generate_metric_candidates_from_kpis(
            [
                {
                    "kpi_id": "quantity-customers",
                    "kpi_name": "成交客户数",
                    "aggregation": "sum",
                    "source_field": "成交客户数",
                    "field_type": "numeric",
                    "category": "核心指标",
                    "lifecycle_status": "saved",
                    "enabled": True,
                }
            ]
        )[0]

        self.assertIn("字段 `成交客户数` 的合计值", candidate["business_definition"])
        self.assertIn("取决于当前数据粒度", candidate["business_definition"])
        self.assertIn("不代表客户 ID 去重数量", candidate["business_definition"])
        self.assertNotIn("唯一客户数", candidate["aliases"])
        self.assertNotIn("去重客户数", candidate["aliases"])
        self.assertNotIn("Unique Customers", candidate["aliases"])

    def test_basic_and_ratio_formulas_are_readable_without_ids(self):
        ratio = {
            "kpi_id": "aov",
            "kpi_name": "客单价",
            "aggregation": "ratio",
            "source_field": "",
            "numerator_kpi_id": "kpi_sales",
            "denominator_kpi_id": "kpi_orders",
            "lifecycle_status": "saved",
        }
        kpi_by_id = {item["kpi_id"]: item for item in self.kpis}

        self.assertEqual(
            build_metric_formula_summary(self.kpis[0], kpi_by_id),
            "求和（成交金额）",
        )
        self.assertEqual(
            build_metric_formula_summary(self.kpis[1], kpi_by_id),
            "非空计数（订单ID）",
        )
        self.assertEqual(
            build_metric_formula_summary(ratio, kpi_by_id),
            "销售额 ÷ 订单数",
        )

    def test_merge_uses_stable_kpi_id_and_preserves_user_edits(self):
        existing = {
            "metric_id": "metric-sales",
            "metric_name": "销售额（管理口径）",
            "business_definition": "用户已编辑定义",
            "linked_kpi_id": "kpi_sales",
            "linked_kpi_name": "销售额",
        }
        candidate = generate_metric_candidates_from_kpis([self.kpis[0]])[0]

        merged = merge_metric_candidates([existing], [candidate])

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["business_definition"], "用户已编辑定义")

    def test_same_name_new_kpi_does_not_rebind_legacy_metric(self):
        historical = {
            "metric_id": "historical",
            "metric_name": "销售额",
            "linked_kpi_id": "deleted-kpi",
            "linked_kpi_name": "销售额",
        }
        candidate = generate_metric_candidates_from_kpis([self.kpis[0]])[0]

        merged = merge_metric_candidates([historical], [candidate])

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["linked_kpi_id"], "deleted-kpi")
        self.assertEqual(merged[1]["linked_kpi_id"], "kpi_sales")

    def test_association_status_and_usability_are_independent_from_enabled(self):
        metrics = [
            {
                "metric_id": "active",
                "metric_name": "销售额",
                "linked_kpi_id": "kpi_sales",
                "enabled": True,
            },
            {
                "metric_id": "missing",
                "metric_name": "历史指标",
                "linked_kpi_id": "deleted",
                "enabled": True,
            },
            {
                "metric_id": "legacy",
                "metric_name": "旧独立定义",
                "linked_kpi_id": "",
                "enabled": True,
            },
            {
                "metric_id": "candidate",
                "metric_name": "候选",
                "linked_kpi_id": "kpi_orders",
                "enabled": True,
            },
        ]

        view = build_metric_association_view(
            metrics,
            self.kpis,
            candidate_metric_ids={"candidate"},
        )
        by_id = {item["metric_id"]: item for item in view}

        self.assertEqual(by_id["active"]["association_status"], METRIC_ASSOCIATION_ACTIVE)
        self.assertTrue(by_id["active"]["usable"])
        self.assertEqual(by_id["missing"]["association_status"], METRIC_ASSOCIATION_INVALID)
        self.assertFalse(by_id["missing"]["usable"])
        self.assertTrue(by_id["missing"]["enabled"])
        self.assertEqual(by_id["legacy"]["association_status"], METRIC_ASSOCIATION_LEGACY)
        self.assertFalse(by_id["legacy"]["usable"])
        self.assertEqual(by_id["candidate"]["association_status"], METRIC_ASSOCIATION_CANDIDATE)
        self.assertFalse(by_id["candidate"]["usable"])


class MetricDictionaryServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "projects"
        self.root_patch = patch.object(
            project_workspace,
            "PROJECT_ROOT",
            self.project_root,
        )
        self.root_patch.start()
        self.project = project_workspace.create_project("Metric Project")
        save_kpi_definitions(
            self.project["project_id"],
            [
                {
                    "kpi_id": "kpi_sales",
                    "kpi_name": "销售额",
                    "aggregation": "sum",
                    "source_field": "成交金额",
                    "field_type": "amount",
                    "category": "核心指标",
                    "description": "统计销售总金额",
                    "enabled": True,
                },
                {
                    "kpi_id": "kpi_orders",
                    "kpi_name": "订单数",
                    "aggregation": "count",
                    "source_field": "订单ID",
                    "field_type": "id",
                    "category": "核心指标",
                    "description": "统计订单数量",
                    "enabled": True,
                },
            ],
        )

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def test_project_candidate_generation_and_save_restore(self):
        candidates = generate_project_metric_candidates(self.project["project_id"])
        saved = save_metric_dictionary(self.project["project_id"], candidates)
        loaded = load_metric_dictionary(self.project["project_id"])
        project = project_workspace.get_project(self.project["project_id"])

        self.assertEqual(saved, loaded)
        self.assertEqual(project["metric_dictionary"], loaded)
        self.assertIsNotNone(find_metric_by_alias(self.project["project_id"], "GMV"))
        self.assertIsNotNone(find_metric_by_alias(self.project["project_id"], "成交金额"))
        self.assertTrue(
            (
                self.project_root
                / self.project["project_id"]
                / "config"
                / "metric_dictionary.json"
            ).is_file()
        )

    def test_add_edit_delete_alias_lookup_and_kpi_link(self):
        add_metric_definition(
            self.project["project_id"],
            {
                "metric_name": "客单价",
                "metric_type": "核心指标",
                "business_definition": "平均每单成交金额",
                "aliases": "AOV，平均订单金额",
                "linked_kpi_id": "kpi_sales",
                "linked_kpi_name": "销售额",
                "enabled": True,
            },
        )
        metric = get_metric_by_name(self.project["project_id"], "客单价")
        self.assertIsNotNone(metric)
        self.assertEqual(metric["linked_kpi_name"], "销售额")
        self.assertEqual(find_metric_by_alias(self.project["project_id"], "aov")["metric_name"], "客单价")

        update_metric_definition(
            self.project["project_id"],
            metric["metric_id"],
            {"enabled": False, "business_definition": "已禁用测试"},
        )
        self.assertEqual(list_enabled_metrics(self.project["project_id"]), [])
        self.assertEqual(
            get_metric_by_name(self.project["project_id"], "客单价")["business_definition"],
            "已禁用测试",
        )

        delete_metric_definition(self.project["project_id"], metric["metric_id"])
        self.assertEqual(get_metric_dictionary(self.project["project_id"]), [])

    def test_unsaved_kpi_candidates_do_not_generate_metric_candidates(self):
        project = project_workspace.create_project("Unsaved KPI Metric Project")
        save_field_mappings(
            project["project_id"],
            [{"column_name": "成交金额", "confirmed_type": "金额字段"}],
        )

        candidates = generate_project_metric_candidates(project["project_id"])

        self.assertEqual(candidates, [])

    def test_disabled_saved_kpi_still_generates_metric_candidate(self):
        save_kpi_definitions(
            self.project["project_id"],
            [
                {
                    "kpi_id": "disabled-saved",
                    "kpi_name": "禁用销售额",
                    "aggregation": "sum",
                    "source_field": "成交金额",
                    "field_type": "amount",
                    "category": "核心指标",
                    "enabled": False,
                    "lifecycle_status": "saved",
                }
            ],
        )

        candidates = generate_project_metric_candidates(self.project["project_id"])

        self.assertEqual([item["metric_name"] for item in candidates], ["禁用销售额"])
        self.assertFalse(candidates[0]["enabled"])

    def test_saved_metric_definitions_remain_when_linked_kpis_are_removed(self):
        save_metric_dictionary(
            self.project["project_id"],
            [
                {
                    "metric_name": "历史销售额",
                    "linked_kpi_id": "missing-kpi",
                    "linked_kpi_name": "已删除 KPI",
                    "enabled": True,
                }
            ],
        )
        save_kpi_definitions(self.project["project_id"], [])

        loaded = load_metric_dictionary(self.project["project_id"])

        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["metric_name"], "历史销售额")
        self.assertEqual(generate_project_metric_candidates(self.project["project_id"]), [])

    def test_saved_semantic_suppresses_duplicate_candidate_by_kpi_id(self):
        candidate = generate_project_metric_candidates(self.project["project_id"])[0]
        save_metric_dictionary(self.project["project_id"], [candidate])

        self.assertEqual(
            [
                item
                for item in generate_project_metric_candidates(
                    self.project["project_id"]
                )
                if item["linked_kpi_id"] == candidate["linked_kpi_id"]
            ],
            [],
        )

    def test_deleted_kpi_marks_semantic_invalid_without_changing_user_content(self):
        candidate = generate_project_metric_candidates(self.project["project_id"])[0]
        candidate["business_definition"] = "用户维护的历史定义"
        saved_metric = save_metric_dictionary(
            self.project["project_id"], [candidate]
        )[0]

        delete_kpi_definition(
            self.project["project_id"], saved_metric["linked_kpi_id"]
        )
        view = get_metric_dictionary_view(self.project["project_id"])

        historical = next(
            item for item in view if item["metric_id"] == saved_metric["metric_id"]
        )
        self.assertEqual(historical["association_status"], METRIC_ASSOCIATION_INVALID)
        self.assertEqual(historical["business_definition"], "用户维护的历史定义")
        self.assertTrue(historical["enabled"])
        self.assertEqual(list_usable_metrics(self.project["project_id"]), [])

    def test_same_name_new_kpi_does_not_restore_deleted_association(self):
        candidate = generate_project_metric_candidates(self.project["project_id"])[0]
        saved_metric = save_metric_dictionary(
            self.project["project_id"], [candidate]
        )[0]
        old_kpi_id = saved_metric["linked_kpi_id"]
        remaining_kpis = [
            item
            for item in load_kpi_definitions(self.project["project_id"])
            if item["kpi_id"] != old_kpi_id
        ]
        save_kpi_definitions(
            self.project["project_id"],
            remaining_kpis
            + [
                {
                    "kpi_id": "new-same-name",
                    "kpi_name": saved_metric["linked_kpi_name"],
                    "aggregation": "sum",
                    "source_field": "成交金额",
                    "field_type": "amount",
                    "category": "核心指标",
                    "enabled": True,
                }
            ],
        )

        view = get_metric_dictionary_view(self.project["project_id"])
        historical = next(
            item for item in view if item["metric_id"] == saved_metric["metric_id"]
        )
        new_candidate = next(
            item for item in view if item["linked_kpi_id"] == "new-same-name"
        )

        self.assertEqual(historical["linked_kpi_id"], old_kpi_id)
        self.assertEqual(historical["association_status"], METRIC_ASSOCIATION_INVALID)
        self.assertEqual(new_candidate["association_status"], METRIC_ASSOCIATION_CANDIDATE)

    def test_legacy_metric_without_kpi_id_has_stable_unlinked_status(self):
        config_path = (
            self.project_root
            / self.project["project_id"]
            / "config"
            / "metric_dictionary.json"
        )
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps(
                [
                    {
                        "metric_name": "旧独立指标",
                        "business_definition": "历史内容",
                        "aliases": ["Legacy"],
                        "enabled": True,
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        first = load_metric_dictionary(self.project["project_id"])[0]
        second = load_metric_dictionary(self.project["project_id"])[0]
        historical = next(
            item
            for item in get_metric_dictionary_view(self.project["project_id"])
            if item["metric_name"] == "旧独立指标"
        )

        self.assertEqual(first["metric_id"], second["metric_id"])
        self.assertEqual(historical["association_status"], METRIC_ASSOCIATION_LEGACY)
        self.assertFalse(historical["usable"])

    def test_delete_semantic_keeps_kpi_file_and_regenerates_candidate(self):
        candidate = generate_project_metric_candidates(self.project["project_id"])[0]
        saved_metric = save_metric_dictionary(
            self.project["project_id"], [candidate]
        )[0]
        kpi_path = (
            self.project_root
            / self.project["project_id"]
            / "config"
            / "kpi_definitions.json"
        )
        before = kpi_path.read_bytes()

        delete_metric_definition(
            self.project["project_id"], saved_metric["metric_id"]
        )

        self.assertEqual(kpi_path.read_bytes(), before)
        regenerated = generate_project_metric_candidates(self.project["project_id"])
        self.assertIn(
            saved_metric["linked_kpi_id"],
            {item["linked_kpi_id"] for item in regenerated},
        )
        self.assertEqual(
            project_workspace.get_project(self.project["project_id"])[
                "metric_dictionary"
            ],
            [],
        )


if __name__ == "__main__":
    unittest.main()
