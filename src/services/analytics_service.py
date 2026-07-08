from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SESSION_STATE_KEY = "_data_insight_analytics_session_id"
EVENT_LOG_PATH = Path("workspace") / "analytics" / "events.jsonl"
_FALLBACK_SESSION_ID: str | None = None


def get_or_create_session_id() -> str:
    """Return a stable analytics session id for Streamlit or test contexts."""
    global _FALLBACK_SESSION_ID

    try:
        get_script_run_ctx = _get_streamlit_script_context_getter()
        if get_script_run_ctx is None:
            raise RuntimeError("Streamlit script context is unavailable.")
        try:
            script_context = get_script_run_ctx(suppress_warning=True)
        except TypeError:
            script_context = get_script_run_ctx()
        if script_context is None:
            raise RuntimeError("Streamlit script context is unavailable.")

        import streamlit as st

        if SESSION_STATE_KEY not in st.session_state:
            st.session_state[SESSION_STATE_KEY] = str(uuid.uuid4())
        return str(st.session_state[SESSION_STATE_KEY])
    except Exception:
        if _FALLBACK_SESSION_ID is None:
            _FALLBACK_SESSION_ID = str(uuid.uuid4())
        return _FALLBACK_SESSION_ID


def build_event(
    event_name: str,
    properties: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    success: bool = True,
    error_type: str | None = None,
    duration_ms: int | float | None = None,
) -> dict[str, Any]:
    """Build a local analytics event with common JSONL fields."""
    context = context or {}
    return {
        "event_id": str(uuid.uuid4()),
        "event_name": str(event_name),
        "session_id": get_or_create_session_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project_id": context.get("project_id"),
        "dataset_id": context.get("dataset_id"),
        "dataset_type": context.get("dataset_type"),
        "success": bool(success),
        "error_type": error_type,
        "duration_ms": duration_ms,
        "properties": _safe_properties(properties),
    }


def track_event(
    event_name: str,
    properties: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    success: bool = True,
    error_type: str | None = None,
    duration_ms: int | float | None = None,
    event_file_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Build and append one local analytics event as a JSONL line."""
    event = build_event(
        event_name=event_name,
        properties=properties,
        context=context,
        success=success,
        error_type=error_type,
        duration_ms=duration_ms,
    )
    event_path = _resolve_event_path(event_file_path)

    try:
        event_path.parent.mkdir(parents=True, exist_ok=True)
        # Local MVP logging only: no external upload. JSONL keeps events easy to
        # inspect manually and migrate to richer analytics storage later.
        with event_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
            file.write("\n")
    except Exception as exc:
        event["analytics_logging_error"] = type(exc).__name__
    return event


def read_events(
    limit: int | None = None,
    event_file_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Read local analytics events from the JSONL log file."""
    event_path = _resolve_event_path(event_file_path)
    if not event_path.is_file():
        return []

    lines = event_path.read_text(encoding="utf-8").splitlines()
    if limit is not None:
        lines = lines[-max(int(limit), 0) :]

    events: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def clear_events(event_file_path: str | Path | None = None) -> None:
    """Delete the local analytics JSONL log file if it exists."""
    event_path = _resolve_event_path(event_file_path)
    try:
        event_path.unlink(missing_ok=True)
    except TypeError:
        if event_path.exists():
            event_path.unlink()


def _resolve_event_path(event_file_path: str | Path | None = None) -> Path:
    return Path(event_file_path) if event_file_path is not None else EVENT_LOG_PATH


def _get_streamlit_script_context_getter() -> Any:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx
    except Exception:
        try:
            from streamlit.runtime.scriptrunner_utils.script_run_context import get_script_run_ctx

            return get_script_run_ctx
        except Exception:
            return None


def _safe_properties(properties: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(properties, dict):
        return {}
    return {str(key): _safe_value(key, value) for key, value in properties.items()}


def _safe_value(key: Any, value: Any) -> Any:
    key_text = str(key).lower()
    if any(token in key_text for token in ("phone", "mobile", "email", "customer_name")):
        return "[redacted]"
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {
            str(child_key): _safe_value(child_key, child_value)
            for child_key, child_value in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        values = list(value)
        if all(item is None or isinstance(item, (bool, int, float, str)) for item in values):
            return values
        return f"[omitted {type(value).__name__}]"
    return f"[omitted {type(value).__name__}]"
