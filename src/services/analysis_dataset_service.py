from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src import project_workspace
from src.services.current_dataset_service import (
    get_current_analysis_dataset,
    load_current_analysis_dataframe,
    set_current_analysis_dataset,
)
from src.services.data_source_service import load_project_data_file
from src.services.field_mapping_service import load_field_mappings
from src.services.kpi_service import load_kpi_definitions
from src.services.metric_dictionary_service import load_metric_dictionary
from src.services.relationship_service import (
    list_project_tables,
    load_table_relationships,
)


ANALYSIS_DIR = "analysis"
ANALYSIS_DATASET_NAME = "analysis_dataset"
ANALYSIS_DATASET_FILE = "analysis_dataset.csv"
ANALYSIS_METADATA_FILE = "analysis_dataset_meta.json"
SUPPORTED_RELATIONSHIP_TYPES = {
    "one_to_one",
    "one_to_many",
    "many_to_one",
    "many_to_many",
}


def generate_join_plan(project_id: str) -> list[dict[str, Any]]:
    relationships = load_table_relationships(project_id)
    table_frames = _load_project_table_frames(project_id)
    plan = []
    for relationship in relationships:
        table_a = table_frames.get(relationship["table_a_id"])
        table_b = table_frames.get(relationship["table_b_id"])
        if not table_a or not table_b:
            plan.append(_missing_table_plan(relationship))
            continue
        plan.append(
            _build_join_plan_item(
                relationship,
                table_a["dataframe"],
                table_b["dataframe"],
            )
        )
    return plan


def build_analysis_dataset(project_id: str) -> dict[str, Any]:
    """Build a persisted analysis dataset copy from confirmed project relationships."""
    relationships = load_table_relationships(project_id)
    table_frames = _load_project_table_frames(project_id)
    if not relationships:
        raise ValueError("当前项目还没有已确认的表关系，无法生成分析数据集。")
    if not table_frames:
        raise ValueError("当前项目没有可读取的数据源。")

    join_plan = generate_join_plan(project_id)
    base_table = _build_current_base_table(project_id, table_frames)
    base_table_id = base_table["table_id"]
    dataset = base_table["dataframe"].copy()
    source_tables = [_table_source_summary(base_table)]
    applied_relationships = []
    health_checks = _health_checks_from_plan(join_plan)

    applied_table_ids = {base_table_id}
    for relationship in relationships:
        applied = _apply_relationship_join(
            dataset,
            relationship,
            table_frames,
            applied_table_ids,
        )
        if not applied["applied"]:
            applied_relationships.append(applied)
            health_checks.append(
                {
                    "check": "JOIN未执行",
                    "risk_level": "中",
                    "detail": applied["reason"],
                }
            )
            continue
        before_rows = len(dataset)
        before_nulls = int(dataset.isna().sum().sum())
        dataset = applied["dataframe"]
        after_rows = len(dataset)
        after_nulls = int(dataset.isna().sum().sum())
        applied_table_ids.add(applied["joined_table_id"])
        applied_relationships.append(
            {
                "relationship_id": relationship["relationship_id"],
                "applied": True,
                "left_table": applied["left_table_name"],
                "right_table": applied["right_table_name"],
                "left_field": applied["left_field"],
                "right_field": applied["right_field"],
                "rows_before": before_rows,
                "rows_after": after_rows,
                "row_expansion": round(after_rows / before_rows, 4) if before_rows else 0,
                "nulls_before": before_nulls,
                "nulls_after": after_nulls,
            }
        )
        source_tables.append(_table_source_summary(table_frames[applied["joined_table_id"]]))
        if before_rows and after_rows / before_rows > 2:
            health_checks.append(
                {
                    "check": "重复扩张",
                    "risk_level": "高",
                    "detail": f"{applied['left_table_name']} JOIN {applied['right_table_name']} 后行数扩张超过 2 倍。",
                }
            )
        elif before_rows and after_rows / before_rows > 1.2:
            health_checks.append(
                {
                    "check": "重复扩张",
                    "risk_level": "中",
                    "detail": f"{applied['left_table_name']} JOIN {applied['right_table_name']} 后行数存在明显扩张。",
                }
            )
        if after_nulls > before_nulls * 1.5 and after_nulls - before_nulls > max(10, len(dataset) * 0.1):
            health_checks.append(
                {
                    "check": "空值率激增",
                    "risk_level": "中",
                    "detail": f"{applied['right_table_name']} 字段合并后空值数量明显增加，请检查匹配率。",
                }
            )

    analysis_path = _analysis_path(project_id)
    analysis_path.mkdir(parents=True, exist_ok=True)
    dataset_path = analysis_path / ANALYSIS_DATASET_FILE
    dataset.to_csv(dataset_path, index=False, encoding="utf-8-sig")
    metadata = {
        "dataset_name": ANALYSIS_DATASET_NAME,
        "file_name": ANALYSIS_DATASET_FILE,
        "file_path": f"{ANALYSIS_DIR}/{ANALYSIS_DATASET_FILE}",
        "rows": int(len(dataset)),
        "columns": int(len(dataset.columns)),
        "source_tables": _unique_source_tables(source_tables),
        "join_count": len([item for item in applied_relationships if item.get("applied")]),
        "join_plan": join_plan,
        "applied_relationships": applied_relationships,
        "health_checks": _deduplicate_health_checks(health_checks),
        "field_count": {
            "field_mappings": len(_safe_load(load_field_mappings, project_id)),
            "kpi_definitions": len(_safe_load(load_kpi_definitions, project_id)),
            "metric_dictionary": len(_safe_load(load_metric_dictionary, project_id)),
            "relationships": len(relationships),
        },
        "file_size": dataset_path.stat().st_size,
        "created_at": _utc_now(),
    }
    metadata_path = analysis_path / ANALYSIS_METADATA_FILE
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    project_workspace.update_project(project_id, {"analysis_dataset": metadata})
    set_current_analysis_dataset(
        project_id,
        {
            "dataset_id": ANALYSIS_DATASET_NAME,
            "dataset_name": ANALYSIS_DATASET_FILE,
            "dataset_type": "joined",
            "file_path": metadata["file_path"],
            "sheet_name": None,
            "source": "join",
            "created_at": metadata["created_at"],
            "row_count": metadata["rows"],
            "column_count": metadata["columns"],
        },
    )
    return metadata


