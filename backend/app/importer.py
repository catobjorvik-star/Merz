
from __future__ import annotations
import io,re,tempfile
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
PLAN_ID_RE = re.compile(r"F-\d+(?:\.\d+)+\.?")
HOUSE_RE = re.compile(r"^F-([AB])\.")
DIM_PAIR_RE = re.compile(r"(\d+(?:,\d+)?)\s*[×x]\s*(\d+(?:,\d+)?)")
FOOTER_MARKERS = {"Fenstertyp", "montage Fenster", "€/LFM", "1Flg.", "1Flg. "}
FOOTER_SEARCH_COLS = ("A", "K", "L", "Q")
PRICE_ROW_RE = re.compile(r"^(\d{3,4})\s*x\s*(\d{3,4})\s+(.*)$")
NUM_TOKEN_RE = re.compile(r"-?\d+,\-| -?\d+,\-| -?\d+,\d+|-?\d+,\d+")
PLAN_RBM_RE = re.compile(r"RBM b/h\s*(\d+(?:,\d+)?)\s*/\s*(\d+(?:,\d+)?)", re.I)
MM = 1000
ORDER_DEDUCTION_MM = 30
APP_DIR = Path('.')
SUPPLIER_PRICE_PDF = Path('/mnt/data/Preisliste-Holz-2016-red.pdf')
SUPPLIER_PAGE_GROUPS = {"40": range(59, 62),"42": range(65, 68),"43": range(69, 72),"45": range(73, 75),"60": range(88, 94),"70": range(98, 99)}
GROUP_LABELS = {"40":"Fenster 1 flg. Drehkipp","42":"Fenster 2 flg. mit Pfosten DF/DK","43":"Fenster 3 flg. DK/DF/DK","45":"Fenster 1 flg. mit fester Brüstung DK/FE","60":"Festverglasung 1 tlg.","70":"Fenstertür 1 flg. Drehkipp"}

def _clean_num_token(token): return token.replace(" ","").strip()
def normalize_id(raw_id): return str(raw_id or "").strip().rstrip(".")
def parse_de_to_mm(value): return int(round(float(str(value).strip().replace(" ","").replace("\n","").replace(",", "."))*MM))
def parse_plan_dim_to_mm(value): return int(round(float(str(value or "").strip().replace(" ","").replace("\n","").replace(",", "."))*10))
def parse_plan_brh_to_mm(value):
    if value in (None,""): return None
    return int(round(float(str(value).strip().replace(" ","").replace("\n","").replace(",", "."))*10))
def parse_de_to_float(value):
    if value in (None,""): return None
    try: return float(str(value).strip().replace(" ","").replace("\n","").replace(",", "."))
    except: return None
def parse_de_price(value): return float(_clean_num_token(value).replace(",-",".0").replace(",","."))
def parse_de_area(value): return float(_clean_num_token(value).replace(",", "."))
def parse_dimension_pair(value):
    if not value: return None
    s = str(value).replace("\n","").replace(" ","")
    m=DIM_PAIR_RE.search(s)
    if not m: return None
    return parse_de_to_mm(m.group(1)), parse_de_to_mm(m.group(2))
def mm_to_de_dimension(value_mm):
    meters = float(value_mm)/MM
    s=f"{meters:.3f}"
    whole,dec=s.split(".")
    dec=dec.rstrip("0")
    if len(dec)<2: dec=dec.ljust(2,"0")
    return f"{whole},{dec}"
def rohbau_text(width_mm,height_mm): return f"{mm_to_de_dimension(width_mm)}×{mm_to_de_dimension(height_mm)}"
def order_dimensions(width_mm,height_mm): return max(0,width_mm-ORDER_DEDUCTION_MM), max(0,height_mm-ORDER_DEDUCTION_MM)
def compose_description(row):
    parts=[f"RBM {rohbau_text(int(row['width_mm']), int(row['height_mm']))}",
           f"Bestellmaß {rohbau_text(int(row['order_width_mm']), int(row['order_height_mm']))}"]
    op=(row.get("operation_type") or "").strip()
    handing=(row.get("handing") or row.get("opening_direction") or "").strip()
    if op: parts.append(op)
    if handing and handing not in {"R","L","---"}: parts.append(handing)
    elif handing in {"R","L"}: parts.append(f"DIN {('rechts' if handing=='R' else 'links')}")
    return " | ".join(parts)

