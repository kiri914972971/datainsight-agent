from __future__ import annotations

import json
import math
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src import project_workspace


HISTORY_FILE_NAME = "saved_business_queries.json"
HISTORY_VERSION = 1


def get_saved_queries_path(project_id: str) -> Path:
    return project_workspace.get_project_path(project_id) / "analysis" / HISTORY_FILE_NAME


def load_saved_queries(project_id: str) -> list[dict]:
    history_path = get_saved_queries_path(project_id)
    if not history_path.is_file():
        return []
    try:
        with history_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        return []
    return [
        record
        for record in payload["records"]
        if isinstance(record, dict) and str(record.get("id") or "").strip()
    ]


def save_query(
    project_id: str,
    question: str,
    query_plan: dict,
    result_df: pd.DataFrame,
    explanation: str,
    dataset_key: str,
    dataset_name: str,
    *,
    is_identifier_dimension: bool = False,
) -> dict:
    if not isinstance(result_df, pd.DataFrame):
        raise TypeError("result_df must be a pandas DataFrame.")

    result_columns, result_rows = dataframe_to_json_data(result_df)
    record = {
        "id": str(uuid.uuid4()),
        "question": str(question),
        "query_plan": _to_json_value(query_plan),
        "result_columns": result_columns,
        "result_rows": result_rows,
        "explanation": str(explanation or ""),
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "dataset_key": str(dataset_key or ""),
        "dataset_name": str(dataset_name or ""),
        "result_row_count": int(len(result_df)),
        "is_identifier_dimension": bool(is_identifier_dimension),
    }
    records = load_saved_queries(project_id)
    records.append(record)
    _write_records(project_id, records)
    return record


def delete_saved_query(project_id: str, record_id: str) -> bool:
    records = load_saved_queries(project_id)
    remaining = [record for record in records if record.get("id") != record_id]
    if len(remaining) == len(records):
        return False
    _write_records(project_id, remaining)
    return True


def get_saved_query(project_id: str, record_id: str) -> dict | None:
    return next(
        (
            record
            for record in load_saved_queries(project_id)
            if record.get("id") == record_id
        ),
        None,
    )


def get_saved_queries_for_dataset(project_id: str, dataset_key: str) -> list[dict]:
    resolved_dataset_key = str(dataset_key or "").strip()
    if not resolved_dataset_key:
        return []
    records = [
        record
        for record in load_saved_queries(project_id)
        if str(record.get("dataset_key") or "") == resolved_dataset_key
    ]
    return sorted(records, key=lambda record: str(record.get("saved_at") or ""))


def build_saved_business_query_report_context(records: list[dict]) -> list[dict]:
    context = []
    for record in records:
        if not isinstance(record, dict):
            continue
        query_plan = (
            record.get("query_plan")
            if isinstance(record.get("query_plan"), dict)
            else {}
        )
        result_df = dataframe_from_saved_query(record)
        dimension = str(query_plan.get("dimension") or "-")
        if record.get("is_identifier_dimension") and dimension in result_df.columns:
            result_df[dimension] = result_df[dimension].map(_identifier_string)
        try:
            result_row_count = int(record.get("result_row_count") or len(result_df))
        except (TypeError, ValueError):
            result_row_count = len(result_df)
        context.append(
            {
                "id": str(record.get("id") or ""),
                "question": str(record.get("question") or "-"),
                "query_plan": query_plan,
                "metric": str(query_plan.get("metric") or "-"),
                "dimension": dimension,
                "result_df": result_df,
                "result_columns": list(result_df.columns),
                "result_rows": result_df.to_dict("records"),
                "explanation": str(record.get("explanation") or "-"),
                "saved_at": str(record.get("saved_at") or ""),
                "dataset_key": str(record.get("dataset_key") or ""),
                "dataset_name": str(record.get("dataset_name") or "-"),
                "result_row_count": result_row_count,
                "is_identifier_dimension": bool(
                    record.get("is_identifier_dimension")
                ),
            }
        )
    return context


def dataframe_to_json_data(dataframe: pd.DataFrame) -> tuple[list[str], list[dict]]:
    columns = [str(column) for column in dataframe.columns]
    rows = []
    for values in dataframe.itertuples(index=False, name=None):
        rows.append(
            {
                column: _to_json_value(value)
                for column, value in zip(columns, values)
            }
        )
    return columns, rows


def dataframe_from_saved_query(record: dict) -> pd.DataFrame:
    columns = [str(column) for column in record.get("result_columns", [])]
    rows = record.get("result_rows", [])
    if not isinstance(rows, list):
        rows = []
    normalized_rows = [row for row in rows if isinstance(row, dict)]
    return pd.DataFrame(normalized_rows, columns=columns or None)


def _write_records(project_id: str, records: list[dict]) -> None:
    history_path = get_saved_queries_path(project_id)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = history_path.with_name(
        f".{history_path.name}.{uuid.uuid4().hex}.tmp"
    )
    payload = {
        "version": HISTORY_VERSION,
        "records": _to_json_value(records),
    }
    try:
        with temporary_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
        temporary_path.replace(history_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _to_json_value(value: Any) -> Any:
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, dict):
        return {str(key): _to_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_json_value(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if hasattr(value, "item") and callable(value.item):
        try:
            return _to_json_value(value.item())
        except (TypeError, ValueError):
            pass
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (str, int, bool)):
        return value
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def _identifier_string(value: Any) -> str:
    if value is None or value is pd.NA or value is pd.NaT:
        return ""
    if pd.api.types.is_integer(value):
        return str(int(value))
    if pd.api.types.is_float(value):
        numeric_value = float(value)
        if not math.isfinite(numeric_value):
            return ""
        if numeric_value.is_integer():
            return f"{numeric_value:.0f}"
        return f"{numeric_value:f}".rstrip("0").rstrip(".")
    return str(value)
