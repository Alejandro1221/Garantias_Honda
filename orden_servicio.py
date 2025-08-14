import re
import fitz
import pytesseract
import io
from PIL import Image

from busqueda_motor import (
    extraer_motor_cerca_vin,
    obtener_modelo,
    obtener_casa_matriz,
    obtener_cobro_casamatriz,
    obtener_responsable,
)

def _ocr_desde_pdf(ruta_pdf: str, pagina_index: int, dpi: int = 600, lang: str = "eng+spa") -> str:
    with fitz.open(ruta_pdf) as doc:
        if not (0 <= pagina_index < len(doc)):
            return ""
        pagina = doc[pagina_index]
        pix = pagina.get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    return pytesseract.image_to_string(img, lang=lang)


def _ocr_desde_imagen(img_base: Image.Image, dpi_virtual: int = 500, lang: str = "eng+spa") -> str:

    if img_base is None:
        return ""
    base_dpi_aprox = 300
    # Limitar el factor para no explotar RAM/CPU
    escala = max(0.5, min(dpi_virtual / base_dpi_aprox, 2.0))
    w = max(1, int(img_base.width * escala))
    h = max(1, int(img_base.height * escala))
    img = img_base.resize((w, h), resample=Image.LANCZOS)
    return pytesseract.image_to_string(img, lang=lang)

def extraer_vin(texto):
    texto = texto.upper()
    patrones = [
        r"VIN[:\s-]*([A-HJ-NPR-Z0-9]{17})",
        r"CHASIS[:\s-]*([A-HJ-NPR-Z0-9]{17})",
        r"\b([A-HJ-NPR-Z0-9]{17})\b"
    ]
    for patron in patrones:
        m = re.search(patron, texto)
        if m:
            return m.group(1)
    return "No detectado"

def procesar_orden(
    archivo_pdf: str,
    campos,
    area_texto,
    pagina_index: int = 0,
    *,
    # Opcionales (modo rápido):
    imagen_pagina: Image.Image = None,  # si la pasas, evita reabrir PDF
    texto_ocr: str = None,              # si ya tienes OCR cacheado, úsalo directo
    # Parámetros de calidad (opcional):
    dpi_pdf_fallback: int = 700,        # mismo valor que usabas antes (retrocompat)
    dpi_virtual_from_base: int = 500,   # “dpi efectivo” al reescalar desde ~180
    lang: str = "eng+spa",
):
    # 1) OCR (elige la ruta más rápida disponible)
    if texto_ocr is None:
        if imagen_pagina is not None:
            # Modo rápido: escala digital desde la imagen base (~180 dpi)
            texto_ocr = _ocr_desde_imagen(imagen_pagina, dpi_virtual=dpi_virtual_from_base, lang=lang)
        else:
            # Retrocompat: render directo desde PDF (700 dpi por defecto)
            texto_ocr = _ocr_desde_pdf(archivo_pdf, pagina_index, dpi=dpi_pdf_fallback, lang=lang)

    area_texto.delete("1.0", "end")
    area_texto.insert("end", texto_ocr)

    # VIN 
    vin = extraer_vin(texto_ocr)
    campos[8].delete(0, "end")
    if vin != "No detectado":
        campos[8].insert(0, vin)

    motor = extraer_motor_cerca_vin(texto_ocr, vin if vin != "No detectado" else "")
    campos[9].delete(0, "end")
    if motor != "No detectado":
        campos[9].insert(0, motor)

        modelo = obtener_modelo(motor)
        campos[12].delete(0, "end")
        if modelo:  
            campos[12].insert(0, modelo)

        casamatriz = obtener_casa_matriz(motor)
        campos[13].delete(0, "end")  
        if casamatriz:
            campos[13].insert(0, casamatriz)
        
        cobro_casamatriz = obtener_cobro_casamatriz(motor)
        campos[25].delete(0, "end") 
        if cobro_casamatriz:
             
            campos[25].insert(0, cobro_casamatriz)
        
        responsable = obtener_responsable(motor)
        campos[26].delete(0, "end") 
        if responsable: 
            campos[26].insert(0, responsable)

      
