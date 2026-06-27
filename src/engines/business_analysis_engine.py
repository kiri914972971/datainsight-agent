from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from src import project_workspace


BUSINESS_ANALYSIS_FILE = "business_analysis.json"
EDA_REPORT_FILE = "eda_report.json"


def generate_business_analysis(
    project_id: str,
    analysis_result: dict[str, Any] | None,
) -> dict[str, Any]:
    """Translate computed analysis results into rule-based business language."""
    normalized_result = _normalize_analysis_result(analysis_result)
    eda_report = _load_analysis_json(project_id, EDA_REPORT_FILE)
    findings = []
    comparisons = []
    risks = []
    recommendations = []

    rows = normalized_result.get("rows", []) or []
    summary = normalized_result.get("summary", {}) or {}
    metric_name = str(summary.get("metric") or summary.get("metric_field") or "指标")
    dimension_name = str(summary.get("dimension") or summary.get("dimension_field") or "维度")

    top_context = _top1_context(rows, summary)
    if top_context:
        top_finding, top_risks, top_recommendations = _analyze_top1(
            top_context,
            metric_name,
            dimension_name,
        )
        findings.append(top_finding)
        risks.extend(top_risks)
        recommendations.extend(top_recommendations)

    growth_rate = _extract_growth_rate(normalized_result)
    if growth_rate is not None:
        comparison, growth_findings, growth_risks = _analyze_growth(growth_rate)
        comparisons.append(comparison)
        findings.extend(growth_findings)
        risks.extend(growth_risks)

    eda_risks, eda_recommendations = _analyze_eda_warnings(eda_report.get("warnings", []))
    risks.extend(eda_risks)
    recommendations.extend(eda_recommendations)

    for warning in normalized_result.get("warnings", []) or []:
        risks.append(f"分析执行提示：{warning}")

    findings = _deduplicate(findings)
    comparisons = _deduplicate(comparisons)
    risks = _deduplicate(risks)
    recommendations = _deduplicate(recommendations)
    summary_text = _build_summary(findings, risks, recommendations)
    business_analysis = {
        "summary": summary_text,
        "findings": findings,
        "comparisons": comparisons,
        "risks": risks,
        "recommendations": recommendations,
        "metadata": _metadata(project_id),
    }
    _save_business_analysis(project_id, business_analysis)
    return business_analysis


