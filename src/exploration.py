import numpy as np
import pandas as pd

from src.outlier import detect_outliers_iqr


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
