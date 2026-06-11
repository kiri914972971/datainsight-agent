import pandas as pd


def run_query(
    df: pd.DataFrame,
    date_column: str | None,
    value_column: str,
    category_column: str,
    aggregation: str,
    year: int | None,
    top_n: int,
) -> pd.DataFrame:
    temp = df.copy()
    if date_column and year is not None:
        dates = pd.to_datetime(temp[date_column], errors="coerce")
        temp = temp.loc[dates.dt.year == year]
    if aggregation == "count":
        result = temp.groupby(category_column, dropna=False).size().reset_index(name="count")
        return result.nlargest(top_n, "count")
    result = temp.groupby(category_column, dropna=False)[value_column].agg(aggregation).reset_index()
    return result.nlargest(top_n, value_column)

