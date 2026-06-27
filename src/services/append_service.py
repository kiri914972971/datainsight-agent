from __future__ import annotations

import json
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd

from src import project_workspace
from src.services.current_dataset_service import (
    register_project_dataset,
    set_current_analysis_dataset,
)
from src.services.data_source_service import (
    list_project_data_files,
    load_project_data_file,
)


ANALYSIS_DIR = "analysis"
APPENDED_DATASET_FILE = "appended_dataset.csv"
APPENDED_METADATA_FILE = "appended_dataset_meta.json"
FILL_STRATEGY_BLANK = "blank"
FILL_STRATEGY_ZERO = "zero"
FILL_STRATEGY_UNKNOWN = "unknown"
FILL_STRATEGY_MODE = "mode"
FILL_STRATEGY_CUSTOM = "custom"
SUPPORTED_FILL_STRATEGIES = {
    FILL_STRATEGY_BLANK,
    FILL_STRATEGY_ZERO,
    FILL_STRATEGY_UNKNOWN,
    FILL_STRATEGY_MODE,
    FILL_STRATEGY_CUSTOM,
}


def list_append_sources(project_id: str) -> list[dict[str, Any]]:
    sources = []
    for file_metadata in list_project_data_files(project_id):
        for sheet in file_metadata.get("sheets", []):
            source_id = _source_id(file_metadata["file_id"], sheet["sheet_name"])
            sources.append(
                {
                    "source_id": source_id,
                    "file_id": file_metadata["file_id"],
                    "file_name": file_metadata["file_name"],
                    "file_type": file_metadata["file_type"],
                    "sheet_name": sheet["sheet_name"],
                    "rows": sheet.get("rows", 0),
                    "columns": sheet.get("columns", 0),
                    "label": f"{file_metadata['file_name']} / {sheet['sheet_name']}",
                }
            )
    return sources


def analyze_append_compatibility(
    project_id: str,
    source_ids: list[str],
) -> dict[str, Any]:
    loaded_sources = _load_sources(project_id, source_ids)
    if len(loaded_sources) < 2:
        raise ValueError("请至少选择两个数据表进行合并。")

    columns_by_source = {
        source["source_id"]: [str(column) for column in source["dataframe"].columns]
        for source in loaded_sources
    }
    all_fields = _ordered_union(columns_by_source.values())
    common_fields = [
        field
        for field in all_fields
        if all(field in columns for columns in columns_by_source.values())
    ]
    missing_by_source = {
        source["source_id"]: [
            field for field in all_fields if field not in columns_by_source[source["source_id"]]
        ]
        for source in loaded_sources
    }
    only_by_source = {
        source["source_id"]: [
            field
            for field in columns_by_source[source["source_id"]]
            if sum(field in columns for columns in columns_by_source.values()) == 1
        ]
        for source in loaded_sources
    }
    order_different = len({tuple(columns) for columns in columns_by_source.values()}) > 1
    similar_fields = _detect_similar_fields(only_by_source, columns_by_source)
    return {
        "source_tables": [_source_summary(source) for source in loaded_sources],
        "common_fields": common_fields,
        "all_fields": all_fields,
        "missing_fields_by_source": missing_by_source,
        "only_fields_by_source": only_by_source,
        "suggested_null_fields": {
            source_id: fields
            for source_id, fields in missing_by_source.items()
            if fields
        },
        "field_order_different": order_different,
        "similar_fields": similar_fields,
        "schema_similarity": _schema_similarity(columns_by_source),
    }


