import pandas as pd


def detect_and_parse_types(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    """Parse likely date columns and classify fields for analysis."""
    result = df.copy()
    date_columns: list[str] = []

    for column in result.columns:
        series = result[column]
        name_hint = any(word in str(column).lower() for word in ("date", "time", "日期", "时间", "年月"))
        if pd.api.types.is_datetime64_any_dtype(series):
            date_columns.append(column)
        elif series.dtype == "object" and (name_hint or series.nunique(dropna=True) > 5):
            parsed = pd.to_datetime(series, errors="coerce")
            valid_ratio = parsed.notna().sum() / max(series.notna().sum(), 1)
            if valid_ratio >= 0.8:
                result[column] = parsed
                date_columns.append(column)

    numeric = result.select_dtypes(include="number").columns.tolist()
    categories: list[str] = []
    texts: list[str] = []
    for column in result.select_dtypes(include=["object", "category", "bool"]).columns:
        unique = result[column].nunique(dropna=True)
        ratio = unique / max(result[column].notna().sum(), 1)
        if unique <= 50 or ratio <= 0.2:
            categories.append(column)
        else:
            texts.append(column)

    return result, {
        "numeric": numeric,
        "categorical": categories,
        "datetime": date_columns,
        "text": texts,
    }


def type_summary(df: pd.DataFrame, field_types: dict[str, list[str]]) -> pd.DataFrame:
    labels = {}
    for kind, columns in field_types.items():
        for column in columns:
            labels[column] = kind
    return pd.DataFrame(
        {
            "字段名": df.columns,
            "Pandas 类型": [str(dtype) for dtype in df.dtypes],
            "识别类型": [labels.get(column, "other") for column in df.columns],
        }
    )

