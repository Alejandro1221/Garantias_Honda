from BusquedaRef import buscar_referencias_en_texto, norm_ocr_para_refs, unir_lineas_cortadas
from PIL import Image
import pytesseract, fitz, io
from difflib import SequenceMatcher
from fechas import fecha_factura

from ia_factura import extraer_campos_factura 
MIN_REFS = 5 

# ---------- OCR helpers (solo para REFERENCIAS) ----------
def _ocr_desde_pdf(ruta_pdf: str, pagina_index: int, dpi: int = 700, lang: str = "eng+spa") -> str:
    with fitz.open(ruta_pdf) as doc:
        if not (0 <= pagina_index < len(doc)):
            return ""
        pix = doc[pagina_index].get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    return pytesseract.image_to_string(img, lang=lang)

def _ocr_desde_imagen(img_base: Image.Image, dpi_objetivo: int = 700, lang: str = "eng+spa") -> str:
    base_dpi = 180.0
    escala = max(0.5, min(dpi_objetivo / base_dpi, 2.0))
    w = max(1, int(img_base.width * escala))
    h = max(1, int(img_base.height * escala))
    img = img_base.resize((w, h), resample=Image.LANCZOS)
    return pytesseract.image_to_string(img, lang=lang)

def _ocr_roi_desde_pdf(ruta_pdf: str, pagina_index: int, dpi: int = 650, lang: str = "eng+spa", bottom_frac: float = 0.60) -> str:
    with fitz.open(ruta_pdf) as doc:
        if not (0 <= pagina_index < len(doc)):
            return ""
        page = doc[pagina_index]
        rect = page.rect
        clip = fitz.Rect(rect.x0, rect.y0 + rect.height * (1 - bottom_frac), rect.x1, rect.y1)
        mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
        pix = page.get_pixmap(matrix=mat, clip=clip)
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    # psm 6 = una o varias líneas, suele ir bien en tablas/listados
    return pytesseract.image_to_string(img, lang=lang, config="--oem 3 --psm 6")

def _ocr_roi_columna_codigos(ruta_pdf: str, pagina_index: int,
                             dpi: int = 650, lang: str = "eng+spa",
                             bottom_frac: float = 0.65, left_frac: float = 0.38) -> str:
    """
    Recorta la banda inferior (bottom_frac) y dentro de ella
    la franja IZQUIERDA (left_frac) donde suelen ir los códigos.
    """
    with fitz.open(ruta_pdf) as doc:
        if not (0 <= pagina_index < len(doc)):
            return ""
        page = doc[pagina_index]
        r = page.rect
        y0 = r.y0 + r.height * (1 - bottom_frac)  # banda inferior
        x1 = r.x0 + r.width  * left_frac          # columna izquierda
        clip = fitz.Rect(r.x0, y0, x1, r.y1)
        mat  = fitz.Matrix(dpi / 72.0, dpi / 72.0)
        pix  = page.get_pixmap(matrix=mat, clip=clip)

    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    cfg = "--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
    return pytesseract.image_to_string(img, lang=lang, config=cfg)

def _merge_refs(dst, src):
    if not dst:
        dst = []
    ya = {r.get("Referencia") for r in dst if r.get("Referencia")}
    for r in (src or []):
        ref = r.get("Referencia")
        if ref and ref not in ya:
            dst.append(r)
            ya.add(ref)
    return dst

def _prefijo5(ref: str) -> str:
    r = norm_ocr_para_refs(ref or "")
    token = r.split("-", 1)[0]
    token5 = (token or "")[:5]          
    if len(token5) == 5:
        return token5
    return r.replace("-", "")[:5]

def _mejor_idx_por_prefijo(ia_ref: str, resultados: list) -> int:
    if not ia_ref or not resultados:
        return -1
    pref5 = _prefijo5(ia_ref)
    if not pref5:
        return -1

    cand = []
    for i, r in enumerate(resultados):
        ref = r.get("Referencia", "")
        if _prefijo5(ref) == pref5:
            score = SequenceMatcher(None, norm_ocr_para_refs(ia_ref), norm_ocr_para_refs(ref)).ratio()
            cand.append((score, i))

    if cand:
        cand.sort(reverse=True)
        return cand[0][1]

    best = (-1.0, -1)
    ia_n = norm_ocr_para_refs(ia_ref)
    for i, r in enumerate(resultados):
        ref_n = norm_ocr_para_refs(r.get("Referencia", ""))
        score = SequenceMatcher(None, ia_n, ref_n).ratio()
        if score > best[0]:
            best = (score, i)
    return best[1]