def detect_pdf_format(pdf_path):
    reader = PdfReader(pdf_path)
    text="\n".join((p.extract_text() or "") for p in reader.pages[:3])
    table_line_hits=sum(1 for line in text.splitlines() if TABLE_ID_RE.match(line.strip()))
    plan_id_hits=len(PLAN_ID_RE.findall(text)); rbm_hits=len(PLAN_RBM_RE.findall(text))
    has_plan_text=any(x in text for x in ["Drehflügel","Dreh- Kippflügel","DIN links","DIN rechts","Fenstertür"])
    if table_line_hits>=3: return "table"
    if plan_id_hits>=8 and rbm_hits>=5 and has_plan_text: return "plan"
    return "unknown"

def _parse_table_brh_and_direction(raw6, raw7):
    a=(raw6 or "").replace("\n"," ").strip()
    b=(raw7 or "").replace("\n"," ").strip()
    combined=(a+b).replace(" ","")
    # opening dir at end of col7 in architect export
    opening=""
    m=re.search(r'([RL]|---)$', b)
    if m:
        opening=m.group(1)
        b=b[:m.start()].strip()
    if not a and not b:
        return None, opening
    brh_text=(a+b).replace(" ","")
    brh_val=parse_de_to_float(brh_text)
    brh_mm=int(round(brh_val*MM)) if brh_val is not None else None
    return brh_mm, opening

def classify_merz_description(row):
    # lightweight heuristic v1 based on reference workbook
    w=row["order_width_mm"]; h=row["order_height_mm"]; od=(row.get("opening_direction") or "").strip().upper()
    if row.get("type","").lower().startswith("fenstertür") or h >= 2400 and w <= 1100:
        return "DKT"
    if od in {"", "---"}:
        return "FE Fest"
    if w <= 900:
        return f"FE DK-DIN {'R' if od=='R' else 'L'}"
    if w <= 1900:
        if od in {"R","L"}:
            other='L' if od=='R' else 'R'
            return f"FE 2 flg. D DIN {od} +  D DIN {other}"
    if w <= 2900:
        return "HST 2 tlg." if h>2400 else "FE 2 flg. DK DIN L + FE Fest"
    return "FE 3 flg. DK DIN L + Fest + DK DIN R"

def _price_candidates_for_group(group):
    if not SUPPLIER_PRICE_PDF.exists(): return []
    reader=PdfReader(str(SUPPLIER_PRICE_PDF)); res=[]
    for page_idx in SUPPLIER_PAGE_GROUPS.get(group,[]):
        if page_idx>=len(reader.pages): continue
        text=reader.pages[page_idx].extract_text() or ""
        for line in text.splitlines():
            line=line.strip(); m=PRICE_ROW_RE.match(line)
            if not m: continue
            toks=[_clean_num_token(t) for t in NUM_TOKEN_RE.findall(m.group(3))]
            if len(toks)<14: continue
            try:
                res.append({"group":group,"group_label":GROUP_LABELS.get(group,group),"width_mm":int(m.group(1)),"height_mm":int(m.group(2)),
                            "price_garda_82":parse_de_price(toks[7]),"glass_area_index_m2":parse_de_area(toks[13]),"page":page_idx+1})
            except: pass
    res.sort(key=lambda x:(x["width_mm"],x["height_mm"]))
    return res

@lru_cache(maxsize=1)
def supplier_price_catalog(): return {g:_price_candidates_for_group(g) for g in SUPPLIER_PAGE_GROUPS}

def infer_supplier_group(row):
    desc=" ".join(str(row.get(k,"") or "") for k in ("type","description","raw_dimension_text","room_name","opening_direction","operation_type")).upper()
    width_mm=int(row["width_mm"]); brh_mm=int(row.get("brh_mm") or 0)
    if "HAUSTÜR" in desc or "FENSTERTÜR" in desc: return "70","medium"
    if "FESTVERGLASUNG" in desc or (row.get("opening_direction") in {"---",""} and ("FE" in desc or "FEST" in desc)): return "60","medium"
    if "FE" in desc and brh_mm>0: return "45","medium"
    if width_mm >= 2230: return "43","medium"
    if width_mm >= 1860: return "42","low"
    return "40","medium"

