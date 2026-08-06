from __future__ import annotations

import math
import re
import uuid
from typing import Any

import pandas as pd

from src.exploration import build_exploration_field_roles, is_derived_time_column


SUPPORTED_AGGREGATIONS = (
    "sum",
    "count",
    "count_rows",
    "count_distinct",
    "avg",
    "max",
    "min",
    "ratio",
)
BASIC_KPI_AGGREGATIONS = frozenset(SUPPORTED_AGGREGATIONS) - {"ratio"}
RESERVED_AGGREGATION = "reserved"
AGGREGATION_LABELS = {
    "sum": "求和",
    "count": "非空计数",
    "count_rows": "记录行数",
    "count_distinct": "去重计数",
    "avg": "平均值",
    "max": "最大值",
    "min": "最小值",
    "ratio": "比率",
    "reserved": "预留能力",
}
AGGREGATION_HELP_TEXTS = {
    "count": "非空计数统计来源字段中的非空记录，不进行去重。",
    "count_rows": "记录行数统计当前分析数据集的总行数，不等同于订单数；该规则无需来源字段。",
    "count_distinct": "去重计数统计来源字段中的非空唯一值数量，适合订单 ID、客户 ID、人员编号等字段。",
}
NO_SOURCE_FIELD_LABEL = "无需来源字段"
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
    "row": "row",
    "dataset": "dataset",
}

_QUANTITY_NAME_KEYWORDS_ZH = (
    "数量",
    "人数",
    "客户数",
    "订单数",
    "件数",
    "销量",
    "次数",
    "访问数",
    "库存数",
    "成交数",
    "交易数",
    "投诉数",
    "退款数",
)
_QUANTITY_NAME_KEYWORDS_EN = {
    "count",
    "quantity",
    "qty",
    "units",
    "volume",
    "visits",
    "customers",
    "orders",
    "transactions",
}
_NON_ADDITIVE_NAME_KEYWORDS_ZH = (
    "转化率",
    "退款率",
    "占比",
    "比例",
    "增长率",
    "百分比",
    "客单价",
    "单价",
    "均价",
    "平均",
    "人均",
)
_NON_ADDITIVE_NAME_KEYWORDS_EN = {
    "percentage",
    "percent",
    "pct",
    "ratio",
    "rate",
    "share",
    "average",
    "avg",
    "mean",
    "price",
}
_IDENTIFIER_NAME_KEYWORDS_ZH = ("工号", "编号", "编码")
_IDENTIFIER_NAME_KEYWORDS_EN = {"id", "code", "key"}
_TIME_COMPONENT_NAME_KEYWORDS_ZH = ("年", "年份", "月", "月份", "季度", "星期", "周几", "日期")
_TIME_COMPONENT_NAME_KEYWORDS_EN = {
    "year",
    "month",
    "quarter",
    "weekday",
    "week_day",
    "date",
}

_UNIT_PRICE_NAMES_ZH = (
    "客单价",
    "单价",
    "均价",
    "平均订单金额",
)
_UNIT_PRICE_NAMES_EN = {
    "aov",
    "average order value",
    "unit price",
    "average price",
}
_AOV_NUMERATOR_NAMES = {
    "销售额",
    "成交金额",
    "营业收入",
    "revenue",
    "sales",
}
_AOV_DENOMINATOR_NAMES = {
    "成交客户数",
    "客户数",
    "成交人数",
    "customer count",
    "customers",
}


def is_additive_quantity_field(column_name: str) -> bool:
    """Return whether a field name clearly describes an additive quantity."""
    raw_name = str(column_name or "").strip()
    if not raw_name:
        return False
    compact_name = re.sub(r"[\s_\-]+", "", raw_name).casefold()
    tokens = set(_field_name_tokens(raw_name))

    if any(keyword in compact_name for keyword in _NON_ADDITIVE_NAME_KEYWORDS_ZH):
        return False
    if tokens & _NON_ADDITIVE_NAME_KEYWORDS_EN:
        return False
    if any(keyword in compact_name for keyword in _IDENTIFIER_NAME_KEYWORDS_ZH):
        return False
    if tokens & _IDENTIFIER_NAME_KEYWORDS_EN:
        return False

    has_quantity_semantics = any(
        keyword in compact_name for keyword in _QUANTITY_NAME_KEYWORDS_ZH
    ) or bool(tokens & _QUANTITY_NAME_KEYWORDS_EN)
    if not has_quantity_semantics:
        return False

    if compact_name in _TIME_COMPONENT_NAME_KEYWORDS_ZH:
        return False
    if tokens and tokens.issubset(_TIME_COMPONENT_NAME_KEYWORDS_EN):
        return False
    return True


