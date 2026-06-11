from io import BytesIO
from xml.etree import ElementTree as ET

import pandas as pd


EXPORT_OPTIONS = {
    "CSV": ("csv", "text/csv"),
    "XLSX": ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "XLS": ("xls", "application/vnd.ms-excel"),
}


def export_dataframe(df: pd.DataFrame, file_format: str) -> bytes:
    if file_format == "CSV":
        return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    if file_format == "XLSX":
        buffer = BytesIO()
        _excel_safe_dataframe(df).to_excel(buffer, index=False, engine="openpyxl")
        return buffer.getvalue()
    if file_format == "XLS":
        return _export_xls(df)
    raise ValueError(f"不支持的导出格式：{file_format}")


def _export_xls(df: pd.DataFrame) -> bytes:
    try:
        import xlwt
    except ImportError:
        return _export_spreadsheetml(df)

    if len(df) > 65_535:
        raise ValueError("XLS 格式最多支持 65,535 行数据，请改用 XLSX 或 CSV。")
    if len(df.columns) > 256:
        raise ValueError("XLS 格式最多支持 256 列，请改用 XLSX 或 CSV。")

    workbook = xlwt.Workbook(encoding="utf-8")
    worksheet = workbook.add_sheet("处理后数据")
    date_style = xlwt.easyxf(num_format_str="YYYY-MM-DD HH:MM:SS")

    for column_index, column in enumerate(df.columns):
        worksheet.write(0, column_index, str(column))

    for row_index, row in enumerate(df.itertuples(index=False, name=None), start=1):
        for column_index, value in enumerate(row):
            if _is_missing(value):
                worksheet.write(row_index, column_index, "")
            elif isinstance(value, pd.Timestamp):
                worksheet.write(row_index, column_index, value.to_pydatetime(), date_style)
            elif hasattr(value, "item"):
                worksheet.write(row_index, column_index, value.item())
            elif isinstance(value, (str, int, float, bool)):
                worksheet.write(row_index, column_index, value)
            else:
                worksheet.write(row_index, column_index, str(value))

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _is_missing(value) -> bool:
    if value is None:
        return True
    try:
        result = pd.isna(value)
        return bool(result) if type(result).__name__ in {"bool", "bool_"} else False
    except (TypeError, ValueError):
        return False


def _excel_safe_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for column in result.select_dtypes(include=["object", "category"]).columns:
        result[column] = result[column].map(
            lambda value: None
            if _is_missing(value)
            else value
            if isinstance(value, (str, int, float, bool))
            else str(value)
        )
    return result


def _export_spreadsheetml(df: pd.DataFrame) -> bytes:
    workbook_ns = "urn:schemas-microsoft-com:office:spreadsheet"
    office_ns = "urn:schemas-microsoft-com:office:office"
    excel_ns = "urn:schemas-microsoft-com:office:excel"
    ET.register_namespace("", workbook_ns)
    ET.register_namespace("o", office_ns)
    ET.register_namespace("x", excel_ns)
    ET.register_namespace("ss", workbook_ns)

    workbook = ET.Element(f"{{{workbook_ns}}}Workbook")
    worksheet = ET.SubElement(workbook, f"{{{workbook_ns}}}Worksheet", {f"{{{workbook_ns}}}Name": "处理后数据"})
    table = ET.SubElement(worksheet, f"{{{workbook_ns}}}Table")

    header = ET.SubElement(table, f"{{{workbook_ns}}}Row")
    for column in df.columns:
        _xml_cell(header, str(column), "String", workbook_ns)

    for row in df.itertuples(index=False, name=None):
        xml_row = ET.SubElement(table, f"{{{workbook_ns}}}Row")
        for value in row:
            if _is_missing(value):
                _xml_cell(xml_row, "", "String", workbook_ns)
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                _xml_cell(xml_row, str(value), "Number", workbook_ns)
            else:
                _xml_cell(xml_row, str(value), "String", workbook_ns)

    return ET.tostring(workbook, encoding="utf-8", xml_declaration=True)


def _xml_cell(row, value: str, value_type: str, namespace: str) -> None:
    cell = ET.SubElement(row, f"{{{namespace}}}Cell")
    data = ET.SubElement(cell, f"{{{namespace}}}Data", {f"{{{namespace}}}Type": value_type})
    data.text = value
