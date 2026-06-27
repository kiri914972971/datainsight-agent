from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src import project_workspace


CURRENT_DATASET_KEY = "current_analysis_dataset"
PROJECT_DATASETS_KEY = "project_datasets"
NO_CURRENT_ANALYSIS_DATASET_MESSAGE = (
    "请先在「项目数据 / 数据源」中选择一个数据集，并设置为当前分析数据集。"
)
CURRENT_ANALYSIS_DATASET_MISSING_FILE_MESSAGE = (
    "当前分析数据集文件不存在，请重新选择或重新生成。"
)


DATASET_TYPE_LABELS = {
    "uploaded": "原始上传",
    "appended": "合并结果",
    "cleaned": "清洗结果",
    "joined": "关联结果",
}


def set_current_analysis_dataset(project_id: str, dataset_info: dict[str, Any]) -> dict[str, Any]:
    """Persist the project-level current analysis dataset and keep legacy keys in sync."""
    normalized = _normalize_dataset_info(project_id, dataset_info)
    registered = register_project_dataset(project_id, normalized)
    legacy_selection = _legacy_selection_from_dataset(normalized)
    project_workspace.update_project(
        project_id,
        {
            CURRENT_DATASET_KEY: registered,
            "current_analysis_file": legacy_selection,
        },
    )
    return registered


def register_project_dataset(project_id: str, dataset_info: dict[str, Any]) -> dict[str, Any]:
    """Register or update one logical project dataset in project.json."""
    normalized = _normalize_dataset_info(project_id, dataset_info)
    project = project_workspace.get_project(project_id)
    datasets = _sync_project_datasets(project)
    dataset_by_id = {item["dataset_id"]: item for item in datasets}
    dataset_by_id[normalized["dataset_id"]] = {
        **dataset_by_id.get(normalized["dataset_id"], {}),
        **normalized,
    }
    updated = _sort_datasets(list(dataset_by_id.values()))
    project_workspace.update_project(project_id, {PROJECT_DATASETS_KEY: updated})
    return dataset_by_id[normalized["dataset_id"]]


def list_project_datasets(project_id: str) -> list[dict[str, Any]]:
    """Return uploaded sheets and generated datasets as one project dataset list."""
    project = project_workspace.get_project(project_id)
    datasets = _sync_project_datasets(project)
    existing = project.get(PROJECT_DATASETS_KEY, [])
    if datasets != existing:
        project_workspace.update_project(project_id, {PROJECT_DATASETS_KEY: datasets})
    return datasets


def get_project_dataset(project_id: str, dataset_id: str) -> dict[str, Any]:
    for dataset in list_project_datasets(project_id):
        if dataset.get("dataset_id") == dataset_id:
            return dataset
    raise FileNotFoundError(f"项目数据集不存在或已被删除：{dataset_id}")


def load_project_dataset_dataframe(project_id: str, dataset_id: str) -> pd.DataFrame:
    dataset = get_project_dataset(project_id, dataset_id)
    return _read_dataset(project_id, dataset)


def get_current_analysis_dataset(project_id: str) -> dict[str, Any] | None:
    """Return current_analysis_dataset, falling back to legacy project fields."""
    project = project_workspace.get_project(project_id)
    current = project.get(CURRENT_DATASET_KEY)
    if isinstance(current, dict) and current.get("file_path"):
        return current
    legacy = _dataset_from_legacy_fields(project)
    return legacy


def load_current_analysis_dataframe(project_id: str) -> pd.DataFrame:
    current = get_current_analysis_dataset(project_id)
    if not current:
        raise FileNotFoundError(NO_CURRENT_ANALYSIS_DATASET_MESSAGE)
    return _read_dataset(project_id, current)