def is_unit_price_field(column_name: str) -> bool:
    """Return whether a field name explicitly describes a unit-price metric."""
    normalized = _normalize_semantic_name(column_name)
    semantic_names = {
        *(_normalize_semantic_name(name) for name in _UNIT_PRICE_NAMES_ZH),
        *(_normalize_semantic_name(name) for name in _UNIT_PRICE_NAMES_EN),
    }
    return any(normalized == name or normalized.endswith(name) for name in semantic_names)


def get_ratio_dependency_options(
    saved_kpis: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Return saved and valid basic KPIs allowed as ratio dependencies."""
    return [
        dict(item)
        for item in saved_kpis or []
        if isinstance(item, dict)
        and str(item.get("kpi_id", "")).strip()
        and str(item.get("lifecycle_status", "saved")).strip().lower() == "saved"
        and str(item.get("validation_status", "")).strip().lower() == "valid"
        and str(item.get("aggregation", "")).strip().lower()
        in BASIC_KPI_AGGREGATIONS
    ]


def infer_ratio_field_type(
    numerator_kpi: dict[str, Any] | None,
    denominator_kpi: dict[str, Any] | None,
) -> str:
    """Infer the minimal V1 result type for a ratio definition."""
    numerator_type = str((numerator_kpi or {}).get("field_type", "")).strip().lower()
    denominator_type = str((denominator_kpi or {}).get("field_type", "")).strip().lower()
    denominator_aggregation = str(
        (denominator_kpi or {}).get("aggregation", "")
    ).strip().lower()
    quantity_like_denominator = (
        denominator_aggregation in {"count", "count_rows", "count_distinct"}
        or denominator_type in {"numeric", "number", "quantity", "id", "row"}
    )
    return "amount" if numerator_type == "amount" and quantity_like_denominator else "numeric"


def format_kpi_source_or_formula(
    kpi: dict[str, Any],
    kpi_by_id: dict[str, dict[str, Any]] | None = None,
    *,
    no_source_field_label: str = NO_SOURCE_FIELD_LABEL,
) -> str:
    """Return a readable source field or ratio formula without exposing IDs."""
    if str(kpi.get("aggregation", "")).strip().lower() != "ratio":
        return str(kpi.get("source_field", "")).strip() or no_source_field_label
    dependencies = kpi_by_id or {}
    numerator = dependencies.get(str(kpi.get("numerator_kpi_id", "")).strip(), {})
    denominator = dependencies.get(str(kpi.get("denominator_kpi_id", "")).strip(), {})
    numerator_name = str(numerator.get("kpi_name", "")).strip() or "分子指标不可用"
    denominator_name = str(denominator.get("kpi_name", "")).strip() or "分母指标不可用"
    return f"{numerator_name} ÷ {denominator_name}"


def get_ratio_dependents(
    saved_kpis: list[dict[str, Any]] | None,
    dependency_kpi_id: str,
) -> list[dict[str, Any]]:
    """Return ratio KPIs that directly reference a basic KPI."""
    target = str(dependency_kpi_id or "").strip()
    return [
        dict(item)
        for item in saved_kpis or []
        if isinstance(item, dict)
        and str(item.get("aggregation", "")).strip().lower() == "ratio"
        and target
        in {
            str(item.get("numerator_kpi_id", "")).strip(),
            str(item.get("denominator_kpi_id", "")).strip(),
        }
    ]


def is_legacy_single_field_aov_kpi(kpi: dict[str, Any]) -> bool:
    """Identify saved legacy AOV definitions that averaged one amount field."""
    return (
        str(kpi.get("kpi_name", "")).strip() == "客单价"
        and str(kpi.get("aggregation", "")).strip().lower() == "avg"
        and str(kpi.get("field_type", "")).strip().lower() == "amount"
        and bool(str(kpi.get("source_field", "")).strip())
    )


def generate_aov_ratio_recommendation(
    saved_kpis: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Recommend one high-confidence saved-KPI AOV ratio, without persistence."""
    saved = [dict(item) for item in saved_kpis or [] if isinstance(item, dict)]
    dependencies = get_ratio_dependency_options(saved)
    numerators = [
        item
        for item in dependencies
        if str(item.get("aggregation", "")).strip().lower() == "sum"
        and str(item.get("field_type", "")).strip().lower() == "amount"
        and _normalize_semantic_name(item.get("kpi_name"))
        in {_normalize_semantic_name(name) for name in _AOV_NUMERATOR_NAMES}
    ]
    denominators = [
        item
        for item in dependencies
        if str(item.get("aggregation", "")).strip().lower()
        in {"sum", "count_distinct"}
        and _normalize_semantic_name(item.get("kpi_name"))
        in {_normalize_semantic_name(name) for name in _AOV_DENOMINATOR_NAMES}
    ]
    if any(str(item.get("kpi_name", "")).strip() == "客单价" for item in saved):
        return {"status": "already_defined", "candidates": [], "message": ""}
    if len(numerators) > 1 or len(denominators) > 1:
        return {
            "status": "ambiguous",
            "candidates": [],
            "message": "检测到多个可能的销售额或客户数量指标，暂不自动推荐客单价，请手动确认分子和分母。",
        }
    if len(numerators) != 1 or len(denominators) != 1:
        return {"status": "insufficient_dependencies", "candidates": [], "message": ""}
    numerator = numerators[0]
    denominator = denominators[0]
    numerator_id = str(numerator.get("kpi_id", "")).strip()
    denominator_id = str(denominator.get("kpi_id", "")).strip()
    if any(
        str(item.get("aggregation", "")).strip().lower() == "ratio"
        and str(item.get("numerator_kpi_id", "")).strip() == numerator_id
        and str(item.get("denominator_kpi_id", "")).strip() == denominator_id
        for item in saved
    ):
        return {"status": "already_defined", "candidates": [], "message": ""}
    candidate = _kpi(
        kpi_name="客单价",
        aggregation="ratio",
        source_field="",
        field_type=infer_ratio_field_type(numerator, denominator),
        category="核心指标",
        description="使用已保存指标计算：销售额 ÷ 成交客户数。",
        enabled=False,
        numerator_kpi_id=numerator_id,
        denominator_kpi_id=denominator_id,
    )
    return {"status": "recommended", "candidates": [candidate], "message": ""}


def get_kpi_source_field_type(
    aggregation: str,
    source_field: str,
    field_mappings: list[dict[str, Any]] | None,
    field_roles: dict[str, Any] | None = None,
) -> str:
    """Return the single valid UI field type for a KPI source selection."""
    if aggregation == "count_rows":
        return "row"

    source_field = str(source_field or "")
    mapping = _mapping_by_column(field_mappings).get(source_field, {})
    mapped_type = str(
        mapping.get("confirmed_type") or mapping.get("inferred_type") or ""
    ).strip()
    normalized_mapping_type = _FIELD_TYPE_ALIASES.get(mapped_type, "")
    role = _field_role_by_column(field_roles).get(source_field)

    if role == "derived_time":
        return "custom"
    if role == "datetime":
        return "date"
    if role == "identifier":
        return "id"
    if role == "numeric":
        return (
            normalized_mapping_type
            if normalized_mapping_type in {"amount", "numeric"}
            else "numeric"
        )
    if role in {"categorical", "boolean"}:
        return (
            normalized_mapping_type
            if normalized_mapping_type
            in {"region", "product", "person", "categorical"}
            else "categorical"
        )
    if role in {"constant", "unsupported"}:
        return "custom"
    return normalized_mapping_type or "custom"


def get_kpi_source_field_options(
    aggregation: str,
    available_fields: list[str] | tuple[str, ...],
    field_mappings: list[dict[str, Any]] | None,
    field_roles: dict[str, Any] | None = None,
    no_source_field_label: str = NO_SOURCE_FIELD_LABEL,
) -> list[str]:
    """Return source fields allowed by the selected KPI aggregation."""
    fields = list(dict.fromkeys(str(field) for field in available_fields))
    if aggregation == "count_rows":
        return [no_source_field_label]
    if aggregation in {"count", "count_distinct"}:
        return fields

    role_by_column = _field_role_by_column(field_roles)
    options = []
    for field in fields:
        role = role_by_column.get(field)
        field_type = get_kpi_source_field_type(
            aggregation,
            field,
            field_mappings,
            field_roles,
        )
        if aggregation in {"sum", "avg"}:
            allowed = role == "numeric" and field_type in {"amount", "numeric"}
        elif aggregation in {"max", "min"}:
            allowed = (
                role in {"numeric", "datetime"}
                and field_type in {"amount", "numeric", "date"}
            )
        else:
            allowed = False
        if allowed:
            options.append(field)
    return options


def resolve_kpi_source_selection(
    aggregation: str,
    current_source_field: str | None,
    available_fields: list[str] | tuple[str, ...],
    field_mappings: list[dict[str, Any]] | None,
    field_roles: dict[str, Any] | None = None,
    no_source_field_label: str = NO_SOURCE_FIELD_LABEL,
) -> dict[str, Any]:
    """Resolve a valid source option and its non-editable field type for the UI."""
    options = get_kpi_source_field_options(
        aggregation,
        available_fields,
        field_mappings,
        field_roles,
        no_source_field_label,
    )
    selected_option = str(current_source_field or "")
    if selected_option not in options:
        selected_option = options[0] if options else ""
    source_field = "" if aggregation == "count_rows" else selected_option
    return {
        "options": options,
        "selected_option": selected_option,
        "source_field": source_field,
        "field_type": get_kpi_source_field_type(
            aggregation,
            source_field,
            field_mappings,
            field_roles,
        ),
        "has_compatible_fields": bool(options),
    }


def generate_kpi_candidates(
    field_mappings: list[dict[str, Any]] | None,
    dataframe: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    """Generate project-level KPI definition candidates from confirmed field mappings."""
    mappings = [
        item
        for item in field_mappings or []
        if item.get("column_name") and item.get("confirmed_type") != "忽略字段"
    ]
    amount_fields = [
        field
        for field in dict.fromkeys(_columns_by_type(mappings, "金额字段"))
        if not is_unit_price_field(field)
    ]
    quantity_fields = _additive_quantity_fields(mappings, dataframe)
    id_fields = _columns_by_type(mappings, "ID字段")
    date_fields = [
        field
        for field in _columns_by_type(mappings, "日期字段")
        if not _is_derived_time_mapping(field, dataframe)
    ]
    person_fields = _columns_by_type(mappings, "人员字段")
    product_fields = _columns_by_type(mappings, "产品字段")
    region_fields = _columns_by_type(mappings, "区域字段")

    candidates: list[dict[str, Any]] = [
        _kpi(
            kpi_name="记录数",
            aggregation="count_rows",
            source_field="",
            field_type="row",
            category="核心指标",
            description=(
                "统计当前分析数据集的记录行数。记录数不等同于订单数，"
                "数据合并可能导致记录重复展开。"
            ),
            enabled=False,
        )
    ]
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
                kpi_name=f"{field}平均值",
                aggregation="avg",
                source_field=field,
                field_type="amount",
                category="核心指标",
                description=f"统计金额字段 `{field}` 的平均值。",
                enabled=False,
            )
        )

    existing_sum_sources = set(amount_fields)
    for field in quantity_fields:
        if field in existing_sum_sources:
            continue
        candidates.append(
            _kpi(
                kpi_name=field,
                aggregation="sum",
                source_field=field,
                field_type="numeric",
                category="核心指标",
                description=(
                    f"根据数量字段 `{field}` 推荐求和指标。"
                    "请确认当前数据集粒度，数据合并或重复展开可能导致数量被重复累计。"
                ),
                enabled=False,
            )
        )
        existing_sum_sources.add(field)

    for field in id_fields:
        candidates.append(
            _kpi(
                kpi_name=_count_kpi_name(field),
                aggregation="count_distinct",
                source_field=field,
                field_type="id",
                category="核心指标",
                description=f"统计 {field} 中非空唯一值的数量",
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
    saved_kpis: list[dict[str, Any]] | None = None,
    kpi_by_id: dict[str, dict[str, Any]] | None = None,
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

    source_field = str(source.get("source_field", "")).strip()
    if aggregation == "ratio":
        source_field = ""
    normalized = {
        "kpi_id": str(source.get("kpi_id") or uuid.uuid4().hex),
        "kpi_name": str(source.get("kpi_name", "")).strip(),
        "aggregation": aggregation,
        "source_field": source_field,
        "numerator_kpi_id": str(source.get("numerator_kpi_id") or "").strip(),
        "denominator_kpi_id": str(source.get("denominator_kpi_id") or "").strip(),
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
            saved_kpis=saved_kpis,
            kpi_by_id=kpi_by_id,
        )
    )
    return normalized


def validate_kpi_definition(
    kpi: dict[str, Any],
    available_fields: list[str] | tuple[str, ...] | set[str] | None = None,
    field_mappings: list[dict[str, Any]] | None = None,
    saved_kpis: list[dict[str, Any]] | None = None,
    kpi_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate one KPI definition without project or UI dependencies."""
    source = dict(kpi) if isinstance(kpi, dict) else {}
    lifecycle_status = str(
        source.get("lifecycle_status", "saved")
    ).strip().lower()
    kpi_name = str(source.get("kpi_name", "")).strip()
    aggregation = str(source.get("aggregation", "")).strip().lower()
    source_field = str(source.get("source_field", "")).strip()
    kpi_id = str(source.get("kpi_id", "")).strip()
    numerator_kpi_id = str(source.get("numerator_kpi_id") or "").strip()
    denominator_kpi_id = str(source.get("denominator_kpi_id") or "").strip()

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

    if aggregation == "ratio" and lifecycle_status != "candidate":
        if not numerator_kpi_id:
            invalid_messages.append("比率 KPI 必须指定分子 KPI。")
        if not denominator_kpi_id:
            invalid_messages.append("比率 KPI 必须指定分母 KPI。")
        if numerator_kpi_id and numerator_kpi_id == denominator_kpi_id:
            invalid_messages.append("比率 KPI 的分子和分母不能引用同一个 KPI。")
        if kpi_id and numerator_kpi_id == kpi_id:
            invalid_messages.append("比率 KPI 不能将自身作为分子。")
        if kpi_id and denominator_kpi_id == kpi_id:
            invalid_messages.append("比率 KPI 不能将自身作为分母。")

        dependency_by_id = _dependency_kpi_by_id(saved_kpis, kpi_by_id)
        if dependency_by_id is not None:
            for dependency_label, dependency_id in (
                ("分子", numerator_kpi_id),
                ("分母", denominator_kpi_id),
            ):
                if not dependency_id:
                    continue
                dependency = dependency_by_id.get(dependency_id)
                if dependency is None:
                    invalid_messages.append(
                        f"比率 KPI 的{dependency_label}依赖不存在：{dependency_id}。"
                    )
                    continue
                dependency_lifecycle = str(
                    dependency.get("lifecycle_status", "saved")
                ).strip().lower()
                dependency_aggregation = str(
                    dependency.get("aggregation", "")
                ).strip().lower()
                if dependency_lifecycle != "saved":
                    invalid_messages.append(
                        f"比率 KPI 的{dependency_label}依赖必须是已保存 KPI："
                        f"{dependency_id}。"
                    )
                if dependency_aggregation == "ratio":
                    invalid_messages.append(
                        f"V1 暂不支持嵌套比率指标：{dependency_id}。"
                    )
                elif dependency_aggregation == RESERVED_AGGREGATION:
                    invalid_messages.append(
                        f"预留 KPI 不能作为比率{dependency_label}：{dependency_id}。"
                    )
                elif dependency_aggregation not in BASIC_KPI_AGGREGATIONS:
                    invalid_messages.append(
                        f"比率 KPI 的{dependency_label}聚合方式无效："
                        f"{dependency_id}。"
                    )
                dependency_status = str(
                    dependency.get("validation_status", "")
                ).strip().lower()
                current_dependency_status = validate_kpi_definition(
                    dependency,
                    available_fields=available_fields,
                    field_mappings=field_mappings,
                )["validation_status"]
                if (
                    dependency_status not in {"", "valid"}
                    or current_dependency_status != "valid"
                ):
                    invalid_messages.append(
                        f"比率 KPI 的{dependency_label}依赖未通过校验："
                        f"{dependency_id}。"
                    )

    source_required_aggregations = set(BASIC_KPI_AGGREGATIONS) - {
        "count_rows"
    }
    if aggregation in source_required_aggregations and not source_field:
        invalid_messages.append("来源字段不能为空。")
    elif aggregation in source_required_aggregations:
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
        elif aggregation == "count_distinct" and resolved_field_type not in {
            "id",
            "date",
            "categorical",
            "person",
            "product",
            "region",
            "custom",
            "numeric",
            "amount",
        }:
            invalid_messages.append(
                "聚合方式 count_distinct 不适用于字段类型 "
                f"{resolved_field_type or 'unknown'}。"
            )
    elif aggregation == "count_rows":
        resolved_field_type = _resolved_field_type(source, None)
        if resolved_field_type not in {"row", "dataset", "custom"}:
            invalid_messages.append(
                "聚合方式 count_rows 仅适用于 row、dataset 或 custom 字段类型。"
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


def calculate_basic_kpi(
    df: pd.DataFrame,
    kpi_definition: dict[str, Any],
) -> dict[str, Any]:
    """Execute one basic KPI definition without mutating the DataFrame."""
    aggregation = str(kpi_definition.get("aggregation", "")).strip().lower()
    source_field = str(kpi_definition.get("source_field", "")).strip()
    base_result = {
        "status": "invalid_definition",
        "value": None,
        "aggregation": aggregation,
        "source_field": source_field,
        "record_count": int(len(df)),
        "message": "",
    }

    if aggregation == RESERVED_AGGREGATION:
        return {
            **base_result,
            "status": "unsupported",
            "message": RESERVED_VALIDATION_MESSAGE,
        }
    if aggregation == "ratio":
        return {
            **base_result,
            "status": "unsupported",
            "message": "比率 KPI 请使用统一比率执行函数计算。",
        }
    if aggregation not in SUPPORTED_AGGREGATIONS:
        return {
            **base_result,
            "message": f"不支持的聚合方式：{aggregation or '空值'}。",
        }
    if aggregation == "count_rows":
        return {
            **base_result,
            "status": "ok",
            "value": int(len(df)),
            "source_field": "",
            "message": "统计当前筛选数据集的记录行数。",
        }
    if not source_field:
        return {**base_result, "message": "来源字段不能为空。"}
    if source_field not in df.columns:
        return {
            **base_result,
            "status": "missing_field",
            "message": f"来源字段不存在：{source_field}。",
        }

    series = df[source_field]
    try:
        if aggregation == "count":
            value = int(series.notna().sum())
        elif aggregation == "count_distinct":
            value = int(series.dropna().nunique())
        elif aggregation in {"sum", "avg"}:
            numeric = pd.to_numeric(series, errors="coerce")
            value = numeric.sum() if aggregation == "sum" else numeric.mean()
        else:
            valid = series.dropna()
            value = valid.max() if aggregation == "max" else valid.min()
    except (TypeError, ValueError) as exc:
        return {
            **base_result,
            "message": f"当前字段无法执行 {aggregation}：{exc}",
        }
    return {
        **base_result,
        "status": "ok",
        "value": _json_safe_scalar(value),
        "message": "计算完成。",
    }


def calculate_ratio_kpi(
    df: pd.DataFrame,
    ratio_kpi: dict[str, Any],
    kpi_by_id: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    """Calculate one non-nested ratio KPI from two existing basic KPIs."""
    source = dict(ratio_kpi) if isinstance(ratio_kpi, dict) else {}
    numerator_kpi_id = str(source.get("numerator_kpi_id") or "").strip()
    denominator_kpi_id = str(source.get("denominator_kpi_id") or "").strip()
    base_result = {
        "status": "invalid_definition",
        "value": None,
        "aggregation": "ratio",
        "numerator_kpi_id": numerator_kpi_id,
        "denominator_kpi_id": denominator_kpi_id,
        "numerator_value": None,
        "denominator_value": None,
        "message": "",
    }
    if str(source.get("aggregation", "")).strip().lower() != "ratio":
        return {**base_result, "status": "unsupported", "message": "当前定义不是比率 KPI。"}
    validation = validate_kpi_definition(source, kpi_by_id=kpi_by_id)
    if validation["validation_status"] != "valid":
        missing_ids = [
            dependency_id
            for dependency_id in (numerator_kpi_id, denominator_kpi_id)
            if dependency_id and dependency_id not in (kpi_by_id or {})
        ]
        status = "missing_dependency" if missing_ids else "invalid_definition"
        return {
            **base_result,
            "status": status,
            "message": "；".join(validation["validation_messages"]),
        }

    numerator = (kpi_by_id or {}).get(numerator_kpi_id)
    denominator = (kpi_by_id or {}).get(denominator_kpi_id)
    if numerator is None or denominator is None:
        return {
            **base_result,
            "status": "missing_dependency",
            "message": "比率 KPI 缺少分子或分母依赖。",
        }

    numerator_result = calculate_basic_kpi(df, numerator)
    if numerator_result.get("status") != "ok":
        return {
            **base_result,
            "status": "dependency_error",
            "message": f"分子 KPI 计算失败：{numerator_result.get('message', '')}",
        }
    numerator_value = numerator_result.get("value")
    denominator_result = calculate_basic_kpi(df, denominator)
    if denominator_result.get("status") != "ok":
        return {
            **base_result,
            "status": "dependency_error",
            "numerator_value": numerator_value,
            "message": f"分母 KPI 计算失败：{denominator_result.get('message', '')}",
        }
    denominator_value = denominator_result.get("value")
    values = {
        "numerator_value": numerator_value,
        "denominator_value": denominator_value,
    }
    if numerator_value is None or denominator_value is None:
        return {
            **base_result,
            **values,
            "status": "dependency_error",
            "message": "分子或分母 KPI 当前没有可用于计算的数值。",
        }
    try:
        numeric_numerator = float(numerator_value)
        numeric_denominator = float(denominator_value)
    except (TypeError, ValueError, OverflowError):
        return {
            **base_result,
            **values,
            "status": "dependency_error",
            "message": "分子或分母 KPI 当前值无法执行比率计算。",
        }
    if not math.isfinite(numeric_numerator) or not math.isfinite(numeric_denominator):
        return {
            **base_result,
            "numerator_value": (
                numerator_value if math.isfinite(numeric_numerator) else None
            ),
            "denominator_value": (
                denominator_value if math.isfinite(numeric_denominator) else None
            ),
            "status": "dependency_error",
            "message": "分子或分母 KPI 当前值不是有限数值。",
        }
    try:
        if numeric_denominator == 0:
            return {
                **base_result,
                **values,
                "status": "zero_denominator",
                "message": "分母指标当前值为 0，无法计算比率。",
            }
        value = numeric_numerator / numeric_denominator
    except (ArithmeticError, OverflowError):
        return {
            **base_result,
            **values,
            "status": "dependency_error",
            "message": "分子或分母 KPI 当前值无法执行比率计算。",
        }
    if not math.isfinite(value):
        return {
            **base_result,
            **values,
            "status": "dependency_error",
            "message": "比率计算结果不是有限数值。",
        }
    return {
        **base_result,
        **values,
        "status": "ok",
        "value": value,
        "message": "比率计算完成。",
    }


def missing_entity_id_candidate_names(
    candidates: list[dict[str, Any]] | None,
) -> list[str]:
    """Return missing order/customer distinct-count candidate names."""
    candidate_names = {
        str(item.get("kpi_name", ""))
        for item in candidates or []
        if isinstance(item, dict)
        and item.get("aggregation") == "count_distinct"
    }
    return [
        name for name in ("订单数", "客户数") if name not in candidate_names
    ]


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
    numerator_kpi_id: str = "",
    denominator_kpi_id: str = "",
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
            "numerator_kpi_id": numerator_kpi_id,
            "denominator_kpi_id": denominator_kpi_id,
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
    if any(
        keyword in lowered
        for keyword in (
            "销售",
            "员工",
            "人员",
            "staff",
            "employee",
            "salesperson",
            "sales_id",
        )
    ):
        return "销售人员数"
    return f"{field}去重数量"


def _columns_by_type(mappings: list[dict[str, Any]], field_type: str) -> list[str]:
    return [
        str(item["column_name"])
        for item in mappings
        if item.get("confirmed_type") == field_type
    ]


def _additive_quantity_fields(
    mappings: list[dict[str, Any]],
    dataframe: pd.DataFrame | None,
) -> list[str]:
    mapping_by_column = _mapping_by_column(mappings)
    role_by_column: dict[str, str] = {}
    if isinstance(dataframe, pd.DataFrame):
        confirmed_types = {
            column: mapping.get("confirmed_type")
            for column, mapping in mapping_by_column.items()
            if column in dataframe.columns
        }
        role_by_column = build_exploration_field_roles(
            dataframe,
            confirmed_type_by_column=confirmed_types,
        )["role_by_column"]
        candidate_fields = [str(column) for column in dataframe.columns]
    else:
        candidate_fields = list(mapping_by_column)

    quantity_fields = []
    for field in candidate_fields:
        mapping = mapping_by_column.get(field, {})
        mapped_type = _FIELD_TYPE_ALIASES.get(
            str(
                mapping.get("confirmed_type")
                or mapping.get("inferred_type")
                or ""
            ).strip(),
            "",
        )
        role = role_by_column.get(field)
        if mapped_type == "amount":
            continue
        if mapped_type in {"id", "date", "row", "dataset"}:
            continue
        if role in {
            "identifier",
            "datetime",
            "derived_time",
            "constant",
            "boolean",
            "unsupported",
        }:
            continue
        if role != "numeric" and mapped_type != "numeric":
            continue
        if isinstance(dataframe, pd.DataFrame) and field in dataframe.columns:
            series = dataframe[field]
            if (
                pd.api.types.is_bool_dtype(series.dtype)
                or series.dropna().empty
                or series.nunique(dropna=True) <= 1
                or is_derived_time_column(field, series)
            ):
                continue
        if is_additive_quantity_field(field):
            quantity_fields.append(field)
    return list(dict.fromkeys(quantity_fields))


def _field_name_tokens(column_name: str) -> list[str]:
    with_camel_boundaries = re.sub(
        r"(?<=[a-z0-9])(?=[A-Z])",
        " ",
        str(column_name or ""),
    )
    return re.findall(r"[a-z0-9]+", with_camel_boundaries.casefold())


def _normalize_semantic_name(value: Any) -> str:
    return re.sub(r"[\s_\-]+", "", str(value or "").strip().casefold())


def _is_derived_time_mapping(
    column_name: str,
    dataframe: pd.DataFrame | None,
) -> bool:
    return bool(
        dataframe is not None
        and column_name in dataframe.columns
        and is_derived_time_column(column_name, dataframe[column_name])
    )


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


def _dependency_kpi_by_id(
    saved_kpis: list[dict[str, Any]] | None,
    kpi_by_id: dict[str, dict[str, Any]] | None,
) -> dict[str, dict[str, Any]] | None:
    if kpi_by_id is not None:
        return {
            str(kpi_id): dict(kpi)
            for kpi_id, kpi in kpi_by_id.items()
            if isinstance(kpi, dict)
        }
    if saved_kpis is None:
        return None
    return {
        str(item.get("kpi_id", "")): dict(item)
        for item in saved_kpis
        if isinstance(item, dict) and item.get("kpi_id")
    }


def _field_role_by_column(
    field_roles: dict[str, Any] | None,
) -> dict[str, str]:
    if not isinstance(field_roles, dict):
        return {}
    role_by_column = field_roles.get("role_by_column", field_roles)
    if not isinstance(role_by_column, dict):
        return {}
    return {
        str(column): str(role)
        for column, role in role_by_column.items()
        if column is not None and role is not None
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


def _json_safe_scalar(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _kpi_key(kpi: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
    return (
        str(kpi.get("kpi_name", "")),
        str(kpi.get("aggregation", "")),
        str(kpi.get("source_field", "")),
        str(kpi.get("category", "")),
        str(kpi.get("numerator_kpi_id", "")),
        str(kpi.get("denominator_kpi_id", "")),
    )
