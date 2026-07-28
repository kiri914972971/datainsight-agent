import warnings

import numpy as np
import pandas as pd

from src.outlier import detect_outliers_iqr


EXPLORATION_FIELD_ROLES = (
    "identifier",
    "numeric",
    "categorical",
    "boolean",
    "datetime",
    "derived_time",
    "constant",
    "unsupported",
)

_CONFIRMED_TYPE_TO_ROLE = {
    "identifier": "identifier",
    "numeric": "numeric",
    "categorical": "categorical",
    "boolean": "boolean",
    "datetime": "datetime",
    "derived_time": "derived_time",
    "constant": "constant",
    "unsupported": "unsupported",
    "ID字段": "identifier",
    "日期字段": "datetime",
    "时间字段": "datetime",
    "金额字段": "numeric",
    "数量字段": "numeric",
    "产品字段": "categorical",
    "区域字段": "categorical",
    "人员字段": "categorical",
    "类别字段": "categorical",
    "布尔字段": "boolean",
    "忽略字段": "unsupported",
    "其他字段": "unsupported",
}

_DERIVED_TIME_EXACT_NAMES = {
    "年",
    "年份",
    "year",
    "月",
    "月份",
    "month",
    "季度",
    "quarter",
    "星期",
    "周几",
    "weekday",
    "week_day",
}

_DERIVED_TIME_CHINESE_SUFFIXES = (
    "年份",
    "月份",
    "季度",
    "星期",
    "周几",
    "年",
    "月",
)

_DERIVED_TIME_ENGLISH_SUFFIXES = (
    "year",
    "month",
    "quarter",
    "weekday",
    "week_day",
)


def is_derived_time_column(column_name, series):
    """Return whether a column name conservatively describes a derived time field."""
    del series

    normalized_name = str(column_name).strip().lower()
    if normalized_name in _DERIVED_TIME_EXACT_NAMES:
        return True

    if any(
        normalized_name.endswith(suffix)
        and len(normalized_name) > len(suffix)
        for suffix in _DERIVED_TIME_CHINESE_SUFFIXES
    ):
        return True

    tokenized_name = normalized_name.replace("-", "_").replace(" ", "_")
    while "__" in tokenized_name:
        tokenized_name = tokenized_name.replace("__", "_")

    return any(
        tokenized_name.endswith(f"_{suffix}")
        for suffix in _DERIVED_TIME_ENGLISH_SUFFIXES
    )


def build_exploration_field_roles(
    df,
    identifier_columns=None,
    datetime_columns=None,
    invalid_columns=None,
    confirmed_type_by_column=None,
):
    """Build one deterministic exploration role for every DataFrame column."""
    identifier_columns = (
        set(identifier_columns) if identifier_columns is not None else set()
    )
    datetime_columns = (
        set(datetime_columns) if datetime_columns is not None else set()
    )
    invalid_columns = set(invalid_columns) if invalid_columns is not None else set()
    confirmed_type_by_column = (
        dict(confirmed_type_by_column)
        if confirmed_type_by_column is not None
        else {}
    )

    role_by_column = {}
    columns_by_role = {role: [] for role in EXPLORATION_FIELD_ROLES}
    excluded_reasons = {}

    for column in df.columns:
        series = df[column]
        role = None
        unsupported_reason = None

        if column in invalid_columns:
            role = "unsupported"
            unsupported_reason = "无效字段"
        else:
            confirmed_type = confirmed_type_by_column.get(column)
            confirmed_role = _CONFIRMED_TYPE_TO_ROLE.get(confirmed_type)
            if confirmed_role is not None:
                role = confirmed_role
                if role == "unsupported":
                    unsupported_reason = "人工确认排除字段"
            elif column in identifier_columns:
                role = "identifier"
            elif column in datetime_columns or pd.api.types.is_datetime64_any_dtype(
                series.dtype
            ):
                role = "datetime"
            elif is_derived_time_column(column, series):
                role = "derived_time"
            elif series.nunique(dropna=True) == 1:
                role = "constant"
            elif pd.api.types.is_bool_dtype(series.dtype):
                role = "boolean"
            elif pd.api.types.is_numeric_dtype(series.dtype):
                role = "numeric"
            elif (
                pd.api.types.is_object_dtype(series.dtype)
                or isinstance(series.dtype, pd.CategoricalDtype)
                or pd.api.types.is_string_dtype(series.dtype)
            ):
                if series.notna().any():
                    role = "categorical"
                else:
                    role = "unsupported"
                    unsupported_reason = "全部为空"
            else:
                role = "unsupported"
                unsupported_reason = "暂不支持的数据类型"

        role_by_column[column] = role
        columns_by_role[role].append(column)

        if role == "identifier":
            excluded_reasons[column] = "标识符字段"
        elif role == "datetime":
            excluded_reasons[column] = "日期时间字段"
        elif role == "derived_time":
            excluded_reasons[column] = "时间派生字段"
        elif role == "constant":
            excluded_reasons[column] = "仅有一个有效值"
        elif role == "unsupported":
            excluded_reasons[column] = unsupported_reason or "暂不支持的数据类型"

    return {
        "role_by_column": role_by_column,
        "columns_by_role": columns_by_role,
        "excluded_reasons": excluded_reasons,
    }


