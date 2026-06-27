from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src import project_workspace
from src.engines.field_mapping_engine import infer_field_mappings


FIELD_MAPPING_FILE = "field_mappings.json"


def save_field_mappings(
    project_id: str,
    mappings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized = [_normalize_mapping(item) for item in mappings]
    config_path = _mapping_path(project_id)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = config_path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    temporary_path.replace(config_path)
    project_workspace.update_project(project_id, {"field_mappings": normalized})
    return normalized


def load_field_mappings(project_id: str) -> list[dict[str, Any]]:
    config_path = _mapping_path(project_id)
    if config_path.is_file():
        try:
            content = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("字段映射配置损坏：config/field_mappings.json") from exc
        if not isinstance(content, list):
            raise ValueError("字段映射配置格式无效：应为映射列表。")
        return [_normalize_mapping(item) for item in content]
    project = project_workspace.get_project(project_id)
    mappings = project.get("field_mappings", [])
    return [_normalize_mapping(item) for item in mappings] if isinstance(mappings, list) else []


def merge_existing_mappings(
    df: pd.DataFrame,
    existing_mappings: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    return infer_field_mappings(df, existing_mappings=existing_mappings)


def get_missing_historical_fields(
    df: pd.DataFrame,
    existing_mappings: list[dict[str, Any]] | None,
) -> list[str]:
    current_columns = set(df.columns)
    return [
        str(item["column_name"])
        for item in (existing_mappings or [])
        if item.get("column_name") not in current_columns
    ]


def get_new_fields(
    df: pd.DataFrame,
    existing_mappings: list[dict[str, Any]] | None,
) -> list[str]:
    historical_columns = {
        item.get("column_name") for item in (existing_mappings or [])
    }
    return [str(column) for column in df.columns if column not in historical_columns]


def confirmed_columns_by_type(
    mappings: list[dict[str, Any]] | None,
    field_type: str,
) -> list[Any]:
    return [
        item["column_name"]
        for item in (mappings or [])
        if item.get("confirmed_type") == field_type
    ]


def prioritize_business_fields(
    df: pd.DataFrame,
    mappings: list[dict[str, Any]] | None,
    business_fields: dict[str, Any],
) -> dict[str, Any]:
    """Prioritize confirmed project mappings in the existing business field model."""
    result = dict(business_fields)
    mapped_dates = _available_columns(df, mappings, ("日期字段",))
    mapped_amounts = _available_columns(df, mappings, ("金额字段",), numeric_only=True)
    mapped_metrics = _available_columns(
        df,
        mappings,
        ("金额字段", "数量字段"),
        numeric_only=True,
    )
    mapped_dimensions = _available_columns(
        df,
        mappings,
        ("区域字段", "产品字段", "人员字段"),
    )
    mapped_identifiers = set(_available_columns(df, mappings, ("ID字段",)))

    if mapped_dates:
        result["date_column"] = mapped_dates[0]
    if mapped_amounts:
        result["amount_column"] = mapped_amounts[0]

    excluded = mapped_identifiers | set(mapped_dates)
    result["numeric_metrics"] = _deduplicate(
        [
            column
            for column in mapped_metrics + list(result.get("numeric_metrics", []))
            if column not in excluded
        ]
    )
    result["dimensions"] = _deduplicate(
        mapped_dimensions + list(result.get("dimensions", []))
    )
    return result


def prioritize_dashboard_fields(
    df: pd.DataFrame,
    mappings: list[dict[str, Any]] | None,
    dashboard_fields: dict[str, Any],
) -> dict[str, Any]:
    """Use confirmed mappings as the default fields for Excel Dashboard export."""
    result = dict(dashboard_fields)
    mapping_to_dashboard_key = {
        "日期字段": "date_column",
        "金额字段": "amount_column",
        "产品字段": "product_column",
        "区域字段": "region_column",
    }
    for field_type, dashboard_key in mapping_to_dashboard_key.items():
        numeric_only = field_type == "金额字段"
        columns = _available_columns(
            df,
            mappings,
            (field_type,),
            numeric_only=numeric_only,
        )
        if columns:
            result[dashboard_key] = columns[0]
    return result


def mapping_business_summary(
    df: pd.DataFrame,
    mappings: list[dict[str, Any]] | None,
) -> dict[str, list[Any]]:
    """Return a compact mapping summary for downstream report exports."""
    return {
        field_type: _available_columns(df, mappings, (field_type,))
        for field_type in ("日期字段", "金额字段", "区域字段", "产品字段", "人员字段")
    }


def _mapping_path(project_id: str) -> Path:
    return (
        project_workspace.get_project_path(project_id)
        / "config"
        / FIELD_MAPPING_FILE
    )


def _available_columns(
    df: pd.DataFrame,
    mappings: list[dict[str, Any]] | None,
    field_types: tuple[str, ...],
    numeric_only: bool = False,
) -> list[Any]:
    columns = []
    for item in mappings or []:
        column = item.get("column_name")
        if item.get("confirmed_type") not in field_types or column not in df.columns:
            continue
        if numeric_only and not pd.api.types.is_numeric_dtype(df[column]):
            continue
        columns.append(column)
    return _deduplicate(columns)


def _deduplicate(columns: list[Any]) -> list[Any]:
    return list(dict.fromkeys(columns))


def _normalize_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    return {
        "column_name": mapping.get("column_name"),
        "pandas_dtype": str(mapping.get("pandas_dtype", "")),
        "inferred_type": str(mapping.get("inferred_type", "其他字段")),
        "confidence": float(mapping.get("confidence", 0)),
        "reason": str(mapping.get("reason", "")),
        "confirmed_type": str(
            mapping.get("confirmed_type")
            or mapping.get("inferred_type")
            or "其他字段"
        ),
    }
