import pandas as pd
import plotly.express as px


def histogram(df: pd.DataFrame, column: str):
    return px.histogram(df, x=column, marginal="box", title=f"{column} 分布")


def box_plot(df: pd.DataFrame, column: str):
    return px.box(df, y=column, points="outliers", title=f"{column} 箱型图")


def category_bar(df: pd.DataFrame, column: str, top_n: int):
    counts = df[column].astype(str).value_counts().head(top_n).reset_index()
    counts.columns = [column, "数量"]
    return px.bar(counts, x=column, y="数量", title=f"{column} Top {top_n}")


def trend_line(df: pd.DataFrame, date_column: str, value_column: str, aggregation: str = "sum"):
    temp = df[[date_column, value_column]].dropna().copy()
    temp[date_column] = pd.to_datetime(temp[date_column])
    grouped = temp.groupby(date_column, as_index=False)[value_column].agg(aggregation)
    return px.line(grouped, x=date_column, y=value_column, markers=True, title=f"{value_column} 随时间趋势")


def correlation_heatmap(df: pd.DataFrame, numeric_columns: list[str]):
    corr = df[numeric_columns].corr()
    return px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1, title="数值字段相关性")

