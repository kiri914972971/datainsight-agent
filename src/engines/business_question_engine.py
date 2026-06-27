from __future__ import annotations

import re
from typing import Any

import pandas as pd


INTENT_TYPES = ("ranking", "trend", "comparison", "contribution", "summary", "unknown")
DIMENSION_KEYWORDS = {
    "区域字段": ("区域", "地区", "省份", "城市", "大区", "华东", "华南", "华北", "华中", "西南", "西北"),
    "产品字段": ("产品", "商品", "SKU", "sku", "品类", "类别"),
    "人员字段": ("销售员", "员工", "业务员", "顾问", "人员"),
    "日期字段": ("日期", "时间", "每天", "每日", "按天", "按月", "月份"),
}
DIMENSION_TYPES = ("区域字段", "产品字段", "人员字段", "日期字段")


def parse_business_question(question: str, project_context: dict[str, Any]) -> dict[str, Any]:
    original_question = str(question or "").strip()
    metric_dictionary = project_context.get("metric_dictionary", [])
    kpis = project_context.get("kpis", [])
    field_mappings = project_context.get("field_mappings", [])
    dataset_preview = project_context.get("dataset_preview")
    dataset_columns = project_context.get("dataset_columns", [])

    intent_type = detect_intent(original_question)
    metric_result = detect_metric(original_question, metric_dictionary, kpis)
    dimension_result = detect_dimension(original_question, field_mappings, dataset_columns)
    time_range = detect_time_range(original_question)
    sort_result = detect_sort_and_topn(original_question)
    comparison = detect_comparison(original_question)
    filters = detect_filters(original_question, dataset_preview, field_mappings)
    aggregation = _aggregation_for_metric(metric_result, kpis)

    warnings = []
    if not metric_result["metric"]:
        warnings.append("未识别到明确业务指标。")
    if intent_type == "unknown":
        warnings.append("暂无法识别问题意图，请补充指标、维度或分析方式。")
    if not dimension_result["dimension"] and intent_type in {"ranking", "comparison", "contribution", "trend"}:
        warnings.append("未识别到明确分析维度。")

    confidence = _calculate_confidence(
        metric=metric_result["metric"],
        dimension=dimension_result["dimension"],
        intent_type=intent_type,
        time_range=time_range,
        sort=sort_result["sort"],
        filters=filters,
    )

    return {
        "original_question": original_question,
        "intent_type": intent_type,
        "metric": metric_result["metric"],
        "metric_alias_matched": metric_result["metric_alias_matched"],
        "dimension": dimension_result["dimension"],
        "filters": filters,
        "time_range": time_range,
        "comparison": comparison,
        "sort": sort_result["sort"],
        "top_n": sort_result["top_n"],
        "aggregation": aggregation,
        "confidence": confidence,
        "warnings": warnings,
    }


def detect_intent(question: str) -> str:
    text = str(question or "").strip()
    if not text:
        return "unknown"
    if any(keyword in text for keyword in ("贡献", "占比", "大部分", "构成", "占了多少")):
        return "contribution"
    if any(keyword in text for keyword in ("同比", "环比", "较上月", "较上周", "比去年", "对比", "比较", "相比")):
        return "comparison"
    if re.search(r".+和.+哪个.*(更|高|低|多|少)", text):
        return "comparison"
    if any(keyword in text for keyword in ("趋势", "走势", "每天", "每日", "逐日", "按日", "按月", "变化怎么样")):
        return "trend"
    if any(keyword in text for keyword in ("最高", "最多", "最大", "最低", "最少", "最小", "Top", "top", "排名", "前")):
        return "ranking"
    if any(keyword in text for keyword in ("整体", "表现", "概况", "总结", "怎么样", "情况")):
        return "summary"
    return "unknown"


def detect_metric(
    question: str,
    metric_dictionary: list[dict[str, Any]] | None,
    kpis: list[dict[str, Any]] | None,
) -> dict[str, str]:
    text = str(question or "")
    metric_candidates = []
    for metric in metric_dictionary or []:
        metric_name = str(metric.get("metric_name", "")).strip()
        names = [metric_name, str(metric.get("linked_kpi_name", "")).strip()]
        names.extend(str(alias).strip() for alias in metric.get("aliases", []))
        for name in names:
            if name:
                metric_candidates.append(
                    {
                        "candidate": name,
                        "metric": metric_name,
                        "source": "metric_dictionary",
                    }
                )

    for kpi in kpis or []:
        kpi_name = str(kpi.get("kpi_name", "")).strip()
        source_field = str(kpi.get("source_field", "")).strip()
        for name in (kpi_name, source_field):
            if name:
                metric_candidates.append(
                    {
                        "candidate": name,
                        "metric": kpi_name,
                        "source": "kpi",
                    }
                )

    matched = _longest_text_match(text, metric_candidates, "candidate")
    if not matched:
        return {"metric": "", "metric_alias_matched": "", "source": ""}
    return {
        "metric": matched["metric"],
        "metric_alias_matched": matched["candidate"],
        "source": matched["source"],
    }


