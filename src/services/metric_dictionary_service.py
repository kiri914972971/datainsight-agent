from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src import project_workspace
from src.engines.metric_dictionary_engine import (
    alias_matches_metric,
    generate_metric_candidates_from_kpis,
    merge_metric_candidates,
    normalize_metric_definition,
)
from src.services.kpi_service import merged_project_kpis


METRIC_DICTIONARY_FILE = "metric_dictionary.json"


def generate_project_metric_candidates(project_id: str) -> list[dict[str, Any]]:
    return generate_metric_candidates_from_kpis(merged_project_kpis(project_id))


def load_metric_dictionary(project_id: str) -> list[dict[str, Any]]:
    config_path = _metric_dictionary_path(project_id)
    if config_path.is_file():
        try:
            content = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("指标字典配置损坏：config/metric_dictionary.json") from exc
        if not isinstance(content, list):
            raise ValueError("指标字典配置格式无效：应为指标定义列表。")
        return [_normalize_with_timestamp(item) for item in content]

    project = project_workspace.get_project(project_id)
    metrics = project.get("metric_dictionary", [])
    return [_normalize_with_timestamp(item) for item in metrics] if isinstance(metrics, list) else []


def save_metric_dictionary(
    project_id: str,
    metrics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized = [
        _normalize_with_timestamp(item)
        for item in metrics
        if str(item.get("metric_name", "")).strip()
    ]
    config_path = _metric_dictionary_path(project_id)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = config_path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(config_path)
    project_workspace.update_project(project_id, {"metric_dictionary": normalized})
    return normalized


def get_metric_dictionary(project_id: str) -> list[dict[str, Any]]:
    return load_metric_dictionary(project_id)


def list_metrics(project_id: str) -> list[dict[str, Any]]:
    return load_metric_dictionary(project_id)


def list_enabled_metrics(project_id: str) -> list[dict[str, Any]]:
    return [item for item in load_metric_dictionary(project_id) if item.get("enabled")]


def get_metric_by_name(project_id: str, name: str) -> dict[str, Any] | None:
    target = str(name).strip()
    for item in load_metric_dictionary(project_id):
        if item.get("metric_name") == target:
            return item
    return None


def find_metric_by_alias(project_id: str, alias: str) -> dict[str, Any] | None:
    for item in load_metric_dictionary(project_id):
        if alias_matches_metric(item, alias):
            return item
    return None


def add_metric_definition(
    project_id: str,
    metric: dict[str, Any],
) -> list[dict[str, Any]]:
    return save_metric_dictionary(
        project_id,
        load_metric_dictionary(project_id) + [metric],
    )


def update_metric_definition(
    project_id: str,
    metric_id: str,
    updates: dict[str, Any],
) -> list[dict[str, Any]]:
    updated = []
    found = False
    for item in load_metric_dictionary(project_id):
        if item["metric_id"] == metric_id:
            updated.append({**item, **updates})
            found = True
        else:
            updated.append(item)
    if not found:
        raise ValueError(f"指标不存在：{metric_id}")
    return save_metric_dictionary(project_id, updated)


def delete_metric_definition(project_id: str, metric_id: str) -> list[dict[str, Any]]:
    return save_metric_dictionary(
        project_id,
        [
            item
            for item in load_metric_dictionary(project_id)
            if item["metric_id"] != metric_id
        ],
    )


def merged_project_metrics(project_id: str) -> list[dict[str, Any]]:
    return merge_metric_candidates(
        load_metric_dictionary(project_id),
        generate_project_metric_candidates(project_id),
    )


def _normalize_with_timestamp(metric: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_metric_definition(metric)
    normalized["updated_at"] = normalized["updated_at"] or _utc_now()
    return normalized


def _metric_dictionary_path(project_id: str) -> Path:
    return project_workspace.get_project_path(project_id) / "config" / METRIC_DICTIONARY_FILE


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