def build_appended_dataset(
    project_id: str,
    source_ids: list[str],
    fill_strategies: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    compatibility = analyze_append_compatibility(project_id, source_ids)
    loaded_sources = _load_sources(project_id, source_ids)
    all_fields = compatibility["all_fields"]
    normalized_fill_strategies = _normalize_fill_strategies(
        compatibility,
        loaded_sources,
        fill_strategies,
    )
    strategy_by_field = {
        item["field"]: item
        for item in normalized_fill_strategies
    }
    frames = []
    before_rows = []
    for source in loaded_sources:
        dataframe = source["dataframe"].copy()
        dataframe.columns = [str(column) for column in dataframe.columns]
        for field in all_fields:
            if field not in dataframe.columns:
                strategy = strategy_by_field.get(field, {"strategy": FILL_STRATEGY_BLANK})
                dataframe[field] = _fill_value_for_strategy(
                    field,
                    strategy,
                    loaded_sources,
                )
        dataframe = dataframe[all_fields]
        frames.append(dataframe)
        before_rows.append(
            {
                "source_id": source["source_id"],
                "file_name": source["file_name"],
                "sheet_name": source["sheet_name"],
                "rows": int(len(dataframe)),
            }
        )

    appended = pd.concat(frames, ignore_index=True)
    before_total_rows = sum(item["rows"] for item in before_rows)
    suggested_null_fields = compatibility["suggested_null_fields"]
    filled_null_fields = sorted(
        {
            field
            for fields in suggested_null_fields.values()
            for field in fields
        }
    )
    missing_fields = [
        {
            "source_id": source_id,
            "fields": list(fields),
        }
        for source_id, fields in compatibility["missing_fields_by_source"].items()
        if fields
    ]
    analysis_path = _analysis_path(project_id)
    analysis_path.mkdir(parents=True, exist_ok=True)
    dataset_path = analysis_path / APPENDED_DATASET_FILE
    appended.to_csv(dataset_path, index=False, encoding="utf-8-sig")

    metadata = {
        "dataset_name": "appended_dataset",
        "dataset_display_name": "合并数据集 appended_dataset.csv",
        "file_name": APPENDED_DATASET_FILE,
        "file_path": f"{ANALYSIS_DIR}/{APPENDED_DATASET_FILE}",
        "saved_path": f"workspace/projects/{project_id}/{ANALYSIS_DIR}/{APPENDED_DATASET_FILE}",
        "metadata_path": f"workspace/projects/{project_id}/{ANALYSIS_DIR}/{APPENDED_METADATA_FILE}",
        "source_tables": compatibility["source_tables"],
        "source_file_count": len(loaded_sources),
        "missing_fields": missing_fields,
        "auto_fill_strategy": "NaN",
        "fill_strategies": normalized_fill_strategies,
        "source_files": [
            {
                "file_name": source["file_name"],
                "sheet_name": source["sheet_name"],
                "rows": int(len(source["dataframe"])),
            }
            for source in loaded_sources
        ],
        "before_rows": before_rows,
        "before_total_rows": int(before_total_rows),
        "after_rows": int(len(appended)),
        "columns": int(len(appended.columns)),
        "validation_summary": {
            "before_total_rows": int(before_total_rows),
            "after_rows": int(len(appended)),
            "row_count_matches": bool(before_total_rows == len(appended)),
            "columns": int(len(appended.columns)),
            "has_filled_null_fields": bool(filled_null_fields),
            "filled_null_fields": filled_null_fields,
        },
        "field_alignment": {
            "common_fields": compatibility["common_fields"],
            "all_fields": compatibility["all_fields"],
            "missing_fields_by_source": compatibility["missing_fields_by_source"],
            "only_fields_by_source": compatibility["only_fields_by_source"],
            "suggested_null_fields": compatibility["suggested_null_fields"],
            "field_order_different": compatibility["field_order_different"],
            "similar_fields": compatibility["similar_fields"],
            "schema_similarity": compatibility["schema_similarity"],
        },
        "created_at": _utc_now(),
        "file_size": dataset_path.stat().st_size,
    }
    metadata_path = analysis_path / APPENDED_METADATA_FILE
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    project_workspace.update_project(project_id, {"appended_dataset": metadata})
    register_project_dataset(
        project_id,
        {
            "dataset_id": "appended_dataset",
            "dataset_name": APPENDED_DATASET_FILE,
            "dataset_type": "appended",
            "file_path": metadata["file_path"],
            "sheet_name": None,
            "source": "append",
            "created_at": metadata.get("created_at", ""),
            "row_count": metadata.get("after_rows"),
            "column_count": metadata.get("columns"),
            "source_files": metadata.get("source_files", []),
        },
    )
    return metadata


def load_appended_dataset(project_id: str) -> pd.DataFrame:
    dataset_path = _analysis_path(project_id) / APPENDED_DATASET_FILE
    if not dataset_path.is_file():
        raise FileNotFoundError("当前项目还没有生成 appended_dataset.csv。")
    return pd.read_csv(dataset_path)


def get_appended_dataset_metadata(project_id: str) -> dict[str, Any] | None:
    metadata_path = _analysis_path(project_id) / APPENDED_METADATA_FILE
    if metadata_path.is_file():
        try:
            return json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("数据合并元数据损坏：analysis/appended_dataset_meta.json") from exc
    project = project_workspace.get_project(project_id)
    metadata = project.get("appended_dataset")
    return metadata if isinstance(metadata, dict) else None


def set_appended_dataset_as_current(project_id: str) -> dict[str, Any]:
    metadata = get_appended_dataset_metadata(project_id)
    if not metadata:
        raise FileNotFoundError("当前项目还没有生成 appended_dataset.csv。")
    dataset = set_current_analysis_dataset(
        project_id,
        {
            "dataset_id": "appended_dataset",
            "dataset_name": APPENDED_DATASET_FILE,
            "dataset_type": "appended",
            "file_path": metadata["file_path"],
            "sheet_name": None,
            "source": "append",
            "created_at": metadata.get("created_at", ""),
            "row_count": metadata.get("after_rows"),
            "column_count": metadata.get("columns"),
        },
    )
    return {
        "source_type": "appended_dataset",
        "file_id": dataset["dataset_id"],
        "file_name": dataset["dataset_name"],
        "display_name": f"合并数据集 {dataset['dataset_name']}",
        "file_path": dataset["file_path"],
        "saved_path": metadata.get(
            "saved_path",
            f"workspace/projects/{project_id}/{ANALYSIS_DIR}/{APPENDED_DATASET_FILE}",
        ),
        "sheet_name": "CSV",
        "created_at": dataset.get("created_at", ""),
        "row_count": dataset.get("row_count"),
        "column_count": dataset.get("column_count"),
    }


def _load_sources(project_id: str, source_ids: list[str]) -> list[dict[str, Any]]:
    source_by_id = {source["source_id"]: source for source in list_append_sources(project_id)}
    loaded = []
    for source_id in source_ids:
        source = source_by_id.get(source_id)
        if source is None:
            raise FileNotFoundError(f"数据表不存在：{source_id}")
        dataframe = load_project_data_file(
            project_id,
            source["file_id"],
            source["sheet_name"],
        )
        loaded.append({**source, "dataframe": dataframe})
    return loaded


def _normalize_fill_strategies(
    compatibility: dict[str, Any],
    loaded_sources: list[dict[str, Any]],
    fill_strategies: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    supplied = {
        str(item.get("field")): item
        for item in fill_strategies or []
        if item.get("field")
    }
    missing_fields_by_source = compatibility["missing_fields_by_source"]
    all_missing_fields = sorted(
        {
            field
            for fields in missing_fields_by_source.values()
            for field in fields
        }
    )
    normalized = []
    for field in all_missing_fields:
        item = supplied.get(field, {})
        strategy = str(item.get("strategy") or FILL_STRATEGY_BLANK)
        if strategy not in SUPPORTED_FILL_STRATEGIES:
            strategy = FILL_STRATEGY_BLANK
        custom_value = item.get("custom_value", "")
        missing_in = [
            source["label"]
            for source in loaded_sources
            if field in missing_fields_by_source.get(source["source_id"], [])
        ]
        normalized.append(
            {
                "field": field,
                "missing_in": missing_in,
                "field_type": _infer_field_type(field, loaded_sources),
                "strategy": strategy,
                "custom_value": "" if custom_value is None else str(custom_value),
            }
        )
    return normalized


def _fill_value_for_strategy(
    field: str,
    strategy: dict[str, Any],
    loaded_sources: list[dict[str, Any]],
) -> Any:
    strategy_name = strategy.get("strategy", FILL_STRATEGY_BLANK)
    if strategy_name == FILL_STRATEGY_ZERO:
        return 0
    if strategy_name == FILL_STRATEGY_UNKNOWN:
        return "未知"
    if strategy_name == FILL_STRATEGY_CUSTOM:
        return strategy.get("custom_value", "")
    if strategy_name == FILL_STRATEGY_MODE:
        return _field_mode(field, loaded_sources)
    return pd.NA


def _field_mode(field: str, loaded_sources: list[dict[str, Any]]) -> Any:
    values = []
    for source in loaded_sources:
        dataframe = source["dataframe"]
        if field in dataframe.columns:
            values.append(dataframe[field].dropna())
    if not values:
        return pd.NA
    series = pd.concat(values, ignore_index=True)
    if series.empty:
        return pd.NA
    modes = series.mode(dropna=True)
    if modes.empty:
        return pd.NA
    return modes.iloc[0]


def _infer_field_type(field: str, loaded_sources: list[dict[str, Any]]) -> str:
    for source in loaded_sources:
        dataframe = source["dataframe"]
        if field in dataframe.columns:
            series = dataframe[field]
            if pd.api.types.is_numeric_dtype(series):
                return "数值字段"
            if pd.api.types.is_datetime64_any_dtype(series):
                return "日期字段"
            unique_ratio = series.nunique(dropna=True) / len(series) if len(series) else 0
            if unique_ratio <= 0.5:
                return "类别字段"
            return "文本字段"
    return "未知字段"


def _ordered_union(column_groups) -> list[str]:
    fields = []
    seen = set()
    for columns in column_groups:
        for column in columns:
            if column not in seen:
                fields.append(column)
                seen.add(column)
    return fields


def _detect_similar_fields(
    only_by_source: dict[str, list[str]],
    columns_by_source: dict[str, list[str]],
) -> list[dict[str, Any]]:
    suggestions = []
    source_ids = list(columns_by_source)
    for index, source_id in enumerate(source_ids):
        for other_source_id in source_ids[index + 1 :]:
            for field in only_by_source.get(source_id, []):
                for other_field in only_by_source.get(other_source_id, []):
                    score = SequenceMatcher(None, field.lower(), other_field.lower()).ratio()
                    if score >= 0.78:
                        suggestions.append(
                            {
                                "source_a": source_id,
                                "field_a": field,
                                "source_b": other_source_id,
                                "field_b": other_field,
                                "similarity": round(score, 3),
                            }
                        )
    return suggestions


def _schema_similarity(columns_by_source: dict[str, list[str]]) -> float:
    source_ids = list(columns_by_source)
    if len(source_ids) < 2:
        return 1.0
    scores = []
    for index, source_id in enumerate(source_ids):
        left = set(columns_by_source[source_id])
        for other_source_id in source_ids[index + 1 :]:
            right = set(columns_by_source[other_source_id])
            denominator = len(left | right)
            scores.append(len(left & right) / denominator if denominator else 1.0)
    return round(sum(scores) / len(scores), 4) if scores else 1.0


def _source_summary(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": source["source_id"],
        "file_name": source["file_name"],
        "sheet_name": source["sheet_name"],
        "rows": int(len(source["dataframe"])),
        "columns": int(len(source["dataframe"].columns)),
    }


def _source_id(file_id: str, sheet_name: str) -> str:
    return f"{file_id}::{sheet_name}"


def _analysis_path(project_id: str) -> Path:
    return project_workspace.get_project_path(project_id) / ANALYSIS_DIR


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
