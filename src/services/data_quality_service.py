from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src import data_quality as legacy_data_quality
from src import project_workspace
from src.outlier import calculate_iqr_bounds
from src.services.current_dataset_service import (
    get_current_analysis_dataset,
    load_current_analysis_dataframe,
    register_project_dataset,
    set_current_analysis_dataset,
)


ANALYSIS_DIR = "analysis"
CLEANED_DATASET_ID = "cleaned_dataset"
CLEANED_DATASET_FILE = "cleaned_dataset.csv"
CLEANED_METADATA_FILE = "cleaned_dataset_meta.json"

IDENTIFIER_NAME_HINTS = (
    "id",
    "编号",
    "编码",
    "工号",
    "订单号",
    "单号",
    "流水号",
    "客户号",
    "用户号",
    "销售工号",
    "customer_id",
    "user_id",
    "employee_id",
    "order_id",
)

MEASURE_NAME_HINTS = (
    "销售额",
    "数量",
    "金额",
    "单价",
    "成本",
    "利润",
    "折扣",
    "收入",
    "价格",
    "amount",
    "price",
    "quantity",
    "revenue",
    "cost",
    "profit",
)

IQR_IDENTIFIER_NAME_HINTS = (
    "id",
    "工号",
    "编号",
    "编码",
    "代码",
    "单号",
    "订单号",
    "客户号",
    "用户id",
    "手机号",
    "phone",
    "mobile",
    "tel",
)


def detect_invalid_columns(df: pd.DataFrame, missing_threshold: float = 0.95) -> list[str]:
    invalid_columns = []
    for column in df.columns:
        normalized = str(column).strip().lower()
        if normalized.startswith("unnamed:") or df[column].isna().mean() >= missing_threshold:
            invalid_columns.append(column)
    return invalid_columns


def suspicious_columns(df: pd.DataFrame, missing_threshold: float = 0.95) -> list[str]:
    return detect_invalid_columns(df, missing_threshold)


def calculate_quality_score(
    df: pd.DataFrame,
    invalid_columns: list[str],
    numeric_columns: list[str],
) -> int:
    return legacy_data_quality.calculate_quality_score(df, invalid_columns, numeric_columns)


def data_quality_summary(
    df: pd.DataFrame,
    invalid_columns: list[str],
    identifier_columns: list[str],
    numeric_columns: list[str],
) -> dict:
    return legacy_data_quality.data_quality_summary(
        df,
        invalid_columns,
        identifier_columns,
        numeric_columns,
    )


def generate_data_repair_suggestions(
    df: pd.DataFrame,
    invalid_columns: list[str],
    identifier_columns: list[str],
    outlier_summary: pd.DataFrame,
) -> pd.DataFrame:
    return legacy_data_quality.generate_data_repair_suggestions(
        df,
        invalid_columns,
        identifier_columns,
        outlier_summary,
    )


def quality_stars(score: int) -> str:
    return legacy_data_quality.quality_stars(score)


def _looks_like_date_column(series: pd.Series, column: str | None = None) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if pd.api.types.is_numeric_dtype(series):
        return False
    normalized = str(column or "").strip().lower()
    if not any(hint in normalized for hint in ("date", "time", "日期", "时间")):
        return False
    non_null = series.dropna()
    if non_null.empty:
        return False
    parsed = pd.to_datetime(non_null, errors="coerce", format="mixed")
    return bool(parsed.notna().mean() >= 0.8)


def _is_measure_name(column: str) -> bool:
    normalized = str(column).strip().lower()
    return any(hint in normalized for hint in MEASURE_NAME_HINTS)


def identifier_reason(df: pd.DataFrame, column: str) -> str | None:
    if column not in df.columns:
        return None
    series = df[column]
    if _looks_like_date_column(series, column):
        return None

    non_null_count = int(series.notna().sum())
    if non_null_count == 0:
        return None

    normalized = str(column).strip().lower()
    if any(hint in normalized for hint in IDENTIFIER_NAME_HINTS):
        return "字段名包含 ID、编号、工号、订单号、流水号、客户号或用户号等标识词"

    unique_ratio = series.nunique(dropna=True) / max(non_null_count, 1)
    if unique_ratio > 0.9 and not _is_measure_name(column):
        return "唯一值占比超过 90%，疑似记录标识字段"
    return None


