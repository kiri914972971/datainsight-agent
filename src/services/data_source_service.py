from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Iterable

import pandas as pd

from src import project_workspace
from src.services.current_dataset_service import (
    list_project_datasets,
    set_current_analysis_dataset,
)


SUPPORTED_DATA_SUFFIXES = {".csv", ".xlsx", ".xls"}


def save_project_data_files(
    project_id: str,
    uploaded_files: Iterable[BinaryIO],
) -> list[dict]:
    project = project_workspace.get_project(project_id)
    data_path = project_workspace.get_project_path(project_id) / "data"
    data_path.mkdir(parents=True, exist_ok=True)
    data_files = list(project.get("data_files", []))
    saved = []

    for uploaded_file in uploaded_files:
        original_name = _safe_file_name(getattr(uploaded_file, "name", ""))
        suffix = Path(original_name).suffix.lower()
        if suffix not in SUPPORTED_DATA_SUFFIXES:
            raise ValueError(f"不支持的文件类型：{original_name}")

        file_name = _available_file_name(data_path, original_name)
        content = _uploaded_bytes(uploaded_file)
        file_path = data_path / file_name
        file_path.write_bytes(content)

        metadata = _build_file_metadata(
            file_path=file_path,
            file_id=uuid.uuid4().hex,
            uploaded_at=_utc_now(),
        )
        data_files.append(metadata)
        saved.append(metadata)

    if saved:
        project_workspace.update_project(project_id, {"data_files": data_files})
        list_project_datasets(project_id)
    return saved


def list_project_data_files(project_id: str) -> list[dict]:
    project = _sync_project_data_files(project_id)
    return sorted(
        project.get("data_files", []),
        key=lambda item: item.get("uploaded_at", ""),
        reverse=True,
    )


def load_project_data_file(
    project_id: str,
    file_id: str,
    sheet_name: str | None = None,
) -> pd.DataFrame:
    metadata = get_data_file_profile(project_id, file_id)
    file_path = _data_file_path(project_id, metadata)
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(file_path)
    if suffix in {".xlsx", ".xls"}:
        selected_sheet = sheet_name or _default_sheet_name(metadata)
        return pd.read_excel(file_path, sheet_name=selected_sheet)
    raise ValueError(f"不支持的文件类型：{suffix}")


def get_data_file_profile(project_id: str, file_id: str) -> dict:
    for metadata in list_project_data_files(project_id):
        if metadata["file_id"] == file_id:
            return metadata
    raise FileNotFoundError("项目数据文件不存在或已被删除。")


def delete_project_data_file(project_id: str, file_id: str) -> dict:
    project = project_workspace.get_project(project_id)
    data_files = list(project.get("data_files", []))
    metadata = next(
        (item for item in data_files if item.get("file_id") == file_id),
        None,
    )
    if metadata is None:
        raise FileNotFoundError("项目数据文件不存在或已被删除。")

    file_path = _data_file_path(project_id, metadata)
    if file_path.exists():
        file_path.unlink()

    current = project.get("current_analysis_dataset") or project.get("current_analysis_file")
    cleared_current = bool(current and current.get("file_id") == file_id)
    if not cleared_current and current:
        cleared_current = bool(
            current.get("dataset_id") == file_id
            or current.get("file_path") == metadata.get("file_path")
        )
    updates = {
        "data_files": [
            item for item in data_files if item.get("file_id") != file_id
        ],
        "project_datasets": [
            item
            for item in project.get("project_datasets", [])
            if item.get("source_file_id") != file_id
            and not str(item.get("dataset_id", "")).startswith(f"{file_id}::")
        ],
    }
    if cleared_current:
        updates["current_analysis_file"] = None
        updates["current_analysis_dataset"] = None
    project_workspace.update_project(project_id, updates)
    return {"file": metadata, "cleared_current_analysis": cleared_current}


def set_current_analysis_file(
    project_id: str,
    file_id: str,
    sheet_name: str | None = None,
) -> dict:
    metadata = get_data_file_profile(project_id, file_id)
    available_sheets = [
        item["sheet_name"] for item in metadata.get("sheets", [])
    ]
    selected_sheet = sheet_name or _default_sheet_name(metadata)
    if selected_sheet not in available_sheets:
        raise ValueError(f"Sheet 不存在：{selected_sheet}")

    sheet_profile = next(
        (item for item in metadata.get("sheets", []) if item["sheet_name"] == selected_sheet),
        {},
    )
    set_current_analysis_dataset(
        project_id,
        {
            "dataset_id": f"{file_id}::{selected_sheet}",
            "dataset_name": (
                f"{metadata['file_name']} / {selected_sheet}"
                if selected_sheet != "CSV"
                else metadata["file_name"]
            ),
            "dataset_type": "uploaded",
            "file_path": metadata["file_path"],
            "sheet_name": selected_sheet,
            "source": "upload",
            "created_at": metadata.get("uploaded_at", ""),
            "row_count": sheet_profile.get("rows"),
            "column_count": sheet_profile.get("columns"),
            "source_files": [],
            "source_file_id": file_id,
        },
    )
    return project_workspace.get_project(project_id)["current_analysis_file"]


