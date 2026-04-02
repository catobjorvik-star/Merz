from __future__ import annotations

import io
import re
import tempfile
from collections import OrderedDict
from copy import copy
from datetime import datetime
from pathlib import Path

import pdfplumber
from openpyxl import load_workbook
from openpyxl.styles import PatternFill

ID_RE = re.compile(r"^F-[AB]\.(EG|OG|DG)\.\d+[A-Za-z]?$")
HOUSE_RE = re.compile(r"^F-([AB])\.")
FOOTER_MARKER = "€/LFM"
FOOTER_SEARCH_COL = "Q"
MM = 1000

def parse_de_to_mm(value: str) -> int:
    if value is None:
        raise ValueError("Missing numeric value")
    s = str(value).strip().replace(" ", "")
    s = s.replace(",", ".")
    return int(round(float(s) * MM))

def mm_to_de_dimension(value_mm: int) -> str:
    meters = float(value_mm) / MM
    s = f"{meters:.3f}"
    whole, dec = s.split(".")
    dec = dec.rstrip("0")
    if len(dec) < 2:
        dec = dec.ljust(2, "0")
    return f"{whole},{dec}"

def rohbau_text(width_mm: int, height_mm: int) -> str:
    return f"{mm_to_de_dimension(width_mm)}×{mm_to_de_dimension(height_mm)}"

def extract_rows_from_pdf(pdf_bytes: bytes) -> list[dict]:
    rows: list[dict] = []
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    try:
        with pdfplumber.open(tmp_path) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables() or []
                for table_index, table in enumerate(tables, start=1):
                    for raw in table:
                        if not raw or len(raw) < 10:
                            continue
                        raw_id = (raw[1] or "").strip() if raw[1] else ""
                        if not ID_RE.match(raw_id):
                            continue
                        qty_text = str(raw[3] or "").strip()
                        width_text = str(raw[4] or "").strip()
                        height_text = str(raw[5] or "").strip()
                        if not qty_text or not width_text or not height_text:
                            continue
                        qty = int(float(qty_text.replace(",", ".")))
                        width_mm = parse_de_to_mm(width_text)
                        height_mm = parse_de_to_mm(height_text)
                        floor = (raw[0] or "").strip()
                        room_no = (raw[8] or "").strip()
                        room_name = (raw[9] or "").strip()
                        construction_type = (raw[2] or "").strip() or "Unbekannt"
                        house_match = HOUSE_RE.match(raw_id)
                        house = house_match.group(1) if house_match else ""
                        rows.append({
                            "page": page_index,
                            "table": table_index,
                            "id": raw_id,
                            "house": house,
                            "floor": floor,
                            "qty": qty,
                            "width_mm": width_mm,
                            "height_mm": height_mm,
                            "room_no": room_no,
                            "room_name": room_name,
                            "type": construction_type,
                            "description": rohbau_text(width_mm, height_mm),
                            "raw_dimension_text": rohbau_text(width_mm, height_mm),
                        })
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    if not rows:
        raise ValueError("Keine gültigen Fensterzeilen im PDF gefunden.")
    return rows

def filter_rows(rows: list[dict], house_mode: str) -> list[dict]:
    house_mode = house_mode.upper()
    if house_mode == "BOTH":
        return list(rows)
    if house_mode not in {"A", "B"}:
        raise ValueError("house_mode must be A, B, or BOTH")
    return [r for r in rows if r["house"] == house_mode]

def aggregate_rows(rows: list[dict]) -> list[dict]:
    grouped: OrderedDict[tuple, dict] = OrderedDict()
    for row in rows:
        key = (row["width_mm"], row["height_mm"], row["type"])
        if key not in grouped:
            grouped[key] = {
                "page": row["page"], "table": row["table"], "id": "",
                "house": "MIX", "floor": "", "qty": 0,
                "width_mm": key[0], "height_mm": key[1],
                "room_no": "", "room_name": "", "type": row["type"],
                "description": rohbau_text(key[0], key[1]),
                "raw_dimension_text": rohbau_text(key[0], key[1]),
            }
        grouped[key]["qty"] += row["qty"]
    out = []
    for idx, item in enumerate(grouped.values(), start=1):
        item["id"] = f"AGG-{idx:03d}"
        out.append(item)
    return out

def validate_rows(rows: list[dict]) -> list[str]:
    warnings: list[str] = []
    seen_ids: set[str] = set()
    for row in rows:
        if row["id"] in seen_ids and not row["id"].startswith("AGG-"):
            warnings.append(f"Doppelte ID gefunden: {row['id']}")
        seen_ids.add(row["id"])
        if row["qty"] < 1:
            warnings.append(f"Ungültige Menge bei {row['id']}: {row['qty']}")
        if not (300 <= row["width_mm"] <= 6000):
            warnings.append(f"Breite außerhalb Plausibilitätsgrenze bei {row['id']}: {row['width_mm']} mm")
        if not (300 <= row["height_mm"] <= 6000):
            warnings.append(f"Höhe außerhalb Plausibilitätsgrenze bei {row['id']}: {row['height_mm']} mm")
    return warnings

def clear_target_block(ws, start_row: int, end_row: int) -> None:
    merged_addresses = {cell.coordinate for merged in ws.merged_cells.ranges for row in ws[merged.coord] for cell in row}
    for row in range(start_row, end_row + 1):
        for col in ("I", "J", "K", "L", "M", "O", "Q", "S"):
            addr = f"{col}{row}"
            if addr in merged_addresses:
                continue
            ws[addr].value = None