def detect_dimension(
    question: str,
    field_mappings: list[dict[str, Any]] | None,
    dataset_columns: list[str] | None,
) -> dict[str, str]:
    text = str(question or "")
    mappings = field_mappings or []
    mapped_columns = [
        {
            "candidate": str(item.get("column_name", "")).strip(),
            "dimension": str(item.get("column_name", "")).strip(),
            "field_type": str(item.get("confirmed_type", "")).strip(),
        }
        for item in mappings
        if item.get("column_name") and item.get("confirmed_type") in DIMENSION_TYPES
    ]
    column_match = _longest_text_match(text, mapped_columns, "candidate")
    if column_match:
        return {"dimension": column_match["dimension"], "matched_by": "field_name"}

    dataset_candidates = [
        {"candidate": str(column), "dimension": str(column), "field_type": ""}
        for column in dataset_columns or []
    ]
    dataset_match = _longest_text_match(text, dataset_candidates, "candidate")
    if dataset_match:
        return {"dimension": dataset_match["dimension"], "matched_by": "dataset_column"}

    for field_type, keywords in DIMENSION_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            mapped = [
                str(item.get("column_name", "")).strip()
                for item in mappings
                if item.get("confirmed_type") == field_type and item.get("column_name")
            ]
            return {
                "dimension": mapped[0] if mapped else field_type,
                "matched_by": "field_type",
            }
    return {"dimension": "", "matched_by": ""}


def detect_time_range(question: str) -> str:
    text = str(question or "")
    ordered_patterns = [
        r"最近\s*\d+\s*天",
        r"最近\s*\d+\s*周",
        r"最近\s*\d+\s*个月",
        r"\d{4}\s*年\s*\d{1,2}\s*月",
        r"\d{1,2}\s*月",
    ]
    for pattern in ordered_patterns:
        match = re.search(pattern, text)
        if match:
            return re.sub(r"\s+", "", match.group(0))
    fixed_terms = ("今天", "昨天", "本周", "上周", "本月", "上月", "本季度", "今年", "最近")
    for term in fixed_terms:
        if term in text:
            return term
    return ""


def detect_sort_and_topn(question: str) -> dict[str, Any]:
    text = str(question or "")
    sort = ""
    if any(keyword in text for keyword in ("最高", "最多", "最大", "Top", "top", "排名", "前")):
        sort = "desc"
    if any(keyword in text for keyword in ("最低", "最少", "最小")):
        sort = "asc"

    top_n = None
    patterns = (
        r"(?:Top|top)\s*(\d+)",
        r"前\s*(\d+)",
        r"(?:最高|最多|最大|最低|最少|最小)的?\s*(\d+)\s*个",
        r"哪\s*(\d+)\s*个",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            top_n = int(match.group(1))
            break
    if top_n is None and sort:
        top_n = 1
    return {"sort": sort, "top_n": top_n}


def detect_comparison(question: str) -> str:
    text = str(question or "")
    if "同比" in text or "比去年" in text:
        return "同比"
    if "环比" in text or "较上月" in text or "较上周" in text:
        return "环比"
    if "增长" in text or "下降" in text or "变化" in text:
        return "增长变化"
    return ""


def detect_filters(
    question: str,
    dataset_preview: Any,
    field_mappings: list[dict[str, Any]] | None,
) -> list[dict[str, str]]:
    dataframe = _to_dataframe(dataset_preview)
    if dataframe.empty:
        return []
    text = str(question or "")
    candidate_fields = _filter_candidate_fields(dataframe, field_mappings)
    filters = []
    for field in candidate_fields:
        if field not in dataframe.columns:
            continue
        values = dataframe[field].dropna().astype(str).unique().tolist()[:200]
        matched_values = [
            value
            for value in values
            if value and len(value) >= 2 and value in text
        ]
        if matched_values:
            filters.append(
                {
                    "field": str(field),
                    "operator": "==",
                    "value": sorted(matched_values, key=len, reverse=True)[0],
                }
            )
    return filters


def _aggregation_for_metric(metric_result: dict[str, str], kpis: list[dict[str, Any]] | None) -> str:
    metric = metric_result.get("metric", "")
    if not metric:
        return ""
    for kpi in kpis or []:
        if kpi.get("kpi_name") == metric:
            return str(kpi.get("aggregation", ""))
    return ""


def _calculate_confidence(
    metric: str,
    dimension: str,
    intent_type: str,
    time_range: str,
    sort: str,
    filters: list[dict[str, str]],
) -> float:
    confidence = 0.0
    if metric:
        confidence += 0.35
    if dimension:
        confidence += 0.25
    if intent_type != "unknown":
        confidence += 0.20
    if time_range or sort:
        confidence += 0.10
    if filters:
        confidence += 0.10
    return round(min(confidence, 1.0), 2)


def _longest_text_match(
    question: str,
    candidates: list[dict[str, Any]],
    candidate_key: str,
) -> dict[str, Any] | None:
    normalized_question = _normalize(question)
    matches = []
    for candidate in candidates:
        value = str(candidate.get(candidate_key, "")).strip()
        if not value:
            continue
        if _normalize(value) in normalized_question:
            matches.append(candidate)
    if not matches:
        return None
    return sorted(matches, key=lambda item: len(str(item.get(candidate_key, ""))), reverse=True)[0]


def _filter_candidate_fields(
    dataframe: pd.DataFrame,
    field_mappings: list[dict[str, Any]] | None,
) -> list[str]:
    mapped_fields = [
        str(item.get("column_name", "")).strip()
        for item in field_mappings or []
        if item.get("confirmed_type") in {"区域字段", "产品字段", "人员字段", "类别字段"}
    ]
    object_fields = [
        str(column)
        for column in dataframe.columns
        if pd.api.types.is_object_dtype(dataframe[column])
        and str(column) not in mapped_fields
    ]
    return mapped_fields + object_fields


def _to_dataframe(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value
    if isinstance(value, list):
        return pd.DataFrame(value)
    if isinstance(value, dict):
        return pd.DataFrame(value)
    return pd.DataFrame()


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").casefold())
