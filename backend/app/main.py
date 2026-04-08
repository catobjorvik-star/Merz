
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .catalogue_router import router as catalogue_router
from .importer import (
    enrich_rows_with_supplier_lookup,
    extract_rows_from_pdf,
    validate_rows,
    write_to_template,
)
from .project_router import router as project_router
from .project_service import load_project, save_export_to_project, save_file_to_project

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
FRONTEND_DIST = BACKEND_DIR / "frontend_dist"

TEMPLATE_CANDIDATES = [
    APP_DIR / "MERZ_Kalkulation_Vorlage.xlsx",
    APP_DIR / "MERZ_Kalkulation_Vorlage (1).xlsx",
    APP_DIR / "MERZ_Kalkulation_Vorlage_neu.xlsx",
]


app = FastAPI(title="MERZ ProjektSuite API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalogue_router)
app.include_router(project_router)


def _get_template_path() -> Path:
    for candidate in TEMPLATE_CANDIDATES:
        if candidate.exists():
            return candidate
    raise HTTPException(
        status_code=500,
        detail="MERZ-Kalkulationsvorlage wurde auf dem Server nicht gefunden.",
    )


def _parse_catalogue_queue(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x) for x in data]
    except Exception:
        pass
    return []


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.post("/api/preview")
async def preview_pdf(
    pdf: UploadFile = File(...),
    project_id: str | None = Form(default=None),
) -> JSONResponse:
    if not pdf.filename or not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Bitte eine PDF-Datei hochladen.")

    pdf_bytes = await pdf.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Die hochgeladene PDF ist leer.")

    try:
        rows = extract_rows_from_pdf(pdf_bytes)
        rows = enrich_rows_with_supplier_lookup(rows)
        warnings = validate_rows(rows)

        if project_id:
            if not load_project(project_id):
                raise HTTPException(status_code=404, detail="Projekt nicht gefunden.")
            save_file_to_project(project_id, "Fensterlisten", pdf.filename, pdf_bytes)

        return JSONResponse(
            {
                "count": len(rows),
                "rows": rows,
                "warnings": warnings,
                "source_pdf": pdf.filename,
                "project_id": project_id,
            }
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/import")
async def import_pdf_to_excel(
    pdf: UploadFile = File(...),
    catalogue_queue: str | None = Form(default=None),
    project_id: str | None = Form(default=None),
) -> FileResponse:
    if not pdf.filename or not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Bitte eine PDF-Datei hochladen.")

    pdf_bytes = await pdf.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Die hochgeladene PDF ist leer.")

    template_path = _get_template_path()
    template_bytes = template_path.read_bytes()

    try:
        rows = extract_rows_from_pdf(pdf_bytes)
        rows = enrich_rows_with_supplier_lookup(rows)
        warnings = validate_rows(rows)

        selected_catalogue_codes = _parse_catalogue_queue(catalogue_queue)
        if selected_catalogue_codes:
            warnings.append("Katalog-Queue übergeben: " + ", ".join(selected_catalogue_codes))

        output_bytes = write_to_template(
            excel_bytes=template_bytes,
            rows=rows,
            warnings=warnings,
            source_pdf_name=pdf.filename,
            house_mode="BOTH",
            aggregate=False,
        )

        out_path = APP_DIR / "MERZ_Fensterimport_export.xlsx"
        out_path.write_bytes(output_bytes)

        if project_id:
            if not load_project(project_id):
                raise HTTPException(status_code=404, detail="Projekt nicht gefunden.")
            save_file_to_project(project_id, "Fensterlisten", pdf.filename, pdf_bytes)
            save_export_to_project(project_id, "MERZ_Fensterimport_export.xlsx", output_bytes)

        headers = {"X-Import-Warnings": str(len(warnings))}
        return FileResponse(
            path=out_path,
            filename="MERZ_Fensterimport_export.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
