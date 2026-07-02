from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src import project_workspace
from src.engines.relationship_engine import (
    connectable_columns,
    discover_relationship_candidates,
)
from src.services.current_dataset_service import (
    list_project_datasets,
    load_project_dataset_dataframe,
)
from src.services.field_mapping_service import load_field_mappings


RELATIONSHIP_FILE = "table_relationships.json"
RELATIONSHIP_TYPES = ("one_to_one", "one_to_many", "many_to_one", "many_to_many")


def list_project_tables(project_id: str) -> list[dict[str, Any]]:
    tables = []
    for dataset in list_project_datasets(project_id):
        tables.append(_dataset_to_table(dataset))
    return tables


def load_relationship_table_dataframe(project_id: str, table_id: str):
    _find_table(project_id, table_id)
    return load_project_dataset_dataframe(project_id, table_id)


def discover_project_relationships(project_id: str) -> list[dict[str, Any]]:
    mapping_overrides = _field_mapping_overrides(project_id)
    tables = []
    for table in list_project_tables(project_id):
        try:
            dataframe = load_relationship_table_dataframe(project_id, table["table_id"])
        except Exception:
            continue
        tables.append(
            {
                **table,
                "dataframe": dataframe,
                "field_mapping_overrides": mapping_overrides,
            }
        )
    return discover_relationship_candidates(tables)


def get_project_table_columns(
    project_id: str,
    table_id: str,
    connectable_only: bool = False,
    fallback_to_all: bool = True,
) -> list[str]:
    dataframe = load_relationship_table_dataframe(project_id, table_id)
    if connectable_only:
        candidates = connectable_columns(dataframe, _field_mapping_overrides(project_id))
        if candidates or not fallback_to_all:
            return candidates
    return [str(column) for column in dataframe.columns]


