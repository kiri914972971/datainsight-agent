import numpy as np
import pandas as pd


def clean_data(df: pd.DataFrame, action: str, column: str | None = None, bins: int = 5) -> pd.DataFrame:
    result = df.copy()
    if action == "删除重复行":
        return result.drop_duplicates().reset_index(drop=True)
    if action == "删除含缺失值的行":
        return result.dropna().reset_index(drop=True)
    if column is None:
        raise ValueError("此操作需要选择字段。")
    if action == "均值填充":
        result[column] = result[column].fillna(result[column].mean())
    elif action == "中位数填充":
        result[column] = result[column].fillna(result[column].median())
    elif action == "众数填充":
        mode = result[column].mode(dropna=True)
        if not mode.empty:
            result[column] = result[column].fillna(mode.iloc[0])
    elif action == "log1p 处理":
        if (result[column].dropna() < -1).any():
            raise ValueError("log1p 仅适用于数值大于等于 -1 的字段。")
        result[f"{column}_log1p"] = np.log1p(result[column])
    elif action == "分箱处理":
        result[f"{column}_bin"] = pd.cut(result[column], bins=bins, duplicates="drop")
    return result


def comparison(before: pd.DataFrame, after: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "指标": ["行数", "列数", "缺失值总数", "重复行数"],
            "处理前": [len(before), len(before.columns), int(before.isna().sum().sum()), int(before.duplicated().sum())],
            "处理后": [len(after), len(after.columns), int(after.isna().sum().sum()), int(after.duplicated().sum())],
        }
    )

