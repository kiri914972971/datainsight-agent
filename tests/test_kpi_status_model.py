import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import project_workspace
from src.engines.kpi_engine import (
    CANDIDATE_VALIDATION_MESSAGE,
    RESERVED_VALIDATION_MESSAGE,
    generate_kpi_candidates,
    merge_kpi_candidates,
    normalize_kpi_definition,
    validate_kpi_definition,
)
from src.engines.metric_dictionary_engine import generate_metric_candidates_from_kpis
from src.services.field_mapping_service import save_field_mappings
from src.services.kpi_service import (
    add_kpi_definition,
    delete_kpi_definition,
    list_enabled_kpis,
    list_usable_kpis,
    load_kpi_definitions,
    save_kpi_definitions,
    update_kpi_definition,
)
from src.services.metric_dictionary_service import generate_project_metric_candidates


FIELD_MAPPINGS = [
    {"column_name": "成交金额", "confirmed_type": "金额字段"},
    {"column_name": "成交客户数", "confirmed_type": "数量字段"},
    {"column_name": "订单ID", "confirmed_type": "ID字段"},
    {"column_name": "成交日期", "confirmed_type": "日期字段"},
    {"column_name": "区域", "confirmed_type": "区域字段"},
]


def _kpi(**overrides):
    result = {
        "kpi_id": "kpi-1",
        "kpi_name": "销售额",
        "aggregation": "sum",
        "source_field": "成交金额",
        "field_type": "amount",
        "category": "核心指标",
        "description": "用户定义",
        "enabled": True,
        "created_by": "user",
        "lifecycle_status": "saved",
        "updated_at": "2026-08-05T00:00:00+00:00",
    }
    result.update(overrides)
    return result


