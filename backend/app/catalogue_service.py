from __future__ import annotations

import ast
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import fitz

APP_DIR = Path(__file__).resolve().parent
SNAPSHOT_PATH = APP_DIR / "catalogue_snapshot.json"
PDF_PATH = APP_DIR / "Preisliste-Holz-2016-red.pdf"
HTML_DEMO_PATH = APP_DIR / "test.html"

CATEGORY_MAP = [
    ("Fenster 1-flg.", {"40", "44", "45", "46", "50"}),
    ("Fenster 2-flg.", {"41", "42", "47", "48", "51"}),
    ("Fenster 3-flg.", {"43"}),
    ("Festverglasungen", {"60", "61"}),
    ("Fenstertüren", {"70", "71", "72", "73", "74", "75"}),
    ("PSK / Schieben", {"76", "77", "78"}),
    ("Hebeschiebetüren", {"80"}),
    ("Sonderformen", {"85", "90", "91", "92", "93", "95"}),
    ("Holzarten / Oberflächen / Zubehör", {"10", "11", "12", "13", "14", "15", "16", "17"}),
    ("Systeme / Details", {"2", "3", "4", "5", "6", "7", "8", "9"}),
]


def clean_space(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def resolve_category(code: str) -> str:
    for name, codes in CATEGORY_MAP:
        if code in codes:
            return name
    return "Sonstiges"


def parse_toc(text: str) -> list[dict[str, Any]]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    entries: list[dict[str, Any]] = []
    i = 0
    while i < len(lines):
        if re.fullmatch(r"\d{1,2}", lines[i]):
            code = lines[i]
            j = i + 1
            title_parts: list[str] = []
            while j < len(lines) and not re.search(r"\d+\.\d+", lines[j]):
                title_parts.append(lines[j])
                j += 1
            if j < len(lines):
                entries.append(
                    {
                        "group_code": code,
                        "title": clean_space(" ".join(title_parts)),
                        "page_range": clean_space(lines[j]),
                    }
                )
                i = j + 1
                continue
        i += 1
    return entries


def find_pricing_page(texts: list[str], group_code: str) -> int | None:
    marker = f"Preisliste 2016\n{group_code}."
    for idx, txt in enumerate(texts, start=1):
        if marker in txt:
            return idx
    return None


def parse_price_rows(text: str) -> list[dict[str, Any]]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    rows: list[dict[str, Any]] = []
    i = 0
    while i < len(lines):
        if re.fullmatch(r"\d{3,4} x \d{3,4}", lines[i]):
            dims = lines[i]
            j = i + 1
            vals: list[str] = []
            while j < len(lines) and not re.fullmatch(r"\d{3,4} x \d{3,4}", lines[j]):
                token = lines[j].replace(" ", "")
                if re.fullmatch(r"-?\d+(?:,\d+|,\-)", token):
                    vals.append(token)
                j += 1
            width_mm, height_mm = map(int, dims.split(" x "))
            rows.append(
                {
                    "width_mm": width_mm,
                    "height_mm": height_mm,
                    "raw_values": vals,
                    "glass_area_index_m2": vals[-1] if vals else None,
                    "column_count": len(vals),
                }
            )
            i = j
            continue
        i += 1
    return rows


def parse_page92_html(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    match = re.search(r"const page92Data = \{(.*?)\n    \};", text, re.S)
    if not match:
        return {}
    obj = "{" + match.group(1) + "}"
    obj = obj.replace("null", "None").replace("true", "True").replace("false", "False")
    obj = re.sub(r"(\b[a-zA-Z_][a-zA-Z0-9_]*\b)\s*:", r'"\1":', obj)
    return ast.literal_eval(obj)


def build_snapshot() -> dict[str, Any]:
    if not PDF_PATH.exists():
        return {"catalogue_title": "Strobel Fenster Preisliste 2016", "families": [], "family_count": 0}

    doc = fitz.open(str(PDF_PATH))
    texts = [doc.load_page(i).get_text() for i in range(len(doc))]
    toc = parse_toc(texts[1])
    families: list[dict[str, Any]] = []

    for entry in toc:
        code = entry["group_code"]
        if int(code) < 2:
            continue
        pricing_page = find_pricing_page(texts, code) if int(code) >= 40 else None
        price_rows = parse_price_rows(texts[pricing_page - 1]) if pricing_page else []
        families.append(
            {
                "id": code,
                "code": code,
                "title": entry["title"],
                "page_range": entry["page_range"],
                "category": resolve_category(code),
                "pricing_pdf_page": pricing_page,
                "pricing_row_count": len(price_rows),
                "price_rows": price_rows[:50],
                "description": f"{entry['title']} · Bereich {entry['page_range']}",
                "workflow_hint": (
                    "Kann für Filterung, Auswahl und Exportoptionen im MERZ-Workflow verwendet werden."
                    if int(code) >= 40
                    else "Hilfs- und Zusatzbereich für Materialien, Zubehör oder technische Definitionen."
                ),
            }
        )

    payload = {
        "catalogue_title": "Strobel Fenster Preisliste 2016",
        "source_pdf": PDF_PATH.name,
        "family_count": len(families),
        "families": families,
        "page92_demo": parse_page92_html(HTML_DEMO_PATH),
        "materials": [
            {"label": "Fichte", "note": "Standardholz"},
            {"label": "Lärche", "note": "Mehrpreis / natürliche Optik"},
            {"label": "Meranti", "note": "Alternative Holzart"},
            {"label": "Eiche", "note": "Premium-Holzart"},
        ],
        "systems": [
            {"name": "Klima Futur", "kind": "Holzfenster"},
            {"name": "Garda Futur D", "kind": "Holz-Alu"},
            {"name": "Garda Futur 82", "kind": "Holz-Alu"},
            {"name": "Garda Futur HF", "kind": "Holz-Alu"},
        ],
    }

    try:
        SNAPSHOT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return payload


@lru_cache(maxsize=1)
def get_catalogue_data() -> dict[str, Any]:
    if SNAPSHOT_PATH.exists():
        try:
            return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return build_snapshot()


def search_catalogue(query: str = "", category: str = "Alle") -> dict[str, Any]:
    data = get_catalogue_data()
    q = query.strip().lower()
    families = []
    for item in data.get("families", []):
        matches_category = category == "Alle" or item.get("category") == category
        hay = " ".join([
            item.get("title", ""),
            item.get("description", ""),
            item.get("page_range", ""),
            item.get("category", ""),
            item.get("code", ""),
        ]).lower()
        matches_query = (not q) or (q in hay)
        if matches_category and matches_query:
            families.append(item)
    return {
        "catalogue_title": data.get("catalogue_title"),
        "family_count": len(families),
        "families": families,
        "materials": data.get("materials", []),
        "systems": data.get("systems", []),
        "page92_demo": data.get("page92_demo", {}),
    }


def get_catalogue_family(code: str) -> dict[str, Any] | None:
    data = get_catalogue_data()
    for item in data.get("families", []):
        if item.get("code") == code:
            return item
    return None
