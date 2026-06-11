import json
import re

import pandas as pd

from src.eda_ai_complete import _extract_text, _request_completion


DATE_NAME_PRIORITY = (
    "成交日期",
    "订单日期",
    "创建时间",
    "支付时间",
    "日期",
    "时间",
    "date",
    "time",
)
AMOUNT_HINTS = ("成交金额", "销售金额", "订单金额", "金额", "销售额", "收入", "revenue", "amount", "sales")
ORDER_HINTS = ("订单号", "订单id", "order_id", "流水号")
CUSTOMER_ID_HINTS = ("客户id", "客户号", "用户id", "用户号", "customer_id", "user_id")
CUSTOMER_COUNT_HINTS = ("成交客户数", "客户数", "人数", "customers", "customer_count")
UNIT_PRICE_HINTS = ("客单价", "单价", "unit_price", "average_order_value")
PRODUCT_HINTS = ("产品", "商品", "品类", "product")
REGION_HINTS = ("区域", "地区", "省份", "城市", "region", "province", "city")
PERSON_HINTS = ("销售工号", "销售人员", "员工", "人员", "业务员", "employee", "salesperson")

PERIOD_RULES = {
    "日报": "D",
    "周报": "W",
    "月报": "M",
    "季报": "Q",
    "年报": "Y",
}


def find_preferred_date_column(df: pd.DataFrame, date_columns: list[str]) -> str | None:
    available = [column for column in date_columns if column in df.columns]
    for hint in DATE_NAME_PRIORITY:
        for column in available:
            if hint in str(column).lower():
                return column
    return available[0] if available else None


def identify_business_fields(
    df: pd.DataFrame,
    date_columns: list[str],
    categorical_columns: list[str],
    numeric_columns: list[str],
    identifier_columns: list[str],
) -> dict:
    return {
        "date_column": find_preferred_date_column(df, date_columns),
        "amount_column": _find_column(numeric_columns, AMOUNT_HINTS),
        "order_id_column": _find_column(df.columns, ORDER_HINTS),
        "customer_id_column": _find_column(df.columns, CUSTOMER_ID_HINTS),
        "customer_count_column": _find_column(numeric_columns, CUSTOMER_COUNT_HINTS),
        "unit_price_column": _find_column(numeric_columns, UNIT_PRICE_HINTS),
        "dimensions": list(
            dict.fromkeys(
                [
                    column
                    for column in categorical_columns
                    if column in df.columns
                    and column not in date_columns
                    and column not in identifier_columns
                ]
                + [
                    column
                    for column in identifier_columns
                    if column in df.columns
                    and column not in date_columns
                    and any(hint in str(column).lower() for hint in PERSON_HINTS)
                ]
            )
        ),
        "numeric_metrics": [
            column
            for column in numeric_columns
            if column not in identifier_columns and column not in date_columns
        ],
    }


def business_metric_options(fields: dict) -> list[str]:
    options = []
    if fields.get("amount_column"):
        options.append("成交金额")
    options.append("订单数")
    if fields.get("customer_id_column") or fields.get("customer_count_column"):
        options.append("客户数")
    if fields.get("unit_price_column") or fields.get("amount_column"):
        options.append("客单价")
    for column in fields.get("numeric_metrics", []):
        if column not in options and column not in {
            fields.get("amount_column"),
            fields.get("customer_count_column"),
            fields.get("unit_price_column"),
        }:
            options.append(column)
    return options


def calculate_kpi(df: pd.DataFrame, fields: dict) -> dict:
    amount_column = fields.get("amount_column")
    order_column = fields.get("order_id_column")
    customer_id_column = fields.get("customer_id_column")
    customer_count_column = fields.get("customer_count_column")
    unit_price_column = fields.get("unit_price_column")

    amount = _numeric_sum(df, amount_column)
    orders = int(df[order_column].nunique(dropna=True)) if order_column else len(df)
    if customer_id_column:
        customers = int(df[customer_id_column].nunique(dropna=True))
    elif customer_count_column:
        customers = _numeric_sum(df, customer_count_column)
    else:
        customers = None
    if unit_price_column:
        unit_price = _numeric_mean(df, unit_price_column)
    elif amount_column:
        unit_price = amount / orders if orders else 0
    else:
        unit_price = None
    return {
        "成交金额": amount if amount_column else None,
        "订单数": orders,
        "客户数": customers,
        "客单价": unit_price,
    }


def calculate_mom(current: float | int | None, previous: float | int | None) -> float | None:
    return _calculate_growth(current, previous)


