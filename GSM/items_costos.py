import re
from BusquedaRef import buscar_referencias_en_texto, unir_lineas_cortadas, norm_ocr_para_refs, DESC_POR_REF

_PAT_IMPORTE = re.compile(r"([0-9]{1,3}(?:[.,][0-9]{3})+[.,]\d{2}|[0-9]+[.,]\d{2}|[0-9]{1,3}(?:[.,][0-9]{3})+)")
def _to_int_without_decimals(s: str) -> int:
    m = re.search(r"([.,])(\d{2})\s*$", s or "")
    has_decimal = bool(m)
    digits = re.sub(r"\D", "", s or "")
    if has_decimal and len(digits) > 2:
        digits = digits[:-2]
    return int(digits) if digits else 0

def _split_cols(line: str):
    if "|" in line:
        cols = [c.strip() for c in line.split("|")]
        if len(cols) >= 2:
            return cols
    parts = re.split(r"\s{2,}", line.strip())
    return parts if len(parts) >= 2 else [line.strip()]

def _mejor_ref_desc(line: str):
    rs = buscar_referencias_en_texto(line) or []
    if rs:
        ref = rs[0].get("Referencia","")
        return ref, DESC_POR_REF.get(ref, rs[0].get("Descripcion",""))
    return "", ""

def _letters(s: str) -> str:
    return re.sub(r"[^A-ZÁÉÍÓÚÜÑ]", "", (s or "").upper())

def _is_header(line: str) -> bool:
    n = _letters(line)
    keys = ["REFERENCIA","DESCRIPCION","CANTIDAD","UNIDAD","PRECIO","VALOR"]
    return sum(k in n for k in keys) >= 2

def _is_corte(line: str) -> bool:
    n = _letters(line)
    cortes = ["OBSERVACIONES","SUBTOTAL","VALORTOTAL","TOTALITEMS","IMPUESTOS","RETENCION","DEDUCIBLE","TOTALANTESDEIVA","VALORTOTALDELAOPERACION"]
    return any(k in n for k in cortes)

def _looks_like_item(line: str) -> bool:
    return bool(_PAT_IMPORTE.search(line))

def item_mas_costoso(texto: str, top_k: int = 1):
    t = unir_lineas_cortadas(texto or "")
    lines = [l for l in t.splitlines() if l.strip()]
    ini = None
    for i, l in enumerate(lines):
        if _is_header(l):
            ini = i + 1
            break
    if ini is None:
        for i, l in enumerate(lines):
            if _looks_like_item(l):
                ini = i
                break
    if ini is None:
        return None
    items = []
    i = ini
    while i < len(lines):
        l = lines[i].strip()
        if _is_corte(l):
            break
        blob = l
        j = i + 1
        while j < len(lines) and not _is_corte(lines[j]) and not _looks_like_item(blob):
            blob = blob + " " + lines[j].strip()
            j += 1
        if j < len(lines) and not _is_corte(lines[j]) and _looks_like_item(lines[j]) and not _looks_like_item(blob):
            blob = blob + " " + lines[j].strip()
            j += 1
        cols = _split_cols(blob)
        ref, desc = _mejor_ref_desc(blob)
        m = list(_PAT_IMPORTE.finditer(blob))
        valor = _to_int_without_decimals(m[-1].group(1)) if m else 0
        unit = _to_int_without_decimals(m[-2].group(1)) if len(m) >= 2 else 0
        qty = 0.0
        try:
            if len(cols) >= 3:
                qraw = re.sub(r"[^\d.,-]", "", cols[2])
                qraw = qraw.replace(".", "").replace(",", ".")
                qty = float(qraw) if qraw else 0.0
        except:
            qty = 0.0
        if valor > 0 and ref and ref in DESC_POR_REF and ref != "700000005":
            items.append({"ref": ref, "desc": desc, "valor": valor, "unitario": unit, "cantidad": qty, "raw": blob})
        i = max(i + 1, j)
    items.sort(key=lambda x: x["valor"], reverse=True)
    if not items:
        return None
    if top_k <= 1:
        return items[0]
    return items[:top_k]

def extraer_mano_obra(texto: str) -> int:
    t = unir_lineas_cortadas(texto or "")
    lines = [l for l in t.splitlines() if l.strip()]
    ini = None
    for i, l in enumerate(lines):
        if _is_header(l):
            ini = i + 1
            break
    if ini is None:
        for i, l in enumerate(lines):
            if _looks_like_item(l):
                ini = i
                break
    if ini is None:
        return 0
    max_val = 0
    i = ini
    while i < len(lines):
        l = lines[i].strip()
        if _is_corte(l):
            break
        blob = l
        j = i + 1
        while j < len(lines) and not _is_corte(lines[j]) and not _looks_like_item(blob):
            blob = blob + " " + lines[j].strip()
            j += 1
        if j < len(lines) and not _is_corte(lines[j]) and _looks_like_item(lines[j]) and not _looks_like_item(blob):
            blob = blob + " " + lines[j].strip()
            j += 1
        ref, desc = _mejor_ref_desc(blob)
        s = f"{ref} {desc} {blob}".upper()
        s = s.replace("Á","A").replace("É","E").replace("Í","I").replace("Ó","O").replace("Ú","U")
        if "CAMBIO DE PARTES" in s or re.search(r"\b700000005\b", s):
            m = list(_PAT_IMPORTE.finditer(blob))
            if m:
                v = _to_int_without_decimals(m[-1].group(1))
                if v > max_val:
                    max_val = v
        i = max(i + 1, j)
    return max_val

def imprimir_top_costosos(texto: str, k: int = 3):
    res = item_mas_costoso(texto, top_k=k)
    if not res:
        print("[COSTO] no se encontraron ítems con valor en la tabla de referencias")
        return
    if isinstance(res, dict):
        print(f"[COSTO][max] {res['ref']} | {res['desc']} | valor={res['valor']:,} | unit={res['unitario']:,} | qty={res['cantidad']}")
        return
    print(f"[COSTO][top {k}]")
    for i, it in enumerate(res, 1):
        print(f"{i}. {it['ref']} | {it['desc']} | valor={it['valor']:,} | unit={it['unitario']:,} | qty={it['cantidad']}")
