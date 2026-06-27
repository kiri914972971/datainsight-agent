from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from src import project_workspace
from src.services.current_dataset_service import load_current_analysis_dataframe
from src.services.field_mapping_service import load_field_mappings


EDA_REPORT_FILE = "eda_report.json"
CORRELATION_THRESHOLD = 0.7
STRONG_CORRELATION_THRESHOLD = 0.8
CONCENTRATION_THRESHOLD = 0.6
OUTLIER_RATIO_THRESHOLD = 0.05
MISSING_RATE_THRESHOLD = 0.3

DATE_FIELD_TYPES = {"日期字段", "时间字段", "date", "datetime"}
DATE_KEYWORDS = ("date", "time", "日期", "时间", "成交日期", "订单日期", "创建时间", "支付时间")


def generate_eda_report(project_id: str) -> dict[str, Any]:
    """Generate field-level exploratory analysis from the persisted Analysis Dataset."""
    try:
        dataframe = load_current_analysis_dataframe(project_id)
    except Exception as exc:
        report = _empty_report(
            project_id,
            {
                "type": "missing_current_analysis_dataset",
                "severity": "high",
                "message": f"无法加载当前分析数据集：{exc}",
            },
        )
        _save_eda_report(project_id, report)
        return report

    field_mappings = _safe_load(load_field_mappings, project_id)
    date_columns = _detect_date_columns(dataframe, field_mappings)
    numeric_columns = _numeric_columns(dataframe)
    categorical_columns = _categorical_columns(dataframe, date_columns)

    numeric_analysis = _numeric_analysis(dataframe, numeric_columns)
    categorical_analysis = _categorical_analysis(dataframe, categorical_columns)
    correlation_analysis = _correlation_analysis(dataframe, numeric_columns)
    outlier_analysis = _outlier_analysis(dataframe, numeric_columns)
    insights = _generate_insights(
        categorical_analysis,
        correlation_analysis,
        outlier_analysis,
    )
    warnings = _generate_warnings(
        dataframe,
        categorical_analysis,
        correlation_analysis,
        outlier_analysis,
    )

    report = {
        "overview": {
            "row_count": int(len(dataframe)),
            "column_count": int(len(dataframe.columns)),
            "numeric_column_count": int(len(numeric_columns)),
            "categorical_column_count": int(len(categorical_columns)),
            "date_column_count": int(len(date_columns)),
        },
        "numeric_analysis": numeric_analysis,
        "categorical_analysis": categorical_analysis,
        "correlation_analysis": correlation_analysis,
        "outlier_analysis": outlier_analysis,
        "insights": insights,
        "warnings": warnings,
        "metadata": _metadata(project_id),
    }
    _save_eda_report(project_id, report)
    return report


def _numeric_analysis(
    dataframe: pd.DataFrame,
    numeric_columns: list[str],
) -> list[dict[str, Any]]:
    rows = []
    for column in numeric_columns:
        series = pd.to_numeric(dataframe[column], errors="coerce")
        rows.append(
            {
                "column": column,
                "mean": _json_number(series.mean()),
                "median": _json_number(series.median()),
                "std": _json_number(series.std()),
                "min": _json_number(series.min()),
                "max": _json_number(series.max()),
                "missing_rate": _json_number(dataframe[column].isna().mean()),
            }
        )
    return rows


def _categorical_analysis(
    dataframe: pd.DataFrame,
    categorical_columns: list[str],
) -> list[dict[str, Any]]:
    rows = []
    total_rows = len(dataframe)
    for column in categorical_columns:
        counts = dataframe[column].astype("string").fillna("<缺失>").value_counts(dropna=False)
        top_values = [
            {
                "value": str(value),
                "count": int(count),
                "ratio": _json_number(count / total_rows if total_rows else 0),
            }
            for value, count in counts.head(5).items()
        ]
        rows.append(
            {
                "column": column,
                "unique_count": int(dataframe[column].nunique(dropna=True)),
                "top5_values": top_values,
                "top5_ratio": _json_number(sum(item["ratio"] for item in top_values)),
                "top1_ratio": top_values[0]["ratio"] if top_values else 0,
                "missing_rate": _json_number(dataframe[column].isna().mean()),
            }
        )
    return rows