def save_table_relationships(
    project_id: str,
    relationships: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized = [
        _hydrate_relationship_metadata(project_id, _normalize_relationship(item))
        for item in relationships
    ]
    _validate_relationships(project_id, normalized)
    config_path = _relationship_path(project_id)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = config_path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(config_path)
    project_workspace.update_project(project_id, {"table_relationships": normalized})
    return normalized


def delete_table_relationship(project_id: str, relationship_id: str) -> list[dict[str, Any]]:
    relationships = load_table_relationships(project_id)
    remaining = [
        item
        for item in relationships
        if item.get("relationship_id") != relationship_id
    ]
    if len(remaining) == len(relationships):
        raise ValueError(f"表关系不存在：{relationship_id}")
    return save_table_relationships(project_id, remaining)


def clear_table_relationships(project_id: str) -> list[dict[str, Any]]:
    return save_table_relationships(project_id, [])


def load_table_relationships(project_id: str) -> list[dict[str, Any]]:
    config_path = _relationship_path(project_id)
    if config_path.is_file():
        try:
            content = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("表关系配置损坏：config/table_relationships.json") from exc
        if not isinstance(content, list):
            raise ValueError("表关系配置格式无效：应为关系列表。")
        return [_normalize_relationship(item) for item in content]
    project = project_workspace.get_project(project_id)
    relationships = project.get("table_relationships", [])
    return (
        [_normalize_relationship(item) for item in relationships]
        if isinstance(relationships, list)
        else []
    )


def _validate_relationships(project_id: str, relationships: list[dict[str, Any]]) -> None:
    table_columns = {
        table["table_id"]: set(get_project_table_columns(project_id, table["table_id"]))
        for table in list_project_tables(project_id)
    }
    for relationship in relationships:
        table_a_id = relationship["table_a_id"]
        table_b_id = relationship["table_b_id"]
        if table_a_id == table_b_id:
            raise ValueError("表A和表B不能是同一个数据表。")
        if table_a_id not in table_columns:
            raise ValueError(f"表A不存在或无法读取：{table_a_id}")
        if table_b_id not in table_columns:
            raise ValueError(f"表B不存在或无法读取：{table_b_id}")
        if relationship["field_a"] not in table_columns[table_a_id]:
            raise ValueError(f"表A连接字段不存在：{relationship['field_a']}")
        if relationship["field_b"] not in table_columns[table_b_id]:
            raise ValueError(f"表B连接字段不存在：{relationship['field_b']}")
    if _has_relationship_cycle(relationships):
        raise ValueError("该关系会造成循环依赖，请调整表关系。")


def _normalize_relationship(relationship: dict[str, Any]) -> dict[str, Any]:
    migrated = _migrate_legacy_relationship(relationship)
    required = ("table_a_id", "field_a", "table_b_id", "field_b")
    missing = [key for key in required if not migrated.get(key)]
    if missing:
        raise ValueError(f"表关系缺少必要字段：{', '.join(missing)}")
    relationship_type = str(migrated.get("relationship_type", "many_to_one"))
    if relationship_type not in RELATIONSHIP_TYPES:
        relationship_type = "many_to_one"
    confidence = float(migrated.get("confidence", 0))
    if confidence <= 1:
        confidence *= 100
    return {
        "relationship_id": migrated.get("relationship_id") or uuid.uuid4().hex,
        "table_a_id": str(migrated["table_a_id"]),
        "table_a_name": str(migrated.get("table_a_name", "")),
        "table_a_file_id": str(migrated.get("table_a_file_id", "")),
        "table_a_file_name": str(migrated.get("table_a_file_name", "")),
        "table_a_sheet_name": _optional_str(migrated.get("table_a_sheet_name")),
        "table_a_dataset_id": str(migrated.get("table_a_dataset_id") or migrated["table_a_id"]),
        "table_a_dataset_name": str(migrated.get("table_a_dataset_name", "")),
        "table_a_dataset_type": str(migrated.get("table_a_dataset_type", "")),
        "table_a_source": str(migrated.get("table_a_source", "")),
        "table_a_file_path": str(migrated.get("table_a_file_path", "")),
        "table_a_is_generated": bool(migrated.get("table_a_is_generated", False)),
        "table_a_source_files": migrated.get("table_a_source_files", []),
        "field_a": str(migrated["field_a"]),
        "table_b_id": str(migrated["table_b_id"]),
        "table_b_name": str(migrated.get("table_b_name", "")),
        "table_b_file_id": str(migrated.get("table_b_file_id", "")),
        "table_b_file_name": str(migrated.get("table_b_file_name", "")),
        "table_b_sheet_name": _optional_str(migrated.get("table_b_sheet_name")),
        "table_b_dataset_id": str(migrated.get("table_b_dataset_id") or migrated["table_b_id"]),
        "table_b_dataset_name": str(migrated.get("table_b_dataset_name", "")),
        "table_b_dataset_type": str(migrated.get("table_b_dataset_type", "")),
        "table_b_source": str(migrated.get("table_b_source", "")),
        "table_b_file_path": str(migrated.get("table_b_file_path", "")),
        "table_b_is_generated": bool(migrated.get("table_b_is_generated", False)),
        "table_b_source_files": migrated.get("table_b_source_files", []),
        "field_b": str(migrated["field_b"]),
        "relationship_type": relationship_type,
        "confidence": round(confidence, 2),
        "score_breakdown": migrated.get("score_breakdown", {}),
        "reason": str(migrated.get("reason", "用户手动确认")),
        "source": str(migrated.get("source", "manual")),
        "confirmed_at": str(migrated.get("confirmed_at") or _utc_now()),
    }


def _migrate_legacy_relationship(relationship: dict[str, Any]) -> dict[str, Any]:
    if relationship.get("table_a_id"):
        return relationship
    return {
        **relationship,
        "table_a_id": relationship.get("main_table_id"),
        "table_a_name": relationship.get("main_table_name"),
        "table_a_file_id": relationship.get("main_file_id"),
        "table_a_file_name": relationship.get("main_file_name"),
        "table_a_sheet_name": relationship.get("main_sheet_name"),
        "field_a": relationship.get("main_column"),
        "table_b_id": relationship.get("target_table_id"),
        "table_b_name": relationship.get("target_table_name"),
        "table_b_file_id": relationship.get("target_file_id"),
        "table_b_file_name": relationship.get("target_file_name"),
        "table_b_sheet_name": relationship.get("target_sheet_name"),
        "field_b": relationship.get("target_column"),
        "relationship_type": relationship.get("relationship_type", "many_to_one"),
    }


def _find_table(project_id: str, table_id: str) -> dict[str, Any]:
    for table in list_project_tables(project_id):
        if table["table_id"] == table_id:
            return table
    raise FileNotFoundError(f"项目数据表不存在：{table_id}")


def _dataset_to_table(dataset: dict[str, Any]) -> dict[str, Any]:
    dataset_id = str(dataset.get("dataset_id", ""))
    dataset_name = str(dataset.get("dataset_name") or dataset_id)
    dataset_type = str(dataset.get("dataset_type") or "uploaded")
    sheet_name = dataset.get("sheet_name")
    file_name = str(dataset.get("file_name") or dataset_name)
    return {
        "table_id": dataset_id,
        "table_name": dataset_name,
        "file_id": str(dataset.get("source_file_id") or dataset_id),
        "file_name": file_name,
        "sheet_name": sheet_name,
        "rows": int(dataset.get("row_count") or dataset.get("rows") or 0),
        "columns": int(dataset.get("column_count") or dataset.get("columns") or 0),
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "dataset_type": dataset_type,
        "source": str(dataset.get("source") or dataset_type),
        "file_path": str(dataset.get("file_path") or ""),
        "is_generated": dataset_type != "uploaded",
        "source_files": dataset.get("source_files", []) or [],
    }


def _hydrate_relationship_metadata(
    project_id: str,
    relationship: dict[str, Any],
) -> dict[str, Any]:
    table_by_id = {table["table_id"]: table for table in list_project_tables(project_id)}
    hydrated = dict(relationship)
    for side in ("a", "b"):
        table = table_by_id.get(hydrated.get(f"table_{side}_id"))
        if not table:
            continue
        hydrated[f"table_{side}_name"] = hydrated.get(f"table_{side}_name") or table["table_name"]
        hydrated[f"table_{side}_file_id"] = hydrated.get(f"table_{side}_file_id") or table["file_id"]
        hydrated[f"table_{side}_file_name"] = hydrated.get(f"table_{side}_file_name") or table["file_name"]
        hydrated[f"table_{side}_sheet_name"] = hydrated.get(f"table_{side}_sheet_name") or table["sheet_name"]
        hydrated[f"table_{side}_dataset_id"] = table["dataset_id"]
        hydrated[f"table_{side}_dataset_name"] = table["dataset_name"]
        hydrated[f"table_{side}_dataset_type"] = table["dataset_type"]
        hydrated[f"table_{side}_source"] = table["source"]
        hydrated[f"table_{side}_file_path"] = table["file_path"]
        hydrated[f"table_{side}_is_generated"] = table["is_generated"]
        hydrated[f"table_{side}_source_files"] = table["source_files"]
    return hydrated


def _has_relationship_cycle(relationships: list[dict[str, Any]]) -> bool:
    graph: dict[str, set[str]] = {}
    for relationship in relationships:
        table_a_id = str(relationship.get("table_a_id", ""))
        table_b_id = str(relationship.get("table_b_id", ""))
        if not table_a_id or not table_b_id:
            continue
        graph.setdefault(table_a_id, set()).add(table_b_id)
        graph.setdefault(table_b_id, set())

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(table_id: str) -> bool:
        if table_id in visiting:
            return True
        if table_id in visited:
            return False
        visiting.add(table_id)
        for next_table_id in graph.get(table_id, set()):
            if visit(next_table_id):
                return True
        visiting.remove(table_id)
        visited.add(table_id)
        return False

    return any(visit(table_id) for table_id in graph)


def _field_mapping_overrides(project_id: str) -> dict[str, str]:
    try:
        mappings = load_field_mappings(project_id)
    except ValueError:
        return {}
    return {
        str(item["column_name"]): str(item["confirmed_type"])
        for item in mappings
        if item.get("column_name") and item.get("confirmed_type")
    }


def _table_id(file_id: str, sheet_name: str) -> str:
    return f"{file_id}::{sheet_name}"


def _relationship_path(project_id: str) -> Path:
    return project_workspace.get_project_path(project_id) / "config" / RELATIONSHIP_FILE


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