class KpiPureStatusModelTests(unittest.TestCase):
    def test_auto_candidates_are_pending_disabled_candidates(self):
        candidates = generate_kpi_candidates(FIELD_MAPPINGS)

        self.assertTrue(candidates)
        for candidate in candidates:
            self.assertEqual(candidate["lifecycle_status"], "candidate")
            self.assertFalse(candidate["enabled"])
            self.assertEqual(candidate["validation_status"], "pending")
            self.assertIn(
                CANDIDATE_VALIDATION_MESSAGE,
                candidate["validation_messages"],
            )

    def test_candidate_forces_enabled_false_even_when_true_is_supplied(self):
        normalized = normalize_kpi_definition(
            _kpi(
                created_by="auto",
                lifecycle_status="candidate",
                enabled=True,
            )
        )

        self.assertFalse(normalized["enabled"])
        self.assertEqual(normalized["validation_status"], "pending")

    def test_invalid_aggregation_is_preserved_and_marked_invalid(self):
        normalized = normalize_kpi_definition(_kpi(aggregation=" Median "))

        self.assertEqual(normalized["aggregation"], "median")
        self.assertEqual(normalized["validation_status"], "invalid")
        self.assertNotEqual(normalized["aggregation"], "sum")

    def test_reserved_rule_is_pending(self):
        result = validate_kpi_definition(
            _kpi(
                aggregation="reserved",
                source_field="",
                field_type="date",
            )
        )

        self.assertEqual(result["validation_status"], "pending")
        self.assertIn(RESERVED_VALIDATION_MESSAGE, result["validation_messages"])

    def test_empty_name_and_source_are_invalid(self):
        empty_name = validate_kpi_definition(_kpi(kpi_name=""))
        empty_source = validate_kpi_definition(_kpi(source_field=""))

        self.assertEqual(empty_name["validation_status"], "invalid")
        self.assertEqual(empty_source["validation_status"], "invalid")

    def test_missing_available_or_mapped_source_is_invalid(self):
        unavailable = validate_kpi_definition(
            _kpi(),
            available_fields=["其他字段"],
        )
        unmapped = validate_kpi_definition(
            _kpi(),
            field_mappings=[
                {"column_name": "其他字段", "confirmed_type": "金额字段"}
            ],
        )

        self.assertEqual(unavailable["validation_status"], "invalid")
        self.assertIn("成交金额", "".join(unavailable["validation_messages"]))
        self.assertEqual(unmapped["validation_status"], "invalid")

    def test_sum_and_avg_accept_amount_or_numeric(self):
        cases = (
            _kpi(aggregation="sum", field_type="amount"),
            _kpi(aggregation="sum", field_type="numeric"),
            _kpi(aggregation="avg", field_type="amount"),
            _kpi(aggregation="avg", field_type="numeric"),
        )

        for item in cases:
            self.assertEqual(
                validate_kpi_definition(item)["validation_status"],
                "valid",
            )

    def test_sum_and_avg_reject_explicit_non_numeric_types(self):
        for field_type in ("date", "id", "region", "product", "person"):
            result = validate_kpi_definition(
                _kpi(field_type=field_type, aggregation="sum")
            )
            self.assertEqual(result["validation_status"], "invalid")

    def test_max_and_min_accept_numeric_amount_and_date(self):
        for aggregation in ("max", "min"):
            for field_type in ("numeric", "amount", "date"):
                result = validate_kpi_definition(
                    _kpi(aggregation=aggregation, field_type=field_type)
                )
                self.assertEqual(result["validation_status"], "valid")

    def test_count_accepts_any_existing_field_type(self):
        for field_type in ("id", "date", "region", "product", "person"):
            result = validate_kpi_definition(
                _kpi(aggregation="count", field_type=field_type),
                available_fields=["成交金额"],
            )
            self.assertEqual(result["validation_status"], "valid")

    def test_enabled_does_not_decide_validation_status(self):
        enabled = normalize_kpi_definition(_kpi(enabled=True))
        disabled = normalize_kpi_definition(_kpi(enabled=False))

        self.assertEqual(enabled["validation_status"], "valid")
        self.assertEqual(disabled["validation_status"], "valid")

    def test_field_mapping_type_is_used_for_compatibility(self):
        normalized = normalize_kpi_definition(
            _kpi(field_type="custom"),
            field_mappings=FIELD_MAPPINGS,
        )

        self.assertEqual(normalized["validation_status"], "valid")

    def test_normalization_is_json_safe_and_does_not_mutate_input(self):
        original = _kpi(validation_messages=["旧消息"])
        before = copy.deepcopy(original)

        normalized = normalize_kpi_definition(original)
        serialized = json.dumps(normalized, ensure_ascii=False)

        self.assertTrue(serialized)
        self.assertEqual(original, before)

    def test_merge_preserves_saved_item_and_adds_new_candidate(self):
        saved = _kpi(
            kpi_name="用户修改名称",
            description="用户修改描述",
            enabled=False,
        )
        matching_candidate = _kpi(
            kpi_name="自动候选名称",
            description="自动描述",
            enabled=True,
            created_by="auto",
            lifecycle_status="candidate",
        )
        new_candidate = _kpi(
            kpi_id="kpi-2",
            kpi_name="订单数",
            aggregation="count",
            source_field="订单ID",
            field_type="id",
            description="自动候选",
            created_by="auto",
            lifecycle_status="candidate",
        )

        merged = merge_kpi_candidates(
            [saved],
            [matching_candidate, new_candidate],
        )

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["kpi_name"], "用户修改名称")
        self.assertEqual(merged[0]["description"], "用户修改描述")
        self.assertFalse(merged[0]["enabled"])
        self.assertEqual(merged[0]["lifecycle_status"], "saved")
        self.assertEqual(merged[1]["lifecycle_status"], "candidate")
        self.assertFalse(merged[1]["enabled"])

    def test_merge_does_not_mutate_inputs(self):
        existing = [_kpi()]
        candidates = [_kpi(kpi_id="candidate", lifecycle_status="candidate")]
        existing_before = copy.deepcopy(existing)
        candidates_before = copy.deepcopy(candidates)

        merge_kpi_candidates(existing, candidates)

        self.assertEqual(existing, existing_before)
        self.assertEqual(candidates, candidates_before)

    def test_merge_does_not_write_project_files(self):
        with patch.object(Path, "write_text") as write_text:
            merge_kpi_candidates(
                [_kpi()],
                [_kpi(kpi_id="candidate", lifecycle_status="candidate")],
            )

        write_text.assert_not_called()

    def test_metric_candidates_ignore_additional_kpi_status_fields_safely(self):
        metric_candidates = generate_metric_candidates_from_kpis(
            [normalize_kpi_definition(_kpi())]
        )

        self.assertEqual(len(metric_candidates), 1)
        self.assertEqual(metric_candidates[0]["metric_name"], "销售额")


class KpiPersistedStatusModelTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name) / "projects"
        self.root_patch = patch.object(
            project_workspace,
            "PROJECT_ROOT",
            self.project_root,
        )
        self.root_patch.start()
        self.project = project_workspace.create_project("KPI Status Project")
        self.project_id = self.project["project_id"]
        save_field_mappings(self.project_id, FIELD_MAPPINGS)

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def test_candidates_are_not_persisted_or_usable_before_save(self):
        candidates = generate_kpi_candidates(FIELD_MAPPINGS)

        self.assertTrue(candidates)
        self.assertEqual(list_usable_kpis(self.project_id), [])
        self.assertFalse(self._config_path().exists())

    def test_save_converts_candidate_to_saved_and_preserves_enabled(self):
        candidate = generate_kpi_candidates(FIELD_MAPPINGS)[0]
        submitted = {**candidate, "enabled": True}

        saved = save_kpi_definitions(self.project_id, [submitted])

        self.assertEqual(saved[0]["lifecycle_status"], "saved")
        self.assertTrue(saved[0]["enabled"])
        self.assertEqual(saved[0]["validation_status"], "valid")

    def test_save_does_not_mutate_submitted_list_or_definition(self):
        submitted = [
            _kpi(
                lifecycle_status="candidate",
                created_by="auto",
                enabled=True,
            )
        ]
        before = copy.deepcopy(submitted)

        save_kpi_definitions(self.project_id, submitted)

        self.assertEqual(submitted, before)

    def test_legacy_configuration_loads_as_saved_and_keeps_enabled(self):
        self._write_raw_config(
            [
                {
                    "kpi_id": "legacy",
                    "kpi_name": "销售额",
                    "aggregation": "sum",
                    "source_field": "成交金额",
                    "field_type": "amount",
                    "enabled": False,
                    "created_by": "auto",
                    "updated_at": "legacy-time",
                }
            ]
        )

        loaded = load_kpi_definitions(self.project_id)

        self.assertEqual(loaded[0]["lifecycle_status"], "saved")
        self.assertFalse(loaded[0]["enabled"])
        self.assertEqual(loaded[0]["validation_status"], "valid")
        self.assertEqual(loaded[0]["updated_at"], "legacy-time")
        self.assertEqual(loaded[0]["created_by"], "auto")

    def test_usable_filter_requires_saved_enabled_and_valid(self):
        save_kpi_definitions(
            self.project_id,
            [
                _kpi(kpi_id="valid-enabled"),
                _kpi(kpi_id="valid-disabled", kpi_name="客户数", aggregation="count", source_field="订单ID", field_type="id", enabled=False),
                _kpi(kpi_id="invalid-enabled", kpi_name="错误指标", aggregation="median"),
                _kpi(kpi_id="pending-enabled", kpi_name="同比", aggregation="reserved", source_field="成交日期", field_type="date"),
            ],
        )

        usable = list_usable_kpis(self.project_id)

        self.assertEqual([item["kpi_id"] for item in usable], ["valid-enabled"])

    def test_available_fields_revalidates_saved_kpis(self):
        save_kpi_definitions(self.project_id, [_kpi()])

        self.assertEqual(len(list_usable_kpis(self.project_id, ["成交金额"])), 1)
        self.assertEqual(list_usable_kpis(self.project_id, ["其他字段"]), [])

    def test_save_keeps_valid_invalid_and_pending_records(self):
        saved = save_kpi_definitions(
            self.project_id,
            [
                _kpi(kpi_id="valid"),
                _kpi(kpi_id="invalid", kpi_name="错误指标", aggregation="median"),
                _kpi(kpi_id="pending", kpi_name="同比", aggregation="reserved", source_field="成交日期", field_type="date"),
                "not-a-dict",
                {"kpi_name": ""},
            ],
        )

        self.assertEqual(len(saved), 3)
        self.assertEqual(
            [item["validation_status"] for item in saved],
            ["valid", "invalid", "pending"],
        )
        json.dumps(saved, ensure_ascii=False)

    def test_load_save_round_trip_keeps_status_fields(self):
        saved = save_kpi_definitions(self.project_id, [_kpi()])
        loaded = load_kpi_definitions(self.project_id)

        self.assertEqual(saved, loaded)
        for field in (
            "lifecycle_status",
            "validation_status",
            "validation_messages",
        ):
            self.assertIn(field, loaded[0])

    def test_list_enabled_kpis_keeps_legacy_enabled_only_behavior(self):
        save_kpi_definitions(
            self.project_id,
            [
                _kpi(kpi_id="invalid", aggregation="median", enabled=True),
                _kpi(kpi_id="disabled", kpi_name="客户数", aggregation="count", source_field="订单ID", field_type="id", enabled=False),
            ],
        )

        enabled = list_enabled_kpis(self.project_id)

        self.assertEqual([item["kpi_id"] for item in enabled], ["invalid"])
        self.assertEqual(enabled[0]["validation_status"], "invalid")

    def test_add_update_delete_legacy_interfaces_still_work(self):
        added = add_kpi_definition(self.project_id, _kpi())
        kpi_id = added[0]["kpi_id"]

        updated = update_kpi_definition(
            self.project_id,
            kpi_id,
            {"enabled": False, "description": "更新后"},
        )
        deleted = delete_kpi_definition(self.project_id, kpi_id)

        self.assertFalse(updated[0]["enabled"])
        self.assertEqual(updated[0]["description"], "更新后")
        self.assertEqual(deleted, [])

    def test_metric_dictionary_project_candidates_remain_compatible(self):
        save_kpi_definitions(self.project_id, [_kpi()])

        candidates = generate_project_metric_candidates(self.project_id)

        self.assertTrue(candidates)
        self.assertEqual(candidates[0]["metric_name"], "销售额")

    def test_corrupted_configuration_has_clear_error(self):
        self._config_path().parent.mkdir(parents=True, exist_ok=True)
        self._config_path().write_text("{broken", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "KPI 配置损坏"):
            load_kpi_definitions(self.project_id)

    def test_project_kpis_are_isolated(self):
        other_project = project_workspace.create_project("Other KPI Project")
        save_field_mappings(other_project["project_id"], FIELD_MAPPINGS)
        save_kpi_definitions(self.project_id, [_kpi()])

        self.assertEqual(load_kpi_definitions(other_project["project_id"]), [])
        self.assertEqual(len(load_kpi_definitions(self.project_id)), 1)

    def _config_path(self):
        return self.project_root / self.project_id / "config" / "kpi_definitions.json"

    def _write_raw_config(self, payload):
        self._config_path().parent.mkdir(parents=True, exist_ok=True)
        self._config_path().write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
