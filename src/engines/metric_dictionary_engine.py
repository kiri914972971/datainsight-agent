from __future__ import annotations

import re
import uuid
from typing import Any


METRIC_CATEGORIES = ("核心指标", "时间指标", "维度指标")

DEFAULT_METRIC_ALIASES = {
    "销售额": ["GMV", "Revenue", "Sales", "销售额", "成交金额", "订单金额", "收入"],
    "订单数": ["订单量", "订单数量", "Orders", "Order Count", "订单ID"],
    "客户数": ["用户数", "客户数量", "Customer Count", "Users", "客户ID"],
    "客单价": ["AOV", "Average Order Value", "客均价", "平均订单金额"],
    "同比": ["YoY", "同比增长", "同比变化"],
    "环比": ["MoM", "QoQ", "环比增长", "环比变化"],
    "增长率": ["Growth Rate", "增速", "增长"],
    "区域销售额": ["区域成交金额", "地区销售额", "大区销售额"],
    "产品销售额": ["产品成交金额", "SKU销售额", "商品销售额"],
    "销售员销售额": ["人员销售额", "员工销售额", "业务员销售额"],
}


def generate_metric_candidates_from_kpis(
    kpis: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Generate business metric dictionary candidates from KPI definitions."""
    candidates = []
    for kpi in kpis or []:
        kpi_name = str(kpi.get("kpi_name", "")).strip()
        if not kpi_name:
            continue
        candidates.append(
            normalize_metric_definition(
                {
                    "metric_name": kpi_name,
                    "metric_type": _metric_type_from_kpi(kpi),
                    "business_definition": _default_definition(kpi),
                    "aliases": _default_aliases(kpi),
                    "linked_kpi_id": str(kpi.get("kpi_id", "")),
                    "linked_kpi_name": kpi_name,
                    "enabled": bool(kpi.get("enabled", True)),
                    "created_by": "auto",
                }
            )
        )
    return _deduplicate_metrics(candidates)


def merge_metric_candidates(
    existing_metrics: list[dict[str, Any]] | None,
    candidates: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Preserve user-defined metric records while adding new KPI-derived candidates."""
    merged = {
        _metric_key(item): normalize_metric_definition(item)
        for item in existing_metrics or []
        if item.get("metric_name")
    }
    for candidate in candidates or []:
        normalized = normalize_metric_definition(candidate)
        merged.setdefault(_metric_key(normalized), normalized)
    return list(merged.values())


def normalize_metric_definition(metric: dict[str, Any]) -> dict[str, Any]:
    metric_type = str(metric.get("metric_type", "核心指标")).strip()
    if metric_type not in METRIC_CATEGORIES:
        metric_type = "核心指标"
    aliases = _normalize_aliases(metric.get("aliases", []))
    metric_name = str(metric.get("metric_name", "")).strip()
    return {
        "metric_id": str(metric.get("metric_id") or uuid.uuid4().hex),
        "metric_name": metric_name,
        "aliases": aliases,
        "metric_type": metric_type,
        "business_definition": str(metric.get("business_definition", "")).strip(),
        "linked_kpi_id": str(metric.get("linked_kpi_id", "")).strip(),
        "linked_kpi_name": str(metric.get("linked_kpi_name", "")).strip(),
        "enabled": bool(metric.get("enabled", True)),
        "created_by": str(metric.get("created_by", "user")),
        "updated_at": str(metric.get("updated_at", "")),
    }


def alias_matches_metric(metric: dict[str, Any], alias: str) -> bool:
    """Return whether a metric name or alias matches a user/business term."""
    target = _normalize_lookup(alias)
    if not target:
        return False
    names = [metric.get("metric_name", ""), *(metric.get("aliases") or [])]
    return any(_normalize_lookup(name) == target for name in names)


def split_aliases(value: Any) -> list[str]:
    return _normalize_aliases(value)


def _metric_type_from_kpi(kpi: dict[str, Any]) -> str:
    category = str(kpi.get("category", "")).strip()
    return category if category in METRIC_CATEGORIES else "核心指标"


def _default_definition(kpi: dict[str, Any]) -> str:
    name = str(kpi.get("kpi_name", "")).strip()
    source_field = str(kpi.get("source_field", "")).strip()
    aggregation = str(kpi.get("aggregation", "")).upper()
    if name == "销售额":
        return "统计订单成交金额总和"
    if name == "订单数":
        return "统计订单数量"
    if name == "客户数":
        return "统计成交客户数量"
    if name == "客单价":
        return "统计单个客户或订单的平均成交金额"
    if name in {"同比", "环比", "增长率"}:
        return f"基于 {source_field or '日期字段'} 的时间对比指标，当前版本仅作为指标字典预留"
    if source_field:
        return f"基于 {source_field} 的 {name} 指标定义，关联 KPI 聚合方式为 {aggregation}"
    return f"{name} 的项目级业务指标定义"


def _default_aliases(kpi: dict[str, Any]) -> list[str]:
    kpi_name = str(kpi.get("kpi_name", "")).strip()
    source_field = str(kpi.get("source_field", "")).strip()
    aliases = list(DEFAULT_METRIC_ALIASES.get(kpi_name, []))
    if source_field:
        aliases.append(source_field)
    return _normalize_aliases(aliases)


def _normalize_aliases(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_aliases = re.split(r"[,，;；\n]+", value)
    elif isinstance(value, list):
        raw_aliases = value
    else:
        raw_aliases = []

    aliases = []
    seen = set()
    for raw_alias in raw_aliases:
        alias = str(raw_alias).strip()
        key = _normalize_lookup(alias)
        if alias and key and key not in seen:
            aliases.append(alias)
            seen.add(key)
    return aliases


def _normalize_lookup(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().casefold())


def _deduplicate_metrics(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return list({_metric_key(item): item for item in metrics}.values())


def _metric_key(metric: dict[str, Any]) -> str:
    return _normalize_lookup(metric.get("metric_name", ""))