def calculate_yoy(current: float | int | None, previous_year: float | int | None) -> float | None:
    return _calculate_growth(current, previous_year)


def generate_dashboard(
    df: pd.DataFrame,
    date_column: str,
    period: str,
    fields: dict,
    comparison_df: pd.DataFrame | None = None,
) -> dict:
    temp = df.copy()
    temp[date_column] = pd.to_datetime(temp[date_column], errors="coerce")
    temp = temp.dropna(subset=[date_column])
    if temp.empty:
        return {"current_period": None, "kpi": calculate_kpi(temp, fields), "trend": pd.DataFrame()}

    frequency = PERIOD_RULES[period]
    temp["_period"] = temp[date_column].dt.to_period(frequency)
    periods = sorted(temp["_period"].unique())
    current_period = periods[-1]
    previous_period = current_period - 1
    previous_year_period = current_period - _periods_per_year(period)

    history = comparison_df.copy() if comparison_df is not None else df.copy()
    history[date_column] = pd.to_datetime(history[date_column], errors="coerce")
    history = history.dropna(subset=[date_column])
    history["_period"] = history[date_column].dt.to_period(frequency)
    current = history.loc[history["_period"] == current_period].drop(columns="_period")
    previous = history.loc[history["_period"] == previous_period].drop(columns="_period")
    previous_year = history.loc[history["_period"] == previous_year_period].drop(columns="_period")
    current_kpi = calculate_kpi(current, fields)
    previous_kpi = calculate_kpi(previous, fields) if not previous.empty else {}
    previous_year_kpi = calculate_kpi(previous_year, fields) if not previous_year.empty else {}

    trend_rows = []
    for period_value, group in temp.groupby("_period"):
        row = {"周期": str(period_value), **calculate_kpi(group.drop(columns="_period"), fields)}
        trend_rows.append(row)
    trend = pd.DataFrame(trend_rows).sort_values("周期")
    return {
        "current_period": str(current_period),
        "current_df": current,
        "kpi": current_kpi,
        "mom": {key: calculate_mom(value, previous_kpi.get(key)) for key, value in current_kpi.items()},
        "yoy": {key: calculate_yoy(value, previous_year_kpi.get(key)) for key, value in current_kpi.items()},
        "trend": trend,
    }


def filter_time_slice(
    df: pd.DataFrame,
    date_column: str,
    year: int | None = None,
    quarter: int | None = None,
    month: int | None = None,
) -> pd.DataFrame:
    dates = pd.to_datetime(df[date_column], errors="coerce")
    mask = dates.notna()
    if year is not None:
        mask &= dates.dt.year == year
    if quarter is not None:
        mask &= dates.dt.quarter == quarter
    if month is not None:
        mask &= dates.dt.month == month
    return df.loc[mask].copy()


def generate_dimension_analysis(
    df: pd.DataFrame,
    dimension: str,
    metric: str,
    fields: dict,
) -> pd.DataFrame:
    if dimension not in df.columns:
        raise KeyError(f"分析维度不存在：{dimension}")
    grouped = []
    for value, group in df.groupby(dimension, dropna=False):
        grouped.append({dimension: value, metric: calculate_business_metric(group, metric, fields)})
    return pd.DataFrame(grouped).sort_values(metric, ascending=False, ignore_index=True)


def generate_top_n(
    df: pd.DataFrame,
    dimension: str,
    metric: str,
    fields: dict,
    top_n: int = 10,
) -> pd.DataFrame:
    result = generate_dimension_analysis(df, dimension, metric, fields).head(top_n).copy()
    result.insert(0, "排名", range(1, len(result) + 1))
    return result


def generate_share_analysis(
    df: pd.DataFrame,
    dimension: str,
    metric: str,
    fields: dict,
) -> pd.DataFrame:
    result = generate_dimension_analysis(df, dimension, metric, fields)
    total = result[metric].sum()
    result["占比"] = result[metric] / total * 100 if total else 0
    return result


def generate_dimension_trend(
    df: pd.DataFrame,
    date_column: str,
    dimension: str,
    metric: str,
    fields: dict,
    period: str = "月报",
    top_n: int = 5,
) -> pd.DataFrame:
    top_values = generate_top_n(df, dimension, metric, fields, top_n)[dimension].tolist()
    temp = df.loc[df[dimension].isin(top_values)].copy()
    temp[date_column] = pd.to_datetime(temp[date_column], errors="coerce")
    temp = temp.dropna(subset=[date_column])
    temp["周期"] = temp[date_column].dt.to_period(PERIOD_RULES[period]).astype(str)
    rows = []
    for (period_value, dimension_value), group in temp.groupby(["周期", dimension], dropna=False):
        rows.append(
            {
                "周期": period_value,
                dimension: dimension_value,
                metric: calculate_business_metric(group, metric, fields),
            }
        )
    return pd.DataFrame(rows)


