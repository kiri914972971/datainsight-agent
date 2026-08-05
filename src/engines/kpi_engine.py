from __future__ import annotations

import uuid
from typing import Any


SUPPORTED_AGGREGATIONS = ("sum", "count", "avg", "max", "min")
RESERVED_AGGREGATION = "reserved"
KPI_CATEGORIES = ("核心指标", "时间指标", "维度指标")
KPI_LIFECYCLE_STATUSES = ("candidate", "saved")
KPI_VALIDATION_STATUSES = ("valid", "invalid", "pending")
CANDIDATE_VALIDATION_MESSAGE = "自动推荐候选，需用户确认并保存后才能供下游使用。"
RESERVED_VALIDATION_MESSAGE = "该规则为预留能力，当前版本不可直接执行。"

_FIELD_TYPE_ALIASES = {
    "amount": "amount",
    "金额字段": "amount",
    "numeric": "numeric",
    "number": "numeric",
    "数量字段": "numeric",
    "date": "date",
    "datetime": "date",
    "日期字段": "date",
    "时间字段": "date",
    "id": "id",
    "identifier": "id",
    "ID字段": "id",
    "region": "region",
    "区域字段": "region",
    "product": "product",
    "产品字段": "product",
    "person": "person",
    "人员字段": "person",
    "categorical": "categorical",
    "类别字段": "categorical",
}


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
                enabled=False,
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
                enabled=False,
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
                enabled=False,
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
    merged = {}
    saved_kpi_ids = set()
    for item in existing_kpis or []:
        if not isinstance(item, dict):
            continue
        normalized = normalize_kpi_definition(
            item,
            lifecycle_status="saved",
        )
        if normalized["kpi_name"]:
            merged[_kpi_key(normalized)] = normalized
            saved_kpi_ids.add(normalized["kpi_id"])
    for candidate in candidates or []:
        if not isinstance(candidate, dict):
            continue
        normalized = normalize_kpi_definition(
            candidate,
            lifecycle_status="candidate",
        )
        if (
            normalized["kpi_name"]
            and normalized["kpi_id"] not in saved_kpi_ids
        ):
            merged.setdefault(_kpi_key(normalized), normalized)
    return list(merged.values())


