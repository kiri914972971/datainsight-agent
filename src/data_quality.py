import pandas as pd

from src.outlier import summarize_outliers


IDENTIFIER_NAME_HINTS = (
    "编号",
    "工号",
    "订单号",
    "流水号",
    "客户号",
    "用户号",
    "销售工号",
    "客户id",
    "用户id",
    "销售id",
    "customer_id",
    "user_id",
    "employee_id",
    "order_id",
)

MEASURE_NAME_HINTS = (
    "金额",
    "价格",
    "单价",
    "数量",
    "人数",
    "比例",
    "比率",
    "成本",
    "利润",
    "收入",
    "销量",
    "amount",
    "price",
    "quantity",
    "count",
    "rate",
    "revenue",
    "cost",
    "profit",
)


def detect_invalid_columns(df: pd.DataFrame, missing_threshold: float = 0.95) -> list[str]:
    """Find unnamed or nearly empty columns that are likely invalid."""
    invalid = []
    for column in df.columns:
        name = str(column).strip().lower()
        missing_ratio = df[column].isna().mean()
        if name.startswith("unnamed:") or missing_ratio >= missing_threshold:
            invalid.append(column)
    return invalid


def suspicious_columns(df: pd.DataFrame, missing_threshold: float = 0.95) -> list[str]:
    return detect_invalid_columns(df, missing_threshold)


def identifier_reason(df: pd.DataFrame, column: str) -> str | None:
    series = df[column]
    if pd.api.types.is_datetime64_any_dtype(series):
        return None

    non_null_count = int(series.notna().sum())
    if non_null_count == 0:
        return None

    normalized_name = str(column).strip().lower()
    if normalized_name == "id" or normalized_name.endswith("_id") or any(
        hint in normalized_name for hint in IDENTIFIER_NAME_HINTS
    ):
        return "字段名包含 ID、编号、工号、订单号等标识词"

    unique_ratio = series.nunique(dropna=True) / non_null_count
    is_measure_name = any(hint in normalized_name for hint in MEASURE_NAME_HINTS)
    if unique_ratio > 0.9 and series.isna().mean() < 0.5 and not is_measure_name:
        if pd.api.types.is_numeric_dtype(series):
            numeric = pd.to_numeric(series, errors="coerce").dropna()
            if not numeric.empty and (numeric % 1 == 0).all():
                return "唯一值占比超过 90%，且取值形态类似记录标识"
        else:
            return "唯一值占比超过 90%"
    return None


def detect_identifier_columns(df: pd.DataFrame, excluded_columns: list[str] | None = None) -> list[str]:
    excluded = set(excluded_columns or [])
    return [
        column
        for column in df.columns
        if column not in excluded and identifier_reason(df, column) is not None
    ]


def summarize_identifier_columns(df: pd.DataFrame, identifier_columns: list[str]) -> pd.DataFrame:
    rows = []
    for column in identifier_columns:
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


def _missing_recommendation(series: pd.Series) -> str:
    ratio = series.isna().mean()
    if ratio >= 0.8:
        return "删除字段或重新获取数据源"
    if ratio >= 0.3:
        return "谨慎填充，建议结合业务判断"
    if ratio == 0:
        return "无需处理"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "不建议随意填充"
    if pd.api.types.is_numeric_dtype(series):
        return "均值 / 中位数填充"
    return "众数填充"


def summarize_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column in df.columns:
        missing_count = int(df[column].isna().sum())
        rows.append(
            {
                "字段名": column,
                "数据类型": str(df[column].dtype),
                "缺失值数量": missing_count,
                "缺失值比例": round(missing_count / max(len(df), 1) * 100, 2),
                "推荐处理方式": _missing_recommendation(df[column]),
            }
        )
    return pd.DataFrame(rows).sort_values("缺失值比例", ascending=False, ignore_index=True)


def summarize_duplicates(df: pd.DataFrame) -> dict:
    duplicate_mask = df.duplicated(keep=False)
    duplicate_count = int(df.duplicated().sum())
    return {
        "duplicate_count": duplicate_count,
        "duplicate_ratio": round(duplicate_count / max(len(df), 1) * 100, 2),
        "preview": df.loc[duplicate_mask].copy(),
    }


