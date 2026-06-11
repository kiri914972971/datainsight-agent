import numpy as np
import pandas as pd


def column_summary(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "字段名": df.columns,
            "数据类型": [str(dtype) for dtype in df.dtypes],
            "缺失值数量": df.isna().sum().values,
            "缺失值比例": (df.isna().mean().values * 100).round(2),
            "唯一值数量": df.nunique(dropna=True).values,
        }
    )


def numeric_summary(df: pd.DataFrame, numeric_columns: list[str]) -> pd.DataFrame:
    rows = []
    for column in numeric_columns:
        series = pd.to_numeric(df[column], errors="coerce")
        rows.append(
            {
                "字段名": column,
                "mean": series.mean(),
                "median": series.median(),
                "std": series.std(),
                "min": series.min(),
                "max": series.max(),
                "skewness": series.skew(),
                "kurtosis": series.kurt(),
            }
        )
    return pd.DataFrame(rows).round(3)


def categorical_summary(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    rows = []
    for column in columns:
        counts = df[column].value_counts(dropna=True)
        rows.append(
            {
                "字段名": column,
                "top value": counts.index[0] if not counts.empty else None,
                "top frequency": int(counts.iloc[0]) if not counts.empty else 0,
            }
        )
    return pd.DataFrame(rows)


def outlier_summary(df: pd.DataFrame, numeric_columns: list[str]) -> pd.DataFrame:
    rows = []
    for column in numeric_columns:
        series = pd.to_numeric(df[column], errors="coerce").dropna()
        q1, q3 = series.quantile([0.25, 0.75]) if not series.empty else (np.nan, np.nan)
        iqr = q3 - q1
        count = int(((series < q1 - 1.5 * iqr) | (series > q3 + 1.5 * iqr)).sum()) if not series.empty else 0
        rows.append({"字段名": column, "异常值数量": count, "异常值比例": round(count / max(len(series), 1) * 100, 2)})
    return pd.DataFrame(rows)