def parse_business_question(
    question: str,
    dimensions: list[str],
    metrics: list[str],
    api_key: str | None = None,
    model: str = "gpt-5.4-mini",
    base_url: str = "https://api.openai.com/v1",
) -> dict:
    if api_key:
        try:
            return _parse_business_question_ai(question, dimensions, metrics, api_key, model, base_url)
        except Exception:
            pass
    return _parse_business_question_rules(question, dimensions, metrics)


def execute_business_query(df: pd.DataFrame, query: dict, fields: dict) -> pd.DataFrame:
    dimension = query.get("dimension")
    metric = query.get("metric")
    limit = int(query.get("limit") or 5)
    if dimension not in fields.get("dimensions", []):
        raise ValueError("未识别到可执行的业务分析维度。")
    if metric not in business_metric_options(fields):
        raise ValueError("未识别到可执行的业务指标。")
    filtered = _apply_query_filters(df, query.get("filters") or [], fields.get("date_column"))
    if query.get("intent") == "growth_ranking":
        date_column = fields.get("date_column")
        if not date_column:
            raise ValueError("未检测到时间字段，无法计算增长排名。")
        trend = generate_dimension_trend(
            filtered,
            date_column,
            dimension,
            metric,
            fields,
            period="月报",
            top_n=50,
        )
        if trend.empty or trend["周期"].nunique() < 2:
            raise ValueError("当前数据不足以计算维度增长排名。")
        pivot = trend.pivot(index=dimension, columns="周期", values=metric).sort_index(axis=1)
        growth = pd.DataFrame(
            {
                dimension: pivot.index,
                "起始值": pivot.iloc[:, 0].values,
                "最新值": pivot.iloc[:, -1].values,
            }
        )
        growth["增长率"] = (growth["最新值"] - growth["起始值"]) / growth["起始值"].abs().replace(0, pd.NA) * 100
        growth = growth.dropna(subset=["增长率"]).sort_values("增长率", ascending=False).head(limit).reset_index(drop=True)
        growth.insert(0, "排名", range(1, len(growth) + 1))
        return growth
    return generate_top_n(filtered, dimension, metric, fields, limit)


def generate_business_explanation(result: pd.DataFrame, dimension: str, metric: str) -> str:
    if result.empty:
        return "当前条件下没有可用于解释的业务结果。"
    result_metric = "增长率" if "增长率" in result.columns else metric
    first = result.iloc[0]
    if len(result) > 1 and result.iloc[1][result_metric] not in (0, None):
        lead = (first[result_metric] - result.iloc[1][result_metric]) / abs(result.iloc[1][result_metric]) * 100
        return (
            f"{dimension}“{first[dimension]}”的{result_metric}排名第一，"
            f"比第二名高 {lead:.1f}%。建议进一步分析其客户来源、产品结构和成交模式。"
        )
    return f"{dimension}“{first[dimension]}”的{result_metric}排名第一，建议进一步分析其业务构成。"


def request_management_summary(
    payload: dict,
    api_key: str,
    model: str,
    base_url: str,
) -> str:
    prompt = f"""
你是一名管理层经营分析顾问。请根据下面的周期报表数据，用简体中文输出管理层摘要。

只使用以下三个标题：
本期亮点
风险
建议

要求：
- 聚焦 KPI、同比、环比、趋势、Top 区域、Top 产品和 Top 人员。
- 不讨论均值、标准差、偏度、峰度、IQR、缺失值或异常值。
- 不把共同变化直接解释为因果。
- 每部分最多 4 点，内容简洁并完整结束。

周期报表数据：
{json.dumps(payload, ensure_ascii=False, default=str)}
""".strip()
    return _extract_text(_request_completion(prompt, api_key, model, base_url, timeout=90))


def calculate_business_metric(df: pd.DataFrame, metric: str, fields: dict) -> float | int:
    if metric == "成交金额":
        return _numeric_sum(df, fields.get("amount_column"))
    if metric == "订单数":
        order_column = fields.get("order_id_column")
        return int(df[order_column].nunique(dropna=True)) if order_column else len(df)
    if metric == "客户数":
        customer_id = fields.get("customer_id_column")
        if customer_id:
            return int(df[customer_id].nunique(dropna=True))
        return _numeric_sum(df, fields.get("customer_count_column"))
    if metric == "客单价":
        unit_price = fields.get("unit_price_column")
        if unit_price:
            return _numeric_mean(df, unit_price)
        amount = _numeric_sum(df, fields.get("amount_column"))
        orders = calculate_business_metric(df, "订单数", fields)
        return amount / orders if orders else 0
    return _numeric_sum(df, metric)


