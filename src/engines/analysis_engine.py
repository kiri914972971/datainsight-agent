from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src import project_workspace
from src.services.current_dataset_service import load_current_analysis_dataframe
from src.services.field_mapping_service import load_field_mappings
from src.services.kpi_service import load_kpi_definitions, merged_project_kpis
from src.services.metric_dictionary_service import load_metric_dictionary, merged_project_metrics


SUPPORTED_AGGREGATIONS = {"sum", "count", "avg", "max", "min"}
RESULT_FILE = "analysis_result.json"


def execute_analysis(project_id: str, parsed_intent: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    try:
        dataframe = load_current_analysis_dataframe(project_id)
        data_source = "current_analysis_dataset"
    except Exception as exc:
        result = _failure_result(parsed_intent, [f"无法加载当前分析数据集：{exc}"])
        _save_analysis_result(project_id, parsed_intent, result)
        return result

    context = _load_project_context(project_id)
    original_rows = len(dataframe)
    metric_field = _resolve_metric_field(
        dataframe,
        parsed_intent,
        context["metric_dictionary"],
        context["kpis"],
        context["field_mappings"],
    )
    dimension_field = _resolve_dimension_field(
        dataframe,
        parsed_intent.get("dimension", ""),
        context["field_mappings"],
    )
    aggregation = _normalize_aggregation(parsed_intent.get("aggregation"))

    if not metric_field and aggregation != "count":
        warnings.append(f"未能定位指标字段：{parsed_intent.get('metric') or '未提供'}")
        result = _failure_result(parsed_intent, warnings)
        _save_analysis_result(project_id, parsed_intent, result)
        return result
    if parsed_intent.get("dimension") and not dimension_field:
        warnings.append(f"未能定位维度字段：{parsed_intent.get('dimension')}")

    filtered_df = dataframe.copy()
    filtered_df, time_warnings = _apply_time_filter(
        filtered_df,
        parsed_intent.get("time_range", ""),
        context["field_mappings"],
    )
    warnings.extend(time_warnings)
    filtered_df, filter_warnings = _apply_filters(
        filtered_df,
        parsed_intent.get("filters", []),
    )
    warnings.extend(filter_warnings)

    if filtered_df.empty:
        warnings.append("过滤后没有可分析的数据。")
        result = {
            "success": True,
            "rows": [],
            "summary": {
                "original_rows": original_rows,
                "filtered_rows": 0,
                "result_rows": 0,
                "metric": parsed_intent.get("metric", ""),
                "metric_field": metric_field,
                "dimension": parsed_intent.get("dimension", ""),
                "dimension_field": dimension_field,
                "aggregation": aggregation,
                "warnings": warnings,
            },
            "metadata": _metadata(project_id, data_source, parsed_intent),
            "warnings": warnings,
        }
        _save_analysis_result(project_id, parsed_intent, result)
        return result

    try:
        result_df = _aggregate(
            filtered_df,
            metric_field,
            dimension_field,
            aggregation,
            parsed_intent.get("metric", "") or metric_field or "记录数",
        )
    except ValueError as exc:
        warnings.append(str(exc))
        result = _failure_result(parsed_intent, warnings)
        _save_analysis_result(project_id, parsed_intent, result)
        return result

    result_df = _sort_and_limit(
        result_df,
        value_column=parsed_intent.get("metric", "") or metric_field or "记录数",
        sort=parsed_intent.get("sort", ""),
        top_n=parsed_intent.get("top_n"),
    )
    rows = _json_rows(result_df)
    result = {
        "success": True,
        "rows": rows,
        "summary": {
            "original_rows": original_rows,
            "filtered_rows": int(len(filtered_df)),
            "result_rows": int(len(result_df)),
            "metric": parsed_intent.get("metric", ""),
            "metric_field": metric_field,
            "dimension": parsed_intent.get("dimension", ""),
            "dimension_field": dimension_field,
            "aggregation": aggregation,
            "sort": parsed_intent.get("sort", ""),
            "top_n": parsed_intent.get("top_n"),
            "filters": parsed_intent.get("filters", []),
            "time_range": parsed_intent.get("time_range", ""),
            "warnings": warnings,
        },
        "metadata": _metadata(project_id, data_source, parsed_intent),
        "warnings": warnings,
    }
    _save_analysis_result(project_id, parsed_intent, result)
    return result


def _aggregate(
    dataframe: pd.DataFrame,
    metric_field: str,
    dimension_field: str,
    aggregation: str,
    output_metric_name: str,
) -> pd.DataFrame:
    if aggregation != "count" and not metric_field:
        raise ValueError("聚合计算缺少指标字段。")
    if aggregation != "count" and metric_field not in dataframe.columns:
        raise ValueError(f"指标字段不存在：{metric_field}")
    if dimension_field and dimension_field not in dataframe.columns:
        raise ValueError(f"维度字段不存在：{dimension_field}")

    if aggregation == "count":
        if dimension_field:
            if metric_field and metric_field in dataframe.columns:
                result = dataframe.groupby(dimension_field, dropna=False)[metric_field].count()
            else:
                result = dataframe.groupby(dimension_field, dropna=False).size()
            return result.reset_index(name=output_metric_name)
        value = int(dataframe[metric_field].count()) if metric_field and metric_field in dataframe.columns else int(len(dataframe))
        return pd.DataFrame([{"指标": output_metric_name, output_metric_name: value}])

    numeric = pd.to_numeric(dataframe[metric_field], errors="coerce")
    working_df = dataframe.copy()
    working_df[metric_field] = numeric
    aggregations = {
        "sum": "sum",
        "avg": "mean",
        "max": "max",
        "min": "min",
    }
    if dimension_field:
        result = (
            working_df.groupby(dimension_field, dropna=False)[metric_field]
            .agg(aggregations[aggregation])
            .reset_index()
            .rename(columns={metric_field: output_metric_name})
        )
        return result
    value = getattr(numeric, aggregations[aggregation])()
    return pd.DataFrame([{"指标": output_metric_name, output_metric_name: value}])


def _sort_and_limit(
    result_df: pd.DataFrame,
    value_column: str,
    sort: str,
    top_n: Any,
) -> pd.DataFrame:
    if value_column in result_df.columns and sort in {"asc", "desc"}:
        result_df = result_df.sort_values(value_column, ascending=sort == "asc")
    if top_n:
        try:
            result_df = result_df.head(int(top_n))
        except (TypeError, ValueError):
            pass
    return result_df.reset_index(drop=True)


def _apply_filters(
    dataframe: pd.DataFrame,
    filters: list[dict[str, Any]] | None,
) -> tuple[pd.DataFrame, list[str]]:
    warnings = []
    result = dataframe
    for item in filters or []:
        field = str(item.get("field", "")).strip()
        value = item.get("value")
        operator = item.get("operator", "==")
        if field not in result.columns:
            warnings.append(f"过滤字段不存在：{field}")
            continue
        if operator != "==":
            warnings.append(f"暂不支持过滤操作符：{operator}")
            continue
        result = result[result[field].astype(str) == str(value)]
    return result, warnings


def _apply_time_filter(
    dataframe: pd.DataFrame,
    time_range: str,
    field_mappings: list[dict[str, Any]],
) -> tuple[pd.DataFrame, list[str]]:
    if not time_range:
        return dataframe, []
    date_field = _resolve_date_field(dataframe, field_mappings)
    if not date_field:
        return dataframe, [f"未找到日期字段，无法应用时间过滤：{time_range}"]
    dates = pd.to_datetime(dataframe[date_field], errors="coerce")
    if dates.notna().sum() == 0:
        return dataframe, [f"日期字段无法解析，无法应用时间过滤：{date_field}"]
    now = pd.Timestamp.now().normalize()
    start = None
    end = None
    if time_range == "今天":
        start, end = now, now
    elif time_range == "昨天":
        start, end = now - pd.Timedelta(days=1), now - pd.Timedelta(days=1)
    elif time_range == "本周":
        start, end = now - pd.Timedelta(days=now.weekday()), now
    elif time_range == "上周":
        this_week_start = now - pd.Timedelta(days=now.weekday())
        start, end = this_week_start - pd.Timedelta(days=7), this_week_start - pd.Timedelta(days=1)
    elif time_range == "本月":
        start, end = now.replace(day=1), now
    elif time_range == "上月":
        this_month_start = now.replace(day=1)
        last_month_end = this_month_start - pd.Timedelta(days=1)
        start, end = last_month_end.replace(day=1), last_month_end
    elif time_range.startswith("最近") and time_range.endswith("天"):
        digits = "".join(ch for ch in time_range if ch.isdigit())
        if digits:
            days = int(digits)
            start, end = now - pd.Timedelta(days=max(days - 1, 0)), now
    if start is None or end is None:
        return dataframe, [f"暂不支持该时间范围的计算：{time_range}"]
    mask = (dates.dt.normalize() >= start) & (dates.dt.normalize() <= end)
    return dataframe.loc[mask].copy(), []


def _resolve_metric_field(
    dataframe: pd.DataFrame,
    parsed_intent: dict[str, Any],
    metric_dictionary: list[dict[str, Any]],
    kpis: list[dict[str, Any]],
    field_mappings: list[dict[str, Any]],
) -> str:
    metric_name = str(parsed_intent.get("metric", "")).strip()
    if metric_name in dataframe.columns:
        return metric_name
    metric = next((item for item in metric_dictionary if item.get("metric_name") == metric_name), None)
    linked_kpi_name = metric.get("linked_kpi_name", "") if metric else metric_name
    kpi = _find_kpi(kpis, linked_kpi_name)
    if kpi and kpi.get("source_field") in dataframe.columns:
        return str(kpi["source_field"])
    if metric:
        for alias in metric.get("aliases", []):
            if alias in dataframe.columns:
                return str(alias)
    for kpi_item in kpis:
        if kpi_item.get("kpi_name") == metric_name and kpi_item.get("source_field") in dataframe.columns:
            return str(kpi_item["source_field"])
    for item in field_mappings:
        column = item.get("column_name")
        if item.get("confirmed_type") in {"金额字段", "数量字段"} and column in dataframe.columns:
            if metric_name and metric_name in str(column):
                return str(column)
    return ""


def _resolve_dimension_field(
    dataframe: pd.DataFrame,
    dimension: str,
    field_mappings: list[dict[str, Any]],
) -> str:
    dimension = str(dimension or "").strip()
    if not dimension:
        return ""
    if dimension in dataframe.columns:
        return dimension
    if dimension in {"区域字段", "产品字段", "人员字段", "日期字段", "类别字段"}:
        for item in field_mappings:
            column = item.get("column_name")
            if item.get("confirmed_type") == dimension and column in dataframe.columns:
                return str(column)
    for item in field_mappings:
        column = str(item.get("column_name", ""))
        if column in dataframe.columns and (dimension in column or column in dimension):
            return column
    return ""


def _resolve_date_field(
    dataframe: pd.DataFrame,
    field_mappings: list[dict[str, Any]],
) -> str:
    for item in field_mappings:
        column = item.get("column_name")
        if item.get("confirmed_type") == "日期字段" and column in dataframe.columns:
            return str(column)
    for column in ("成交日期", "订单日期", "日期", "时间", "创建时间", "支付时间"):
        if column in dataframe.columns:
            return column
    for column in dataframe.columns:
        if pd.api.types.is_datetime64_any_dtype(dataframe[column]):
            return str(column)
    return ""


def _normalize_aggregation(value: Any) -> str:
    aggregation = str(value or "").strip().lower()
    if aggregation == "mean":
        aggregation = "avg"
    return aggregation if aggregation in SUPPORTED_AGGREGATIONS else "sum"


def _find_kpi(kpis: list[dict[str, Any]], kpi_name: str) -> dict[str, Any] | None:
    for kpi in kpis:
        if kpi.get("kpi_name") == kpi_name or kpi.get("kpi_id") == kpi_name:
            return kpi
    return None


def _load_project_context(project_id: str) -> dict[str, list[dict[str, Any]]]:
    kpis = _safe_load(load_kpi_definitions, project_id)
    if not kpis:
        kpis = _safe_load(merged_project_kpis, project_id)
    metrics = _safe_load(load_metric_dictionary, project_id)
    if not metrics:
        metrics = _safe_load(merged_project_metrics, project_id)
    return {
        "field_mappings": _safe_load(load_field_mappings, project_id),
        "kpis": kpis,
        "metric_dictionary": metrics,
    }


def _save_analysis_result(
    project_id: str,
    parsed_intent: dict[str, Any],
    result: dict[str, Any],
) -> None:
    analysis_path = project_workspace.get_project_path(project_id) / "analysis"
    analysis_path.mkdir(parents=True, exist_ok=True)
    payload = {
        "question": parsed_intent.get("original_question", ""),
        "parsed_intent": parsed_intent,
        "analysis_result": result,
        "created_at": _utc_now(),
    }
    result_path = analysis_path / RESULT_FILE
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    project_workspace.update_project(project_id, {"latest_analysis_result": payload})


def _failure_result(parsed_intent: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    return {
        "success": False,
        "rows": [],
        "summary": {
            "metric": parsed_intent.get("metric", ""),
            "dimension": parsed_intent.get("dimension", ""),
            "aggregation": parsed_intent.get("aggregation", ""),
            "warnings": warnings,
        },
        "metadata": {
            "executed_at": _utc_now(),
            "engine": "analysis_engine_v1",
        },
        "warnings": warnings,
    }


def _metadata(project_id: str, data_source: str, parsed_intent: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "data_source": data_source,
        "engine": "analysis_engine_v1",
        "executed_at": _utc_now(),
        "intent_type": parsed_intent.get("intent_type", ""),
    }


def _json_rows(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for row in dataframe.to_dict("records"):
        clean_row = {}
        for key, value in row.items():
            if pd.isna(value):
                clean_row[str(key)] = None
            elif hasattr(value, "item"):
                clean_row[str(key)] = value.item()
            else:
                clean_row[str(key)] = value
        rows.append(clean_row)
    return rows


def _safe_load(loader, project_id: str) -> list[dict[str, Any]]:
    try:
        value = loader(project_id)
    except Exception:
        return []
    return value if isinstance(value, list) else []


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
