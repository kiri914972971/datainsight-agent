from __future__ import annotations

from typing import Any, Callable

from src.services import analytics_service


TrackEvent = Callable[..., dict[str, Any] | None]


def safe_track_event(
    event_name: str,
    properties: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    success: bool = True,
    error_type: str | None = None,
    duration_ms: int | float | None = None,
    tracker: TrackEvent | None = None,
) -> dict[str, Any] | None:
    """Track an analytics event without allowing analytics failures to affect product flows."""
    try:
        return (tracker or analytics_service.track_event)(
            event_name,
            properties=properties,
            context=context,
            success=success,
            error_type=error_type,
            duration_ms=duration_ms,
        )
    except Exception:
        return None


def track_event_once(
    state: Any,
    state_key: str,
    fingerprint: str,
    event_name: str,
    properties: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    success: bool = True,
    error_type: str | None = None,
    duration_ms: int | float | None = None,
    tracker: TrackEvent | None = None,
) -> dict[str, Any] | None:
    """Track an event once for a session-state fingerprint."""
    if state.get(state_key) == fingerprint:
        return None
    event = safe_track_event(
        event_name,
        properties=properties,
        context=context,
        success=success,
        error_type=error_type,
        duration_ms=duration_ms,
        tracker=tracker,
    )
    state[state_key] = fingerprint
    return event


def dataset_context(project_id: str, dataset: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build common analytics context from project and dataset metadata."""
    dataset = dataset or {}
    return {
        "project_id": project_id,
        "dataset_id": dataset.get("dataset_id"),
        "dataset_type": dataset.get("dataset_type"),
    }


def dataset_properties(dataset: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return aggregate dataset properties safe for local analytics logging."""
    dataset = dataset or {}
    return {
        "dataset_type": dataset.get("dataset_type") or "unknown",
        "row_count": _optional_int(dataset.get("row_count") or dataset.get("rows")),
        "column_count": _optional_int(dataset.get("column_count") or dataset.get("columns")),
    }


def upload_event_inputs(
    project_id: str,
    saved_files: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Return one dataset_uploaded context/properties pair per saved file sheet."""
    events = []
    for file_metadata in saved_files:
        sheets = file_metadata.get("sheets") or []
        if not sheets:
            events.append(
                (
                    {"project_id": project_id, "dataset_id": file_metadata.get("file_id"), "dataset_type": "uploaded"},
                    {
                        "file_type": file_metadata.get("file_type") or "unknown",
                        "dataset_type": "uploaded",
                        "row_count": None,
                        "column_count": None,
                        "sheet_count": 0,
                    },
                )
            )
            continue
        for sheet in sheets:
            sheet_name = sheet.get("sheet_name") or "CSV"
            dataset_id = f"{file_metadata.get('file_id')}::{sheet_name}"
            events.append(
                (
                    {"project_id": project_id, "dataset_id": dataset_id, "dataset_type": "uploaded"},
                    {
                        "file_type": file_metadata.get("file_type") or "unknown",
                        "dataset_type": "uploaded",
                        "row_count": _optional_int(sheet.get("rows")),
                        "column_count": _optional_int(sheet.get("columns")),
                        "sheet_count": len(sheets),
                    },
                )
            )
    return events


def data_quality_properties(
    dataset: dict[str, Any],
    quality_overview: dict[str, Any],
    row_count: int,
    column_count: int,
    outlier_field_count: int,
) -> dict[str, Any]:
    """Build aggregate properties for a data_quality_viewed event."""
    return {
        "dataset_type": dataset.get("dataset_type") or "unknown",
        "row_count": int(row_count),
        "column_count": int(column_count),
        "quality_score": _optional_int(quality_overview.get("score")),
        "missing_total": _optional_int(quality_overview.get("missing_values")),
        "duplicate_count": _optional_int(quality_overview.get("duplicate_rows")),
        "suspected_id_count": _optional_int(quality_overview.get("identifier_column_count")),
        "outlier_field_count": int(outlier_field_count),
        "outlier_value_count": _optional_int(quality_overview.get("outlier_count")),
    }


def cleaned_dataset_properties(
    metadata: dict[str, Any],
    *,
    missing_plan_step_count: int,
    duplicate_plan_enabled: bool,
    id_override_count: int,
    outlier_plan_step_count: int,
) -> dict[str, Any]:
    """Build aggregate properties for a cleaned_dataset_generated event."""
    source_dataset = metadata.get("source_dataset") or {}
    return {
        "source_dataset_id": metadata.get("source_dataset_id") or source_dataset.get("dataset_id"),
        "source_dataset_type": source_dataset.get("dataset_type"),
        "cleaned_dataset_id": metadata.get("dataset_id"),
        "missing_plan_step_count": int(missing_plan_step_count),
        "duplicate_plan_enabled": bool(duplicate_plan_enabled),
        "id_override_count": int(id_override_count),
        "outlier_plan_step_count": int(outlier_plan_step_count),
        "before_row_count": _optional_int(metadata.get("before_rows")),
        "after_row_count": _optional_int(metadata.get("after_rows")),
        "before_column_count": _optional_int(metadata.get("before_columns")),
        "after_column_count": _optional_int(metadata.get("after_columns")),
    }


def report_export_properties(
    export_type: str,
    *,
    dataset: dict[str, Any] | None = None,
    file_size: int | None = None,
    has_quality_summary: bool | None = None,
    has_charts: bool | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    """Build non-sensitive report export event properties."""
    properties = {
        "export_type": export_type or "unknown",
        "dataset_type": (dataset or {}).get("dataset_type") or "unknown",
        "file_size": _optional_int(file_size),
        "has_quality_summary": has_quality_summary,
        "has_charts": has_charts,
    }
    if error_message:
        properties["error_message"] = short_error_message(error_message)
    return properties


def short_error_message(error: Any, limit: int = 120) -> str:
    """Return a short non-sensitive error summary for analytics properties."""
    text = str(error).replace("\n", " ").strip()
    return text[:limit]


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
