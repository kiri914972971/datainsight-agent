import numpy as np
import pandas as pd


def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        raise KeyError(f"字段不存在：{column}")
    return pd.to_numeric(df[column], errors="coerce")


def calculate_iqr_bounds(df: pd.DataFrame, column: str) -> dict:
    """Calculate IQR boundaries for a numeric-compatible column."""
    series = _numeric_series(df, column).dropna()
    if series.empty:
        return {
            "q1": np.nan,
            "q3": np.nan,
            "iqr": np.nan,
            "lower_bound": np.nan,
            "upper_bound": np.nan,
        }

    q1 = float(series.quantile(0.25))
    q3 = float(series.quantile(0.75))
    iqr = q3 - q1
    return {
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "lower_bound": q1 - 1.5 * iqr,
        "upper_bound": q3 + 1.5 * iqr,
    }


def _outlier_mask(df: pd.DataFrame, column: str, bounds: dict | None = None) -> pd.Series:
    bounds = bounds or calculate_iqr_bounds(df, column)
    series = _numeric_series(df, column)
    if pd.isna(bounds["lower_bound"]) or pd.isna(bounds["upper_bound"]):
        return pd.Series(False, index=df.index)
    return (series < bounds["lower_bound"]) | (series > bounds["upper_bound"])


def detect_outliers_iqr(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Return rows that are outside the column's IQR boundaries."""
    return df.loc[_outlier_mask(df, column)].copy()


def create_outlier_preview(
    df: pd.DataFrame,
    column: str,
    date_columns: list[str] | None = None,
    category_columns: list[str] | None = None,
    identifier_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Create a compact outlier table with useful row context."""
    outliers = detect_outliers_iqr(df, column)
    context_columns = []
    for candidates in (date_columns or [], category_columns or [], identifier_columns or []):
        for candidate in candidates:
            if candidate in df.columns and candidate != column and candidate not in context_columns:
                context_columns.append(candidate)

    preview_columns = [column] + context_columns
    preview = outliers[preview_columns].copy()
    preview.insert(0, "原始行索引", outliers.index)
    return preview


def create_outlier_download(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Create a full-row export with IQR diagnostic metadata."""
    bounds = calculate_iqr_bounds(df, column)
    outliers = df.loc[_outlier_mask(df, column, bounds)].copy()
    outliers.insert(0, "原始行索引", outliers.index)
    values = pd.to_numeric(outliers[column], errors="coerce")
    outliers["outlier_field"] = column
    outliers["outlier_value"] = values
    outliers["lower_bound"] = bounds["lower_bound"]
    outliers["upper_bound"] = bounds["upper_bound"]
    outliers["outlier_reason"] = np.where(
        values < bounds["lower_bound"],
        "below lower bound",
        "above upper bound",
    )
    return outliers


def summarize_outliers(
    df: pd.DataFrame,
    numeric_columns: list[str],
    identifier_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Summarize IQR outliers while always excluding identifier fields."""
    identifiers = set(identifier_columns or [])
    rows = []
    for column in numeric_columns:
        if column in identifiers:
            continue
        series = _numeric_series(df, column)
        valid_count = int(series.notna().sum())
        count = int(_outlier_mask(df, column).sum())
        rows.append(
            {
                "字段名": column,
                "异常值数量": count,
                "异常值比例": round(count / max(valid_count, 1) * 100, 2),
            }
        )
    return pd.DataFrame(rows)


def remove_outliers(df: pd.DataFrame, column: str) -> pd.DataFrame:
    return df.loc[~_outlier_mask(df, column)].copy()


def winsorize_outliers(df: pd.DataFrame, column: str) -> pd.DataFrame:
    result = df.copy()
    bounds = calculate_iqr_bounds(result, column)
    result[column] = _numeric_series(result, column).astype(float).clip(
        lower=bounds["lower_bound"],
        upper=bounds["upper_bound"],
    )
    return result


def replace_outliers_with_median(df: pd.DataFrame, column: str) -> pd.DataFrame:
    result = df.copy()
    mask = _outlier_mask(result, column)
    result[column] = _numeric_series(result, column).astype(float)
    result.loc[mask, column] = result[column].median()
    return result


def replace_outliers_with_quantile(
    df: pd.DataFrame,
    column: str,
    lower_q: float = 0.01,
    upper_q: float = 0.99,
) -> pd.DataFrame:
    if not 0 <= lower_q < upper_q <= 1:
        raise ValueError("替换分位数必须满足 0 <= 下侧分位数 < 上侧分位数 <= 1。")

    result = df.copy()
    series = _numeric_series(result, column).astype(float)
    result[column] = series
    bounds = calculate_iqr_bounds(result, column)
    lower_mask = series < bounds["lower_bound"]
    upper_mask = series > bounds["upper_bound"]
    result.loc[lower_mask, column] = series.quantile(lower_q)
    result.loc[upper_mask, column] = series.quantile(upper_q)
    return result


def _column_statistics(df: pd.DataFrame, column: str) -> dict:
    series = _numeric_series(df, column).dropna()
    return {
        "行数": len(df),
        "异常值数量": len(detect_outliers_iqr(df, column)),
        "均值": series.mean(),
        "中位数": series.median(),
        "最大值": series.max(),
        "最小值": series.min(),
        "标准差": series.std(),
        "偏度": series.skew(),
        "峰度": series.kurt(),
    }


def compare_before_after_outlier_treatment(
    before_df: pd.DataFrame,
    after_df: pd.DataFrame,
    column: str,
) -> pd.DataFrame:
    before = _column_statistics(before_df, column)
    after = _column_statistics(after_df, column)
    rows = [
        {"指标": metric, "处理前": before[metric], "处理后": after[metric]}
        for metric in before
    ]
    return pd.DataFrame(rows).round(3)