def _normalize_dataset_info(project_id: str, dataset_info: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(dataset_info, dict):
        raise TypeError("dataset_info must be a dict.")
    dataset = dict(dataset_info)
    dataset.setdefault("dataset_id", dataset.get("file_id") or dataset.get("dataset_name") or "dataset")
    dataset.setdefault("dataset_name", dataset.get("file_name") or dataset.get("dataset_id"))
    dataset.setdefault("dataset_type", dataset.get("source_type") or "uploaded")
    dataset.setdefault("source", dataset.get("source_type") or dataset.get("dataset_type"))
    dataset.setdefault("sheet_name", None)
    dataset.setdefault("created_at", _utc_now())

    file_path = str(dataset.get("file_path") or "").strip()
    if not file_path:
        raise ValueError("当前分析数据集缺少 file_path。")
    dataset["file_path"] = file_path.replace("\\", "/")

    dataframe = _read_dataset(project_id, dataset)
    dataset["row_count"] = int(dataset.get("row_count") or len(dataframe))
    dataset["column_count"] = int(dataset.get("column_count") or len(dataframe.columns))
    dataset.setdefault("source_files", [])
    return dataset


def _dataset_from_legacy_fields(project: dict[str, Any]) -> dict[str, Any] | None:
    current = project.get("current_analysis_file") or {}
    if not isinstance(current, dict):
        current = {}
    if current.get("source_type") == "appended_dataset":
        return {
            "dataset_id": current.get("file_id", "appended_dataset"),
            "dataset_name": current.get("file_name", "appended_dataset.csv"),
            "dataset_type": "appended",
            "file_path": current.get("file_path", "analysis/appended_dataset.csv"),
            "sheet_name": None,
            "source": "append",
            "created_at": current.get("created_at") or project.get("updated_at", ""),
            "row_count": current.get("row_count"),
            "column_count": current.get("column_count"),
        }

    file_id = current.get("file_id") or project.get("current_file")
    sheet_name = current.get("sheet_name") or project.get("current_sheet")
    if file_id:
        metadata = next(
            (
                item
                for item in project.get("data_files", [])
                if item.get("file_id") == file_id
            ),
            None,
        )
        if metadata:
            sheet_profile = _sheet_profile(metadata, sheet_name)
            resolved_sheet_name = sheet_profile.get("sheet_name") if sheet_profile else sheet_name
            return {
                "dataset_id": _uploaded_dataset_id(metadata["file_id"], resolved_sheet_name),
                "dataset_name": _uploaded_dataset_name(metadata["file_name"], resolved_sheet_name),
                "dataset_type": "uploaded",
                "file_path": metadata["file_path"],
                "sheet_name": resolved_sheet_name,
                "source": "upload",
                "created_at": current.get("created_at") or metadata.get("uploaded_at", ""),
                "row_count": sheet_profile.get("rows") if sheet_profile else None,
                "column_count": sheet_profile.get("columns") if sheet_profile else None,
                "source_files": [],
                "source_file_id": metadata["file_id"],
            }
    analysis_dataset = project.get("analysis_dataset")
    if isinstance(analysis_dataset, dict) and analysis_dataset.get("file_path"):
        return {
            "dataset_id": analysis_dataset.get("dataset_name", "analysis_dataset"),
            "dataset_name": analysis_dataset.get("file_name", "analysis_dataset.csv"),
            "dataset_type": "joined",
            "file_path": analysis_dataset["file_path"],
            "sheet_name": None,
            "source": "join",
            "created_at": analysis_dataset.get("created_at") or project.get("updated_at", ""),
            "row_count": analysis_dataset.get("rows"),
            "column_count": analysis_dataset.get("columns"),
        }
    analysis_dataset_path = (
        project_workspace.get_project_path(project["project_id"]) / "analysis" / "analysis_dataset.csv"
    )
    if analysis_dataset_path.is_file():
        return {
            "dataset_id": "analysis_dataset",
            "dataset_name": "analysis_dataset.csv",
            "dataset_type": "joined",
            "file_path": "analysis/analysis_dataset.csv",
            "sheet_name": None,
            "source": "join",
            "created_at": project.get("updated_at", ""),
            "row_count": None,
            "column_count": None,
        }
    return None


def _sync_project_datasets(project: dict[str, Any]) -> list[dict[str, Any]]:
    project_id = project["project_id"]
    project_path = project_workspace.get_project_path(project_id)
    existing_by_id = {
        item.get("dataset_id"): item
        for item in project.get(PROJECT_DATASETS_KEY, [])
        if isinstance(item, dict) and item.get("dataset_id")
    }
    datasets: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for file_metadata in project.get("data_files", []):
        file_path = project_path / str(file_metadata.get("file_path", ""))
        if not file_path.is_file():
            continue
        for sheet in file_metadata.get("sheets", []):
            sheet_name = sheet.get("sheet_name")
            dataset_id = _uploaded_dataset_id(file_metadata["file_id"], sheet_name)
            dataset = {
                **existing_by_id.get(dataset_id, {}),
                "dataset_id": dataset_id,
                "dataset_name": _uploaded_dataset_name(file_metadata["file_name"], sheet_name),
                "dataset_type": "uploaded",
                "file_path": file_metadata["file_path"],
                "sheet_name": sheet_name,
                "row_count": int(sheet.get("rows", 0)),
                "column_count": int(sheet.get("columns", 0)),
                "created_at": file_metadata.get("uploaded_at", ""),
                "source": "upload",
                "source_files": [],
                "source_file_id": file_metadata["file_id"],
                "file_size": file_metadata.get("file_size", 0),
            }
            datasets.append(dataset)
            seen_ids.add(dataset_id)

    appended = project.get("appended_dataset")
    if isinstance(appended, dict):
        _append_generated_dataset(
            datasets,
            seen_ids,
            existing_by_id,
            dataset_id="appended_dataset",
            dataset_name=appended.get("file_name", "appended_dataset.csv"),
            dataset_type="appended",
            file_path=appended.get("file_path", "analysis/appended_dataset.csv"),
            row_count=appended.get("after_rows"),
            column_count=appended.get("columns"),
            created_at=appended.get("created_at", ""),
            source="append",
            source_files=appended.get("source_files", []),
            project_path=project_path,
        )

    analysis_dataset = project.get("analysis_dataset")
    if isinstance(analysis_dataset, dict):
        _append_generated_dataset(
            datasets,
            seen_ids,
            existing_by_id,
            dataset_id=analysis_dataset.get("dataset_name", "analysis_dataset"),
            dataset_name=analysis_dataset.get("file_name", "analysis_dataset.csv"),
            dataset_type="joined",
            file_path=analysis_dataset.get("file_path", "analysis/analysis_dataset.csv"),
            row_count=analysis_dataset.get("rows"),
            column_count=analysis_dataset.get("columns"),
            created_at=analysis_dataset.get("created_at", ""),
            source="join",
            source_files=analysis_dataset.get("source_tables", []),
            project_path=project_path,
        )

    for dataset_id, file_name, dataset_type, source in (
        ("cleaned_dataset", "cleaned_dataset.csv", "cleaned", "clean"),
        ("joined_dataset", "joined_dataset.csv", "joined", "join"),
        ("analysis_dataset", "analysis_dataset.csv", "joined", "join"),
    ):
        file_path = f"analysis/{file_name}"
        if dataset_id not in seen_ids and (project_path / file_path).is_file():
            dataframe = _read_dataset(project_id, {"file_path": file_path, "sheet_name": None})
            _append_generated_dataset(
                datasets,
                seen_ids,
                existing_by_id,
                dataset_id=dataset_id,
                dataset_name=file_name,
                dataset_type=dataset_type,
                file_path=file_path,
                row_count=len(dataframe),
                column_count=len(dataframe.columns),
                created_at=project.get("updated_at", ""),
                source=source,
                source_files=[],
                project_path=project_path,
            )

    for dataset_id, dataset in existing_by_id.items():
        if dataset_id in seen_ids:
            continue
        dataset_path = project_path / str(dataset.get("file_path", ""))
        if dataset.get("dataset_type") in {"cleaned", "joined"} and dataset_path.is_file():
            datasets.append(dataset)
            seen_ids.add(dataset_id)

    return _sort_datasets(datasets)


def _append_generated_dataset(
    datasets: list[dict[str, Any]],
    seen_ids: set[str],
    existing_by_id: dict[str, dict[str, Any]],
    *,
    dataset_id: str,
    dataset_name: str,
    dataset_type: str,
    file_path: str,
    row_count: Any,
    column_count: Any,
    created_at: str,
    source: str,
    source_files: list[Any],
    project_path: Path,
) -> None:
    if not file_path:
        return
    if not (project_path / file_path).is_file():
        return
    dataset = {
        **existing_by_id.get(dataset_id, {}),
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "dataset_type": dataset_type,
        "file_path": file_path,
        "sheet_name": None,
        "row_count": int(row_count or 0),
        "column_count": int(column_count or 0),
        "created_at": created_at,
        "source": source,
        "source_files": source_files or [],
    }
    datasets.append(dataset)
    seen_ids.add(dataset_id)


def _sort_datasets(datasets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    type_order = {"uploaded": 0, "appended": 1, "cleaned": 2, "joined": 3}
    return sorted(
        datasets,
        key=lambda item: (
            type_order.get(item.get("dataset_type"), 99),
            str(item.get("created_at", "")),
            str(item.get("dataset_name", "")),
        ),
        reverse=False,
    )


def _uploaded_dataset_id(file_id: str | None, sheet_name: str | None) -> str:
    return f"{file_id}::{sheet_name or 'CSV'}"


def _uploaded_dataset_name(file_name: str, sheet_name: str | None) -> str:
    if sheet_name and sheet_name != "CSV":
        return f"{file_name} / {sheet_name}"
    return file_name


def _legacy_selection_from_dataset(dataset: dict[str, Any]) -> dict[str, Any]:
    if dataset.get("dataset_type") == "appended":
        return {
            "source_type": "appended_dataset",
            "file_id": dataset.get("dataset_id", "appended_dataset"),
            "file_name": dataset.get("dataset_name", "appended_dataset.csv"),
            "display_name": f"合并数据集 {dataset.get('dataset_name', 'appended_dataset.csv')}",
            "file_path": dataset.get("file_path", "analysis/appended_dataset.csv"),
            "sheet_name": "CSV",
            "created_at": dataset.get("created_at", ""),
            "row_count": dataset.get("row_count"),
            "column_count": dataset.get("column_count"),
        }
    return {
        "file_id": dataset.get("source_file_id") or dataset.get("dataset_id"),
        "file_name": dataset.get("dataset_name"),
        "sheet_name": dataset.get("sheet_name"),
        "created_at": dataset.get("created_at", ""),
        "row_count": dataset.get("row_count"),
        "column_count": dataset.get("column_count"),
    }


def _read_dataset(project_id: str, dataset: dict[str, Any]) -> pd.DataFrame:
    file_path = _resolve_project_file(project_id, str(dataset.get("file_path", "")))
    if not file_path.is_file():
        raise FileNotFoundError(CURRENT_ANALYSIS_DATASET_MISSING_FILE_MESSAGE)
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(file_path)
    if suffix in {".xlsx", ".xls"}:
        sheet_name = dataset.get("sheet_name")
        return pd.read_excel(file_path, sheet_name=sheet_name or 0)
    raise ValueError(f"不支持的当前分析数据集文件类型：{suffix}")


def _resolve_project_file(project_id: str, file_path: str) -> Path:
    project_path = project_workspace.get_project_path(project_id).resolve()
    candidate = (project_path / file_path).resolve()
    if project_path not in candidate.parents and candidate != project_path:
        raise ValueError("当前分析数据集路径无效。")
    return candidate


def _sheet_profile(metadata: dict[str, Any], sheet_name: str | None) -> dict[str, Any]:
    sheets = metadata.get("sheets", [])
    if not sheets:
        return {}
    if sheet_name:
        for sheet in sheets:
            if sheet.get("sheet_name") == sheet_name:
                return sheet
    return sheets[0]


def _read_csv(file_path: Path) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "latin1"):
        try:
            return pd.read_csv(file_path, encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("无法识别 CSV 文件编码。")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
