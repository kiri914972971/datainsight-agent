from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src import project_workspace
from src.engines.kpi_engine import (
    generate_kpi_candidates,
    merge_kpi_candidates,
    normalize_kpi_definition,
)
from src.services.field_mapping_service import load_field_mappings


KPI_FILE = "kpi_definitions.json"


def generate_project_kpi_candidates(project_id: str) -> list[dict[str, Any]]:
    mappings = load_field_mappings(project_id)
    return generate_kpi_candidates(mappings)


def load_kpi_definitions(project_id: str) -> list[dict[str, Any]]:
    field_mappings = _load_validation_field_mappings(project_id)
    config_path = _kpi_path(project_id)
    if config_path.is_file():
        try:
            content = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("KPI 配置损坏：config/kpi_definitions.json") from exc
        if not isinstance(content, list):
            raise ValueError("KPI 配置格式无效：应为 KPI 定义列表。")
        return [
            _normalize_with_timestamp(
                item,
                lifecycle_status="saved",
                field_mappings=field_mappings,
            )
            for item in content
            if isinstance(item, dict)
        ]
    project = project_workspace.get_project(project_id)
    kpis = project.get("kpi_definitions", [])
    return (
        [
            _normalize_with_timestamp(
                item,
                lifecycle_status="saved",
                field_mappings=field_mappings,
            )
            for item in kpis
            if isinstance(item, dict)
        ]
        if isinstance(kpis, list)
        else []
    )


def save_kpi_definitions(
    project_id: str,
    kpis: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    field_mappings = _load_validation_field_mappings(project_id)
    normalized = [
        _normalize_with_timestamp(
            item,
            lifecycle_status="saved",
            field_mappings=field_mappings,
        )
        for item in kpis or []
        if isinstance(item, dict)
        and str(item.get("kpi_name", "")).strip()
    ]
    config_path = _kpi_path(project_id)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = config_path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(config_path)
    project_workspace.update_project(project_id, {"kpi_definitions": normalized})
    return normalized


def get_project_kpis(project_id: str) -> list[dict[str, Any]]:
    return load_kpi_definitions(project_id)


def list_enabled_kpis(project_id: str) -> list[dict[str, Any]]:
    """Compatibility API: filter persisted KPI definitions only by enabled."""
    return [item for item in load_kpi_definitions(project_id) if item.get("enabled")]


def list_usable_kpis(
    project_id: str,
    available_fields: list[str] | tuple[str, ...] | set[str] | None = None,
) -> list[dict[str, Any]]:
    """Return saved, enabled and currently valid KPIs in persisted order."""
    field_mappings = _load_validation_field_mappings(project_id)
    usable_kpis = []
    for item in load_kpi_definitions(project_id):
        normalized = _normalize_with_timestamp(
            item,
            lifecycle_status="saved",
            available_fields=available_fields,
            field_mappings=field_mappings,
        )
        if (
            normalized["lifecycle_status"] == "saved"
            and normalized["enabled"]
            and normalized["validation_status"] == "valid"
        ):
            usable_kpis.append(normalized)
    return usable_kpis


def get_kpi_by_name(project_id: str, kpi_name: str) -> dict[str, Any] | None:
    for item in load_kpi_definitions(project_id):
        if item.get("kpi_name") == kpi_name:
            return item
    return None


def add_kpi_definition(
    project_id: str,
    kpi: dict[str, Any],
) -> list[dict[str, Any]]:
    return save_kpi_definitions(project_id, load_kpi_definitions(project_id) + [kpi])


def update_kpi_definition(
    project_id: str,
    kpi_id: str,
    updates: dict[str, Any],
) -> list[dict[str, Any]]:
    updated = []
    found = False
    for item in load_kpi_definitions(project_id):
        if item["kpi_id"] == kpi_id:
            updated.append({**item, **updates})
            found = True
        else:
            updated.append(item)
    if not found:
        raise ValueError(f"KPI 不存在：{kpi_id}")
    return save_kpi_definitions(project_id, updated)


def delete_kpi_definition(project_id: str, kpi_id: str) -> list[dict[str, Any]]:
    return save_kpi_definitions(
        project_id,
        [item for item in load_kpi_definitions(project_id) if item["kpi_id"] != kpi_id],
    )


def merged_project_kpis(project_id: str) -> list[dict[str, Any]]:
    return merge_kpi_candidates(
        load_kpi_definitions(project_id),
        generate_project_kpi_candidates(project_id),
    )


def _normalize_with_timestamp(
    kpi: dict[str, Any],
    *,
    lifecycle_status: str = "saved",
    available_fields: list[str] | tuple[str, ...] | set[str] | None = None,
    field_mappings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized = normalize_kpi_definition(
        kpi,
        lifecycle_status=lifecycle_status,
        available_fields=available_fields,
        field_mappings=field_mappings,
    )
    normalized["updated_at"] = normalized["updated_at"] or _utc_now()
    return normalized


def _load_validation_field_mappings(
    project_id: str,
) -> list[dict[str, Any]] | None:
    try:
        mappings = load_field_mappings(project_id)
    except (FileNotFoundError, ValueError):
        return None
    return mappings or None


def _kpi_path(project_id: str) -> Path:
    return project_workspace.get_project_path(project_id) / "config" / KPI_FILE


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
