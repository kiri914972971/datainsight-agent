from __future__ import annotations

import hashlib
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
    available_fields: list[str] | tuple[str, ...] | set[str] | None = None,
) -> list[dict[str, Any]]:
    field_mappings = _load_validation_field_mappings(project_id)
    normalized = [
        _normalize_with_timestamp(
            item,
            lifecycle_status="saved",
            available_fields=available_fields,
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


def list_unsaved_kpi_candidates(project_id: str) -> list[dict[str, Any]]:
    """Return generated candidates that are not already persisted KPIs."""
    return filter_unsaved_kpi_candidates(
        load_kpi_definitions(project_id),
        generate_project_kpi_candidates(project_id),
    )


def filter_unsaved_kpi_candidates(
    saved_kpis: list[dict[str, Any]] | None,
    candidates: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Filter candidate rows without mutating or persisting either input."""
    saved_ids = {
        str(item.get("kpi_id", ""))
        for item in saved_kpis or []
        if isinstance(item, dict) and item.get("kpi_id")
    }
    saved_keys = {
        _kpi_identity(item)
        for item in saved_kpis or []
        if isinstance(item, dict)
    }
    result = []
    seen_ids = set()
    seen_keys = set()
    for candidate in candidates or []:
        if not isinstance(candidate, dict):
            continue
        candidate_id = str(candidate.get("kpi_id", ""))
        candidate_key = _kpi_identity(candidate)
        if (
            candidate_id in saved_ids
            or candidate_key in saved_keys
            or candidate_id in seen_ids
            or candidate_key in seen_keys
        ):
            continue
        result.append(dict(candidate))
        seen_ids.add(candidate_id)
        seen_keys.add(candidate_key)
    return result


def kpi_collection_signature(kpis: list[dict[str, Any]] | None) -> str:
    """Build a stable signature for project-scoped editor state keys."""
    payload = [
        {
            "kpi_id": str(item.get("kpi_id", "")),
            "kpi_name": str(item.get("kpi_name", "")),
            "aggregation": str(item.get("aggregation", "")),
            "source_field": str(item.get("source_field", "")),
            "field_type": str(item.get("field_type", "")),
            "category": str(item.get("category", "")),
            "description": str(item.get("description", "")),
            "enabled": bool(item.get("enabled", False)),
            "lifecycle_status": str(item.get("lifecycle_status", "")),
            "validation_status": str(item.get("validation_status", "")),
            "validation_messages": [
                str(message)
                for message in item.get("validation_messages", []) or []
            ],
        }
        for item in kpis or []
        if isinstance(item, dict)
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def summarize_kpi_center(
    saved_kpis: list[dict[str, Any]] | None,
    candidate_kpis: list[dict[str, Any]] | None,
    usable_kpis: list[dict[str, Any]] | None,
) -> dict[str, int]:
    saved = [item for item in saved_kpis or [] if isinstance(item, dict)]
    return {
        "candidate_count": len(
            [item for item in candidate_kpis or [] if isinstance(item, dict)]
        ),
        "saved_count": len(saved),
        "enabled_count": len([item for item in saved if item.get("enabled")]),
        "usable_count": len(
            [item for item in usable_kpis or [] if isinstance(item, dict)]
        ),
        "invalid_count": len(
            [
                item
                for item in saved
                if item.get("validation_status") == "invalid"
            ]
        ),
    }


def save_selected_kpi_candidates(
    project_id: str,
    selected_candidates: list[dict[str, Any]],
    available_fields: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Persist only selected candidates, with validation-based default enablement."""
    existing = load_kpi_definitions(project_id)
    field_mappings = _load_validation_field_mappings(project_id)
    existing_ids = {str(item.get("kpi_id", "")) for item in existing}
    existing_keys = {_kpi_identity(item) for item in existing}
    saved_items = []
    skipped_items = []
    failed_items = []

    for candidate in selected_candidates or []:
        if not isinstance(candidate, dict):
            failed_items.append({"kpi_name": "", "reason": "候选数据格式无效。"})
            continue
        kpi_name = str(candidate.get("kpi_name", "")).strip()
        if not kpi_name:
            failed_items.append({"kpi_name": "", "reason": "KPI 名称不能为空。"})
            continue
        prepared = _prepare_saved_kpi(
            candidate,
            default_enabled=True,
            available_fields=available_fields,
            field_mappings=field_mappings,
        )
        identity = _kpi_identity(prepared)
        if prepared["kpi_id"] in existing_ids or identity in existing_keys:
            skipped_items.append(
                {"kpi_name": prepared["kpi_name"], "reason": "指标已保存。"}
            )
            continue
        saved_items.append(prepared)
        existing_ids.add(prepared["kpi_id"])
        existing_keys.add(identity)

    all_kpis = existing
    if saved_items:
        all_kpis = save_kpi_definitions(
            project_id,
            existing + saved_items,
            available_fields=available_fields,
        )
        saved_ids = {item["kpi_id"] for item in saved_items}
        saved_items = [
            item for item in all_kpis if item.get("kpi_id") in saved_ids
        ]
    return {
        "saved": saved_items,
        "skipped": skipped_items,
        "failed": failed_items,
        "all_kpis": all_kpis,
    }


def save_edited_kpi_definitions(
    project_id: str,
    kpis: list[dict[str, Any]],
    available_fields: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, Any]:
    """Revalidate saved KPI edits and disable definitions that are not valid."""
    field_mappings = _load_validation_field_mappings(project_id)
    normalized = []
    forced_disabled = []
    for item in kpis or []:
        if not isinstance(item, dict) or not str(item.get("kpi_name", "")).strip():
            continue
        requested_enabled = bool(item.get("enabled", False))
        prepared = _prepare_saved_kpi(
            item,
            default_enabled=None,
            available_fields=available_fields,
            field_mappings=field_mappings,
        )
        if requested_enabled and not prepared["enabled"]:
            forced_disabled.append(prepared["kpi_name"])
        normalized.append(prepared)
    saved = save_kpi_definitions(
        project_id,
        normalized,
        available_fields=available_fields,
    )
    return {"saved": saved, "forced_disabled": forced_disabled}


def add_saved_kpi_definition(
    project_id: str,
    kpi: dict[str, Any],
    available_fields: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, Any]:
    """Create one formal KPI and default-enable it only when validation succeeds."""
    field_mappings = _load_validation_field_mappings(project_id)
    prepared = _prepare_saved_kpi(
        {**dict(kpi), "created_by": "user"},
        default_enabled=True,
        available_fields=available_fields,
        field_mappings=field_mappings,
    )
    existing = load_kpi_definitions(project_id)
    if any(_kpi_identity(item) == _kpi_identity(prepared) for item in existing):
        raise ValueError(f"指标已存在：{prepared['kpi_name']}")
    saved = save_kpi_definitions(
        project_id,
        existing + [prepared],
        available_fields=available_fields,
    )
    return next(item for item in saved if item["kpi_id"] == prepared["kpi_id"])


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


def _prepare_saved_kpi(
    kpi: dict[str, Any],
    *,
    default_enabled: bool | None,
    available_fields: list[str] | tuple[str, ...] | set[str] | None,
    field_mappings: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    normalized = normalize_kpi_definition(
        kpi,
        lifecycle_status="saved",
        available_fields=available_fields,
        field_mappings=field_mappings,
    )
    requested_enabled = (
        bool(kpi.get("enabled", False))
        if default_enabled is None
        else default_enabled
    )
    normalized["enabled"] = bool(
        requested_enabled and normalized["validation_status"] == "valid"
    )
    return normalized


def _kpi_identity(kpi: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(kpi.get("kpi_name", "")).strip().casefold(),
        str(kpi.get("aggregation", "")).strip().lower(),
        str(kpi.get("source_field", "")).strip(),
        str(kpi.get("category", "")).strip(),
    )


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
