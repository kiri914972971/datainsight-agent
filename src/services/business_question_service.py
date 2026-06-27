from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src import project_workspace
from src.engines.business_question_engine import parse_business_question
from src.services.current_dataset_service import load_current_analysis_dataframe
from src.services.field_mapping_service import load_field_mappings
from src.services.kpi_service import load_kpi_definitions, merged_project_kpis
from src.services.metric_dictionary_service import load_metric_dictionary, merged_project_metrics


QUESTION_HISTORY_FILE = "question_parse_history.json"


def parse_question_for_project(project_id: str, question: str) -> dict[str, Any]:
    context = _build_project_context(project_id)
    result = parse_business_question(question, context)
    save_question_parse_history(project_id, result)
    return result


def save_question_parse_history(project_id: str, result: dict[str, Any]) -> list[dict[str, Any]]:
    history = load_question_parse_history(project_id)
    record = {
        "original_question": result.get("original_question", ""),
        "parsed_intent": result,
        "created_at": _utc_now(),
    }
    history.insert(0, record)
    history = history[:100]
    config_path = _history_path(project_id)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = config_path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(config_path)
    project_workspace.update_project(project_id, {"question_parse_history": history})
    return history


def load_question_parse_history(project_id: str) -> list[dict[str, Any]]:
    config_path = _history_path(project_id)
    if config_path.is_file():
        try:
            content = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("业务问题解析历史损坏：config/question_parse_history.json") from exc
        if not isinstance(content, list):
            raise ValueError("业务问题解析历史格式无效：应为列表。")
        return content
    project = project_workspace.get_project(project_id)
    history = project.get("question_parse_history", [])
    return history if isinstance(history, list) else []


def _build_project_context(project_id: str) -> dict[str, Any]:
    field_mappings = _safe_load(load_field_mappings, project_id)
    kpis = _safe_load(load_kpi_definitions, project_id)
    if not kpis:
        kpis = _safe_load(merged_project_kpis, project_id)
    metric_dictionary = _safe_load(load_metric_dictionary, project_id)
    if not metric_dictionary:
        metric_dictionary = _safe_load(merged_project_metrics, project_id)
    dataset_preview = _load_dataset_preview(project_id)
    return {
        "field_mappings": field_mappings,
        "kpis": kpis,
        "metric_dictionary": metric_dictionary,
        "dataset_preview": dataset_preview,
        "dataset_columns": [str(column) for column in dataset_preview.columns],
    }


def _load_dataset_preview(project_id: str) -> pd.DataFrame:
    try:
        return load_current_analysis_dataframe(project_id).head(500)
    except Exception:
        pass
    return pd.DataFrame()


def _safe_load(loader, project_id: str) -> list[Any]:
    try:
        value = loader(project_id)
    except Exception:
        return []
    return value if isinstance(value, list) else []


def _history_path(project_id: str) -> Path:
    return project_workspace.get_project_path(project_id) / "config" / QUESTION_HISTORY_FILE


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