def _normalize_analysis_result(analysis_result: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(analysis_result, dict):
        return {"success": False, "rows": [], "summary": {}, "warnings": ["未提供 analysis_result。"]}
    if isinstance(analysis_result.get("analysis_result"), dict):
        return analysis_result["analysis_result"]
    return analysis_result


def _top1_context(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
) -> dict[str, Any] | None:
    if not rows:
        return None
    first_row = rows[0]
    if not isinstance(first_row, dict) or not first_row:
        return None
    metric_key = _metric_key(first_row, summary)
    label_key = _label_key(first_row, metric_key, summary)
    if not metric_key or not label_key:
        return None
    values = [_safe_number(row.get(metric_key)) for row in rows if isinstance(row, dict)]
    total = sum(value for value in values if value is not None)
    top_value = _safe_number(first_row.get(metric_key))
    share = top_value / total if top_value is not None and total else None
    return {
        "label": first_row.get(label_key),
        "label_key": label_key,
        "metric_key": metric_key,
        "value": top_value,
        "share": share,
        "row_count": len(rows),
    }


def _analyze_top1(
    context: dict[str, Any],
    metric_name: str,
    dimension_name: str,
) -> tuple[str, list[str], list[str]]:
    label = context.get("label")
    dimension_label = _business_dimension_label(dimension_name)
    finding = f"{dimension_label}{label}是当前{metric_name}贡献最大的{dimension_label}。"
    risks = []
    recommendations = []
    share = context.get("share")
    if share is not None and share > 0.5:
        risks.append("业务集中度较高。")
        recommendations.append("建议扩大产品结构或拓展更多高贡献维度，降低单一来源依赖。")
    return finding, risks, recommendations


def _analyze_growth(growth_rate: float) -> tuple[str, list[str], list[str]]:
    comparison = f"当前结果较对比期变化 {growth_rate:+.2f}%。"
    findings = []
    risks = []
    if growth_rate > 20:
        findings.append("业务增长明显。")
    elif growth_rate < -20:
        risks.append("业务出现明显下滑。")
    return comparison, findings, risks


def _analyze_eda_warnings(warnings: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    risks = []
    recommendations = []
    for warning in warnings or []:
        if not isinstance(warning, dict):
            risks.append(str(warning))
            continue
        warning_type = warning.get("type", "")
        message = str(warning.get("message") or warning)
        if warning_type in {"high_concentration", "concentration_risk"}:
            risks.append(f"高集中度风险：{message}")
            recommendations.append("建议扩大产品结构，减少业务过度集中。")
        elif warning_type in {"high_missing_rate", "missing_value_risk"}:
            risks.append(f"高缺失率风险：{message}")
            recommendations.append("建议完善数据采集流程，优先补齐关键字段。")
        elif warning_type in {"high_outlier_ratio", "outlier_risk"}:
            risks.append(f"高异常率风险：{message}")
            recommendations.append("建议核查异常记录，确认是否为录入错误、极端订单或特殊业务场景。")
        elif warning_type in {"strong_correlation"}:
            risks.append(f"强相关字段提示：{message}")
        else:
            risks.append(message)
    return risks, recommendations


def _extract_growth_rate(analysis_result: dict[str, Any]) -> float | None:
    summary = analysis_result.get("summary", {}) or {}
    for key in ("growth_rate", "growth", "mom", "yoy"):
        value = _safe_number(summary.get(key))
        if value is not None:
            return value
    for row in analysis_result.get("rows", []) or []:
        if not isinstance(row, dict):
            continue
        for key in ("growth_rate", "增长率", "环比", "同比"):
            value = _safe_number(row.get(key))
            if value is not None:
                return value
    return None


def _metric_key(row: dict[str, Any], summary: dict[str, Any]) -> str:
    for candidate in (
        summary.get("metric"),
        summary.get("metric_field"),
        "value",
        "count",
        "销售额",
        "成交金额",
    ):
        if candidate in row and _safe_number(row.get(candidate)) is not None:
            return str(candidate)
    for key, value in row.items():
        if _safe_number(value) is not None:
            return str(key)
    return ""


def _label_key(row: dict[str, Any], metric_key: str, summary: dict[str, Any]) -> str:
    for candidate in (
        summary.get("dimension_field"),
        summary.get("dimension"),
    ):
        if candidate in row and candidate != metric_key:
            return str(candidate)
    for key in row:
        if key != metric_key and _safe_number(row.get(key)) is None:
            return str(key)
    for key in row:
        if key != metric_key:
            return str(key)
    return ""


def _business_dimension_label(dimension_name: str) -> str:
    text = str(dimension_name or "")
    if any(keyword in text for keyword in ("产品", "商品", "SKU", "品类")):
        return "产品"
    if any(keyword in text for keyword in ("区域", "地区", "省份", "城市")):
        return "区域"
    if any(keyword in text for keyword in ("销售", "员工", "人员", "顾问")):
        return "销售员"
    if any(keyword in text for keyword in ("客户", "用户")):
        return "客户"
    return text or "维度"


def _build_summary(
    findings: list[str],
    risks: list[str],
    recommendations: list[str],
) -> str:
    if not findings and not risks:
        return "当前分析结果暂未发现明显业务特征。"
    parts = []
    if findings:
        parts.append(findings[0])
    if risks:
        parts.append(f"需要关注：{risks[0]}")
    if recommendations:
        parts.append(f"建议：{recommendations[0]}")
    return " ".join(parts)


def _load_analysis_json(project_id: str, file_name: str) -> dict[str, Any]:
    path = project_workspace.get_project_path(project_id) / "analysis" / file_name
    if not path.is_file():
        return {}
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"分析结果文件损坏：analysis/{file_name}") from exc
    return content if isinstance(content, dict) else {}


def _save_business_analysis(project_id: str, business_analysis: dict[str, Any]) -> None:
    analysis_path = project_workspace.get_project_path(project_id) / "analysis"
    analysis_path.mkdir(parents=True, exist_ok=True)
    output_path = analysis_path / BUSINESS_ANALYSIS_FILE
    output_path.write_text(
        json.dumps(business_analysis, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    project_workspace.update_project(project_id, {"latest_business_analysis": business_analysis})


def _safe_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _deduplicate(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _metadata(project_id: str) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "engine": "business_analysis_engine_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "business_analysis_file": f"analysis/{BUSINESS_ANALYSIS_FILE}",
    }