def apply_missing_value_fix(df: pd.DataFrame, column: str, method: str) -> pd.DataFrame:
    if column not in df.columns:
        raise KeyError(f"字段不存在：{column}")
    result = df.copy()
    if method == "均值填充":
        if not pd.api.types.is_numeric_dtype(result[column]):
            raise ValueError("均值填充仅适用于数值字段。")
        result[column] = result[column].fillna(result[column].mean())
    elif method == "中位数填充":
        if not pd.api.types.is_numeric_dtype(result[column]):
            raise ValueError("中位数填充仅适用于数值字段。")
        result[column] = result[column].fillna(result[column].median())
    elif method == "众数填充":
        mode = result[column].mode(dropna=True)
        if not mode.empty:
            result[column] = result[column].fillna(mode.iloc[0])
    else:
        raise ValueError(f"不支持的缺失值处理方式：{method}")
    return result


def drop_high_missing_columns(df: pd.DataFrame, threshold: float = 0.8) -> pd.DataFrame:
    columns = [column for column in df.columns if df[column].isna().mean() >= threshold]
    return df.drop(columns=columns).copy()


def drop_duplicate_rows(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop_duplicates().reset_index(drop=True)


def calculate_quality_score(
    df: pd.DataFrame,
    invalid_columns: list[str],
    numeric_columns: list[str],
) -> int:
    missing_count = int(df.isna().sum().sum())
    duplicate_count = int(df.duplicated().sum())
    outliers = summarize_outliers(df, numeric_columns)
    outlier_count = int(outliers["异常值数量"].sum()) if not outliers.empty else 0
    cell_count = max(df.shape[0] * df.shape[1], 1)
    numeric_value_count = max(int(df[numeric_columns].notna().sum().sum()), 1) if numeric_columns else 1
    deductions = (
        min(30, round(missing_count / cell_count * 100))
        + min(20, round(duplicate_count / max(len(df), 1) * 100))
        + min(25, len(invalid_columns) * 5)
        + min(25, round(outlier_count / numeric_value_count * 100))
    )
    return max(0, 100 - deductions)


def data_quality_summary(
    df: pd.DataFrame,
    invalid_columns: list[str],
    identifier_columns: list[str],
    numeric_columns: list[str],
) -> dict:
    outliers = summarize_outliers(df, numeric_columns, identifier_columns)
    return {
        "score": calculate_quality_score(df, invalid_columns, numeric_columns),
        "missing_values": int(df.isna().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
        "suspicious_columns": invalid_columns,
        "suspicious_column_count": len(invalid_columns),
        "outlier_count": int(outliers["异常值数量"].sum()) if not outliers.empty else 0,
        "identifier_columns": identifier_columns,
        "identifier_column_count": len(identifier_columns),
    }


def generate_data_repair_suggestions(
    df: pd.DataFrame,
    invalid_columns: list[str],
    identifier_columns: list[str],
    outlier_summary: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    high_missing = [column for column in df.columns if df[column].isna().mean() >= 0.8]
    for column in high_missing:
        rows.append(
            {
                "问题类型": "缺失率过高",
                "涉及字段": column,
                "影响": "字段信息严重不足，可能无法支持可靠分析",
                "推荐操作": "建议重新获取数据源，确认后再删除该字段",
                "操作建议": "请在上方缺失值处理区域处理",
            }
        )
    if df.duplicated().any():
        rows.append(
            {
                "问题类型": "重复行",
                "涉及字段": "整行",
                "影响": "可能导致金额、客户数等指标重复计算",
                "推荐操作": "建议确认业务含义后删除重复行",
                "操作建议": "请在上方重复值诊断区域处理",
            }
        )
    for column in identifier_columns:
        rows.append(
            {
                "问题类型": "疑似 ID 字段",
                "涉及字段": column,
                "影响": "不适合做均值、偏度、异常值和相关性分析",
                "推荐操作": "已自动从统计分析中排除",
                "操作建议": "无需处理，仅标记",
            }
        )
    if "异常值数量" in outlier_summary.columns:
        for _, row in outlier_summary.loc[outlier_summary["异常值数量"] > 0].iterrows():
            rows.append(
                {
                    "问题类型": "检测到异常值",
                    "涉及字段": row["字段名"],
                    "影响": "可能拉高或拉低整体统计结果",
                    "推荐操作": "建议先查看异常值明细，再决定保留、截断或删除",
                    "操作建议": "请在上方异常值诊断与处理区域查看",
                }
            )
    for column in invalid_columns:
        if column not in high_missing:
            rows.append(
                {
                    "问题类型": "疑似无效字段",
                    "涉及字段": column,
                    "影响": "可能增加数据噪声并干扰分析",
                    "推荐操作": "确认业务含义后，可删除字段",
                    "操作建议": "请在上方缺失值处理区域确认后处理",
                }
            )
    return pd.DataFrame(rows)


def quality_stars(score: int) -> str:
    filled = max(0, min(5, round(score / 20)))
    return "★" * filled + "☆" * (5 - filled)