def normalize_kpi_definition(
    kpi: dict[str, Any],
    *,
    lifecycle_status: str | None = None,
    available_fields: list[str] | tuple[str, ...] | set[str] | None = None,
    field_mappings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a JSON-safe KPI definition without mutating the input."""
    source = dict(kpi) if isinstance(kpi, dict) else {}
    aggregation = str(source.get("aggregation", "")).strip().lower()
    category = str(source.get("category", "核心指标"))
    if category not in KPI_CATEGORIES:
        category = "核心指标"
    created_by = str(source.get("created_by", "user")).strip() or "user"
    resolved_lifecycle_status = str(
        lifecycle_status
        or source.get("lifecycle_status")
        or ("candidate" if created_by == "auto" else "saved")
    ).strip().lower()
    if resolved_lifecycle_status not in KPI_LIFECYCLE_STATUSES:
        resolved_lifecycle_status = (
            "candidate" if created_by == "auto" else "saved"
        )
    enabled = bool(source.get("enabled", True))
    if resolved_lifecycle_status == "candidate":
        enabled = False

    normalized = {
        "kpi_id": str(source.get("kpi_id") or uuid.uuid4().hex),
        "kpi_name": str(source.get("kpi_name", "")).strip(),
        "aggregation": aggregation,
        "source_field": str(source.get("source_field", "")).strip(),
        "field_type": str(source.get("field_type", "custom")).strip() or "custom",
        "category": category,
        "description": str(source.get("description", "")).strip(),
        "enabled": enabled,
        "created_by": created_by,
        "lifecycle_status": resolved_lifecycle_status,
        "validation_status": "pending",
        "validation_messages": [],
        "updated_at": str(source.get("updated_at", "")),
    }
    normalized.update(
        validate_kpi_definition(
            normalized,
            available_fields=available_fields,
            field_mappings=field_mappings,
        )
    )
    return normalized


def validate_kpi_definition(
    kpi: dict[str, Any],
    available_fields: list[str] | tuple[str, ...] | set[str] | None = None,
    field_mappings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate one KPI definition without project or UI dependencies."""
    source = dict(kpi) if isinstance(kpi, dict) else {}
    lifecycle_status = str(
        source.get("lifecycle_status", "saved")
    ).strip().lower()
    kpi_name = str(source.get("kpi_name", "")).strip()
    aggregation = str(source.get("aggregation", "")).strip().lower()
    source_field = str(source.get("source_field", "")).strip()

    invalid_messages: list[str] = []
    pending_messages: list[str] = []
    if lifecycle_status == "candidate":
        pending_messages.append(CANDIDATE_VALIDATION_MESSAGE)
    if not kpi_name:
        invalid_messages.append("KPI 名称不能为空。")
    if aggregation == RESERVED_AGGREGATION:
        pending_messages.append(RESERVED_VALIDATION_MESSAGE)
    elif aggregation not in SUPPORTED_AGGREGATIONS:
        invalid_messages.append(
            f"不支持的聚合方式：{aggregation or '空值'}。"
        )

    if aggregation in SUPPORTED_AGGREGATIONS and not source_field:
        invalid_messages.append("来源字段不能为空。")
    elif aggregation in SUPPORTED_AGGREGATIONS:
        if available_fields is not None:
            available_field_names = {
                str(field) for field in available_fields
            }
            if source_field not in available_field_names:
                invalid_messages.append(
                    f"来源字段不存在于当前分析数据集：{source_field}。"
                )

        mapping_by_column = _mapping_by_column(field_mappings)
        if field_mappings is not None and source_field not in mapping_by_column:
            invalid_messages.append(
                f"来源字段不存在于字段映射：{source_field}。"
            )

        resolved_field_type = _resolved_field_type(
            source,
            mapping_by_column.get(source_field),
        )
        if aggregation in {"sum", "avg"} and resolved_field_type not in {
            "amount",
            "numeric",
        }:
            invalid_messages.append(
                f"聚合方式 {aggregation} 不适用于字段类型 "
                f"{resolved_field_type or 'unknown'}。"
            )
        elif aggregation in {"max", "min"} and resolved_field_type not in {
            "amount",
            "numeric",
            "date",
        }:
            invalid_messages.append(
                f"聚合方式 {aggregation} 不适用于字段类型 "
                f"{resolved_field_type or 'unknown'}。"
            )

    validation_messages = _deduplicate_messages(
        invalid_messages + pending_messages
    )
    if invalid_messages:
        validation_status = "invalid"
    elif pending_messages:
        validation_status = "pending"
    else:
        validation_status = "valid"
    return {
        "validation_status": validation_status,
        "validation_messages": validation_messages,
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
            "kpi_id": _candidate_kpi_id(
                kpi_name,
                aggregation,
                source_field,
                category,
            ),
            "kpi_name": kpi_name,
            "aggregation": aggregation,
            "source_field": source_field,
            "field_type": field_type,
            "category": category,
            "description": description,
            "enabled": enabled,
            "created_by": "auto",
            "lifecycle_status": "candidate",
        }
    )


def _candidate_kpi_id(
    kpi_name: str,
    aggregation: str,
    source_field: str,
    category: str,
) -> str:
    identity = "|".join(
        (kpi_name, aggregation, source_field, category)
    )
    return uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"data-insight-agent:kpi-candidate:{identity}",
    ).hex


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


def _mapping_by_column(
    field_mappings: list[dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("column_name")): dict(item)
        for item in field_mappings or []
        if isinstance(item, dict) and item.get("column_name")
    }


def _resolved_field_type(
    kpi: dict[str, Any],
    field_mapping: dict[str, Any] | None,
) -> str:
    if field_mapping:
        mapped_type = str(
            field_mapping.get("confirmed_type")
            or field_mapping.get("inferred_type")
            or ""
        ).strip()
        if mapped_type in _FIELD_TYPE_ALIASES:
            return _FIELD_TYPE_ALIASES[mapped_type]
    field_type = str(kpi.get("field_type", "")).strip()
    return _FIELD_TYPE_ALIASES.get(field_type, field_type.lower())


def _deduplicate_messages(messages: list[str]) -> list[str]:
    return list(dict.fromkeys(str(message) for message in messages if message))


def _kpi_key(kpi: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(kpi.get("kpi_name", "")),
        str(kpi.get("aggregation", "")),
        str(kpi.get("source_field", "")),
        str(kpi.get("category", "")),
    )
