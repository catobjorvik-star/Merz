
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .project_service import (
    create_project,
    list_project_files,
    list_projects,
    load_project,
    save_file_to_project,
)

router = APIRouter(tags=["projects"])


@router.get("/api/projects")
def get_projects():
    return {"projects": list_projects()}


@router.post("/api/projects")
def new_project(payload: dict):
    try:
        name = str(payload.get("name", "")).strip()
        number = str(payload.get("number", "")).strip()
        if not name or not number:
            raise ValueError("Projektname und Projektnummer sind Pflichtfelder.")
        project = create_project(
            name=name,
            number=number,
            client=str(payload.get("client", "")).strip(),
            location=str(payload.get("location", "")).strip(),
            notes=str(payload.get("notes", "")).strip(),
        )
        return project
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/api/projects/{project_id}")
def project_detail(project_id: str):
    project = load_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projekt nicht gefunden.")
    return {"project": project, "files": list_project_files(project_id)}


@router.post("/api/projects/{project_id}/upload")
async def upload_project_file(
    project_id: str,
    folder: str = Form(...),
    file: UploadFile = File(...),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Keine Datei hochgeladen.")
    try:
        content = await file.read()
        save_file_to_project(project_id, folder, file.filename, content)
        return {"ok": True, "project_id": project_id, "folder": folder, "filename": file.filename}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