def build_field_profile(dataframe: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "字段名": dataframe.columns.astype(str),
            "字段类型": [str(dtype) for dtype in dataframe.dtypes],
            "缺失值数量": dataframe.isna().sum().astype(int).values,
            "唯一值数量": dataframe.nunique(dropna=True).astype(int).values,
        }
    )


def _sync_project_data_files(project_id: str) -> dict:
    project = project_workspace.get_project(project_id)
    project_path = project_workspace.get_project_path(project_id)
    data_path = project_path / "data"
    data_path.mkdir(parents=True, exist_ok=True)
    metadata_by_path = {
        item.get("file_path"): item for item in project.get("data_files", [])
    }
    synced = []
    changed = False

    for file_path in sorted(data_path.iterdir()):
        if not file_path.is_file() or file_path.suffix.lower() not in SUPPORTED_DATA_SUFFIXES:
            continue
        relative_path = file_path.relative_to(project_path).as_posix()
        metadata = metadata_by_path.get(relative_path)
        if metadata is None:
            metadata = _build_file_metadata(
                file_path=file_path,
                file_id=uuid.uuid4().hex,
                uploaded_at=datetime.fromtimestamp(
                    file_path.stat().st_mtime,
                    tz=timezone.utc,
                ).isoformat(),
            )
            changed = True
        synced.append(metadata)

    if len(synced) != len(project.get("data_files", [])):
        changed = True
    current = project.get("current_analysis_dataset") or project.get("current_analysis_file")
    valid_file_ids = {item["file_id"] for item in synced}
    current_file_ref = (
        current.get("source_file_id")
        or current.get("file_id")
        or str(current.get("dataset_id", "")).split("::", 1)[0]
        if current
        else None
    )
    clear_current = bool(
        current
        and current.get("source_type") != "appended_dataset"
        and (
            current.get("dataset_type") == "uploaded"
            or not current.get("dataset_type")
        )
        and current_file_ref not in valid_file_ids
    )
    if changed or clear_current:
        updates = {"data_files": synced}
        if clear_current:
            updates["current_analysis_file"] = None
            updates["current_analysis_dataset"] = None
        project = project_workspace.update_project(
            project_id,
            updates,
        )
    return project


def _build_file_metadata(
    file_path: Path,
    file_id: str,
    uploaded_at: str,
) -> dict:
    suffix = file_path.suffix.lower()
    profile_error = None
    try:
        sheets = _profile_file_sheets(file_path)
    except Exception as exc:
        sheets = []
        profile_error = str(exc)
    metadata = {
        "file_id": file_id,
        "file_name": file_path.name,
        "file_path": f"data/{file_path.name}",
        "file_type": suffix.removeprefix("."),
        "file_size": file_path.stat().st_size,
        "uploaded_at": uploaded_at,
        "sheets": sheets,
    }
    if profile_error:
        metadata["profile_error"] = profile_error
    return metadata


def _profile_file_sheets(file_path: Path) -> list[dict]:
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        dataframe = _read_csv(file_path)
        return [
            {
                "sheet_name": "CSV",
                "rows": len(dataframe),
                "columns": len(dataframe.columns),
            }
        ]

    sheets = []
    with pd.ExcelFile(file_path) as excel_file:
        for sheet_name in excel_file.sheet_names:
            dataframe = pd.read_excel(excel_file, sheet_name=sheet_name)
            sheets.append(
                {
                    "sheet_name": sheet_name,
                    "rows": len(dataframe),
                    "columns": len(dataframe.columns),
                }
            )
    return sheets


def _read_csv(file_path: Path) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "latin1"):
        try:
            return pd.read_csv(file_path, encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("无法识别 CSV 文件编码。")


def _default_sheet_name(metadata: dict) -> str:
    sheets = metadata.get("sheets", [])
    if not sheets:
        raise ValueError("文件没有可读取的数据表。")
    return sheets[0]["sheet_name"]


def _available_file_name(data_path: Path, original_name: str) -> str:
    candidate = original_name
    stem = Path(original_name).stem
    suffix = Path(original_name).suffix
    counter = 2
    while (data_path / candidate).exists():
        candidate = f"{stem} ({counter}){suffix}"
        counter += 1
    return candidate


def _data_file_path(project_id: str, metadata: dict) -> Path:
    data_path = (project_workspace.get_project_path(project_id) / "data").resolve()
    file_path = (
        project_workspace.get_project_path(project_id) / metadata["file_path"]
    ).resolve()
    if file_path.parent != data_path:
        raise ValueError("项目数据文件路径无效。")
    return file_path


def _safe_file_name(file_name: str) -> str:
    safe_name = Path(file_name).name.strip()
    if not safe_name or safe_name in {".", ".."}:
        raise ValueError("文件名无效。")
    return safe_name


def _uploaded_bytes(uploaded_file: BinaryIO) -> bytes:
    if hasattr(uploaded_file, "getvalue"):
        return uploaded_file.getvalue()
    uploaded_file.seek(0)
    return uploaded_file.read()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
