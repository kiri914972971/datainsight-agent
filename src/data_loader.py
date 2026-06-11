from pathlib import Path

import pandas as pd


def load_data(uploaded_file) -> pd.DataFrame:
    """Read a Streamlit uploaded CSV or Excel file."""
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix == ".csv":
        for encoding in ("utf-8-sig", "utf-8", "gb18030", "latin1"):
            try:
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file, encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("无法识别 CSV 文件编码。")
    if suffix in {".xlsx", ".xls"}:
        uploaded_file.seek(0)
        return pd.read_excel(uploaded_file)
    raise ValueError("仅支持 CSV、XLSX 和 XLS 文件。")


def basic_info(df: pd.DataFrame) -> dict:
    return {
        "rows": len(df),
        "columns": len(df.columns),
        "duplicate_rows": int(df.duplicated().sum()),
        "memory_mb": round(df.memory_usage(deep=True).sum() / 1024**2, 2),
    }

