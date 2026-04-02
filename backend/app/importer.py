
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
DIM_PAIR_RE = re.compile(r"(\d+(?:,\d+)?)\s*[×x]\s*(\d+(?:,\d+)?)")
MM = 1000

# Template anchors
INPUT_START = 4
INPUT_LAST_ORIG = 34
INPUT_SUMMARY_ORIG = 35

LOWER1_SUMROW_ORIG = 48
LOWER1_HEADER_ORIG = 49
LOWER1_SUBHDR_ORIG = 50
LOWER1_START_ORIG = 51
LOWER1_LAST_ORIG = 79
SETTINGS_ORIG = 82

LOWER2_HEADER_ORIG = 90
LOWER2_START_ORIG = 92
LOWER2_LAST_ORIG = 104


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
                        # In these Archicad exports the reliable combined field is usually the last "Rohbauöffnung"
                        for idx in range(len(raw) - 1, -1, -1):
                            value = raw[idx]
                            if value and "×" in str(value):
                                combined_dim = str(value).strip()
                                break

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


def validate_rows(rows: list[dict]) -> list[str]:
    warnings: list[str] = []
    seen_ids: set[str] = set()
    for row in rows:
        if row["id"] in seen_ids and row["id"]:
            warnings.append(f"Doppelte ID gefunden: {row['id']}")
        seen_ids.add(row["id"])
        if row["qty"] < 1:
            warnings.append(f"Ungültige Menge bei {row['id']}: {row['qty']}")
        if not (300 <= row["width_mm"] <= 6000):
            warnings.append(f"Breite außerhalb Plausibilitätsgrenze bei {row['id']}: {row['width_mm']} mm")
        if not (300 <= row["height_mm"] <= 6000):
            warnings.append(f"Höhe außerhalb Plausibilitätsgrenze bei {row['id']}: {row['height_mm']} mm")
    return warnings


def _copy_row_style(ws, src_row: int, dst_row: int, min_col: int = 1, max_col: int | None = None) -> None:
    if max_col is None:
        max_col = ws.max_column
    ws.row_dimensions[dst_row].height = ws.row_dimensions[src_row].height
    for col in range(min_col, max_col + 1):
        src = ws.cell(src_row, col)
        dst = ws.cell(dst_row, col)
        dst._style = copy(src._style)
        dst.font = copy(src.font)
        dst.fill = copy(src.fill)
        dst.border = copy(src.border)
        dst.alignment = copy(src.alignment)
        dst.protection = copy(src.protection)
        dst.number_format = src.number_format
        if not isinstance(src.value, str) or not src.value.startswith("="):
            dst.value = src.value
        else:
            dst.value = None


def _unmerge_intersecting_rows(ws, start_row: int, end_row: int) -> None:
    for merged in list(ws.merged_cells.ranges):
        if merged.min_row <= end_row and merged.max_row >= start_row:
            try:
                ws.unmerge_cells(str(merged))
            except Exception:
                if merged in ws.merged_cells.ranges:
                    ws.merged_cells.ranges.remove(merged)


def _clear_range(ws, start_row: int, end_row: int, min_col: int, max_col: int) -> None:
    if end_row < start_row:
        return
    for row in range(start_row, end_row + 1):
        for col in range(min_col, max_col + 1):
            ws.cell(row, col).value = None


