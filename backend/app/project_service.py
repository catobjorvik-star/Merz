
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PROJECTS_DIR = BACKEND_DIR / "projects"

PROJECT_FOLDERS = [
    "Fensterlisten",
    "Pläne",
    "Angebote",
    "Exports",
]

PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


def _safe_slug(value: str) -> str:
    value = value.strip().replace("/", "-").replace("\\", "-")
    cleaned = "".join(ch for ch in value if ch.isalnum() or ch in ("-", "_", " "))
    return cleaned.strip().replace(" ", "_")


def project_path(project_id: str) -> Path:
    return PROJECTS_DIR / project_id


def project_meta_path(project_id: str) -> Path:
    return project_path(project_id) / "project.json"


def load_project(project_id: str) -> dict[str, Any] | None:
    meta = project_meta_path(project_id)
    if not meta.exists():
        return None
    return json.loads(meta.read_text(encoding="utf-8"))


def create_project(name: str, number: str, client: str = "", location: str = "", notes: str = "") -> dict[str, Any]:
    number_slug = _safe_slug(number)
    name_slug = _safe_slug(name)
    project_id = f"Projekt_{number_slug}_{name_slug}"

    path = project_path(project_id)
    path.mkdir(parents=True, exist_ok=True)

    for folder in PROJECT_FOLDERS:
        (path / folder).mkdir(exist_ok=True)

    meta = {
        "id": project_id,
        "name": name,
        "number": number,
        "client": client,
        "location": location,
        "notes": notes,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    project_meta_path(project_id).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def list_projects() -> list[dict[str, Any]]:
    projects: list[dict[str, Any]] = []
    for path in PROJECTS_DIR.iterdir():
        if not path.is_dir():
            continue
        meta = path / "project.json"
        if meta.exists():
            data = json.loads(meta.read_text(encoding="utf-8"))
            data["file_counts"] = {
                folder: len([p for p in (path / folder).glob("*") if p.is_file()])
                for folder in PROJECT_FOLDERS
            }
            projects.append(data)
    return sorted(projects, key=lambda x: x.get("number", ""))


def list_project_files(project_id: str) -> dict[str, list[dict[str, Any]]]:
    path = project_path(project_id)
    if not path.exists():
        raise FileNotFoundError("Projekt nicht gefunden.")

    result: dict[str, list[dict[str, Any]]] = {}
    for folder in PROJECT_FOLDERS:
        folder_path = path / folder
        folder_path.mkdir(exist_ok=True)
        result[folder] = [
            {
                "name": item.name,
                "size": item.stat().st_size,
                "modified_at": datetime.fromtimestamp(item.stat().st_mtime).isoformat(timespec="seconds"),
            }
            for item in sorted(folder_path.iterdir())
            if item.is_file()
        ]
    return result


def save_file_to_project(project_id: str, folder: str, filename: str, content: bytes) -> Path:
    if folder not in PROJECT_FOLDERS:
        raise ValueError("Ungültiger Projektordner.")
    path = project_path(project_id)
    if not path.exists():
        raise FileNotFoundError("Projekt nicht gefunden.")
    safe_name = Path(filename).name
    target = path / folder / safe_name
    target.write_bytes(content)
    return target


def save_export_to_project(project_id: str, filename: str, content: bytes) -> Path:
    return save_file_to_project(project_id, "Exports", filename, content)
