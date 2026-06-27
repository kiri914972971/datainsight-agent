from __future__ import annotations

import uuid
from typing import Any


SUPPORTED_AGGREGATIONS = ("sum", "count", "avg", "max", "min")
RESERVED_AGGREGATION = "reserved"
KPI_CATEGORIES = ("核心指标", "时间指标", "维度指标")


def generate_kpi_candidates(
    field_mappings: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Generate project-level KPI definition candidates from confirmed field mappings."""
    mappings = [
        item
        for item in field_mappings or []
        if item.get("column_name") and item.get("confirmed_type") != "忽略字段"
    ]
    amount_fields = _columns_by_type(mappings, "金额字段")
    id_fields = _columns_by_type(mappings, "ID字段")
    date_fields = _columns_by_type(mappings, "日期字段")
    person_fields = _columns_by_type(mappings, "人员字段")
    product_fields = _columns_by_type(mappings, "产品字段")
    region_fields = _columns_by_type(mappings, "区域字段")

    candidates: list[dict[str, Any]] = []
    for index, field in enumerate(amount_fields):
        candidates.append(
            _kpi(
                kpi_name="销售额" if index == 0 else f"{field}合计",
                aggregation="sum",
                source_field=field,
                field_type="amount",
                category="核心指标",
                description="统计销售总金额",
                enabled=True,
            )
        )
        candidates.append(
            _kpi(
                kpi_name="客单价" if index == 0 else f"{field}平均值",
                aggregation="avg",
                source_field=field,
                field_type="amount",
                category="核心指标",
                description="V1 使用金额字段 AVG 定义；复杂公式后续支持。",
                enabled=True,
            )
        )

    for field in id_fields:
        candidates.append(
            _kpi(
                kpi_name=_count_kpi_name(field),
                aggregation="count",
                source_field=field,
                field_type="id",
                category="核心指标",
                description=f"统计 {field} 的记录数量",
                enabled=True,
            )
        )

    for field in date_fields:
        for name in ("同比", "环比", "增长率"):
            candidates.append(
                _kpi(
                    kpi_name=name,
                    aggregation=RESERVED_AGGREGATION,
                    source_field=field,
                    field_type="date",
                    category="时间指标",
                    description=f"基于 {field} 预留时间分析能力，V1 不计算。",
                    enabled=False,
                )
            )

    for field in region_fields:
        candidates.append(_dimension_kpi(field, "区域销售额", "region"))
    for field in product_fields:
        candidates.append(_dimension_kpi(field, "产品销售额", "product"))
    for field in person_fields:
        candidates.append(_dimension_kpi(field, "销售员销售额", "person"))

    return _deduplicate_kpis(candidates)


def merge_kpi_candidates(
    existing_kpis: list[dict[str, Any]] | None,
    candidates: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Preserve user edits while adding new auto-detected KPI candidates."""
    merged = {_kpi_key(item): item for item in existing_kpis or []}
    for candidate in candidates or []:
        merged.setdefault(_kpi_key(candidate), candidate)
    return list(merged.values())


def normalize_kpi_definition(kpi: dict[str, Any]) -> dict[str, Any]:
    aggregation = str(kpi.get("aggregation", "")).lower()
    if aggregation not in SUPPORTED_AGGREGATIONS and aggregation != RESERVED_AGGREGATION:
        aggregation = "sum"
    category = str(kpi.get("category", "核心指标"))
    if category not in KPI_CATEGORIES:
        category = "核心指标"
    return {
        "kpi_id": str(kpi.get("kpi_id") or uuid.uuid4().hex),
        "kpi_name": str(kpi.get("kpi_name", "")).strip(),
        "aggregation": aggregation,
        "source_field": str(kpi.get("source_field", "")).strip(),
        "field_type": str(kpi.get("field_type", "custom")).strip() or "custom",
        "category": category,
        "description": str(kpi.get("description", "")).strip(),
        "enabled": bool(kpi.get("enabled", True)),
        "created_by": str(kpi.get("created_by", "user")),
        "updated_at": str(kpi.get("updated_at", "")),
    }


def _dimension_kpi(field: str, name: str, field_type: str) -> dict[str, Any]:
    return _kpi(
        kpi_name=name,
        aggregation=RESERVED_AGGREGATION,
        source_field=field,
        field_type=field_type,
        category="维度指标",
        description=f"基于 {field} 预留维度分析能力，V1 不计算。",
        enabled=False,
    )


def _kpi(
    kpi_name: str,
    aggregation: str,
    source_field: str,
    field_type: str,
    category: str,
    description: str,
    enabled: bool,
) -> dict[str, Any]:
    return normalize_kpi_definition(
        {
            "kpi_name": kpi_name,
            "aggregation": aggregation,
            "source_field": source_field,
            "field_type": field_type,
            "category": category,
            "description": description,
            "enabled": enabled,
            "created_by": "auto",
        }
    )


def _count_kpi_name(field: str) -> str:
    lowered = str(field).lower()
    if any(keyword in lowered for keyword in ("订单", "order")):
        return "订单数"
    if any(keyword in lowered for keyword in ("客户", "用户", "customer", "user")):
        return "客户数"
    return f"{field}数量"


def _columns_by_type(mappings: list[dict[str, Any]], field_type: str) -> list[str]:
    return [
        str(item["column_name"])
        for item in mappings
        if item.get("confirmed_type") == field_type
    ]


def _deduplicate_kpis(kpis: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return list({_kpi_key(item): item for item in kpis}.values())


def _kpi_key(kpi: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(kpi.get("kpi_name", "")),
        str(kpi.get("aggregation", "")),
        str(kpi.get("source_field", "")),
        str(kpi.get("category", "")),
    )