def find_footer_row(ws, default_row: int = 39) -> int:
    for row in range(1, ws.max_row + 1):
        if ws[f"{FOOTER_SEARCH_COL}{row}"].value == FOOTER_MARKER:
            return row
    return default_row

def apply_row_style(ws, source_row: int, target_row: int, start_col: int = 9, end_col: int = 19) -> None:
    for col in range(start_col, end_col + 1):
        source = ws.cell(source_row, col)
        target = ws.cell(target_row, col)
        target._style = copy(source._style)
        target.font = copy(source.font)
        target.fill = copy(source.fill)
        target.border = copy(source.border)
        target.alignment = copy(source.alignment)
        target.protection = copy(source.protection)
        target.number_format = source.number_format

def populate_report_sheet(wb, rows: list[dict], warnings: list[str], source_pdf: str, house_mode: str, aggregate: bool):
    if "Import_PDF" in wb.sheetnames:
        del wb["Import_PDF"]
    report = wb.create_sheet("Import_PDF")
    report["A1"] = "Importbericht"
    report["A2"] = "Quelle PDF"; report["B2"] = source_pdf
    report["A3"] = "Haus-Modus"; report["B3"] = house_mode
    report["A4"] = "Aggregation"; report["B4"] = "Ja" if aggregate else "Nein"
    report["A5"] = "Zeitstempel"; report["B5"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report["A7"] = "Warnungen"; report["B7"] = len(warnings)
    warn_fill = PatternFill(fill_type="solid", fgColor="FFF2CC")
    row_cursor = 8
    if warnings:
        for warning in warnings:
            report[f"A{row_cursor}"] = "WARN"
            report[f"B{row_cursor}"] = warning
            report[f"A{row_cursor}"].fill = warn_fill
            report[f"B{row_cursor}"].fill = warn_fill
            row_cursor += 1
    else:
        report[f"A{row_cursor}"] = "OK"; report[f"B{row_cursor}"] = "Keine Warnungen"; row_cursor += 2
    row_cursor += 1
    headers = ["ID","Haus","Geschoss","Menge","Breite_mm","Höhe_mm","Rohbauöffnung","Typ","Raumnr.","Raumname"]
    for idx, header in enumerate(headers, start=1):
        report.cell(row_cursor, idx).value = header
    row_cursor += 1
    for item in rows:
        vals = [item["id"], item["house"], item["floor"], item["qty"], item["width_mm"], item["height_mm"], item["description"], item["type"], item["room_no"], item["room_name"]]
        for idx, val in enumerate(vals, start=1):
            report.cell(row_cursor, idx).value = val
        row_cursor += 1
    for col in ("A","B","C","D","E","F","G","H","I","J"):
        report.column_dimensions[col].width = 18

def write_to_template(excel_bytes: bytes, rows: list[dict], warnings: list[str], source_pdf_name: str, house_mode: str, aggregate: bool) -> bytes:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(excel_bytes); tmp_path = tmp.name
    try:
        wb = load_workbook(tmp_path)
        if "Tabelle1" not in wb.sheetnames:
            raise ValueError("Arbeitsblatt 'Tabelle1' wurde in der Vorlage nicht gefunden.")
        ws = wb["Tabelle1"]
        start_row = 4; style_row = 4; footer_row = find_footer_row(ws)
        rows_needed = max(len(rows), 1); last_needed_row = start_row + rows_needed - 1
        if last_needed_row >= footer_row:
            insert_count = last_needed_row - footer_row + 2
            ws.insert_rows(footer_row, insert_count)
            for offset in range(insert_count):
                apply_row_style(ws, style_row, footer_row + offset)
        clear_target_block(ws, start_row, last_needed_row + 10)
        for idx, r in enumerate(rows):
            excel_row = start_row + idx
            apply_row_style(ws, style_row, excel_row)
            ws[f"I{excel_row}"].value = r["id"]
            ws[f"J{excel_row}"].value = r["qty"]
            ws[f"K{excel_row}"].value = r["width_mm"]
            ws[f"L{excel_row}"].value = r["height_mm"]
            ws[f"M{excel_row}"].value = r["description"]
            ws[f"M{excel_row}"].alignment = copy(ws[f"M{style_row}"].alignment)
            ws.row_dimensions[excel_row].height = ws.row_dimensions[style_row].height or 18
        for row in range(last_needed_row + 1, last_needed_row + 6):
            for col in ("I","J","K","L","M"):
                ws[f"{col}{row}"].value = None
        ws.column_dimensions["I"].width = max(ws.column_dimensions["I"].width or 8, 16)
        ws.column_dimensions["J"].width = max(ws.column_dimensions["J"].width or 8, 8)
        ws.column_dimensions["K"].width = max(ws.column_dimensions["K"].width or 8, 12)
        ws.column_dimensions["L"].width = max(ws.column_dimensions["L"].width or 8, 12)
        ws.column_dimensions["M"].width = max(ws.column_dimensions["M"].width or 8, 22)
        populate_report_sheet(wb, rows, warnings, source_pdf_name, house_mode, aggregate)
        out = io.BytesIO(); wb.save(out); return out.getvalue()
    finally:
        Path(tmp_path).unlink(missing_ok=True)

def preview_data(pdf_bytes: bytes, house_mode: str, aggregate: bool) -> dict:
    rows = extract_rows_from_pdf(pdf_bytes)
    rows = filter_rows(rows, house_mode)
    if aggregate:
        rows = aggregate_rows(rows)
    warnings = validate_rows(rows)
    return {"rows": rows, "warnings": warnings, "count": len(rows)}
