from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from src import project_workspace


EDA_REPORT_FILE = "eda_report.json"
DASHBOARD_FILE = "dashboard.json"


def generate_dashboard(project_id: str) -> dict[str, Any]:
    """Build dashboard-ready chart/card specs from persisted analysis reports."""
    eda_report = _load_analysis_json(project_id, EDA_REPORT_FILE)
    if not eda_report:
        dashboard = {
            "overview_cards": [],
            "trend_charts": [],
            "topn_charts": [],
            "risk_cards": [
                {
                    "risk_level": "high",
                    "message": "未找到 eda_report.json，请先生成探索性分析报告。",
                }
            ],
            "metadata": _metadata(project_id),
        }
        _save_dashboard(project_id, dashboard)
        return dashboard

    dashboard = {
        "overview_cards": _build_overview_cards(eda_report.get("overview", {})),
        "trend_charts": _build_trend_charts(eda_report),
        "topn_charts": _build_topn_charts(eda_report),
        "risk_cards": _build_risk_cards(eda_report.get("warnings", [])),
        "metadata": _metadata(project_id),
    }
    _save_dashboard(project_id, dashboard)
    return dashboard


def _build_overview_cards(overview: dict[str, Any]) -> list[dict[str, Any]]:
    time_span = overview.get("time_span", "暂无")
    if isinstance(time_span, dict):
        start = time_span.get("start")
        end = time_span.get("end")
        time_span = f"{start} ~ {end}" if start and end else "暂无"
    return [
        {
            "title": "行数",
            "value": overview.get("row_count", 0),
            "description": "Analysis Dataset 行数",
        },
        {
            "title": "字段数",
            "value": overview.get("column_count", 0),
            "description": "Analysis Dataset 字段数",
        },
        {
            "title": "KPI数",
            "value": overview.get("kpi_count", overview.get("numeric_column_count", 0)),
            "description": "当前可用于指标展示的数量",
        },
        {
            "title": "时间跨度",
            "value": time_span,
            "description": "来自 EDA 概览或数据日期范围",
        },
    ]


def _build_trend_charts(eda_report: dict[str, Any]) -> list[dict[str, Any]]:
    trend_source = (
        eda_report.get("trend_analysis")
        or eda_report.get("trends")
        or []
    )
    charts = []
    for item in trend_source:
        if not isinstance(item, dict):
            continue
        if item.get("x") is not None and item.get("y") is not None:
            charts.append(
                {
                    "title": str(item.get("title") or "趋势图"),
                    "x": list(item.get("x") or []),
                    "y": list(item.get("y") or []),
                }
            )
            continue
        previous_period = item.get("previous_period")
        current_period = item.get("current_period")
        if previous_period and current_period:
            charts.append(
                {
                    "title": f"{item.get('kpi_name', '指标')}{item.get('period_type', '')}趋势",
                    "x": [previous_period, current_period],
                    "y": [
                        item.get("previous_value", 0),
                        item.get("current_value", 0),
                    ],
                }
            )
    return charts


def _build_topn_charts(eda_report: dict[str, Any]) -> list[dict[str, Any]]:
    explicit_source = eda_report.get("dimension_analysis") or []
    charts = []
    for item in explicit_source:
        if not isinstance(item, dict):
            continue
        if item.get("labels") is not None and item.get("values") is not None:
            charts.append(
                {
                    "title": str(item.get("title") or "TopN"),
                    "labels": list(item.get("labels") or []),
                    "values": list(item.get("values") or []),
                }
            )
            continue
        top5 = item.get("top5") or []
        if top5:
            label_key, value_key = _infer_topn_keys(top5[0])
            charts.append(
                {
                    "title": f"Top5{item.get('dimension_field', item.get('column', '维度'))}",
                    "labels": [str(row.get(label_key, "")) for row in top5],
                    "values": [row.get(value_key, 0) for row in top5],
                }
            )

    if charts:
        return charts

    for item in eda_report.get("categorical_analysis", []):
        top_values = item.get("top5_values", [])
        if not top_values:
            continue
        charts.append(
            {
                "title": f"Top5{item.get('column', '类别')}",
                "labels": [str(row.get("value", "")) for row in top_values],
                "values": [row.get("count", 0) for row in top_values],
            }
        )
    return charts


def _build_risk_cards(warnings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    risk_cards = []
    for item in warnings or []:
        if not isinstance(item, dict):
            risk_cards.append({"risk_level": "medium", "message": str(item)})
            continue
        risk_cards.append(
            {
                "risk_level": _normalize_risk_level(item.get("risk_level") or item.get("severity")),
                "message": str(item.get("message") or item),
                "type": item.get("type", ""),
            }
        )
    return risk_cards


def _infer_topn_keys(row: dict[str, Any]) -> tuple[str, str]:
    value_candidates = ("value", "count", "amount", "sales", "销售额")
    value_key = next((key for key in value_candidates if key in row), "")
    if not value_key:
        numeric_keys = [
            key
            for key, value in row.items()
            if isinstance(value, (int, float)) and key not in {"share", "ratio"}
        ]
        value_key = numeric_keys[0] if numeric_keys else next(iter(row), "")
    label_key = next(
        (
            key
            for key in row
            if key not in {value_key, "share", "ratio", "top1_ratio"}
        ),
        next(iter(row), ""),
    )
    return label_key, value_key


def _normalize_risk_level(value: Any) -> str:
    text = str(value or "").lower()
    if text in {"high", "高", "严重"}:
        return "high"
    if text in {"low", "低", "info"}:
        return "low"
    return "medium"


def _load_analysis_json(project_id: str, file_name: str) -> dict[str, Any]:
    path = project_workspace.get_project_path(project_id) / "analysis" / file_name
    if not path.is_file():
        return {}
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"分析结果文件损坏：analysis/{file_name}") from exc
    return content if isinstance(content, dict) else {}


def _save_dashboard(project_id: str, dashboard: dict[str, Any]) -> None:
    analysis_path = project_workspace.get_project_path(project_id) / "analysis"
    analysis_path.mkdir(parents=True, exist_ok=True)
    dashboard_path = analysis_path / DASHBOARD_FILE
    dashboard_path.write_text(
        json.dumps(dashboard, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    project_workspace.update_project(project_id, {"latest_dashboard": dashboard})


def _metadata(project_id: str) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "engine": "dashboard_engine_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dashboard_file": f"analysis/{DASHBOARD_FILE}",
    }
