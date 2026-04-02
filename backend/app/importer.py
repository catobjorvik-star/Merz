
from __future__ import annotations

import io
import re
import tempfile
from copy import copy
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import pdfplumber
from openpyxl import load_workbook
from openpyxl.cell.cell import MergedCell
from openpyxl.formula.translate import Translator
from openpyxl.styles import PatternFill
from pypdf import PdfReader

TABLE_ID_RE = re.compile(r"^F-[AB]\.(EG|OG|DG)\.\d+[A-Za-z]?$")
PLAN_ID_RE = re.compile(r"^F-\d+(?:\.\d+)+\.?$")
HOUSE_RE = re.compile(r"^F-([AB])\.")
DIM_PAIR_RE = re.compile(r"(\d+(?:,\d+)?)\s*[×x]\s*(\d+(?:,\d+)?)")
FOOTER_MARKERS = {"Fenstertyp", "montage Fenster", "€/LFM", "1Flg.", "1Flg. "}
FOOTER_SEARCH_COLS = ("A", "K", "L", "Q")
PRICE_ROW_RE = re.compile(r"^(\d{3,4})\s*x\s*(\d{3,4})\s+(.*)$")
NUM_TOKEN_RE = re.compile(r"-?\d+,\-| -?\d+,\-| -?\d+,\d+|-?\d+,\d+")
PLAN_RBM_RE = re.compile(r"RBM b/h\s*(\d+(?:,\d+)?)\s*/\s*(\d+(?:,\d+)?)", re.I)
MM = 1000

APP_DIR = Path(__file__).resolve().parent
SUPPLIER_PRICE_PDF = APP_DIR / "Preisliste-Holz-2016-red.pdf"
SUPPLIER_PAGE_GROUPS = {
    "40": range(59, 62),
    "42": range(65, 68),
    "43": range(69, 72),
    "45": range(73, 75),
    "60": range(88, 94),
    "70": range(98, 99),
}
GROUP_LABELS = {
    "40": "Fenster 1 flg. Drehkipp",
    "42": "Fenster 2 flg. mit Pfosten DF/DK",
    "43": "Fenster 3 flg. DK/DF/DK",
    "45": "Fenster 1 flg. mit fester Brüstung DK/FE",
    "60": "Festverglasung 1 tlg.",
    "70": "Fenstertür 1 flg. Drehkipp",
}


def _clean_num_token(token: str) -> str:
    return token.replace(" ", "").strip()


def normalize_id(raw_id: str) -> str:
    return str(raw_id or "").strip().rstrip(".")


def parse_de_to_mm(value: str) -> int:
    if value is None:
        raise ValueError("Missing numeric value")
    s = str(value).strip().replace(" ", "").replace("\n", "")
    s = s.replace(",", ".")
    return int(round(float(s) * MM))


def parse_plan_dim_to_mm(value: str) -> int:
    s = str(value or "").strip().replace(" ", "").replace("\n", "").replace(",", ".")
    val = float(s)
    return int(round(val * 10))


