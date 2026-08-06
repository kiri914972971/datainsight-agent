from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src import project_workspace
from src.engines.metric_dictionary_engine import (
    alias_matches_metric,
    build_metric_association_view,
    generate_metric_candidates_from_kpis,
    merge_metric_candidates,
    normalize_metric_definition,
)
from src.services.kpi_service import load_kpi_definitions


METRIC_DICTIONARY_FILE = "metric_dictionary.json"


def generate_project_metric_candidates(project_id: str) -> list[dict[str, Any]]:
    saved_kpis = [
        item
        for item in load_kpi_definitions(project_id)
        if item.get("lifecycle_status") == "saved"
    ]
    existing_linked_kpi_ids = {
        str(item.get("linked_kpi_id", "")).strip()
        for item in load_metric_dictionary(project_id)
        if item.get("linked_kpi_id")
    }
    return [
        item
        for item in generate_metric_candidates_from_kpis(saved_kpis)
        if item.get("linked_kpi_id") not in existing_linked_kpi_ids
    ]


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
    """Compatibility API: enabled semantic definitions must also remain usable."""
    return list_usable_metrics(project_id)


def get_metric_dictionary_view(project_id: str) -> list[dict[str, Any]]:
    """Return saved definitions plus missing candidates with live association state."""
    saved_kpis = load_kpi_definitions(project_id)
    candidates = generate_project_metric_candidates(project_id)
    merged = merge_metric_candidates(load_metric_dictionary(project_id), candidates)
    return build_metric_association_view(
        merged,
        saved_kpis,
        candidate_metric_ids={item["metric_id"] for item in candidates},
    )


def list_usable_metrics(project_id: str) -> list[dict[str, Any]]:
    """Return semantic definitions that remain usable with their linked KPI."""
    saved_kpis = load_kpi_definitions(project_id)
    return [
        item
        for item in build_metric_association_view(
            load_metric_dictionary(project_id),
            saved_kpis,
        )
        if item["usable"]
    ]


def get_metric_by_name(project_id: str, name: str) -> dict[str, Any] | None:
    target = str(name).strip()
    for item in load_metric_dictionary(project_id):
        if item.get("metric_name") == target:
            return item
    return None


def find_metric_by_alias(project_id: str, alias: str) -> dict[str, Any] | None:
    for item in list_usable_metrics(project_id):
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
    source = dict(metric)
    if not str(source.get("metric_id", "")).strip():
        source["metric_id"] = _legacy_metric_id(source)
    normalized = normalize_metric_definition(source)
    normalized["updated_at"] = normalized["updated_at"] or _utc_now()
    return normalized


def _metric_dictionary_path(project_id: str) -> Path:
    return project_workspace.get_project_path(project_id) / "config" / METRIC_DICTIONARY_FILE


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _legacy_metric_id(metric: dict[str, Any]) -> str:
    linked_kpi_id = str(metric.get("linked_kpi_id", "")).strip()
    if linked_kpi_id:
        identity = f"linked:{linked_kpi_id}"
    else:
        identity = json.dumps(
            {
                "metric_name": str(metric.get("metric_name", "")).strip(),
                "linked_kpi_name": str(metric.get("linked_kpi_name", "")).strip(),
                "business_definition": str(
                    metric.get("business_definition", "")
                ).strip(),
                "aliases": metric.get("aliases", []),
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
    return uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"data-insight-agent:legacy-metric:{identity}",
    ).hex
