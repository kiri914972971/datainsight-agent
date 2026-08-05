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

def _derived_time_component_kind(column_name):
    normalized_name = str(column_name).strip().lower()
    exact_kinds = {
        "年": "year",
        "年份": "year",
        "year": "year",
        "月": "month",
        "月份": "month",
        "month": "month",
        "季度": "quarter",
        "quarter": "quarter",
        "星期": "weekday",
        "周几": "weekday",
        "weekday": "weekday",
        "week_day": "weekday",
    }
    if normalized_name in exact_kinds:
        return exact_kinds[normalized_name]

    chinese_suffix_kinds = (
        ("年份", "year"),
        ("月份", "month"),
        ("季度", "quarter"),
        ("星期", "weekday"),
        ("周几", "weekday"),
        ("年", "year"),
        ("月", "month"),
    )
    for suffix, kind in chinese_suffix_kinds:
        if normalized_name.endswith(suffix) and len(normalized_name) > len(suffix):
            return kind

    tokenized_name = normalized_name.replace("-", "_").replace(" ", "_")
    while "__" in tokenized_name:
        tokenized_name = tokenized_name.replace("__", "_")
    english_suffix_kinds = (
        ("week_day", "weekday"),
        ("weekday", "weekday"),
        ("quarter", "quarter"),
        ("month", "month"),
        ("year", "year"),
    )
    for suffix, kind in english_suffix_kinds:
        if tokenized_name.endswith(f"_{suffix}"):
            return kind
    return None


def _matches_derived_time_values(series, component_kind):
    values = series.dropna()
    if values.empty or pd.api.types.is_datetime64_any_dtype(series.dtype):
        return False

    text_values = values.astype(str).str.strip()
    numeric_values = pd.to_numeric(text_values, errors="coerce")
    integer_like = numeric_values.notna() & np.isclose(
        numeric_values.fillna(0).to_numpy(dtype=float),
        np.rint(numeric_values.fillna(0).to_numpy(dtype=float)),
        rtol=0,
        atol=1e-9,
    )

    if component_kind == "year":
        matches = integer_like & numeric_values.between(1000, 9999)
    elif component_kind == "month":
        numeric_matches = integer_like & numeric_values.between(1, 12)
        text_matches = text_values.str.fullmatch(
            r"(?:0?[1-9]|1[0-2])月",
            case=False,
            na=False,
        )
        matches = numeric_matches | text_matches
    elif component_kind == "quarter":
        numeric_matches = integer_like & numeric_values.between(1, 4)
        text_matches = text_values.str.fullmatch(
            r"(?:(?:\d{4})\s*[-/]?\s*)?(?:Q[1-4]|第?[1-4]季度)",
            case=False,
            na=False,
        )
        matches = numeric_matches | text_matches
    elif component_kind == "weekday":
        numeric_matches = integer_like & numeric_values.between(0, 7)
        text_matches = text_values.str.fullmatch(
            r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|"
            r"Mon|Tue|Wed|Thu|Fri|Sat|Sun|星期[一二三四五六日天]|周[一二三四五六日天])",
            case=False,
            na=False,
        )
        matches = numeric_matches | text_matches
    else:
        return False

    return bool(matches.mean() >= 0.8)


def is_derived_time_column(column_name, series):
    """Return whether name and values describe a partial time component."""
    component_kind = _derived_time_component_kind(column_name)
    return bool(
        component_kind
        and _matches_derived_time_values(series, component_kind)
    )