def load_analysis_dataset(project_id: str) -> pd.DataFrame:
    dataset_path = _analysis_path(project_id) / ANALYSIS_DATASET_FILE
    if not dataset_path.is_file():
        raise FileNotFoundError("当前项目还没有生成 analysis_dataset.csv。")
    return pd.read_csv(dataset_path)


def preview_analysis_dataset(project_id: str) -> dict[str, Any]:
    metadata = get_dataset_metadata(project_id)
    dataframe = load_analysis_dataset(project_id)
    return {
        "metadata": metadata,
        "preview": dataframe.head(20),
        "fields": [
            {
                "字段名": str(column),
                "字段类型": str(dataframe[column].dtype),
                "缺失值数量": int(dataframe[column].isna().sum()),
                "唯一值数量": int(dataframe[column].nunique(dropna=True)),
            }
            for column in dataframe.columns
        ],
    }


def get_dataset_metadata(project_id: str) -> dict[str, Any] | None:
    metadata_path = _analysis_path(project_id) / ANALYSIS_METADATA_FILE
    if metadata_path.is_file():
        try:
            return json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("分析数据集元数据损坏：analysis/analysis_dataset_meta.json") from exc
    project = project_workspace.get_project(project_id)
    metadata = project.get("analysis_dataset")
    return metadata if isinstance(metadata, dict) else None