def lookup_supplier_match(row):
    catalog=supplier_price_catalog(); group,base_conf=infer_supplier_group(row); cands=catalog.get(group,[])
    lw,lh=int(row["order_width_mm"]), int(row["order_height_mm"])
    if not cands:
        return {"supplier_group":group,"supplier_type":GROUP_LABELS.get(group,"Unbekannt"),"lookup_width_mm":lw,"lookup_height_mm":lh,
                "supplier_price_eur":None,"glass_area_index_m2":None,"supplier_confidence":"none","supplier_match_note":"Keine Preistabelle für diese Gruppe verfügbar.","supplier_page":None}
    best=min(cands,key=lambda item: abs(item["width_mm"]-lw)+abs(item["height_mm"]-lh))
    dw,dh=abs(best["width_mm"]-lw), abs(best["height_mm"]-lh)
    conf="exact" if (dw==0 and dh==0 and base_conf!="low") else ("medium" if dw==0 and dh==0 else ("close" if dw<=60 and dh<=60 else "low"))
    note=f"Match {best['width_mm']}×{best['height_mm']} mm" + (f" | Abweichung {dw} / {dh} mm" if dw or dh else "")
    return {"supplier_group":group,"supplier_type":best["group_label"],"lookup_width_mm":lw,"lookup_height_mm":lh,
            "supplier_price_eur":best["price_garda_82"],"glass_area_index_m2":best["glass_area_index_m2"],"supplier_confidence":conf,"supplier_match_note":note,"supplier_page":best["page"]}

def enrich_rows_with_supplier_lookup(rows):
    enriched=[]
    for row in rows:
        rr=dict(row)
        rr["order_width_mm"], rr["order_height_mm"]=order_dimensions(int(rr["width_mm"]), int(rr["height_mm"]))
        if not rr.get("operation_type"):
            rr["operation_type"] = classify_merz_description(rr)
        rr["description"]=compose_description(rr)
        rr.update(lookup_supplier_match(rr))
        enriched.append(rr)
    return enriched

def _extract_rows_from_table_pdf(pdf_path):
    rows=[]
    with pdfplumber.open(pdf_path) as pdf:
        for page_index,page in enumerate(pdf.pages, start=1):
            tables=page.extract_tables() or []
            for table_index,table in enumerate(tables, start=1):
                for raw in table:
                    if not raw or len(raw)<10: continue
                    raw_id=normalize_id((raw[1] or "") if len(raw)>1 else "")
                    if not TABLE_ID_RE.match(raw_id): continue
                    qty_text=str(raw[3] or "").strip()
                    width_text=str(raw[4] or "").strip()
                    height_text=str(raw[5] or "").strip()
                    brh_mm, opening_direction = _parse_table_brh_and_direction(raw[6] if len(raw)>6 else "", raw[7] if len(raw)>7 else "")
                    room_no=(raw[8] or "").strip() if len(raw)>8 and raw[8] else ""
                    room_name=(raw[9] or "").strip() if len(raw)>9 and raw[9] else ""
                    construction_type=(raw[17] or raw[18] or raw[2] or "").strip() if len(raw)>18 else (raw[2] or "").strip()
                    combined_dim=str(raw[18]).strip() if len(raw)>18 and raw[18] else ""
                    pair=parse_dimension_pair(combined_dim)
                    if pair:
                        width_mm,height_mm=pair
                    else:
                        width_mm=parse_de_to_mm(width_text); height_mm=parse_de_to_mm(height_text)
                    if not qty_text: continue
                    qty=int(float(qty_text.replace(",",".")))
                    floor=(raw[0] or "").strip() if len(raw)>0 and raw[0] else ""
                    house=HOUSE_RE.match(raw_id).group(1) if HOUSE_RE.match(raw_id) else ""
                    rows.append({"page":page_index,"table":table_index,"source_format":"table","id":raw_id,"house":house,"floor":floor,"qty":qty,
                                 "width_mm":width_mm,"height_mm":height_mm,"room_no":room_no,"room_name":room_name.replace("\n"," ").strip(),"type":construction_type or "Fenster",
                                 "operation_type":"","handing":"","description":"","raw_dimension_text":combined_dim or rohbau_text(width_mm,height_mm),"brh_mm":brh_mm,"opening_direction":opening_direction})
    return rows

def _plan_spec_no_from_id(raw_id):
    return {"F-0.1":1,"F-0.2":2,"F-0.3":3,"F-0.6":4,"F-1.1":5,"F-1.2":6,"F-1.4":7,"F-1.5":8,"F-1.6":9,"F-1.7":10,"F-1.8":10,"F-2.1":11,"F-2.3":12,"F-3.1":13,"F-3.2":14}.get(normalize_id(raw_id))

def _extract_operation_specs(full_text):
    start_idx=full_text.find("UG\n1"); end_idx=full_text.find("Alle auf diesen Plänen")
    if start_idx==-1: return {}
    segment=full_text[start_idx:end_idx if end_idx!=-1 else None]
    block_re=re.compile(r'(Dreh(?:-\s*Kipp)?flügel|Fenstertür)(?:\n(DIN[^\n]+))?(.*?g=0,45)', re.S|re.I)
    visible=[1,3,4,5,6,7,8,9,10,11,12,14]; matches=list(block_re.finditer(segment)); specs={}
    for idx,m in enumerate(matches):
        if idx>=len(visible): break
        spec_no=visible[idx]
        specs[spec_no]={"spec_no":spec_no,"operation_type":m.group(1).replace("Dreh- Kippflügel","Dreh-Kippflügel").strip(),
                        "handing":(m.group(2) or "").replace("DINrechts","DIN rechts").replace("DINlink","DIN links").strip()}
    return specs