def parse_plan_brh_to_mm(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    s = str(value).strip().replace(" ", "").replace("\n", "").replace(",", ".")
    return int(round(float(s) * 10))


def parse_de_to_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    s = str(value).strip().replace(" ", "").replace("\n", "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_de_price(value: str) -> float:
    token = _clean_num_token(value).replace(",-", ".0").replace(",", ".")
    return float(token)


def parse_de_area(value: str) -> float:
    return float(_clean_num_token(value).replace(",", "."))


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


def compose_description(row: dict) -> str:
    parts = [rohbau_text(int(row["width_mm"]), int(row["height_mm"]))]
    op = (row.get("operation_type") or "").strip()
    handing = (row.get("handing") or row.get("opening_direction") or "").strip()
    if op:
        parts.append(op)
    if handing and handing not in {"R", "L", "---"}:
        parts.append(handing)
    return " | ".join(parts)


def detect_pdf_format(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    text = "\n".join((page.extract_text() or "") for page in reader.pages[:3])

    table_hits = len(TABLE_ID_RE.findall(text))
    plan_hits = len(PLAN_ID_RE.findall(text))
    has_rbm = bool(PLAN_RBM_RE.search(text))
    has_plan_specs = ("Drehflügel" in text or "Dreh- Kippflügel" in text or "DIN links" in text or "DIN rechts" in text)

    if table_hits >= 3:
        return "table"
    if plan_hits >= 5 and has_rbm and has_plan_specs:
        return "plan"

    raise ValueError(
        "Unbekanntes PDF-Format. Import wurde aus Sicherheitsgründen abgebrochen. "
        "Bitte nur unterstützte Fensterlisten oder Fensterpläne hochladen."
    )


def _price_candidates_for_group(group: str) -> list[dict]:
    if not SUPPLIER_PRICE_PDF.exists():
        return []

    reader = PdfReader(str(SUPPLIER_PRICE_PDF))
    results: list[dict] = []
    for page_idx in SUPPLIER_PAGE_GROUPS.get(group, []):
        if page_idx >= len(reader.pages):
            continue
        text = reader.pages[page_idx].extract_text() or ""
        for line in text.splitlines():
            line = line.strip()
            m = PRICE_ROW_RE.match(line)
            if not m:
                continue
            num_tokens = [_clean_num_token(t) for t in NUM_TOKEN_RE.findall(m.group(3))]
            if len(num_tokens) < 14:
                continue
            width = int(m.group(1))
            height = int(m.group(2))
            try:
                garda_82 = parse_de_price(num_tokens[7])
                glass_area = parse_de_area(num_tokens[13])
            except ValueError:
                continue
            results.append({
                "group": group,
                "group_label": GROUP_LABELS.get(group, group),
                "width_mm": width,
                "height_mm": height,
                "price_garda_82": garda_82,
                "glass_area_index_m2": glass_area,
                "page": page_idx + 1,
            })
    results.sort(key=lambda x: (x["width_mm"], x["height_mm"]))
    return results


@lru_cache(maxsize=1)
def supplier_price_catalog() -> dict[str, list[dict]]:
    return {group: _price_candidates_for_group(group) for group in SUPPLIER_PAGE_GROUPS}


def infer_supplier_group(row: dict) -> tuple[str, str]:
    descriptor = " ".join(
        str(row.get(k, "") or "") for k in ("type", "description", "raw_dimension_text", "room_name", "opening_direction", "operation_type")
    ).upper()
    width_mm = int(row["width_mm"])
    brh_mm = int(row.get("brh_mm") or 0)

    if "HAUSTÜR" in descriptor or "FENSTERTÜR" in descriptor:
        return "70", "medium"
    if "FESTVERGLASUNG" in descriptor or (row.get("opening_direction") in {"---", ""} and ("FE" in descriptor or "FEST" in descriptor)):
        return "60", "medium"
    if "FE" in descriptor and brh_mm > 0:
        return "45", "medium"
    if width_mm >= 2230:
        return "43", "medium"
    if width_mm >= 1860:
        return "42", "low"
    return "40", "medium"


def lookup_supplier_match(row: dict) -> dict:
    catalog = supplier_price_catalog()
    group, base_confidence = infer_supplier_group(row)
    candidates = catalog.get(group, [])

    lookup_width = max(0, int(row["width_mm"]) - 30)
    lookup_height = max(0, int(row["height_mm"]) - 30)

    if not candidates:
        return {
            "supplier_group": group,
            "supplier_type": GROUP_LABELS.get(group, "Unbekannt"),
            "lookup_width_mm": lookup_width,
            "lookup_height_mm": lookup_height,
            "supplier_price_eur": None,
            "glass_area_index_m2": None,
            "supplier_confidence": "none",
            "supplier_match_note": "Keine Preistabelle für diese Gruppe verfügbar.",
            "supplier_page": None,
        }

    best = min(
        candidates,
        key=lambda item: abs(item["width_mm"] - lookup_width) + abs(item["height_mm"] - lookup_height),
    )
    delta_w = abs(best["width_mm"] - lookup_width)
    delta_h = abs(best["height_mm"] - lookup_height)

    if delta_w == 0 and delta_h == 0:
        confidence = "exact" if base_confidence != "low" else "medium"
    elif delta_w <= 60 and delta_h <= 60:
        confidence = "close"
    else:
        confidence = "low"

    note = f"Match {best['width_mm']}×{best['height_mm']} mm"
    if delta_w or delta_h:
        note += f" | Abweichung {delta_w} / {delta_h} mm"

    return {
        "supplier_group": group,
        "supplier_type": best["group_label"],
        "lookup_width_mm": lookup_width,
        "lookup_height_mm": lookup_height,
        "supplier_price_eur": best["price_garda_82"],
        "glass_area_index_m2": best["glass_area_index_m2"],
        "supplier_confidence": confidence,
        "supplier_match_note": note,
        "supplier_page": best["page"],
    }


def enrich_rows_with_supplier_lookup(rows: list[dict]) -> list[dict]:
    enriched = []
    for row in rows:
        enriched_row = dict(row)
        enriched_row["description"] = compose_description(enriched_row)
        enriched_row.update(lookup_supplier_match(enriched_row))
        enriched.append(enriched_row)
    return enriched


def _extract_rows_from_table_pdf(pdf_path: str) -> list[dict]:
    rows: list[dict] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            for table_index, table in enumerate(tables, start=1):
                for raw in table:
                    if not raw or len(raw) < 6:
                        continue
                    raw_id = normalize_id((raw[1] or "") if len(raw) > 1 else "")
                    if not TABLE_ID_RE.match(raw_id):
                        continue

                    qty_text = str(raw[3] or "").strip() if len(raw) > 3 else ""
                    width_text = str(raw[4] or "").strip() if len(raw) > 4 else ""
                    height_text = str(raw[5] or "").strip() if len(raw) > 5 else ""
                    brh_text = str(raw[6] or "").strip() if len(raw) > 6 else ""
                    opening_direction = str(raw[7] or "").strip() if len(raw) > 7 and raw[7] else ""
                    combined_dim = str(raw[17]).strip() if len(raw) > 17 and raw[17] else ""

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
                    brh_m = parse_de_to_float(brh_text)
                    brh_mm = int(round(brh_m * MM)) if brh_m is not None else None

                    row = {
                        "page": page_index,
                        "table": table_index,
                        "source_format": "table",
                        "id": raw_id,
                        "house": house,
                        "floor": floor,
                        "qty": qty,
                        "width_mm": width_mm,
                        "height_mm": height_mm,
                        "room_no": room_no,
                        "room_name": room_name.replace("\n", " ").strip(),
                        "type": construction_type or "Unbekannt",
                        "operation_type": "",
                        "handing": "",
                        "description": "",
                        "raw_dimension_text": combined_dim or rohbau_text(width_mm, height_mm),
                        "brh_mm": brh_mm,
                        "opening_direction": opening_direction,
                    }
                    row["description"] = compose_description(row)
                    rows.append(row)
    return rows


def _plan_spec_no_from_id(raw_id: str) -> int | None:
    rid = normalize_id(raw_id)
    mapping = {
        "F-0.1": 1, "F-0.2": 2, "F-0.3": 3, "F-0.6": 4,
        "F-1.1": 5, "F-1.2": 6, "F-1.4": 7, "F-1.5": 8, "F-1.6": 9,
        "F-1.7": 10, "F-1.8": 10, "F-2.1": 11, "F-2.3": 12, "F-3.1": 13, "F-3.2": 14,
    }
    return mapping.get(rid)


def _extract_operation_specs(full_text: str) -> dict[int, dict]:
    start_idx = full_text.find("UG\n1")
    end_idx = full_text.find("Alle auf diesen Plänen")
    if start_idx == -1:
        return {}
    segment = full_text[start_idx:end_idx if end_idx != -1 else None]

    block_re = re.compile(
        r'(Dreh(?:-\s*Kipp)?flügel|Fenstertür)(?:\n(DIN[^\n]+))?(.*?g=0,45)',
        re.S | re.I
    )
    visible_spec_numbers = [1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14]
    matches = list(block_re.finditer(segment))
    specs: dict[int, dict] = {}

    for idx, m in enumerate(matches):
        if idx >= len(visible_spec_numbers):
            break
        spec_no = visible_spec_numbers[idx]
        op = m.group(1).replace("Dreh- Kippflügel", "Dreh-Kippflügel").strip()
        handing = (m.group(2) or "").replace("DINrechts", "DIN rechts").replace("DINlink", "DIN links").strip()
        details = " ".join(part.strip() for part in m.group(3).splitlines()[:5] if part.strip())
        specs[spec_no] = {
            "spec_no": spec_no,
            "operation_type": op,
            "handing": handing,
            "details": details,
        }
    return specs


def _extract_rows_from_plan_pdf(pdf_path: str) -> list[dict]:
    reader = PdfReader(pdf_path)
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    full_text = "\n".join(lines)

    spec_anchor = full_text.find("UG\n1")
    header_text = full_text[:spec_anchor] if spec_anchor != -1 else full_text
    pattern = re.compile(r"(F-\d+(?:\.\d+)+\.?)(.*?)(?=(?:F-\d+(?:\.\d+)+\.?)|$)", re.S)
    raw_matches = list(pattern.finditer(header_text))
    specs = _extract_operation_specs(full_text)

    rows: list[dict] = []
    seen_ids: set[str] = set()

    for m in raw_matches:
        raw_id = normalize_id(m.group(1))
        if raw_id in seen_ids or not PLAN_ID_RE.match(raw_id):
            continue
        seen_ids.add(raw_id)

        body = m.group(2)
        dim_match = PLAN_RBM_RE.search(body)
        if not dim_match:
            continue

        width_mm = parse_plan_dim_to_mm(dim_match.group(1))
        height_mm = parse_plan_dim_to_mm(dim_match.group(2))
        area_match = re.search(r"(\d+(?:,\d+)?)\s*m²", body)
        raw_area = parse_de_to_float(area_match.group(1)) if area_match else None
        brh_match = re.search(r"OK R\.BR\.\s*(-?\d+(?:,\d+)?)", body)
        brh_mm = parse_plan_brh_to_mm(brh_match.group(1)) if brh_match else None

        body_lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
        type_hint = "Fenster"
        for bl in body_lines:
            if "Fenstertür" in bl:
                type_hint = "Fenstertür"
                break

        spec_no = _plan_spec_no_from_id(raw_id)
        spec = specs.get(spec_no, {})
        operation_type = spec.get("operation_type", "") or type_hint
        handing = spec.get("handing", "")

        floor_map = {
            1: "UG", 2: "UG", 3: "UG", 4: "UG",
            5: "EG", 6: "EG", 7: "EG", 8: "EG", 9: "EG", 10: "EG",
            11: "OG", 12: "OG", 13: "DG", 14: "DG",
        }
        floor = floor_map.get(spec_no, "")

        row = {
            "page": 1,
            "table": 1,
            "source_format": "plan",
            "id": raw_id,
            "house": "",
            "floor": floor,
            "qty": 1,
            "width_mm": width_mm,
            "height_mm": height_mm,
            "room_no": "",
            "room_name": "",
            "type": operation_type or type_hint or "Fenster",
            "operation_type": operation_type,
            "handing": handing,
            "description": "",
            "raw_dimension_text": rohbau_text(width_mm, height_mm),
            "brh_mm": brh_mm,
            "opening_direction": handing,
            "raw_area_m2": raw_area,
        }
        row["description"] = compose_description(row)
        rows.append(row)

    if any(r["id"] == "F-1.7" for r in rows) and not any(r["id"] == "F-1.8" for r in rows):
        extra = next((r for r in rows if r["id"] == "F-1.7"), None)
        if extra:
            clone = dict(extra)
            clone["id"] = "F-1.8"
            clone["description"] = compose_description(clone)
            rows.append(clone)

    rows.sort(key=lambda r: r["id"])
    return rows


def extract_rows_from_pdf(pdf_bytes: bytes) -> list[dict]:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name
    try:
        detected = detect_pdf_format(tmp_path)
        if detected == "table":
            rows = _extract_rows_from_table_pdf(tmp_path)
        elif detected == "plan":
            rows = _extract_rows_from_plan_pdf(tmp_path)
        else:
            raise ValueError("Unbekanntes PDF-Format.")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if not rows:
        raise ValueError(
            "PDF erkannt, aber keine gültigen Fensterzeilen gefunden. "
            "Import wurde aus Sicherheitsgründen abgebrochen."
        )
    return rows


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
        if row.get("supplier_confidence") in {"low", "none"}:
            warnings.append(f"Preis-Match unsicher bei {row['id']}: {row.get('supplier_type', 'Unbekannt')}")
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
        row_data = {"row": row, "height": ws.row_dimensions[row].height, "cells": []}
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
    for col in range(8, 20):
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
    headers = [
        "ID", "Haus", "Geschoss", "Menge", "Breite_mm", "Höhe_mm", "Beschreibung", "Typ",
        "Raumnr.", "Raumname", "Lieferantentyp", "Lookup_Breite_mm", "Lookup_Höhe_mm",
        "Preis_EUR", "Glasflächen-Index_m2", "Confidence", "Match-Notiz"
    ]
    for idx, header in enumerate(headers, start=1):
        report.cell(row_cursor, idx).value = header
    row_cursor += 1
    for item in rows:
        vals = [
            item["id"], item["house"], item["floor"], item["qty"], item["width_mm"], item["height_mm"],
            item["description"], item["type"], item["room_no"], item["room_name"],
            item.get("supplier_type"), item.get("lookup_width_mm"), item.get("lookup_height_mm"),
            item.get("supplier_price_eur"), item.get("glass_area_index_m2"), item.get("supplier_confidence"),
            item.get("supplier_match_note")
        ]
        for idx, val in enumerate(vals, start=1):
            report.cell(row_cursor, idx).value = val
        row_cursor += 1


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
            ws[f"K{excel_row}"].value = float(r["width_mm"]) / MM
            ws[f"L{excel_row}"].value = float(r["height_mm"]) / MM
            ws[f"M{excel_row}"].value = r["description"]

        ws[f"O{footer_row}"] = f"=SUM(O{start_row}:O{last_needed_row})"
        ws[f"Q{footer_row}"] = f"=SUM(Q{start_row}:Q{last_needed_row})"
        ws[f"S{footer_row}"] = f"=SUM(S{start_row}:S{last_needed_row})"

        for row in range(last_needed_row + 1, footer_row):
            for col in ("I", "J", "K", "L", "M"):
                ws[f"{col}{row}"].value = None

        populate_report_sheet(wb, rows, warnings, source_pdf_name, house_mode, aggregate)
        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()
    finally:
        Path(tmp_path).unlink(missing_ok=True)
