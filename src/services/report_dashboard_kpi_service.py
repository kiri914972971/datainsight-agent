from __future__ import annotations

import math
from copy import deepcopy
from datetime import date, datetime
from numbers import Number
from typing import Any

import pandas as pd

from src.engines.kpi_engine import (
    calculate_basic_kpi,
    calculate_ratio_kpi,
    format_kpi_source_or_formula,
)
from src.engines.metric_dictionary_engine import (
    METRIC_ASSOCIATION_ACTIVE,
    build_metric_association_view,
    build_metric_formula_summary,
)
from src.services.kpi_service import load_kpi_definitions, list_usable_kpis
from src.services.metric_dictionary_service import load_metric_dictionary


def build_report_dashboard_kpi_context(
    project_id: str,
    dataframe: pd.DataFrame,
) -> dict[str, Any]:
    """Build a read-only, JSON-safe formal KPI context for the report dashboard."""
    context: dict[str, Any] = {
        "project_id": str(project_id),
        "dataset_row_count": int(len(dataframe)),
        "usable_kpi_count": 0,
        "calculated_kpi_count": 0,
        "failed_kpi_count": 0,
        "items": [],
        "warnings": [],
    }
    available_fields = [str(column) for column in dataframe.columns]

    try:
        saved_kpis = load_kpi_definitions(project_id)
    except (FileNotFoundError, ValueError) as exc:
        context["warnings"].append(f"正式 KPI 定义加载失败：{exc}")
        return context

    try:
        usable_kpis = list_usable_kpis(
            project_id,
            available_fields=available_fields,
        )
    except (FileNotFoundError, ValueError) as exc:
        context["warnings"].append(f"正式 KPI 可用性检查失败：{exc}")
        return context

    kpi_by_id = {
        str(item.get("kpi_id", "")): deepcopy(item)
        for item in saved_kpis
        if isinstance(item, dict) and item.get("kpi_id")
    }
    semantic_by_kpi_id: dict[str, dict[str, Any]] = {}
    try:
        semantic_definitions = load_metric_dictionary(project_id)
    except (FileNotFoundError, ValueError) as exc:
        semantic_definitions = []
        context["warnings"].append(f"指标语义定义加载失败：{exc}")
    else:
        semantic_view = build_metric_association_view(
            semantic_definitions,
            saved_kpis,
        )
        for semantic in semantic_view:
            linked_kpi_id = str(semantic.get("linked_kpi_id", "")).strip()
            if (
                linked_kpi_id
                and semantic.get("enabled")
                and semantic.get("association_status") == METRIC_ASSOCIATION_ACTIVE
            ):
                semantic_by_kpi_id.setdefault(linked_kpi_id, semantic)

    items = []
    warnings = context["warnings"]
    for kpi in usable_kpis:
        item = _calculate_context_item(
            dataframe=dataframe,
            kpi=deepcopy(kpi),
            kpi_by_id=kpi_by_id,
            semantic=semantic_by_kpi_id.get(str(kpi.get("kpi_id", ""))),
        )
        items.append(item)
        if item["semantic_status"] == "missing":
            warnings.append(
                f"指标 {item['kpi_name']} 尚未保存有效业务语义定义。"
            )
        if item["calculation_status"] != "ok":
            warnings.append(
                f"指标 {item['kpi_name']} 暂不可计算："
                f"{item['calculation_message'] or item['calculation_status']}"
            )

    context["items"] = items
    context["usable_kpi_count"] = len(items)
    context["calculated_kpi_count"] = len(
        [item for item in items if item["calculation_status"] == "ok"]
    )
    context["failed_kpi_count"] = len(items) - context["calculated_kpi_count"]
    context["warnings"] = list(dict.fromkeys(warnings))
    return context


def _calculate_context_item(
    *,
    dataframe: pd.DataFrame,
    kpi: dict[str, Any],
    kpi_by_id: dict[str, dict[str, Any]],
    semantic: dict[str, Any] | None,
) -> dict[str, Any]:
    aggregation = str(kpi.get("aggregation", "")).strip().lower()
    formula = build_metric_formula_summary(kpi, kpi_by_id)
    if aggregation == "ratio" and not formula:
        formula = format_kpi_source_or_formula(kpi, kpi_by_id)

    try:
        calculation = (
            calculate_ratio_kpi(dataframe, kpi, kpi_by_id)
            if aggregation == "ratio"
            else calculate_basic_kpi(dataframe, kpi)
        )
    except Exception as exc:  # pragma: no cover - protects future engine extensions
        calculation = {
            "status": "calculation_error",
            "value": None,
            "message": f"KPI 计算失败：{exc}",
        }

    calculation_status = str(
        calculation.get("status", "calculation_error")
    ).strip() or "calculation_error"
    calculation_message = str(calculation.get("message", "")).strip()
    value, value_is_safe = _json_safe_scalar(calculation.get("value"))
    if calculation_status == "ok" and not value_is_safe:
        calculation_status = "calculation_error"
        calculation_message = "KPI 计算结果不是可用的有限标量。"
        value = None
    elif calculation_status != "ok":
        value = None

    item = {
        "kpi_id": str(kpi.get("kpi_id", "")),
        "kpi_name": str(kpi.get("kpi_name", "")),
        "category": str(kpi.get("category", "")),
        "aggregation": aggregation,
        "field_type": str(kpi.get("field_type", "")),
        "source_field": str(kpi.get("source_field", "")),
        "formula": formula,
        "value": value,
        "calculation_status": calculation_status,
        "calculation_message": calculation_message,
        "business_definition": (
            str(semantic.get("business_definition", "")) if semantic else ""
        ),
        "aliases": [str(alias) for alias in semantic.get("aliases", [])]
        if semantic
        else [],
        "semantic_status": "linked" if semantic else "missing",
        "created_by": str(kpi.get("created_by", "")),
    }
    for key in ("numerator_value", "denominator_value"):
        if key in calculation:
            item[key] = _json_safe_scalar(calculation.get(key))[0]
    return item


def _json_safe_scalar(value: Any) -> tuple[int | float | str | None, bool]:
    if value is None or value is pd.NA or value is pd.NaT:
        return None, True
    if isinstance(value, pd.Timestamp):
        return value.isoformat(), True
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            value = value.item()
        except (TypeError, ValueError):
            return None, False
    if value is None:
        return None, True
    if isinstance(value, bool):
        return int(value), True
    if isinstance(value, int):
        return value, True
    if isinstance(value, Number):
        numeric = float(value)
        return (numeric, True) if math.isfinite(numeric) else (None, False)
    if isinstance(value, (datetime, date)):
        return value.isoformat(), True
    if isinstance(value, str):
        return value, True
    return None, False