def _correlation_analysis(
    dataframe: pd.DataFrame,
    numeric_columns: list[str],
) -> list[dict[str, Any]]:
    if len(numeric_columns) < 2:
        return []
    numeric_df = dataframe[numeric_columns].apply(pd.to_numeric, errors="coerce")
    correlation_matrix = numeric_df.corr(method="pearson")
    rows = []
    for index, column_a in enumerate(numeric_columns):
        for column_b in numeric_columns[index + 1 :]:
            correlation = correlation_matrix.loc[column_a, column_b]
            if pd.isna(correlation):
                continue
            if abs(float(correlation)) > CORRELATION_THRESHOLD:
                rows.append(
                    {
                        "column_a": column_a,
                        "column_b": column_b,
                        "correlation": _json_number(correlation),
                    }
                )
    return sorted(rows, key=lambda item: abs(item["correlation"]), reverse=True)


def _outlier_analysis(
    dataframe: pd.DataFrame,
    numeric_columns: list[str],
) -> list[dict[str, Any]]:
    rows = []
    for column in numeric_columns:
        series = pd.to_numeric(dataframe[column], errors="coerce").dropna()
        if series.empty:
            q1 = q3 = iqr = lower_bound = upper_bound = None
            outlier_count = 0
            outlier_ratio = 0
        else:
            q1 = float(series.quantile(0.25))
            q3 = float(series.quantile(0.75))
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            outlier_mask = (series < lower_bound) | (series > upper_bound)
            outlier_count = int(outlier_mask.sum())
            outlier_ratio = outlier_count / len(series) if len(series) else 0
        rows.append(
            {
                "column": column,
                "q1": _json_number(q1),
                "q3": _json_number(q3),
                "iqr": _json_number(iqr),
                "lower_bound": _json_number(lower_bound),
                "upper_bound": _json_number(upper_bound),
                "outlier_count": outlier_count,
                "outlier_ratio": _json_number(outlier_ratio),
            }
        )
    return rows