def get_invalid_exploration_datetime_confirmations(
    df,
    confirmed_type_by_column,
):
    """Return partial time fields incorrectly confirmed as complete datetimes."""
    confirmed_types = dict(confirmed_type_by_column or {})
    datetime_confirmation_types = {"datetime", "日期字段", "时间字段"}
    return [
        column
        for column in df.columns
        if confirmed_types.get(column) in datetime_confirmation_types
        and is_derived_time_column(column, df[column])
    ]


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
            is_derived_time = is_derived_time_column(column, series)
            if confirmed_role == "datetime" and is_derived_time:
                role = "derived_time"
            elif confirmed_role is not None:
                role = confirmed_role
                if role == "unsupported":
                    unsupported_reason = "人工确认排除字段"
            elif column in identifier_columns:
                role = "identifier"
            elif is_derived_time:
                role = "derived_time"
            elif column in datetime_columns or pd.api.types.is_datetime64_any_dtype(
                series.dtype
            ):
                role = "datetime"
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
            parsed_dates = parse_exploration_datetime_series(
                df[datetime_column]
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


def clean_finite_numeric_values(series):
    """Return a numeric copy containing only finite values."""
    numeric_series = pd.to_numeric(series.copy(deep=True), errors="coerce")
    numeric_series = pd.Series(
        numeric_series,
        index=series.index,
        name=series.name,
    )
    numeric_series = numeric_series.replace([np.inf, -np.inf], np.nan)
    return numeric_series.dropna().astype(float)


def classify_numeric_distribution(series):
    """Classify finite numeric values as discrete or continuous."""
    values = clean_finite_numeric_values(series)
    if values.empty:
        return "continuous"

    integer_like = np.isclose(
        values.to_numpy(dtype=float),
        np.rint(values.to_numpy(dtype=float)),
        rtol=0,
        atol=1e-9,
    ).all()
    if integer_like and values.nunique(dropna=True) <= 30:
        return "discrete"
    return "continuous"


def calculate_histogram_bin_count(series):
    """Calculate a stable histogram bin count constrained to 10 through 50."""
    values = clean_finite_numeric_values(series)
    sample_count = len(values)
    if sample_count < 2 or values.min() == values.max():
        return 10

    with np.errstate(over="ignore", invalid="ignore"):
        value_range = float(values.max() - values.min())
    if not np.isfinite(value_range):
        return 50

    q1, q3 = values.quantile([0.25, 0.75])
    iqr = float(q3 - q1)
    if iqr > 0:
        bin_width = 2 * iqr * sample_count ** (-1 / 3)
        if np.isfinite(bin_width) and bin_width > 0:
            calculated_bins = int(np.ceil(value_range / bin_width))
        else:
            calculated_bins = 50
    else:
        calculated_bins = int(np.ceil(np.sqrt(sample_count)))

    return max(10, min(50, calculated_bins))


def build_discrete_numeric_frequency_table(series):
    """Build an ascending frequency table for discrete numeric values."""
    values = clean_finite_numeric_values(series)
    counts = values.value_counts(sort=False).sort_index()
    return [
        {
            "value": int(value) if float(value).is_integer() else float(value),
            "count": int(count),
        }
        for value, count in counts.items()
    ]


def generate_numeric_distribution_interpretation(series, field_name):
    """Generate a deterministic statistical description without recommendations."""
    values = clean_finite_numeric_values(series)
    if values.empty:
        return "当前字段没有可用于分析的有效数值。"
    if len(values) < 20:
        return "当前有效样本较少，分布特征可能不稳定。"
    if values.nunique(dropna=True) == 1:
        return f"{field_name} 的所有有效记录取值相同，当前数据无法形成分布差异。"

    if classify_numeric_distribution(values) == "discrete":
        counts = values.value_counts().sort_values(ascending=False)
        most_common_value = counts.index[0]
        most_common_count = int(counts.iloc[0])
        return (
            f"{field_name} 为离散数值字段，有效取值范围为 "
            f"{_plain_number(values.min())} 至 {_plain_number(values.max())}，"
            f"最常见取值为 {_plain_number(most_common_value)}"
            f"（{most_common_count} 条记录）。"
            "后续进行分组比较时，可同时观察均值和中位数。"
        )

    skewness = values.skew()
    if pd.isna(skewness):
        return "当前分布的偏度暂不可计算。后续进行分组比较时，可同时观察均值和中位数。"

    absolute_skewness = abs(float(skewness))
    if absolute_skewness < 0.5:
        description = f"{field_name} 的分布大致对称。"
    elif skewness > 0:
        degree = "存在一定右偏" if absolute_skewness < 1 else "右偏较明显"
        description = (
            f"{field_name} 的分布{degree}。"
            "均值高于中位数，少数较高取值可能拉高均值。"
        )
    else:
        degree = "存在一定左偏" if absolute_skewness < 1 else "左偏较明显"
        description = (
            f"{field_name} 的分布{degree}。"
            "均值低于中位数，少数较低取值可能拉低均值。"
        )
    return description + "后续进行分组比较时，可同时观察均值和中位数。"


def build_numeric_distribution_analysis(series, field_name):
    """Build serializable statistics and chart data for one numeric field."""
    values = clean_finite_numeric_values(series)
    total_count = len(series)
    valid_count = len(values)
    unique_count = int(values.nunique(dropna=True))

    if valid_count > 0 and unique_count == 1:
        status = "constant"
    elif valid_count < 5:
        status = "insufficient_data"
    else:
        status = "ok"

    distribution_type = classify_numeric_distribution(values)
    summary = {
        "mean": _finite_number(values.mean()) if valid_count else None,
        "median": _finite_number(values.median()) if valid_count else None,
        "std": _finite_number(values.std()) if valid_count else None,
        "min": _finite_number(values.min()) if valid_count else None,
        "q1": _finite_number(values.quantile(0.25)) if valid_count else None,
        "q3": _finite_number(values.quantile(0.75)) if valid_count else None,
        "max": _finite_number(values.max()) if valid_count else None,
    }
    advanced = {
        "p10": _finite_number(values.quantile(0.10)) if valid_count else None,
        "p25": _finite_number(values.quantile(0.25)) if valid_count else None,
        "p50": _finite_number(values.quantile(0.50)) if valid_count else None,
        "p75": _finite_number(values.quantile(0.75)) if valid_count else None,
        "p90": _finite_number(values.quantile(0.90)) if valid_count else None,
        "skew": _finite_number(values.skew()) if valid_count else None,
        "kurtosis": _finite_number(values.kurt()) if valid_count else None,
    }

    return {
        "status": status,
        "field_name": str(field_name),
        "original_dtype": str(series.dtype),
        "total_count": int(total_count),
        "valid_count": int(valid_count),
        "excluded_count": int(total_count - valid_count),
        "unique_count": unique_count,
        "distribution_type": distribution_type,
        "summary": summary,
        "advanced": advanced,
        "values": [float(value) for value in values.tolist()],
        "discrete_table": (
            build_discrete_numeric_frequency_table(values)
            if distribution_type == "discrete"
            else []
        ),
        "default_bin_count": (
            calculate_histogram_bin_count(values)
            if distribution_type == "continuous"
            else None
        ),
        "interpretation": generate_numeric_distribution_interpretation(
            values,
            field_name,
        ),
    }


def _finite_number(value):
    if value is None or pd.isna(value) or not np.isfinite(value):
        return None
    return float(value)


def _plain_number(value):
    number = float(value)
    if number.is_integer():
        return f"{number:,.0f}"
    return f"{number:,.6f}".rstrip("0").rstrip(".")


def build_categorical_composition_analysis(series, field_name):
    """Build complete, serializable category composition statistics."""
    valid_values = series.loc[series.notna()].copy()
    total_count = len(series)
    valid_count = len(valid_values)
    excluded_count = total_count - valid_count

    if valid_count == 0:
        return {
            "status": "no_valid_data",
            "field_name": str(field_name),
            "total_count": int(total_count),
            "valid_count": 0,
            "excluded_count": int(excluded_count),
            "category_count": 0,
            "top1_category": None,
            "top1_count": 0,
            "top1_ratio": 0.0,
            "top5_ratio": 0.0,
            "low_frequency_count": 0,
            "low_frequency_ratio": 0.0,
            "rows": [],
            "interpretation": "当前字段没有可用于类别构成分析的有效记录。",
        }

    counts = valid_values.value_counts(dropna=False, sort=False)
    count_rows = [
        {
            "category": _categorical_display_value(category),
            "count": int(count),
            "_stable_value": (
                _categorical_display_value(category).casefold(),
                _categorical_display_value(category),
                type(category).__name__,
                repr(category),
            ),
        }
        for category, count in counts.items()
    ]
    count_rows.sort(
        key=lambda item: (
            -item["count"],
            item["_stable_value"],
        )
    )

    cumulative_count = 0
    rows = []
    for rank, item in enumerate(count_rows, start=1):
        cumulative_count += item["count"]
        rows.append(
            {
                "rank": rank,
                "category": item["category"],
                "count": item["count"],
                "ratio": float(item["count"] / valid_count),
                "cumulative_ratio": float(cumulative_count / valid_count),
            }
        )

    category_count = len(rows)
    top1_row = rows[0]
    top5_count = sum(item["count"] for item in rows[:5])
    low_frequency_rows = [
        item
        for item in rows
        if item["ratio"] < 0.01
    ]
    result = {
        "status": "constant" if category_count == 1 else "ok",
        "field_name": str(field_name),
        "total_count": int(total_count),
        "valid_count": int(valid_count),
        "excluded_count": int(excluded_count),
        "category_count": int(category_count),
        "top1_category": top1_row["category"],
        "top1_count": int(top1_row["count"]),
        "top1_ratio": float(top1_row["ratio"]),
        "top5_ratio": float(top5_count / valid_count),
        "low_frequency_count": int(len(low_frequency_rows)),
        "low_frequency_ratio": float(
            sum(item["count"] for item in low_frequency_rows) / valid_count
        ),
        "rows": rows,
    }
    result["interpretation"] = generate_categorical_composition_interpretation(
        field_name,
        result,
    )
    return result


def build_categorical_top_n_chart_data(analysis_result, top_n):
    """Build Top N chart rows while keeping merged categories separate."""
    all_rows = analysis_result.get("rows", [])
    if not all_rows:
        return {
            "top_n": 0,
            "top_rows": [],
            "other_rows": [],
            "chart_rows": [],
            "has_other": False,
        }

    resolved_top_n = max(1, min(int(top_n), len(all_rows)))
    top_rows = [dict(item) for item in all_rows[:resolved_top_n]]
    other_rows = [dict(item) for item in all_rows[resolved_top_n:]]
    chart_rows = [
        {
            "category": item["category"],
            "count": int(item["count"]),
            "ratio": float(item["ratio"]),
            "is_merged_other": False,
        }
        for item in top_rows
    ]
    if other_rows:
        other_count = sum(item["count"] for item in other_rows)
        valid_count = max(int(analysis_result.get("valid_count", 0)), 1)
        chart_rows.append(
            {
                "category": "其他（合并）",
                "count": int(other_count),
                "ratio": float(other_count / valid_count),
                "is_merged_other": True,
            }
        )

    return {
        "top_n": resolved_top_n,
        "top_rows": top_rows,
        "other_rows": other_rows,
        "chart_rows": chart_rows,
        "has_other": bool(other_rows),
    }


def generate_categorical_composition_interpretation(
    field_name,
    composition_result,
    chart_result=None,
):
    """Generate a deterministic description of record-count composition."""
    status = composition_result.get("status")
    if status == "no_valid_data":
        return "当前字段没有可用于类别构成分析的有效记录。"
    if status == "constant":
        return "该字段只有一个有效类别，无法形成类别构成比较。"

    top1_category = composition_result.get("top1_category", "")
    top1_count = int(composition_result.get("top1_count", 0))
    top1_ratio = float(composition_result.get("top1_ratio", 0.0))
    category_count = int(composition_result.get("category_count", 0))
    top5_ratio = float(composition_result.get("top5_ratio", 0.0))
    descriptions = [
        (
            f"{field_name} 共包含 {category_count:,} 个类别。"
            f"{top1_category} 包含 {top1_count:,} 条记录，"
            f"占该字段有效记录的 {top1_ratio * 100:.2f}%。"
        ),
        f"Top 5 类别累计覆盖 {top5_ratio * 100:.2f}% 的有效记录。",
    ]

    low_frequency_count = int(
        composition_result.get("low_frequency_count", 0)
    )
    if low_frequency_count > 0:
        low_frequency_ratio = float(
            composition_result.get("low_frequency_ratio", 0.0)
        )
        descriptions.append(
            f"共有 {low_frequency_count:,} 个类别的记录数占比低于 1%，"
            f"合计占比 {low_frequency_ratio * 100:.2f}%。"
        )

    if chart_result and chart_result.get("has_other"):
        other_ratio = sum(
            float(item.get("ratio", 0.0))
            for item in chart_result.get("other_rows", [])
        )
        descriptions.append(
            f"当前图表中的“其他（合并）”合计占比 {other_ratio * 100:.2f}%。"
        )

    descriptions.append("以上内容仅描述当前分析数据集中的记录分布。")
    return "".join(descriptions)


def _categorical_display_value(value):
    return str(value)


def calculate_dataframe_height(
    row_count,
    max_visible_rows=12,
    row_height=35,
    header_height=38,
):
    """Calculate a compact dataframe height with a bounded visible row count."""
    resolved_row_count = max(int(row_count or 0), 0)
    resolved_max_rows = max(int(max_visible_rows), 1)
    resolved_row_height = max(int(row_height), 1)
    resolved_header_height = max(int(header_height), 1)
    visible_rows = min(max(resolved_row_count, 1), resolved_max_rows)
    vertical_padding = 6
    return (
        resolved_header_height
        + visible_rows * resolved_row_height
        + vertical_padding
    )


def categorical_composition_table_title(category_count, display_limit=5000):
    """Return a truthful title for complete or page-limited category tables."""
    if int(category_count or 0) > int(display_limit):
        return f"类别构成表（页面展示前 {int(display_limit):,} 类）"
    return "完整类别构成表"


TIME_GRANULARITIES = ("day", "week", "month", "quarter", "year")
TIME_GRANULARITY_LABELS = {
    "day": "日",
    "week": "周",
    "month": "月",
    "quarter": "季度",
    "year": "年",
}
_TIME_GRANULARITY_LABELS = TIME_GRANULARITY_LABELS
TIME_DISTRIBUTION_MAX_POINTS = 400


def get_time_distribution_datetime_columns(df, field_roles):
    """Return DataFrame columns whose unified exploration role is datetime."""
    role_by_column = field_roles.get("role_by_column", {})
    datetime_columns = set(
        field_roles.get("columns_by_role", {}).get("datetime", [])
    )
    options = []
    for column in df.columns:
        if (
            column not in datetime_columns
            or role_by_column.get(column) != "datetime"
            or is_derived_time_column(column, df[column])
        ):
            continue
        dtype = df[column].dtype
        if (
            pd.api.types.is_numeric_dtype(dtype)
            and not pd.api.types.is_datetime64_any_dtype(dtype)
        ):
            continue
        if not (
            pd.api.types.is_datetime64_any_dtype(dtype)
            or pd.api.types.is_object_dtype(dtype)
            or pd.api.types.is_string_dtype(dtype)
        ):
            continue
        options.append(column)
    return options


def resolve_time_distribution_datetime_selection(
    datetime_columns,
    current_selection,
):
    """Keep a valid datetime selection or fall back to the first option."""
    options = list(datetime_columns or [])
    if current_selection in options:
        return current_selection
    return options[0] if options else None


def build_time_distribution_view_data(analysis_result):
    """Prepare existing helper output for UI rendering without recomputation."""
    status = analysis_result.get("status")
    known_status = status in {
        "ok",
        "no_valid_dates",
        "single_date",
        "too_dense",
    }
    source_rows = analysis_result.get("rows", [])
    show_chart = (
        status == "ok"
        and bool(source_rows)
        and int(analysis_result.get("period_count", 0))
        <= TIME_DISTRIBUTION_MAX_POINTS
    )
    rendered_rows = [dict(item) for item in source_rows] if show_chart else []
    return {
        "known_status": known_status,
        "show_chart": show_chart,
        "show_details": show_chart,
        "chart_rows": rendered_rows,
        "detail_rows": [dict(item) for item in rendered_rows],
        "zero_ranges": (
            [
                dict(item)
                for item in analysis_result.get("zero_ranges", [])
            ]
            if show_chart
            else []
        ),
    }


def build_time_distribution_analysis(series, field_name, granularity=None):
    """Build a complete natural-period time distribution without side effects."""
    if granularity is not None and granularity not in TIME_GRANULARITIES:
        raise ValueError(
            "不支持的时间粒度。可选值为 day、week、month、quarter、year。"
        )

    total_count = len(series)
    valid_dates = _clean_time_distribution_dates(series)
    valid_count = len(valid_dates)
    selected_granularity = granularity or "day"
    if valid_count == 0:
        return {
            "status": "no_valid_dates",
            "field_name": str(field_name),
            "total_count": int(total_count),
            "valid_count": 0,
            "excluded_count": int(total_count),
            "start_date": None,
            "end_date": None,
            "calendar_span_days": 0,
            "active_date_count": 0,
            "recommended_granularity": "day",
            "selected_granularity": selected_granularity,
            "period_count": 0,
            "active_period_count": 0,
            "zero_period_count": 0,
            "peak_period": None,
            "peak_count": 0,
            "rows": [],
            "zero_ranges": [],
            "interpretation": "当前字段没有可用于时间分布分析的有效日期。",
        }

    start_day = valid_dates.min()
    end_day = valid_dates.max()
    calendar_span_days = int((end_day - start_day).days) + 1
    active_date_count = int(valid_dates.nunique())
    recommended_granularity = _recommend_time_granularity(
        start_day,
        end_day,
        calendar_span_days,
    )
    selected_granularity = granularity or recommended_granularity

    period_keys = valid_dates.map(
        lambda value: _time_period_start(value, selected_granularity)
    )
    period_counts = period_keys.value_counts(sort=False).sort_index()
    first_period_start = _time_period_start(
        start_day,
        selected_granularity,
    )
    last_period_start = _time_period_start(
        end_day,
        selected_granularity,
    )
    period_count = _time_period_count(
        first_period_start,
        last_period_start,
        selected_granularity,
    )
    active_period_count = int(len(period_counts))
    zero_period_count = int(period_count - active_period_count)
    peak_count = int(period_counts.max())
    peak_start = min(
        period_start
        for period_start, count in period_counts.items()
        if int(count) == peak_count
    )
    peak_period = _time_period_label(
        peak_start,
        _time_period_end(peak_start, selected_granularity),
        selected_granularity,
    )

    base_result = {
        "status": "ok",
        "field_name": str(field_name),
        "total_count": int(total_count),
        "valid_count": int(valid_count),
        "excluded_count": int(total_count - valid_count),
        "start_date": start_day.strftime("%Y-%m-%d"),
        "end_date": end_day.strftime("%Y-%m-%d"),
        "calendar_span_days": calendar_span_days,
        "active_date_count": active_date_count,
        "recommended_granularity": recommended_granularity,
        "selected_granularity": selected_granularity,
        "period_count": int(period_count),
        "active_period_count": active_period_count,
        "zero_period_count": zero_period_count,
        "peak_period": peak_period,
        "peak_count": peak_count,
        "rows": [],
        "zero_ranges": [],
        "interpretation": "",
    }

    if period_count > TIME_DISTRIBUTION_MAX_POINTS:
        base_result["status"] = "too_dense"
        base_result["interpretation"] = (
            f"当前数据覆盖 {base_result['start_date']} 至 "
            f"{base_result['end_date']}。"
            f"按{_TIME_GRANULARITY_LABELS[selected_granularity]}统计将生成 "
            f"{period_count:,} 个时间点，超过 "
            f"{TIME_DISTRIBUTION_MAX_POINTS} 个时间点。"
            "请选择更粗粒度后查看时间分布。"
        )
        return base_result

    rows = []
    for period_start in _time_period_starts(
        first_period_start,
        last_period_start,
        selected_granularity,
    ):
        period_end = _time_period_end(
            period_start,
            selected_granularity,
        )
        count = int(period_counts.get(period_start, 0))
        rows.append(
            {
                "period_start": period_start.strftime("%Y-%m-%d"),
                "period_end": period_end.strftime("%Y-%m-%d"),
                "period_label": _time_period_label(
                    period_start,
                    period_end,
                    selected_granularity,
                ),
                "count": count,
                "ratio": float(count / valid_count) if count else 0.0,
            }
        )

    zero_ranges = _build_zero_time_ranges(
        rows,
        selected_granularity,
    )
    base_result["rows"] = rows
    base_result["zero_ranges"] = zero_ranges
    if active_date_count == 1:
        base_result["status"] = "single_date"
    base_result["interpretation"] = generate_time_distribution_interpretation(
        base_result
    )
    return base_result


def generate_time_distribution_interpretation(analysis_result):
    """Generate a neutral interpretation of time coverage and record counts."""
    status = analysis_result.get("status")
    if status == "no_valid_dates":
        return "当前字段没有可用于时间分布分析的有效日期。"
    if status == "too_dense":
        return analysis_result.get("interpretation", "")
    if status == "single_date":
        return (
            f"当前有效日期记录均落在 {analysis_result['start_date']}，"
            f"共 {analysis_result['valid_count']:,} 条记录。"
        )

    granularity_label = _TIME_GRANULARITY_LABELS[
        analysis_result["selected_granularity"]
    ]
    descriptions = [
        (
            f"当前数据覆盖 {analysis_result['start_date']} 至 "
            f"{analysis_result['end_date']}。"
        ),
        (
            f"按{granularity_label}统计共包含 "
            f"{analysis_result['period_count']:,} 个时间段，"
            f"其中 {analysis_result['active_period_count']:,} 个时间段存在记录，"
            f"{analysis_result['zero_period_count']:,} 个时间段无记录。"
        ),
        (
            f"记录数最高的时间段为 {analysis_result['peak_period']}，"
            f"共 {analysis_result['peak_count']:,} 条记录。"
        ),
    ]
    zero_ranges = analysis_result.get("zero_ranges", [])
    if zero_ranges:
        longest_range = zero_ranges[0]
        descriptions.append(
            f"最长连续无记录时间段为 {longest_range['start_label']} 至 "
            f"{longest_range['end_label']}，"
            f"共 {longest_range['period_count']:,} 个时间段。"
        )
    if analysis_result.get("period_count") == 1:
        descriptions.append(
            "当前粒度下只有一个时间段，可选择更细粒度查看记录分布。"
        )
    descriptions.append(
        "无记录时间段不一定表示数据缺失，也可能是当时没有业务活动，"
        "请结合业务日历核验。"
    )
    return "".join(descriptions)


def parse_exploration_datetime_series(series):
    """Parse exploration dates without imposing one format on mixed strings."""
    source = series.copy(deep=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        if pd.api.types.is_datetime64_any_dtype(source.dtype):
            parsed = pd.to_datetime(
                source,
                errors="coerce",
            )
        elif pd.api.types.is_numeric_dtype(source.dtype):
            parsed = pd.Series(
                pd.NaT,
                index=source.index,
                name=source.name,
                dtype="datetime64[ns]",
            )
        else:
            try:
                parsed = pd.to_datetime(
                    source,
                    errors="coerce",
                    format="mixed",
                )
            except (TypeError, ValueError):
                parsed = source.map(
                    lambda value: pd.to_datetime(
                        value,
                        errors="coerce",
                    )
                )
    return pd.Series(
        parsed,
        index=series.index,
        name=series.name,
    )


def _clean_time_distribution_dates(series):
    parsed_series = parse_exploration_datetime_series(series)
    local_days = []
    for value in parsed_series.dropna().tolist():
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is not None:
            timestamp = timestamp.tz_localize(None)
        local_days.append(timestamp.normalize())
    return pd.Series(local_days, dtype="datetime64[ns]")


def _recommend_time_granularity(start_day, end_day, calendar_span_days):
    if calendar_span_days <= 90:
        return "day"
    if end_day <= start_day + pd.DateOffset(years=2):
        return "week"
    if end_day <= start_day + pd.DateOffset(years=8):
        return "month"
    return "year"


def _time_period_start(value, granularity):
    timestamp = pd.Timestamp(value).normalize()
    if granularity == "day":
        return timestamp
    if granularity == "week":
        return timestamp - pd.Timedelta(days=timestamp.weekday())
    if granularity == "month":
        return pd.Timestamp(timestamp.year, timestamp.month, 1)
    if granularity == "quarter":
        quarter_month = ((timestamp.month - 1) // 3) * 3 + 1
        return pd.Timestamp(timestamp.year, quarter_month, 1)
    return pd.Timestamp(timestamp.year, 1, 1)


def _time_period_end(period_start, granularity):
    if granularity == "day":
        return period_start
    if granularity == "week":
        return period_start + pd.Timedelta(days=6)
    if granularity == "month":
        return period_start + pd.offsets.MonthEnd(0)
    if granularity == "quarter":
        return period_start + pd.DateOffset(months=3) - pd.Timedelta(days=1)
    return pd.Timestamp(period_start.year, 12, 31)


def _time_period_label(period_start, period_end, granularity):
    if granularity == "day":
        return period_start.strftime("%Y-%m-%d")
    if granularity == "week":
        return (
            f"{period_start.strftime('%Y-%m-%d')} 至 "
            f"{period_end.strftime('%Y-%m-%d')}"
        )
    if granularity == "month":
        return period_start.strftime("%Y-%m")
    if granularity == "quarter":
        quarter = (period_start.month - 1) // 3 + 1
        return f"{period_start.year} Q{quarter}"
    return str(period_start.year)


def _time_period_count(first_period_start, last_period_start, granularity):
    if granularity == "day":
        return int((last_period_start - first_period_start).days) + 1
    if granularity == "week":
        return int((last_period_start - first_period_start).days // 7) + 1
    if granularity == "month":
        return (
            (last_period_start.year - first_period_start.year) * 12
            + last_period_start.month
            - first_period_start.month
            + 1
        )
    if granularity == "quarter":
        first_quarter = (first_period_start.month - 1) // 3
        last_quarter = (last_period_start.month - 1) // 3
        return (
            (last_period_start.year - first_period_start.year) * 4
            + last_quarter
            - first_quarter
            + 1
        )
    return last_period_start.year - first_period_start.year + 1


def _time_period_starts(first_period_start, last_period_start, granularity):
    frequency_by_granularity = {
        "day": "D",
        "week": "7D",
        "month": "MS",
        "quarter": "QS",
        "year": "YS",
    }
    return pd.date_range(
        first_period_start,
        last_period_start,
        freq=frequency_by_granularity[granularity],
    )


def _build_zero_time_ranges(rows, granularity):
    zero_segments = []
    segment_start = None
    for index, row in enumerate(rows):
        if row["count"] == 0 and segment_start is None:
            segment_start = index
        is_segment_end = (
            segment_start is not None
            and (
                row["count"] != 0
                or index == len(rows) - 1
            )
        )
        if not is_segment_end:
            continue

        segment_end = (
            index
            if row["count"] == 0
            else index - 1
        )
        start_row = rows[segment_start]
        end_row = rows[segment_end]
        zero_segments.append(
            {
                "start_label": start_row["period_label"],
                "end_label": end_row["period_label"],
                "start_date": start_row["period_start"],
                "end_date": end_row["period_end"],
                "period_count": segment_end - segment_start + 1,
                "granularity": granularity,
            }
        )
        segment_start = None

    zero_segments.sort(
        key=lambda item: (
            -item["period_count"],
            item["start_date"],
        )
    )
    return zero_segments[:10]


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


CORRELATION_METHODS = ("pearson", "spearman")
CORRELATION_MIN_SAMPLE_SIZE = 5
CORRELATION_NORMAL_SAMPLE_SIZE = 20
CORRELATION_COMPLETE_THRESHOLD = 0.9999
CORRELATION_HIGH_RELATIONSHIP_WARNING = (
    "高相关可能来自字段计算关系、共同趋势、样本结构或极端值，不代表因果关系。"
)
CORRELATION_COMPLETE_RELATIONSHIP_WARNING = (
    "字段对接近完全相关，可能存在重复字段、单位转换或直接计算关系，"
    "请检查字段定义。"
)


def describe_correlation_strength(value):
    """Return the display strength label for a correlation coefficient."""
    absolute_value = abs(float(value))
    if absolute_value < 0.3:
        return "关系较弱"
    if absolute_value < 0.5:
        return "存在一定关系"
    if absolute_value < 0.7:
        return "中等关系"
    return "较强关系"


def build_correlation_relationship_analysis(
    df,
    selected_columns,
    method="pearson",
    threshold=0.5,
):
    """Build JSON-safe pairwise correlation matrices and relationship rows."""
    normalized_method = _normalize_correlation_method(method)
    normalized_threshold = _normalize_correlation_threshold(threshold)
    selected = _unique_correlation_columns(selected_columns)
    valid_columns, excluded_columns, validation_warnings = (
        _validate_correlation_columns(df, selected)
    )

    correlation_rows = [
        [None for _ in valid_columns]
        for _ in valid_columns
    ]
    sample_size_rows = [
        [None for _ in valid_columns]
        for _ in valid_columns
    ]
    finite_by_column = {
        column: clean_finite_numeric_values(df[column])
        for column in valid_columns
    }
    for index, column in enumerate(valid_columns):
        correlation_rows[index][index] = 1.0
        sample_size_rows[index][index] = int(len(finite_by_column[column]))

    all_pairs = []
    warnings_list = list(validation_warnings)
    for index, field_a in enumerate(valid_columns):
        for field_b_index in range(index + 1, len(valid_columns)):
            field_b = valid_columns[field_b_index]
            pair_frame = _pairwise_finite_numeric_frame(
                df,
                field_a,
                field_b,
            )
            sample_size = int(len(pair_frame))
            sample_size_rows[index][field_b_index] = sample_size
            sample_size_rows[field_b_index][index] = sample_size
            if sample_size < CORRELATION_MIN_SAMPLE_SIZE:
                warnings_list.append(
                    f"{field_a} 与 {field_b} 的共同有效有限数值记录不足 "
                    f"{CORRELATION_MIN_SAMPLE_SIZE} 条，未计算相关系数。"
                )
                continue

            correlation = _calculate_pair_correlation(
                pair_frame,
                normalized_method,
            )
            if pd.isna(correlation) or not np.isfinite(correlation):
                warnings_list.append(
                    f"{field_a} 与 {field_b} 在共同有效样本中无法计算相关系数。"
                )
                continue

            correlation_value = max(
                -1.0,
                min(1.0, float(correlation)),
            )
            correlation_rows[index][field_b_index] = correlation_value
            correlation_rows[field_b_index][index] = correlation_value
            pair_warning = (
                CORRELATION_COMPLETE_RELATIONSHIP_WARNING
                if abs(correlation_value)
                >= CORRELATION_COMPLETE_THRESHOLD
                else None
            )
            all_pairs.append(
                {
                    "field_a": str(field_a),
                    "field_b": str(field_b),
                    "correlation": correlation_value,
                    "absolute_correlation": abs(correlation_value),
                    "direction": _correlation_direction(
                        correlation_value
                    ),
                    "strength": describe_correlation_strength(
                        correlation_value
                    ),
                    "sample_size": sample_size,
                    "sample_status": (
                        "样本较少"
                        if sample_size < CORRELATION_NORMAL_SAMPLE_SIZE
                        else "正常"
                    ),
                    "warning": pair_warning,
                }
            )

    all_pairs.sort(
        key=lambda item: (
            -item["absolute_correlation"],
            item["field_a"],
            item["field_b"],
        )
    )
    pairs = [
        dict(item)
        for item in all_pairs
        if item["absolute_correlation"] >= normalized_threshold
    ]
    if any(
        item["absolute_correlation"] >= 0.7
        for item in all_pairs
    ):
        warnings_list.append(CORRELATION_HIGH_RELATIONSHIP_WARNING)

    if len(selected) < 2 or len(valid_columns) < 2:
        status = "insufficient_columns"
    elif not all_pairs:
        status = "no_valid_pairs"
    else:
        status = "ok"
    result = {
        "status": status,
        "method": normalized_method,
        "threshold": normalized_threshold,
        "selected_columns": [str(column) for column in selected],
        "valid_columns": [str(column) for column in valid_columns],
        "excluded_columns": [str(column) for column in excluded_columns],
        "matrix": {
            "columns": [str(column) for column in valid_columns],
            "rows": correlation_rows,
        },
        "sample_size_matrix": {
            "columns": [str(column) for column in valid_columns],
            "rows": sample_size_rows,
        },
        "pairs": pairs,
        "all_pairs": [dict(item) for item in all_pairs],
        "warnings": warnings_list,
    }
    result["interpretation"] = (
        generate_correlation_relationship_interpretation(result)
    )
    return result


def generate_correlation_relationship_interpretation(analysis_result):
    """Generate a neutral, non-causal summary of displayed relationships."""
    threshold = float(analysis_result.get("threshold", 0.5))
    pairs = analysis_result.get("pairs", [])
    if not pairs:
        return (
            f"当前没有字段对达到 |r| ≥ {threshold:g} 的显示阈值。"
            "可以调低阈值查看较弱关系。"
        )

    descriptions = []
    for pair in pairs[:3]:
        strength = pair["strength"].replace("关系", "")
        direction = pair["direction"]
        if direction == "无明显方向":
            relationship = f"{pair['strength']}且无明显方向"
        else:
            relationship = f"{strength}{direction}关系"
        descriptions.append(
            f"{pair['field_a']}与{pair['field_b']}呈{relationship}"
            f"（r={pair['correlation']:.2f}，"
            f"N={pair['sample_size']:,}）"
        )
    return (
        "；".join(descriptions)
        + "。相关关系不代表因果，高相关也可能来自指标定义、"
        "共同时间趋势或样本结构。"
    )


def build_correlation_scatter_data(
    df,
    field_x,
    field_y,
    method="pearson",
    max_points=5000,
    random_state=42,
):
    """Build deterministic scatter rows while correlating all valid records."""
    normalized_method = _normalize_correlation_method(method)
    try:
        normalized_max_points = int(max_points)
    except (TypeError, ValueError) as exc:
        raise ValueError("max_points 必须是正整数。") from exc
    if normalized_max_points < 1:
        raise ValueError("max_points 必须是正整数。")

    base_result = {
        "status": "invalid_fields",
        "field_x": str(field_x),
        "field_y": str(field_y),
        "method": normalized_method,
        "correlation": None,
        "sample_size": 0,
        "displayed_point_count": 0,
        "is_sampled": False,
        "rows": [],
    }
    if (
        field_x == field_y
        or field_x not in df.columns
        or field_y not in df.columns
        or not _is_supported_correlation_numeric(df[field_x])
        or not _is_supported_correlation_numeric(df[field_y])
    ):
        return base_result

    pair_frame = _pairwise_finite_numeric_frame(
        df,
        field_x,
        field_y,
    )
    sample_size = int(len(pair_frame))
    base_result["sample_size"] = sample_size
    if sample_size < CORRELATION_MIN_SAMPLE_SIZE:
        base_result["status"] = "insufficient_data"
        return base_result

    correlation = _calculate_pair_correlation(
        pair_frame,
        normalized_method,
    )
    if pd.isna(correlation) or not np.isfinite(correlation):
        base_result["status"] = "insufficient_data"
        return base_result

    if sample_size > normalized_max_points:
        display_frame = pair_frame.sample(
            n=normalized_max_points,
            random_state=random_state,
        )
        is_sampled = True
    else:
        display_frame = pair_frame
        is_sampled = False
    rows = [
        {
            "x": float(field_x_value),
            "y": float(field_y_value),
        }
        for field_x_value, field_y_value in display_frame[
            ["_field_a", "_field_b"]
        ].itertuples(index=False, name=None)
    ]
    base_result.update(
        {
            "status": "ok",
            "correlation": max(
                -1.0,
                min(1.0, float(correlation)),
            ),
            "displayed_point_count": int(len(rows)),
            "is_sampled": is_sampled,
            "rows": rows,
        }
    )
    return base_result


def _normalize_correlation_method(method):
    normalized_method = str(method).lower()
    if normalized_method not in CORRELATION_METHODS:
        raise ValueError("method 仅支持 pearson 或 spearman。")
    return normalized_method


def _normalize_correlation_threshold(threshold):
    try:
        normalized_threshold = float(threshold)
    except (TypeError, ValueError) as exc:
        raise ValueError("threshold 必须在 0 到 1 之间。") from exc
    if (
        not np.isfinite(normalized_threshold)
        or not 0 <= normalized_threshold <= 1
    ):
        raise ValueError("threshold 必须在 0 到 1 之间。")
    return normalized_threshold


def _unique_correlation_columns(selected_columns):
    selected = []
    for column in selected_columns or []:
        if column not in selected:
            selected.append(column)
    return selected


def _validate_correlation_columns(df, selected_columns):
    valid_columns = []
    excluded_columns = []
    warnings_list = []
    for column in selected_columns:
        reason = None
        if column not in df.columns:
            reason = "字段不存在"
        elif not _is_supported_correlation_numeric(df[column]):
            reason = "不是数值字段"
        else:
            finite_values = clean_finite_numeric_values(df[column])
            if finite_values.empty:
                reason = "没有有效有限数值"
            elif finite_values.nunique(dropna=True) <= 1:
                reason = "字段为常量"
            elif len(finite_values) < CORRELATION_MIN_SAMPLE_SIZE:
                reason = (
                    f"有效有限数值不足 {CORRELATION_MIN_SAMPLE_SIZE} 条"
                )
        if reason is None:
            valid_columns.append(column)
        else:
            excluded_columns.append(column)
            warnings_list.append(f"{column}：{reason}，已排除。")
    return valid_columns, excluded_columns, warnings_list


def _is_supported_correlation_numeric(series):
    return (
        pd.api.types.is_numeric_dtype(series.dtype)
        and not pd.api.types.is_bool_dtype(series.dtype)
        and not pd.api.types.is_datetime64_any_dtype(series.dtype)
    )


def _pairwise_finite_numeric_frame(df, field_a, field_b):
    field_a_values = pd.to_numeric(
        df[field_a].copy(deep=True),
        errors="coerce",
    ).replace([np.inf, -np.inf], np.nan)
    field_b_values = pd.to_numeric(
        df[field_b].copy(deep=True),
        errors="coerce",
    ).replace([np.inf, -np.inf], np.nan)
    return pd.DataFrame(
        {
            "_field_a": field_a_values,
            "_field_b": field_b_values,
        },
        index=df.index,
    ).dropna()


def _calculate_pair_correlation(pair_frame, method):
    field_a_values = pair_frame["_field_a"]
    field_b_values = pair_frame["_field_b"]
    if method == "spearman":
        field_a_values = field_a_values.rank(method="average")
        field_b_values = field_b_values.rank(method="average")
    return field_a_values.corr(field_b_values, method="pearson")


def _correlation_direction(value):
    if value > 0:
        return "正向"
    if value < 0:
        return "负向"
    return "无明显方向"


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
