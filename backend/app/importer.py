
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
from openpyxl.formula.translate import Translator
from openpyxl.styles import PatternFill
from openpyxl.cell.cell import MergedCell

ID_RE = re.compile(r"^F-[AB]\.(EG|OG|DG)\.\d+[A-Za-z]?$")
HOUSE_RE = re.compile(r"^F-([AB])\.")
DIM_PAIR_RE = re.compile(r"(\d+(?:,\d+)?)\s*[×x]\s*(\d+(?:,\d+)?)")
FOOTER_MARKERS = {"Fenstertyp", "montage Fenster", "€/LFM", "1Flg.", "1Flg. "}
FOOTER_SEARCH_COLS = ("A", "K", "L", "Q")
MM = 1000


def parse_de_to_mm(value: str) -> int:
    if value is None:
        raise ValueError("Missing numeric value")
    s = str(value).strip().replace(" ", "").replace("\n", "")
    s = s.replace(",", ".")
    return int(round(float(s) * MM))


def parse_dimension_pair(value: str) -> tuple[int, int] | None:
    if not value:
        return None
    s = str(value).replace("\n", "").replace(" ", "")
    match = DIM_PAIR_RE.search(s)
    if not match:
        return None
    width_text, height_text = match.groups()
    return parse_de_to_mm(width_text), parse_de_to_mm(height_text)


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
                        if not raw or len(raw) < 6:
                            continue
                        raw_id = (raw[1] or "").strip() if len(raw) > 1 and raw[1] else ""
                        if not ID_RE.match(raw_id):
                            continue

                        qty_text = str(raw[3] or "").strip() if len(raw) > 3 else ""
                        width_text = str(raw[4] or "").strip() if len(raw) > 4 else ""
                        height_text = str(raw[5] or "").strip() if len(raw) > 5 else ""
                        combined_dim = ""
                        if len(raw) > 17 and raw[17]:
                            combined_dim = str(raw[17]).strip()

                        pair = parse_dimension_pair(combined_dim)
                        if pair:
                            width_mm, height_mm = pair
                        else:
                            width_mm = parse_de_to_mm(width_text)
                            height_mm = parse_de_to_mm(height_text)

                        if not qty_text:
                            continue
                        qty = int(float(qty_text.replace(",", ".")))

                        floor = (raw[0] or "").strip() if len(raw) > 0 and raw[0] else ""
                        room_no = (raw[8] or "").strip() if len(raw) > 8 and raw[8] else ""
                        room_name = (raw[9] or "").strip() if len(raw) > 9 and raw[9] else ""
                        construction_type = (raw[2] or "").strip() if len(raw) > 2 and raw[2] else "Unbekannt"
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
                            "room_name": room_name.replace("\n", " ").strip(),
                            "type": construction_type or "Unbekannt",
                            "description": rohbau_text(width_mm, height_mm),
                            "raw_dimension_text": combined_dim or rohbau_text(width_mm, height_mm),
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
                "page": row["page"],
                "table": row["table"],
                "id": "",
                "house": "MIX",
                "floor": "",
                "qty": 0,
                "width_mm": key[0],
                "height_mm": key[1],
                "room_no": "",
                "room_name": "",
                "type": row["type"],
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
        if row["id"] in seen_ids and row["id"] and not row["id"].startswith("AGG-"):
            warnings.append(f"Doppelte ID gefunden: {row['id']}")
        seen_ids.add(row["id"])
        if row["qty"] < 1:
            warnings.append(f"Ungültige Menge bei {row['id']}: {row['qty']}")
        if not (300 <= row["width_mm"] <= 6000):
            warnings.append(f"Breite außerhalb Plausibilitätsgrenze bei {row['id']}: {row['width_mm']} mm")
        if not (300 <= row["height_mm"] <= 6000):
            warnings.append(f"Höhe außerhalb Plausibilitätsgrenze bei {row['id']}: {row['height_mm']} mm")
    return warnings


