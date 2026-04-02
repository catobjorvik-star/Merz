from __future__ import annotations

import io
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .importer import (
    aggregate_rows,
    extract_rows_from_pdf,
    filter_rows,
    validate_rows,
    write_to_template,
)

APP_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = APP_DIR.parent.parent / "frontend_dist"

app = FastAPI(title="MERZ Fensterimport", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _normalize_house_mode(value: str) -> str:
    value = (value or "").strip().upper()
    if value in {"A", "B", "BOTH"}:
        return value
    raise HTTPException(status_code=400, detail="house_mode must be A, B, or BOTH")

def _prepare_preview(pdf_bytes: bytes, house_mode: str, aggregate: bool):
    rows = extract_rows_from_pdf(pdf_bytes)
    rows = filter_rows(rows, house_mode)
    if aggregate:
        rows = aggregate_rows(rows)
    warnings = validate_rows(rows)
    return rows, warnings

@app.get("/api/health")
def health():
    return {"ok": True}

@app.post("/api/preview")
async def preview(
    pdf: UploadFile = File(...),
    house_mode: str = Form("BOTH"),
    aggregate: bool = Form(False),
):
    if not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Bitte eine PDF-Datei hochladen.")
    pdf_bytes = await pdf.read()
    try:
        house_mode = _normalize_house_mode(house_mode)
        rows, warnings = _prepare_preview(pdf_bytes, house_mode, aggregate)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    preview_rows = [
        {
            "id": row["id"],
            "house": row["house"],
            "floor": row["floor"],
            "qty": row["qty"],
            "width_mm": row["width_mm"],
            "height_mm": row["height_mm"],
            "rohbau": row["description"],
            "type": row["type"],
            "room_no": row["room_no"],
            "room_name": row["room_name"],
        }
        for row in rows
    ]
    return {
        "count": len(preview_rows),
        "warnings": warnings,
        "rows": preview_rows,
    }

@app.post("/api/import")
async def perform_import(
    pdf: UploadFile = File(...),
    template: UploadFile = File(...),
    house_mode: str = Form("BOTH"),
    aggregate: bool = Form(False),
):
    pdf_name = pdf.filename or "Fensterliste.pdf"
    template_name = template.filename or "Vorlage.xlsx"

    if not pdf_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Bitte eine PDF-Datei hochladen.")
    if not template_name.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Bitte eine XLSX-Vorlage hochladen.")

    pdf_bytes = await pdf.read()
    template_bytes = await template.read()

    try:
        house_mode = _normalize_house_mode(house_mode)
        rows, warnings = _prepare_preview(pdf_bytes, house_mode, aggregate)
        out_bytes = write_to_template(
            excel_bytes=template_bytes,
            rows=rows,
            warnings=warnings,
            source_pdf_name=pdf_name,
            house_mode=house_mode,
            aggregate=aggregate,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    stem = Path(template_name).stem
    suffix = f"_{house_mode.lower()}" if house_mode != "BOTH" else "_beide"
    if aggregate:
        suffix += "_aggregiert"
    out_name = f"{stem}_importiert{suffix}.xlsx"

    headers = {
        "Content-Disposition": f'attachment; filename="{out_name}"',
        "X-Import-Warnings": str(len(warnings)),
    }
    return Response(
        content=out_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )

if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