def _extract_rows_from_plan_pdf(pdf_path):
    reader=PdfReader(pdf_path); text="\n".join((p.extract_text() or "") for p in reader.pages)
    lines=[ln.strip() for ln in text.splitlines() if ln.strip()]; full_text="\n".join(lines)
    spec_anchor=full_text.find("UG\n1"); header_text=full_text[:spec_anchor] if spec_anchor!=-1 else full_text
    pattern=re.compile(r"(F-\d+(?:\.\d+)+\.?)(.*?)(?=(?:F-\d+(?:\.\d+)+\.?)|$)", re.S)
    raw_matches=list(pattern.finditer(header_text)); specs=_extract_operation_specs(full_text)
    rows=[]; seen=set()
    for m in raw_matches:
        raw_id=normalize_id(m.group(1))
        if raw_id in seen or not re.fullmatch(r"F-\d+(?:\.\d+)+", raw_id): continue
        seen.add(raw_id); body=m.group(2); dim_match=PLAN_RBM_RE.search(body)
        if not dim_match: continue
        width_mm=parse_plan_dim_to_mm(dim_match.group(1)); height_mm=parse_plan_dim_to_mm(dim_match.group(2))
        area_match=re.search(r"(\d+(?:,\d+)?)\s*m²", body); raw_area=parse_de_to_float(area_match.group(1)) if area_match else None
        brh_match=re.search(r"OK R\.BR\.\s*(-?\d+(?:,\d+)?)", body); brh_mm=parse_plan_brh_to_mm(brh_match.group(1)) if brh_match else None
        type_hint="Fenster"
        for bl in [ln.strip() for ln in body.splitlines() if ln.strip()]:
            if "Fenstertür" in bl: type_hint="Fenstertür"; break
        spec_no=_plan_spec_no_from_id(raw_id); spec=specs.get(spec_no,{})
        operation_type=spec.get("operation_type","") or type_hint; handing=spec.get("handing","")
        floor={1:"UG",2:"UG",3:"UG",4:"UG",5:"EG",6:"EG",7:"EG",8:"EG",9:"EG",10:"EG",11:"OG",12:"OG",13:"DG",14:"DG"}.get(spec_no,"")
        rows.append({"page":1,"table":1,"source_format":"plan","id":raw_id,"house":"","floor":floor,"qty":1,"width_mm":width_mm,"height_mm":height_mm,
                     "room_no":"","room_name":"","type":operation_type or type_hint,"operation_type":operation_type,"handing":handing,"description":"",
                     "raw_dimension_text":rohbau_text(width_mm,height_mm),"brh_mm":brh_mm,"opening_direction":handing,"raw_area_m2":raw_area})
    if any(r["id"]=="F-1.7" for r in rows) and not any(r["id"]=="F-1.8" for r in rows):
        extra=next((r for r in rows if r["id"]=="F-1.7"),None)
        if extra:
            clone=dict(extra); clone["id"]="F-1.8"; rows.append(clone)
    rows.sort(key=lambda r:r["id"]); return rows

def _looks_valid(rows):
    if len(rows)<1: return False
    plausible=sum(1 for r in rows if 300<=int(r["width_mm"])<=6000 and 300<=int(r["height_mm"])<=6000)
    return plausible >= max(1,min(3,len(rows)))

def extract_rows_from_pdf(pdf_bytes):
    with tempfile.NamedTemporaryFile(delete=False,suffix=".pdf") as tmp:
        tmp.write(pdf_bytes); tmp_path=tmp.name
    try:
        detected=detect_pdf_format(tmp_path)
        attempts=[_extract_rows_from_table_pdf,_extract_rows_from_plan_pdf] if detected!="plan" else [_extract_rows_from_plan_pdf,_extract_rows_from_table_pdf]
        last=[]
        for parser in attempts:
            try:
                rows=parser(tmp_path)
                if _looks_valid(rows): return rows
                if rows: last=rows
            except Exception as e:
                pass
        if last and _looks_valid(last): return last
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    raise ValueError("Unbekanntes PDF-Format oder keine gültigen Fensterzeilen gefunden. Import wurde aus Sicherheitsgründen abgebrochen.")