def clear_input_block(ws, start_row: int, end_row: int) -> None:
    for row in range(start_row, end_row + 1):
        for col in ("I", "J", "K", "L", "M"):
            ws[f"{col}{row}"].value = None


def find_footer_row(ws, default_row: int = 35) -> int:
    for row in range(default_row, ws.max_row + 1):
        for col in FOOTER_SEARCH_COLS:
            value = ws[f"{col}{row}"].value
            if isinstance(value, str) and value.strip() in FOOTER_MARKERS:
                return row
    return default_row


def copy_cell(source, target, target_row: int | None = None):
    target._style = copy(source._style)
    target.font = copy(source.font)
    target.fill = copy(source.fill)
    target.border = copy(source.border)
    target.alignment = copy(source.alignment)
    target.protection = copy(source.protection)
    target.number_format = source.number_format
    value = source.value
    if isinstance(value, str) and value.startswith("=") and target_row is not None:
        target.value = Translator(value, origin=source.coordinate).translate_formula(target.coordinate)
    else:
        target.value = value


def snapshot_rows(ws, start_row: int, end_row: int) -> list[dict]:
    snapshot = []
    for row in range(start_row, end_row + 1):
        row_data = {
            "row": row,
            "height": ws.row_dimensions[row].height,
            "cells": []
        }
        for col in range(1, ws.max_column + 1):
            cell = ws._cells.get((row, col))
            if isinstance(cell, MergedCell):
                continue
            if cell is None:
                cell = ws.cell(row, col)
            row_data["cells"].append({
                "column": col,
                "value": cell.value,
                "style": copy(cell._style),
                "font": copy(cell.font),
                "fill": copy(cell.fill),
                "border": copy(cell.border),
                "alignment": copy(cell.alignment),
                "protection": copy(cell.protection),
                "number_format": cell.number_format,
            })
        snapshot.append(row_data)
    return snapshot


def restore_rows_translated(ws, snapshot: list[dict], row_offset: int) -> None:
    for row_data in snapshot:
        source_row = row_data["row"]
        target_row = source_row + row_offset
        ws.row_dimensions[target_row].height = row_data["height"]
        for cell_data in row_data["cells"]:
            target_cell = ws.cell(target_row, cell_data["column"])
            target_cell._style = copy(cell_data["style"])
            target_cell.font = copy(cell_data["font"])
            target_cell.fill = copy(cell_data["fill"])
            target_cell.border = copy(cell_data["border"])
            target_cell.alignment = copy(cell_data["alignment"])
            target_cell.protection = copy(cell_data["protection"])
            target_cell.number_format = cell_data["number_format"]
            value = cell_data["value"]
            if isinstance(value, str) and value.startswith("="):
                target_cell.value = Translator(value, origin=f"{target_cell.column_letter}{source_row}").translate_formula(f"{target_cell.column_letter}{target_row}")
            else:
                target_cell.value = value


def clone_import_formula_row(ws, source_row: int, target_row: int) -> None:
    ws.row_dimensions[target_row].height = ws.row_dimensions[source_row].height
    for col in range(8, 20):  # H:S
        source = ws.cell(source_row, col)
        target = ws.cell(target_row, col)
        copy_cell(source, target, target_row=target_row)