# ---------- Flujo principal ----------
def procesar_factura(
    archivo_pdf: str,
    campos,
    area_texto,
    pagina_index: int = 0,
    imagen_pagina: Image.Image = None,   # imagen ya renderizada (si la tienes)
    texto_ocr: str = None,               # cache opcional de texto OCR
    texto_dpi_alto: str = None,          # no usado para IA; lo usamos para refs
 
):
    # ===== 1) IA -> número, total, mano_obra =====
    numero = total = mano_obra = fecha =""
    datos = {}
    if imagen_pagina is not None:
        try:
            datos = extraer_campos_factura(imagen_pagina) or {}
            numero    = (datos.get("numero_factura") or "").replace("-", "").replace(" ", "").strip()
            total     = (datos.get("total_factura") or "").strip()
            mano_obra = (datos.get("mano_obra") or "").strip()
            fecha = fecha_factura((datos.get("fecha_emision") or "").strip()) or ""

            ref_principal = datos.get("ref_principal", "")
            if ref_principal:
                print("[IA] Ref principal detectada:", ref_principal)
        except Exception as e:
            print("IA (numero/total/mano_obra) error:", e)
    print("=== DEBUG IA ===", datos) 

    # Pinta campos IA
    campos[0].delete(0, "end"); campos[0].insert(0, numero)   # Número factura
    campos[3].delete(0, "end"); campos[3].insert(0, numero)   # N° solicitud = número
    campos[28].delete(0, "end"); campos[28].insert(0, numero) # Factura interna
    campos[29].delete(0, "end"); campos[29].insert(0, total)  # Valor total factura
    campos[30].delete(0, "end"); campos[30].insert(0, mano_obra)  # Mano de obra
    campos[32].delete(0, "end"); campos[32].insert(0, fecha)  # Fecha emisión

    # Siempre usamos OCR propio a 400 DPI y lang="eng" para mejor lectura de códigos
    if texto_ocr is not None and not texto_dpi_alto:
        texto_dpi_alto = texto_ocr  # reutiliza cache si vino

    if texto_dpi_alto is None:
        if imagen_pagina is not None:
            texto_dpi_alto = _ocr_desde_imagen(imagen_pagina, dpi_objetivo=400, lang="eng+spa")
        else:
            texto_dpi_alto = _ocr_desde_pdf(archivo_pdf, pagina_index, dpi=400, lang="eng+spa")

    # Muestra OCR en el panel derecho
    texto_ui = unir_lineas_cortadas(texto_dpi_alto)
    area_texto.delete("1.0", "end")
    #area_texto.insert("end", texto_dpi_alto)
    area_texto.insert("end", texto_ui)

    # Detecta referencias en el texto OCR
    resultados = buscar_referencias_en_texto(texto_ui) or []
    print("Total referencias detectadas:", len(resultados))

    # 2) ROI inferior a 650 DPI
    if len(resultados) < MIN_REFS:
        try:
            texto_roi = _ocr_roi_desde_pdf(
                archivo_pdf, pagina_index, dpi=650, lang="eng+spa", bottom_frac=0.60
            )
            resultados_roi = buscar_referencias_en_texto(unir_lineas_cortadas(texto_roi)) or []
            resultados = _merge_refs(resultados, resultados_roi)
        except Exception as e:
            print("ROI error:", e)

    # 2.5) ROI columna de CÓDIGOS (muy barato y suele sacar el resto)
    if len(resultados) < MIN_REFS:
        try:
            texto_col = _ocr_roi_columna_codigos(
                archivo_pdf, pagina_index, dpi=650, lang="eng+spa",
                bottom_frac=0.65, left_frac=0.38
            )
            resultados_col = buscar_referencias_en_texto(unir_lineas_cortadas(texto_col)) or []
            resultados = _merge_refs(resultados, resultados_col)
        except Exception as e:
            print("ROI-col error:", e)

    # 3) Página completa a 650 DPI
    if len(resultados) < MIN_REFS:
        try:
            texto_full = _ocr_desde_pdf(archivo_pdf, pagina_index, dpi=650, lang="eng+spa")
            resultados_full = buscar_referencias_en_texto(unir_lineas_cortadas(texto_full)) or []
            resultados = _merge_refs(resultados, resultados_full)
        except Exception as e:
            print("FULL error:", e)

    # --- Reordenar poniendo primero la ref más parecida a la ref_principal de la IA ---
    ia_ref_principal = datos.get("ref_principal", "")  
    idx = _mejor_idx_por_prefijo(ia_ref_principal, resultados)
    if isinstance(idx, int) and idx >= 0:
        ganador = resultados.pop(idx)
        resultados.insert(0, ganador)

    # Campo 21 = referencias (códigos)
    campos[21].delete(0, "end")
    if resultados:
        refs = [r["Referencia"] for r in resultados if r.get("Referencia")]
        if refs:
            campos[21].insert(0, "/ ".join(refs))

    # Campo 22 = descripciones
    campos[22].delete(0, "end")
    if resultados:
        descs = [r["Descripcion"] for r in resultados if r.get("Descripcion")]
        if descs:
            campos[22].insert(0, " / ".join(descs))

    print("[IA] fecha_emision =", fecha) 




