from __future__ import annotations

from typing import Any

import pandas as pd


FIELD_TYPES = (
    "日期字段",
    "金额字段",
    "数量字段",
    "ID字段",
    "产品字段",
    "区域字段",
    "人员字段",
    "类别字段",
    "其他字段",
    "忽略字段",
)

DATE_HINTS = (
    "date",
    "time",
    "日期",
    "时间",
    "成交日期",
    "订单日期",
    "创建时间",
    "支付时间",
)
AMOUNT_HINTS = (
    "amount",
    "gmv",
    "revenue",
    "sales",
    "price",
    "fee",
    "cost",
    "金额",
    "销售额",
    "成交金额",
    "实付金额",
    "客单价",
    "价格",
    "费用",
    "成本",
)
QUANTITY_HINTS = (
    "count",
    "qty",
    "quantity",
    "num",
    "数量",
    "人数",
    "客户数",
    "订单数",
    "成交客户数",
)
ID_HINTS = (
    "id",
    "编号",
    "工号",
    "订单号",
    "用户号",
    "客户号",
    "商品号",
)
PRODUCT_HINTS = ("product", "sku", "商品", "产品", "品类", "类别")
REGION_HINTS = (
    "region",
    "province",
    "city",
    "area",
    "地区",
    "区域",
    "省份",
    "城市",
)
PERSON_HINTS = (
    "sales",
    "staff",
    "employee",
    "person",
    "销售",
    "员工",
    "人员",
    "顾问",
)


def infer_field_mappings(
    df: pd.DataFrame,
    existing_mappings: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    existing_by_column = {
        item.get("column_name"): item
        for item in (existing_mappings or [])
        if item.get("column_name")
    }
    mappings = []
    for column in df.columns:
        inferred_type, confidence, reason = _infer_field(df, column)
        existing = existing_by_column.get(column)
        confirmed_type = (
            existing.get("confirmed_type")
            if existing and existing.get("confirmed_type") in FIELD_TYPES
            else inferred_type
        )
        mappings.append(
            {
                "column_name": column,
                "pandas_dtype": str(df[column].dtype),
                "inferred_type": inferred_type,
                "confidence": confidence,
                "reason": reason,
                "confirmed_type": confirmed_type,
            }
        )
    return mappings


def _infer_field(df: pd.DataFrame, column: Any) -> tuple[str, float, str]:
    series = df[column]
    name = str(column).strip().lower()
    is_numeric = pd.api.types.is_numeric_dtype(series)
    is_datetime = pd.api.types.is_datetime64_any_dtype(series)

    if is_datetime:
        return "日期字段", 0.99, "pandas 数据类型为日期时间"
    if _contains_hint(name, DATE_HINTS):
        return "日期字段", 0.95, "字段名包含日期或时间关键词"
    parse_ratio = _date_parse_ratio(series)
    if parse_ratio >= 0.8:
        return "日期字段", 0.85, f"{parse_ratio:.0%} 的非空值可解析为日期"

    if is_numeric and _contains_hint(name, AMOUNT_HINTS):
        return "金额字段", 0.95, "数值字段名包含金额、价格或收入关键词"
    if is_numeric and _contains_hint(name, QUANTITY_HINTS):
        return "数量字段", 0.95, "数值字段名包含数量或计数关键词"

    if _contains_hint(name, ID_HINTS):
        return "ID字段", 0.97, "字段名包含 ID、编号、工号或业务单号关键词"
    if _contains_hint(name, REGION_HINTS):
        return "区域字段", 0.95, "字段名包含地区、区域、省份或城市关键词"
    if _contains_hint(name, PRODUCT_HINTS):
        return "产品字段", 0.93, "字段名包含产品、商品、SKU 或品类关键词"
    if _contains_hint(name, PERSON_HINTS):
        return "人员字段", 0.92, "字段名包含销售、员工或人员关键词"

    non_null_count = int(series.notna().sum())
    unique_ratio = (
        series.nunique(dropna=True) / non_null_count
        if non_null_count
        else 0
    )
    if unique_ratio > 0.8 and _looks_like_identifier(series, is_numeric):
        return "ID字段", 0.82, f"唯一值比例为 {unique_ratio:.1%}，取值形态类似记录标识"

    if _is_categorical(series):
        return "类别字段", 0.75, "字段为类别、布尔或低基数字段"
    return "其他字段", 0.55, "未匹配到明确业务字段规则"


def _contains_hint(name: str, hints: tuple[str, ...]) -> bool:
    return any(hint in name for hint in hints)


def _date_parse_ratio(series: pd.Series) -> float:
    if pd.api.types.is_numeric_dtype(series):
        return 0.0
    values = series.dropna()
    if values.empty:
        return 0.0
    sample = values.astype(str).head(200)
    parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
    return float(parsed.notna().mean())


def _looks_like_identifier(series: pd.Series, is_numeric: bool) -> bool:
    if not is_numeric:
        return True
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    return bool(not numeric.empty and (numeric % 1 == 0).all())


def _is_categorical(series: pd.Series) -> bool:
    if (
        isinstance(series.dtype, pd.CategoricalDtype)
        or pd.api.types.is_object_dtype(series)
        or pd.api.types.is_string_dtype(series)
        or pd.api.types.is_bool_dtype(series)
    ):
        return True
    non_null_count = int(series.notna().sum())
    if not non_null_count:
        return False
    return series.nunique(dropna=True) <= min(20, max(5, int(non_null_count * 0.1)))