def build_exploration_overview(df, field_roles, dataset_name=None):
    """Build a display-ready overview from unified exploration field roles."""
    columns_by_role = field_roles.get("columns_by_role", {})
    role_by_column = field_roles.get("role_by_column", {})
    excluded_reasons = field_roles.get("excluded_reasons", {})

    numeric_columns = list(columns_by_role.get("numeric", []))
    categorical_columns = list(columns_by_role.get("categorical", []))
    boolean_columns = list(columns_by_role.get("boolean", []))
    datetime_columns = list(columns_by_role.get("datetime", []))
    identifier_columns = list(columns_by_role.get("identifier", []))

    datetime_summary = {
        "mode": "none",
        "column": None,
        "start_date": None,
        "end_date": None,
        "column_count": len(datetime_columns),
    }
    if len(datetime_columns) == 1:
        datetime_column = datetime_columns[0]
        datetime_summary["mode"] = "single"
        datetime_summary["column"] = datetime_column
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                parsed_dates = pd.to_datetime(
                    df[datetime_column],
                    errors="coerce",
                ).dropna()
            if not parsed_dates.empty:
                datetime_summary["start_date"] = parsed_dates.min().strftime("%Y-%m-%d")
                datetime_summary["end_date"] = parsed_dates.max().strftime("%Y-%m-%d")
        except (KeyError, TypeError, ValueError, OverflowError):
            pass
    elif len(datetime_columns) > 1:
        datetime_summary["mode"] = "multiple"

    excluded_roles = {
        "identifier",
        "derived_time",
        "constant",
        "unsupported",
    }
    excluded_fields = []
    for column in df.columns:
        role = role_by_column.get(column)
        if role not in excluded_roles:
            continue
        excluded_fields.append(
            {
                "column": column,
                "role": role,
                "reason": excluded_reasons.get(column, ""),
            }
        )

    return {
        "dataset_name": dataset_name or "当前分析数据集",
        "row_count": len(df),
        "column_count": len(df.columns),
        "numeric_count": len(numeric_columns),
        "categorical_count": len(categorical_columns) + len(boolean_columns),
        "datetime_count": len(datetime_columns),
        "identifier_count": len(identifier_columns),
        "datetime_summary": datetime_summary,
        "excluded_fields": excluded_fields,
    }


def get_analysis_numeric_columns(df: pd.DataFrame, identifier_columns: list[str]) -> list[str]:
    identifiers = set(identifier_columns)
    return [
        column
        for column in df.select_dtypes(include="number").columns
        if column not in identifiers and not pd.api.types.is_datetime64_any_dtype(df[column])
    ]


def get_analysis_categorical_columns(df: pd.DataFrame, identifier_columns: list[str]) -> list[str]:
    identifiers = set(identifier_columns)
    columns = []
    for column in df.select_dtypes(include=["object", "category", "bool"]).columns:
        if column in identifiers:
            continue
        non_null_count = int(df[column].notna().sum())
        unique_count = int(df[column].nunique(dropna=True))
        unique_ratio = unique_count / max(non_null_count, 1)
        if unique_count <= 50 or unique_ratio <= 0.2:
            columns.append(column)
    return columns


def summarize_numeric_columns(df: pd.DataFrame, numeric_columns: list[str]) -> pd.DataFrame:
    rows = []
    for column in numeric_columns:
        series = pd.to_numeric(df[column], errors="coerce")
        rows.append(
            {
                "字段名": column,
                "均值": series.mean(),
                "中位数": series.median(),
                "标准差": series.std(),
                "最小值": series.min(),
                "最大值": series.max(),
                "偏度": series.skew(),
                "峰度": series.kurt(),
            }
        )
    return pd.DataFrame(rows).round(3)


def numeric_profile(df: pd.DataFrame, column: str) -> dict:
    series = pd.to_numeric(df[column], errors="coerce")
    valid_count = int(series.notna().sum())
    return {
        "均值": series.mean(),
        "中位数": series.median(),
        "标准差": series.std(),
        "最小值": series.min(),
        "最大值": series.max(),
        "偏度": series.skew(),
        "峰度": series.kurt(),
        "缺失率": series.isna().mean() * 100,
        "异常值比例": len(detect_outliers_iqr(df, column)) / max(valid_count, 1) * 100,
    }


