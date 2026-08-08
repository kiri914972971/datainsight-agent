from __future__ import annotations

import math
from numbers import Number
from typing import Any


CORE_KPI_CATEGORY = "核心指标"
MAX_CORE_KPI_CARDS = 6

_COUNT_AGGREGATIONS = {"count", "count_rows", "count_distinct"}
_CALCULATION_STATUS_LABELS = {
    "zero_denominator": "分母为 0",
    "missing_dependency": "缺少依赖指标",
    "dependency_error": "依赖指标计算失败",
    "invalid_definition": "指标定义无效",
    "unsupported": "暂不支持",
    "calculation_error": "计算失败",
}


def format_dashboard_kpi_value(item: dict[str, Any]) -> str:
    """Format one formal dashboard KPI without changing its business value."""
    value = item.get("value")
    if value is None:
        return "暂无数据"
    if not isinstance(value, Number):
        return str(value)

    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        return "暂无数据"

    aggregation = str(item.get("aggregation", "")).strip().lower()
    field_type = str(item.get("field_type", "")).strip().lower()
    if field_type == "row" or aggregation in _COUNT_AGGREGATIONS:
        return f"{int(round(numeric_value)):,}"

    rounded_value = round(numeric_value, 2)
    if rounded_value == 0:
        rounded_value = 0.0
    return f"{rounded_value:,.2f}".rstrip("0").rstrip(".")


def build_dashboard_kpi_card_rows(
    items: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    """Arrange cards without empty placeholders."""
    copied_items = [dict(item) for item in items]
    if len(copied_items) <= 4:
        return [copied_items] if copied_items else []
    return [
        copied_items[index : index + 3]
        for index in range(0, len(copied_items), 3)
    ]


def prepare_report_dashboard_kpi_view(
    context: dict[str, Any],
    *,
    max_cards: int = MAX_CORE_KPI_CARDS,
) -> dict[str, Any]:
    """Build the read-only card and failure-table view from formal KPI context."""
    context_items = context.get("items", [])
    items = [item for item in context_items if isinstance(item, dict)]
    core_items = [
        item
        for item in items
        if item.get("category") == CORE_KPI_CATEGORY
        and _is_formal_context_item(item)
    ]
    successful_items = [
        item
        for item in core_items
        if item.get("calculation_status") == "ok" and item.get("value") is not None
    ]
    failed_items = [
        item
        for item in core_items
        if item.get("calculation_status") != "ok"
        or item.get("value") is None
    ]

    safe_limit = max(0, int(max_cards))
    displayed_items = [dict(item) for item in successful_items[:safe_limit]]
    failed_rows = [
        {
            "指标名称": str(item.get("kpi_name", "")),
            "计算状态": _format_calculation_status(item),
            "说明": _format_calculation_message(item),
        }
        for item in failed_items
    ]
    return {
        "available_core_count": len(successful_items),
        "cards": displayed_items,
        "card_rows": build_dashboard_kpi_card_rows(displayed_items),
        "is_truncated": len(successful_items) > safe_limit,
        "has_missing_semantics": any(
            item.get("semantic_status") == "missing"
            for item in successful_items
        ),
        "failed_rows": failed_rows,
    }


def format_dashboard_kpi_definition(
    definition: object,
    *,
    max_length: int = 80,
) -> str:
    """Return a compact single-line semantic definition for a card caption."""
    compact = " ".join(str(definition or "").split())
    if not compact or max_length <= 0:
        return ""
    if len(compact) <= max_length:
        return compact
    return f"{compact[: max_length - 1].rstrip()}…"


def _format_calculation_status(item: dict[str, Any]) -> str:
    status = str(item.get("calculation_status", "")).strip()
    if status == "ok" and item.get("value") is None:
        return "计算结果不可用"
    return _CALCULATION_STATUS_LABELS.get(status, "暂不可计算")


def _is_formal_context_item(item: dict[str, Any]) -> bool:
    if str(item.get("aggregation", "")).strip().lower() == "reserved":
        return False
    if item.get("lifecycle_status") not in (None, "saved"):
        return False
    if "enabled" in item and item.get("enabled") is not True:
        return False
    if item.get("validation_status") not in (None, "valid"):
        return False
    return True


def _format_calculation_message(item: dict[str, Any]) -> str:
    message = str(item.get("calculation_message", "")).strip()
    if message:
        return message.splitlines()[0][:300]
    return _format_calculation_status(item)