def _apply_relationship_join(
    dataset: pd.DataFrame,
    relationship: dict[str, Any],
    table_frames: dict[str, dict[str, Any]],
    applied_table_ids: set[str],
) -> dict[str, Any]:
    table_a = table_frames.get(relationship["table_a_id"])
    table_b = table_frames.get(relationship["table_b_id"])
    if not table_a or not table_b:
        return {"applied": False, "reason": "关系中的数据表不存在或无法读取。"}

    field_a = relationship["field_a"]
    field_b = relationship["field_b"]
    if field_a in dataset.columns and relationship["table_b_id"] not in applied_table_ids:
        return _merge_dataset(
            dataset,
            table_b,
            left_field=field_a,
            right_field=field_b,
            relationship=relationship,
        )
    if field_b in dataset.columns and relationship["table_a_id"] not in applied_table_ids:
        return _merge_dataset(
            dataset,
            table_a,
            left_field=field_b,
            right_field=field_a,
            relationship=relationship,
        )
    if relationship["table_a_id"] in applied_table_ids and relationship["table_b_id"] in applied_table_ids:
        return {"applied": False, "reason": "关系两侧表已经在分析数据集中，避免重复 JOIN。"}
    return {
        "applied": False,
        "reason": f"当前数据集中未找到连接字段：{field_a} 或 {field_b}。",
    }


def _merge_dataset(
    dataset: pd.DataFrame,
    right_table: dict[str, Any],
    left_field: str,
    right_field: str,
    relationship: dict[str, Any],
) -> dict[str, Any]:
    right_df = right_table["dataframe"].copy()
    if left_field not in dataset.columns:
        return {"applied": False, "reason": f"左侧连接字段不存在：{left_field}"}
    if right_field not in right_df.columns:
        return {"applied": False, "reason": f"右侧连接字段不存在：{right_field}"}
    suffix = f"__{_safe_suffix(right_table['table_name'])}"
    merged = dataset.merge(
        right_df,
        how="left",
        left_on=left_field,
        right_on=right_field,
        suffixes=("", suffix),
    )
    return {
        "applied": True,
        "dataframe": merged,
        "joined_table_id": right_table["table_id"],
        "left_table_name": relationship.get("table_a_name", "分析数据集"),
        "right_table_name": right_table["table_name"],
        "left_field": left_field,
        "right_field": right_field,
    }


def _build_join_plan_item(
    relationship: dict[str, Any],
    dataframe_a: pd.DataFrame,
    dataframe_b: pd.DataFrame,
) -> dict[str, Any]:
    field_a = relationship["field_a"]
    field_b = relationship["field_b"]
    stats = _relationship_stats(dataframe_a, field_a, dataframe_b, field_b)
    risk = _assess_join_risk(relationship, stats)
    return {
        "relationship_id": relationship["relationship_id"],
        "表A": relationship.get("table_a_name", relationship["table_a_id"]),
        "字段A": field_a,
        "JOIN": "LEFT JOIN",
        "表B": relationship.get("table_b_name", relationship["table_b_id"]),
        "字段B": field_b,
        "关系类型": relationship.get("relationship_type", "many_to_one"),
        "预计匹配率": round(stats["match_rate"] * 100, 2),
        "预计扩张倍数": round(stats["expansion_factor"], 2),
        "风险": risk["risk_level"],
        "风险说明": risk["detail"],
        "left_unique_ratio": round(stats["left_unique_ratio"], 4),
        "right_unique_ratio": round(stats["right_unique_ratio"], 4),
        "left_rows": stats["left_rows"],
        "right_rows": stats["right_rows"],
    }