def _generate_insights(
    categorical_analysis: list[dict[str, Any]],
    correlation_analysis: list[dict[str, Any]],
    outlier_analysis: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    insights = []
    for item in categorical_analysis:
        top_values = item.get("top5_values", [])
        if top_values and top_values[0]["ratio"] > CONCENTRATION_THRESHOLD:
            insights.append(
                {
                    "type": "high_concentration",
                    "message": (
                        f"{item['column']} 字段中「{top_values[0]['value']}」占比"
                        f"{top_values[0]['ratio']:.0%}，业务集中度较高。"
                    ),
                    "column": item["column"],
                }
            )
    for item in correlation_analysis:
        if abs(item["correlation"]) > STRONG_CORRELATION_THRESHOLD:
            direction = "正相关" if item["correlation"] > 0 else "负相关"
            insights.append(
                {
                    "type": "strong_correlation",
                    "message": f"{item['column_a']} 与 {item['column_b']} 呈强{direction}。",
                    "column_a": item["column_a"],
                    "column_b": item["column_b"],
                }
            )
    for item in outlier_analysis:
        if item["outlier_ratio"] > OUTLIER_RATIO_THRESHOLD:
            insights.append(
                {
                    "type": "high_outlier_ratio",
                    "message": f"{item['column']} 字段存在较多异常值。",
                    "column": item["column"],
                }
            )
    return insights


def _generate_warnings(
    dataframe: pd.DataFrame,
    categorical_analysis: list[dict[str, Any]],
    correlation_analysis: list[dict[str, Any]],
    outlier_analysis: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    warnings = []
    for column in dataframe.columns:
        missing_rate = dataframe[column].isna().mean()
        if missing_rate > MISSING_RATE_THRESHOLD:
            warnings.append(
                {
                    "type": "high_missing_rate",
                    "severity": "medium",
                    "message": f"{column} 缺失率为 {missing_rate:.0%}，存在数据质量风险。",
                    "column": str(column),
                    "missing_rate": _json_number(missing_rate),
                }
            )
    for item in categorical_analysis:
        top_values = item.get("top5_values", [])
        if top_values and top_values[0]["ratio"] > CONCENTRATION_THRESHOLD:
            warnings.append(
                {
                    "type": "high_concentration",
                    "severity": "medium",
                    "message": f"{item['column']} Top1 占比超过 60%。",
                    "column": item["column"],
                    "top1_ratio": item["top1_ratio"],
                }
            )
    for item in outlier_analysis:
        if item["outlier_ratio"] > OUTLIER_RATIO_THRESHOLD:
            warnings.append(
                {
                    "type": "high_outlier_ratio",
                    "severity": "medium",
                    "message": f"{item['column']} 异常值比例超过 5%。",
                    "column": item["column"],
                    "outlier_ratio": item["outlier_ratio"],
                }
            )
    for item in correlation_analysis:
        if abs(item["correlation"]) > STRONG_CORRELATION_THRESHOLD:
            warnings.append(
                {
                    "type": "strong_correlation",
                    "severity": "low",
                    "message": f"{item['column_a']} 与 {item['column_b']} 存在强相关。",
                    "column_a": item["column_a"],
                    "column_b": item["column_b"],
                    "correlation": item["correlation"],
                }
            )
    return warnings


def _numeric_columns(dataframe: pd.DataFrame) -> list[str]:
    return [
        str(column)
        for column in dataframe.columns
        if pd.api.types.is_numeric_dtype(dataframe[column])
    ]


def _categorical_columns(
    dataframe: pd.DataFrame,
    date_columns: list[str],
) -> list[str]:
    date_set = set(date_columns)
    return [
        str(column)
        for column in dataframe.columns
        if column not in date_set
        and (
            pd.api.types.is_object_dtype(dataframe[column])
            or pd.api.types.is_string_dtype(dataframe[column])
            or isinstance(dataframe[column].dtype, pd.CategoricalDtype)
            or pd.api.types.is_bool_dtype(dataframe[column])
        )
    ]


def _detect_date_columns(
    dataframe: pd.DataFrame,
    field_mappings: list[dict[str, Any]],
) -> list[str]:
    mapped_dates = []
    for item in field_mappings:
        column = item.get("column_name")
        confirmed_type = str(item.get("confirmed_type", "")).lower()
        if column in dataframe.columns and any(date_type.lower() in confirmed_type for date_type in DATE_FIELD_TYPES):
            mapped_dates.append(str(column))
    detected = []
    for column in dataframe.columns:
        if column in mapped_dates:
            detected.append(str(column))
            continue
        column_name = str(column).lower()
        if any(keyword.lower() in column_name for keyword in DATE_KEYWORDS) and _is_date_like(dataframe[column]):
            detected.append(str(column))
        elif pd.api.types.is_datetime64_any_dtype(dataframe[column]):
            detected.append(str(column))
    return list(dict.fromkeys(detected))


def _is_date_like(series: pd.Series) -> bool:
    if pd.api.types.is_numeric_dtype(series) or series.dropna().empty:
        return False
    parsed = pd.to_datetime(series, errors="coerce")
    return parsed.notna().mean() >= 0.8


def _empty_report(project_id: str, warning: dict[str, Any]) -> dict[str, Any]:
    return {
        "overview": {},
        "numeric_analysis": [],
        "categorical_analysis": [],
        "correlation_analysis": [],
        "outlier_analysis": [],
        "insights": [],
        "warnings": [warning],
        "metadata": _metadata(project_id),
    }


def _save_eda_report(project_id: str, report: dict[str, Any]) -> None:
    analysis_path = project_workspace.get_project_path(project_id) / "analysis"
    analysis_path.mkdir(parents=True, exist_ok=True)
    report_path = analysis_path / EDA_REPORT_FILE
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    project_workspace.update_project(project_id, {"latest_eda_report": report})


def _metadata(project_id: str) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "engine": "eda_engine_v1",
        "generated_at": _utc_now(),
        "report_file": f"analysis/{EDA_REPORT_FILE}",
    }


def _json_number(value: Any) -> float | int | None:
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return round(value, 6)
    return value


def _safe_load(loader, project_id: str) -> list[dict[str, Any]]:
    try:
        value = loader(project_id)
    except Exception:
        return []
    return value if isinstance(value, list) else []


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
