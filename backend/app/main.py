from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from .importer import extract_rows_from_pdf, enrich_rows_with_supplier_lookup, validate_rows, write_to_template

APP_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = APP_DIR.parent.parent / "frontend_dist"
SERVER_TEMPLATE = APP_DIR / "MERZ_Kalkulation_Vorlage.xlsx"

app = FastAPI(title="MERZ Fensterimport", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _prepare_preview(pdf_bytes: bytes):
    rows = extract_rows_from_pdf(pdf_bytes)
    rows = enrich_rows_with_supplier_lookup(rows)
    warnings = validate_rows(rows)
    return rows, warnings

@app.get("/api/health")
def health():
    return {"ok": True}

@app.post("/api/preview")
async def preview(pdf: UploadFile = File(...)):
    if not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Bitte eine PDF-Datei hochladen.")
    pdf_bytes = await pdf.read()
    try:
        rows, warnings = _prepare_preview(pdf_bytes)
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
            "supplier_type": row.get("supplier_type"),
            "lookup_width_mm": row.get("lookup_width_mm"),
            "lookup_height_mm": row.get("lookup_height_mm"),
            "supplier_price_eur": row.get("supplier_price_eur"),
            "glass_area_index_m2": row.get("glass_area_index_m2"),
            "supplier_confidence": row.get("supplier_confidence"),
            "supplier_match_note": row.get("supplier_match_note"),
        }
        for row in rows
    ]
    return {"count": len(preview_rows), "warnings": warnings, "rows": preview_rows}

@app.post("/api/import")
async def perform_import(pdf: UploadFile = File(...)):
    pdf_name = pdf.filename or "Fensterliste.pdf"
    if not pdf_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Bitte eine PDF-Datei hochladen.")
    if not SERVER_TEMPLATE.exists():
        raise HTTPException(status_code=500, detail="Server-Vorlage wurde nicht gefunden.")

    pdf_bytes = await pdf.read()
    template_bytes = SERVER_TEMPLATE.read_bytes()

    try:
        rows, warnings = _prepare_preview(pdf_bytes)
        out_bytes = write_to_template(
            excel_bytes=template_bytes,
            rows=rows,
            warnings=warnings,
            source_pdf_name=pdf_name,
            house_mode="BOTH",
            aggregate=False,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    out_name = "MERZ_Kalkulation_importiert.xlsx"
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