def _relationship_stats(
    dataframe_a: pd.DataFrame,
    field_a: str,
    dataframe_b: pd.DataFrame,
    field_b: str,
) -> dict[str, Any]:
    if field_a not in dataframe_a.columns or field_b not in dataframe_b.columns:
        return {
            "left_rows": len(dataframe_a),
            "right_rows": len(dataframe_b),
            "match_rate": 0.0,
            "expansion_factor": 0.0,
            "left_unique_ratio": 0.0,
            "right_unique_ratio": 0.0,
            "missing_field": True,
        }

    left = dataframe_a[field_a]
    right = dataframe_b[field_b]
    left_non_null = left.dropna()
    right_non_null = right.dropna()
    right_counts = right_non_null.value_counts(dropna=True)
    match_counts = left_non_null.map(right_counts).fillna(0)
    matched_rows = int((match_counts > 0).sum())
    joined_rows_estimate = float(match_counts.clip(lower=1).sum() + left.isna().sum())
    return {
        "left_rows": len(dataframe_a),
        "right_rows": len(dataframe_b),
        "match_rate": matched_rows / len(left_non_null) if len(left_non_null) else 0.0,
        "expansion_factor": joined_rows_estimate / len(dataframe_a) if len(dataframe_a) else 0.0,
        "left_unique_ratio": left_non_null.nunique(dropna=True) / len(left_non_null) if len(left_non_null) else 0.0,
        "right_unique_ratio": right_non_null.nunique(dropna=True) / len(right_non_null) if len(right_non_null) else 0.0,
        "missing_field": False,
    }


def _assess_join_risk(
    relationship: dict[str, Any],
    stats: dict[str, Any],
) -> dict[str, str]:
    reasons = []
    risk_level = "低"
    if stats.get("missing_field"):
        return {"risk_level": "高", "detail": "连接字段不存在，无法执行 JOIN。"}
    relationship_type = relationship.get("relationship_type", "many_to_one")
    if relationship_type == "many_to_many":
        risk_level = "高"
        reasons.append("关系类型为 Many-To-Many，容易造成重复扩张")
    if stats["expansion_factor"] > 2:
        risk_level = "高"
        reasons.append("预计扩张倍数超过 2.00x")
    elif stats["expansion_factor"] > 1.2 and risk_level != "高":
        risk_level = "中"
        reasons.append("预计存在明显行数扩张")
    if stats["match_rate"] < 0.6:
        risk_level = "高"
        reasons.append("预计匹配率低于 60%")
    elif stats["match_rate"] < 0.85 and risk_level != "高":
        risk_level = "中"
        reasons.append("预计匹配率低于 85%")
    if relationship_type == "many_to_one" and stats["right_unique_ratio"] < 0.98:
        if risk_level != "高":
            risk_level = "中"
        reasons.append("目标表连接字段并非唯一，可能造成扩张")
    if not reasons:
        reasons.append("匹配率和扩张倍数处于可控范围")
    return {"risk_level": risk_level, "detail": "；".join(reasons)}


def _health_checks_from_plan(join_plan: list[dict[str, Any]]) -> list[dict[str, str]]:
    checks = []
    for item in join_plan:
        if item["关系类型"] == "many_to_many":
            checks.append(
                {
                    "check": "Many-To-Many",
                    "risk_level": "高",
                    "detail": f"{item['表A']} 与 {item['表B']} 为 Many-To-Many，需谨慎生成分析数据集。",
                }
            )
        if item["预计匹配率"] < 60:
            checks.append(
                {
                    "check": "匹配率过低",
                    "risk_level": "高",
                    "detail": f"{item['表A']} ↔ {item['表B']} 预计匹配率为 {item['预计匹配率']}%。",
                }
            )
        elif item["预计匹配率"] < 85:
            checks.append(
                {
                    "check": "匹配率偏低",
                    "risk_level": "中",
                    "detail": f"{item['表A']} ↔ {item['表B']} 预计匹配率为 {item['预计匹配率']}%。",
                }
            )
        if item["预计扩张倍数"] > 2:
            checks.append(
                {
                    "check": "重复扩张",
                    "risk_level": "高",
                    "detail": f"{item['表A']} LEFT JOIN {item['表B']} 预计扩张 {item['预计扩张倍数']}x。",
                }
            )
        elif item["预计扩张倍数"] > 1.2:
            checks.append(
                {
                    "check": "重复扩张",
                    "risk_level": "中",
                    "detail": f"{item['表A']} LEFT JOIN {item['表B']} 预计扩张 {item['预计扩张倍数']}x。",
                }
            )
    if not checks:
        checks.append(
            {
                "check": "JOIN健康检查",
                "risk_level": "低",
                "detail": "未发现明显 Many-To-Many、重复扩张或低匹配率风险。",
            }
        )
    return checks


