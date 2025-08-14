# pdf_io.py
from PIL import Image
import fitz
import io
import pytesseract

PDF_DPI = 180

def leer_pdf_con_ocr(ruta_pdf, lang="eng"):
    """Devuelve (textos_por_pagina: list[str], imagenes_por_pagina: list[PIL.Image])"""
    textos = []
    imagenes = []
    doc = fitz.open(ruta_pdf)
    for pagina in doc:
        pix = pagina.get_pixmap(dpi=PDF_DPI)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        imagenes.append(img)
        textos.append(pytesseract.image_to_string(img, lang=lang))
    return textos, imagenes