def detect_identifier_columns(
    df: pd.DataFrame,
    excluded_columns: list[str] | None = None,
) -> list[str]:
    excluded = set(excluded_columns or [])
    return [
        column
        for column in df.columns
        if column not in excluded and identifier_reason(df, column) is not None
    ]


def summarize_identifier_columns(df: pd.DataFrame, identifier_columns: list[str]) -> pd.DataFrame:
    rows = []
    for column in identifier_columns:
        if column not in df.columns:
            continue
        non_null_count = int(df[column].notna().sum())
        unique_count = int(df[column].nunique(dropna=True))
        rows.append(
            {
                "字段名": column,
                "数据类型": str(df[column].dtype),
                "唯一值数量": unique_count,
                "唯一值比例": round(unique_count / max(non_null_count, 1) * 100, 2),
                "识别原因": identifier_reason(df, column),
            }
        )
    return pd.DataFrame(rows)


def missing_value_recommendation(series: pd.Series) -> str:
    missing_ratio = series.isna().mean()
    if missing_ratio >= 0.8:
        return "删除字段或重新获取数据源"
    if missing_ratio >= 0.3:
        return "谨慎填充，建议结合业务判断"
    if missing_ratio > 0:
        if _looks_like_date_column(series, series.name):
            return "不建议随意填充"
        if pd.api.types.is_numeric_dtype(series):
            return "均值 / 中位数填充"
        return "众数填充"
    return "无需处理"


def is_iqr_measure_column(column: str) -> bool:
    """Return whether a column name looks like a measure suitable for IQR analysis."""
    normalized = str(column).strip().lower()
    return not any(hint in normalized for hint in IQR_IDENTIFIER_NAME_HINTS)


def get_iqr_numeric_measure_columns(
    df: pd.DataFrame,
    identifier_columns: list[str] | None = None,
) -> list[str]:
    identifiers = set(identifier_columns or detect_identifier_columns(df))
    return [
        column
        for column in df.columns
        if pd.api.types.is_numeric_dtype(df[column])
        and column not in identifiers
        and is_iqr_measure_column(column)
    ]