def _load_project_table_frames(project_id: str) -> dict[str, dict[str, Any]]:
    tables = {}
    for table in list_project_tables(project_id):
        try:
            dataframe = load_project_data_file(
                project_id,
                table["file_id"],
                table["sheet_name"],
            )
        except Exception:
            continue
        tables[table["table_id"]] = {**table, "dataframe": dataframe}
    return tables


def _select_base_table_id(
    project_id: str,
    relationships: list[dict[str, Any]],
    table_frames: dict[str, dict[str, Any]],
) -> str:
    current = get_current_analysis_dataset(project_id) or {}
    if current.get("dataset_type") == "uploaded" and current.get("dataset_id"):
        current_table_id = current["dataset_id"]
        if current_table_id in table_frames:
            return current_table_id
    for relationship in relationships:
        if relationship["table_a_id"] in table_frames:
            return relationship["table_a_id"]
    return next(iter(table_frames))


def _build_current_base_table(
    project_id: str,
    table_frames: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    current = get_current_analysis_dataset(project_id) or {}
    current_table_id = current.get("dataset_id")
    if current.get("dataset_type") == "uploaded" and current_table_id in table_frames:
        return table_frames[current_table_id]
    if current.get("file_path"):
        dataframe = load_current_analysis_dataframe(project_id)
        return {
            "table_id": current.get("dataset_id", "current_analysis_dataset"),
            "table_name": current.get("dataset_name", "current_analysis_dataset"),
            "file_id": current.get("source_file_id") or current.get("dataset_id", "current_analysis_dataset"),
            "file_name": current.get("dataset_name", "current_analysis_dataset"),
            "sheet_name": current.get("sheet_name"),
            "dataframe": dataframe,
        }
    return table_frames[next(iter(table_frames))]


def _missing_table_plan(relationship: dict[str, Any]) -> dict[str, Any]:
    return {
        "relationship_id": relationship.get("relationship_id", ""),
        "表A": relationship.get("table_a_name", relationship.get("table_a_id", "")),
        "字段A": relationship.get("field_a", ""),
        "JOIN": "LEFT JOIN",
        "表B": relationship.get("table_b_name", relationship.get("table_b_id", "")),
        "字段B": relationship.get("field_b", ""),
        "关系类型": relationship.get("relationship_type", "many_to_one"),
        "预计匹配率": 0.0,
        "预计扩张倍数": 0.0,
        "风险": "高",
        "风险说明": "关系中的数据表不存在或无法读取。",
        "left_unique_ratio": 0.0,
        "right_unique_ratio": 0.0,
        "left_rows": 0,
        "right_rows": 0,
    }


def _table_source_summary(table: dict[str, Any]) -> dict[str, Any]:
    return {
        "table_id": table["table_id"],
        "table_name": table["table_name"],
        "file_id": table["file_id"],
        "file_name": table["file_name"],
        "sheet_name": table["sheet_name"],
        "rows": int(len(table["dataframe"])),
        "columns": int(len(table["dataframe"].columns)),
    }


def _unique_source_tables(source_tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique = {}
    for table in source_tables:
        unique[table["table_id"]] = table
    return list(unique.values())


def _deduplicate_health_checks(checks: list[dict[str, str]]) -> list[dict[str, str]]:
    unique = {}
    for item in checks:
        unique[(item.get("check", ""), item.get("detail", ""))] = item
    return list(unique.values())


def _safe_load(loader, project_id: str) -> list[Any]:
    try:
        value = loader(project_id)
    except Exception:
        return []
    return value if isinstance(value, list) else []


def _analysis_path(project_id: str) -> Path:
    return project_workspace.get_project_path(project_id) / ANALYSIS_DIR


def _safe_suffix(value: str) -> str:
    suffix = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "_", str(value)).strip("_")
    return suffix or "right"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