def interpret_numeric_distribution(series: pd.Series) -> str:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return "当前字段没有可用于分析的有效数值。"

    mean = values.mean()
    median = values.median()
    skewness = values.skew()
    kurtosis = values.kurt()
    abs_skewness = abs(skewness) if pd.notna(skewness) else 0

    if abs_skewness < 0.5:
        distribution = "分布较为对称"
    elif abs_skewness < 1:
        distribution = "呈轻度右偏" if skewness > 0 else "呈轻度左偏"
    else:
        distribution = "呈明显右偏" if skewness > 0 else "呈明显左偏"

    explanations = [distribution]
    difference_ratio = abs(mean - median) / max(abs(median), values.std(), 1e-9)
    if difference_ratio >= 0.1:
        if mean > median:
            explanations.append("少数较大值可能拉高均值，建议同时关注中位数")
        else:
            explanations.append("少数较小值可能拉低均值，建议同时关注中位数")
    if pd.notna(kurtosis) and kurtosis > 3:
        explanations.append("分布尖峰厚尾，可能存在极端值")

    q1, q3 = values.quantile([0.25, 0.75])
    iqr = q3 - q1
    outlier_ratio = ((values < q1 - 1.5 * iqr) | (values > q3 + 1.5 * iqr)).mean() * 100
    if outlier_ratio > 5:
        explanations.append(f"IQR异常值占比约 {outlier_ratio:.1f}%，需要重点关注")
    return "；".join(explanations) + "。"


def summarize_categorical_columns(df: pd.DataFrame, categorical_columns: list[str]) -> pd.DataFrame:
    rows = []
    for column in categorical_columns:
        counts = df[column].value_counts(dropna=True)
        non_null_count = int(df[column].notna().sum())
        top_count = int(counts.iloc[0]) if not counts.empty else 0
        rows.append(
            {
                "字段名": column,
                "最常见取值": counts.index[0] if not counts.empty else None,
                "出现次数": top_count,
                "占比": round(top_count / max(non_null_count, 1) * 100, 2),
                "唯一值数量": int(df[column].nunique(dropna=True)),
            }
        )
    return pd.DataFrame(rows)


def categorical_profile(series: pd.Series) -> dict:
    counts = series.value_counts(dropna=True)
    non_null_count = int(series.notna().sum())
    top_count = int(counts.iloc[0]) if not counts.empty else 0
    top_share = top_count / max(non_null_count, 1) * 100
    top_five_share = int(counts.head(5).sum()) / max(non_null_count, 1) * 100
    return {
        "唯一值数量": int(series.nunique(dropna=True)),
        "Top 1 类别": counts.index[0] if not counts.empty else None,
        "Top 1 占比": top_share,
        "Top 5 类别覆盖率": top_five_share,
        "集中程度": _concentration_label(top_share),
    }


def interpret_categorical_distribution(series: pd.Series, column: str | None = None) -> str:
    profile = categorical_profile(series)
    label = column or str(series.name or "该字段")
    top_share = profile["Top 1 占比"]
    if top_share >= 80:
        return (
            f"{label}高度集中，Top 类别占比 {top_share:.1f}%，"
            "说明字段区分度较低，不适合直接进行类别间对比分析。"
        )
    if top_share >= 50:
        return f"{label}呈中度集中，Top 类别占比 {top_share:.1f}%，分析时需要关注头部类别影响。"
    return f"{label}分布较分散，Top 类别占比 {top_share:.1f}%，适合进一步比较不同类别表现。"


def categorical_distribution_table(series: pd.Series, top_n: int) -> pd.DataFrame:
    counts = series.value_counts(dropna=True).head(top_n)
    total = max(int(series.notna().sum()), 1)
    return pd.DataFrame(
        {
            "类别": counts.index.astype(str),
            "数量": counts.values,
            "占比": (counts.values / total * 100).round(2),
        }
    )


def calculate_correlation_pairs(df: pd.DataFrame, numeric_columns: list[str]) -> pd.DataFrame:
    if len(numeric_columns) < 2:
        return pd.DataFrame(columns=["字段A", "字段B", "相关系数", "相关强度", "可能含义"])
    correlation = df[numeric_columns].corr()
    rows = []
    for index, field_a in enumerate(numeric_columns):
        for field_b in numeric_columns[index + 1 :]:
            value = correlation.loc[field_a, field_b]
            if pd.isna(value):
                continue
            direction = "正相关" if value >= 0 else "负相关"
            strength = interpret_correlation_strength(value)
            if strength == "相关性较弱":
                meaning = f"{field_a} 与 {field_b} 的线性相关性较弱，暂未显示明显共同变化关系。"
            else:
                meaning = f"{field_a} 与 {field_b} 呈{strength.replace('相关', '')}{direction}，两者通常共同变化。"
            rows.append(
                {
                    "字段A": field_a,
                    "字段B": field_b,
                    "相关系数": round(float(value), 3),
                    "相关强度": strength,
                    "可能含义": meaning,
                    "_absolute_correlation": abs(value),
                }
            )
    if not rows:
        return pd.DataFrame(columns=["字段A", "字段B", "相关系数", "相关强度", "可能含义"])
    result = pd.DataFrame(rows).sort_values("_absolute_correlation", ascending=False)
    return result.drop(columns="_absolute_correlation").reset_index(drop=True)


def interpret_correlation_strength(correlation: float) -> str:
    value = abs(correlation)
    if value >= 0.8:
        return "强相关"
    if value >= 0.5:
        return "中等相关"
    if value >= 0.3:
        return "弱相关"
    return "相关性较弱"


def _concentration_label(top_share: float) -> str:
    if top_share >= 80:
        return "高度集中"
    if top_share >= 50:
        return "中度集中"
    return "分布较分散"
