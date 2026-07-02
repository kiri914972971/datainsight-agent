from __future__ import annotations

import re
import uuid
from typing import Any

import pandas as pd

from src.engines.field_mapping_engine import infer_field_mappings


RECOMMENDATION_THRESHOLD = 70
CONNECTABLE_FIELD_TYPES = {"ID字段", "日期字段"}
NON_CONNECTABLE_FIELD_TYPES = {"金额字段"}


def discover_relationship_candidates(tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Recommend explainable cross-table relationships with a 100-point score."""
    candidates = []
    for left_index, left in enumerate(tables):
        for right in tables[left_index + 1 :]:
            candidates.extend(_compare_tables(left, right))
    return sorted(
        candidates,
        key=lambda item: (-item["confidence"], item["table_a_name"], item["field_a"]),
    )


def profile_relationship_columns(
    dataframe: pd.DataFrame,
    mapping_overrides: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    row_count = len(dataframe)
    mapping_by_column = {
        item["column_name"]: item["confirmed_type"]
        for item in infer_field_mappings(dataframe)
    }
    mapping_by_column.update(
        {
            column: field_type
            for column, field_type in (mapping_overrides or {}).items()
            if column in dataframe.columns
        }
    )
    profiles = []
    for column in dataframe.columns:
        non_null = int(dataframe[column].notna().sum())
        unique = int(dataframe[column].nunique(dropna=True))
        profiles.append(
            {
                "column_name": str(column),
                "pandas_dtype": str(dataframe[column].dtype),
                "type_family": _type_family(dataframe[column]),
                "mapping_type": mapping_by_column.get(column, "其他字段"),
                "unique_count": unique,
                "unique_ratio": unique / non_null if non_null else 0.0,
                "row_count": row_count,
            }
        )
    return profiles


def connectable_columns(
    dataframe: pd.DataFrame,
    mapping_overrides: dict[str, str] | None = None,
) -> list[str]:
    """Return relationship-friendly fields while excluding measures such as amount."""
    profiles = profile_relationship_columns(dataframe, mapping_overrides)
    preferred = [
        item["column_name"]
        for item in profiles
        if item["mapping_type"] in CONNECTABLE_FIELD_TYPES
    ]
    secondary = [
        item["column_name"]
        for item in profiles
        if item["mapping_type"] not in NON_CONNECTABLE_FIELD_TYPES
        and item["column_name"] not in preferred
        and item["unique_ratio"] >= 0.8
    ]
    return preferred + secondary


def _compare_tables(left: dict[str, Any], right: dict[str, Any]) -> list[dict[str, Any]]:
    left_profiles = profile_relationship_columns(
        left["dataframe"],
        left.get("field_mapping_overrides"),
    )
    right_profiles = profile_relationship_columns(
        right["dataframe"],
        right.get("field_mapping_overrides"),
    )
    candidates = []
    for left_column in left_profiles:
        for right_column in right_profiles:
            score_parts = _score_relationship(left_column, right_column)
            score = sum(score_parts.values())
            if score < RECOMMENDATION_THRESHOLD:
                continue
            if (
                left_column["mapping_type"] in NON_CONNECTABLE_FIELD_TYPES
                or right_column["mapping_type"] in NON_CONNECTABLE_FIELD_TYPES
            ):
                continue
            table_a, field_a, table_b, field_b = _relationship_direction(
                left,
                left_column,
                right,
                right_column,
            )
            signature = (
                f"{table_a['table_id']}:{field_a['column_name']}<->"
                f"{table_b['table_id']}:{field_b['column_name']}"
            )
            candidates.append(
                {
                    "relationship_id": uuid.uuid5(uuid.NAMESPACE_URL, signature).hex,
                    **_table_fields("table_a", table_a, field_a["column_name"]),
                    **_table_fields("table_b", table_b, field_b["column_name"]),
                    "relationship_type": "many_to_one",
                    "confidence": score,
                    "score_breakdown": score_parts,
                    "reason": _score_reason(score_parts, field_a, field_b),
                    "source": "auto",
                }
            )
    return candidates


def _score_relationship(left: dict[str, Any], right: dict[str, Any]) -> dict[str, int]:
    exact_name = _normalize_name(left["column_name"]) == _normalize_name(right["column_name"])
    mapping_match = left["mapping_type"] == right["mapping_type"]
    dtype_match = left["type_family"] == right["type_family"]
    uniqueness_close = abs(left["unique_ratio"] - right["unique_ratio"]) <= 0.2
    return {
        "字段名完全一致": 50 if exact_name else 0,
        "字段映射类型一致": 20 if mapping_match else 0,
        "数据类型一致": 20 if dtype_match else 0,
        "唯一值比例接近": 10 if uniqueness_close else 0,
    }


def _relationship_direction(left, left_column, right, right_column):
    left_key = (left_column["unique_ratio"], -left_column["row_count"])
    right_key = (right_column["unique_ratio"], -right_column["row_count"])
    if left_key <= right_key:
        return left, left_column, right, right_column
    return right, right_column, left, left_column


def _table_fields(prefix: str, table: dict[str, Any], column: str) -> dict[str, Any]:
    return {
        f"{prefix}_id": table["table_id"],
        f"{prefix}_name": table["table_name"],
        f"{prefix}_file_id": table["file_id"],
        f"{prefix}_file_name": table["file_name"],
        f"{prefix}_sheet_name": table["sheet_name"],
        f"{prefix}_dataset_id": table.get("dataset_id", table["table_id"]),
        f"{prefix}_dataset_name": table.get("dataset_name", table["table_name"]),
        f"{prefix}_dataset_type": table.get("dataset_type", ""),
        f"{prefix}_source": table.get("source", ""),
        f"{prefix}_file_path": table.get("file_path", ""),
        f"{prefix}_is_generated": table.get("is_generated", False),
        f"{prefix}_source_files": table.get("source_files", []),
        f"field_{prefix[-1]}": column,
    }


def _score_reason(
    score_parts: dict[str, int],
    field_a: dict[str, Any],
    field_b: dict[str, Any],
) -> str:
    matched = [label for label, score in score_parts.items() if score]
    return (
        "、".join(matched)
        + f"；唯一值比例分别为 {field_a['unique_ratio']:.1%} 和 {field_b['unique_ratio']:.1%}。"
    )


def _normalize_name(value: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(value).strip().lower())


def _type_family(series: pd.Series) -> str:
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    return "text"