def _parse_business_question_rules(question: str, dimensions: list[str], metrics: list[str]) -> dict:
    normalized = question.strip().lower()
    dimension = next((column for column in dimensions if str(column).lower() in normalized), None)
    if dimension is None:
        dimension = _find_dimension_by_concept(normalized, dimensions)
    metric = next((value for value in metrics if str(value).lower() in normalized), None)
    if metric is None:
        metric = next((value for value in ("成交金额", "客户数", "订单数", "客单价") if value in normalized), None)
    limit_match = re.search(r"(?:top\s*|前|最高的?|排名前)\s*(\d+)", normalized)
    limit = int(limit_match.group(1)) if limit_match else 5
    recent_months = re.search(r"近\s*(\d+)\s*个?月", normalized)
    filters = [{"type": "recent_months", "value": int(recent_months.group(1))}] if recent_months else []
    return {
        "intent": "growth_ranking" if "增长最快" in normalized or "增长最高" in normalized else "ranking",
        "dimension": dimension or (dimensions[0] if dimensions else ""),
        "metric": metric or (metrics[0] if metrics else ""),
        "aggregation": "sum",
        "limit": limit,
        "filters": filters,
    }


def _parse_business_question_ai(
    question: str,
    dimensions: list[str],
    metrics: list[str],
    api_key: str,
    model: str,
    base_url: str,
) -> dict:
    prompt = f"""
将业务问题解析为 JSON，不要生成 Python 代码，不要输出 JSON 以外的内容。

允许的维度：{json.dumps(dimensions, ensure_ascii=False)}
允许的指标：{json.dumps(metrics, ensure_ascii=False)}

JSON 格式：
{{"intent":"ranking","dimension":"","metric":"","aggregation":"sum","limit":5,"filters":[]}}

业务问题：{question}
""".strip()
    text = _extract_text(_request_completion(prompt, api_key, model, base_url, timeout=45))
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise ValueError("AI 未返回结构化查询。")
    query = json.loads(match.group(0))
    if query.get("dimension") not in dimensions or query.get("metric") not in metrics:
        raise ValueError("AI 返回了未允许的维度或指标。")
    return {
        "intent": str(query.get("intent") or "ranking"),
        "dimension": query["dimension"],
        "metric": query["metric"],
        "aggregation": str(query.get("aggregation") or "sum"),
        "limit": max(1, min(50, int(query.get("limit") or 5))),
        "filters": query.get("filters") if isinstance(query.get("filters"), list) else [],
    }


def _find_column(columns, hints: tuple[str, ...]) -> str | None:
    return next((column for column in columns if any(hint in str(column).lower() for hint in hints)), None)


def _find_dimension_by_concept(question: str, columns: list[str]) -> str | None:
    for hints in (REGION_HINTS, PRODUCT_HINTS, PERSON_HINTS):
        if any(hint in question for hint in hints):
            return next(
                (column for column in columns if any(hint in str(column).lower() for hint in hints)),
                None,
            )
    return None


def _apply_query_filters(df: pd.DataFrame, filters: list[dict], date_column: str | None) -> pd.DataFrame:
    result = df.copy()
    for query_filter in filters:
        if query_filter.get("type") == "recent_months" and date_column:
            dates = pd.to_datetime(result[date_column], errors="coerce")
            latest = dates.max()
            if pd.notna(latest):
                start = latest - pd.DateOffset(months=max(1, int(query_filter.get("value") or 1)) - 1)
                result = result.loc[dates >= start]
    return result


def _numeric_sum(df: pd.DataFrame, column: str | None) -> float:
    return float(pd.to_numeric(df[column], errors="coerce").sum()) if column and column in df.columns else 0.0


def _numeric_mean(df: pd.DataFrame, column: str | None) -> float:
    return float(pd.to_numeric(df[column], errors="coerce").mean()) if column and column in df.columns else 0.0


def _calculate_growth(current: float | int | None, previous: float | int | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return (float(current) - float(previous)) / abs(float(previous)) * 100


def _periods_per_year(period: str) -> int:
    return {"日报": 365, "周报": 52, "月报": 12, "季报": 4, "年报": 1}[period]
