from __future__ import annotations

import json
import re
import shutil
import unicodedata
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1] / "workspace" / "projects"
PROJECT_DIRECTORIES = ("data", "reports", "exports", "config", "analysis")
SUPPORTED_DATA_SUFFIXES = {".csv", ".xlsx", ".xls"}


class ProjectFile(BytesIO):
    """In-memory project file compatible with the existing upload pipeline."""

    def __init__(self, content: bytes, name: str):
        super().__init__(content)
        self.name = name
        self.size = len(content)


def create_project(project_name: str) -> dict:
    clean_name = project_name.strip()
    if not clean_name:
        raise ValueError("项目名称不能为空。")

    PROJECT_ROOT.mkdir(parents=True, exist_ok=True)
    project_id = _available_project_id(clean_name)
    project_path = PROJECT_ROOT / project_id
    project_path.mkdir()
    for directory in PROJECT_DIRECTORIES:
        (project_path / directory).mkdir()

    now = _utc_now()
    project = {
        "project_id": project_id,
        "project_name": clean_name,
        "create_time": now,
        "last_modified": now,
        "created_at": now,
        "updated_at": now,
        "data_files": [],
        "project_datasets": [],
        "current_analysis_dataset": None,
        "current_analysis_file": None,
    }
    _write_project(project_path, project)
    return project


def list_projects() -> list[dict]:
    PROJECT_ROOT.mkdir(parents=True, exist_ok=True)
    projects = []
    for project_file in PROJECT_ROOT.glob("*/project.json"):
        try:
            projects.append(_read_project(project_file.parent))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return sorted(projects, key=lambda item: item["last_modified"], reverse=True)


def get_project(project_id: str) -> dict:
    return _read_project(_project_path(project_id))


def update_project(project_id: str, updates: dict) -> dict:
    project_path = _project_path(project_id)
    if not project_path.is_dir():
        raise FileNotFoundError(f"Project not found: {project_id}")
    if not isinstance(updates, dict):
        raise TypeError("Project updates must be a dict.")
    try:
        project = _read_project(project_path)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Project not found: {project_id}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid project configuration: {project_id}/project.json is corrupted."
        ) from exc
    except ValueError as exc:
        raise ValueError(
            f"Invalid project configuration: {project_id}/project.json is incomplete."
        ) from exc

    project.update(updates)
    now = _utc_now()
    project["last_modified"] = now
    project["updated_at"] = now
    _write_project(project_path, project)
    return project


def delete_project(project_id: str) -> None:
    project_path = _project_path(project_id)
    if not project_path.exists():
        raise FileNotFoundError("项目不存在或已被删除。")
    shutil.rmtree(project_path)


def save_project_files(project_id: str, uploaded_files: Iterable[BinaryIO]) -> list[str]:
    project_path = _project_path(project_id)
    data_path = project_path / "data"
    data_path.mkdir(parents=True, exist_ok=True)
    saved_files = []

    for uploaded_file in uploaded_files:
        file_name = _safe_file_name(getattr(uploaded_file, "name", ""))
        suffix = Path(file_name).suffix.lower()
        if suffix not in SUPPORTED_DATA_SUFFIXES:
            raise ValueError(f"不支持的文件类型：{file_name}")

        if hasattr(uploaded_file, "getvalue"):
            content = uploaded_file.getvalue()
        else:
            uploaded_file.seek(0)
            content = uploaded_file.read()
        (data_path / file_name).write_bytes(content)
        saved_files.append(file_name)

    if saved_files:
        _touch_project(project_path)
    return saved_files


def list_project_files(project_id: str) -> list[dict]:
    data_path = _project_path(project_id) / "data"
    files = []
    if not data_path.exists():
        return files
    for file_path in data_path.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_DATA_SUFFIXES:
            stat = file_path.stat()
            files.append(
                {
                    "name": file_path.name,
                    "size": stat.st_size,
                    "last_modified": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                }
            )
    return sorted(files, key=lambda item: item["name"].lower())


def load_project_file(project_id: str, file_name: str) -> ProjectFile:
    safe_name = _safe_file_name(file_name)
    file_path = _project_path(project_id) / "data" / safe_name
    if not file_path.is_file():
        raise FileNotFoundError(f"项目文件不存在：{safe_name}")
    return ProjectFile(file_path.read_bytes(), safe_name)


def get_project_path(project_id: str) -> Path:
    return _project_path(project_id)


def _project_path(project_id: str) -> Path:
    root = PROJECT_ROOT.resolve()
    candidate = (root / project_id).resolve()
    if candidate.parent != root:
        raise ValueError("无效的项目 ID。")
    return candidate


def _available_project_id(project_name: str) -> str:
    base = _slugify(project_name)
    candidate = base
    while (PROJECT_ROOT / candidate).exists():
        candidate = f"{base}-{uuid.uuid4().hex[:6]}"
    return candidate


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")
    return slug[:48] or f"project-{uuid.uuid4().hex[:8]}"


def _safe_file_name(file_name: str) -> str:
    safe_name = Path(file_name).name.strip()
    if not safe_name or safe_name in {".", ".."}:
        raise ValueError("文件名无效。")
    return safe_name


def _read_project(project_path: Path) -> dict:
    project_file = project_path / "project.json"
    with project_file.open("r", encoding="utf-8") as handle:
        project = json.load(handle)
    required = {"project_id", "project_name", "create_time", "last_modified"}
    if not required.issubset(project):
        raise ValueError("项目配置不完整。")
    project.setdefault("created_at", project["create_time"])
    project.setdefault("updated_at", project["last_modified"])
    project.setdefault("data_files", [])
    project.setdefault("project_datasets", [])
    project.setdefault("current_analysis_dataset", None)
    project.setdefault("current_analysis_file", None)
    return project


def _write_project(project_path: Path, project: dict) -> None:
    with (project_path / "project.json").open("w", encoding="utf-8") as handle:
        json.dump(project, handle, ensure_ascii=False, indent=2)


def _touch_project(project_path: Path) -> None:
    project = _read_project(project_path)
    now = _utc_now()
    project["last_modified"] = now
    project["updated_at"] = now
    _write_project(project_path, project)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