def populate_report_sheet(wb, rows: list[dict], warnings: list[str], source_pdf: str):
    if "Import_PDF" in wb.sheetnames:
        del wb["Import_PDF"]
    report = wb.create_sheet("Import_PDF")
    report["A1"] = "Importbericht"
    report["A2"] = "Quelle PDF"
    report["B2"] = source_pdf
    report["A3"] = "Zeitstempel"
    report["B3"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report["A5"] = "Warnungen"
    report["B5"] = len(warnings)

    warn_fill = PatternFill(fill_type="solid", fgColor="FFF2CC")
    cursor = 6
    if warnings:
        for warning in warnings:
            report[f"A{cursor}"] = "WARN"
            report[f"B{cursor}"] = warning
            report[f"A{cursor}"].fill = warn_fill
            report[f"B{cursor}"].fill = warn_fill
            cursor += 1
    else:
        report[f"A{cursor}"] = "OK"
        report[f"B{cursor}"] = "Keine Warnungen"
        cursor += 2

    cursor += 1
    headers = ["ID", "Haus", "Geschoss", "Menge", "Breite_mm", "Höhe_mm", "Rohbauöffnung", "Typ", "Raumnr.", "Raumname"]
    for idx, header in enumerate(headers, start=1):
        report.cell(cursor, idx).value = header
    cursor += 1
    for item in rows:
        values = [
            item["id"], item["house"], item["floor"], item["qty"], item["width_mm"], item["height_mm"],
            item["description"], item["type"], item["room_no"], item["room_name"],
        ]
        for idx, value in enumerate(values, start=1):
            report.cell(cursor, idx).value = value
        cursor += 1
    for col in "ABCDEFGHIJ":
        report.column_dimensions[col].width = 18


def write_to_template(excel_bytes: bytes, rows: list[dict], warnings: list[str], source_pdf_name: str, house_mode: str = "BOTH", aggregate: bool = False) -> bytes:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(excel_bytes)
        tmp_path = tmp.name

    try:
        wb = load_workbook(tmp_path)
        if "Tabelle1" not in wb.sheetnames:
            raise ValueError("Arbeitsblatt 'Tabelle1' wurde in der Vorlage nicht gefunden.")
        ws = wb["Tabelle1"]

        n = len(rows)
        if n < 1:
            raise ValueError("Keine Zeilen zum Importieren vorhanden.")

        # 1) Extend top import area when more rows are needed
        input_capacity = INPUT_LAST_ORIG - INPUT_START + 1
        extra_input = max(0, n - input_capacity)
        if extra_input:
            ws.insert_rows(INPUT_SUMMARY_ORIG, extra_input)
            for row in range(INPUT_LAST_ORIG + 1, INPUT_LAST_ORIG + extra_input + 1):
                _copy_row_style(ws, INPUT_LAST_ORIG, row)

        summary_row = INPUT_SUMMARY_ORIG + extra_input
        lower1_sumrow = LOWER1_SUMROW_ORIG + extra_input
        lower1_header = LOWER1_HEADER_ORIG + extra_input
        lower1_subhdr = LOWER1_SUBHDR_ORIG + extra_input
        lower1_start = LOWER1_START_ORIG + extra_input
        settings_row = SETTINGS_ORIG + extra_input
        lower2_header = LOWER2_HEADER_ORIG + extra_input
        lower2_start = LOWER2_START_ORIG + extra_input

        # 2) Extend first dependent table
        lower1_capacity = LOWER1_LAST_ORIG - LOWER1_START_ORIG + 1
        extra_lower1 = max(0, n - lower1_capacity)
        if extra_lower1:
            ws.insert_rows(settings_row, extra_lower1)
            for row in range(lower1_start + lower1_capacity, lower1_start + lower1_capacity + extra_lower1):
                _copy_row_style(ws, lower1_start, row, 1, 13)

        settings_row += extra_lower1
        lower2_header += extra_lower1
        lower2_start += extra_lower1

        # 3) Extend second dependent table
        lower2_capacity = LOWER2_LAST_ORIG - LOWER2_START_ORIG + 1
        extra_lower2 = max(0, n - lower2_capacity)
        if extra_lower2:
            ws.insert_rows(lower2_start + lower2_capacity, extra_lower2)
            for row in range(lower2_start + lower2_capacity, lower2_start + lower2_capacity + extra_lower2):
                _copy_row_style(ws, lower2_start, row, 1, 17)

        input_last = INPUT_START + n - 1
        lower1_last = lower1_start + n - 1
        lower2_last = lower2_start + n - 1

        # 4) Remove broken merged cells that would swallow dynamic rows
        _unmerge_intersecting_rows(ws, lower1_start, lower1_last)
        _unmerge_intersecting_rows(ws, lower2_start, lower2_last)

        # 5) Fill import area
        _clear_range(ws, INPUT_START, summary_row - 1, 9, 19)  # I:S
        for idx, item in enumerate(rows, start=INPUT_START):
            ws[f"I{idx}"] = item["id"]
            ws[f"J{idx}"] = item["qty"]
            ws[f"K{idx}"] = item["width_mm"] / 1000
            ws[f"L{idx}"] = item["height_mm"] / 1000
            ws[f"M{idx}"] = item["description"]

            # Template logic adjusted for mm inputs
            ws[f"O{idx}"] = f"=(K{idx}*L{idx})*J{idx}"
            ws[f"Q{idx}"] = f"=((K{idx}+L{idx})*2)*J{idx}"
            ws[f"S{idx}"] = f"=((L{idx}*2)+K{idx})"

        # clear spare import rows before the summary row
        if input_last + 1 <= summary_row - 1:
            _clear_range(ws, input_last + 1, summary_row - 1, 9, 19)

        ws[f"O{summary_row}"] = f"=SUM(O{INPUT_START}:O{input_last})"
        ws[f"Q{summary_row}"] = f"=SUM(Q{INPUT_START}:Q{input_last})"
        ws[f"S{summary_row}"] = f"=SUM(S{INPUT_START}:S{input_last})"

        # 6) Rebuild first dependent table completely
        ws[f"C{lower1_sumrow}"] = f"=SUM(C{lower1_start}:C{lower1_last})"
        for row in range(lower1_start, lower1_last + 1):
            _copy_row_style(ws, lower1_start, row, 1, 13)
            src = INPUT_START + (row - lower1_start)
            ws[f"A{row}"] = f"=I{src}"
            ws[f"B{row}"] = f"=M{src}"
            ws[f"C{row}"] = f"=J{src}"
            ws[f"D{row}"] = f"=K{src}*1000"
            ws[f"E{row}"] = f"=L{src}*1000"
            ws[f"F{row}"] = None
            ws[f"G{row}"] = 0
            ws[f"H{row}"] = None
            ws[f"I{row}"] = f"=H{row}*$B$37"
            ws[f"J{row}"] = 0
            ws[f"K{row}"] = 0
            ws[f"L{row}"] = 0
            ws[f"M{row}"] = 0

        # clear spare rows between end of first table and settings block
        if lower1_last + 1 < settings_row:
            _clear_range(ws, lower1_last + 1, settings_row - 1, 1, 17)

        # 7) Rebuild second dependent table completely
        # Settings references are fixed relative to the shifted settings block
        # Width calc column Q in template depends on Q{settings_row}, Q{settings_row+2}, Q{settings_row+3}
        for row in range(lower2_start, lower2_last + 1):
            _copy_row_style(ws, lower2_start, row, 1, 17)
            src = lower1_start + (row - lower2_start)
            ws[f"A{row}"] = f"=A{src}"
            ws[f"B{row}"] = f"=B{src}"
            ws[f"C{row}"] = f"=C{src}"
            ws[f"D{row}"] = f"=D{src}+24"
            ws[f"E{row}"] = f"=SUM($C${settings_row+1}:$D${settings_row+4})+40"
            ws[f"F{row}"] = 30
            ws[f"L{row}"] = f"=A{src}"
            ws[f"M{row}"] = f"=C{src}"
            ws[f"Q{row}"] = f"=(D{src}-(Q{settings_row}+Q{settings_row+2}))-Q{settings_row+3}"

        populate_report_sheet(wb, rows, warnings, source_pdf_name)
        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()
    finally:
        Path(tmp_path).unlink(missing_ok=True)