def populate_report_sheet(wb, rows: list[dict], warnings: list[str], source_pdf: str, house_mode: str, aggregate: bool):
    if "Import_PDF" in wb.sheetnames:
        del wb["Import_PDF"]
    report = wb.create_sheet("Import_PDF")
    report["A1"] = "Importbericht"
    report["A2"] = "Quelle PDF"
    report["B2"] = source_pdf
    report["A3"] = "Haus-Modus"
    report["B3"] = house_mode
    report["A4"] = "Aggregation"
    report["B4"] = "Ja" if aggregate else "Nein"
    report["A5"] = "Zeitstempel"
    report["B5"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report["A7"] = "Warnungen"
    report["B7"] = len(warnings)
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
        report[f"A{row_cursor}"] = "OK"
        report[f"B{row_cursor}"] = "Keine Warnungen"
        row_cursor += 2
    row_cursor += 1
    headers = ["ID", "Haus", "Geschoss", "Menge", "Breite_mm", "Höhe_mm", "Rohbauöffnung", "Typ", "Raumnr.", "Raumname"]
    for idx, header in enumerate(headers, start=1):
        report.cell(row_cursor, idx).value = header
    row_cursor += 1
    for item in rows:
        vals = [
            item["id"], item["house"], item["floor"], item["qty"], item["width_mm"], item["height_mm"],
            item["description"], item["type"], item["room_no"], item["room_name"]
        ]
        for idx, val in enumerate(vals, start=1):
            report.cell(row_cursor, idx).value = val
        row_cursor += 1
    for col in ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J"):
        report.column_dimensions[col].width = 18


def write_to_template(excel_bytes: bytes, rows: list[dict], warnings: list[str], source_pdf_name: str, house_mode: str, aggregate: bool) -> bytes:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(excel_bytes)
        tmp_path = tmp.name
    try:
        wb = load_workbook(tmp_path)
        if "Tabelle1" not in wb.sheetnames:
            raise ValueError("Arbeitsblatt 'Tabelle1' wurde in der Vorlage nicht gefunden.")
        ws = wb["Tabelle1"]

        start_row = 4
        original_footer_row = find_footer_row(ws)
        original_import_capacity = original_footer_row - start_row
        rows_needed = max(len(rows), 1)
        insert_count = max(0, rows_needed - original_import_capacity)

        if insert_count:
            footer_snapshot = snapshot_rows(ws, original_footer_row, ws.max_row)
            ws.insert_rows(original_footer_row, insert_count)
            restore_rows_translated(ws, footer_snapshot, insert_count)
            for extra_row in range(original_footer_row, original_footer_row + insert_count):
                clone_import_formula_row(ws, extra_row - 1, extra_row)

        footer_row = original_footer_row + insert_count
        last_needed_row = start_row + rows_needed - 1

        clear_input_block(ws, start_row, footer_row - 1)

        for idx, r in enumerate(rows):
            excel_row = start_row + idx
            ws[f"I{excel_row}"].value = r["id"]
            ws[f"J{excel_row}"].value = r["qty"]
            ws[f"K{excel_row}"].value = r["width_mm"]
            ws[f"L{excel_row}"].value = r["height_mm"]
            ws[f"M{excel_row}"].value = r["description"]

        # Update summary row formulas
        ws[f"O{footer_row}"] = f"=SUM(O{start_row}:O{last_needed_row})"
        ws[f"Q{footer_row}"] = f"=SUM(Q{start_row}:Q{last_needed_row})"
        ws[f"S{footer_row}"] = f"=SUM(S{start_row}:S{last_needed_row})"

        # Keep following blank import rows visually clean
        for row in range(last_needed_row + 1, footer_row):
            for col in ("I", "J", "K", "L", "M"):
                ws[f"{col}{row}"].value = None

        ws.column_dimensions["I"].width = max(ws.column_dimensions["I"].width or 8, 16)
        ws.column_dimensions["J"].width = max(ws.column_dimensions["J"].width or 8, 8)
        ws.column_dimensions["K"].width = max(ws.column_dimensions["K"].width or 8, 12)
        ws.column_dimensions["L"].width = max(ws.column_dimensions["L"].width or 8, 12)
        ws.column_dimensions["M"].width = max(ws.column_dimensions["M"].width or 8, 22)

        populate_report_sheet(wb, rows, warnings, source_pdf_name, house_mode, aggregate)
        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def preview_data(pdf_bytes: bytes, house_mode: str, aggregate: bool) -> dict:
    rows = extract_rows_from_pdf(pdf_bytes)
    rows = filter_rows(rows, house_mode)
    if aggregate:
        rows = aggregate_rows(rows)
    warnings = validate_rows(rows)
    return {"rows": rows, "warnings": warnings, "count": len(rows)}