def summarize_missing_values_for_quality(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column in df.columns:
        missing_count = int(df[column].isna().sum())
        rows.append(
            {
                "字段名": column,
                "数据类型": str(df[column].dtype),
                "缺失值数量": missing_count,
                "缺失值比例": round(missing_count / max(len(df), 1) * 100, 2),
                "推荐处理方式": missing_value_recommendation(df[column]),
            }
        )
    return pd.DataFrame(rows).sort_values("缺失值比例", ascending=False, ignore_index=True)


def missing_sample_preview(df: pd.DataFrame, limit: int = 20) -> pd.DataFrame:
    mask = df.isna().any(axis=1)
    preview = df.loc[mask].head(limit).copy()
    if preview.empty:
        return preview
    preview.insert(0, "原始行索引", preview.index)
    return preview.reset_index(drop=True)


def summarize_duplicates_for_quality(df: pd.DataFrame) -> dict[str, Any]:
    duplicate_mask = df.duplicated(keep=False)
    duplicate_count = int(df.duplicated().sum())
    return {
        "duplicate_count": duplicate_count,
        "duplicate_ratio": round(duplicate_count / max(len(df), 1) * 100, 2),
        "preview": df.loc[duplicate_mask].head(50).copy(),
    }


def summarize_iqr_outliers_for_quality(
    df: pd.DataFrame,
    identifier_columns: list[str] | None = None,
) -> pd.DataFrame:
    rows = []
    numeric_columns = get_iqr_numeric_measure_columns(df, identifier_columns)
    for column in numeric_columns:
        bounds = calculate_iqr_bounds(df, column)
        series = pd.to_numeric(df[column], errors="coerce")
        if pd.isna(bounds["lower_bound"]) or pd.isna(bounds["upper_bound"]):
            outlier_mask = pd.Series(False, index=df.index)
        else:
            outlier_mask = (series < bounds["lower_bound"]) | (series > bounds["upper_bound"])
        valid_count = int(series.notna().sum())
        outlier_count = int(outlier_mask.sum())
        rows.append(
            {
                "字段名": column,
                "Q1": bounds["q1"],
                "Q3": bounds["q3"],
                "IQR": bounds["iqr"],
                "下界": bounds["lower_bound"],
                "上界": bounds["upper_bound"],
                "异常值数量": outlier_count,
                "异常值比例": round(outlier_count / max(valid_count, 1) * 100, 2),
            }
        )
    return pd.DataFrame(rows)


def summarize_quality_overview(
    df: pd.DataFrame,
    identifier_columns: list[str] | None = None,
    invalid_columns: list[str] | None = None,
    outlier_summary: pd.DataFrame | None = None,
) -> dict[str, Any]:
    identifiers = identifier_columns if identifier_columns is not None else detect_identifier_columns(df)
    invalid = invalid_columns if invalid_columns is not None else detect_invalid_columns(df)
    outliers = outlier_summary
    if outliers is None:
        outliers = summarize_iqr_outliers_for_quality(df, identifiers)
    missing_total = int(df.isna().sum().sum())
    duplicate_count = int(df.duplicated().sum())
    outlier_count = int(outliers["异常值数量"].sum()) if not outliers.empty else 0
    cell_count = max(df.shape[0] * df.shape[1], 1)
    numeric_columns = get_iqr_numeric_measure_columns(df, identifiers)
    numeric_value_count = (
        max(int(df[numeric_columns].notna().sum().sum()), 1)
        if numeric_columns
        else 1
    )
    deductions = (
        min(30, round(missing_total / cell_count * 100))
        + min(20, round(duplicate_count / max(len(df), 1) * 100))
        + min(15, len(identifiers) * 3)
        + min(20, len(invalid) * 5)
        + min(15, round(outlier_count / numeric_value_count * 100))
    )
    return {
        "score": max(0, 100 - deductions),
        "missing_values": missing_total,
        "duplicate_rows": duplicate_count,
        "identifier_column_count": len(identifiers),
        "suspicious_column_count": len(invalid),
        "outlier_count": outlier_count,
    }


def generate_data_repair_suggestions_for_quality(
    df: pd.DataFrame,
    identifier_columns: list[str],
    invalid_columns: list[str],
    outlier_summary: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    high_missing_columns = [column for column in df.columns if df[column].isna().mean() >= 0.8]
    for column in high_missing_columns:
        rows.append(
            {
                "问题类型": "缺失率过高",
                "涉及字段": column,
                "严重程度": "高",
                "影响": "字段信息严重不足，可能无法支持可靠分析",
                "推荐操作": "删除字段或重新获取数据源",
                "建议处理位置": "缺失值",
                "操作建议": "在缺失值处理中选择高缺失字段阈值后生成清洗数据集",
            }
        )
    if df.duplicated().any():
        rows.append(
            {
                "问题类型": "重复行",
                "涉及字段": "整行",
                "严重程度": "中",
                "影响": "可能导致金额、数量、客户数等指标重复计算",
                "推荐操作": "确认业务含义后删除完全重复行",
                "建议处理位置": "重复值",
                "操作建议": "在重复值处理中选择删除完全重复行",
            }
        )
    for column in identifier_columns:
        rows.append(
            {
                "问题类型": "疑似 ID 字段",
                "涉及字段": column,
                "严重程度": "低",
                "影响": "不适合做均值、异常值检测和相关性分析",
                "推荐操作": "保留为记录定位字段，并从统计分析中排除",
                "建议处理位置": "ID识别",
                "操作建议": "无需删除；系统已从 IQR 异常值检测中排除",
            }
        )
    if "异常值数量" in outlier_summary.columns:
        for _, row in outlier_summary.loc[outlier_summary["异常值数量"] > 0].iterrows():
            rows.append(
                {
                    "问题类型": "检测到异常值",
                    "涉及字段": row["字段名"],
                    "严重程度": "中",
                    "影响": "可能拉高或拉低整体统计结果",
                    "推荐操作": "先查看异常值样例，再决定保留、截尾、标记或删除",
                    "建议处理位置": "异常值",
                    "操作建议": "在异常值处理中选择对应方式后生成清洗数据集",
                }
            )
    for column in invalid_columns:
        rows.append(
            {
                "问题类型": "疑似无效字段",
                "涉及字段": column,
                "严重程度": "高",
                "影响": "可能增加数据噪声并干扰分析",
                "推荐操作": "确认业务含义后删除字段或重新获取数据源",
                "建议处理位置": "缺失值",
                "操作建议": "如缺失率过高，可在缺失值处理中按阈值删除",
            }
        )
    return pd.DataFrame(rows)


def upsert_missing_value_plan_item(
    plan: list[dict[str, Any]] | None,
    item: dict[str, Any],
) -> list[dict[str, Any]]:
    column = item.get("column")
    if not column:
        return list(plan or [])
    normalized = {
        "column": column,
        "method": item.get("method", "none"),
        "fill_value": item.get("fill_value", ""),
    }
    return [
        *(step for step in (plan or []) if step.get("column") != column),
        normalized,
    ]


def remove_missing_value_plan_item(
    plan: list[dict[str, Any]] | None,
    column: str,
) -> list[dict[str, Any]]:
    return [step for step in (plan or []) if step.get("column") != column]


def missing_value_plan_to_operations(plan: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    operations = []
    for step in plan or []:
        column = step.get("column")
        method = step.get("method")
        if not column or method in {None, "none"}:
            continue
        if method == "drop_column":
            operations.append({"type": "drop_columns", "columns": [column]})
        elif method == "drop_rows":
            operations.append({"type": "drop_missing_rows", "columns": [column]})
        elif method in {"zero", "mean", "median", "mode", "unknown", "custom"}:
            operations.append(
                {
                    "type": "fill_missing",
                    "column": column,
                    "method": method,
                    "custom_value": step.get("fill_value", ""),
                }
            )
    return operations


def apply_missing_value_plan_preview(
    df: pd.DataFrame,
    plan: list[dict[str, Any]] | None,
) -> pd.DataFrame:
    result, _ = apply_quality_operations(df.copy(), missing_value_plan_to_operations(plan))
    return result


def summarize_missing_value_plan_effect(
    df: pd.DataFrame,
    plan: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    preview = apply_missing_value_plan_preview(df, plan)
    return {
        "before_missing_values": int(df.isna().sum().sum()),
        "after_missing_values": int(preview.isna().sum().sum()),
        "before_rows": int(len(df)),
        "after_rows": int(len(preview)),
        "before_columns": int(len(df.columns)),
        "after_columns": int(len(preview.columns)),
    }


def format_missing_value_plan(
    plan: list[dict[str, Any]] | None,
    df: pd.DataFrame,
) -> pd.DataFrame:
    method_labels = {
        "drop_column": "删除字段",
        "drop_rows": "删除含缺失值的行",
        "zero": "填 0",
        "mean": "均值填充",
        "median": "中位数填充",
        "mode": "众数填充",
        "unknown": "填“未知”",
        "custom": "固定值填充",
        "none": "不处理",
    }
    rows = []
    for step in plan or []:
        column = step.get("column", "")
        method = step.get("method", "none")
        if column in df.columns:
            missing_count = int(df[column].isna().sum())
        else:
            missing_count = 0
        if method == "drop_column":
            impact = "预计减少 1 个字段"
        elif method == "drop_rows":
            impact = f"预计删除 {missing_count:,} 行含该字段缺失值的记录"
        elif method in {"zero", "mean", "median", "mode", "unknown", "custom"}:
            impact = f"预计填充 {missing_count:,} 个缺失值"
        else:
            impact = "不会改变数据"
        rows.append(
            {
                "字段": column,
                "处理方式": method_labels.get(method, str(method)),
                "预计影响": impact,
                "状态": "待执行",
            }
        )
    return pd.DataFrame(rows)


def apply_quality_operations(
    df: pd.DataFrame,
    operations: list[dict[str, Any]],
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    result = df.copy()
    applied_steps = []
    for operation in operations:
        op_type = operation.get("type")
        before_shape = result.shape

        if op_type == "drop_missing_rows":
            columns = operation.get("columns")
            column = operation.get("column")
            subset = columns or ([column] if column else None)
            result = result.dropna(subset=subset).reset_index(drop=True)
        elif op_type == "drop_columns":
            columns = [
                column
                for column in operation.get("columns", [])
                if column in result.columns
            ]
            result = result.drop(columns=columns)
            operation = {**operation, "dropped_columns": columns}
        elif op_type == "drop_high_missing_columns":
            threshold = float(operation.get("threshold", 0.8))
            columns = [
                column
                for column in result.columns
                if result[column].isna().mean() >= threshold
            ]
            result = result.drop(columns=columns)
            operation = {**operation, "dropped_columns": columns}
        elif op_type == "fill_missing":
            column = operation.get("column")
            method = operation.get("method")
            custom_value = operation.get("custom_value", "")
            result = _fill_missing(result, column, method, custom_value)
        elif op_type == "drop_duplicates":
            result = result.drop_duplicates().reset_index(drop=True)
        elif op_type == "outlier":
            column = operation.get("column")
            method = operation.get("method")
            result = _apply_outlier_operation(result, column, method)
        elif op_type in {None, "none"}:
            continue
        else:
            raise ValueError(f"不支持的数据质量处理操作：{op_type}")

        applied_steps.append(
            {
                **operation,
                "before_rows": before_shape[0],
                "before_columns": before_shape[1],
                "after_rows": result.shape[0],
                "after_columns": result.shape[1],
            }
        )
    return result, applied_steps


def create_cleaned_dataset(
    project_id: str,
    operations: list[dict[str, Any]],
) -> dict[str, Any]:
    source_dataset = get_current_analysis_dataset(project_id)
    if not source_dataset:
        raise FileNotFoundError("尚未设置当前分析数据集，无法生成清洗数据集。")
    before_df = load_current_analysis_dataframe(project_id)
    cleaned_df, applied_steps = apply_quality_operations(before_df, operations)

    analysis_path = _analysis_path(project_id)
    analysis_path.mkdir(parents=True, exist_ok=True)
    dataset_path = analysis_path / CLEANED_DATASET_FILE
    cleaned_df.to_csv(dataset_path, index=False, encoding="utf-8-sig")

    metadata = {
        "dataset_id": CLEANED_DATASET_ID,
        "dataset_name": CLEANED_DATASET_FILE,
        "dataset_type": "cleaned",
        "file_path": f"{ANALYSIS_DIR}/{CLEANED_DATASET_FILE}",
        "metadata_path": f"{ANALYSIS_DIR}/{CLEANED_METADATA_FILE}",
        "source": "quality_cleaning",
        "source_dataset": source_dataset,
        "source_dataset_id": source_dataset.get("dataset_id"),
        "source_dataset_name": source_dataset.get("dataset_name"),
        "processing_steps": applied_steps,
        "missing_value_actions": [
            step
            for step in applied_steps
            if step.get("type") in {"drop_missing_rows", "drop_high_missing_columns", "drop_columns", "fill_missing"}
        ],
        "duplicate_actions": [
            step for step in applied_steps if step.get("type") == "drop_duplicates"
        ],
        "outlier_actions": [
            step for step in applied_steps if step.get("type") == "outlier"
        ],
        "before_rows": int(len(before_df)),
        "after_rows": int(len(cleaned_df)),
        "before_columns": int(len(before_df.columns)),
        "after_columns": int(len(cleaned_df.columns)),
        "created_at": _utc_now(),
        "file_size": dataset_path.stat().st_size,
    }
    metadata_path = analysis_path / CLEANED_METADATA_FILE
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    project_workspace.update_project(project_id, {"cleaned_dataset": metadata})
    register_project_dataset(
        project_id,
        {
            "dataset_id": CLEANED_DATASET_ID,
            "dataset_name": CLEANED_DATASET_FILE,
            "dataset_type": "cleaned",
            "file_path": metadata["file_path"],
            "sheet_name": None,
            "source": "quality_cleaning",
            "created_at": metadata["created_at"],
            "row_count": metadata["after_rows"],
            "column_count": metadata["after_columns"],
            "source_files": [source_dataset],
        },
    )
    return metadata


def get_cleaned_dataset_metadata(project_id: str) -> dict[str, Any] | None:
    metadata_path = _analysis_path(project_id) / CLEANED_METADATA_FILE
    if metadata_path.is_file():
        try:
            return json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("清洗数据集元数据损坏：analysis/cleaned_dataset_meta.json") from exc
    project = project_workspace.get_project(project_id)
    metadata = project.get("cleaned_dataset")
    return metadata if isinstance(metadata, dict) else None


def load_cleaned_dataset(project_id: str) -> pd.DataFrame:
    dataset_path = _analysis_path(project_id) / CLEANED_DATASET_FILE
    if not dataset_path.is_file():
        raise FileNotFoundError("当前项目还没有生成 cleaned_dataset.csv。")
    return pd.read_csv(dataset_path)


def set_cleaned_dataset_as_current(project_id: str) -> dict[str, Any]:
    metadata = get_cleaned_dataset_metadata(project_id)
    if not metadata:
        raise FileNotFoundError("当前项目还没有生成 cleaned_dataset.csv。")
    return set_current_analysis_dataset(
        project_id,
        {
            "dataset_id": CLEANED_DATASET_ID,
            "dataset_name": CLEANED_DATASET_FILE,
            "dataset_type": "cleaned",
            "file_path": metadata["file_path"],
            "sheet_name": None,
            "source": "quality_cleaning",
            "created_at": metadata.get("created_at", ""),
            "row_count": metadata.get("after_rows"),
            "column_count": metadata.get("after_columns"),
            "source_files": [metadata.get("source_dataset", {})],
        },
    )


def _fill_missing(
    df: pd.DataFrame,
    column: str,
    method: str,
    custom_value: Any = "",
) -> pd.DataFrame:
    if column not in df.columns:
        raise KeyError(f"字段不存在：{column}")
    result = df.copy()
    if method == "zero":
        if not pd.api.types.is_numeric_dtype(result[column]):
            raise ValueError("填 0 仅适用于数值字段。")
        result[column] = result[column].fillna(0)
    elif method == "mean":
        if not pd.api.types.is_numeric_dtype(result[column]):
            raise ValueError("均值填充仅适用于数值字段。")
        result[column] = result[column].fillna(result[column].mean())
    elif method == "median":
        if not pd.api.types.is_numeric_dtype(result[column]):
            raise ValueError("中位数填充仅适用于数值字段。")
        result[column] = result[column].fillna(result[column].median())
    elif method == "mode":
        mode = result[column].mode(dropna=True)
        if not mode.empty:
            result[column] = result[column].fillna(mode.iloc[0])
    elif method == "unknown":
        result[column] = result[column].fillna("未知")
    elif method == "custom":
        result[column] = result[column].fillna(custom_value)
    else:
        raise ValueError(f"不支持的缺失值填充方式：{method}")
    return result


def _apply_outlier_operation(
    df: pd.DataFrame,
    column: str,
    method: str,
) -> pd.DataFrame:
    if column not in df.columns:
        raise KeyError(f"字段不存在：{column}")
    result = df.copy()
    bounds = calculate_iqr_bounds(result, column)
    series = pd.to_numeric(result[column], errors="coerce")
    if pd.isna(bounds["lower_bound"]) or pd.isna(bounds["upper_bound"]):
        mask = pd.Series(False, index=result.index)
    else:
        mask = (series < bounds["lower_bound"]) | (series > bounds["upper_bound"])

    if method in {None, "keep"}:
        return result
    if method == "drop_rows":
        return result.loc[~mask].reset_index(drop=True)
    if method == "winsorize":
        result[column] = series.astype(float).clip(
            lower=bounds["lower_bound"],
            upper=bounds["upper_bound"],
        )
        return result
    if method == "mark":
        result[f"is_outlier_{column}"] = mask
        return result
    raise ValueError(f"不支持的异常值处理方式：{method}")


def _analysis_path(project_id: str) -> Path:
    return project_workspace.get_project_path(project_id) / ANALYSIS_DIR


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
